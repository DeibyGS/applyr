"""CLI command implementations for applyr job application tracker."""

import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from applyr.config import APPLYR_DIR, create_default_config, load_config
from applyr.db import (
    VALID_CHANNELS,
    VALID_SENIORITY,
    VALID_STATUSES,
    VALID_WORK_MODES,
    STATUS_LABELS,
    get_conn,
    get_db_path,
    init_db,
)
from applyr.scoring import calculate_score

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CV_MASTER_TEMPLATE = """\
# CV Master — {name}

## Summary
...

## Experience
...

## Education
...

## Skills
...
"""

_STATUS_ORDER = ["applied", "waiting", "in_process", "offer", "pending", "discarded", "rejected"]


def _today() -> str:
    """Return today's date as ISO string."""
    return date.today().isoformat()


def _make_display_row(r) -> dict:
    """Convert a sqlite3.Row from offers into a table-ready display dict."""
    return {
        "ID": str(r["id"]),
        "COMPANY": _truncate(r["company"] or "—", 18),
        "TITLE": _truncate(r["title"], 28),
        "%": str(r["compatibility_pct"]),
        "STATUS": STATUS_LABELS.get(r["status"], r["status"]),
        "MODE": r["work_mode"] or "—",
        "DATE": r["date_applied"] or r["date_received"] or "—",
    }


