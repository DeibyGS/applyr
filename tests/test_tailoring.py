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
