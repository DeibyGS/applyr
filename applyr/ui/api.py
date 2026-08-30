"""HTTP routes for the Visual UI backend.

Reads/writes only through applyr's existing `db.py` and `intake.py`. Never
scores, judges, or reasons about an offer — that stays the AI coding agent's
job (ADR-003). This module is the read/intake surface only.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from applyr.commands.analytics import _stats_payload, _trends_payload
from applyr.commands.workflow import _check_cv_master
from applyr.config import load_config
from applyr.cv import get_cv_master_path
from applyr.cv_master import inspect_cv_master
from applyr.db import (
    VALID_CHANNELS,
    VALID_PIPELINE_STAGES,
    VALID_ROLE_CATEGORIES,
    VALID_SENIORITY,
    VALID_WORK_MODES,
    get_conn,
)
from applyr.intake import create_intake, get_intake, list_intake
from applyr.ui import jobs as pipeline_jobs

router = APIRouter()

# Applyr World Phase 2 (ADR-013): every currently-connected GET /api/events
# client has its own queue here. POST /api/internal/pipeline-stage fans an
# event out to all of them. Process-local by design — this is a single-user,
# single-process local tool (ADR-011); no cross-process broker needed.
_event_subscribers: set[asyncio.Queue] = set()

# Enriched event subscribers (Phase 1: granular agent events)
_enriched_event_subscribers: set[asyncio.Queue] = set()

# Async intake pipeline (ADR-014). Set by `POST /api/intake` and the retry
# endpoint right after a job becomes claimable, so the in-process worker
# (server.py wires this same Event into `pipeline_worker.run_worker`) reacts
# immediately instead of waiting for its next poll tick.
_worker_wake_event: asyncio.Event = asyncio.Event()


def _broadcast_enriched(event: dict) -> None:
    """Fan `event` out to every connected `/api/events/enriched` client.

    Shared by every producer of enriched events — external ones arriving via
    `POST /api/internal/agent-event`/`/api/agent-response`, and the
    in-process pipeline worker (server.py passes this function straight to
    `pipeline_worker.run_worker` as its `on_event` callback, no HTTP hop
    needed since the worker runs in this same process).
    """
    for queue in list(_enriched_event_subscribers):
        queue.put_nowait(event)

# Core offer columns for the list view — matches the spec's "core fields"
# scope for GET /api/jobs. The full row (all columns) is only returned by
# GET /api/jobs/{id}, alongside the topic breakdown.
_JOB_LIST_COLUMNS = (
    "id, title, company, status, compatibility_pct, work_mode, location, "
    "seniority_level, role_category, created_at, date_applied, pipeline_stage"
)


class IntakeCreate(BaseModel):
    raw_text: str
    source_note: str | None = None


class PipelineStageEvent(BaseModel):
    offer_id: int
    stage: str


class AgentEvent(BaseModel):
    type: str
    agent_id: str
    timestamp: str
    correlation_id: str
    offer_id: int | None = None
    payload: dict | None = None


class AgentResponse(BaseModel):
    agent_id: str
    message: str
    correlation_id: str | None = None


class JobStateEvent(BaseModel):
    intake_id: int
    state: str
    error_message: str | None = None


class PipelineStageConfig(BaseModel):
    id: str
    name: str
    position: dict
    inputs: list[str]
    outputs: list[str]
    next_stages: list[str]


class PipelineConfigResponse(BaseModel):
    pipeline: dict


@router.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/api/config")
def get_config() -> dict:
    """Read-only view of the score thresholds the frontend needs to color-code
    compatibility scores correctly. Deliberately narrow: never the full config
    file, which can hold local filesystem details (e.g. chrome_path) with no
    reason to leave the machine, even over loopback."""
    general = load_config()["general"]
    return {
        "threshold_apply": general["threshold_apply"],
        "threshold_maybe": general["threshold_maybe"],
    }


@router.get("/api/pipeline-config")
def get_pipeline_config() -> dict:
    """Read-only view of the pipeline definition for the Visual UI.
    Returns the merged config (user overrides + built-in defaults)."""
    config = load_config()
    pipeline_config = config.get("pipeline", {})
    return {
        "pipeline": pipeline_config,
    }


@router.get("/api/settings")
def get_settings() -> dict:
    """Read-only view of scoring thresholds, per-topic weights, and CV Master
    health. Reuses `doctor`'s `_check_cv_master()` for the "is the profile still
    a blank template" logic rather than reimplementing it, but strips the local
    filesystem path out of its message before responding — same boundary
    `GET /api/config` already draws for chrome_path etc. (never a local path
    over the API, even on loopback). Coupled to `_check_cv_master()`'s exact two
    message formats ("OK (<path>, N words...)" / "NOT FOUND — <path>") by
    design — if that formatting changes, this sanitization needs updating too."""
    config = load_config()
    general = config["general"]

    check = _check_cv_master()
    # Derived from the already-loaded `config` rather than a second
    # get_cv_master_path() call (which would re-parse applyr.toml on its own)
    # — _check_cv_master() still does its own internal load, but this keeps
    # this route to 2 parses instead of 3.
    cv_master_path = os.path.expanduser(config["cv"]["cv_master"])
    if check["status"] == "ok":
        message = check["message"].replace(f"({cv_master_path}, ", "(")
    elif cv_master_path in check["message"]:
        message = "NOT FOUND — run 'applyr init' to create a template."
    else:
        message = check["message"]

    return {
        "threshold_apply": general["threshold_apply"],
        "threshold_maybe": general["threshold_maybe"],
        "weights": config["weights_raw"],
        "cv_master_status": "ok" if check["status"] == "ok" else "warning",
        "cv_master_message": message,
    }


@router.get("/api/cv-master")
def get_cv_master_status_route() -> dict:
    """Read-only CV Master health check. Returns filled status, word count,
    and reason when unfilled. Reuses inspect_cv_master() — never reimplements
    the template-detection logic."""
    path = get_cv_master_path()
    if not path.exists():
        return {"filled": False, "content_words": 0, "reason": "File not found — run 'applyr init'."}
    report = inspect_cv_master(path.read_text(encoding="utf-8"))
    return {
        "filled": report.filled,
        "content_words": report.content_words,
        "reason": None if report.filled else report.reason,
    }


@router.get("/api/cv-master/content")
def get_cv_master_content_route() -> dict:
    """Return the raw markdown content of cv-master.md. Returns 404 when the
    file does not exist (distinct from 'exists but unfilled')."""
    path = get_cv_master_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="cv-master.md not found — run 'applyr init'.")
    return {"content": path.read_text(encoding="utf-8")}


@router.post("/api/intake", status_code=201)
def post_intake(body: IntakeCreate) -> dict:
    """Creates the `ui_intake` row and its paired `ui_jobs` row (ADR-014) in
    one transaction, then wakes the worker. Idempotent: a resubmit of the
    same `raw_text` within `intake.IDEMPOTENCY_WINDOW_SECONDS` returns the
    existing pending row's job instead of creating a second one — the worker
    is still woken in that case, harmlessly, in case it was somehow missed."""
    if not body.raw_text or not body.raw_text.strip():
        raise HTTPException(status_code=422, detail="raw_text must not be empty")
    conn = get_conn()
    try:
        intake_row = create_intake(body.raw_text, body.source_note, conn=conn)
        job_row = pipeline_jobs.get_job_by_intake(intake_row["id"])
        if job_row is None:
            job_row = pipeline_jobs.create_job(intake_row["id"], conn)
        conn.commit()
    finally:
        conn.close()
    _worker_wake_event.set()
    return {**intake_row, "job": job_row}


@router.get("/api/intake")
def get_intake_list(status: str | None = Query(default=None)) -> list[dict]:
    rows = list_intake(status=status)
    for row in rows:
        row["job"] = pipeline_jobs.get_job_by_intake(row["id"])
    return rows


@router.get("/api/intake/{intake_id}")
def get_intake_one(intake_id: int) -> dict:
    row = get_intake(intake_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No intake row with id {intake_id}")
    row["job"] = pipeline_jobs.get_job_by_intake(intake_id)
    return row


@router.post("/api/intake/{intake_id}/retry")
def post_intake_retry(intake_id: int) -> dict:
    """Manually resets a `failed` job back to `queued` (ADR-014 — retries are
    never automatic). 404 if there's no job for `intake_id`, 409 if the job
    exists but isn't `failed`."""
    existing = pipeline_jobs.get_job_by_intake(intake_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No job for intake_id {intake_id}")
    if existing["state"] != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Job for intake_id {intake_id} is '{existing['state']}', not 'failed'",
        )
    job_row = pipeline_jobs.retry_job(intake_id)
    _worker_wake_event.set()
    return job_row