def _bar(score: int, width: int = 20) -> str:
    """Render a simple ASCII progress bar for a 0-100 score."""
    filled = round(score * width / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _truncate(text: str | None, max_len: int) -> str:
    """Truncate a string to max_len characters, appending ellipsis if needed."""
    if not text:
        return ""
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _parse_date(raw: str | None) -> str | None:
    """Validate and normalise a date string to ISO format (YYYY-MM-DD)."""
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None  # Unrecognised format — caller decides what to do


def _print_table(rows: list[dict], headers: list[str], col_widths: list[int]) -> None:
    """Print a fixed-width ASCII table."""
    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"
    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for row in rows:
        print(fmt.format(*[_truncate(str(row.get(h, "")), col_widths[i]) for i, h in enumerate(headers)]))
    print(sep)


# ---------------------------------------------------------------------------
# cmd_init
# ---------------------------------------------------------------------------

def cmd_init() -> None:
    """Initialise the ~/.applyr directory, config, and database."""
    print("Initialising applyr...")

    create_default_config()
    init_db()
    print(f"  Database ready at {get_db_path()}")

    # Copy a starter cv-master.md only if one does not already exist
    cv_master_path = APPLYR_DIR / "cv-master.md"
    if not cv_master_path.exists():
        cv_master_path.write_text(_CV_MASTER_TEMPLATE.format(name="Your Name"))
        print(f"  Created {cv_master_path}  (edit this with your master CV content)")
    else:
        print(f"  {cv_master_path} already exists — skipped")

    print("\napplyr is ready.  Run 'applyr add <json>' to log your first offer.")


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------

def cmd_add(raw: str) -> None:
    """Parse JSON and insert a new job offer into the database."""
    # --- Parse input -------------------------------------------------------
    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON — {exc}")
        sys.exit(1)

    config = load_config()
    threshold: int = config["general"]["threshold"]
    followup_days: int = config["general"]["followup_days"]

    # --- Required field ----------------------------------------------------
    title: str = (data.get("title") or "").strip()
    if not title:
        print("Error: 'title' is required.")
        sys.exit(1)

    # --- Optional scalars --------------------------------------------------
    company: str | None = data.get("company")
    summary: str | None = data.get("summary")
    notes: str | None = data.get("notes")
    status: str = data.get("status", "pending")
    canal: str | None = data.get("canal")
    cv_used: str | None = data.get("cv_used")
    work_mode: str | None = data.get("work_mode")
    location: str | None = data.get("location")
    salary_min: int | None = data.get("salary_min")
    salary_max: int | None = data.get("salary_max")
    salary_period: str = data.get("salary_period", "annual")
    seniority_level: str | None = data.get("seniority_level")
    role_category: str | None = data.get("role_category")
    tech_stack: str | None = data.get("tech_stack")
    cover_letter: int = 1 if data.get("cover_letter") else 0
    cover_letter_file: str | None = data.get("cover_letter_file")
    contact_name: str | None = data.get("contact_name")
    contact_role: str | None = data.get("contact_role")
    job_url: str | None = data.get("job_url")
    rejection_reason: str | None = data.get("rejection_reason")

    # --- Date fields -------------------------------------------------------
    date_received: str = data.get("date_received") or _today()
    date_applied: str | None = _parse_date(data.get("date_applied"))
    date_responded: str | None = _parse_date(data.get("date_responded"))

    # --- Validate enums ----------------------------------------------------
    if status not in VALID_STATUSES:
        print(f"Error: invalid status '{status}'. Valid: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    if canal and canal not in VALID_CHANNELS:
        print(f"Error: invalid canal '{canal}'. Valid: {', '.join(VALID_CHANNELS)}")
        sys.exit(1)

    if work_mode and work_mode not in VALID_WORK_MODES:
        print(f"Error: invalid work_mode '{work_mode}'. Valid: {', '.join(VALID_WORK_MODES)}")
        sys.exit(1)

    if seniority_level and seniority_level not in VALID_SENIORITY:
        print(f"Error: invalid seniority_level '{seniority_level}'. Valid: {', '.join(VALID_SENIORITY)}")
        sys.exit(1)

    # --- Compatibility score -----------------------------------------------
    topics: dict = data.get("topics", {})
    compat_raw = data.get("compatibility_pct")

    if compat_raw is not None:
        try:
            compatibility_pct = int(compat_raw)
        except (TypeError, ValueError):
            print("Error: 'compatibility_pct' must be an integer 0-100.")
            sys.exit(1)
        if not 0 <= compatibility_pct <= 100:
            print("Error: 'compatibility_pct' must be between 0 and 100.")
            sys.exit(1)
    elif topics:
        compatibility_pct = calculate_score(topics)
    else:
        compatibility_pct = 0

    # --- Auto follow-up date ----------------------------------------------
    follow_up_date: str | None = data.get("follow_up_date")
    if not follow_up_date and status in ("applied", "waiting"):
        follow_up_date = (date.today() + timedelta(days=followup_days)).isoformat()

    # --- Insert offer ------------------------------------------------------
    conn = get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO offers (
                title, company, summary, date_received, date_applied, date_responded,
                compatibility_pct, status, canal, cv_used,
                follow_up_date, follow_up_done, follow_up_notes,
                work_mode, location, salary_min, salary_max, salary_period,
                seniority_level, role_category, tech_stack,
                cover_letter, cover_letter_file,
                contact_name, contact_role, job_url, rejection_reason, notes
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, 0, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                title, company, summary, date_received, date_applied, date_responded,
                compatibility_pct, status, canal, cv_used,
                follow_up_date, data.get("follow_up_notes"),
                work_mode, location, salary_min, salary_max, salary_period,
                seniority_level, role_category, tech_stack,
                cover_letter, cover_letter_file,
                contact_name, contact_role, job_url, rejection_reason, notes,
            ),
        )
        offer_id: int = cursor.lastrowid

        # --- Insert topics -------------------------------------------------
        skill_gaps: list[tuple] = []
        for topic_key, values in topics.items():
            score = values.get("score", 0)
            detail = values.get("detail", "")
            conn.execute(
                "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (?, ?, ?, ?)",
                (offer_id, topic_key, score, detail),
            )
            # Track gaps: topics below threshold
            if isinstance(score, (int, float)) and score < threshold:
                skill_gaps.append((topic_key, threshold - score))

        # --- Update skill_gaps table --------------------------------------
        for skill, gap in skill_gaps:
            conn.execute(
                """
                INSERT INTO skill_gaps (skill, frequency, total_gap, last_seen)
                VALUES (?, 1, ?, ?)
                ON CONFLICT(skill) DO UPDATE SET
                    frequency = frequency + 1,
                    total_gap = total_gap + excluded.total_gap,
                    last_seen = excluded.last_seen
                """,
                (skill, gap, _today()),
            )

        conn.commit()
    finally:
        conn.close()

    # --- Confirmation -----------------------------------------------------
    rec_label = STATUS_LABELS.get(status, status)
    print(f"\nOffer added successfully.")
    print(f"  ID          : {offer_id}")
    print(f"  Title       : {title}")
    print(f"  Company     : {company or '—'}")
    print(f"  Compat.     : {compatibility_pct}%")
    print(f"  Status      : {rec_label}")
    if follow_up_date:
        print(f"  Follow-up   : {follow_up_date}")
    if skill_gaps:
        gap_labels = config.get("topics", {})
        gap_names = [gap_labels.get(s, s) for s, _ in skill_gaps]
        print(f"  Skill gaps  : {', '.join(gap_names)}")


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

def cmd_list(status_filter: str | None = None, sort_by: str = "date_applied", limit: int | None = None) -> None:
    """List job offers as a summary table."""
    config = load_config()
    effective_limit = limit if limit is not None else config["general"]["list_limit"]

    # Validate sort column against allowed values to prevent injection
    allowed_sort = {"date_applied", "date_received", "compatibility_pct", "company", "status", "id"}
    if sort_by not in allowed_sort:
        sort_by = "date_applied"

    where_clause = "WHERE status = ?" if status_filter else ""
    params: list = [status_filter] if status_filter else []

    # COALESCE so offers without date_applied still sort by date_received
    order_clause = (
        f"ORDER BY COALESCE({sort_by}, date_received) DESC"
        if sort_by in ("date_applied", "date_received")
        else f"ORDER BY {sort_by} DESC"
    )
    limit_clause = f"LIMIT {int(effective_limit)}" if effective_limit else ""

    query = f"SELECT id, company, title, compatibility_pct, status, work_mode, date_applied, date_received FROM offers {where_clause} {order_clause} {limit_clause}"

    conn = get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    if not rows:
        msg = f"No offers found"
        if status_filter:
            msg += f" with status '{status_filter}'"
        print(msg + ".")
        return

    # Build display rows
    display = [_make_display_row(r) for r in rows]
    headers = ["ID", "COMPANY", "TITLE", "%", "STATUS", "MODE", "DATE"]
    widths =  [4,    18,        28,      4,   16,       8,      10   ]
    _print_table(display, headers, widths)
    print(f"  {len(rows)} offer(s) shown.")


# ---------------------------------------------------------------------------
# cmd_pipeline
# ---------------------------------------------------------------------------

def cmd_pipeline(min_score: int = 0) -> None:
    """Show offers grouped by status in funnel order."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT status, compatibility_pct, title, company, id FROM offers ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No offers in the database.")
        return

    # Group by status
    groups: dict[str, list] = {s: [] for s in _STATUS_ORDER}
    for r in rows:
        if r["compatibility_pct"] < min_score:
            continue
        bucket = r["status"] if r["status"] in groups else "pending"
        groups[bucket].append(r)

    print("\n--- Pipeline ---\n")
    for status in _STATUS_ORDER:
        items = groups[status]
        label = STATUS_LABELS.get(status, status)
        print(f"  {label:<20} ({len(items)})")
        for item in items:
            pct = item["compatibility_pct"]
            company = item["company"] or "—"
            print(f"    #{item['id']:>4}  {pct:>3}%  {_truncate(company, 16):<16}  {_truncate(item['title'], 30)}")
    print()


# ---------------------------------------------------------------------------
# cmd_show
# ---------------------------------------------------------------------------

def cmd_show(offer_id: int) -> None:
    """Display all fields for a single offer."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            print(f"Error: offer #{offer_id} not found.")
            return

        topics = conn.execute(
            "SELECT topic, score, detail FROM offer_topics WHERE offer_id = ?", (offer_id,)
        ).fetchall()
    finally:
        conn.close()

    config = load_config()
    topic_labels: dict = config.get("topics", {})

    print(f"\n{'='*60}")
    print(f"  Offer #{row['id']}  —  {row['title']}")
    print(f"{'='*60}")

    def _field(label: str, value) -> None:
        if value is not None and value != "" and value != 0:
            print(f"  {label:<22}: {value}")

    _field("Company", row["company"])
    _field("Job URL", row["job_url"])
    _field("Status", STATUS_LABELS.get(row["status"], row["status"]))
    _field("Canal", row["canal"])
    _field("Compatibility", f"{row['compatibility_pct']}%")
    print()

    _field("Work Mode", row["work_mode"])
    _field("Location", row["location"])
    _field("Seniority", row["seniority_level"])
    _field("Role Category", row["role_category"])
    _field("Tech Stack", row["tech_stack"])
    print()

    _field("Date Received", row["date_received"])
    _field("Date Applied", row["date_applied"])
    _field("Date Responded", row["date_responded"])
    print()

    # Salary
    if row["salary_min"] or row["salary_max"]:
        period = row["salary_period"] or "annual"
        sal_str = ""
        if row["salary_min"] and row["salary_max"]:
            sal_str = f"{row['salary_min']:,} – {row['salary_max']:,} ({period})"
        elif row["salary_min"]:
            sal_str = f">= {row['salary_min']:,} ({period})"
        else:
            sal_str = f"<= {row['salary_max']:,} ({period})"
        _field("Salary", sal_str)
        print()

    # Contact
    _field("Contact Name", row["contact_name"])
    _field("Contact Role", row["contact_role"])
    if row["contact_name"] or row["contact_role"]:
        print()

    # Materials
    if row["cover_letter"]:
        _field("Cover Letter", row["cover_letter_file"] or "Yes (no file specified)")
    _field("CV Used", row["cv_used"])

    # Follow-up
    today_str = _today()
    fu_date = row["follow_up_date"]
    if fu_date:
        if row["follow_up_done"]:
            fu_status = "Done"
        elif fu_date < today_str:
            fu_status = f"OVERDUE (was {fu_date})"
        elif fu_date <= (date.today() + timedelta(days=5)).isoformat():
            fu_status = f"Upcoming ({fu_date})"
        else:
            fu_status = fu_date
        _field("Follow-up", fu_status)
    _field("Follow-up Notes", row["follow_up_notes"])

    # Rejection
    _field("Rejection Reason", row["rejection_reason"])

    # Summary / Notes
    if row["summary"]:
        print(f"\n  Summary:\n    {row['summary']}")
    if row["notes"]:
        print(f"\n  Notes:\n    {row['notes']}")

    # Topic scores
    if topics:
        print(f"\n  Scoring Topics:")
        for t in topics:
            label = topic_labels.get(t["topic"], t["topic"])
            bar = _bar(t["score"])
            detail = f"  ({t['detail']})" if t["detail"] else ""
            print(f"    {label:<18} {t['score']:>3}%  {bar}{detail}")

    print()


# ---------------------------------------------------------------------------
# cmd_update
# ---------------------------------------------------------------------------

def cmd_update(offer_id: int, status: str, notes: str | None = None, canal: str | None = None) -> None:
    """Update the status (and optionally notes/canal) of an offer."""
    if status not in VALID_STATUSES:
        print(f"Error: invalid status '{status}'. Valid: {', '.join(VALID_STATUSES)}")
        sys.exit(1)

    if canal and canal not in VALID_CHANNELS:
        print(f"Error: invalid canal '{canal}'. Valid: {', '.join(VALID_CHANNELS)}")
        sys.exit(1)

    config = load_config()
    followup_days: int = config["general"]["followup_days"]

    conn = get_conn()
    try:
        row = conn.execute("SELECT id, title, company FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            print(f"Error: offer #{offer_id} not found.")
            return

        # Build dynamic update
        fields: list[str] = ["status = ?"]
        params: list = [status]

        if notes is not None:
            fields.append("notes = ?")
            params.append(notes)

        if canal is not None:
            fields.append("canal = ?")
            params.append(canal)

        # Auto follow-up when moving to applied/waiting
        if status in ("applied", "waiting"):
            new_follow_up = (date.today() + timedelta(days=followup_days)).isoformat()
            fields.append("follow_up_date = ?")
            params.append(new_follow_up)

        # Record response date when first response received
        if status in ("in_process", "rejected", "offer"):
            fields.append("date_responded = COALESCE(date_responded, ?)")
            params.append(_today())

        params.append(offer_id)
        conn.execute(f"UPDATE offers SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    finally:
        conn.close()

    print(f"Offer #{offer_id} updated.")
    print(f"  Title  : {row['title']}")
    print(f"  Status : {STATUS_LABELS.get(status, status)}")


# ---------------------------------------------------------------------------
# cmd_delete
# ---------------------------------------------------------------------------

def cmd_delete(offer_id: int) -> None:
    """Delete an offer and its associated topics (CASCADE)."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT id, title, company, status FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            print(f"Error: offer #{offer_id} not found.")
            return

        print(f"About to delete:")
        print(f"  #{row['id']}  {row['title']}  ({row['company'] or '—'})  [{STATUS_LABELS.get(row['status'], row['status'])}]")
        confirm = input("Confirm deletion? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

        conn.execute("DELETE FROM offers WHERE id = ?", (offer_id,))
        conn.commit()
    finally:
        conn.close()

    print(f"Offer #{offer_id} deleted.")


# ---------------------------------------------------------------------------
# cmd_search
# ---------------------------------------------------------------------------

def cmd_search(keyword: str, status_filter: str | None = None) -> None:
    """Search offers by keyword across title, company, summary, notes, tech_stack."""
    pattern = f"%{keyword}%"
    base_query = """
        SELECT id, company, title, compatibility_pct, status, work_mode, date_applied, date_received
        FROM offers
        WHERE (
            title       LIKE ?
            OR company  LIKE ?
            OR summary  LIKE ?
            OR notes    LIKE ?
            OR tech_stack LIKE ?
        )
    """
    params: list = [pattern] * 5

    if status_filter:
        if status_filter not in VALID_STATUSES:
            print(f"Error: invalid status '{status_filter}'. Valid: {', '.join(VALID_STATUSES)}")
            sys.exit(1)
        base_query += " AND status = ?"
        params.append(status_filter)

    base_query += " ORDER BY COALESCE(date_applied, date_received) DESC"

    conn = get_conn()
    try:
        rows = conn.execute(base_query, params).fetchall()
    finally:
        conn.close()

    if not rows:
        print(f"No offers found matching '{keyword}'.")
        return

    display = [_make_display_row(r) for r in rows]
    headers = ["ID", "COMPANY", "TITLE", "%", "STATUS", "MODE", "DATE"]
    widths =  [4,    18,        28,      4,   16,       8,      10   ]
    _print_table(display, headers, widths)
    print(f"  {len(rows)} result(s) for '{keyword}'.")


# ---------------------------------------------------------------------------
# cmd_stats
# ---------------------------------------------------------------------------

def cmd_stats() -> None:
    """Print aggregate statistics for the offer database."""
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
        if total == 0:
            print("No offers in the database yet.")
            return

        discarded = conn.execute("SELECT COUNT(*) FROM offers WHERE status = 'discarded'").fetchone()[0]
        pending   = conn.execute("SELECT COUNT(*) FROM offers WHERE status = 'pending'").fetchone()[0]
        avg_compat = conn.execute("SELECT AVG(compatibility_pct) FROM offers").fetchone()[0] or 0

        # Conversion funnel
        applied    = conn.execute("SELECT COUNT(*) FROM offers WHERE status != 'pending' AND status != 'discarded'").fetchone()[0]
        responded  = conn.execute("SELECT COUNT(*) FROM offers WHERE status IN ('in_process','rejected','offer','waiting')").fetchone()[0]
        interview  = conn.execute("SELECT COUNT(*) FROM offers WHERE status = 'in_process'").fetchone()[0]
        offers_cnt = conn.execute("SELECT COUNT(*) FROM offers WHERE status = 'offer'").fetchone()[0]

        # Channel breakdown
        channels = conn.execute(
            "SELECT canal, COUNT(*) as cnt FROM offers WHERE canal IS NOT NULL GROUP BY canal ORDER BY cnt DESC"
        ).fetchall()

        # Work mode breakdown
        modes = conn.execute(
            "SELECT work_mode, COUNT(*) as cnt FROM offers WHERE work_mode IS NOT NULL GROUP BY work_mode ORDER BY cnt DESC"
        ).fetchall()

        # Salary stats
        sal = conn.execute(
            "SELECT MIN(salary_min), MAX(salary_min), AVG(salary_min) FROM offers WHERE salary_min IS NOT NULL"
        ).fetchone()
    finally:
        conn.close()

    def _pct(num, denom):
        return f"{round(num / denom * 100)}%" if denom else "—"

    print("\n--- Stats ---\n")
    print(f"  Total offers    : {total}")
    print(f"  Pending         : {pending}")
    print(f"  Discarded       : {discarded}")
    print(f"  Avg Compat.     : {avg_compat:.1f}%")

    print(f"\n  Conversion Funnel:")
    print(f"    Applied        {applied:>4}  ({_pct(applied, total)} of total)")
    print(f"    Responded      {responded:>4}  ({_pct(responded, applied)} of applied)")
    print(f"    Interview      {interview:>4}  ({_pct(interview, responded)} of responded)")
    print(f"    Offer          {offers_cnt:>4}  ({_pct(offers_cnt, interview)} of interviews)")

    if channels:
        print(f"\n  Channel Breakdown:")
        for ch in channels:
            print(f"    {ch['canal']:<20} {ch['cnt']}")

    if modes:
        print(f"\n  Work Mode Breakdown:")
        for m in modes:
            print(f"    {m['work_mode']:<12} {m['cnt']}")

    if sal and sal[0] is not None:
        print(f"\n  Salary (salary_min, where provided):")
        print(f"    Min : {sal[0]:,}")
        print(f"    Max : {sal[1]:,}")
        print(f"    Avg : {round(sal[2]):,}")

    print()


# ---------------------------------------------------------------------------
# cmd_gaps
# ---------------------------------------------------------------------------

def cmd_gaps(limit: int = 10) -> None:
    """Show recurring skill gaps sorted by frequency."""
    config = load_config()
    topic_labels: dict = config.get("topics", {})

    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT skill, frequency, total_gap FROM skill_gaps ORDER BY frequency DESC, total_gap DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No skill gaps recorded yet.")
        return

    print("\n--- Skill Gaps ---\n")
    for r in rows:
        label = topic_labels.get(r["skill"], r["skill"])
        freq  = r["frequency"]
        if freq >= 3:
            priority = "HIGH  "
        elif freq == 2:
            priority = "MEDIUM"
        else:
            priority = "LOW   "
        avg_gap = round(r["total_gap"] / freq) if freq else 0
        print(f"  [{priority}]  {label:<20}  seen {freq}x  avg gap {avg_gap}%")
    print()


# ---------------------------------------------------------------------------
# cmd_followups
# ---------------------------------------------------------------------------

def cmd_followups() -> None:
    """Show overdue and upcoming (next 5 days) follow-ups."""
    today = _today()
    upcoming_limit = (date.today() + timedelta(days=5)).isoformat()

    conn = get_conn()
    try:
        overdue = conn.execute(
            """
            SELECT id, title, company, contact_name, contact_role, follow_up_date, follow_up_done
            FROM offers
            WHERE follow_up_date < ? AND follow_up_done = 0
            ORDER BY follow_up_date
            """,
            (today,),
        ).fetchall()

        upcoming = conn.execute(
            """
            SELECT id, title, company, contact_name, contact_role, follow_up_date, follow_up_done
            FROM offers
            WHERE follow_up_date >= ? AND follow_up_date <= ? AND follow_up_done = 0
            ORDER BY follow_up_date
            """,
            (today, upcoming_limit),
        ).fetchall()
    finally:
        conn.close()

    def _print_followup_row(r) -> None:
        contact = ""
        if r["contact_name"]:
            contact = f"  Contact: {r['contact_name']}"
            if r["contact_role"]:
                contact += f" ({r['contact_role']})"
        print(f"    #{r['id']:>4}  {r['follow_up_date']}  {_truncate(r['company'] or '—', 16):<16}  {_truncate(r['title'], 28)}{contact}")

    if not overdue and not upcoming:
        print("No pending follow-ups.")
        return

    if overdue:
        print(f"\n  OVERDUE ({len(overdue)}):")
        for r in overdue:
            _print_followup_row(r)

    if upcoming:
        print(f"\n  Upcoming — next 5 days ({len(upcoming)}):")
        for r in upcoming:
            _print_followup_row(r)

    print()


# ---------------------------------------------------------------------------
# cmd_trends
# ---------------------------------------------------------------------------

def cmd_trends(period: str = "week") -> None:
    """Group applications by week or month and show growth vs previous period."""
    if period not in ("week", "month"):
        print("Error: period must be 'week' or 'month'.")
        sys.exit(1)

    # SQLite strftime format
    fmt = "%Y-W%W" if period == "week" else "%Y-%m"

    conn = get_conn()
    try:
        rows = conn.execute(
            f"""
            SELECT strftime('{fmt}', COALESCE(date_applied, date_received)) AS period,
                   COUNT(*) AS cnt
            FROM offers
            WHERE COALESCE(date_applied, date_received) IS NOT NULL
            GROUP BY period
            ORDER BY period DESC
            LIMIT 12
            """,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No dated offers found.")
        return

    print(f"\n--- Trends by {period.capitalize()} ---\n")
    for i, r in enumerate(rows):
        cnt = r["cnt"]
        prev_cnt = rows[i + 1]["cnt"] if i + 1 < len(rows) else None
        if prev_cnt is not None and prev_cnt > 0:
            growth = round((cnt - prev_cnt) / prev_cnt * 100)
            growth_str = f"  ({'+' if growth >= 0 else ''}{growth}% vs prev)"
        else:
            growth_str = ""
        bar = _bar(cnt, width=15)
        print(f"  {r['period']}  {bar}  {cnt:>3}{growth_str}")
    print()


# ---------------------------------------------------------------------------
# cmd_summary
# ---------------------------------------------------------------------------

def cmd_summary(as_json: bool = False) -> None:
    """Print a weekly summary of activity, optionally as JSON for LLM consumption."""
    config = load_config()
    topic_labels: dict = config.get("topics", {})

    # Week boundaries
    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_end = today.isoformat()

    conn = get_conn()
    try:
        sent = conn.execute(
            "SELECT COUNT(*) FROM offers WHERE date_applied >= ? AND date_applied <= ?",
            (week_start, week_end),
        ).fetchone()[0]

        responses = conn.execute(
            "SELECT COUNT(*) FROM offers WHERE date_responded >= ? AND date_responded <= ?",
            (week_start, week_end),
        ).fetchone()[0]

        avg_compat_row = conn.execute(
            "SELECT AVG(compatibility_pct) FROM offers WHERE date_applied >= ? AND date_applied <= ?",
            (week_start, week_end),
        ).fetchone()[0]
        avg_compat = round(avg_compat_row or 0, 1)

        # Channels used this week
        channels_rows = conn.execute(
            """
            SELECT canal, COUNT(*) as cnt FROM offers
            WHERE date_applied >= ? AND date_applied <= ? AND canal IS NOT NULL
            GROUP BY canal ORDER BY cnt DESC
            """,
            (week_start, week_end),
        ).fetchall()
        channels_used = {r["canal"]: r["cnt"] for r in channels_rows}

        # Work modes this week
        modes_rows = conn.execute(
            """
            SELECT work_mode, COUNT(*) as cnt FROM offers
            WHERE date_applied >= ? AND date_applied <= ? AND work_mode IS NOT NULL
            GROUP BY work_mode ORDER BY cnt DESC
            """,
            (week_start, week_end),
        ).fetchall()
        work_modes = {r["work_mode"]: r["cnt"] for r in modes_rows}

        # Top skill gap
        top_gap_row = conn.execute(
            "SELECT skill FROM skill_gaps ORDER BY frequency DESC LIMIT 1"
        ).fetchone()
        top_gap = topic_labels.get(top_gap_row["skill"], top_gap_row["skill"]) if top_gap_row else None
    finally:
        conn.close()

    response_rate = round(responses / sent * 100, 1) if sent else 0.0

    if as_json:
        payload = {
            "week": {"start": week_start, "end": week_end},
            "applications_sent": sent,
            "responses_received": responses,
            "response_rate_pct": response_rate,
            "avg_compatibility_pct": avg_compat,
            "top_skill_gap": top_gap,
            "channels": channels_used,
            "work_modes": work_modes,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"\n--- Weekly Summary  ({week_start} to {week_end}) ---\n")
        print(f"  Applications sent    : {sent}")
        print(f"  Responses received   : {responses}  ({response_rate}% response rate)")
        print(f"  Avg compatibility    : {avg_compat}%")
        if top_gap:
            print(f"  Top skill gap        : {top_gap}")
        if channels_used:
            ch_str = ", ".join(f"{k}: {v}" for k, v in channels_used.items())
            print(f"  Channels used        : {ch_str}")
        if work_modes:
            wm_str = ", ".join(f"{k}: {v}" for k, v in work_modes.items())
            print(f"  Work modes           : {wm_str}")
        print()


# ---------------------------------------------------------------------------
# cmd_export
# ---------------------------------------------------------------------------

def cmd_export(fmt: str = "csv", filepath: str | None = None) -> None:
    """Export all offers to CSV or JSON."""
    if fmt not in ("csv", "json"):
        print(f"Error: unsupported format '{fmt}'. Use 'csv' or 'json'.")
        sys.exit(1)

    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM offers ORDER BY id").fetchall()
    finally:
        conn.close()

    if not rows:
        print("No offers to export.")
        return

    # Determine output path
    default_name = f"applyr_export.{fmt}"
    out_path = Path(filepath) if filepath else Path.cwd() / default_name

    # Convert sqlite3.Row objects to plain dicts
    records = [dict(r) for r in rows]

    try:
        if fmt == "csv":
            fieldnames = list(records[0].keys())
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
        else:  # json
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        print(f"Error writing file: {exc}")
        sys.exit(1)

    print(f"Exported {len(records)} offer(s) to {out_path}")
