"""Eligibility / knockout check (docs/adr/017-eligibility-knockout-check.md).

The agent extracts an offer's *mandatory* requirements into `add`'s
`eligibility` block; this module judges them against cv-master.md. Pure: no
DB, no config, no clock — the same requirements and profile text always give
the same result, which is what makes the gate testable and trustworthy.
"""

import json
import math
import re
from dataclasses import dataclass, field

from applyr.constants import (
    CEFR_LEVELS,
    ELIGIBILITY_BLOCK,
    ELIGIBILITY_KEYS,
    ELIGIBILITY_PASS,
    ELIGIBILITY_PROFILE_KEYS,
    ELIGIBILITY_SECTION_NAMES,
    ELIGIBILITY_UNKNOWN,
    ELIGIBILITY_WARN,
    ELIGIBILITY_YEARS_TOLERANCE,
    LANGUAGE_ALIASES,
    LANGUAGE_SECTION_NAMES,
    NATIVE_LEVEL_WORDS,
    NO_WORDS,
    YES_WORDS,
)
from applyr.cv_master import strip_template_guidance
from applyr.evidence import fold_accents

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_CEFR_RE = re.compile(r"\b([abc][12])\b", re.IGNORECASE)
_EMPHASIS_RE = re.compile(r"\*+|__|`")
_RANGE_RE = re.compile(r"\d\s*[-–]\s*\d")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
# A languages line is "name <sep> level": a table cell border, a colon, or a dash.
_LANGUAGE_SEP_RE = re.compile(r"\s*(?:\||:|—|–|\s-\s)\s*")
_ONSITE_MODES = ("onsite", "hybrid")
_NATIVE_WORDS = frozenset(fold_accents(w) for w in NATIVE_LEVEL_WORDS)
_OFFER_LEVELS = {level.lower(): i for i, level in enumerate(CEFR_LEVELS)} | {
    w: CEFR_LEVELS.index("NATIVE") for w in _NATIVE_WORDS}


class EligibilityError(ValueError):
    """An invalid `eligibility` block; `field` names the offending key."""

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(message)
        self.field = field_name


@dataclass(frozen=True)
class EligibilityProfile:
    """What cv-master.md says about the candidate. `None` means "not stated"."""

    has_section: bool = False
    years: float | None = None
    cities: tuple[str, ...] | None = None
    relocation: bool | None = None
    driving_license: bool | None = None
    languages: dict[str, int] = field(default_factory=dict)


def _norm(text: str) -> str:
    return fold_accents(text).strip().lower()


def _language_key(name: str) -> str:
    folded = _norm(name)
    return LANGUAGE_ALIASES.get(folded, folded)


def _level_index(text: str) -> int | None:
    """CEFR index of a level cell ("B1 - Intermedio" -> B1), native ranked top."""
    # The CEFR code wins over words: "C1 (non-native)" contains "native".
    match = _CEFR_RE.search(text)
    if match:
        return CEFR_LEVELS.index(match.group(1).upper())
    if set(re.findall(r"[a-z]+", _norm(text))) & _NATIVE_WORDS:
        return CEFR_LEVELS.index("NATIVE")
    return None


def _yes_no(value: str) -> bool | None:
    word = (re.findall(r"[a-z]+", _norm(value)) or [""])[0]
    if word in YES_WORDS:
        return True
    if word in NO_WORDS:
        return False
    return None


def _plain(line: str) -> str:
    """A profile line without its bullet and Markdown emphasis ("- **English**: C1")."""
    return _EMPHASIS_RE.sub("", line).strip().lstrip("-* ")


def _sections(text: str) -> dict[str, str]:
    """`## NAME` -> body, keyed by the folded lowercase name."""
    headings = list(_SECTION_RE.finditer(text))
    return {
        _norm(m.group(1)): text[m.end(): headings[i + 1].start() if i + 1 < len(headings) else len(text)]
        for i, m in enumerate(headings)
    }


def _parse_languages(body: str) -> dict[str, int]:
    languages: dict[str, int] = {}
    for line in body.splitlines():
        parts = [p for p in _LANGUAGE_SEP_RE.split(_plain(line)) if p]
        if len(parts) < 2:
            continue
        level = _level_index(" ".join(parts[1:]))
        if level is not None:
            languages[_language_key(parts[0])] = level
    return languages


