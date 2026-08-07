"""Export and doctor commands."""

import csv
import json
import os
from pathlib import Path

from applyr import __version__
from applyr.config import APPLYR_DIR, load_config
from applyr.constants import CV_MASTER_MIN_SIZE, CV_STATS_NAME_WIDTH
from applyr.cv_stats import build_report
from applyr.db import get_conn
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
    out_path = Path(filepath) if filepath else Path.cwd() / default_name

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

def cmd_doctor() -> None:
    """Check applyr configuration, database, and environment health."""
    from applyr.cv import get_cv_master_path

    config = load_config()
    issues = 0

    print(f"applyr v{__version__} — health check\n")

    # Database
    db_path = Path(config["general"]["db_path"])
    if db_path.exists():
        conn = get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
            print(f"  Database     : OK ({db_path}, {count} offers)")
        except Exception as e:
            print(f"  Database     : ERROR — {e}")
            issues += 1
        finally:
            conn.close()
    else:
        print(f"  Database     : NOT FOUND — {db_path}")
        print("                 Run 'applyr init' to create it.")
        issues += 1

    # Config
    config_path = APPLYR_DIR / "applyr.toml"
    if config_path.exists():
        print(f"  Config       : OK ({config_path})")
    else:
        print(f"  Config       : NOT FOUND — using defaults")
        issues += 1

    # CV master
    cv_master = get_cv_master_path()
    if cv_master.exists():
        size = cv_master.stat().st_size
        if size < CV_MASTER_MIN_SIZE:
            print(f"  CV Master    : WARNING — file exists but looks empty ({size} bytes)")
            print(f"                 Edit {cv_master} with your professional profile.")
            issues += 1
        else:
            print(f"  CV Master    : OK ({cv_master}, {size:,} bytes)")
    else:
        print(f"  CV Master    : NOT FOUND — {cv_master}")
        print("                 Run 'applyr init' to create a template.")
        issues += 1

    # Agent instructions
    agent_path = APPLYR_DIR / "AGENT_INSTRUCTIONS.md"
    if agent_path.exists():
        print(f"  Agent Instr. : OK ({agent_path})")
    else:
        print(f"  Agent Instr. : NOT FOUND — run 'applyr init'")
        issues += 1

    # Chrome
    chrome = config["cv"]["chrome_path"]
    if chrome and os.path.isfile(chrome):
        print(f"  Chrome       : OK ({chrome})")
    else:
        print(f"  Chrome       : NOT FOUND (PDF generation will not work)")
        print("                 Set CHROME_BIN env var or chrome_path in applyr.toml")

    # Scoring weights (auto-normalized, just check they exist and are positive)
    weights = config["weights"]
    if all(v > 0 for v in weights.values()):
        print(f"  Weights      : OK ({len(weights)} topics, auto-normalized)")
    else:
        print(f"  Weights      : WARNING — some weights are zero or negative")
        issues += 1

    # Summary
    print()
    if issues == 0:
        print("  All checks passed.")
    else:
        print(f"  {issues} issue(s) found.")


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
