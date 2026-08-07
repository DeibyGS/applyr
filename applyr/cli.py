"""CLI entry point — argparse setup, command routing, error handling."""

import os
import sys

from applyr import __version__
from applyr.colors import init_colors
from applyr.commands import (
    cmd_add,
    cmd_cv_stats,
    cmd_compare,
    cmd_delete,
    cmd_doctor,
    cmd_export,
    cmd_followups,
    cmd_gaps,
    cmd_init,
    cmd_list,
    cmd_pipeline,
    cmd_plan,
    cmd_salary,
    cmd_search,
    cmd_setup_agent,
    cmd_show,
    cmd_stats,
    cmd_summary,
    cmd_trends,
    cmd_update,
)
from applyr.cv import cmd_cv_generate, cmd_cv_pdf, cmd_cv_review
from applyr.db import init_db, VALID_STATUSES
from applyr.errors import die, error, set_json_mode

USAGE = f"""\
applyr v{__version__} — CLI job application tracker for AI coding agents

Usage: applyr <command> [options]

Commands:
  init                          Set up ~/.applyr/ (config, database, templates)
  setup-agent [--agent NAME]    Configure AI agent (claude, cursor, opencode, generic)
  add '<json>' [--force]        Register a new job offer (--force skips duplicate check)
  list [--status S] [--sort F]  List offers (default: last 50)
  pipeline [--min-score N]      View offers grouped by status
  show <id>                     Show full offer details
  update <id> <status> [opts]   Update offer status (--notes, --canal, --cv)
  delete <id>                   Delete an offer
  search <keyword> [--status S] Search by company/title/notes/tech_stack
  stats                         Conversion funnel and metrics
  gaps [--limit N]              Skill gap analysis
  followups                     Pending/overdue follow-ups
  trends [--period week|month]  Application trends over time
  summary [--json]              Weekly summary (LLM-optimized)
  compare <id1> <id2> [<idN>..] Compare offers side by side
  plan [--limit N]              Prioritized learning plan from skill gaps
  salary [--seniority S]        Salary insights by seniority/category
  export [--format csv|json|md]  Export all data
  cv stats [--min-sample N]     Compare CVs by response and interview rate
  doctor [--json]               Check configuration and database health (exit 1 if unhealthy)
  version                       Show version
  help                          Show this help

Aliases: ls=list, st=stats, fu=followups, cmp=compare, sal=salary

Statuses: {' | '.join(VALID_STATUSES)}

Docs: https://github.com/DeibyGS/applyr
"""


def _safe_int(value: str, label: str = "ID") -> int:
    """Parse string to int. Exits with an error if the value is not an integer."""
    try:
        return int(value)
    except ValueError:
        die(f"Error: {label} must be an integer, got: {value}",
            code="invalid_argument",
            details={"argument": label, "value": value})


def _get_flag(args: list[str], flag: str) -> str | None:
    """Get the value after a flag like --status, or None if not present."""
    if flag not in args:
        return None
    idx = args.index(flag)
    if idx + 1 >= len(args):
        die(f"Error: {flag} requires a value",
            code="missing_value", details={"flag": flag})
    return args[idx + 1]


def _has_flag(args: list[str], flag: str) -> bool:
    """Check if a flag is present."""
    return flag in args


_GETTING_STARTED = f"""\
applyr v{__version__} — CLI job application tracker for AI coding agents

Getting started:

  1. applyr init                        Set up config, database, and templates
  2. Edit ~/.applyr/cv-master.md        Fill in your professional profile
  3. applyr setup-agent --agent claude  Connect your AI agent (claude, cursor, opencode, generic)

Then paste a job offer into your AI agent — it handles the rest.
Docs: https://github.com/DeibyGS/applyr
"""


def _is_initialized() -> bool:
    """Check if applyr has been initialized."""
    from applyr.config import APPLYR_DIR
    return (APPLYR_DIR / "jobs.db").exists() or (APPLYR_DIR / "applyr.toml").exists()


