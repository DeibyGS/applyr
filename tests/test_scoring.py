"""Tests for the scoring engine."""

import pytest

from applyr.scoring import calculate_score


class TestScoreBreakdownMatchesCalculateScore:
    """`_show_score_breakdown`'s printed "Total" previously summed score*weight
    without dividing by the weights actually used, silently diverging from
    calculate_score() whenever fewer than all topics were scored — the
    rubric-encouraged common case (omit topics the offer doesn't mention).
    Live repro: offer #234 (Procesia), header showed 78%, the breakdown's own
    "Total" line showed 58.2%, same command, same screen."""

    def test_total_matches_calculate_score_on_partial_topics(self, tmp_applyr, capsys):
        from applyr.commands._helpers import _show_score_breakdown
        from applyr.config import load_config

        # Mirrors the real offer #234 repro: 4 of 6 topics scored.
        topics_for_calculate = {
            "tech_stack": {"score": 80, "detail": ""},
            "experience": {"score": 65, "detail": ""},
            "projects": {"score": 85, "detail": ""},
            "cultural_fit": {"score": 75, "detail": ""},
        }
        expected = calculate_score(topics_for_calculate)

        weights = load_config()["weights"]
        topics_for_breakdown = [{"topic": t, "score": v["score"]} for t, v in topics_for_calculate.items()]
        _show_score_breakdown(topics_for_breakdown, weights)

        out = capsys.readouterr().out
        total_line = next(line for line in out.splitlines() if line.strip().startswith("Total"))
        printed_pct = float(total_line.split()[1].rstrip("%"))
        assert printed_pct == pytest.approx(expected, abs=0.5)

    def test_total_still_correct_when_all_topics_are_scored(self, tmp_applyr, capsys):
        from applyr.commands._helpers import _show_score_breakdown
        from applyr.config import load_config

        topics_for_calculate = {t: {"score": 90, "detail": ""} for t in
                                 ("tech_stack", "education", "english", "experience", "projects", "cultural_fit")}
        expected = calculate_score(topics_for_calculate)
        assert expected == 90  # sanity: uniform score, any weights, total must equal it

        weights = load_config()["weights"]
        topics_for_breakdown = [{"topic": t, "score": 90} for t in topics_for_calculate]
        _show_score_breakdown(topics_for_breakdown, weights)

        out = capsys.readouterr().out
        total_line = next(line for line in out.splitlines() if line.strip().startswith("Total"))
        printed_pct = float(total_line.split()[1].rstrip("%"))
        assert printed_pct == pytest.approx(90.0, abs=0.5)

    def test_out_of_range_score_excluded_from_total_not_just_the_divisor(self, tmp_applyr, capsys):
        """Fixing the divisor alone (total_weight instead of 100%) was not
        enough: an out-of-range score left IN the numerator can still push
        Total above 100%, or otherwise off calculate_score()'s value — found
        by /code-review on this same PR. tech_stack=150 must be excluded
        entirely, the same way calculate_score() already excludes it."""
        from applyr.commands._helpers import _show_score_breakdown
        from applyr.config import load_config

        topics_for_calculate = {
            "tech_stack": {"score": 150, "detail": "typo'd a 15 as 150"},
            "projects": {"score": 90, "detail": ""},
        }
        expected = calculate_score(topics_for_calculate)
        assert expected == 90  # tech_stack excluded entirely by calculate_score()

        weights = load_config()["weights"]
        topics_for_breakdown = [{"topic": t, "score": v["score"]} for t, v in topics_for_calculate.items()]
        _show_score_breakdown(topics_for_breakdown, weights)

        out = capsys.readouterr().out
        assert "tech_stack" not in out and "Technical skills" not in out
        total_line = next(line for line in out.splitlines() if line.strip().startswith("Total"))
        printed_pct = float(total_line.split()[1].rstrip("%"))
        assert printed_pct == pytest.approx(expected, abs=0.5)
        assert printed_pct <= 100.0


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
        # tech_stack weight=35, education weight=5
        # (80*35 + 40*5) / (35+5) = 3000/40 = 75.0 -> 75
        topics = {
            "tech_stack": {"score": 80, "detail": ""},
            "education": {"score": 40, "detail": ""},
        }
        assert calculate_score(topics) == 75

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
        # tech_stack normalized weight = 0.35
        # (100*0.35 + 50*0.10) / (0.35+0.10) = 40/0.45 = 88.89 -> 89
        assert result == 89

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

        assert calculate_score(stated) == 56
        assert calculate_score(padded) == 60
        assert calculate_score(padded) - calculate_score(stated) == 4

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
