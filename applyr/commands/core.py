"""CRUD and setup commands: init, setup-agent, add, list, show, update, delete, search."""

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from applyr import __version__
from applyr.agent_instructions import (
    FALLBACK,
    is_stale,
    packaged_instructions,
    stamp,
    stamped_version,
)
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
    REPLY_STATUSES,
    SENT_STATUSES,
    STATUS_LABELS,
    VALID_CHANNELS,
    VALID_LANGUAGES,
    VALID_ROLE_CATEGORIES,
    VALID_SENIORITY,
    VALID_STATUSES,
    VALID_WORK_MODES,
    get_conn,
    get_db_path,
    init_db,
)
from applyr.scoring import calculate_score
from applyr.commands._helpers import _bar, _today, _truncate, _classify_topic, _show_score_breakdown
from applyr.duplicates import find_company_offers, find_exact, find_similar
from applyr.errors import die, error, warn

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_CV_MASTER_TEMPLATE = """\
# CV Master — Your Name

## Summary
...

## Experience
...

## Education
...

## Skills
...
"""


def _cv_master_template_text() -> str:
    """Return the starter cv-master.md: the packaged template if present.

    The full template lives in `templates/cv-master-template.md` so it can be
    edited alongside the other shipped files; this constant is only a fallback
    for installations that lack it. Keeping a bare `...` per section matters:
    `inspect_cv_master()` flags those as unfilled, so the guard that stops `cv
    generate` from building a CV on nothing keeps working on a fresh template.
    """
    src = Path(__file__).parent.parent / "templates" / "cv-master-template.md"
    if src.exists():
        return src.read_text()
    return _CV_MASTER_TEMPLATE


_STATUS_ORDER = ["applied", "waiting", "in_process", "offer", "pending", "discarded", "rejected"]

# What `--sort` accepts, mapped to the column each name means. The keys are the
# public contract; the values are storage detail that used to leak out as the
# only working vocabulary — `--sort compatibility_pct` sorted, `--sort score`
# silently did not. Anything outside this mapping is an error, not a fallback,
# and the allowlist still keeps the column name out of string interpolation.
SORT_FIELDS = {
    "score": "compatibility_pct",
    "compatibility_pct": "compatibility_pct",
    "date": "date_applied",
    "date_applied": "date_applied",
    "date_received": "date_received",
    "company": "company",
    "status": "status",
    "id": "id",
}

_AGENT_TARGETS = {
    "claude":   ("CLAUDE.md",),
    "cursor":   (".cursorrules",),
    "opencode": ("AGENTS.md",),
    "generic":  ("AGENTS.md",),
}

# Canonical per-user global paths for `--global`. Resolved against the user's home.
_AGENT_GLOBAL_TARGETS = {
    "claude":   ".claude/CLAUDE.md",
    "cursor":   ".cursorrules",
    "opencode": ".config/opencode/AGENTS.md",
}

_AGENT_DETECT_ORDER = [
    ("claude",   "CLAUDE.md"),
    ("claude",   ".claude/CLAUDE.md"),
    ("cursor",   ".cursorrules"),
    ("cursor",   ".cursor/rules"),
    ("generic",  "AGENTS.md"),
]


# ---------------------------------------------------------------------------
# Recommendation helpers
# ---------------------------------------------------------------------------

def _get_recommendation(score: int, config: dict) -> tuple[str, str]:
    """Get recommendation state and icon based on score and thresholds.

    Returns:
        Tuple of (recommendation, icon) where recommendation is
        "apply", "maybe", or "low_match" and icon is the display emoji.
    """
    general = config.get("general", {})
    threshold_apply = general.get("threshold_apply", 80)
    threshold_maybe = general.get("threshold_maybe", 60)

    if score >= threshold_apply:
        return "apply", "✅"
    elif score >= threshold_maybe:
        return "maybe", "⚠️"
    else:
        return "low_match", "❌"


def _get_recommendation_label(recommendation: str) -> str:
    """Get human-readable label for recommendation."""
    labels = {
        "apply": "STRONG MATCH: APPLY",
        "maybe": "GOOD MATCH: MAYBE",
        "low_match": "LOW MATCH: SKIP",
    }
    return labels.get(recommendation, recommendation.upper())


