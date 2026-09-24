"""Eligibility / knockout evaluator — pure, deterministic (ADR-017)."""

import pytest

from applyr.eligibility import (
    EligibilityError,
    EligibilityProfile,
    block_reason,
    evaluate,
    parse_profile,
    validate_requirements,
)

PROFILE_EN = """\
## LANGUAGES
- English: B2
- Spanish: Native

## ELIGIBILITY
- Relevant experience (years): 2
- Cities: Madrid, Alcalá de Henares
- Relocation: no
- Driving license: yes
"""

# Deiby's real layout: Spanish headings/keys and a languages *table*.
PROFILE_ES = """\
## IDIOMAS

| Idioma | Nivel |
|--------|-------|
| Espanol | Nativo |
| Ingles | B1 - Intermedio |

## ELEGIBILIDAD
- Experiencia relevante (años): 1,5
- Ciudades: Málaga
- Reubicación: sí
- Carnet de conducir: no
"""


def _status(result: dict, item: str) -> str:
    return next(i["status"] for i in result["items"] if i["item"] == item)


def _eval(requirements: dict, profile_text: str = PROFILE_EN, work_mode: str | None = "onsite") -> dict:
    return evaluate(validate_requirements(requirements), parse_profile(profile_text), work_mode)


# --- profile parsing ---------------------------------------------------------

def test_parse_english_profile():
    p = parse_profile(PROFILE_EN)
    assert p.has_section and p.years == 2
    assert p.cities == ("madrid", "alcala de henares")
    assert p.relocation is False and p.driving_license is True
    assert p.languages == {"english": 3, "spanish": 6}


def test_parse_spanish_profile_with_language_table():
    p = parse_profile(PROFILE_ES)
    assert p.has_section and p.years == 1.5
    assert p.cities == ("malaga",) and p.relocation is True and p.driving_license is False
    assert p.languages == {"spanish": 6, "english": 2}


def test_profile_without_section_keeps_languages_and_has_no_section():
    p = parse_profile("## LANGUAGES\n- English: C1\n")
    assert not p.has_section and p.years is None and p.languages == {"english": 4}


def test_template_guidance_comments_are_ignored():
    p = parse_profile("## ELIGIBILITY\n<!-- Relevant experience (years): 9 -->\n")
    assert p.has_section and p.years is None


def test_unparseable_years_is_none():
    p = parse_profile("## ELIGIBILITY\n- Relevant experience (years): some\n")
    assert p.years is None


# --- requirement validation (AC-E1) ------------------------------------------

@pytest.mark.parametrize("raw, field", [
    ({"salary": 1}, "salary"),
    ({"min_years": -1}, "min_years"),
    ({"min_years": "3"}, "min_years"),
    ({"min_years": True}, "min_years"),
    ({"min_years": float("nan")}, "min_years"),
    ({"languages": [{"language": "english", "level": "fluent"}]}, "languages"),
    ({"languages": [{"language": "english", "level": "B1 - Intermedio"}]}, "languages"),
    ({"languages": [{"language": "", "level": "B2"}]}, "languages"),
    ({"languages": "english"}, "languages"),
    ({"city": ""}, "city"),
    ({"driving_license": "yes"}, "driving_license"),
    ([], "eligibility"),
])
def test_invalid_blocks_name_the_field(raw, field):
    with pytest.raises(EligibilityError) as exc:
        validate_requirements(raw)
    assert exc.value.field == field


def test_valid_block_is_normalized():
    req = validate_requirements({"min_years": 3, "languages": [{"language": " English ", "level": "c1"}],
                                 "city": " Madrid ", "driving_license": True})
    assert req == {"min_years": 3, "languages": [{"language": "English", "level": "C1"}],
                   "city": "Madrid", "driving_license": True}
    assert validate_requirements({"languages": [{"language": "es", "level": "Nativo"}]})["languages"][0]["level"] == "NATIVE"


# --- years (AC-03) -----------------------------------------------------------

@pytest.mark.parametrize("required, expected", [(0, "pass"), (2, "pass"), (3, "warn"), (3.5, "block"), (5, "block")])
def test_years(required, expected):
    assert _status(_eval({"min_years": required}), "min_years") == expected


