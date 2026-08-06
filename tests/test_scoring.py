"""Tests for the scoring engine."""

import pytest

from applyr.scoring import calculate_score


@pytest.mark.unit
class TestCalculateScore:

    def test_empty_topics_returns_zero(self, tmp_applyr):
        assert calculate_score({}) == 0

    def test_single_topic(self, tmp_applyr):
        topics = {"tech_stack": {"score": 80, "detail": "ok"}}
        result = calculate_score(topics)
        assert result == 80

    def test_all_topics_perfect(self, tmp_applyr):
        topics = {
            "tech_stack": {"score": 100, "detail": ""},
            "education": {"score": 100, "detail": ""},
            "english": {"score": 100, "detail": ""},
            "experience": {"score": 100, "detail": ""},
            "projects": {"score": 100, "detail": ""},
            "cultural_fit": {"score": 100, "detail": ""},
        }
        assert calculate_score(topics) == 100

    def test_all_topics_zero(self, tmp_applyr):
        topics = {
            "tech_stack": {"score": 0, "detail": ""},
            "education": {"score": 0, "detail": ""},
        }
        assert calculate_score(topics) == 0

    def test_weighted_average(self, tmp_applyr):
        # tech_stack weight=30, education weight=15
        # (80*30 + 40*15) / (30+15) = 3000/45 = 66.67 -> 67
        topics = {
            "tech_stack": {"score": 80, "detail": ""},
            "education": {"score": 40, "detail": ""},
        }
        assert calculate_score(topics) == 67

    def test_invalid_score_skipped(self, tmp_applyr):
        topics = {
            "tech_stack": {"score": 80, "detail": "ok"},
            "education": {"score": -10, "detail": "invalid"},
        }
        # -10 is out of range, should be skipped -> only tech_stack counts
        assert calculate_score(topics) == 80

    def test_score_above_100_skipped(self, tmp_applyr):
        topics = {
            "tech_stack": {"score": 150, "detail": ""},
            "education": {"score": 60, "detail": ""},
        }
        assert calculate_score(topics) == 60

    def test_string_score_skipped(self, tmp_applyr):
        topics = {
            "tech_stack": {"score": "high", "detail": ""},
            "education": {"score": 70, "detail": ""},
        }
        assert calculate_score(topics) == 70

    def test_missing_score_key_defaults_zero(self, tmp_applyr):
        topics = {"tech_stack": {"detail": "no score key"}}
        assert calculate_score(topics) == 0

    def test_unknown_topic_uses_default_weight(self, tmp_applyr):
        topics = {
            "tech_stack": {"score": 100, "detail": ""},
            "unknown_topic": {"score": 50, "detail": ""},
        }
        result = calculate_score(topics)
        # unknown_topic gets DEFAULT_TOPIC_WEIGHT (0.10)
        # tech_stack normalized weight = 0.30
        # (100*0.30 + 50*0.10) / (0.30+0.10) = 35/0.40 = 87.5 -> 88
        assert result == 88

    def test_boundary_zero(self, tmp_applyr):
        topics = {"tech_stack": {"score": 0, "detail": ""}}
        assert calculate_score(topics) == 0

    def test_boundary_hundred(self, tmp_applyr):
        topics = {"tech_stack": {"score": 100, "detail": ""}}
        assert calculate_score(topics) == 100
