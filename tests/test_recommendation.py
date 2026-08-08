"""Tests for three-state recommendation logic."""

import pytest

from applyr.commands.core import _get_recommendation, _get_recommendation_label


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