# --- languages (AC-04, AC-05) ------------------------------------------------

@pytest.mark.parametrize("level, expected", [("B1", "pass"), ("B2", "pass"), ("C1", "warn"), ("C2", "block")])
def test_language_levels(level, expected):
    assert _status(_eval({"languages": [{"language": "english", "level": level}]}), "language:english") == expected


def test_language_names_match_across_spanish_and_english():
    result = _eval({"languages": [{"language": "Inglés", "level": "B2"}]}, PROFILE_ES)
    assert _status(result, "language:english") == "warn"  # profile B1


def test_native_counts_as_at_least_c2():
    assert _status(_eval({"languages": [{"language": "spanish", "level": "C2"}]}), "language:spanish") == "pass"


def test_unlisted_language_is_unknown():
    assert _status(_eval({"languages": [{"language": "German", "level": "B1"}]}), "language:german") == "unknown"


# --- location (AC-06, AC-07) -------------------------------------------------

@pytest.mark.parametrize("city, expected", [("Madrid", "pass"), ("alcala de henares", "pass"), ("Barcelona", "block")])
def test_location_without_relocation(city, expected):
    assert _status(_eval({"city": city}), "location") == expected


def test_relocation_accepted_passes_any_city():
    assert _status(_eval({"city": "Barcelona"}, PROFILE_ES, "hybrid"), "location") == "pass"


def test_remote_never_blocks():
    assert _status(_eval({"city": "Barcelona"}, work_mode="remote"), "location") == "pass"


def test_hybrid_without_city_is_unknown():
    assert _status(_eval({}, work_mode="hybrid"), "location") == "unknown"


def test_city_without_work_mode_is_unknown():
    assert _status(_eval({"city": "Barcelona"}, work_mode=None), "location") == "unknown"


# --- driving license (AC-08) -------------------------------------------------

def test_driving_license():
    assert _status(_eval({"driving_license": True}), "driving_license") == "pass"
    assert _status(_eval({"driving_license": True}, PROFILE_ES), "driving_license") == "block"
    assert _eval({"driving_license": False}, work_mode="remote")["items"] == []


# --- unknown never blocks (AC-09, AC-E4) --------------------------------------

def test_no_profile_section_makes_everything_unknown_and_unblocked():
    result = evaluate(validate_requirements({"min_years": 9, "city": "Oslo", "driving_license": True}),
                      EligibilityProfile(), "onsite")
    assert {i["status"] for i in result["items"]} == {"unknown"}
    assert result["blocked"] is False and block_reason(result) is None


# --- aggregation -------------------------------------------------------------

def test_any_block_blocks_and_reason_lists_only_blocking_items():
    result = _eval({"min_years": 3, "languages": [{"language": "english", "level": "C2"}], "city": "Oslo"})
    assert result["blocked"] is True
    reason = block_reason(result)
    assert "language:english" in reason and "location" in reason and "min_years" not in reason


def test_deterministic():
    req = {"min_years": 3, "languages": [{"language": "english", "level": "C1"}], "city": "Oslo"}
    assert _eval(req) == _eval(req)


# --- /code-review findings ---------------------------------------------------

def test_markdown_bold_labels_are_read():
    p = parse_profile("## LANGUAGES\n- **English**: C1\n| **Spanish** | Native |\n\n"
                      "## ELIGIBILITY\n- **Relevant experience (years)**: 2\n- **Driving license:** yes\n")
    assert p.languages == {"english": 4, "spanish": 6}
    assert p.years == 2 and p.driving_license is True


@pytest.mark.parametrize("city", ["Madrid, Spain", "Madrid (Spain)"])
def test_city_with_country_matches_listed_city(city):
    assert _status(_eval({"city": city}), "location") == "pass"


def test_non_native_with_cefr_code_keeps_the_code():
    assert parse_profile("## LANGUAGES\n- English: C1 (non-native)\n").languages == {"english": 4}


def test_years_range_is_unknown():
    assert parse_profile("## ELIGIBILITY\n- Relevant experience (years): 1-2\n").years is None
