"""CV A/B tracking — correlate which CV was used with what happened next.

Two rates, because they answer different questions:

- **Response rate**: did anyone reply at all? Approximates whether the CV got
  past the ATS and the first human screen. Rejections count as responses —
  being rejected means you were read.
- **Interview rate**: did it reach a real conversation? Approximates whether
  the CV convinced someone once read.

A CV can score high on the first and low on the second, which is a different
problem from silence. Collapsing them into one number hides that.
"""

from applyr.db import REPLY_STATUSES, SENT_STATUSES, VALID_STATUSES

# A reply of any kind was received — including a rejection. `waiting` used to be
# counted here, which read the label backwards: "Waiting Response" is the state
# of having heard nothing, and `update` schedules a follow-up for exactly that
# reason. Counting it made this rate disagree with `response-rate` on the same
# data, so the definition now lives in db.py and is shared.
RESPONDED_STATUSES = REPLY_STATUSES

# Reached a real conversation.
INTERVIEW_STATUSES = frozenset({"in_process", "offer"})

# `SENT_STATUSES` is imported from db.py rather than defined here: the `applied`
# column records the same idea, and a single definition is what keeps the column
# and these rates from drifting apart.


def _rate(part: int, whole: int) -> float:
    """Percentage of part in whole, 0.0 when whole is zero."""
    return round(100 * part / whole, 1) if whole else 0.0


def summarize_cv(rows: list) -> dict:
    """Aggregate one CV's offers into counts and rates.

    `rows` are offer records for a single cv_used value. Only offers that were
    actually sent count toward the rates — a pending offer says nothing about
    the CV, and including it would drag every rate down as you add offers you
    have not applied to yet.
    """
    statuses = [r["status"] for r in rows]
    sent = [s for s in statuses if s in SENT_STATUSES]
    responded = [s for s in sent if s in RESPONDED_STATUSES]
    interviews = [s for s in sent if s in INTERVIEW_STATUSES]
    offers = [s for s in sent if s == "offer"]

    return {
        "total": len(rows),
        "sent": len(sent),
        "responded": len(responded),
        "interviews": len(interviews),
        "offers": len(offers),
        "response_rate": _rate(len(responded), len(sent)),
        "interview_rate": _rate(len(interviews), len(sent)),
    }


def build_report(rows: list, min_sample: int = 1) -> dict:
    """Group offers by cv_used and summarize each.

    Offers with no cv_used are reported separately rather than dropped: a large
    untracked group is the most useful thing the report can tell you, because
    it means the numbers above it rest on a small slice of reality.
    """
    by_cv: dict[str, list] = {}
    untracked = 0
    for row in rows:
        cv = (row["cv_used"] or "").strip()
        if not cv:
            untracked += 1
            continue
        by_cv.setdefault(cv, []).append(row)

    cvs = []
    for name, cv_rows in by_cv.items():
        summary = summarize_cv(cv_rows)
        summary["cv"] = name
        summary["below_min_sample"] = summary["sent"] < min_sample
        cvs.append(summary)

    # Best interview rate first; ties broken by sample size, so a 100% from one
    # application never outranks a 100% from five.
    cvs.sort(key=lambda c: (c["interview_rate"], c["sent"]), reverse=True)

    return {
        "cvs": cvs,
        "untracked": untracked,
        "total_offers": len(rows),
        "tracked_offers": len(rows) - untracked,
    }


def status_breakdown(rows: list) -> dict[str, int]:
    """Count offers per status, in the canonical status order."""
    counts = {s: 0 for s in VALID_STATUSES}
    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] += 1
    return counts