def parse_profile(text: str) -> EligibilityProfile:
    """Read the ELIGIBILITY and LANGUAGES sections; missing values stay None."""
    sections = _sections(strip_template_guidance(text))
    languages: dict[str, int] = {}
    for name, body in sections.items():
        if name in LANGUAGE_SECTION_NAMES:
            languages.update(_parse_languages(body))
    body = next((b for n, b in sections.items() if n in ELIGIBILITY_SECTION_NAMES), None)
    if body is None:
        return EligibilityProfile(languages=languages)

    values: dict[str, str] = {}
    for line in body.splitlines():
        key, sep, value = _plain(line).partition(":")
        if not sep:
            continue
        target = ELIGIBILITY_PROFILE_KEYS.get(_norm(key.split("(")[0]))
        if target and value.strip():
            values[target] = value.strip()

    years = None
    # A range ("1-2") is ambiguous either way — prefer omission over guessing.
    if "years" in values and not _RANGE_RE.search(values["years"]) and (
            match := _NUMBER_RE.search(values["years"])):
        years = float(match.group(0).replace(",", "."))
    cities = None
    if "cities" in values:
        cities = tuple(c for c in map(_norm, re.split(r"[,;]", values["cities"])) if c) or None
    return EligibilityProfile(
        has_section=True,
        years=years,
        cities=cities,
        relocation=_yes_no(values["relocation"]) if "relocation" in values else None,
        driving_license=_yes_no(values["driving_license"]) if "driving_license" in values else None,
        languages=languages,
    )


