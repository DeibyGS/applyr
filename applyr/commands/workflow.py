"""Export and doctor commands."""

import csv
import json
import os
import sys
from pathlib import Path

from applyr import __version__
from applyr.agent_instructions import is_stale, stamped_version
from applyr.config import APPLYR_DIR, load_config
from applyr.constants import CV_STATS_NAME_WIDTH
from applyr.cv import get_cv_master_path
from applyr.cv_master import inspect_cv_master
from applyr.cv_stats import build_report
from applyr.db import SCHEMA_VERSION, get_conn, get_schema_version
from applyr.errors import die


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _export_markdown(records: list[dict]) -> str:
    """Convert offer records to a Markdown table."""
    lines = ["# applyr — Job Applications Export", ""]
    lines.append("| ID | Company | Title | % | Status | Mode | Applied | Tech Stack |")
    lines.append("|---:|---------|-------|--:|--------|------|---------|------------|")
    for r in records:
        lines.append(
            f"| {r['id']} "
            f"| {r.get('company') or '—'} "
            f"| {r['title']} "
            f"| {r.get('compatibility_pct', 0)} "
            f"| {r.get('status', '—')} "
            f"| {r.get('work_mode') or '—'} "
            f"| {r.get('date_applied') or r.get('date_received') or '—'} "
            f"| {r.get('tech_stack') or '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# cmd_export
# ---------------------------------------------------------------------------

def cmd_export(fmt: str = "csv", filepath: str | None = None) -> None:
    """Export all offers to CSV, JSON, or Markdown."""
    if fmt not in ("csv", "json", "md"):
        die(f"Error: unsupported format '{fmt}'. Use 'csv', 'json', or 'md'.", code="invalid_value")

    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM offers ORDER BY id").fetchall()
    finally:
        conn.close()

    if not rows:
        print("No offers to export.")
        return

    records = [dict(r) for r in rows]

    ext = "md" if fmt == "md" else fmt
    default_name = f"applyr_export.{ext}"

    # Default into APPLYR_DIR, not the working directory. An export is the whole
    # database in one file — every company, score, note and private assessment —
    # and dropping it wherever the user happens to stand means dropping it into
    # a checkout more often than not, untracked and one `git add .` from being
    # published. Everything else applyr owns already lives here; this was the
    # only command that wrote outside it. An explicit path still wins.
    out_path = Path(filepath).expanduser() if filepath else APPLYR_DIR / default_name

    try:
        if fmt == "csv":
            fieldnames = list(records[0].keys())
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
        elif fmt == "json":
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        elif fmt == "md":
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(_export_markdown(records))
    except OSError as exc:
        die(f"Error: writing file — {exc}")

    print(f"Exported {len(records)} offer(s) to {out_path}")


# ---------------------------------------------------------------------------
# cmd_doctor
# ---------------------------------------------------------------------------

def _ok(name: str, message: str) -> dict:
    """A check that passed."""
    return {"name": name, "status": "ok", "message": message, "hint": None}


def _issue(name: str, message: str, hint: str | None = None) -> dict:
    """A check that failed in a way that makes the rest of applyr unreliable."""
    return {"name": name, "status": "issue", "message": message, "hint": hint}


def _note(name: str, message: str, hint: str | None = None) -> dict:
    """A check that failed without invalidating the setup — reported, not blocking."""
    return {"name": name, "status": "note", "message": message, "hint": hint}


def _check_database(config: dict) -> dict:
    db_path = Path(config["general"]["db_path"])
    if not db_path.exists():
        return _issue("Database", f"NOT FOUND — {db_path}",
                      "Run 'applyr init' to create it.")
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
        db_version = get_schema_version(conn)
    except Exception as e:  # pylint: disable=broad-except
        # A health check must report a broken database, never crash on it.
        return _issue("Database", f"ERROR — {e}")
    finally:
        conn.close()
    # A newer schema is forward-compat, not breakage: an older applyr just
    # ignores columns/tables it doesn't know about yet. `init_db` already
    # warns about this on every other command; doctor's own report must say
    # the same thing plainly, since a human reading "newer... Consider
    # upgrading" out of context can't tell that from an actual problem.
    if db_version is not None and db_version > SCHEMA_VERSION:
        return _note("Database",
                     f"OK ({db_path}, {count} offers) — schema v{db_version} is "
                     f"newer than applyr v{SCHEMA_VERSION} (forward-compat, not an error)",
                     f"Run 'pip install --upgrade applyr' to match the schema version.")
    return _ok("Database", f"OK ({db_path}, {count} offers)")


def _check_config() -> dict:
    config_path = APPLYR_DIR / "applyr.toml"
    if config_path.exists():
        return _ok("Config", f"OK ({config_path})")
    return _issue("Config", "NOT FOUND — using defaults")


def _check_cv_master() -> dict:
    cv_master = get_cv_master_path()
    if not cv_master.exists():
        return _issue("CV Master", f"NOT FOUND — {cv_master}",
                      "Run 'applyr init' to create a template.")
    report = inspect_cv_master(cv_master.read_text(encoding="utf-8"))
    if not report.filled:
        return _issue("CV Master",
                      f"WARNING — {report.reason}",
                      f"Edit {cv_master} with your professional profile.")
    return _ok("CV Master", f"OK ({cv_master}, {report.content_words} words of content)")


def _check_agent_instructions() -> dict:
    agent_path = APPLYR_DIR / "AGENT_INSTRUCTIONS.md"
    if not agent_path.exists():
        return _issue("Agent Instr.", "NOT FOUND — run 'applyr init'")
    # Stale instructions are reported but do not block: `setup-agent` already
    # falls back to the packaged copy, so work continues correctly meanwhile.
    text = agent_path.read_text()
    if is_stale(text):
        return _note("Agent Instr.",
                     "STALE — local copy is from "
                     f"{stamped_version(text) or 'an unstamped version'}, "
                     f"package is {__version__}",
                     "setup-agent uses the packaged version instead. Delete "
                     f"{agent_path} and run 'applyr init' to refresh it.")
    return _ok("Agent Instr.", f"OK ({agent_path})")


def _check_chrome(config: dict) -> dict:
    chrome = config["cv"]["chrome_path"]
    if chrome and os.path.isfile(chrome):
        return _ok("Chrome", f"OK ({chrome})")
    # Not blocking: without Chrome only `cv pdf` breaks. Scoring, tracking and
    # HTML generation all still work, so this must not fail the health check.
    return _note("Chrome", "NOT FOUND (PDF generation will not work)",
                 "Set CHROME_BIN env var or chrome_path in applyr.toml.")


def _check_weights(config: dict) -> dict:
    weights = config["weights"]
    if all(v > 0 for v in weights.values()):
        return _ok("Weights", f"OK ({len(weights)} topics, auto-normalized)")
    return _issue("Weights", "WARNING — some weights are zero or negative")


def cmd_doctor(as_json: bool = False) -> None:
    """Check applyr configuration, database, and environment health.

    Exits 1 when a blocking issue is found. `doctor` is a gate, not a report:
    a health check that always exits 0 cannot guard anything, so
    `applyr doctor && applyr cv generate 3` would happily build a CV from an
    empty profile. The report itself is data and stays on stdout in both modes
    — the exit code carries the verdict.
    """
    config = load_config()
    checks = [
        _check_database(config),
        _check_config(),
        _check_cv_master(),
        _check_agent_instructions(),
        _check_chrome(config),
        _check_weights(config),
    ]
    issues = [c for c in checks if c["status"] == "issue"]

    if as_json:
        print(json.dumps({
            "version": __version__,
            "healthy": not issues,
            "issues": len(issues),
            "checks": checks,
        }, indent=2))
    else:
        print(f"applyr v{__version__} — health check\n")
        for check in checks:
            # Messages are self-describing so the human report is unchanged;
            # `status` is what machines read in --json mode.
            print(f"  {check['name']:<13}: {check['message']}")
            if check["hint"]:
                print(f"                 {check['hint']}")
        print()
        # A `note` is not an issue and must not fail the run, but claiming
        # "all checks passed" right under a line reading STALE reads as a bug
        # in the report. Count the notes instead of hiding them.
        notes = [c for c in checks if c["status"] == "note"]
        if issues:
            print(f"  {len(issues)} issue(s) found.")
        elif notes:
            print(f"  All checks passed — {len(notes)} note(s) to review above.")
        else:
            print("  All checks passed.")

    if issues:
        sys.exit(1)


# ---------------------------------------------------------------------------
# cmd_cv_stats
# ---------------------------------------------------------------------------

def cmd_cv_stats(min_sample: int = 1, as_json: bool = False) -> None:
    """Compare CVs by response and interview rate."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, company, status, cv_used FROM offers"
        ).fetchall()
    finally:
        conn.close()

    report = build_report(rows, min_sample=min_sample)

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("CV Performance\n")

    if not report["cvs"]:
        print("  No offers have a CV recorded yet.")
        print()
        print("  'applyr cv generate <id>' records the CV automatically.")
        print("  For offers you already applied to, set it with:")
        print("    applyr update <id> <status> --cv <filename>")
        print()
        return

    header = f"  {'CV':<28} {'SENT':>5} {'RESP':>6} {'INTV':>6} {'OFFER':>6}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for cv in report["cvs"]:
        name = _truncate_cv(cv["cv"], CV_STATS_NAME_WIDTH)
        marker = " *" if cv["below_min_sample"] else ""
        print(f"  {name:<28} {cv['sent']:>5} "
              f"{cv['response_rate']:>5.0f}% {cv['interview_rate']:>5.0f}% "
              f"{cv['offers']:>6}{marker}")

    print()
    if any(cv["below_min_sample"] for cv in report["cvs"]):
        print(f"  * fewer than {min_sample} applications — treat the rate as noise")
    if report["untracked"]:
        print(f"  {report['untracked']} of {report['total_offers']} offers have no CV recorded "
              f"and are excluded.")
    print()
    print("  RESP  = got any reply, including rejections (did it pass the filter?)")
    print("  INTV  = reached in_process or offer (did it convince?)")
    print()


def _truncate_cv(name: str, width: int) -> str:
    """Shorten a CV filename for table display."""
    return name if len(name) <= width else name[:width - 1] + "…"
