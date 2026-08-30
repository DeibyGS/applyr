"""Async intake pipeline worker (ADR-014) — replaces the SSE-keyword-triggered
`autopilot.py` daemon.

Runs in-process with `applyr ui` (no separate command, no Redis/Celery — see
ADR-014 and docs/visual-ui/AGENTS.md's "Explicitly rejected" list). Drives
`ui_jobs.state` through the deterministic steps only:

    queued -> structuring -> deduping -> duplicate
                                       -> pending_agent

`pending_agent` is a hard stop: only an attended agent's `applyr add
--intake-id` (external CLI process) advances a job past it, via
`ui_events.notify_job_state()`. This module never calls an LLM API and never
scores an offer — reaffirms ADR-003.

`structured_data` is always a hint for the attended agent, never
authoritative — the agent still verifies it against cv-master.md
(AGENTS.md core principle #1), the same as every other value applyr surfaces.
"""

from __future__ import annotations

import asyncio
import re
from typing import Callable

from applyr.db import get_conn
from applyr.duplicates import find_exact
from applyr.intake import get_intake
from applyr.ui import jobs

EventCallback = Callable[[dict], None]

# Explicit labels win over the first-two-lines heuristic — a label is a
# deliberate signal from whoever pasted the text, the heuristic is a guess.
# Bilingual (ES/EN): postings pasted into this UI mix both languages.
_LABEL_PATTERNS: dict[str, re.Pattern[str]] = {
    "company": re.compile(r"^(?:empresa|compañ[íi]a|company)\s*:\s*(.+)$", re.IGNORECASE),
    "title": re.compile(
        r"^(?:puesto|t[íi]tulo|cargo|posici[óo]n|position|role|title|rol)\s*:\s*(.+)$",
        re.IGNORECASE,
    ),
    "tech_stack": re.compile(
        r"^(?:stack|tech|tecnolog[íi]as|technologies)\s*:\s*(.+)$", re.IGNORECASE
    ),
}


def extract_structured_data(raw_text: str) -> dict:
    """Extract company/title/tech_stack from pasted offer text.

    Falls back to the first two non-blank lines (this UI's original
    heuristic) only for whichever fields no label matched.
    `extraction_method` is "labeled" only when every extracted field came
    from an explicit label — otherwise "heuristic", so the agent knows to
    double-check before trusting it.
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

    labeled: dict[str, str] = {}
    for line in lines:
        for field, pattern in _LABEL_PATTERNS.items():
            if field in labeled:
                continue
            match = pattern.match(line)
            if match:
                labeled[field] = match.group(1).strip()

    company = labeled.get("company")
    title = labeled.get("title")
    used_heuristic = "company" not in labeled or "title" not in labeled

    if company is None:
        company = lines[0] if lines else None
    if title is None:
        title = lines[1] if len(lines) > 1 else None

    return {
        "company": company,
        "title": title,
        "tech_stack": labeled.get("tech_stack"),
        "extraction_method": "heuristic" if used_heuristic else "labeled",
    }


def _find_duplicate_offer_id(structured: dict, db_path: str | None = None) -> int | None:
    """Same definition `applyr search --company`/`add` already use: exact
    title+company match, case/accent-insensitive (`duplicates.find_exact`)."""
    if not structured.get("company") or not structured.get("title"):
        return None
    conn = get_conn(db_path)
    try:
        row = find_exact(conn, structured["title"], structured["company"])
        return row["id"] if row else None
    finally:
        conn.close()


def _emit(on_event: EventCallback | None, job: dict, state: str, **extra: object) -> None:
    if on_event is None:
        return
    event = {
        "type": "job.state_changed",
        "intake_id": job["intake_id"],
        "job_id": job["id"],
        "state": state,
    }
    event.update(extra)
    on_event(event)


def process_one_job(
    job: dict, *, on_event: EventCallback | None = None, db_path: str | None = None
) -> dict:
    """Run a `queued`/`structuring` job through to `duplicate` or
    `pending_agent`. Synchronous and side-effect-only — safe to call
    directly from tests without asyncio."""
    intake_id = job["intake_id"]
    intake_row = get_intake(intake_id, db_path=db_path)

    job = jobs.update_job_state(intake_id, "structuring", db_path=db_path)
    _emit(on_event, job, "structuring")

    structured = extract_structured_data(intake_row["raw_text"])

    job = jobs.update_job_state(
        intake_id,
        "deduping",
        structured_data=structured,
        extraction_method=structured["extraction_method"],
        db_path=db_path,
    )
    _emit(on_event, job, "deduping")

    duplicate_offer_id = _find_duplicate_offer_id(structured, db_path=db_path)

    if duplicate_offer_id is not None:
        job = jobs.update_job_state(
            intake_id, "duplicate", duplicate_of_offer_id=duplicate_offer_id, db_path=db_path
        )
        _emit(on_event, job, "duplicate", duplicate_of_offer_id=duplicate_offer_id)
        return job

    job = jobs.update_job_state(intake_id, "pending_agent", db_path=db_path)
    _emit(on_event, job, "pending_agent", structured_data=structured)
    return job


def process_pending_jobs(*, on_event: EventCallback | None = None, db_path: str | None = None) -> int:
    """Process every claimable job — `queued` (normal case) and
    `structuring` (a job a previous worker process was interrupted on,
    reprocessed from scratch: `process_one_job` is a pure function of
    `raw_text`, safe to re-run). Returns how many jobs were processed."""
    claimable = jobs.list_jobs_by_state("queued", "structuring", db_path=db_path)
    for job in claimable:
        process_one_job(job, on_event=on_event, db_path=db_path)
    return len(claimable)


async def run_worker(
    wake_event: asyncio.Event,
    *,
    on_event: EventCallback | None = None,
    poll_interval: float = 2.0,
    db_path: str | None = None,
) -> None:
    """Poll loop: drains every claimable job, then sleeps until `poll_interval`
    elapses or `wake_event` is set (a new job was just submitted) — whichever
    comes first. Runs until the task is cancelled (`applyr ui`'s shutdown)."""
    while True:
        process_pending_jobs(on_event=on_event, db_path=db_path)
        try:
            await asyncio.wait_for(wake_event.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass
        wake_event.clear()