def _show_match_breakdown(topics: list[dict], topic_labels: dict) -> None:
    """Show skill-level match breakdown (Strong/Partial/Missing)."""
    if not topics:
        return

    strong = []
    partial = []
    missing = []

    for t in topics:
        score = t.get("score", 0)
        classification = _classify_topic(score)
        entry = {
            "topic": t["topic"],
            "score": score,
            "detail": t.get("detail", ""),
            "label": topic_labels.get(t["topic"], t["topic"]),
        }
        if classification == "strong":
            strong.append(entry)
        elif classification == "partial":
            partial.append(entry)
        else:
            missing.append(entry)

    if strong:
        print("\n  Strong:")
        for e in strong:
            detail = f" ({e['detail']})" if e["detail"] else ""
            print(f"    ✓ {e['label']}: {e['score']}%{detail}")

    if partial:
        print("\n  Partial:")
        for e in partial:
            detail = f" ({e['detail']})" if e["detail"] else ""
            print(f"    △ {e['label']}: {e['score']}%{detail}")

    if missing:
        print("\n  Missing:")
        for e in missing:
            detail = f" ({e['detail']})" if e["detail"] else ""
            print(f"    ✕ {e['label']}: {e['score']}%{detail}")


def _get_match_breakdown(topics: list[dict]) -> dict:
    """Get match breakdown as dict for JSON output."""
    strong = []
    partial = []
    missing = []

    for t in topics:
        score = t.get("score", 0)
        classification = _classify_topic(score)
        entry = {"topic": t["topic"], "score": score, "detail": t.get("detail", "")}
        if classification == "strong":
            strong.append(entry)
        elif classification == "partial":
            partial.append(entry)
        else:
            missing.append(entry)

    return {"strong": strong, "partial": partial, "missing": missing}


def _get_why_you_match(topics: list[dict], topic_labels: dict) -> tuple[list[str], str | None]:
    """Get top 3 strong topics and biggest weakness.

    Returns:
        Tuple of (why_match_lines, biggest_weakness)
    """
    strong = []
    partial = []
    missing = []

    for t in topics:
        score = t.get("score", 0)
        label = topic_labels.get(t["topic"], t["topic"])
        detail = t.get("detail", "")
        entry = f"• {label}: {detail}" if detail else f"• {label} (score: {score})"

        classification = _classify_topic(score)
        if classification == "strong":
            strong.append((score, entry))
        elif classification == "partial":
            partial.append((score, entry))
        else:
            missing.append((score, entry))

    # Top 3 strong topics (sorted by score descending)
    strong.sort(key=lambda x: x[0], reverse=True)
    why_match = [entry for _, entry in strong[:3]]

    # Biggest weakness: the lowest-scoring topic that is not already strong.
    #
    # This used to read "lowest partial, or else highest missing", which got it
    # wrong twice. Preferring the partial bucket meant a topic scored 30 and
    # printed under "Missing" two lines above was passed over for one scored 50
    # — the line contradicted the breakdown it sits under. And the missing
    # branch sorted descending, so when everything was weak it surfaced the
    # *least* bad of them.
    weak = partial + missing
    biggest_weakness = min(weak, key=lambda x: x[0])[1] if weak else None

    return why_match, biggest_weakness

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_agent_instructions() -> str:
    """Return the instructions `setup-agent` should inject into a project.

    The local copy wins while it is current, so hand edits survive. Once it falls
    behind the installed package it is bypassed rather than rewritten: the file
    belongs to the user, and silently overwriting it would be the mirror image of
    the bug this fixes.
    """
    local = APPLYR_DIR / "AGENT_INSTRUCTIONS.md"
    if not local.exists():
        packaged = packaged_instructions()
        return stamp(packaged) if packaged else ""

    local_text = local.read_text()
    if not is_stale(local_text):
        return local_text

    packaged = packaged_instructions()
    if not packaged:
        return local_text  # stale, but there is nothing better to offer

    warn(f"Local AGENT_INSTRUCTIONS.md is from applyr "
         f"{stamped_version(local_text) or 'an unstamped version'}; "
         f"using the {__version__} instructions from the package instead.")
    warn(f"  {local} was left untouched. "
         "Delete it and run 'applyr init' to refresh it.")
    return stamp(packaged)


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
        cv_master_path.write_text(_cv_master_template_text())
        print(f"  Created {cv_master_path}  (edit this with your master CV content)")
    else:
        print(f"  {cv_master_path} already exists — skipped")

    # Copy AGENT_INSTRUCTIONS.md
    agent_instructions_dst = APPLYR_DIR / "AGENT_INSTRUCTIONS.md"
    if not agent_instructions_dst.exists():
        packaged = packaged_instructions()
        agent_instructions_dst.write_text(stamp(packaged) if packaged else FALLBACK)
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

