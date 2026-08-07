"""CRUD and setup commands: init, setup-agent, add, list, show, update, delete, search."""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from applyr.config import APPLYR_DIR, TOPIC_LABELS, create_default_config, load_config
from applyr.constants import (
    DUPLICATE_COMPANY_HISTORY_LIMIT,
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
from applyr.duplicates import find_company_offers, find_exact, find_similar
from applyr.errors import die, error, warn

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


def _report_duplicate(row, reason: str) -> None:
    """Report a blocking duplicate on stderr and exit. Never returns."""
    label = STATUS_LABELS.get(row["status"], row["status"])
    error(f"\nDuplicate detected — {reason}.")
    error(f"  ID          : {row['id']}")
    error(f"  Title       : {row['title']}")
    error(f"  Status      : {label}")
    error(f"  Received    : {row['date_received']}")
    error(f"  Compat.     : {row['compatibility_pct']}%")
    error(f"\nUse 'applyr show {row['id']}' to review, "
          f"'applyr update {row['id']} <status>' to change it,")
    die(f"Duplicate detected — {reason}. Re-run with --force to add it anyway.",
        code="duplicate",
        details={"existing_id": row["id"], "existing_title": row["title"],
                 "existing_status": row["status"]},
        text="or re-run with --force to add it anyway.")


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
    print(f"  1. Edit {APPLYR_DIR / 'cv-master.md'} with your professional profile")
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
        error("Error: could not find AGENT_INSTRUCTIONS.md")
        die("Could not find AGENT_INSTRUCTIONS.md", code="not_found",
            text="  Run 'applyr init' first.")

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
        error(f"Error: unknown agent '{agent}'")
        die(f"Unknown agent '{agent}'", code="invalid_value",
            details={"value": agent, "valid": list(_AGENT_TARGETS)},
            text=f"  Supported: {', '.join(_AGENT_TARGETS.keys())}")

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
    print(f"  Make sure {APPLYR_DIR / 'cv-master.md'} has your professional profile.")


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------

def cmd_add(raw: str, force: bool = False) -> None:
    """Parse JSON and insert a new job offer into the database.

    Blocks on an exact or near-identical duplicate at the same company unless
    force is set. Previous offers at the same company are reported but never
    block — see applyr/duplicates.py.
    """
    # --- Parse input -------------------------------------------------------
    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        error(f"Error: invalid JSON — {exc.msg} at line {exc.lineno}, column {exc.colno}")
        if exc.pos is not None:
            snippet = raw[max(0, exc.pos - JSON_ERROR_CONTEXT):exc.pos + JSON_ERROR_CONTEXT]
            error(f"  Around: ...{snippet}...")
        die(f"invalid JSON — {exc.msg} at line {exc.lineno}, column {exc.colno}",
            code="invalid_json",
            details={"line": exc.lineno, "column": exc.colno, "position": exc.pos},
            text='  Example: applyr add \'{"title": "Backend Dev", "company": "Acme"}\'')

    config = load_config()
    threshold: int = config["general"]["threshold"]
    followup_days: int = config["general"]["followup_days"]

    # --- Required field ----------------------------------------------------
    title: str = (data.get("title") or "").strip()
    if not title:
        die("Error: 'title' is required.", code="missing_field", details={"field": "title"})
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
        error(f"Error: salary_min ({salary_min}) cannot be greater than salary_max ({salary_max}).")
        die(f"salary_min ({salary_min}) cannot be greater than salary_max ({salary_max}).",
            code="invalid_range",
            details={"salary_min": salary_min, "salary_max": salary_max},
            text="  Hint: swap the values or correct the input.")
    salary_period: str = data.get("salary_period", "annual")
    if salary_period not in VALID_SALARY_PERIODS:
        die(f"Error: invalid salary_period '{salary_period}'. Valid: {', '.join(VALID_SALARY_PERIODS)}", code="invalid_value", details={"field": "salary_period", "value": salary_period, "valid": list(VALID_SALARY_PERIODS)})
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
        die(f"Error: invalid status '{status}'. Valid: {', '.join(VALID_STATUSES)}", code="invalid_value", details={"field": "status", "value": status, "valid": list(VALID_STATUSES)})
    if canal and canal not in VALID_CHANNELS:
        die(f"Error: invalid canal '{canal}'. Valid: {', '.join(VALID_CHANNELS)}", code="invalid_value", details={"field": "canal", "value": canal, "valid": list(VALID_CHANNELS)})
    if work_mode and work_mode not in VALID_WORK_MODES:
        die(f"Error: invalid work_mode '{work_mode}'. Valid: {', '.join(VALID_WORK_MODES)}", code="invalid_value", details={"field": "work_mode", "value": work_mode, "valid": list(VALID_WORK_MODES)})
    if seniority_level and seniority_level not in VALID_SENIORITY:
        die(f"Error: invalid seniority_level '{seniority_level}'. Valid: {', '.join(VALID_SENIORITY)}", code="invalid_value", details={"field": "seniority_level", "value": seniority_level, "valid": list(VALID_SENIORITY)})
    if role_category and role_category not in VALID_ROLE_CATEGORIES:
        die(f"Error: invalid role_category '{role_category}'. Valid: {', '.join(VALID_ROLE_CATEGORIES)}", code="invalid_value", details={"field": "role_category", "value": role_category, "valid": list(VALID_ROLE_CATEGORIES)})
    # --- Duplicate detection -----------------------------------------------
    conn = get_conn()
    try:
        exact = find_exact(conn, title, company)
        company_offers = find_company_offers(conn, company)
    finally:
        conn.close()

    if exact and not force:
        _report_duplicate(exact, "this offer already exists in your database")

    similar = None
    if not exact:
        similar = find_similar(company_offers, title)
    if similar and not force:
        row, score = similar
        _report_duplicate(row, f"a very similar offer already exists ({score:.0%} match)")

    # Same company, different role — informational, never blocks.
    already_reported = {row["id"] for row in (exact, similar[0] if similar else None) if row}
    others = [r for r in company_offers if r["id"] not in already_reported]
    if others:
        warn(f"\nYou have already applied to {company} — {len(others)} previous offer(s):")
        for row in others[:DUPLICATE_COMPANY_HISTORY_LIMIT]:
            label = STATUS_LABELS.get(row["status"], row["status"])
            warn(f"  #{row['id']:<4} {_truncate(row['title'], TRUNCATE_TITLE):<28} {label}")
        if len(others) > DUPLICATE_COMPANY_HISTORY_LIMIT:
            warn(f"  ... and {len(others) - DUPLICATE_COMPANY_HISTORY_LIMIT} more")
        warn("")

    # --- Compatibility score -----------------------------------------------
    topics: dict = data.get("topics", {})
    compat_raw = data.get("compatibility_pct")

    if compat_raw is not None:
        try:
            compatibility_pct = int(compat_raw)
        except (TypeError, ValueError):
            die("Error: 'compatibility_pct' must be an integer 0-100.", code="invalid_value", details={"field": "compatibility_pct"})
        if not 0 <= compatibility_pct <= 100:
            die("Error: 'compatibility_pct' must be between 0 and 100.", code="invalid_value", details={"field": "compatibility_pct"})
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
    # Validate before querying: an unknown status would otherwise return an
    # empty list, which reads as "no offers" rather than "you mistyped it".
    if status_filter and status_filter not in VALID_STATUSES:
        die(f"Error: invalid status '{status_filter}'. Valid: {', '.join(VALID_STATUSES)}",
            code="invalid_value",
            details={"field": "status", "value": status_filter,
                     "valid": list(VALID_STATUSES)})

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
            error(f"Error: offer #{offer_id} not found.")
            die(f"offer #{offer_id} not found.", code="not_found",
                details={"offer_id": offer_id},
                text="  Hint: run 'applyr list' to see available offers.")

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

def cmd_update(offer_id: int, status: str, notes: str | None = None,
               canal: str | None = None, cv: str | None = None) -> None:
    """Update the status (and optionally notes/canal/cv) of an offer."""
    if status not in VALID_STATUSES:
        die(f"Error: invalid status '{status}'. Valid: {', '.join(VALID_STATUSES)}", code="invalid_value", details={"field": "status", "value": status, "valid": list(VALID_STATUSES)})
    if canal and canal not in VALID_CHANNELS:
        die(f"Error: invalid canal '{canal}'. Valid: {', '.join(VALID_CHANNELS)}", code="invalid_value", details={"field": "canal", "value": canal, "valid": list(VALID_CHANNELS)})
    config = load_config()
    followup_days: int = config["general"]["followup_days"]

    conn = get_conn()
    try:
        row = conn.execute("SELECT id, title, company FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            error(f"Error: offer #{offer_id} not found.")
            die(f"offer #{offer_id} not found.", code="not_found",
                details={"offer_id": offer_id},
                text="  Hint: run 'applyr list' to see available offers.")

        # Build dynamic update
        fields: list[str] = ["status = ?"]
        params: list = [status]

        if notes is not None:
            fields.append("notes = ?")
            params.append(notes)

        if canal is not None:
            fields.append("canal = ?")
            params.append(canal)

        # Which CV was sent — feeds `applyr cv stats`. Set automatically by
        # `cv generate`; this is the manual path for offers applied elsewhere.
        # `--cv ""` clears the link: store NULL rather than an empty string so
        # "never had a CV" and "CV unlinked" are the same value in the database.
        if cv is not None:
            fields.append("cv_used = ?")
            params.append(cv.strip() or None)

        # Auto follow-up when moving to applied/waiting
        if status in ("applied", "waiting"):
            new_follow_up = (date.today() + timedelta(days=followup_days)).isoformat()
            fields.append("follow_up_date = ?")
            params.append(new_follow_up)

            # Stamp the send date too. Without it `summary` counts zero
            # applications, the default `list` sort has nothing to sort on and
            # follow-ups never come due. COALESCE keeps the original date when
            # an offer moves applied -> waiting.
            fields.append("date_applied = COALESCE(date_applied, ?)")
            params.append(_today())

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

def cmd_delete(offer_id: int, force: bool = False) -> None:
    """Delete an offer and its associated topics (CASCADE)."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT id, title, company, status FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            error(f"Error: offer #{offer_id} not found.")
            die(f"offer #{offer_id} not found.", code="not_found",
                details={"offer_id": offer_id},
                text="  Hint: run 'applyr list' to see available offers.")

        print(f"About to delete:")
        print(f"  #{row['id']}  {row['title']}  ({row['company'] or '—'})  [{STATUS_LABELS.get(row['status'], row['status'])}]")

        if not force:
            # Without a terminal there is nobody to answer the prompt, and
            # input() would raise EOFError as a bare traceback.
            if not sys.stdin.isatty():
                die("Refusing to delete without confirmation.", code="confirmation_required",
                    details={"offer_id": offer_id},
                    text="  No terminal available to confirm. Pass --force to delete.")
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
            die(f"Error: invalid status '{status_filter}'. Valid: {', '.join(VALID_STATUSES)}",
                code="invalid_value",
                details={"field": "status", "value": status_filter,
                         "valid": list(VALID_STATUSES)})
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
