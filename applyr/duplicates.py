"""Duplicate detection for incoming offers.

Three distinct situations, deliberately treated differently:

1. Same title, same company        → blocking duplicate
2. Similar title, same company     → blocking duplicate (likely a variant)
3. Different title, same company   → informational only, never blocks

Case 3 is normal and desirable: applying to several roles at one company is
not a mistake, but knowing you already have history there changes how you
write the application.
"""

import re
import sqlite3
from difflib import SequenceMatcher

from applyr.constants import DUPLICATE_SIMILARITY_THRESHOLD

# Qualifiers that describe the posting, not the role itself.
_PARENTHETICAL = re.compile(r"[\(\[\{].*?[\)\]\}]")
_PUNCTUATION = re.compile(r"[^\w\s]")

# Work-mode and gender-notation tokens that postings append to a title.
# "Backend Engineer, Remote" and "Backend Engineer" are the same role.
# Kept bilingual because postings in Spain mix English and Spanish titles.
_NOISE_TOKENS = frozenset({
    "remote", "remoto", "hybrid", "hibrido", "híbrido",
    "onsite", "presencial", "teletrabajo",
    "m", "f", "d", "w", "h", "x",  # m/f/d, h/m/x gender notations
})


def normalize_title(title: str) -> str:
    """Reduce a job title to its comparable core.

    Strips parenthetical qualifiers, punctuation and redundant whitespace, so
    that "Backend Engineer (Remote)" and "Backend Engineer" compare equal.

    Note that seniority is intentionally preserved: "Senior Backend Engineer"
    is a different role from "Backend Engineer", not a variant of it.
    """
    text = _PARENTHETICAL.sub(" ", title.lower())
    text = _PUNCTUATION.sub(" ", text)
    # split() already collapses runs of whitespace, so joining is enough
    return " ".join(t for t in text.split() if t not in _NOISE_TOKENS)


def title_similarity(a: str, b: str) -> float:
    """Similarity between two job titles, from 0.0 to 1.0.

    Both titles are normalized first, so the score reflects the role rather
    than how the posting was formatted.
    """
    norm_a, norm_b = normalize_title(a), normalize_title(b)
    if not norm_a or not norm_b:
        return 0.0
    return SequenceMatcher(None, norm_a, norm_b).ratio()


def find_exact(conn: sqlite3.Connection, title: str, company: str | None) -> sqlite3.Row | None:
    """Find an offer with the same title and company, case-insensitively."""
    return conn.execute(
        """SELECT id, title, status, date_received, compatibility_pct
           FROM offers
           WHERE LOWER(title) = LOWER(?)
             AND LOWER(COALESCE(company,'')) = LOWER(COALESCE(?,''))""",
        (title, company),
    ).fetchone()


def find_company_offers(conn: sqlite3.Connection, company: str | None) -> list[sqlite3.Row]:
    """All offers already recorded for a company, newest first."""
    if not company:
        return []
    return conn.execute(
        """SELECT id, title, status, date_received, compatibility_pct
           FROM offers
           WHERE LOWER(COALESCE(company,'')) = LOWER(?)
           ORDER BY id DESC""",
        (company,),
    ).fetchall()


def find_similar(
    rows: list[sqlite3.Row],
    title: str,
    threshold: float = DUPLICATE_SIMILARITY_THRESHOLD,
) -> tuple[sqlite3.Row, float] | None:
    """Find the closest title variant among a company's existing offers.

    Returns the best match and its score, or None if nothing reaches the
    threshold. Only the closest match is reported — listing every near-miss
    would bury the one that matters.
    """
    best_row: sqlite3.Row | None = None
    best_score = 0.0
    for row in rows:
        score = title_similarity(title, row["title"])
        if score >= threshold and score > best_score:
            best_row, best_score = row, score
    return (best_row, best_score) if best_row is not None else None
