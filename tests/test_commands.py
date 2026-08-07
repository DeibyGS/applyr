"""Regression tests for command behaviour found during a full CLI audit."""

import json
import sqlite3

import pytest


def _add(**fields):
    from applyr.commands.core import cmd_add
    cmd_add(json.dumps({"title": "Backend Dev", **fields}))


def _row(tmp_applyr, offer_id):
    conn = sqlite3.connect(tmp_applyr / "jobs.db")
    conn.row_factory = sqlite3.Row
    try:
        return dict(conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone())
    finally:
        conn.close()


class TestUpdateStampsDateApplied:
    """Without date_applied, `summary` counts zero applications, the default
    list sort has nothing to sort on and follow-ups never come due."""

    def test_applied_sets_date_applied(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied")
        assert _row(tmp_applyr, 1)["date_applied"] is not None

    def test_waiting_sets_date_applied(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "waiting")
        assert _row(tmp_applyr, 1)["date_applied"] is not None

    def test_later_transition_keeps_the_original_date(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied")
        first = _row(tmp_applyr, 1)["date_applied"]

        conn = sqlite3.connect(tmp_applyr / "jobs.db")
        conn.execute("UPDATE offers SET date_applied = '2020-01-01' WHERE id = 1")
        conn.commit()
        conn.close()

        cmd_update(1, "waiting")
        assert _row(tmp_applyr, 1)["date_applied"] == "2020-01-01"
        assert first is not None

    def test_pending_does_not_stamp(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "pending")
        assert _row(tmp_applyr, 1)["date_applied"] is None


class TestLiveSkillGaps:
    """skill_gaps is an append-only counter nothing ever decrements, so gaps
    must be derived from the offers that actually exist."""

    def test_reflects_only_current_offers(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import _live_skill_gaps
        from applyr.commands.core import cmd_delete

        _add(company="Acme", topics={"experience": {"score": 10, "detail": "x"}})
        assert _live_skill_gaps()[0]["frequency"] == 1

        cmd_delete(1, force=True)
        assert _live_skill_gaps() == []

    def test_ignores_stale_accumulator_rows(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import _live_skill_gaps

        conn = sqlite3.connect(tmp_applyr / "jobs.db")
        conn.execute(
            "INSERT INTO skill_gaps (skill, frequency, total_gap, last_seen)"
            " VALUES ('fake_topic', 99, 900, '2020-01-01')"
        )
        conn.commit()
        conn.close()

        assert all(g["skill"] != "fake_topic" for g in _live_skill_gaps())

    def test_scores_at_or_above_threshold_are_not_gaps(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import _live_skill_gaps

        _add(company="Acme", topics={"english": {"score": 100, "detail": "fluent"}})
        assert _live_skill_gaps() == []


class TestConfigTemplate:
    def test_has_no_hardcoded_home(self):
        """A literal ~/.applyr would override the APPLYR_HOME-derived default
        and send generated CVs outside an isolated install."""
        from applyr.config import TOML_TEMPLATE

        assert "~/.applyr" not in TOML_TEMPLATE
        assert "__APPLYR_DIR__" in TOML_TEMPLATE

    def test_written_config_points_inside_applyr_home(self, tmp_applyr):
        from applyr.config import create_default_config

        create_default_config()
        written = (tmp_applyr / "applyr.toml").read_text()
        assert str(tmp_applyr) in written
        assert "__APPLYR_DIR__" not in written
