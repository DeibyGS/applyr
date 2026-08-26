"""Tests for CV tailoring hints."""

import pytest

from applyr.cv import _get_tailoring_hints, _format_tailoring_hints


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
