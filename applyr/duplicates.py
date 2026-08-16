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
import unicodedata
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


def normalize_company(text: str | None) -> str:
    """Lowercase and strip diacritics, so "Mática" and "Matica" compare equal.

    Company names get typed inconsistently far more often than two
    genuinely different companies happen to share a name — a posting
    pasted from LinkedIn, OCR, or a rushed manual entry drops accents far
    more often than it invents a real collision. Unlike substring or fuzzy
    matching (rejected for company names — see module docstring), stripping
    diacritics never merges two different companies together, so it carries
    none of that false-positive risk.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _register_company_normalizer(conn: sqlite3.Connection) -> None:
    """Expose normalize_company() to SQL as unaccent_lower(). Idempotent —
    re-registering the same function on a connection is safe and cheap."""
    conn.create_function("unaccent_lower", 1, normalize_company)


def find_exact(conn: sqlite3.Connection, title: str, company: str | None) -> sqlite3.Row | None:
    """Find an offer with the same title and company, case/accent-insensitively.

    Ordered newest-first (matches find_company_offers) so that when --force
    created more than one exact duplicate, the block message surfaces the most
    recent one instead of an arbitrary row from an unordered table scan.
    """
    _register_company_normalizer(conn)
    return conn.execute(
        """SELECT id, title, status, date_received, compatibility_pct
           FROM offers
           WHERE LOWER(title) = LOWER(?)
             AND unaccent_lower(COALESCE(company,'')) = unaccent_lower(COALESCE(?,''))
           ORDER BY id DESC""",
        (title, company),
    ).fetchone()


def find_company_offers(conn: sqlite3.Connection, company: str | None) -> list[sqlite3.Row]:
    """All offers already recorded for a company, newest first."""
    if not company:
        return []
    _register_company_normalizer(conn)
    return conn.execute(
        """SELECT id, title, status, date_received, compatibility_pct
           FROM offers
           WHERE unaccent_lower(COALESCE(company,'')) = unaccent_lower(?)
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
