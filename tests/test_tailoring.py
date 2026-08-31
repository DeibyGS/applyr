"""Tests for CV tailoring hints and evidence evaluation."""

import pytest

from applyr.cv import _get_tailoring_hints, _format_tailoring_hints
from applyr.scoring import (
    evaluate_evidence, build_tailoring_plan, _parse_tech_stack,
)


class TestGetTailoringHints:
    def test_empty(self):
        highlight, de_emphasize, not_included = _get_tailoring_hints(None, {})
        assert highlight == []
        assert de_emphasize == []
        assert not_included == []

    def test_tech_stack(self):
        highlight, de_emphasize, not_included = _get_tailoring_hints("Python, AWS, PostgreSQL", {})
        assert "Python" in highlight
        assert "AWS" in highlight
        assert "PostgreSQL" in highlight

    def test_strong_topics(self):
        topics = {
            "tech_stack": {"score": 90, "detail": "Python expert"},
            "experience": {"score": 85, "detail": "5 years"},
        }
        highlight, de_emphasize, not_included = _get_tailoring_hints(None, topics)
        assert "Technical Skills" in highlight
        assert "Work Experience" in highlight

    def test_missing_topics(self):
        topics = {
            "tech_stack": {"score": 30, "detail": "Limited skills"},
            "experience": {"score": 20, "detail": "No experience"},
        }
        highlight, de_emphasize, not_included = _get_tailoring_hints(None, topics)
        assert "Technical Skills" in de_emphasize
        assert "Work Experience" in de_emphasize


class TestGetTailoringHintsGroundedAgainstProfile:
    """profile_text truthy path — grounded via the Evidence Graph parser
    (applyr/evidence.py, PR3 of specs/evidence-based-cv-engine) instead of a
    raw substring check."""

    def test_alias_form_in_profile_matches_offer_term(self):
        # The bug this PR fixes: a raw substring check missed this because the
        # offer says "AWS" and the profile spells it "Amazon Web Services".
        profile = "## TECHNICAL SKILLS\n\nCloud: Amazon Web Services, Docker\n"
        highlight, _, not_included = _get_tailoring_hints("AWS, Docker", {}, profile)
        assert "AWS" in highlight
        assert "AWS" not in not_included

    def test_evidenced_term_is_highlighted(self):
        profile = "## TECHNICAL SKILLS\n\nBackend: Python, FastAPI\n"
        highlight, _, not_included = _get_tailoring_hints("Python, Kubernetes", {}, profile)
        assert "Python" in highlight
        assert "Python" not in not_included

    def test_unevidenced_term_is_not_included(self):
        profile = "## TECHNICAL SKILLS\n\nBackend: Python, FastAPI\n"
        _, _, not_included = _get_tailoring_hints("Python, Kubernetes", {}, profile)
        assert "Kubernetes" in not_included

    def test_profile_text_is_used_raw_case_insensitively(self):
        # The call site stopped pre-lowering profile_text (cv.py:445) — the
        # Evidence Graph's own matching (evidence.is_evidenced) must still be
        # case-insensitive, and entry_context/text must keep original casing.
        profile = "## WORK EXPERIENCE\n\n**Backend Developer — Acme**\n- Built APIs with FastAPI\n"
        highlight, _, _ = _get_tailoring_hints("fastapi", {}, profile)
        assert "fastapi" in highlight


class TestFormatTailoringHints:
    def test_empty(self):
        result = _format_tailoring_hints([], [], [])
        assert result == ""

    def test_highlight_only(self):
        result = _format_tailoring_hints(["Python", "AWS"], [], [])
        assert "TAILOR" in result
        assert "Python" in result
        assert "AWS" in result

    def test_de_emphasize_only(self):
        result = _format_tailoring_hints([], ["Frontend", "Mobile"], [])
        assert "DE-EMPHASIZE" in result
        assert "Frontend" in result
        assert "Mobile" in result

    def test_all(self):
        result = _format_tailoring_hints(["Python"], ["Frontend"], ["React"])
        assert "TAILOR" in result
        assert "DE-EMPHASIZE" in result
        assert "NOT INCLUDED" in result


# ---------------------------------------------------------------------------
# Evidence evaluation tests
# ---------------------------------------------------------------------------

PROFILE_PYTHON = """\
## WORK EXPERIENCE

**Backend Developer — Acme Corp**
- Built REST APIs with Python and FastAPI
- PostgreSQL database design

## TECHNICAL SKILLS

**Backend:** Python, FastAPI, PostgreSQL
**DevOps:** Docker
"""

