"""Tests for three-state recommendation logic and match breakdown."""

import pytest

from applyr.commands.core import _get_recommendation, _get_recommendation_label, _show_match_breakdown, _get_match_breakdown
from applyr.commands._helpers import _classify_topic, _classify_icon


class TestGetRecommendation:
    def test_strong_match(self):
        config = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
        rec, icon = _get_recommendation(85, config)
        assert rec == "apply"
        assert icon == "✅"

    def test_good_match(self):
        config = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
        rec, icon = _get_recommendation(70, config)
        assert rec == "maybe"
        assert icon == "⚠️"

    def test_low_match(self):
        config = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
        rec, icon = _get_recommendation(50, config)
        assert rec == "low_match"
        assert icon == "❌"

    def test_boundary_apply(self):
        config = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
        rec, _ = _get_recommendation(80, config)
        assert rec == "apply"

    def test_boundary_maybe(self):
        config = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
        rec, _ = _get_recommendation(60, config)
        assert rec == "maybe"

    def test_boundary_low(self):
        config = {"general": {"threshold_apply": 80, "threshold_maybe": 60}}
        rec, _ = _get_recommendation(59, config)
        assert rec == "low_match"

    def test_custom_thresholds(self):
        config = {"general": {"threshold_apply": 90, "threshold_maybe": 70}}
        rec, _ = _get_recommendation(85, config)
        assert rec == "maybe"


class TestGetRecommendationLabel:
    def test_apply(self):
        assert "APPLY" in _get_recommendation_label("apply")

    def test_maybe(self):
        assert "MAYBE" in _get_recommendation_label("maybe")

    def test_low_match(self):
        assert "LOW MATCH" in _get_recommendation_label("low_match")


class TestClassifyTopic:
    def test_strong(self):
        assert _classify_topic(95) == "strong"
        assert _classify_topic(80) == "strong"

    def test_partial(self):
        assert _classify_topic(79) == "partial"
        assert _classify_topic(50) == "partial"

    def test_missing(self):
        assert _classify_topic(49) == "missing"
        assert _classify_topic(0) == "missing"


class TestClassifyIcon:
    def test_strong(self):
        assert _classify_icon("strong") == "✓"

    def test_partial(self):
        assert _classify_icon("partial") == "△"

    def test_missing(self):
        assert _classify_icon("missing") == "✕"


class TestGetMatchBreakdown:
    def test_empty(self):
        result = _get_match_breakdown([])
        assert result == {"strong": [], "partial": [], "missing": []}

    def test_mixed(self):
        topics = [
            {"topic": "tech_stack", "score": 90, "detail": "Python expert"},
            {"topic": "experience", "score": 60, "detail": "2 years"},
            {"topic": "projects", "score": 30, "detail": "No relevant projects"},
        ]
        result = _get_match_breakdown(topics)
        assert len(result["strong"]) == 1
        assert len(result["partial"]) == 1
        assert len(result["missing"]) == 1
        assert result["strong"][0]["topic"] == "tech_stack"
        assert result["partial"][0]["topic"] == "experience"
        assert result["missing"][0]["topic"] == "projects"
