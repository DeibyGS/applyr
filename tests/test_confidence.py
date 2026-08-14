"""Tests for per-topic confidence + required-evidence warning (specs/scoring-confidence)."""

import json

import pytest

from applyr.commands._helpers import _derive_confidence
from applyr.commands.core import cmd_add, cmd_show


def _add(**fields):
    cmd_add(json.dumps({"title": "Backend Dev", **fields}))


@pytest.mark.unit
class TestDeriveConfidence:
    """The weakest per-topic confidence wins; missing entirely means "unknown",
    never a fabricated "medium"."""

    def test_all_high_is_high(self):
        topics = [{"confidence": "high"}, {"confidence": "high"}]
        assert _derive_confidence(topics) == "high"

    def test_one_low_drags_down_the_rest(self):
        topics = [{"confidence": "high"}, {"confidence": "low"}, {"confidence": "high"}]
        assert _derive_confidence(topics) == "low"

    def test_medium_beats_high_but_loses_to_low(self):
        topics = [{"confidence": "high"}, {"confidence": "medium"}]
        assert _derive_confidence(topics) == "medium"

    def test_no_topics_provided_confidence_is_unknown(self):
        topics = [{"score": 80}, {"score": 40, "confidence": None}]
        assert _derive_confidence(topics) == "unknown"

    def test_empty_list_is_unknown(self):
        assert _derive_confidence([]) == "unknown"

    def test_mixed_missing_and_present_ignores_missing(self):
        topics = [{"confidence": "high"}, {"score": 50}]  # second has no confidence key
        assert _derive_confidence(topics) == "high"


class TestConfidenceValidation:
    """Invalid confidence values reject the whole `add` (same pattern as
    salary_period); a missing `detail` only warns, never blocks — must not
    break agents that don't send it yet."""

    def test_invalid_confidence_dies(self, tmp_db, tmp_applyr):
        with pytest.raises(SystemExit):
            _add(topics={"tech_stack": {"score": 80, "detail": "x", "confidence": "very high"}})

    def test_invalid_confidence_rolls_back_the_whole_offer(self, tmp_db, tmp_applyr):
        from applyr.db import get_conn

        with pytest.raises(SystemExit):
            _add(topics={"tech_stack": {"score": 80, "detail": "x", "confidence": "nope"}})

        conn = get_conn()
        try:
            count = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
        finally:
            conn.close()
        assert count == 0

    def test_valid_confidence_is_accepted(self, tmp_db, tmp_applyr):
        _add(topics={"tech_stack": {"score": 80, "detail": "x", "confidence": "medium"}})
        from applyr.db import get_conn

        conn = get_conn()
        try:
            row = conn.execute("SELECT confidence FROM offer_topics WHERE offer_id = 1").fetchone()
        finally:
            conn.close()
        assert row["confidence"] == "medium"

    def test_missing_confidence_is_stored_as_null_not_a_default(self, tmp_db, tmp_applyr):
        _add(topics={"tech_stack": {"score": 80, "detail": "x"}})
        from applyr.db import get_conn

        conn = get_conn()
        try:
            row = conn.execute("SELECT confidence FROM offer_topics WHERE offer_id = 1").fetchone()
        finally:
            conn.close()
        assert row["confidence"] is None

    def test_missing_detail_warns_but_does_not_die(self, tmp_db, tmp_applyr, capsys):
        _add(topics={"tech_stack": {"score": 80, "confidence": "high"}})  # no detail
        captured = capsys.readouterr()
        assert "no 'detail'" in captured.err  # warn() goes to stderr, not stdout
        assert "Offer added successfully" in captured.out  # reached confirmation, so it never died


class TestAddAndShowSurfaceConfidence:
    """`add` and `show` must agree on what confidence data exists — same
    shape, same derivation function, so they can't disagree with each other."""

    def test_add_prints_per_topic_and_derived_confidence(self, tmp_db, tmp_applyr, capsys):
        _add(topics={
            "tech_stack": {"score": 85, "detail": "x", "confidence": "high"},
            "experience": {"score": 60, "detail": "y", "confidence": "low"},
        })
        out = capsys.readouterr().out
        assert "high confidence" in out
        assert "low confidence" in out
        assert "CONFIDENCE: LOW" in out  # derived: weakest wins

    def test_show_json_includes_derived_confidence(self, tmp_db, tmp_applyr, capsys):
        _add(topics={"tech_stack": {"score": 85, "detail": "x", "confidence": "high"}})
        capsys.readouterr()
        cmd_show(1, as_json=True)
        data = json.loads(capsys.readouterr().out)
        assert data["confidence"] == "high"
        assert data["topics"][0]["confidence"] == "high"

    def test_show_json_confidence_is_unknown_when_never_provided(self, tmp_db, tmp_applyr, capsys):
        _add(topics={"tech_stack": {"score": 85, "detail": "x"}})
        capsys.readouterr()
        cmd_show(1, as_json=True)
        data = json.loads(capsys.readouterr().out)
        assert data["confidence"] == "unknown"
        assert data["topics"][0]["confidence"] is None
