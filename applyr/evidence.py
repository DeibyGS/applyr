"""Evidence Graph — deterministic claim extraction from cv-master.md.

No LLM calls (ADR-003): every function here is pure text parsing. The Evidence
Graph is derived at runtime on every call, never cached or persisted — see
docs/adr/011-evidence-based-cv-engine.md for why a persisted cache was
rejected (a stale cache could make a future truth-checking command approve or
reject a CV against claims that no longer match the live cv-master.md).

cv-master.md's file format does not change for this feature. This module
parses the `## SECTION` / `**Bold Title**` / bullet structure
`cv-master-template.md` already documents — it does not require or enforce
that structure; unrecognized lines degrade to fewer extracted claims rather
than raising, since the file is free text a human edits, not a validated
schema.
"""

import re
from dataclasses import dataclass

from applyr.constants import PROTECTED_FACT_ALIASES

# cv-master-template.md's `## SECTION` names, mapped to a canonical claim
# section. CONTACT / PROFESSIONAL SUMMARY / ADDITIONAL are intentionally
# absent — they carry no verifiable skill/employment/metric claims to extract.
_SECTION_MAP = {
    "work experience": "experience",
    "projects": "project",
    "education": "education",
    "certifications": "certification",
    "technical skills": "skill",
    "languages": "language",
}

# Ephemeral claim-id prefix per section — stable only within one parse_evidence
# call (see EvidenceClaim.id docstring below).
_PREFIXES = {
    "experience": "EXP",
    "project": "PROJ",
    "education": "EDU",
    "certification": "CERT",
    "skill": "SKILL",
    "language": "LANG",
}

# WORK EXPERIENCE / PROJECTS / EDUCATION / CERTIFICATIONS: entries start with
# a **Bold Title** line, followed by bullets belonging to that entry.
_ENTRY_SECTIONS = {"experience", "project", "education", "certification"}
# TECHNICAL SKILLS / LANGUAGES: flat comma- or line-separated tokens, no
# entry/bullet structure — dispatch falls through to _parse_flat_section via
# negative check (line 98) rather than explicit _FLAT_SECTIONS membership test.

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_BOLD_TITLE_RE = re.compile(r"^\*\*(.+?)\*\*")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")

# Reverse index (any spelling, lowercased) -> canonical key in
# PROTECTED_FACT_ALIASES, built once at import time.
_ALIAS_INDEX: dict[str, str] = {}
for _canonical, _forms in PROTECTED_FACT_ALIASES.items():
    _ALIAS_INDEX[_canonical.lower()] = _canonical
    for _form in _forms:
        _ALIAS_INDEX[_form.lower()] = _canonical


@dataclass(frozen=True)
class EvidenceClaim:
    """One fact extracted from cv-master.md.

    `id` is ephemeral — stable only within the `parse_evidence` call that
    produced it (e.g. "EXP-001-C02"), never a foreign key. cv-master.md has
    no authored claim IDs; a claim's persistent identity, when one is needed
    (the PR4 audit snapshot), is its verbatim `text`, not this id.
    """

    id: str
    section: str
    text: str
    entry_context: str | None


def parse_evidence(profile_text: str) -> list[EvidenceClaim]:
    """Extract evidence claims from cv-master.md's raw Markdown text.

    Pure and deterministic: same input always produces the same claims, no
    I/O, no LLM calls. Missing sections are skipped silently; lines that
    match no known pattern (stray prose, a leftover "..." template guidance
    line) are ignored rather than raising.
    """
    claims: list[EvidenceClaim] = []
    headings = list(_HEADING_RE.finditer(profile_text))
    for i, match in enumerate(headings):
        section = _SECTION_MAP.get(match.group(1).strip().lower())
        if section is None:
            continue
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(profile_text)
        body = profile_text[start:end]
        if section in _ENTRY_SECTIONS:
            claims.extend(_parse_entry_section(body, section))
        else:
            claims.extend(_parse_flat_section(body, section))
    return claims


def _parse_entry_section(body: str, section: str) -> list[EvidenceClaim]:
    prefix = _PREFIXES[section]
    claims: list[EvidenceClaim] = []
    entry_context: str | None = None
    entry_num = 0
    claim_num = 0
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line == "...":
            continue
        bold_match = _BOLD_TITLE_RE.match(line)
        if bold_match:
            entry_num += 1
            claim_num = 0
            entry_context = bold_match.group(1).strip()
            continue
        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            claim_num += 1
            claims.append(EvidenceClaim(
                id=f"{prefix}-{entry_num:03d}-C{claim_num:02d}",
                section=section,
                text=bullet_match.group(1).strip(),
                entry_context=entry_context,
            ))
        # Anything else (stray prose) is silently ignored — see module docstring.
    return claims


def _parse_flat_section(body: str, section: str) -> list[EvidenceClaim]:
    prefix = _PREFIXES[section]
    claims: list[EvidenceClaim] = []
    index = 0
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line == "...":
            continue
        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            line = bullet_match.group(1).strip()
        # TECHNICAL SKILLS lines are documented as "Category: item, item" in
        # cv-master-template.md (e.g. "Backend: Python, FastAPI") — strip the
        # category label so claims are the skills themselves. LANGUAGES has no
        # such grouping convention (a colon there is more likely "English:
        # C1", where the text before the colon *is* the fact) — left alone.
        if section == "skill" and ":" in line:
            _, _, rest = line.partition(":")
            if rest.strip():
                line = rest
        for token in line.split(","):
            token = token.strip()
            if not token:
                continue
            index += 1
            claims.append(EvidenceClaim(
                id=f"{prefix}-{index:03d}",
                section=section,
                text=token,
                entry_context=None,
            ))
    return claims


def _all_forms(term: str) -> list[str]:
    """Every spelling PROTECTED_FACT_ALIASES treats as the same fact as `term`."""
    canonical = _ALIAS_INDEX.get(term.lower(), term)
    return [canonical, *PROTECTED_FACT_ALIASES.get(canonical, [])]


def is_evidenced(term: str, claims: list[EvidenceClaim]) -> bool:
    """Whether `term` (or an alias of it) appears in any claim's text/entry.

    Alphanumeric-boundary substring + PROTECTED_FACT_ALIASES expansion only —
    deliberately not fuzzy or semantic matching (ADR-011): a fuzzy matcher
    risks the verifier itself hallucinating support for a term that isn't
    really there.

    Not a plain `in` check, and not `\\b`-based either: a short alias like
    "TS" would substring-match inside "costs", and `\\b` itself fails to
    require a boundary after a term ending in a non-word character (e.g.
    "42%" or "C++" followed by a space) since two non-word characters don't
    form a `\\b` transition. The lookaround below only requires the character
    immediately before/after the match to be non-alphanumeric, which
    correctly bounds both plain words and symbol-suffixed terms.
    """
    for form in _all_forms(term):
        pattern = re.compile(rf'(?<![A-Za-z0-9]){re.escape(form)}(?![A-Za-z0-9])', re.IGNORECASE)
        for claim in claims:
            haystack = f"{claim.text} {claim.entry_context or ''}"
            if pattern.search(haystack):
                return True
    return False