def _warn_if_profile_empty() -> None:
    """Warn when cv-master.md cannot produce a truthful CV.

    `setup-agent` can succeed today while `cv generate` still refuses to run —
    the profile simply has nothing in it. The first time a user meets that
    failure is inside a job application; better to surface the missing piece
    now, while setting up, than at the moment it matters.
    """
    from applyr.cv import get_cv_master_path
    from applyr.cv_master import inspect_cv_master

    cv_master = get_cv_master_path()
    if not cv_master.exists():
        warn(f"Warning: {cv_master} not found.")
        warn("  Run 'applyr init' to create the template, then fill it with "
             "your professional profile before generating CVs.")
        return
    report = inspect_cv_master(cv_master.read_text(encoding="utf-8"))
    if not report.filled:
        warn(f"Warning: {cv_master} is {report.reason}.")
        warn("  Edit it with your professional profile before generating CVs — "
             "applyr refuses to build a CV on nothing.")


def cmd_setup_agent(agent: str | None = None, global_: bool = False) -> None:
    """Write applyr agent instructions into the project or user-global AI config file."""
    cwd = Path.cwd()
    instructions = _get_agent_instructions()
    if not instructions:
        error("Error: could not find AGENT_INSTRUCTIONS.md")
        die("Could not find AGENT_INSTRUCTIONS.md", code="not_found",
            text="  Run 'applyr init' first.")

    # Auto-detect only when targeting the current project; --global needs an explicit agent
    detected_path: str | None = None
    if not agent and not global_:
        for name, path in _AGENT_DETECT_ORDER:
            if (cwd / path).exists():
                agent = name
                detected_path = path
                print(f"  Detected {name} config ({path})")
                break

    if not agent:
        if global_:
            error("Error: --global requires an explicit --agent")
            die("--global requires an explicit --agent", code="invalid_value",
                text="  Supported: --agent claude | cursor | opencode")
        print("No AI agent config detected in this directory.")
        print("  Supported: --agent claude | cursor | opencode | generic")
        print("  Example: applyr setup-agent --agent claude")
        return

    if agent not in _AGENT_TARGETS:
        error(f"Error: unknown agent '{agent}'")
        die(f"Unknown agent '{agent}'", code="invalid_value",
            details={"value": agent, "valid": list(_AGENT_TARGETS)},
            text=f"  Supported: {', '.join(_AGENT_TARGETS.keys())}")

    if global_ and agent not in _AGENT_GLOBAL_TARGETS:
        error(f"Error: agent '{agent}' has no canonical global path")
        die(f"Agent '{agent}' has no canonical global path", code="invalid_value",
            details={"value": agent, "global_targets": list(_AGENT_GLOBAL_TARGETS)},
            text="  --global is only supported for claude, cursor and opencode")

    _warn_if_profile_empty()

    if agent == "opencode" and (cwd / ".opencode/instructions.md").exists():
        warn("Deprecation: .opencode/instructions.md is no longer read by OpenCode "
             "— instructions for setup-agent now go to AGENTS.md")

    if global_:
        rel_path = _AGENT_GLOBAL_TARGETS[agent]
        target = Path.home() / rel_path
        display = "~/" + rel_path
    else:
        # `_AGENT_DETECT_ORDER` lists two valid locations for claude
        # (`CLAUDE.md`, `.claude/CLAUDE.md`) and cursor (`.cursorrules`,
        # `.cursor/rules`). Detection matched one of them, but the target was
        # always the first — a project already using `.claude/CLAUDE.md` got
        # a brand new top-level `CLAUDE.md` instead of its own file appended,
        # splitting the agent's context across two files it never asked for.
        # `detected_path` is only ever a value from that curated table, never
        # user input, so writing to it directly is safe.
        rel_path = detected_path or _AGENT_TARGETS[agent][0]
        target = cwd / rel_path
        display = rel_path

    # Create parent dirs if needed (e.g. .claude/ or ~/.config/opencode/)
    target.parent.mkdir(parents=True, exist_ok=True)

    # If file exists, append (don't overwrite user content)
    if target.exists():
        existing = target.read_text()
        if "applyr" in existing.lower() and "agent instructions" in existing.lower():
            print(f"  {display} already contains applyr instructions — skipped.")
            return
        separator = "\n\n---\n\n"
        target.write_text(existing.rstrip() + separator + instructions)
        print(f"  Appended applyr instructions to {display}")
    else:
        target.write_text(instructions)
        print(f"  Created {display} with applyr instructions")

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
    language: str | None = data.get("language")
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
    if language and language not in VALID_LANGUAGES:
        die(f"Error: invalid language '{language}'. Valid: {', '.join(VALID_LANGUAGES)}", code="invalid_value", details={"field": "language", "value": language, "valid": list(VALID_LANGUAGES)})
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
                seniority_level, role_category, tech_stack, language,
                cover_letter, cover_letter_file,
                contact_name, contact_role, job_url, rejection_reason, notes
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, 0, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?
            )
            """,
            (
                title, company, summary, date_received, date_applied, date_responded,
                compatibility_pct, status, canal, cv_used,
                follow_up_date, data.get("follow_up_notes"),
                work_mode, location, salary_min, salary_max, salary_period,
                seniority_level, role_category, tech_stack, language,
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
            # Track gaps: topics below threshold (for in-memory notice only)
            if isinstance(score, (int, float)) and score < threshold:
                skill_gaps.append((topic_key, threshold - score))

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

    # --- Three-state recommendation ----------------------------------------
    recommendation, icon = _get_recommendation(compatibility_pct, config)
    rec_label_text = _get_recommendation_label(recommendation)
    print(f"\n  >> {icon} {rec_label_text} (score {compatibility_pct}%)")

    # --- Skill-level breakdown ---------------------------------------------
    topics_list = [{"topic": k, "score": v.get("score", 0), "detail": v.get("detail", "")}
                   for k, v in topics.items()]
    if topics_list:
        _show_match_breakdown(topics_list, TOPIC_LABELS)

        # --- Why you match ---------------------------------------------------
        why_match, biggest_weakness = _get_why_you_match(topics_list, TOPIC_LABELS)
        if why_match:
            print("\n  Why you match:")
            for line in why_match:
                print(f"    {line}")
        if biggest_weakness:
            print("\n  Biggest weakness:")
            print(f"    {biggest_weakness}")

    if recommendation == "apply":
        print(f"\n     Next: 'applyr cv generate {offer_id}' to create a tailored CV")
    elif recommendation == "maybe":
        print(f"\n     Consider: review the gaps above before deciding")
        print(f"     Next: 'applyr cv generate {offer_id}' to create a tailored CV")
    else:
        print(f"\n     Consider: 'applyr update {offer_id} discarded' to archive this offer")


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

    # Same reasoning as the status check above, which this used to ignore: an
    # unrecognised sort field fell through to the default, so `--sort score`
    # returned an unsorted list and said nothing. Only raw column names worked,
    # and none of them were documented anywhere.
    if sort_by not in SORT_FIELDS:
        die(f"Error: invalid sort field '{sort_by}'. Valid: {', '.join(sorted(SORT_FIELDS))}",
            code="invalid_value",
            details={"field": "sort", "value": sort_by, "valid": sorted(SORT_FIELDS)})
    sort_by = SORT_FIELDS[sort_by]

    # 0 is the "no limit" sentinel used by `--all`; anything below it would
    # reach SQLite as a negative LIMIT, which it reads as unbounded.
    if limit is not None and limit < 0:
        die(f"Error: limit cannot be negative, got: {limit}",
            code="invalid_value", details={"field": "limit", "value": limit})

    config = load_config()
    effective_limit = limit if limit is not None else config["general"]["list_limit"]

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
        if as_json:
            print(json.dumps([], indent=2, ensure_ascii=False))
        else:
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
    _field("Language", row["language"])
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

        # Skill-level breakdown
        _show_match_breakdown([dict(t) for t in topics], topic_labels)

        # Score breakdown
        _show_score_breakdown([dict(t) for t in topics], config.get("weights", {}))

    # Recommendation
    recommendation, icon = _get_recommendation(row["compatibility_pct"], config)
    rec_label_text = _get_recommendation_label(recommendation)
    print(f"\n  >> {icon} {rec_label_text} (score {row['compatibility_pct']}%)")

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

        # The `applied` column is the machine-readable form of "this went out",
        # and `response_rate` filters on it. Deriving it from the status here
        # keeps it honest in both directions: a status moved back to pending or
        # discarded clears the flag rather than leaving a stale 1 behind.
        sent = status in SENT_STATUSES
        fields.append("applied = ?")
        params.append(1 if sent else 0)

        # Stamp the send date for anything that went out, not just applied and
        # waiting. `response_rate` requires both the flag and the date, so an
        # offer taken straight to rejected — a real path, the reply arrives
        # before the status is ever moved to applied — would otherwise carry
        # applied = 1 with no date and drop out of the metric entirely.
        # COALESCE keeps the original date across later transitions.
        if sent:
            fields.append("date_applied = COALESCE(date_applied, ?)")
            params.append(_today())

        # Auto follow-up only while an answer is still owed. A rejected or
        # closed offer needs no chasing.
        if status in ("applied", "waiting"):
            new_follow_up = (date.today() + timedelta(days=followup_days)).isoformat()
            fields.append("follow_up_date = ?")
            params.append(new_follow_up)

        # Record response date when first response received. The status doubles
        # as the response kind: `response_status` had no writer at all until
        # now, so `response_rate` counted every application as unanswered no
        # matter what happened to it. COALESCE keeps the first reply's date;
        # the status itself tracks the latest one.
        if status in REPLY_STATUSES:
            fields.append("date_responded = COALESCE(date_responded, ?)")
            params.append(_today())
            fields.append("response_status = ?")
            params.append(status)

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

def cmd_search(keyword: str, status_filter: str | None = None, company: str | None = None,
                as_json: bool = False) -> None:
    """Search offers by keyword across title, company, summary, notes, tech_stack.

    `company` switches to an exact, case-insensitive company match instead —
    the same definition `add`'s duplicate check uses (`find_company_offers`).
    Free-text `keyword` search stays substring-based on purpose, since it
    scans five unrelated fields at once; making that fuzzy on company names
    risks false positives on short names (e.g. "IO" inside "Studio"). The
    workflow's "check duplicates before adding" step needs the stricter,
    add-compatible definition, so it gets its own flag instead.
    """
    if status_filter and status_filter not in VALID_STATUSES:
        die(f"Error: invalid status '{status_filter}'. Valid: {', '.join(VALID_STATUSES)}",
            code="invalid_value",
            details={"field": "status", "value": status_filter,
                     "valid": list(VALID_STATUSES)})

    conn = get_conn()
    try:
        if company:
            matches = find_company_offers(conn, company)
            ids = [row["id"] for row in matches]
            if not ids:
                rows = []
            else:
                placeholders = ",".join("?" * len(ids))
                query = f"""
                    SELECT id, company, title, compatibility_pct, status, work_mode, date_applied, date_received
                    FROM offers
                    WHERE id IN ({placeholders})
                """
                params: list = list(ids)
                if status_filter:
                    query += " AND status = ?"
                    params.append(status_filter)
                query += " ORDER BY COALESCE(date_applied, date_received) DESC"
                rows = conn.execute(query, params).fetchall()
        else:
            pattern = f"%{keyword}%"
            query = """
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
            params = [pattern] * 5
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            query += " ORDER BY COALESCE(date_applied, date_received) DESC"
            rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    target = f"company '{company}'" if company else f"'{keyword}'"

    if not rows:
        if as_json:
            print(json.dumps([], indent=2, ensure_ascii=False))
        else:
            print(f"No offers found matching {target}.")
        return

    if as_json:
        print(json.dumps([dict(r) for r in rows], indent=2, ensure_ascii=False))
        return

    display = [_make_display_row(r) for r in rows]
    _print_table(display, LIST_HEADERS, LIST_COL_WIDTHS)
    print(f"  {len(rows)} result(s) for {target}.")
