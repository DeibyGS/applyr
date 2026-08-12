"""Analysis and reporting commands: pipeline, stats, gaps, followups, trends, summary, compare, plan, salary."""

import json
from collections import defaultdict
from datetime import date, timedelta

from applyr.colors import color
from applyr.config import TOPIC_LABELS, load_config
from applyr.constants import (
    COMPARE_COL_MAX,
    COMPARE_COL_MIN,
    COMPARE_LABEL_WIDTH,
    COMPARE_MAX_OFFERS,
    COMPARE_MIN_OFFERS,
    COMPARE_TERMINAL_WIDTH,
    FOLLOWUP_COMPANY_WIDTH,
    FOLLOWUP_TITLE_WIDTH,
    FOLLOWUP_UPCOMING_DAYS,
    GAP_PRIORITY_HIGH_SHARE,
    GAP_PRIORITY_MEDIUM_SHARE,
    PIPELINE_COMPANY_WIDTH,
    PIPELINE_TITLE_WIDTH,
    TREND_BAR_WIDTH,
    TREND_HISTORY_LIMIT,
)
from applyr.db import REPLY_STATUSES, STATUS_LABELS, VALID_SEVERITIES, get_conn
from applyr.commands._helpers import _bar, _today, _truncate
from applyr.errors import die

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_STATUS_ORDER = ["applied", "waiting", "in_process", "offer", "pending", "discarded", "rejected"]

_COMPARE_FIELDS = [
    ("Company", "company"),
    ("Title", "title"),
    ("Score", "compatibility_pct"),
    ("Status", "status"),
    ("Seniority", "seniority_level"),
    ("Work Mode", "work_mode"),
    ("Salary", None),  # computed
    ("Tech Stack", "tech_stack"),
]

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _median(values: list[int]) -> int:
    """Return the median of a sorted list of integers."""
    n = len(values)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2 == 0:
        return (values[mid - 1] + values[mid]) // 2
    return values[mid]


def _salary_stats(entries: list[dict]) -> tuple[int, int, int, int] | None:
    """Extract salary values from entries and return (min, max, avg, median).

    Returns None if no valid salary data found.
    """
    all_values = []
    for e in entries:
        if e["salary_min"]:
            all_values.append(e["salary_min"])
        if e["salary_max"]:
            all_values.append(e["salary_max"])

    if not all_values:
        return None

    all_values.sort()
    s_min = min(all_values)
    s_max = max(all_values)
    s_avg = round(sum(all_values) / len(all_values))
    s_med = _median(all_values)
    return s_min, s_max, s_avg, s_med

# ---------------------------------------------------------------------------
# cmd_pipeline
# ---------------------------------------------------------------------------

def cmd_pipeline(min_score: int = 0, as_json: bool = False) -> None:
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

    if as_json:
        payload = {}
        for status in _STATUS_ORDER:
            payload[status] = [{"id": i["id"], "compatibility_pct": i["compatibility_pct"],
                                "company": i["company"], "title": i["title"]} for i in groups[status]]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"\n{color('--- Pipeline ---', 'bold')}\n")
    for status in _STATUS_ORDER:
        items = groups[status]
        label = STATUS_LABELS.get(status, status)
        status_color = {"offer": "green", "in_process": "cyan", "applied": "blue",
                        "waiting": "yellow", "rejected": "red", "discarded": "dim"}.get(status, "white")
        print(f"  {color(f'{label:<20}', status_color)} ({len(items)})")
        for item in items:
            pct = item["compatibility_pct"]
            company = item["company"] or "—"
            print(f"    #{item['id']:>4}  {pct:>3}%  {_truncate(company, PIPELINE_COMPANY_WIDTH):<{PIPELINE_COMPANY_WIDTH}}  {_truncate(item['title'], PIPELINE_TITLE_WIDTH)}")
    print()


# ---------------------------------------------------------------------------
# cmd_stats
# ---------------------------------------------------------------------------

