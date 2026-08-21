"""Analytics — CV comparison, response tracking, application performance."""

from __future__ import annotations

import re
from pathlib import Path
from collections import Counter

from applyr.db import get_conn
from applyr.ats import validate_ats_format
from applyr.errors import read_text_or_die

TECH_KEYWORDS = [
    "python", "javascript", "typescript", "react", "vue", "angular", "node",
    "django", "flask", "fastapi", "sql", "postgresql", "mysql", "mongodb",
    "docker", "kubernetes", "aws", "gcp", "azure", "git", "rest", "graphql",
    "html", "css", "sass", "tailwind", "redis", "rabbitmq", "kafka",
    "java", "go", "rust", "ruby", "php", "swift", "kotlin",
    "machine learning", "ai", "data science", "pandas", "numpy",
    "agile", "scrum", "ci/cd", "terraform", "ansible",
]


def _extract_text_keywords(text: str) -> list[str]:
    """Extract tech keywords from raw text."""
    text_lower = text.lower()
    found = [kw for kw in TECH_KEYWORDS if kw in text_lower]
    return sorted(set(found))


def compare_cvs(v1_path: str, v2_path: str) -> dict:
    """Compare two CV versions and return ATS compatibility score delta, keyword coverage delta, and recommendations."""
    v1_html = read_text_or_die(Path(v1_path))
    v2_html = read_text_or_die(Path(v2_path))

    v1_ats = validate_ats_format(v1_html)
    v2_ats = validate_ats_format(v2_html)

    v1_score = v1_ats.score
    v2_score = v2_ats.score
    score_delta = v2_score - v1_score

    v1_text = re.sub(r"<[^>]+>", " ", v1_html).lower()
    v2_text = re.sub(r"<[^>]+>", " ", v2_html).lower()
    v1_kw = _extract_text_keywords(v1_text)
    v2_kw = _extract_text_keywords(v2_text)

    v1_kw_set = set(v1_kw)
    v2_kw_set = set(v2_kw)
    gained = v2_kw_set - v1_kw_set
    lost = v1_kw_set - v2_kw_set

    v1_word_count = len(re.findall(r"\w+", v1_text))
    v2_word_count = len(re.findall(r"\w+", v2_text))

    recommendations = []
    if score_delta < 0:
        recommendations.append(f"v2 has {abs(score_delta)}% lower ATS compatibility score — review formatting changes")
    if lost:
        recommendations.append(f"v2 lost keywords: {', '.join(sorted(lost)[:5])}")
    if not recommendations:
        if score_delta > 0:
            recommendations.append(f"v2 is {score_delta}% better — ready to use")
        else:
            recommendations.append("Both versions are equivalent")

    return {
        "v1": {"path": str(v1_path), "ats_score": v1_score, "word_count": v1_word_count, "keywords": len(v1_kw)},
        "v2": {"path": str(v2_path), "ats_score": v2_score, "word_count": v2_word_count, "keywords": len(v2_kw)},
        "score_delta": score_delta,
        "keywords_gained": sorted(gained),
        "keywords_lost": sorted(lost),
        "recommendations": recommendations,
    }


def response_rate(min_sample: int = 1, as_json: bool = False) -> dict | None:
    """Calculate response rate and trends from applications."""
    conn = get_conn()
    try:
        rows = conn.execute("""
            -- No `date_applied IS NOT NULL` filter: an application with no
            -- recorded send date is still an application, and the monthly
            -- grouping below already buckets it as "unknown". Excluding it
            -- here made that fallback unreachable and silently shrank the
            -- denominator of the rate.
            SELECT date_applied, status, response_status
            FROM offers
            WHERE applied = 1
            ORDER BY date_applied
        """).fetchall()

        if not rows:
            if as_json:
                # Same keys as the populated payload. This branch printed
                # nothing before, so the mismatch was invisible; an agent
                # reading `total_applications` would now hit a KeyError on
                # exactly the case it most needs to handle — an empty start.
                return {
                    "total_applications": 0,
                    "responded": 0,
                    "response_rate": 0.0,
                    "by_status": {},
                    "monthly_trend": {},
                    "message": "No applications found",
                }
            # Say so out loud. Returning None printed nothing at all, which
            # reads as a broken command rather than an empty result.
            print("\n  No applications sent yet — nothing to measure.")
            print("  Mark one with: applyr update <id> applied")
            return None

        total = len(rows)
        responded = sum(1 for r in rows if r["response_status"] and r["response_status"] != "no_response")
        rate = round((responded / total) * 100, 1) if total > 0 else 0

        by_status = Counter()
        for r in rows:
            by_status[r["status"]] += 1

        monthly: dict[str, dict] = {}
        for r in rows:
            month = r["date_applied"][:7] if r["date_applied"] else "unknown"
            if month not in monthly:
                monthly[month] = {"total": 0, "responded": 0}
            monthly[month]["total"] += 1
            if r["response_status"] and r["response_status"] != "no_response":
                monthly[month]["responded"] += 1

        monthly_trend = {}
        for m, d in monthly.items():
            monthly_trend[m] = {
                "total": d["total"],
                "responded": d["responded"],
                "rate": round((d["responded"] / d["total"]) * 100, 1) if d["total"] > 0 else 0,
            }

        result = {
            "total_applications": total,
            "responded": responded,
            "response_rate": rate,
            "by_status": dict(by_status),
            "monthly_trend": monthly_trend,
        }

        if not as_json:
            print(f"\n📊 Response Rate: {rate}% ({responded}/{total} applications)")
            print(f"\nBy status:")
            for s, c in by_status.most_common():
                print(f"  {s}: {c}")
            if monthly_trend:
                print(f"\nMonthly trend:")
                for m in sorted(monthly_trend.keys()):
                    d = monthly_trend[m]
                    print(f"  {m}: {d['rate']}% ({d['responded']}/{d['total']})")
            return None

        return result
    finally:
        conn.close()
