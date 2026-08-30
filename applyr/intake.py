"""ui_intake CRUD — the Visual UI dashboard's paste/upload queue.

Mirrors the module split already used for offers: `db.py` owns schema and
migrations, `duplicates.py` owns the offer-matching queries, this module owns
the queries for one specific concern (see `docs/visual-ui/AGENTS.md`).
"""

import sqlite3

from applyr.db import get_conn

# ADR-014: how long a repeated paste of the same raw_text is treated as a
# double "Enviar" click (return the existing pending row) rather than a
# deliberate second submission (create a new one). Named constant, not a
# magic number, so it's a one-line change to retune.
IDEMPOTENCY_WINDOW_SECONDS = 10


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def create_intake(
    raw_text: str,
    source_note: str | None = None,
    db_path: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Insert a new pending intake row, or return the existing one if the
    same raw_text was submitted within IDEMPOTENCY_WINDOW_SECONDS and is
    still pending (guards a double "Enviar" click from creating two
    intake/job pairs for one paste). Raises ValueError if raw_text is blank.

    Accepts an existing, uncommitted `conn` so a caller can create the paired
    `ui_jobs` row in the same transaction (ADR-014) — same reasoning as
    `mark_intake_promoted`. When no `conn` is given, opens, commits, and
    closes its own, same as before.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text must not be empty")

    owns_conn = conn is None
    if owns_conn:
        conn = get_conn(db_path)
    try:
        existing = conn.execute(
            """SELECT * FROM ui_intake
               WHERE raw_text = ? AND status = 'pending'
                 AND created_at > datetime('now', ?)
               ORDER BY created_at DESC LIMIT 1""",
            (raw_text, f"-{IDEMPOTENCY_WINDOW_SECONDS} seconds"),
        ).fetchone()
        if existing is not None:
            return _row_to_dict(existing)

        cursor = conn.execute(
            "INSERT INTO ui_intake (raw_text, source_note) VALUES (?, ?)",
            (raw_text, source_note),
        )
        if owns_conn:
            conn.commit()
        row = conn.execute("SELECT * FROM ui_intake WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        if owns_conn:
            conn.close()


def list_intake(status: str | None = None, db_path: str | None = None) -> list[dict]:
    """List intake rows, newest first. Optionally filtered by status."""
    conn = get_conn(db_path)
    try:
        query = "SELECT * FROM ui_intake"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC, id DESC"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def get_intake(intake_id: int, db_path: str | None = None) -> dict | None:
    """Fetch one intake row by id, or None if it doesn't exist."""
    conn = get_conn(db_path)
    try:
        row = conn.execute("SELECT * FROM ui_intake WHERE id = ?", (intake_id,)).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def mark_intake_promoted(intake_id: int, offer_id: int, conn: sqlite3.Connection) -> None:
    """Flip a pending intake row to promoted, linked to offer_id.

    Takes an existing connection rather than opening its own, because this
    must run inside the same transaction as the offer insert it belongs to —
    `applyr add --intake-id` succeeds or fails as one unit, never leaving an
    orphaned offer with no linkage or a promoted row with no offer.

    Raises ValueError if the row doesn't exist or isn't status='pending' —
    the caller is expected to let that abort the whole `add`.
    """
    row = conn.execute("SELECT status FROM ui_intake WHERE id = ?", (intake_id,)).fetchone()
    if row is None:
        raise ValueError(f"No ui_intake row with id {intake_id}")
    if row["status"] != "pending":
        raise ValueError(f"ui_intake row {intake_id} is already '{row['status']}', not 'pending'")
    conn.execute(
        "UPDATE ui_intake SET status = 'promoted', offer_id = ?, promoted_at = CURRENT_TIMESTAMP WHERE id = ?",
        (offer_id, intake_id),
    )