def main():
    args = sys.argv[1:]

    # Global flags — extract before command routing
    no_color = _has_flag(args, "--no-color")
    if no_color and "--no-color" in args:
        args.remove("--no-color")
    as_json = _has_flag(args, "--json")
    if as_json and "--json" in args:
        args.remove("--json")

    init_colors(no_color=no_color or as_json)
    set_json_mode(as_json)

    if not args or args[0] in ("help", "--help", "-h"):
        if not args and not _is_initialized():
            print(_GETTING_STARTED)
        else:
            print(USAGE)
        return

    cmd = args[0]

    if cmd in ("version", "--version", "-v"):
        print(f"applyr v{__version__}")
        return

    # Commands that need DB initialized. `doctor` is excluded on purpose: it
    # must observe the environment, not mutate it. While it ran through this
    # path the database was recreated before the check, so its "NOT FOUND"
    # branch was unreachable and a missing database always reported OK.
    if cmd not in ("init", "doctor"):
        try:
            init_db()
        except Exception as e:
            error(f"Error: could not initialize database: {e}")
            die(f"Could not initialize database: {e}", code="db_error",
                details={"reason": str(e)}, text="  Try running: applyr init")

    if cmd == "init":
        cmd_init()

    elif cmd == "setup-agent":
        agent = _get_flag(args, "--agent")
        cmd_setup_agent(agent=agent)

    elif cmd == "add":
        # Extract --force before positional parsing, so it can appear anywhere
        force = _has_flag(args, "--force")
        if force:
            args.remove("--force")
        # `--help` must win over JSON parsing, otherwise asking for usage is
        # reported as an invalid-JSON error.
        wants_help = len(args) >= 2 and args[1] in ("--help", "-h")
        if wants_help or (len(args) < 2 and sys.stdin.isatty()):
            print("Usage: applyr add '<json>' [--force]")
            print("       applyr add offer.json")
            print("       cat offer.json | applyr add -")
            print("  --force: add even if a duplicate offer is detected")
            print("  Required: title")
            print("  Optional: company, summary, date_received, date_applied,")
            print("            compatibility_pct, status, canal, work_mode,")
            print("            location, salary_min, salary_max, seniority_level,")
            print("            role_category, tech_stack, cover_letter, job_url,")
            print("            contact_name, contact_role, topics, notes")
            return
        if len(args) >= 2 and args[1] == "-":
            raw = sys.stdin.read()
        elif len(args) >= 2 and os.path.isfile(args[1]):
            with open(args[1], encoding="utf-8") as f:
                raw = f.read()
        elif len(args) >= 2:
            raw = args[1]
        else:
            raw = sys.stdin.read()
        cmd_add(raw, force=force)

    elif cmd == "list":
        status = _get_flag(args, "--status")
        sort_by = _get_flag(args, "--sort") or "date_applied"
        limit = None
        if _has_flag(args, "--all"):
            limit = -1
        elif _get_flag(args, "--limit") is not None:
            limit = _safe_int(_get_flag(args, "--limit"), "--limit")
        cmd_list(status_filter=status, sort_by=sort_by, limit=limit, as_json=as_json)

    elif cmd == "pipeline":
        min_score = 0
        raw = _get_flag(args, "--min-score")
        if raw is not None:
            min_score = _safe_int(raw, "--min-score")
        cmd_pipeline(min_score=min_score, as_json=as_json)

    elif cmd == "show":
        if len(args) < 2:
            print("Usage: applyr show <id>")
            return
        offer_id = _safe_int(args[1])
        cmd_show(offer_id, as_json=as_json)

    elif cmd == "update":
        if len(args) < 3:
            print("Usage: applyr update <id> <status> [--notes '...'] [--canal '...'] [--cv file.html]")
            print("  --cv \"\": clear the CV linked to this offer")
            print(f"  Statuses: {', '.join(VALID_STATUSES)}")
            return
        offer_id = _safe_int(args[1])
        status = args[2]
        notes = _get_flag(args, "--notes")
        canal = _get_flag(args, "--canal")
        cv = _get_flag(args, "--cv")
        cmd_update(offer_id, status, notes, canal, cv)

    elif cmd == "delete":
        if len(args) < 2 or args[1] in ("--help", "-h"):
            print("Usage: applyr delete <id> [--force]")
            print("  --force: skip the confirmation prompt (required when not on a terminal)")
            return
        offer_id = _safe_int(args[1])
        cmd_delete(offer_id, force=_has_flag(args, "--force"))

    elif cmd == "search":
        if len(args) < 2:
            print("Usage: applyr search <keyword> [--status S]")
            return
        status = _get_flag(args, "--status")
        # Collect keyword (everything between cmd and flags)
        keyword_parts = []
        i = 1
        while i < len(args):
            if args[i].startswith("--"):
                i += 2 if (i + 1 < len(args)) else 1
                continue
            keyword_parts.append(args[i])
            i += 1
        keyword = " ".join(keyword_parts)
        cmd_search(keyword, status_filter=status, as_json=as_json)

    elif cmd == "stats":
        cmd_stats(as_json=as_json)

    elif cmd == "gaps":
        limit = 10
        raw = _get_flag(args, "--limit")
        if raw is not None:
            limit = _safe_int(raw, "--limit")
        cmd_gaps(limit=limit, as_json=as_json)

    elif cmd == "followups":
        cmd_followups(as_json=as_json)

    elif cmd == "trends":
        period = _get_flag(args, "--period") or "week"
        if period not in ("week", "month"):
            die(f"Error: period must be 'week' or 'month', got: {period}", code="invalid_value")
        cmd_trends(period=period, as_json=as_json)

    elif cmd == "summary":
        cmd_summary(as_json=as_json)

    elif cmd in ("compare", "cmp"):
        if len(args) == 1:
            print("Usage: applyr compare <id1> <id2> [<id3> ...]")
            return
        if len(args) < 3:
            die("compare needs at least 2 offer IDs.",
                code="invalid_argument",
                details={"given": len(args) - 1, "minimum": 2},
                text="Usage: applyr compare <id1> <id2> [<id3> ...]")
        ids = []
        for a in args[1:]:
            oid = _safe_int(a)
            ids.append(oid)
        cmd_compare(ids, as_json=as_json)

    elif cmd == "plan":
        limit = 10
        raw = _get_flag(args, "--limit")
        if raw is not None:
            limit = _safe_int(raw, "--limit")
        cmd_plan(limit=limit, as_json=as_json)

    elif cmd in ("salary", "sal"):
        seniority = _get_flag(args, "--seniority")
        category = _get_flag(args, "--category")
        cmd_salary(seniority=seniority, category=category, as_json=as_json)

    elif cmd == "doctor":
        cmd_doctor(as_json=as_json)

    elif cmd == "export":
        fmt = _get_flag(args, "--format") or "csv"
        if fmt not in ("csv", "json", "md", "markdown"):
            die(f"Error: format must be 'csv', 'json', or 'md', got: {fmt}", code="invalid_value")
        if fmt == "markdown":
            fmt = "md"
        filepath = _get_flag(args, "--file")
        cmd_export(fmt=fmt, filepath=filepath)

    elif cmd == "cv":
        if len(args) < 2:
            print("Usage:")
            print("  applyr cv generate <id> [--template ats] [--force]")
            print("                                            Generate CV for offer")
            print("  applyr cv review <html-file>              Recruiter review prompt")
            print("  applyr cv pdf <html-file> [--output f.pdf] HTML to PDF via Chrome")
            return
        subcmd = args[1]
        if subcmd == "generate":
            if len(args) < 3 or args[2] in ("--help", "-h"):
                print("Usage: applyr cv generate <id> [--template ats] [--force]")
                print("  --force: overwrite an existing CV for this offer")
                return
            offer_id = _safe_int(args[2])
            template = _get_flag(args, "--template") or "ats"
            cmd_cv_generate(offer_id, template=template, force=_has_flag(args, "--force"))
        elif subcmd == "review":
            if len(args) < 3:
                print("Usage: applyr cv review <html-file>")
                return
            cmd_cv_review(args[2], as_json=as_json)
        elif subcmd == "pdf":
            if len(args) < 3:
                print("Usage: applyr cv pdf <html-file> [--output file.pdf]")
                return
            html_file = args[2]
            output = _get_flag(args, "--output")
            cmd_cv_pdf(html_file, output=output)
        elif subcmd == "stats":
            min_sample = 1
            raw = _get_flag(args, "--min-sample")
            if raw is not None:
                min_sample = _safe_int(raw, "--min-sample")
            cmd_cv_stats(min_sample=min_sample, as_json=as_json)
        else:
            die(f"Unknown cv subcommand: '{subcmd}'", code="invalid_value",
                details={"value": subcmd, "valid": ["generate", "review", "pdf", "stats"]})
            print("  Available: generate, review, pdf")

    elif cmd == "ls":
        cmd_list(as_json=as_json)

    elif cmd == "st":
        cmd_stats(as_json=as_json)

    elif cmd == "fu":
        cmd_followups(as_json=as_json)

    else:
        print(f"Unknown command: '{cmd}'")
        print("Run 'applyr help' to see available commands.")


if __name__ == "__main__":
    main()
