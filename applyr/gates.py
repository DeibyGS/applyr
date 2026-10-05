"""Artifact gates between CV pipeline steps — ADR-018.

Applyr cannot check that an agent *did* the thinking a step asks for (ADR-003:
no LLM calls), only that the artifact the previous step was supposed to leave
behind is readable here. This module owns that check for the CV Architect's
plan (AGENT_INSTRUCTIONS Step 5.7) so `cv generate`, `cv gate` and
`applyr next` cannot disagree about whether the pipeline is mid-step.

Filesystem reads only: no DB, no config, no network.
"""

import re
from enum import Enum
from pathlib import Path

from applyr.constants import PLAN_HEADING_ALIASES, PLAN_MIN_FORBIDDEN_CLAIMS


class PlanStatus(Enum):
    """Why a plan passed or failed — a boolean would hide which one it was."""

    MISSING = "missing"        # nowhere to be found
    WRONG_OFFER = "wrong_offer"  # declares a different offer_id
    EMPTY = "empty"            # no forbidden-claims section, or no claims in it
    UNREADABLE = "unreadable"  # exists but is not UTF-8 text
    VALID = "valid"

    @property
    def ok(self) -> bool:
        return self is PlanStatus.VALID

    @property
    def error_code(self) -> str:
        """The stable `die(code=...)` this state maps to (docs/contracts.md).

        Skipped step and malformed artifact branch differently in an agent:
        "you missed Step 5.7" needs a different command than "your plan is
        incomplete", so they are two codes, not one.
        """
        if self.ok:
            return ""
        return "plan_required" if self is PlanStatus.MISSING else "plan_invalid"


_FRONTMATTER_RE = re.compile(r"---\r?\n(.*?)\r?\n---", re.DOTALL)
_OFFER_ID_RE = re.compile(r"^\s*offer_id:\s*(\d+)", re.MULTILINE)
_HEADING_RE = re.compile(
    r"^(#{1,6})\s*(" + "|".join(re.escape(a) for a in PLAN_HEADING_ALIASES) + r")\s*#*\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(\S.*)$")
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.MULTILINE)


def plan_path_for(company: str | None) -> Path:
    """Where the Architect's plan for `company` must live: next to the CVs.

    Local import so importing this module never drags in applyr.cv (which
    reads back into this module when it runs the gate).
    """
    from applyr.cv import get_output_dir, make_slug

    return get_output_dir(create=False) / f"cv-{make_slug(company)}-plan.md"


def declared_offer_id(text: str) -> int | None:
    """The `offer_id` in a plan's YAML frontmatter, or None if it declares none."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    id_match = _OFFER_ID_RE.search(match.group(1))
    return int(id_match.group(1)) if id_match else None


def forbidden_claims(text: str) -> list[str]:
    """Bullets under the forbidden-claims heading, in any accepted spelling.

    Nothing else counts: a plan whose "forbidden claims" are buried in prose
    under a different heading is a plan applyr cannot check, which is the same
    thing as a plan with no forbidden claims.
    """
    claims: list[str] = []
    for heading in _HEADING_RE.finditer(text):
        rest = text[heading.end():]
        end = _ANY_HEADING_RE.search(rest)
        section = rest[:end.start()] if end else rest
        for line in section.splitlines():
            bullet = _BULLET_RE.match(line)
            if bullet:
                claims.append(bullet.group(1).strip())
    return claims


def validate_plan(path: Path, offer_id: int) -> PlanStatus:
    """Validate one plan file against the offer it claims to be for."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return PlanStatus.MISSING
    except (UnicodeDecodeError, IsADirectoryError, OSError):
        return PlanStatus.UNREADABLE

    declared = declared_offer_id(text)
    if declared is None or declared != offer_id:
        return PlanStatus.WRONG_OFFER
    if len(forbidden_claims(text)) < PLAN_MIN_FORBIDDEN_CLAIMS:
        return PlanStatus.EMPTY
    return PlanStatus.VALID


def check_plan(company: str | None, offer_id: int) -> tuple[PlanStatus, Path]:
    """Locate and validate the plan for an offer.

    Returns (status, path): the path is always one the message can point at —
    the canonical `cv-<slug>-plan.md` when nothing was found, or whatever file
    was actually judged. An agent that named the file after the raw company
    name (`cv-Fusuma (Spain)-plan.md`) instead of the slug still gets its
    `offer_id` checked: the filename is a convention, the offer id is the
    contract.
    """
    canonical = plan_path_for(company)
    candidates = []
    if canonical.exists():
        candidates.append(canonical)
    candidates += sorted(p for p in canonical.parent.glob("cv-*-plan.md") if p != canonical)

    fallback: tuple[PlanStatus, Path] | None = None
    for path in candidates:
        status = validate_plan(path, offer_id)
        if status.ok:
            return status, path
        if fallback is None:
            fallback = (status, path)
    return fallback if fallback else (PlanStatus.MISSING, canonical)


def plan_hint(status: PlanStatus) -> str:
    """What a human (or agent) has to do about a non-valid plan, in one line."""
    return {
        PlanStatus.MISSING: "No plan file was found — write it as the CV Architect (Step 5.7)",
        PlanStatus.WRONG_OFFER: "It declares a different offer_id",
        PlanStatus.EMPTY: "It lists no forbidden claims",
        PlanStatus.UNREADABLE: "It could not be read as UTF-8 text",
        PlanStatus.VALID: "",
    }[status]