PROFILE_WITH_AWS = """\
## WORK EXPERIENCE

**Cloud Engineer — CloudCo**
- Deployed services on AWS (EC2, S3, Lambda)

## TECHNICAL SKILLS

**Backend:** Python, FastAPI
**Cloud:** Amazon Web Services, Docker
"""


class TestEvaluateEvidence:
    def test_empty(self):
        result, claims = evaluate_evidence({}, "profile")
        assert result == {}
        result, claims = evaluate_evidence({"tech_stack": {"score": 80}}, "")
        assert result == {}

    def test_returns_parsed_claims(self):
        result, claims = evaluate_evidence(
            {"tech_stack": {"score": 85, "detail": "ok"}},
            PROFILE_PYTHON, "Python",
        )
        assert isinstance(claims, list)
        assert len(claims) > 0

    def test_strong_tech_evidence(self):
        topics = {"tech_stack": {"score": 85, "detail": "Strong Python match"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON, "Python, FastAPI, PostgreSQL")
        assert result["tech_stack"]["evidence_status"] == "strong"
        assert "Python" in result["tech_stack"]["evidence"]
        assert result["tech_stack"]["missing"] == []

    def test_weak_tech_evidence(self):
        topics = {"tech_stack": {"score": 70, "detail": "Partial match"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON, "Python, Kubernetes, Docker")
        assert result["tech_stack"]["evidence_status"] == "weak"
        assert "Python" in result["tech_stack"]["evidence"]
        assert "Kubernetes" in result["tech_stack"]["missing"]

    def test_missing_tech_evidence(self):
        topics = {"tech_stack": {"score": 50, "detail": "Limited match"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON, "Kubernetes, Terraform")
        assert result["tech_stack"]["evidence_status"] == "missing"
        assert result["tech_stack"]["evidence"] == []
        assert "Kubernetes" in result["tech_stack"]["missing"]

    def test_alias_aws_match(self):
        topics = {"tech_stack": {"score": 80, "detail": "AWS match"}}
        result, _ = evaluate_evidence(topics, PROFILE_WITH_AWS, "AWS, Docker")
        assert result["tech_stack"]["evidence_status"] == "strong"
        assert "AWS" in result["tech_stack"]["evidence"]

    def test_tech_stack_without_offer_string_falls_back_to_score(self):
        topics = {"tech_stack": {"score": 85, "detail": "Strong match but no tech string"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON)
        assert result["tech_stack"]["evidence_status"] == "strong"

    def test_tech_stack_weak_score_without_offer_string(self):
        topics = {"tech_stack": {"score": 60, "detail": "Moderate match"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON)
        assert result["tech_stack"]["evidence_status"] == "weak"

    def test_experience_strong(self):
        topics = {"experience": {"score": 85, "detail": "5 years relevant"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON)
        assert result["experience"]["evidence_status"] == "strong"

    def test_experience_weak(self):
        topics = {"experience": {"score": 60, "detail": "Some experience"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON)
        assert result["experience"]["evidence_status"] == "weak"

    def test_experience_missing(self):
        topics = {"experience": {"score": 30, "detail": "Limited"}}
        result, _ = evaluate_evidence(topics, PROFILE_PYTHON)
        assert result["experience"]["evidence_status"] == "missing"


class TestBuildTailoringPlan:
    def test_basic_plan(self):
        offer = {
            "title": "Backend Developer",
            "company": "Acme Corp",
            "tech_stack": "Python, FastAPI, PostgreSQL",
            "seniority_level": "mid",
            "role_category": "backend",
        }
        topics = {
            "tech_stack": {"score": 85, "detail": "Strong Python match"},
            "experience": {"score": 70, "detail": "Good experience"},
        }
        plan = build_tailoring_plan(offer, topics, PROFILE_PYTHON)

        assert plan["version"] == "1.0"
        assert plan["target_role"] == "Backend Developer"
        assert plan["company"] == "Acme Corp"
        assert len(plan["requirements"]) == 2
        assert plan["quality_constraints"]["max_pages"] == 1

    def test_forbidden_claims_from_missing(self):
        offer = {
            "title": "ML Engineer",
            "company": "AI Corp",
            "tech_stack": "Python, TensorFlow, Kubernetes",
            "seniority_level": "senior",
            "role_category": "ai",
        }
        topics = {
            "tech_stack": {"score": 60, "detail": "Python strong, others missing"},
        }
        plan = build_tailoring_plan(offer, topics, PROFILE_PYTHON)

        assert "TensorFlow experience" in plan["forbidden_claims"]
        assert "Kubernetes experience" in plan["forbidden_claims"]

    def test_seniority_affects_page_limit(self):
        offer_senior = {
            "title": "Lead Engineer",
            "company": "BigCorp",
            "tech_stack": "Python",
            "seniority_level": "senior",
            "role_category": "backend",
        }
        offer_junior = {
            "title": "Developer",
            "company": "SmallCorp",
            "tech_stack": "Python",
            "seniority_level": "junior",
            "role_category": "backend",
        }
        topics = {"tech_stack": {"score": 80, "detail": "ok"}}

        plan_senior = build_tailoring_plan(offer_senior, topics, PROFILE_PYTHON)
        plan_junior = build_tailoring_plan(offer_junior, topics, PROFILE_PYTHON)

        assert plan_senior["quality_constraints"]["max_pages"] == 2
        assert plan_junior["quality_constraints"]["max_pages"] == 1

    def test_skills_strategy(self):
        offer = {
            "title": "Backend Developer",
            "company": "Acme",
            "tech_stack": "Python, FastAPI, Kubernetes",
            "seniority_level": "mid",
            "role_category": "backend",
        }
        topics = {"tech_stack": {"score": 75, "detail": "partial match"}}
        plan = build_tailoring_plan(offer, topics, PROFILE_PYTHON)

        assert "Python" in plan["skills_strategy"]["core"]
        assert "FastAPI" in plan["skills_strategy"]["core"]
        assert "Kubernetes" in plan["skills_strategy"]["omit"]

    def test_tech_stack_with_parenthetical_grouping(self):
        offer = {
            "title": "AI Developer",
            "company": "TechCo",
            "tech_stack": "Python, JavaScript, LLMs (agentes, prompting, function calling), REST APIs, low-code/no-code (n8n/Make/Zapier)",
            "seniority_level": "junior",
            "role_category": "ai",
        }
        topics = {
            "tech_stack": {"score": 75, "detail": "Python/JS strong, LLMs partial"},
        }
        plan = build_tailoring_plan(offer, topics, PROFILE_PYTHON)

        # Parenthetical groupings must stay intact
        assert "LLMs (agentes, prompting, function calling)" in plan["evidence_map"]
        assert "low-code/no-code (n8n/Make/Zapier)" in plan["evidence_map"]
        # No broken fragments
        assert "LLMs (agentes" not in plan["forbidden_claims"]
        assert "function calling)" not in plan["forbidden_claims"]

    def test_null_seniority_does_not_produce_none_string(self):
        offer = {
            "title": "Developer",
            "company": "Corp",
            "tech_stack": "Python",
            "seniority_level": None,
            "role_category": None,
        }
        topics = {"tech_stack": {"score": 80, "detail": "ok"}}
        plan = build_tailoring_plan(offer, topics, PROFILE_PYTHON)
        assert "None" not in plan["summary_strategy"]["positioning"]

    def test_secondary_skills_populated_for_partial_match(self):
        offer = {
            "title": "Fullstack",
            "company": "Acme",
            "tech_stack": "Python, FastAPI, Redis, Kubernetes",
            "seniority_level": "mid",
            "role_category": "backend",
        }
        topics = {"tech_stack": {"score": 70, "detail": "partial"}}
        plan = build_tailoring_plan(offer, topics, PROFILE_PYTHON)
        # Python and FastAPI are evidenced; Redis and Kubernetes are not
        assert "Python" in plan["skills_strategy"]["core"]
        assert "FastAPI" in plan["skills_strategy"]["core"]
        assert "Kubernetes" in plan["skills_strategy"]["omit"]


class TestParseTechStack:
    def test_simple(self):
        assert _parse_tech_stack("Python, FastAPI") == ["Python", "FastAPI"]

    def test_parenthetical_grouping(self):
        result = _parse_tech_stack("Python, LLMs (agentes, prompting, function calling), REST")
        assert result == ["Python", "LLMs (agentes, prompting, function calling)", "REST"]

    def test_nested_parentheses(self):
        result = _parse_tech_stack("A, B (x (y), z), C")
        assert result == ["A", "B (x (y), z)", "C"]

    def test_empty(self):
        assert _parse_tech_stack("") == []
        assert _parse_tech_stack(None) == []

    def test_deduplication(self):
        result = _parse_tech_stack("Python, Python, FastAPI")
        assert result == ["Python", "FastAPI"]

    def test_trailing_comma(self):
        result = _parse_tech_stack("Python, FastAPI,")
        assert result == ["Python", "FastAPI"]

    def test_whitespace(self):
        result = _parse_tech_stack("  Python  ,  FastAPI  ")
        assert result == ["Python", "FastAPI"]