def cmd_stats(as_json: bool = False) -> None:
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

        # Conversion funnel. `responded` excludes `waiting`: that status means
        # the application is out and nothing has come back, which is why
        # `update` schedules a follow-up for it. Counting it as a reply made
        # this funnel disagree with `response-rate` on identical data — 14%
        # against 9% on a real 206-offer database.
        applied    = conn.execute("SELECT COUNT(*) FROM offers WHERE status != 'pending' AND status != 'discarded'").fetchone()[0]
        reply_slots = ", ".join("?" * len(REPLY_STATUSES))
        responded  = conn.execute(
            f"SELECT COUNT(*) FROM offers WHERE status IN ({reply_slots})",
            sorted(REPLY_STATUSES),
        ).fetchone()[0]
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

    if as_json:
        payload = {
            "total": total, "pending": pending, "discarded": discarded,
            "avg_compatibility_pct": round(avg_compat, 1),
            "funnel": {"applied": applied, "responded": responded, "interview": interview, "offer": offers_cnt},
            "channels": {ch["canal"]: ch["cnt"] for ch in channels},
            "work_modes": {m["work_mode"]: m["cnt"] for m in modes},
        }
        if sal and sal[0] is not None:
            payload["salary"] = {"min": sal[0], "max": sal[1], "avg": round(sal[2])}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

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

