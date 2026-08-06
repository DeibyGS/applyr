"""CRUD and setup commands: init, setup-agent, add, list, show, update, delete, search."""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from applyr.colors import color
from applyr.config import APPLYR_DIR, TOPIC_LABELS, create_default_config, load_config
from applyr.constants import (
    FOLLOWUP_UPCOMING_DAYS,
    JSON_ERROR_CONTEXT,
    LIST_COL_WIDTHS,
    LIST_HEADERS,
    TRUNCATE_COMPANY,
    TRUNCATE_TITLE,
    VALID_SALARY_PERIODS,
)
from applyr.db import (
    STATUS_LABELS,
    VALID_CHANNELS,
    VALID_ROLE_CATEGORIES,
    VALID_SENIORITY,
    VALID_STATUSES,
    VALID_WORK_MODES,
    get_conn,
    get_db_path,
    init_db,
)
from applyr.scoring import calculate_score
from applyr.commands._helpers import _bar, _today, _truncate

# ---------------------------------------------------------------------------
# Module-level constants
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

_AGENT_TARGETS = {
    "claude":   ("CLAUDE.md",),
    "cursor":   (".cursorrules",),
    "opencode": (".opencode/instructions.md",),
    "generic":  ("AGENTS.md",),
}

_AGENT_DETECT_ORDER = [
    ("claude",   "CLAUDE.md"),
    ("claude",   ".claude/CLAUDE.md"),
    ("cursor",   ".cursorrules"),
    ("cursor",   ".cursor/rules"),
    ("opencode", ".opencode/instructions.md"),
    ("generic",  "AGENTS.md"),
]

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_agent_instructions() -> str:
    """Read AGENT_INSTRUCTIONS.md content from ~/.applyr/ or bundled template."""
    local = APPLYR_DIR / "AGENT_INSTRUCTIONS.md"
    if local.exists():
        return local.read_text()
    for src in [
        Path(__file__).parent.parent.parent / "templates" / "AGENT_INSTRUCTIONS.md",
        Path(__file__).parent.parent / "templates" / "AGENT_INSTRUCTIONS.md",
    ]:
        if src.exists():
            return src.read_text()
    return ""


def _make_display_row(r) -> dict:
    """Convert a sqlite3.Row from offers into a table-ready display dict."""
    return {
        "ID": str(r["id"]),
        "COMPANY": _truncate(r["company"] or "—", TRUNCATE_COMPANY),
        "TITLE": _truncate(r["title"], TRUNCATE_TITLE),
        "%": str(r["compatibility_pct"]),
        "STATUS": STATUS_LABELS.get(r["status"], r["status"]),
        "MODE": r["work_mode"] or "—",
        "DATE": r["date_applied"] or r["date_received"] or "—",
    }


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

    # Copy AGENT_INSTRUCTIONS.md
    agent_instructions_dst = APPLYR_DIR / "AGENT_INSTRUCTIONS.md"
    if not agent_instructions_dst.exists():
        # Try to find the template bundled with the package or in templates/
        src_candidates = [
            Path(__file__).parent.parent.parent / "templates" / "AGENT_INSTRUCTIONS.md",
            Path(__file__).parent.parent / "templates" / "AGENT_INSTRUCTIONS.md",
        ]
        for src in src_candidates:
            if src.exists():
                agent_instructions_dst.write_text(src.read_text())
                break
        else:
            # Fallback: create a minimal pointer
            agent_instructions_dst.write_text(
                "# applyr — Agent Instructions\n\n"
                "Download the full instructions from:\n"
                "https://github.com/DeibyGS/applyr/blob/main/templates/AGENT_INSTRUCTIONS.md\n"
            )
        print(f"  Created {agent_instructions_dst}")
    else:
        print(f"  {agent_instructions_dst} already exists — skipped")

    print("\napplyr is ready.")
    print("  1. Edit ~/.applyr/cv-master.md with your professional profile")
    print("  2. Run 'applyr setup-agent' in your project directory")
    print("     to configure your AI agent (Claude, Cursor, OpenCode, etc.)")
    print("  3. Run 'applyr add <json>' to log your first offer")


# ---------------------------------------------------------------------------
# cmd_setup_agent
# ---------------------------------------------------------------------------

def cmd_setup_agent(agent: str | None = None) -> None:
    """Write applyr agent instructions into the current project's AI config file."""
    cwd = Path.cwd()
    instructions = _get_agent_instructions()
    if not instructions:
        print("Error: could not find AGENT_INSTRUCTIONS.md")
        print("  Run 'applyr init' first.")
        return

    # Auto-detect if no agent specified
    if not agent:
        for name, path in _AGENT_DETECT_ORDER:
            if (cwd / path).exists():
                agent = name
                print(f"  Detected {name} config ({path})")
                break

    if not agent:
        print("No AI agent config detected in this directory.")
        print("  Supported: --agent claude | cursor | opencode | generic")
        print("  Example: applyr setup-agent --agent claude")
        return

    if agent not in _AGENT_TARGETS:
        print(f"Error: unknown agent '{agent}'")
        print(f"  Supported: {', '.join(_AGENT_TARGETS.keys())}")
        return

    rel_path = _AGENT_TARGETS[agent][0]
    target = cwd / rel_path

    # Create parent dirs if needed (e.g. .opencode/)
    target.parent.mkdir(parents=True, exist_ok=True)

    # If file exists, append (don't overwrite user content)
    if target.exists():
        existing = target.read_text()
        if "applyr" in existing.lower() and "agent instructions" in existing.lower():
            print(f"  {rel_path} already contains applyr instructions — skipped.")
            return
        separator = "\n\n---\n\n"
        target.write_text(existing.rstrip() + separator + instructions)
        print(f"  Appended applyr instructions to {rel_path}")
    else:
        target.write_text(instructions)
        print(f"  Created {rel_path} with applyr instructions")

    print(f"\n  Your AI agent will now use applyr automatically.")
    print(f"  Make sure ~/.applyr/cv-master.md has your professional profile.")


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------

