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


class TestUpdateCvUsed:
    """`--cv ""` is the only way to unlink a CV from an offer. It must land as
    NULL, so "never had a CV" and "CV unlinked" are one value for cv stats."""

    def test_sets_cv_used(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied", cv="cv-acme.html")
        assert _row(tmp_applyr, 1)["cv_used"] == "cv-acme.html"

    def test_empty_value_clears_to_null(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied", cv="cv-acme.html")
        cmd_update(1, "applied", cv="")
        assert _row(tmp_applyr, 1)["cv_used"] is None

    def test_whitespace_only_value_clears_to_null(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied", cv="cv-acme.html")
        cmd_update(1, "applied", cv="   ")
        assert _row(tmp_applyr, 1)["cv_used"] is None

    def test_omitting_the_flag_leaves_it_untouched(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied", cv="cv-acme.html")
        cmd_update(1, "waiting")
        assert _row(tmp_applyr, 1)["cv_used"] == "cv-acme.html"


class TestLiveSkillGaps:
    """skill_gaps is derived from offer_topics, not the (now-dropped) table."""

    def test_reflects_only_current_offers(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import _live_skill_gaps
        from applyr.commands.core import cmd_delete

        _add(company="Acme", topics={"experience": {"score": 10, "detail": "x"}})
        assert _live_skill_gaps()[0]["frequency"] == 1

        cmd_delete(1, force=True)
        assert _live_skill_gaps() == []

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


class TestUpdateSetsAppliedFlag:
    """`response_rate` filters on `applied = 1`, but nothing ever wrote that
    column — so the command reported no applications no matter what the user
    had done. The flag is derived from the status on every update."""

    @pytest.mark.parametrize("status", ["applied", "waiting", "in_process", "rejected", "offer"])
    def test_sent_statuses_set_the_flag(self, tmp_db, tmp_applyr, status):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, status)
        assert _row(tmp_applyr, 1)["applied"] == 1

    @pytest.mark.parametrize("status", ["pending", "discarded"])
    def test_unsent_statuses_clear_the_flag(self, tmp_db, tmp_applyr, status):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, status)
        assert _row(tmp_applyr, 1)["applied"] == 0

    def test_moving_back_clears_a_stale_flag(self, tmp_db, tmp_applyr):
        """An offer applied to and then dropped must not keep counting as sent."""
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied")
        cmd_update(1, "discarded")
        assert _row(tmp_applyr, 1)["applied"] == 0


class TestUpdateRecordsResponseStatus:
    """`response_status` had no writer at all, so every application counted as
    unanswered even after a rejection or an offer."""

    @pytest.mark.parametrize("status", ["in_process", "rejected", "offer"])
    def test_reply_statuses_record_the_response(self, tmp_db, tmp_applyr, status):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, status)
        assert _row(tmp_applyr, 1)["response_status"] == status

    @pytest.mark.parametrize("status", ["applied", "waiting"])
    def test_sent_but_unanswered_stays_no_response(self, tmp_db, tmp_applyr, status):
        """`waiting` means the reply has not arrived — it is not a response."""
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, status)
        assert _row(tmp_applyr, 1)["response_status"] == "no_response"

    def test_response_rate_counts_a_real_reply(self, tmp_db, tmp_applyr):
        """End to end: the two columns together make the metric work."""
        from applyr.commands.core import cmd_update
        from applyr.analytics import response_rate

        _add(company="Acme")
        _add(company="Globex")
        cmd_update(1, "applied")
        cmd_update(2, "rejected")

        result = response_rate(as_json=True)
        assert result["total_applications"] == 2
        assert result["responded"] == 1
        assert result["response_rate"] == 50.0
