"""HTTP routes for the Visual UI backend.

Reads/writes only through applyr's existing `db.py` and `intake.py`. Never
scores, judges, or reasons about an offer — that stays the AI coding agent's
job (ADR-003). This module is the read/intake surface only.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from applyr.commands.analytics import _stats_payload, _trends_payload
from applyr.config import load_config
from applyr.db import get_conn
from applyr.intake import create_intake, get_intake, list_intake

router = APIRouter()

# Core offer columns for the list view — matches the spec's "core fields"
# scope for GET /api/jobs. The full row (all columns) is only returned by
# GET /api/jobs/{id}, alongside the topic breakdown.
_JOB_LIST_COLUMNS = (
    "id, title, company, status, compatibility_pct, work_mode, location, "
    "seniority_level, role_category, created_at, date_applied"
)


class IntakeCreate(BaseModel):
    raw_text: str
    source_note: str | None = None


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


@router.post("/api/intake", status_code=201)
def post_intake(body: IntakeCreate) -> dict:
    if not body.raw_text or not body.raw_text.strip():
        raise HTTPException(status_code=422, detail="raw_text must not be empty")
    return create_intake(body.raw_text, body.source_note)


@router.get("/api/intake")
def get_intake_list(status: str | None = Query(default=None)) -> list[dict]:
    return list_intake(status=status)


@router.get("/api/intake/{intake_id}")
def get_intake_one(intake_id: int) -> dict:
    row = get_intake(intake_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No intake row with id {intake_id}")
    return row


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


@router.get("/api/stats")
def get_stats() -> dict:
    """Same aggregate payload as `applyr stats --json` (funnel, channel/work-mode
    breakdown, salary, score calibration) — reuses `_stats_payload`, never
    reimplements the aggregation SQL here."""
    conn = get_conn()
    try:
        payload = _stats_payload(conn)
    finally:
        conn.close()
    if payload is None:
        return {"total": 0}
    return payload


@router.get("/api/trends")
def get_trends(period: str = Query(default="week")) -> list[dict]:
    """Same payload as `applyr trends --period <p> --json` — reuses
    `_trends_payload`, never reimplements the aggregation SQL here."""
    if period not in ("week", "month"):
        raise HTTPException(status_code=400, detail="period must be 'week' or 'month'")
    conn = get_conn()
    try:
        return _trends_payload(conn, period)
    finally:
        conn.close()
