"""ui_intake CRUD — the Visual UI dashboard's paste/upload queue.

Mirrors the module split already used for offers: `db.py` owns schema and
migrations, `duplicates.py` owns the offer-matching queries, this module owns
the queries for one specific concern (see `docs/visual-ui/AGENTS.md`).
"""

import sqlite3

from applyr.db import get_conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def create_intake(raw_text: str, source_note: str | None = None, db_path: str | None = None) -> dict:
    """Insert a new pending intake row. Raises ValueError if raw_text is blank."""
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text must not be empty")
    conn = get_conn(db_path)
    try:
        cursor = conn.execute(
            "INSERT INTO ui_intake (raw_text, source_note) VALUES (?, ?)",
            (raw_text, source_note),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM ui_intake WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
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
