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
# Spanish aliases included: cv-master.md's own language is unconstrained (only
# the *generated CV*'s language is config-driven, per VALID_LANGUAGES = (en,
# es)) — a Spanish-authored profile is the common case, not an edge case.
_SECTION_MAP = {
    "work experience": "experience",
    "experiencia profesional": "experience",
    "projects": "project",
    "proyectos": "project",
    "education": "education",
    "formación": "education",
    "formacion": "education",
    "certifications": "certification",
    "certificaciones": "certification",
    "technical skills": "skill",
    "habilidades tecnicas": "skill",
    "habilidades técnicas": "skill",
    "languages": "language",
    "idiomas": "language",
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
# "### Job Title" on its own line, with the employer/entry details on a
# following (possibly bold) line — real-world cv-master.md files commonly
# split title and employer this way rather than combining them in one
# "**Title — Employer**" bold line.
_H3_RE = re.compile(r"^###\s+(.+)$")
# "Label: content" or "**Label:** content" (e.g. "Stack: Python, FastAPI" or
# "**Stack:** Python, FastAPI") — a labeled fact list attached to the current
# entry, not a new entry itself. The colon must sit right after the label
# text (optionally still inside the bold markers) to avoid matching a real
# entry-title bold line like "**Acme Corp** — Remote — 01/2022".
_LABELED_LINE_RE = re.compile(r"^(?:\*\*)?([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9 /]*?):(?:\*\*)?\s*(.+)$")
# Real profiles separate tech/skill tokens with commas, middle dots, or
# markdown table pipes depending on section — accept all three.
_TOKEN_SPLIT_RE = re.compile(r"[,·|]")

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
    # A "### Job Title" line seen but not yet attached to an entry — merged
    # into entry_context the moment a following bold employer line (or any
    # other content) confirms the entry, so "### Title" + "**Employer**"
    # becomes one "Title — Employer" context, matching how the single-line
    # "**Title — Employer**" form already reads.
    pending_heading: str | None = None

    def flush_empty_entry() -> None:
        # An entry that produced zero claims (e.g. an EDUCATION entry that's
        # just "**Degree**" + a plain institution/dates line, no bullets, no
        # labeled fact list) would otherwise vanish from the Evidence Graph
        # entirely — its entry_context never attaches to any claim, so
        # nothing (e.g. cv.py's employer/title check) can ever match against
        # it. Give it one claim, its own title, so "this entry exists" is
        # still checkable.
        if entry_context is not None and claim_num == 0:
            claims.append(EvidenceClaim(
                id=f"{prefix}-{entry_num:03d}-C01",
                section=section,
                text=entry_context,
                entry_context=entry_context,
            ))

    def start_entry(label: str, merge_pending: bool = True) -> None:
        nonlocal entry_context, entry_num, claim_num, pending_heading
        flush_empty_entry()
        entry_num += 1
        claim_num = 0
        if merge_pending and pending_heading:
            entry_context = f"{pending_heading} — {label}"
        else:
            entry_context = label
        pending_heading = None

    def ensure_started() -> None:
        # A "### Title" with no bold employer line after it (e.g. PROJECTS
        # entries, which are often "### Name" alone) still starts an entry —
        # on whatever the next real content line turns out to be.
        if pending_heading is not None:
            start_entry(pending_heading, merge_pending=False)

    def add_claim(text: str) -> None:
        nonlocal claim_num
        claim_num += 1
        claims.append(EvidenceClaim(
            id=f"{prefix}-{entry_num:03d}-C{claim_num:02d}",
            section=section,
            text=text,
            entry_context=entry_context,
        ))

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line == "...":
            continue

        h3_match = _H3_RE.match(line)
        if h3_match:
            ensure_started()  # flush a previous lone heading first, if any
            pending_heading = h3_match.group(1).strip()
            continue

        # Checked before the generic bold-title match: "**Stack:** Python,
        # FastAPI" and plain "Stack: Python, FastAPI" are both a labeled
        # fact list for the CURRENT entry, not a new entry.
        labeled_match = _LABELED_LINE_RE.match(line)
        if labeled_match:
            ensure_started()
            for token in _TOKEN_SPLIT_RE.split(labeled_match.group(2)):
                token = token.strip()
                if token:
                    add_claim(token)
            continue

        bold_match = _BOLD_TITLE_RE.match(line)
        if bold_match:
            start_entry(bold_match.group(1).strip())
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            ensure_started()
            add_claim(bullet_match.group(1).strip())
            continue

        # Stray prose: not a claim itself, but still confirms a pending
        # "### Title"-only entry so later lines in this block (e.g. a plain
        # "Stack:" line further down) attach to it.
        ensure_started()

    ensure_started()  # a trailing lone "### Title" with nothing after it
    flush_empty_entry()  # the section's last entry, if it produced nothing
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
        # "**Backend**" category headers (real profiles group skills under a
        # bold sub-heading, then list items on the next line) — strip the
        # markers so the header itself doesn't read as a claim wrapped in
        # literal asterisks. Harmless either way for is_evidenced, but this
        # keeps claim text clean for anything that displays it later.
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        # TECHNICAL SKILLS lines are documented as "Category: item, item" in
        # cv-master-template.md (e.g. "Backend: Python, FastAPI") — strip the
        # category label so claims are the skills themselves. LANGUAGES has no
        # such grouping convention (a colon there is more likely "English:
        # C1", where the text before the colon *is* the fact) — left alone.
        if section == "skill" and ":" in line:
            _, _, rest = line.partition(":")
            if rest.strip():
                line = rest
        for token in _TOKEN_SPLIT_RE.split(line):
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


# Connector words ignored when decomposing a multi-word term for
# is_evidenced()'s compound-term fallback — grammatical filler, not a
# distinguishing word an offer's phrasing and the master's own wording would
# need to share verbatim. Bilingual (see evidence.py's Spanish _SECTION_MAP
# aliases: cv-master.md's language is unconstrained).
_COMPOUND_TERM_STOPWORDS = frozenset({
    "de", "del", "la", "el", "los", "las", "y", "o", "con", "en", "a",
    "the", "and", "of", "or", "with", "in", "for", "an",
})


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
    form a `\\b` transition — confirmed live via /code-review. The lookaround
    below only requires the character immediately before/after the match to
    be non-alphanumeric, which correctly bounds both plain words and
    symbol-suffixed terms.

    Multi-word terms also get a compound-term fallback: an offer's phrasing
    ("agentes de IA") doesn't have to appear verbatim in cv-master.md if the
    candidate's own wording states the same fact differently in ONE claim
    ("Desarrollo de agentes basados en modelos de IA"). Two guards keep this
    from turning into a semantic/fuzzy match: (1) every significant word
    (short connector words like "de"/"the" don't count) must independently
    pass the exact same boundary check above, and (2) — confirmed as a real
    gap via /code-review, not hypothetical — ALL of those words must co-occur
    in the SAME claim's text, not just be independently true somewhere across
    the whole graph. Without (2), "Machine" evidenced by one unrelated claim
    and "Learning" by a different unrelated claim would wrongly credit
    "Machine Learning" as evidenced. The significant-word length cutoff is
    >= 2, not >= 3 (also found via /code-review): a >= 3 cutoff drops short
    but real distinguishing words like "IA"/"AI"/"ML", which — combined with
    guard (2) not existing yet at the time — let a compound term get credited
    off a single leftover generic word with no AI-context confirmation at
    all. A translation gap ("GenAI" vs "IA Generativa") or a different
    specific product (a fabricated "GitHub Copilot" when the profile only
    shows "Claude Code") still correctly fails: those aren't the same words
    in a different order, they're different words entirely.
    """
    for form in _all_forms(term):
        pattern = re.compile(rf'(?<![A-Za-z0-9]){re.escape(form)}(?![A-Za-z0-9])', re.IGNORECASE)
        for claim in claims:
            haystack = f"{claim.text} {claim.entry_context or ''}"
            if pattern.search(haystack):
                return True

    raw_words = term.split()
    if len(raw_words) >= 2:
        significant_words = [
            w for w in raw_words
            if len(w) >= 2 and w.lower() not in _COMPOUND_TERM_STOPWORDS
        ]
        if significant_words:
            word_patterns = [
                re.compile(rf'(?<![A-Za-z0-9]){re.escape(w)}(?![A-Za-z0-9])', re.IGNORECASE)
                for w in significant_words
            ]
            # Each claim's own text, and each distinct entry_context, are
            # independent coherent units here — NOT concatenated together.
            # entry_context (a job title/company name) is shared across
            # every bullet under that entry; concatenating it onto each
            # bullet's haystack let a compound term borrow one word from the
            # title and an unrelated word from any sibling bullet under the
            # same entry — confirmed via /code-review: a company literally
            # named "Kubernetes Solutions Inc" paired with an unrelated
            # "Python" bullet under the same job wrongly credited a
            # fabricated "Kubernetes Python" claim, since neither word was
            # ever true of the SAME real fact.
            units = {claim.text for claim in claims}
            units.update(claim.entry_context for claim in claims if claim.entry_context)
            for unit in units:
                if all(p.search(unit) for p in word_patterns):
                    return True

    return False