def _validate_language(entry: object) -> dict:
    name = entry.get("language") if isinstance(entry, dict) else None
    level = entry.get("level") if isinstance(entry, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise EligibilityError("languages", "each language needs a non-empty 'language'")
    # Strict here, unlike the profile's free-text level cells: the agent must
    # send an exact level, not prose applyr would have to interpret.
    index = _OFFER_LEVELS.get(_norm(level)) if isinstance(level, str) else None
    if index is None:
        raise EligibilityError("languages", f"invalid level {level!r} for '{name}' "
                                            "(use A1, A2, B1, B2, C1, C2 or native)")
    return {"language": name.strip(), "level": CEFR_LEVELS[index]}


def validate_requirements(raw: object) -> dict:
    """Normalize `add`'s `eligibility` block, or raise EligibilityError naming the field."""
    if not isinstance(raw, dict):
        raise EligibilityError("eligibility", "'eligibility' must be an object")
    unknown = sorted(set(raw) - set(ELIGIBILITY_KEYS))
    if unknown:
        raise EligibilityError(unknown[0], f"unknown eligibility key '{unknown[0]}' "
                                           f"(allowed: {', '.join(ELIGIBILITY_KEYS)})")
    req: dict = {}
    if "min_years" in raw:
        years = raw["min_years"]
        if isinstance(years, bool) or not isinstance(years, (int, float)) or not math.isfinite(years) or years < 0:
            raise EligibilityError("min_years", "'min_years' must be a non-negative number")
        req["min_years"] = years
    if "languages" in raw:
        if not isinstance(raw["languages"], list):
            raise EligibilityError("languages", "'languages' must be a list of {language, level}")
        req["languages"] = [_validate_language(entry) for entry in raw["languages"]]
    if "city" in raw:
        if not isinstance(raw["city"], str) or not raw["city"].strip():
            raise EligibilityError("city", "'city' must be a non-empty string")
        req["city"] = raw["city"].strip()
    if "driving_license" in raw:
        if not isinstance(raw["driving_license"], bool):
            raise EligibilityError("driving_license", "'driving_license' must be true or false")
        req["driving_license"] = raw["driving_license"]
    return req


def _item(name: str, status: str, required: str, profile: str | None, detail: str) -> dict:
    return {"item": name, "status": status, "required": required, "profile": profile, "detail": detail}


def _years_item(required: float, profile: EligibilityProfile) -> dict:
    need = f"{required:g}"
    if required == 0:
        return _item("min_years", ELIGIBILITY_PASS, need, None, "no minimum")
    if profile.years is None:
        return _item("min_years", ELIGIBILITY_UNKNOWN, need, None, "relevant years not stated in the profile")
    have = f"{profile.years:g}"
    short = required - profile.years
    if short <= 0:
        return _item("min_years", ELIGIBILITY_PASS, need, have, f"{have} years, {need} required")
    status = ELIGIBILITY_WARN if short <= ELIGIBILITY_YEARS_TOLERANCE else ELIGIBILITY_BLOCK
    return _item("min_years", status, need, have, f"{need} years required, profile states {have}")


def _language_item(entry: dict, profile: EligibilityProfile) -> dict:
    name, level = entry["language"], entry["level"]
    label = f"language:{_language_key(name)}"
    have = profile.languages.get(_language_key(name))
    if have is None:
        return _item(label, ELIGIBILITY_UNKNOWN, level, None, f"{name} not listed in the profile's languages")
    short = CEFR_LEVELS.index(level) - have
    if short <= 0:
        status = ELIGIBILITY_PASS
    else:
        status = ELIGIBILITY_WARN if short == 1 else ELIGIBILITY_BLOCK
    return _item(label, status, level, CEFR_LEVELS[have], f"{name} {level} required, profile {CEFR_LEVELS[have]}")


def _location_item(city: str | None, work_mode: str | None, profile: EligibilityProfile) -> dict | None:
    if work_mode == "remote":
        return _item("location", ELIGIBILITY_PASS, city or "remote", None, "remote role") if city else None
    if work_mode not in _ONSITE_MODES:
        if city is None:
            return None
        return _item("location", ELIGIBILITY_UNKNOWN, city, None, "work mode not stated")
    if city is None:
        return _item("location", ELIGIBILITY_UNKNOWN, work_mode, None, f"{work_mode} role with no city stated")
    listed = ", ".join(profile.cities) if profile.cities else None
    # "Madrid, Spain" / "Madrid (Spain)" -> "madrid": offers append the country.
    if profile.cities and _norm(re.split(r"[,(]", city)[0]) in profile.cities:
        return _item("location", ELIGIBILITY_PASS, city, listed, f"{city} is an accepted city")
    if profile.relocation:
        return _item("location", ELIGIBILITY_PASS, city, listed, "relocation accepted")
    if profile.cities is None or profile.relocation is None:
        return _item("location", ELIGIBILITY_UNKNOWN, city, listed, "accepted cities or relocation not stated")
    return _item("location", ELIGIBILITY_BLOCK, city, listed,
                 f"{work_mode} in {city}, not an accepted city and relocation not accepted")


def _license_item(profile: EligibilityProfile) -> dict:
    if profile.driving_license is None:
        return _item("driving_license", ELIGIBILITY_UNKNOWN, "yes", None, "driving license not stated")
    if profile.driving_license:
        return _item("driving_license", ELIGIBILITY_PASS, "yes", "yes", "holds a driving license")
    return _item("driving_license", ELIGIBILITY_BLOCK, "yes", "no", "driving license required, profile has none")


def evaluate(requirements: dict, profile: EligibilityProfile, work_mode: str | None) -> dict:
    """Judge validated requirements: {"items": [...], "blocked": bool}."""
    items: list[dict] = []
    if "min_years" in requirements:
        items.append(_years_item(requirements["min_years"], profile))
    items.extend(_language_item(e, profile) for e in requirements.get("languages", []))
    location = _location_item(requirements.get("city"), work_mode, profile)
    if location:
        items.append(location)
    if requirements.get("driving_license"):
        items.append(_license_item(profile))
    return {"items": items, "blocked": any(i["status"] == ELIGIBILITY_BLOCK for i in items)}


def load_stored(raw: str | None) -> dict | None:
    """A stored eligibility column (requirements or result) as a dict — None when absent or corrupt."""
    if not raw:
        return None
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return result if isinstance(result, dict) else None


def block_reason(result: dict | None) -> str | None:
    """"language:english: english C1 required, profile B1" — or None when nothing blocks."""
    if not result or not result.get("blocked"):
        return None
    return "; ".join(f"{i['item']}: {i['detail']}" for i in result["items"] if i["status"] == ELIGIBILITY_BLOCK)
