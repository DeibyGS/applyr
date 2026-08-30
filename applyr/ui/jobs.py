"""ui_jobs CRUD — the async intake pipeline's per-offer job state (ADR-014).

Mirrors the module split already used for offers and `ui_intake`: `db.py` owns
schema and migrations, this module owns the queries for one specific concern
(see docs/visual-ui/AGENTS.md).
"""

import json
import sqlite3

from applyr.db import VALID_JOB_STATES, get_conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    data = dict(row)
    if data.get("structured_data"):
        data["structured_data"] = json.loads(data["structured_data"])
    return data


def create_job(intake_id: int, conn: sqlite3.Connection) -> dict:
    """Insert a new `queued` job row for `intake_id`.

    Takes an existing connection rather than opening its own, so callers can
    create the paired `ui_intake` + `ui_jobs` rows in one transaction — same
    reasoning as `intake.mark_intake_promoted`. Does not commit; the caller
    owns the transaction boundary.
    """
    cursor = conn.execute("INSERT INTO ui_jobs (intake_id) VALUES (?)", (intake_id,))
    row = conn.execute("SELECT * FROM ui_jobs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_dict(row)


def get_job_by_intake(intake_id: int, db_path: str | None = None) -> dict | None:
    """Fetch the job row paired with `intake_id`, or None if none exists."""
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM ui_jobs WHERE intake_id = ?", (intake_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def list_jobs_by_state(*states: str, db_path: str | None = None) -> list[dict]:
    """List jobs currently in any of `states`, oldest first (FIFO claim order)."""
    if not states:
        return []
    conn = get_conn(db_path)
    try:
        placeholders = ", ".join("?" for _ in states)
        rows = conn.execute(
            f"SELECT * FROM ui_jobs WHERE state IN ({placeholders}) ORDER BY created_at ASC",
            states,
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def update_job_state(
    intake_id: int,
    state: str,
    *,
    structured_data: dict | None = None,
    extraction_method: str | None = None,
    duplicate_of_offer_id: int | None = None,
    failed_step: str | None = None,
    error_message: str | None = None,
    db_path: str | None = None,
) -> dict:
    """Transition the job for `intake_id` to `state`.

    `structured_data`/`extraction_method`/`duplicate_of_offer_id` are sticky —
    once set they persist across later transitions unless a caller passes a
    new value. `failed_step`/`error_message` are not — they are overwritten
    on every call, so leaving a job's previous failure behind once it moves
    past `failed` requires no separate clearing step.

    Raises ValueError if `state` isn't a valid job state or no job exists for
    `intake_id`.
    """
    if state not in VALID_JOB_STATES:
        raise ValueError(f"invalid job state: {state}")
    conn = get_conn(db_path)
    try:
        existing = conn.execute(
            "SELECT id FROM ui_jobs WHERE intake_id = ?", (intake_id,)
        ).fetchone()
        if existing is None:
            raise ValueError(f"No ui_jobs row for intake_id {intake_id}")
        conn.execute(
            """UPDATE ui_jobs SET
                state = ?,
                structured_data = COALESCE(?, structured_data),
                extraction_method = COALESCE(?, extraction_method),
                duplicate_of_offer_id = COALESCE(?, duplicate_of_offer_id),
                failed_step = ?,
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE intake_id = ?""",
            (
                state,
                json.dumps(structured_data) if structured_data is not None else None,
                extraction_method,
                duplicate_of_offer_id,
                failed_step,
                error_message,
                intake_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM ui_jobs WHERE intake_id = ?", (intake_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def retry_job(intake_id: int, db_path: str | None = None) -> dict:
    """Reset a `failed` job back to `queued`, clearing failure fields and
    incrementing `retry_count`. Raises ValueError if the job isn't `failed`
    (retries are never automatic — this is always a manual client action)."""
    conn = get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT state FROM ui_jobs WHERE intake_id = ?", (intake_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No ui_jobs row for intake_id {intake_id}")
        if row["state"] != "failed":
            raise ValueError(
                f"ui_jobs row for intake_id {intake_id} is '{row['state']}', not 'failed'"
            )
        conn.execute(
            """UPDATE ui_jobs SET
                state = 'queued',
                failed_step = NULL,
                error_message = NULL,
                retry_count = retry_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE intake_id = ?""",
            (intake_id,),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM ui_jobs WHERE intake_id = ?", (intake_id,)).fetchone()
        return _row_to_dict(updated)
    finally:
        conn.close()
