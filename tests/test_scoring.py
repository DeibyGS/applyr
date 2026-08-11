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


class TestOmittedTopicsAreExcluded:
    """The instructions used to tell agents to score an unmentioned requirement
    100. That put a 25-point floor under any vague offer — `education` and
    `english` alone carry 25% of the weight — so a posting that omitted half its
    requirements outscored a detailed one describing the same job.

    The engine already did the right thing: it sums only the weights of the
    topics it is given. These tests pin that contract so the scoring and the
    written instructions cannot drift apart again.
    """

    def test_omitted_topic_is_not_a_zero(self, tmp_applyr):
        """Leaving a topic out must not drag the average down."""
        from applyr.scoring import calculate_score

        assert calculate_score({"tech_stack": {"score": 80}}) == 80

    def test_omitted_topic_redistributes_its_weight(self, tmp_applyr):
        """Two topics at the same score average to that score, whatever the weights."""
        from applyr.scoring import calculate_score

        assert calculate_score({
            "tech_stack": {"score": 60},   # weight 30
            "cultural_fit": {"score": 60},  # weight 10
        }) == 60

    def test_scoring_unmentioned_topics_100_inflates_the_result(self, tmp_applyr):
        """The regression this guards against, stated as an assertion.

        Same real offer (Fibonad/Lab Cave, #207): the four topics the posting
        actually describes, then the same four plus education and english padded
        to 100 because the offer never mentions them.
        """
        from applyr.scoring import calculate_score

        stated = {
            "tech_stack": {"score": 40},
            "projects": {"score": 75},
            "experience": {"score": 60},
            "cultural_fit": {"score": 85},
        }
        padded = {**stated, "education": {"score": 100}, "english": {"score": 100}}

        assert calculate_score(stated) == 59
        assert calculate_score(padded) == 70
        assert calculate_score(padded) - calculate_score(stated) == 11

    def test_a_single_omitted_topic_still_scores(self, tmp_applyr):
        """Five of six topics is the common case, not an error path."""
        from applyr.scoring import calculate_score

        score = calculate_score({
            "tech_stack": {"score": 50},
            "projects": {"score": 50},
            "experience": {"score": 50},
            "education": {"score": 50},
            "cultural_fit": {"score": 50},
        })
        assert score == 50
