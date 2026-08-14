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


class TestRespondedMeansTheSameEverywhere:
    """`stats` counted `waiting` as a reply and `response-rate` did not, so the
    two commands reported different response rates from one database — 14%
    against 9% on a real 206-offer history."""

    def _stats(self, capsys):
        from applyr.commands.analytics import cmd_stats

        capsys.readouterr()  # drop whatever add/update printed first
        cmd_stats(as_json=True)
        return json.loads(capsys.readouterr().out)

    def test_waiting_is_not_a_response(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "waiting")
        assert self._stats(capsys)["funnel"]["responded"] == 0

    def test_a_rejection_is_a_response(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "rejected")
        assert self._stats(capsys)["funnel"]["responded"] == 1

    def test_both_commands_agree(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_update
        from applyr.analytics import response_rate

        for company, status in [("A", "applied"), ("B", "waiting"),
                                ("C", "rejected"), ("D", "in_process")]:
            _add(company=company)
        for offer_id, status in enumerate(["applied", "waiting", "rejected", "in_process"], start=1):
            cmd_update(offer_id, status)

        funnel = self._stats(capsys)["funnel"]
        rate = response_rate(as_json=True)
        assert funnel["responded"] == rate["responded"] == 2
        assert funnel["applied"] == rate["total_applications"] == 4

    def test_cv_stats_uses_the_same_definition(self):
        from applyr.cv_stats import RESPONDED_STATUSES
        from applyr.db import REPLY_STATUSES

        assert "waiting" not in RESPONDED_STATUSES
        assert RESPONDED_STATUSES == REPLY_STATUSES


class TestScoreCalibration:
    """`stats` buckets applied offers by score band (threshold_apply/
    threshold_maybe from config) and reports real outcome rates per band —
    the same bands `add`'s recommendation uses, so calibration can't
    disagree with it about what counts as APPLY/MAYBE/LOW MATCH."""

    def _stats(self, capsys):
        from applyr.commands.analytics import cmd_stats

        capsys.readouterr()
        cmd_stats(as_json=True)
        return json.loads(capsys.readouterr().out)

    def test_bands_match_add_recommendation_thresholds(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_update

        _add(company="A", topics={"tech_stack": {"score": 85, "detail": "x"}})  # apply band
        _add(company="B", topics={"tech_stack": {"score": 70, "detail": "x"}})  # maybe band
        _add(company="C", topics={"tech_stack": {"score": 40, "detail": "x"}})  # low_match band
        for offer_id, status in enumerate(["rejected", "waiting", "applied"], start=1):
            cmd_update(offer_id, status)

        calibration = self._stats(capsys)["score_calibration"]
        assert calibration["apply"]["total"] == 1
        assert calibration["apply"]["responded"] == 1
        assert calibration["maybe"]["total"] == 1
        assert calibration["maybe"]["responded"] == 0  # waiting is not a response
        assert calibration["low_match"]["total"] == 1

    def test_pending_offers_are_excluded(self, tmp_db, tmp_applyr, capsys):
        # never applied — status stays "pending", so it isn't an "outcome" yet
        _add(company="A", topics={"tech_stack": {"score": 90, "detail": "x"}})

        calibration = self._stats(capsys)["score_calibration"]
        assert calibration["apply"]["total"] == 0

    def test_json_reports_raw_count_below_minimum_sample(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_update
        from applyr.constants import CALIBRATION_MIN_SAMPLE

        _add(company="A", topics={"tech_stack": {"score": 90, "detail": "x"}})
        cmd_update(1, "applied")

        calibration = self._stats(capsys)["score_calibration"]
        # The "not enough data" framing is a human-output guard only — JSON
        # always exposes the raw count so an agent can apply its own floor.
        assert calibration["apply"]["total"] == 1
        assert calibration["apply"]["total"] < CALIBRATION_MIN_SAMPLE


class TestGapPriorityScalesWithTheDatabase:
    """Priority keyed off a fixed recurrence count (>= 3 == HIGH) marked every
    topic HIGH once the database held a few hundred offers — exactly when the
    ranking is worth reading."""

    def test_the_worst_gap_is_high(self):
        from applyr.commands.analytics import _gap_priority

        assert _gap_priority(4320, 4320) == "HIGH"

    def test_a_third_of_the_worst_is_medium(self):
        from applyr.commands.analytics import _gap_priority

        assert _gap_priority(1500, 4320) == "MEDIUM"

    def test_a_tenth_of_the_worst_is_low(self):
        from applyr.commands.analytics import _gap_priority

        assert _gap_priority(420, 4320) == "LOW"

    def test_magnitude_counts_not_only_sightings(self):
        """Two topics seen equally often rank apart when one falls further short."""
        from applyr.commands.analytics import _gap_priority

        deep, shallow = 1000, 150
        assert _gap_priority(deep, deep) == "HIGH"
        assert _gap_priority(shallow, deep) == "LOW"

    def test_priority_is_unchanged_by_database_size(self):
        """The same relative shape must rank the same at any scale."""
        from applyr.commands.analytics import _gap_priority

        small = [_gap_priority(g, 100) for g in (100, 30, 5)]
        large = [_gap_priority(g, 100_000) for g in (100_000, 30_000, 5_000)]
        assert small == large == ["HIGH", "MEDIUM", "LOW"]

    def test_no_gaps_at_all_does_not_divide_by_zero(self):
        from applyr.commands.analytics import _gap_priority

        assert _gap_priority(0, 0) == "LOW"


class TestPlanAndGapsAgree:
    """`plan` scored priority against absolute thresholds (200/100/40) while
    `gaps` scored it relative to the worst gap. On a real 207-offer database
    every topic cleared 200 — the weakest already scored 415 — so `plan` called
    all six CRITICAL while `gaps` spread them across HIGH/MEDIUM/LOW. Two
    commands, one dataset, contradictory answers."""

    def _seed(self):
        """Offers whose gaps differ enough to separate into distinct bands."""
        for i in range(12):
            _add(company=f"Deep{i}", topics={"tech_stack": {"score": 10, "detail": "x"}})
        for i in range(4):
            _add(company=f"Mid{i}", topics={"english": {"score": 40, "detail": "x"}})
        _add(company="Shallow", topics={"education": {"score": 60, "detail": "x"}})

    def _priorities(self, capsys, fn):
        capsys.readouterr()
        fn(as_json=True)
        return {row["skill"]: row["priority"] for row in json.loads(capsys.readouterr().out)}

    def test_both_commands_report_the_same_priority(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_gaps, cmd_plan

        self._seed()
        assert self._priorities(capsys, cmd_plan) == self._priorities(capsys, cmd_gaps)

    def test_priority_still_discriminates(self, tmp_db, tmp_applyr, capsys):
        """The regression: every topic landing in one band tells the user nothing."""
        from applyr.commands.analytics import cmd_plan

        self._seed()
        priorities = self._priorities(capsys, cmd_plan)
        assert len(set(priorities.values())) > 1, f"all topics in one band: {priorities}"

    def test_plan_orders_by_impact_not_frequency(self, tmp_db, tmp_applyr, capsys):
        """A topic seen less often but missed by more must outrank the other."""
        from applyr.commands.analytics import cmd_plan

        for i in range(3):
            _add(company=f"Deep{i}", topics={"tech_stack": {"score": 0, "detail": "x"}})
        for i in range(8):
            _add(company=f"Shallow{i}", topics={"english": {"score": 60, "detail": "x"}})

        capsys.readouterr()
        cmd_plan(as_json=True)
        ranked = [row["skill"] for row in json.loads(capsys.readouterr().out)]
        assert ranked[0] == "tech_stack", "3 offers missing 65 pts each beats 8 missing 5"


class TestExportStaysInsideApplyrHome:
    """`export` wrote the whole database — every company, score and private
    note — into the current working directory. Run from any checkout that
    dropped an untracked file full of personal data one `git add .` away from
    being published. Everything else applyr owns lives in APPLYR_DIR."""

    def test_default_path_is_applyr_home(self, tmp_db, tmp_applyr, monkeypatch, tmp_path):
        from applyr.commands import workflow

        monkeypatch.setattr(workflow, "APPLYR_DIR", tmp_applyr)
        elsewhere = tmp_path / "some-repo"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        _add(company="Acme")
        workflow.cmd_export(fmt="json")

        assert (tmp_applyr / "applyr_export.json").exists()
        assert not (elsewhere / "applyr_export.json").exists(), "must not write into the cwd"

    def test_an_explicit_path_still_wins(self, tmp_db, tmp_applyr, monkeypatch, tmp_path):
        from applyr.commands import workflow

        monkeypatch.setattr(workflow, "APPLYR_DIR", tmp_applyr)
        target = tmp_path / "chosen.json"

        _add(company="Acme")
        workflow.cmd_export(fmt="json", filepath=str(target))

        assert target.exists()
        assert not (tmp_applyr / "applyr_export.json").exists()


class TestListSortAndLimitValidation:
    """`--status` was validated because an unknown value "reads as 'no offers'
    rather than 'you mistyped it'" — the comment is in the source. Two lines
    below, an unknown `--sort` fell through to the default instead, so
    `--sort score` returned an unsorted list and said nothing. Only raw column
    names worked, and none were documented."""

    def _scores(self, capsys, **kwargs):
        from applyr.commands.core import cmd_list

        capsys.readouterr()
        cmd_list(as_json=True, **kwargs)
        return [o["compatibility_pct"] for o in json.loads(capsys.readouterr().out)]

    def _seed(self):
        for i, score in enumerate((10, 90, 50)):
            _add(company=f"C{i}", topics={"tech_stack": {"score": score, "detail": "x"}})

    def test_score_is_an_accepted_alias(self, tmp_db, tmp_applyr, capsys):
        self._seed()
        assert self._scores(capsys, sort_by="score") == [90, 50, 10]

    def test_the_column_name_still_works(self, tmp_db, tmp_applyr, capsys):
        self._seed()
        assert self._scores(capsys, sort_by="compatibility_pct") == [90, 50, 10]

    def test_an_unknown_sort_field_is_an_error(self, tmp_db, tmp_applyr):
        from applyr.commands.core import cmd_list

        self._seed()
        with pytest.raises(SystemExit) as exc:
            cmd_list(sort_by="scoer")
        assert exc.value.code != 0

    def test_a_negative_limit_is_an_error(self, tmp_db, tmp_applyr):
        """SQLite reads a negative LIMIT as unbounded, so this used to return
        the whole database when the caller asked for -5 rows."""
        from applyr.commands.core import cmd_list

        self._seed()
        with pytest.raises(SystemExit) as exc:
            cmd_list(limit=-5)
        assert exc.value.code != 0

    def test_zero_is_the_no_limit_sentinel_used_by_all(self, tmp_db, tmp_applyr, capsys):
        self._seed()
        assert len(self._scores(capsys, limit=0)) == 3


class TestFollowupsExcludeAnsweredOffers:
    """`follow_up_done` is checked by the followups query but written by
    nothing in applyr — no command exposes it, so it stays 0 forever and never
    excluded a row. A rejection, an offer, or an interview all left the row
    demanding a chase weeks after the question was already answered. On a real
    database, an offer rejected 3 weeks ago still listed as an overdue
    follow-up next to offers that were genuinely still waiting."""

    def _set_followup_date(self, tmp_applyr, offer_id, iso_date):
        conn = sqlite3.connect(tmp_applyr / "jobs.db")
        conn.execute("UPDATE offers SET follow_up_date = ? WHERE id = ?", (iso_date, offer_id))
        conn.commit()
        conn.close()

    def _overdue_ids(self, capsys):
        from applyr.commands.analytics import cmd_followups

        capsys.readouterr()
        cmd_followups(as_json=True)
        payload = json.loads(capsys.readouterr().out)
        return {o["id"] for o in payload["overdue"]}

    @pytest.mark.parametrize("status", ["rejected", "in_process", "offer", "discarded"])
    def test_an_answered_offer_is_not_a_pending_followup(self, tmp_db, tmp_applyr, capsys, status):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, "applied")
        self._set_followup_date(tmp_applyr, 1, "2020-01-01")
        cmd_update(1, status)
        assert 1 not in self._overdue_ids(capsys)

    @pytest.mark.parametrize("status", ["applied", "waiting"])
    def test_a_genuinely_pending_offer_still_shows(self, tmp_db, tmp_applyr, capsys, status):
        from applyr.commands.core import cmd_update

        _add(company="Acme")
        cmd_update(1, status)
        self._set_followup_date(tmp_applyr, 1, "2020-01-01")
        assert 1 in self._overdue_ids(capsys)


class TestFollowupsEmptyJsonPayload:
    """The early return for "nothing pending" printed a plain sentence
    regardless of `as_json` — the exact class of bug already fixed in
    `response_rate`: an agent parsing `followups --json` with nothing due got
    a JSONDecodeError on the one result it most needs to handle cleanly."""

    def test_nothing_pending_is_still_valid_json(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_followups

        cmd_followups(as_json=True)
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"overdue": [], "upcoming": []}

    def test_nothing_pending_says_so_in_human_mode(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_followups

        cmd_followups(as_json=False)
        assert "No pending follow-ups" in capsys.readouterr().out