def _live_skill_gaps(limit: int | None = None) -> list[dict]:
    """Derive recurring skill gaps from the offers currently stored.

    The skill_gaps table is an append-only counter: cmd_add increments it and
    nothing ever decrements it, so deleting an offer leaves its gaps behind
    forever. Deriving from offer_topics keeps these numbers consistent with
    what `applyr list` actually shows.
    """
    threshold = load_config()["general"]["threshold"]

    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT t.topic                AS skill,
                   COUNT(*)               AS frequency,
                   SUM(:threshold - t.score) AS total_gap
            FROM offer_topics t
            -- SQLite runs with foreign_keys OFF, so orphaned topic rows are
            -- possible. The join drops them rather than counting them.
            JOIN offers o ON o.id = t.offer_id
            WHERE t.score < :threshold
            GROUP BY t.topic
            -- Worst total impact first, so the ranking and the priority
            -- label cannot disagree with each other.
            ORDER BY total_gap DESC, frequency DESC
            """,
            {"threshold": threshold},
        ).fetchall()
    finally:
        conn.close()

    gaps = [{"skill": r["skill"], "frequency": r["frequency"], "total_gap": r["total_gap"]}
            for r in rows]
    return gaps[:limit] if limit is not None else gaps


def _gap_priority(total_gap: int, worst_gap: int) -> str:
    """Rank a gap against the worst one, not against a fixed number of sightings.

    Counting recurrences stopped telling the user anything the moment the
    database grew: a threshold of three marks every topic HIGH once there are a
    couple of hundred offers, and it ignored how far short each one fell, so a
    topic missed by 30 points ranked level with one missed by 12.

    `total_gap` already carries both halves — it sums the points a topic cost
    across every offer that fell short — so comparing it to the largest gap
    keeps the ranking readable at six offers and at six hundred.
    """
    if worst_gap <= 0:
        return "LOW"
    share = total_gap / worst_gap
    if share >= GAP_PRIORITY_HIGH_SHARE:
        return "HIGH"
    if share >= GAP_PRIORITY_MEDIUM_SHARE:
        return "MEDIUM"
    return "LOW"


def cmd_gaps(limit: int = 10, as_json: bool = False) -> None:
    """Show recurring skill gaps, worst total impact first."""
    topic_labels: dict = TOPIC_LABELS

    rows = _live_skill_gaps(limit)

    if not rows:
        print("No skill gaps recorded yet.")
        return

    worst_gap = max(r["total_gap"] for r in rows)

    if as_json:
        payload = []
        for r in rows:
            freq = r["frequency"]
            payload.append({
                "skill": r["skill"],
                "label": topic_labels.get(r["skill"], r["skill"]),
                "frequency": freq,
                "avg_gap": round(r["total_gap"] / freq) if freq else 0,
                "total_gap": r["total_gap"],
                "priority": _gap_priority(r["total_gap"], worst_gap),
            })
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("\n--- Skill Gaps ---\n")
    for r in rows:
        label = topic_labels.get(r["skill"], r["skill"])
        freq  = r["frequency"]
        priority = _gap_priority(r["total_gap"], worst_gap)
        priority_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "dim"}.get(priority, "white")
        avg_gap = round(r["total_gap"] / freq) if freq else 0
        print(f"  [{color(f'{priority:<6}', priority_color)}]  {label:<20}  seen {freq}x  avg gap {avg_gap}%")
    print()


# ---------------------------------------------------------------------------
# cmd_followups
# ---------------------------------------------------------------------------

def cmd_followups(as_json: bool = False) -> None:
    """Show overdue and upcoming (next 5 days) follow-ups."""
    today = _today()
    upcoming_limit = (date.today() + timedelta(days=FOLLOWUP_UPCOMING_DAYS)).isoformat()

    # `follow_up_done` is checked but nothing in applyr ever sets it — no command
    # exposes it, so it stays 0 forever and never excluded anything. A follow-up
    # only means something while a reply is still owed, and that state already
    # exists: `status IN ('applied', 'waiting')`. Once a reply arrives (or the
    # offer is discarded), the row keeps whatever `follow_up_date` it was last
    # given, and without this filter an offer marked `rejected` weeks ago still
    # showed up demanding a chase.
    owed_clause = "status IN ('applied', 'waiting')"

    conn = get_conn()
    try:
        overdue = conn.execute(
            f"""
            SELECT id, title, company, contact_name, contact_role, follow_up_date, follow_up_done
            FROM offers
            WHERE follow_up_date < ? AND {owed_clause}
            ORDER BY follow_up_date
            """,
            (today,),
        ).fetchall()

        upcoming = conn.execute(
            f"""
            SELECT id, title, company, contact_name, contact_role, follow_up_date, follow_up_done
            FROM offers
            WHERE follow_up_date >= ? AND follow_up_date <= ? AND {owed_clause}
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
        print(f"    #{r['id']:>4}  {r['follow_up_date']}  {_truncate(r['company'] or '—', FOLLOWUP_COMPANY_WIDTH):<{FOLLOWUP_COMPANY_WIDTH}}  {_truncate(r['title'], FOLLOWUP_TITLE_WIDTH)}{contact}")

    if not overdue and not upcoming:
        # This early return ignored `as_json` and always printed the human
        # sentence, so an agent calling `followups --json` with nothing pending
        # got a plain string instead of a payload — a JSONDecodeError on the
        # one case its caller most needs to handle cleanly: nothing to do.
        if as_json:
            print(json.dumps({"overdue": [], "upcoming": []}, indent=2))
        else:
            print("No pending follow-ups.")
        return

    if as_json:
        payload = {
            "overdue": [{"id": r["id"], "title": r["title"], "company": r["company"],
                         "follow_up_date": r["follow_up_date"]} for r in overdue],
            "upcoming": [{"id": r["id"], "title": r["title"], "company": r["company"],
                          "follow_up_date": r["follow_up_date"]} for r in upcoming],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if overdue:
        print(f"\n  {color('OVERDUE', 'red')} ({len(overdue)}):")
        for r in overdue:
            _print_followup_row(r)

    if upcoming:
        print(f"\n  Upcoming — next {FOLLOWUP_UPCOMING_DAYS} days ({len(upcoming)}):")
        for r in upcoming:
            _print_followup_row(r)

    print()


# ---------------------------------------------------------------------------
# cmd_trends
# ---------------------------------------------------------------------------

def cmd_trends(period: str = "week", as_json: bool = False) -> None:
    """Group applications by week or month and show growth vs previous period."""
    if period not in ("week", "month"):
        die("Error: period must be 'week' or 'month'.")

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
            LIMIT {TREND_HISTORY_LIMIT}
            """,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No dated offers found.")
        return

    if as_json:
        payload = []
        for i, r in enumerate(rows):
            cnt = r["cnt"]
            prev_cnt = rows[i + 1]["cnt"] if i + 1 < len(rows) else None
            growth = None
            if prev_cnt is not None and prev_cnt > 0:
                growth = round((cnt - prev_cnt) / prev_cnt * 100)
            payload.append({"period": r["period"], "count": cnt, "growth_pct": growth})
        print(json.dumps(payload, indent=2, ensure_ascii=False))
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
        bar = _bar(cnt, width=TREND_BAR_WIDTH)
        print(f"  {r['period']}  {bar}  {cnt:>3}{growth_str}")
    print()


# ---------------------------------------------------------------------------
# cmd_summary
# ---------------------------------------------------------------------------

def cmd_summary(as_json: bool = False) -> None:
    """Print a weekly summary of activity, optionally as JSON for LLM consumption."""
    topic_labels: dict = TOPIC_LABELS

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
    finally:
        conn.close()

    # Top skill gap — derived from current offers, see _live_skill_gaps
    top_gaps = _live_skill_gaps(limit=1)
    top_gap = topic_labels.get(top_gaps[0]["skill"], top_gaps[0]["skill"]) if top_gaps else None

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
# cmd_compare
# ---------------------------------------------------------------------------

def cmd_compare(ids: list[int], as_json: bool = False) -> None:
    """Compare 2-10 offers side by side in a vertical table."""
    if len(ids) < COMPARE_MIN_OFFERS:
        die("Error: need at least 2 IDs to compare.", code="invalid_argument")
    if len(ids) > COMPARE_MAX_OFFERS:
        die("Error: maximum 10 offers to compare.", code="error")

    conn = get_conn()
    try:
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM offers WHERE id IN ({placeholders})", ids
        ).fetchall()
    finally:
        conn.close()

    found_ids = {r["id"] for r in rows}
    for oid in ids:
        if oid not in found_ids:
            die(f"Error: offer {oid} not found.", code="error")

    # Keep original order
    by_id = {r["id"]: r for r in rows}
    offers = [by_id[oid] for oid in ids]

    # Build vertical comparison table
    label_width = COMPARE_LABEL_WIDTH
    col_width = max(COMPARE_COL_MIN, min(COMPARE_COL_MAX, COMPARE_TERMINAL_WIDTH // len(offers)))

    if as_json:
        payload = []
        for o in offers:
            entry = {"id": o["id"]}
            for field_label, field_key in _COMPARE_FIELDS:
                if field_key is None:  # salary
                    s_min = o["salary_min"]
                    s_max = o["salary_max"]
                    period = o["salary_period"] or "annual"
                    if s_min and s_max:
                        val = f"{s_min}-{s_max}/{period[:3]}"
                    elif s_min:
                        val = f"{s_min}+/{period[:3]}"
                    elif s_max:
                        val = f"<={s_max}/{period[:3]}"
                    else:
                        val = None
                elif field_key == "status":
                    val = STATUS_LABELS.get(o[field_key], o[field_key])
                else:
                    val = o[field_key]
                entry[field_label.lower().replace(" ", "_")] = val
            payload.append(entry)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    # Header row
    header = f"{'Field':<{label_width}}"
    for o in offers:
        header += f"  {'#' + str(o['id']):<{col_width}}"
    print()
    print(header)
    print("-" * len(header))

    for field_label, field_key in _COMPARE_FIELDS:
        line = f"{field_label:<{label_width}}"
        for o in offers:
            if field_key is None:  # salary
                s_min = o["salary_min"]
                s_max = o["salary_max"]
                period = o["salary_period"] or "annual"
                if s_min and s_max:
                    val = f"{s_min}-{s_max}/{period[:3]}"
                elif s_min:
                    val = f"{s_min}+/{period[:3]}"
                elif s_max:
                    val = f"<={s_max}/{period[:3]}"
                else:
                    val = "—"
            elif field_key == "compatibility_pct":
                val = f"{o[field_key]}%"
            elif field_key == "status":
                val = STATUS_LABELS.get(o[field_key], o[field_key])
            else:
                val = str(o[field_key] or "—")
            line += f"  {_truncate(val, col_width):<{col_width}}"
        print(line)
    print()


# ---------------------------------------------------------------------------
# cmd_plan
# ---------------------------------------------------------------------------

def cmd_plan(limit: int = 10, as_json: bool = False) -> None:
    """Show a prioritized learning plan based on skill gaps."""
    topic_labels: dict = TOPIC_LABELS

    rows = _live_skill_gaps()

    if not rows:
        print("No skill gaps recorded yet.")
        return

    # `total_gap` is already frequency times average gap — the points a topic
    # cost across every offer that fell short. Ranking and priority both read
    # it, so the order and the label cannot disagree.
    scored = sorted(rows, key=lambda r: r["total_gap"], reverse=True)[:limit]
    worst_gap = max(r["total_gap"] for r in rows)

    def _row(rank: int, r: dict) -> tuple:
        freq = r["frequency"]
        return (
            rank,
            r["skill"],
            topic_labels.get(r["skill"], r["skill"]),
            freq,
            round(r["total_gap"] / freq) if freq else 0,
            _gap_priority(r["total_gap"], worst_gap),
        )

    if as_json:
        payload = [
            {"rank": rank, "skill": skill, "label": label,
             "frequency": freq, "avg_gap": avg_gap, "priority": priority}
            for rank, skill, label, freq, avg_gap, priority in
            (_row(i, r) for i, r in enumerate(scored, 1))
        ]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("\n--- Learning Plan ---\n")
    print(f"  {'#':<4}  {'Skill':<22}  {'Seen':>4}  {'Avg Gap':>7}  {'Priority':<8}")
    print(f"  {'—'*4}  {'—'*22}  {'—'*4}  {'—'*7}  {'—'*8}")

    for rank, _skill, label, freq, avg_gap, priority in (_row(i, r) for i, r in enumerate(scored, 1)):
        priority_color = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "dim"}.get(priority, "white")
        print(f"  {rank:<4}  {label:<22}  {freq:>4}x  {avg_gap:>6}%  {color(f'{priority:<8}', priority_color)}")

    print("\n  Focus on HIGH items first.")
    print("  Skill gaps update automatically when you add scored offers.\n")


# ---------------------------------------------------------------------------
# cmd_salary
# ---------------------------------------------------------------------------

def cmd_salary(seniority: str | None = None, category: str | None = None, as_json: bool = False) -> None:
    """Show salary statistics grouped by seniority and/or role category."""
    conn = get_conn()
    try:
        query = "SELECT seniority_level, role_category, salary_min, salary_max, salary_period FROM offers WHERE salary_min IS NOT NULL OR salary_max IS NOT NULL"
        params: list = []
        if seniority:
            query += " AND seniority_level = ?"
            params.append(seniority)
        if category:
            query += " AND role_category = ?"
            params.append(category)

        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No salary data available.")
        return

    # Group by seniority
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = r["seniority_level"] or "unspecified"
        groups[key].append(dict(r))

    if as_json:
        payload = {"by_seniority": [], "by_category": []}
        for level in sorted(groups.keys()):
            entries = groups[level]
            stats = _salary_stats(entries)
            if not stats:
                continue
            s_min, s_max, s_avg, s_med = stats
            periods = set(e["salary_period"] or "annual" for e in entries)
            payload["by_seniority"].append({
                "seniority": level, "count": len(entries),
                "min": s_min, "max": s_max, "avg": s_avg, "median": s_med,
                "period": "/".join(sorted(periods)),
            })
        cat_groups: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            key = r["role_category"] or "unspecified"
            cat_groups[key].append(dict(r))
        for cat in sorted(cat_groups.keys()):
            stats = _salary_stats(cat_groups[cat])
            if not stats:
                continue
            s_min, s_max, s_avg, s_med = stats
            payload["by_category"].append({
                "category": cat, "count": len(cat_groups[cat]),
                "min": s_min, "max": s_max, "avg": s_avg, "median": s_med,
            })
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("\n--- Salary Insights ---\n")
    print(f"  {'Seniority':<14}  {'Count':>5}  {'Min':>8}  {'Max':>8}  {'Avg':>8}  {'Median':>8}  {'Period':<6}")
    print(f"  {'—'*14}  {'—'*5}  {'—'*8}  {'—'*8}  {'—'*8}  {'—'*8}  {'—'*6}")

    for level in sorted(groups.keys()):
        entries = groups[level]
        stats = _salary_stats(entries)
        if not stats:
            continue

        periods = set(e["salary_period"] or "annual" for e in entries)
        s_min, s_max, s_avg, s_med = stats
        period = "/".join(sorted(periods))
        print(f"  {level:<14}  {len(entries):>5}  {s_min:>8,}  {s_max:>8,}  {s_avg:>8,}  {s_med:>8,}  {period:<6}")

    # Category breakdown if data has categories
    cat_groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        key = r["role_category"] or "unspecified"
        cat_groups[key].append(dict(r))

    if len(cat_groups) > 1:
        print(f"\n  {'Category':<14}  {'Count':>5}  {'Min':>8}  {'Max':>8}  {'Avg':>8}  {'Median':>8}")
        print(f"  {'—'*14}  {'—'*5}  {'—'*8}  {'—'*8}  {'—'*8}  {'—'*8}")

        for cat in sorted(cat_groups.keys()):
            stats = _salary_stats(cat_groups[cat])
            if not stats:
                continue
            s_min, s_max, s_avg, s_med = stats
            print(f"  {cat:<14}  {len(cat_groups[cat]):>5}  {s_min:>8,}  {s_max:>8,}  {s_avg:>8,}  {s_med:>8,}")

    print()


# ---------------------------------------------------------------------------
# cmd_gaps_save
# ---------------------------------------------------------------------------

def cmd_gaps_save(offer_id: int, gaps_json: str, as_json: bool = False) -> None:
    """Save learning gaps for a job offer."""
    try:
        data = json.loads(gaps_json)
    except json.JSONDecodeError as exc:
        die(f"Error: invalid JSON — {exc}", code="invalid_json")

    gaps = data.get("gaps", [])
    if not gaps:
        die("Error: gaps array is empty or missing.", code="missing_field")

    conn = get_conn()
    try:
        offer = conn.execute("SELECT id, title, company FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not offer:
            die(f"Error: offer #{offer_id} not found.", code="not_found")

        saved = 0
        for gap in gaps:
            topic = gap.get("topic", "")
            gap_detail = gap.get("gap_detail", "")
            severity = gap.get("severity", "medium")
            suggested_action = gap.get("suggested_action")

            if not topic:
                die("Error: each gap must have a 'topic' field.", code="missing_field")
            if not gap_detail:
                die("Error: each gap must have a 'gap_detail' field.", code="missing_field")
            if topic not in TOPIC_LABELS:
                die(f"Error: topic must be one of {list(TOPIC_LABELS.keys())}.", code="invalid_value")
            if severity not in VALID_SEVERITIES:
                die(f"Error: severity must be one of {VALID_SEVERITIES}.", code="invalid_value")

            conn.execute(
                "INSERT INTO learning_gaps (offer_id, topic, gap_detail, severity, suggested_action) "
                "VALUES (?, ?, ?, ?, ?)",
                (offer_id, topic, gap_detail, severity, suggested_action),
            )
            saved += 1

        conn.commit()
    finally:
        conn.close()

    company = offer["company"] or "—"
    title = offer["title"]
    if as_json:
        print(json.dumps({"offer_id": offer_id, "gaps_saved": saved}))
    else:
        print(f"Saved {saved} gap{'s' if saved != 1 else ''} for offer #{offer_id} ({title} @ {company})")


# ---------------------------------------------------------------------------
# cmd_gaps_list
# ---------------------------------------------------------------------------

def cmd_gaps_list(topic: str | None = None, severity: str | None = None, as_json: bool = False) -> None:
    """List learning gaps with optional filters."""
    topic_labels: dict = TOPIC_LABELS

    query = """
        SELECT lg.id, lg.offer_id, lg.topic, lg.gap_detail, lg.severity,
               lg.suggested_action, lg.created_at,
               o.title AS offer_title, o.company
        FROM learning_gaps lg
        JOIN offers o ON o.id = lg.offer_id
    """
    params: list = []
    conditions: list = []

    if topic:
        conditions.append("lg.topic = ?")
        params.append(topic)
    if severity:
        conditions.append("lg.severity = ?")
        params.append(severity)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY lg.created_at DESC"

    conn = get_conn()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    if not rows:
        if as_json:
            print(json.dumps({"total": 0, "gaps": []}))
        else:
            print("No learning gaps found.")
        return

    if as_json:
        payload = {
            "total": len(rows),
            "gaps": [
                {
                    "id": r["id"],
                    "offer_id": r["offer_id"],
                    "offer_title": r["offer_title"],
                    "company": r["company"],
                    "topic": r["topic"],
                    "gap_detail": r["gap_detail"],
                    "severity": r["severity"],
                    "suggested_action": r["suggested_action"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    severity_colors = {"high": "red", "medium": "yellow", "low": "dim"}

    print(f"\nLearning Gaps ({len(rows)} total)\n")
    print(f"  {'#':<4}  {'Offer':<30}  {'Topic':<14}  {'Severity':<8}  Gap Detail")
    print(f"  {'—'*4}  {'—'*30}  {'—'*14}  {'—'*8}  {'—'*30}")

    for r in rows:
        label = topic_labels.get(r["topic"], r["topic"])
        sev_color = severity_colors.get(r["severity"], "white")
        company = r["company"] or "—"
        offer_label = _truncate(f"{company} - {r['offer_title']}", 30)
        gap_text = _truncate(r["gap_detail"], 40)
        sev = r["severity"]
        print(f"  {r['id']:<4}  {offer_label:<30}  {label:<14}  {color(f'{sev:<8}', sev_color)}  {gap_text}")

    print()


# ---------------------------------------------------------------------------
# cmd_gaps_stats
# ---------------------------------------------------------------------------

def cmd_gaps_stats(as_json: bool = False) -> None:
    """Show summary statistics of learning gaps."""
    topic_labels: dict = TOPIC_LABELS

    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) FROM learning_gaps").fetchone()[0]
        if total == 0:
            if as_json:
                print(json.dumps({"total": 0, "by_topic": {}, "by_severity": {}, "top_gaps": []}))
            else:
                print("No learning gaps recorded yet.")
            return

        by_topic = conn.execute(
            "SELECT topic, COUNT(*) as cnt FROM learning_gaps GROUP BY topic ORDER BY cnt DESC"
        ).fetchall()

        by_severity = conn.execute(
            "SELECT severity, COUNT(*) as cnt FROM learning_gaps GROUP BY severity ORDER BY cnt DESC"
        ).fetchall()

        top_gaps = conn.execute(
            "SELECT gap_detail, COUNT(*) as cnt FROM learning_gaps GROUP BY gap_detail ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
    finally:
        conn.close()

    if as_json:
        payload = {
            "total": total,
            "by_topic": {r["topic"]: r["cnt"] for r in by_topic},
            "by_severity": {r["severity"]: r["cnt"] for r in by_severity},
            "top_gaps": [{"detail": r["gap_detail"], "count": r["cnt"]} for r in top_gaps],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print("\nLearning Gaps Summary\n")
    print(f"  Total gaps: {total}\n")

    # By topic with bar chart
    print("  By Topic:")
    max_freq = max(r["cnt"] for r in by_topic) if by_topic else 1
    for r in by_topic:
        label = topic_labels.get(r["topic"], r["topic"])
        bar_width = round(r["cnt"] / max_freq * 20) if max_freq else 0
        bar = "█" * bar_width
        print(f"    {label:<16} {r['cnt']:>3}  {bar}")

    # By severity with bar chart
    print("\n  By Severity:")
    max_sev = max(r["cnt"] for r in by_severity) if by_severity else 1
    severity_colors = {"high": "red", "medium": "yellow", "low": "dim"}
    for r in by_severity:
        bar_width = round(r["cnt"] / max_sev * 20) if max_sev else 0
        bar = "█" * bar_width
        sev_color = severity_colors.get(r["severity"], "white")
        sev = r["severity"]
        print(f"    {color(f'{sev:<10}', sev_color)} {r['cnt']:>3}  {bar}")

    # Top gaps
    if top_gaps:
        print("\n  Top Gaps (by frequency):")
        for i, r in enumerate(top_gaps, 1):
            print(f"    {i}. {r['gap_detail']}  ({r['cnt']} offer{'s' if r['cnt'] != 1 else ''})")

    print()