def cmd_add(raw: str) -> None:
    """Parse JSON and insert a new job offer into the database."""
    # --- Parse input -------------------------------------------------------
    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON — {exc.msg} at line {exc.lineno}, column {exc.colno}")
        if exc.pos is not None:
            snippet = raw[max(0, exc.pos - JSON_ERROR_CONTEXT):exc.pos + JSON_ERROR_CONTEXT]
            print(f"  Around: ...{snippet}...")
        print('  Example: applyr add \'{"title": "Backend Dev", "company": "Acme"}\'')
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
    if salary_min and salary_max and salary_min > salary_max:
        print(f"Error: salary_min ({salary_min}) cannot be greater than salary_max ({salary_max}).")
        print("  Hint: swap the values or correct the input.")
        sys.exit(1)
    salary_period: str = data.get("salary_period", "annual")
    if salary_period not in VALID_SALARY_PERIODS:
        print(f"Error: invalid salary_period '{salary_period}'. Valid: {', '.join(VALID_SALARY_PERIODS)}")
        sys.exit(1)
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
    if data.get("date_applied") and date_applied is None:
        print(f"Warning: invalid date_applied format '{data['date_applied']}' — ignored. Use YYYY-MM-DD.")
    date_responded: str | None = _parse_date(data.get("date_responded"))
    if data.get("date_responded") and date_responded is None:
        print(f"Warning: invalid date_responded format '{data['date_responded']}' — ignored. Use YYYY-MM-DD.")

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

    if role_category and role_category not in VALID_ROLE_CATEGORIES:
        print(f"Error: invalid role_category '{role_category}'. Valid: {', '.join(VALID_ROLE_CATEGORIES)}")
        sys.exit(1)

    # --- Duplicate detection -----------------------------------------------
    conn = get_conn()
    try:
        dup = conn.execute(
            """SELECT id, status, date_received, compatibility_pct
               FROM offers
               WHERE LOWER(title) = LOWER(?) AND LOWER(COALESCE(company,'')) = LOWER(COALESCE(?,''))""",
            (title, company),
        ).fetchone()
    finally:
        conn.close()

    if dup:
        dup_label = STATUS_LABELS.get(dup["status"], dup["status"])
        print(f"\nDuplicate detected — this offer already exists in your database.")
        print(f"  ID          : {dup['id']}")
        print(f"  Status      : {dup_label}")
        print(f"  Received    : {dup['date_received']}")
        print(f"  Compat.     : {dup['compatibility_pct']}%")
        print(f"\nUse 'applyr show {dup['id']}' to review or 'applyr update {dup['id']} <status>' to change it.")
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

        # --- Validate topic keys -------------------------------------------
        valid_topics = set(config.get("topics", {}).keys()) or set(TOPIC_LABELS.keys())
        for key in topics:
            if key not in valid_topics:
                print(f"  Warning: topic '{key}' not in config. Valid: {', '.join(sorted(valid_topics))}")

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
        gap_labels = TOPIC_LABELS
        gap_names = [gap_labels.get(s, s) for s, _ in skill_gaps]
        print(f"  Skill gaps  : {', '.join(gap_names)}")

    # --- Threshold recommendation ------------------------------------------
    if compatibility_pct >= threshold:
        print(f"\n  >> RECOMMENDATION: APPLY (score {compatibility_pct}% >= {threshold}% threshold)")
        print(f"     Next: 'applyr cv generate {offer_id}' to create a tailored CV")
    else:
        print(f"\n  >> RECOMMENDATION: SKIP (score {compatibility_pct}% < {threshold}% threshold)")
        print(f"     Consider: 'applyr update {offer_id} discarded' to archive this offer")


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

def cmd_list(status_filter: str | None = None, sort_by: str = "date_applied", limit: int | None = None, as_json: bool = False) -> None:
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

    if as_json:
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
        return

    # Build display rows
    display = [_make_display_row(r) for r in rows]
    _print_table(display, LIST_HEADERS, LIST_COL_WIDTHS)
    print(f"  {len(rows)} offer(s) shown.")


# ---------------------------------------------------------------------------
# cmd_show
# ---------------------------------------------------------------------------

def cmd_show(offer_id: int, as_json: bool = False) -> None:
    """Display all fields for a single offer."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            print(f"Error: offer #{offer_id} not found.")
            print("  Hint: run 'applyr list' to see available offers.")
            sys.exit(1)

        topics = conn.execute(
            "SELECT topic, score, detail FROM offer_topics WHERE offer_id = ?", (offer_id,)
        ).fetchall()
    finally:
        conn.close()

    if as_json:
        data = dict(row)
        data["topics"] = [{"topic": t["topic"], "score": t["score"], "detail": t["detail"]} for t in topics]
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    config = load_config()
    topic_labels: dict = TOPIC_LABELS

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
        elif fu_date <= (date.today() + timedelta(days=FOLLOWUP_UPCOMING_DAYS)).isoformat():
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
            print("  Hint: run 'applyr list' to see available offers.")
            sys.exit(1)

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
            print("  Hint: run 'applyr list' to see available offers.")
            sys.exit(1)

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

def cmd_search(keyword: str, status_filter: str | None = None, as_json: bool = False) -> None:
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

    if as_json:
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
        return

    display = [_make_display_row(r) for r in rows]
    _print_table(display, LIST_HEADERS, LIST_COL_WIDTHS)
    print(f"  {len(rows)} result(s) for '{keyword}'.")
