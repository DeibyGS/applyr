"""Tests for three-state recommendation logic and match breakdown."""

import pytest

from applyr.commands.core import _get_recommendation, _get_recommendation_label, _show_match_breakdown, _get_match_breakdown, _get_why_you_match
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

    def test_invalid_above_100(self):
        assert _classify_topic(150) == "invalid"
        assert _classify_topic(101) == "invalid"

    def test_invalid_below_zero(self):
        assert _classify_topic(-1) == "invalid"
        assert _classify_topic(-10) == "invalid"


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

    def test_out_of_range_score_appears_in_no_bucket(self):
        """A score outside [0, 100] previously fell into the `else` branch
        and was displayed as "Missing" (or "Strong" if >100), contradicting
        the compatibility% that already excludes it — must appear nowhere."""
        topics = [
            {"topic": "tech_stack", "score": 150, "detail": "typo'd a 15 as 150"},
            {"topic": "projects", "score": 90, "detail": "Relevant projects"},
        ]
        result = _get_match_breakdown(topics)
        all_topics = [e["topic"] for bucket in result.values() for e in bucket]
        assert "tech_stack" not in all_topics
        assert "projects" in all_topics


class TestGetWhyYouMatch:
    def test_empty(self):
        why_match, weakness = _get_why_you_match([], {})
        assert why_match == []
        assert weakness is None

    def test_strong_only(self):
        topics = [
            {"topic": "tech_stack", "score": 90, "detail": "Python expert"},
            {"topic": "projects", "score": 85, "detail": "Relevant projects"},
        ]
        topic_labels = {"tech_stack": "Tech Stack", "projects": "Projects"}
        why_match, weakness = _get_why_you_match(topics, topic_labels)
        assert len(why_match) == 2
        assert weakness is None

    def test_with_weakness(self):
        """The weakest topic wins, whichever bucket it lands in.

        This asserted "Experience" (60, partial) over "Projects" (30, missing):
        the old rule preferred the partial bucket outright, so the line
        contradicted the "Missing" section printed directly above it.
        """
        topics = [
            {"topic": "tech_stack", "score": 90, "detail": "Python expert"},
            {"topic": "experience", "score": 60, "detail": "2 years"},
            {"topic": "projects", "score": 30, "detail": "No relevant projects"},
        ]
        topic_labels = {"tech_stack": "Tech Stack", "experience": "Experience", "projects": "Projects"}
        why_match, weakness = _get_why_you_match(topics, topic_labels)
        assert len(why_match) == 1
        assert weakness is not None
        assert "Projects" in weakness

    def test_weakest_missing_wins_over_a_higher_missing(self):
        """When everything is weak, surface the worst — not the least bad.

        The old `missing` branch sorted descending, so a profile that was bad
        across the board was told its *strongest* shortfall was the problem.
        """
        topics = [
            {"topic": "experience", "score": 10, "detail": "none"},
            {"topic": "projects", "score": 40, "detail": "few"},
        ]
        labels = {"experience": "Experience", "projects": "Projects"}
        _, weakness = _get_why_you_match(topics, labels)
        assert "Experience" in weakness

    def test_a_partial_can_still_be_the_weakest(self):
        """The fix must not simply invert the old preference."""
        topics = [
            {"topic": "tech_stack", "score": 95, "detail": "expert"},
            {"topic": "english", "score": 55, "detail": "B1"},
        ]
        labels = {"tech_stack": "Tech Stack", "english": "English"}
        _, weakness = _get_why_you_match(topics, labels)
        assert "English" in weakness

    def test_top_three(self):
        topics = [
            {"topic": "tech_stack", "score": 95, "detail": "Expert"},
            {"topic": "projects", "score": 90, "detail": "Relevant"},
            {"topic": "education", "score": 85, "detail": "CS degree"},
            {"topic": "english", "score": 80, "detail": "Fluent"},
        ]
        topic_labels = {"tech_stack": "Tech Stack", "projects": "Projects", "education": "Education", "english": "English"}
        why_match, weakness = _get_why_you_match(topics, topic_labels)
        assert len(why_match) == 3  # Only top 3

    def test_out_of_range_score_is_never_the_biggest_weakness(self):
        """An out-of-range score used to fall into the `else` (missing)
        branch, so a stray -10 or 150 could win "biggest weakness" purely by
        being numerically lowest — not because it's a real gap."""
        topics = [
            {"topic": "tech_stack", "score": -10, "detail": "bad input"},
            {"topic": "experience", "score": 40, "detail": "junior"},
        ]
        labels = {"tech_stack": "Tech Stack", "experience": "Experience"}
        _, weakness = _get_why_you_match(topics, labels)
        assert "Experience" in weakness
        assert "Tech Stack" not in weakness


from applyr.commands._helpers import _show_score_breakdown


class TestShowScoreBreakdown:
    def test_empty(self, capsys):
        _show_score_breakdown([], {})
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_single_topic(self, capsys):
        topics = [{"topic": "tech_stack", "score": 80}]
        weights = {"tech_stack": 0.3}
        _show_score_breakdown(topics, weights)
        captured = capsys.readouterr()
        assert "Technical skills" in captured.out
        assert "80%" in captured.out
        assert "24.0" in captured.out  # 80 * 0.3

    def test_multiple_topics(self, capsys):
        topics = [
            {"topic": "tech_stack", "score": 80},
            {"topic": "experience", "score": 60},
        ]
        weights = {"tech_stack": 0.3, "experience": 0.15}
        _show_score_breakdown(topics, weights)
        captured = capsys.readouterr()
        assert "Technical skills" in captured.out
        assert "Experience" in captured.out
        assert "Total" in captured.out
        # Total must be the weighted AVERAGE (divided by weights actually
        # used: 0.3+0.15=0.45), not the raw contribution sum (24+9=33) — the
        # raw sum silently disagreed with the real compatibility% whenever
        # fewer than all topics were scored, which is the common case.
        assert "73.3%" in captured.out