@router.post("/api/internal/job-state", status_code=204)
async def post_job_state(body: JobStateEvent) -> None:
    """Internal-only — called by the CLI's `notify_job_state()` (ADR-014)
    when an attended agent's `applyr add --intake-id` completes. Only
    `applyr add --intake-id` drives a job past `pending_agent`; nothing in
    this backend does it automatically. Not part of the CLI's `--json`
    compatibility surface — free to change, same treatment as
    `/api/internal/pipeline-stage`."""
    if body.state not in ("ready", "failed"):
        raise HTTPException(
            status_code=422, detail=f"invalid job state for this endpoint: {body.state}"
        )
    existing = pipeline_jobs.get_job_by_intake(body.intake_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No job for intake_id {body.intake_id}")
    job_row = pipeline_jobs.update_job_state(
        body.intake_id,
        body.state,
        failed_step="pending_agent" if body.state == "failed" else None,
        error_message=body.error_message,
    )
    _broadcast_enriched(
        {
            "type": "job.state_changed",
            "intake_id": body.intake_id,
            "job_id": job_row["id"],
            "state": body.state,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
    )


@router.get("/api/jobs")
def get_jobs() -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT {_JOB_LIST_COLUMNS} FROM offers ORDER BY created_at DESC, id DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


@router.get("/api/jobs/{job_id}")
def get_job_detail(job_id: int) -> dict:
    conn = get_conn()
    try:
        offer = conn.execute("SELECT * FROM offers WHERE id = ?", (job_id,)).fetchone()
        if offer is None:
            raise HTTPException(status_code=404, detail=f"No offer with id {job_id}")
        topics = conn.execute(
            "SELECT topic, score, detail, confidence FROM offer_topics WHERE offer_id = ?",
            (job_id,),
        ).fetchall()
        result = dict(offer)
        result["topics"] = [dict(topic) for topic in topics]
        return result
    finally:
        conn.close()


def _validate_analytics_filters(work_mode: str | None, canal: str | None,
                                 seniority_level: str | None, role_category: str | None) -> None:
    """Reject a filter value outside its existing `VALID_*` enum (db.py) with
    a 400 rather than silently applying a no-op WHERE clause that would just
    match zero rows — see analytics-filters-and-fixes spec."""
    if work_mode is not None and work_mode not in VALID_WORK_MODES:
        raise HTTPException(status_code=400, detail=f"work_mode must be one of {VALID_WORK_MODES}")
    if canal is not None and canal not in VALID_CHANNELS:
        raise HTTPException(status_code=400, detail=f"canal must be one of {VALID_CHANNELS}")
    if seniority_level is not None and seniority_level not in VALID_SENIORITY:
        raise HTTPException(status_code=400, detail=f"seniority_level must be one of {VALID_SENIORITY}")
    if role_category is not None and role_category not in VALID_ROLE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"role_category must be one of {VALID_ROLE_CATEGORIES}")


@router.get("/api/stats")
def get_stats(
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    work_mode: str | None = Query(default=None),
    canal: str | None = Query(default=None),
    seniority_level: str | None = Query(default=None),
    role_category: str | None = Query(default=None),
) -> dict:
    """Same aggregate payload as `applyr stats --json` (funnel, channel/work-mode
    breakdown, salary, score calibration) — reuses `_stats_payload`, never
    reimplements the aggregation SQL here. All filter params are optional and
    AND-combined (see `_analytics_filter_clause`)."""
    _validate_analytics_filters(work_mode, canal, seniority_level, role_category)
    conn = get_conn()
    try:
        payload = _stats_payload(
            conn, date_from=date_from, date_to=date_to, work_mode=work_mode,
            canal=canal, seniority_level=seniority_level, role_category=role_category,
        )
    finally:
        conn.close()
    if payload is None:
        return {"total": 0}
    return payload


@router.get("/api/trends")
def get_trends(
    period: str = Query(default="week"),
    date_from: str | None = Query(default=None, alias="from"),
    date_to: str | None = Query(default=None, alias="to"),
    work_mode: str | None = Query(default=None),
    canal: str | None = Query(default=None),
    seniority_level: str | None = Query(default=None),
    role_category: str | None = Query(default=None),
) -> list[dict]:
    """Same payload as `applyr trends --period <p> --json` — reuses
    `_trends_payload`, never reimplements the aggregation SQL here. Accepts
    the same optional filter params as `/api/stats`, in addition to `period`."""
    if period not in ("week", "month"):
        raise HTTPException(status_code=400, detail="period must be 'week' or 'month'")
    _validate_analytics_filters(work_mode, canal, seniority_level, role_category)
    conn = get_conn()
    try:
        return _trends_payload(
            conn, period, date_from=date_from, date_to=date_to, work_mode=work_mode,
            canal=canal, seniority_level=seniority_level, role_category=role_category,
        )
    finally:
        conn.close()


@router.post("/api/internal/pipeline-stage", status_code=204)
async def post_pipeline_stage(body: PipelineStageEvent) -> None:
    """Internal-only — called by the CLI's `notify_stage()` (ADR-013), never
    by the frontend directly. Not part of the CLI's `--json` compatibility
    surface (docs/adr/007-structured-json-errors.md): free to change without
    the guarantees that give. The CLI already wrote `pipeline_stage` to the
    database itself before calling this; this endpoint only fans the event
    out to connected `GET /api/events` clients, it never persists anything.
    `pipeline_stage_at` is stamped here, at receipt, rather than passed by
    the CLI — it's an informational broadcast timestamp for the frontend,
    not required to match the DB row's stored value to the second."""
    if body.stage not in VALID_PIPELINE_STAGES:
        raise HTTPException(status_code=422, detail=f"invalid stage: {body.stage}")
    payload = {
        "offer_id": body.offer_id,
        "stage": body.stage,
        "pipeline_stage_at": datetime.now(timezone.utc).isoformat(),
    }
    for queue in list(_event_subscribers):
        queue.put_nowait(payload)


@router.post("/api/internal/agent-event", status_code=204)
async def post_agent_event(body: AgentEvent) -> None:
    """Internal-only — called by the CLI's `notify_event()` for granular
    agent lifecycle events. Fans out to all connected enriched event clients.
    Never persists anything — pure broadcast."""
    # Validate event type
    valid_types = {
        "agent.started",
        "agent.command",
        "agent.output",
        "agent.completed",
        "agent.failed",
        "agent.waiting",
        "agent.blocked",
        "agent.receiving",
        "handoff.started",
        "handoff.walking",
        "handoff.completed",
        "pipeline.stage",
        "user.response",
    }
    if body.type not in valid_types:
        raise HTTPException(status_code=422, detail=f"invalid event type: {body.type}")

    # Validate agent_id
    valid_agents = {"recruiter", "matching", "cv", "ats", "application"}
    if body.agent_id not in valid_agents:
        raise HTTPException(status_code=422, detail=f"invalid agent_id: {body.agent_id}")

    # Stamp receipt time if not provided
    event = body.model_dump()
    event["received_at"] = datetime.now(timezone.utc).isoformat()

    _broadcast_enriched(event)


@router.post("/api/agent-response", status_code=204)
async def post_agent_response(body: AgentResponse) -> None:
    """User-to-agent response endpoint. Persists the response in agent_responses
    and broadcasts a user.response event to all connected SSE clients so the
    frontend live transcript shows it immediately."""
    valid_agents = {"recruiter", "matching", "cv", "ats", "application"}
    if body.agent_id not in valid_agents:
        raise HTTPException(status_code=422, detail=f"invalid agent_id: {body.agent_id}")

    # Persist to DB so the CLI can read it via `applyr doctor`
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO agent_responses (agent_id, message) VALUES (?, ?)",
            (body.agent_id, body.message),
        )
        conn.commit()
    finally:
        conn.close()

    # Broadcast SSE so the frontend live transcript shows it immediately
    event = {
        "type": "user.response",
        "agent_id": body.agent_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "correlation_id": body.correlation_id or str(uuid.uuid4()),
        "payload": {"message": body.message},
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    _broadcast_enriched(event)


@router.get("/api/events")
async def stream_events() -> StreamingResponse:
    """Server-Sent Events stream of real pipeline-stage transitions
    (ADR-013). Receive-only from the frontend's perspective — the reason SSE
    was chosen over WebSocket. On load or reconnect the frontend is expected
    to fetch current state via GET /api/jobs itself; this stream only ever
    carries transitions that happen while a client is connected, never a
    backlog (spec's "no retroactive replay" rule)."""

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        _event_subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            _event_subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/events/enriched")
async def stream_enriched_events() -> StreamingResponse:
    """Server-Sent Events stream of granular agent lifecycle events (Phase 1).
    Carries agent.started, agent.command, agent.output, agent.completed,
    agent.failed, agent.waiting, agent.blocked, handoff.*, and pipeline.stage.
    Same no-retroactive-replay rule as /api/events."""

    async def event_generator():
        queue: asyncio.Queue = asyncio.Queue()
        _enriched_event_subscribers.add(queue)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            _enriched_event_subscribers.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
