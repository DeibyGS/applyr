"""`cv generate` refuses to run without a valid Step 5.7 plan (ADR-018).

The barrier exists because the plan is the only place "what this CV must NOT
say" is written down: skipping it produced a CV whose profile claimed RAG as
professional experience while every keyword check passed.
"""

import json

import pytest

import applyr.cv as cv_mod
from applyr.gates import plan_path_for


@pytest.fixture
def offer(tmp_db, tmp_applyr):
    """A scored offer with a fillable cv-master and no Step 5.7 plan."""
    from applyr.commands.core import cmd_add

    (tmp_applyr / "cv-master.md").write_text(
        "# CV Master\n\n## Summary\n" + "Fullstack developer. " * 20
    )
    cmd_add(json.dumps({
        "title": "Full Stack (JS)",
        "company": "Fusuma",
        "tech_stack": "Python",
        "topics": {"experience": {"score": 20, "detail": "no professional experience"}},
    }))
    return 1


def _error(capsys, fn):
    """Run a command expected to die() and return its structured JSON error."""
    from applyr.errors import set_json_mode

    set_json_mode(True)
    try:
        with pytest.raises(SystemExit) as exc:
            fn()
    finally:
        set_json_mode(False)
    assert exc.value.code == 1
    return json.loads(capsys.readouterr().err.strip().splitlines()[-1])["error"]


def _cv_files(tmp_applyr):
    """Generated CVs — `cv-*-plan.md` files live in the same directory."""
    return sorted(p for p in (tmp_applyr / "cv").glob("cv-*.md")
                  if not p.name.endswith("-plan.md"))


def _notes(offer_id):
    from applyr.db import get_conn

    conn = get_conn()
    try:
        return conn.execute("SELECT notes FROM offers WHERE id = ?",
                            (offer_id,)).fetchone()["notes"]
    finally:
        conn.close()


class TestGenerationGate:
    def test_no_plan_refuses_and_writes_nothing(self, offer, tmp_applyr, capsys):
        err = _error(capsys, lambda: cv_mod.cmd_cv_generate(offer))
        assert err["code"] == "plan_required"
        assert err["details"]["offer_id"] == offer
        assert err["details"]["state"] == "missing"
        assert err["details"]["plan_path"] == str(plan_path_for("Fusuma"))
        assert not _cv_files(tmp_applyr)

    def test_refusal_tells_the_agent_which_command_fixes_it(self, offer, capsys):
        """A code without a next command is a dead end for an agent."""
        with pytest.raises(SystemExit):
            cv_mod.cmd_cv_generate(offer)
        assert "applyr role architect" in capsys.readouterr().err

    def test_valid_plan_generates(self, offer, tmp_applyr, write_plan):
        write_plan("Fusuma", offer)
        cv_mod.cmd_cv_generate(offer)
        assert len(_cv_files(tmp_applyr)) == 1

    def test_plan_without_forbidden_claims_is_invalid(self, offer, tmp_applyr, capsys, write_plan):
        write_plan("Fusuma", offer, claims=())
        err = _error(capsys, lambda: cv_mod.cmd_cv_generate(offer))
        assert err["code"] == "plan_invalid"
        assert err["details"]["state"] == "empty"
        assert not _cv_files(tmp_applyr)

    def test_plan_for_another_offer_is_invalid(self, offer, tmp_applyr, capsys, write_plan):
        write_plan("Fusuma", 99)
        err = _error(capsys, lambda: cv_mod.cmd_cv_generate(offer))
        assert err["code"] == "plan_invalid"
        assert err["details"]["state"] == "wrong_offer"
        assert not _cv_files(tmp_applyr)


class TestForceBypass:
    def test_force_generates_without_a_plan(self, offer, tmp_applyr, capsys):
        cv_mod.cmd_cv_generate(offer, force=True)
        assert len(_cv_files(tmp_applyr)) == 1
        assert "--force" in capsys.readouterr().err

    def test_force_records_the_bypass_on_the_offer(self, offer):
        """"This CV shipped without a plan" must stay auditable (AC-04)."""
        cv_mod.cmd_cv_generate(offer, force=True)
        assert "cv generate --force: plan skipped (missing)" in _notes(offer)

    def test_force_with_a_valid_plan_writes_no_bypass_note(self, offer, write_plan):
        """The note records a gate being skipped, not a routine overwrite."""
        write_plan("Fusuma", offer)
        cv_mod.cmd_cv_generate(offer, force=True)
        notes = _notes(offer) or ""
        assert "plan skipped" not in notes


class TestRetroCompatibility:
    def test_offer_with_a_cv_never_has_to_plan_retroactively(self, offer, tmp_applyr, write_plan):
        """AC-05: the gate stops the next first pass, not past ones."""
        write_plan("Fusuma", offer)
        cv_mod.cmd_cv_generate(offer)
        plan_path_for("Fusuma").unlink()
        _cv_files(tmp_applyr)[0].unlink()  # cv_used still records the CV

        cv_mod.cmd_cv_generate(offer)  # must not raise
        assert len(_cv_files(tmp_applyr)) == 1


# --- `cv gate`: the checklist, not the barrier (T6-T9) -------------------------

def _gate_json(capsys, run_cli, offer_id):
    """Run `cv gate <id> --json` and return (payload, error, exit_code)."""
    code = 0
    try:
        run_cli(["cv", "gate", str(offer_id), "--json"])
    except SystemExit as exc:
        code = exc.code or 1
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else None
    err = (json.loads(captured.err.strip().splitlines()[-1])["error"]
           if captured.err.strip() else None)
    return payload, err, code


def _statuses(payload):
    return {s["step"]: s["status"] for s in payload["steps"]}


class TestCvGate:
    def test_unknown_offer_reports_not_found(self, tmp_db, capsys, run_cli):
        """AC-E3: same contract as every other cv subcommand."""
        payload, err, code = _gate_json(capsys, run_cli, 999)
        assert payload is None and code == 1
        assert err["code"] == "not_found"

    def test_offer_without_a_plan_reports_every_later_step_pending(
            self, offer, capsys, run_cli):
        """AC-E4: a blocked pipeline reads as pending, never as a crash."""
        payload, err, code = _gate_json(capsys, run_cli, offer)
        assert code == 1
        assert err["code"] == "gates_incomplete"
        assert set(payload) == {"offer_id", "ok", "state", "missing", "steps"}
        assert payload["ok"] is False
        assert _statuses(payload) == {
            "score": "ok",
            "decide": "missing",
            "plan": "missing",
            "generate": "pending",
            "cv_review": "pending",
            "verify": "pending",
            "pdf": "pending",
            "apply": "pending",
        }
        assert payload["missing"] == ["decide", "plan"]
        assert payload["state"] == "decide"

    def test_plan_and_a_recorded_review_clear_the_gate(
            self, offer, capsys, run_cli, write_plan):
        from applyr.cv import cmd_cv_review_blind

        cmd_cv_review_blind(offer, record="74")
        capsys.readouterr()
        write_plan("Fusuma", offer)

        payload, err, code = _gate_json(capsys, run_cli, offer)
        assert code == 0 and err is None
        assert payload["ok"] is True
        assert payload["missing"] == []
        assert payload["state"] == "generate"

    def test_plan_for_another_offer_is_reported_invalid(
            self, offer, capsys, run_cli, write_plan):
        write_plan("Fusuma", 99)

        payload, err, code = _gate_json(capsys, run_cli, offer)
        assert code == 1
        assert err["code"] == "gates_incomplete"
        assert _statuses(payload)["plan"] == "invalid"
        assert payload["missing"] == ["decide", "plan"]

    def test_the_plan_step_disappears_once_a_cv_exists(
            self, offer, capsys, run_cli, write_plan):
        """AC-05: an offer that already generated a CV is never stranded at plan."""
        from applyr.cv import cmd_cv_generate, cmd_cv_review_blind

        cmd_cv_review_blind(offer, record="74")
        write_plan("Fusuma", offer)
        cmd_cv_generate(offer)
        capsys.readouterr()

        payload, err, code = _gate_json(capsys, run_cli, offer)
        statuses = _statuses(payload)
        assert code == 1
        assert statuses["plan"] == "not_applicable"
        assert payload["state"] == "cv_review"
        assert statuses["cv_review"] == "missing"

    def test_human_report_names_the_artifacts_and_their_fix(
            self, offer, capsys, run_cli):
        with pytest.raises(SystemExit) as exc:
            run_cli(["cv", "gate", str(offer)])
        out = capsys.readouterr().out
        assert exc.value.code == 1
        assert "Fusuma" in out
        assert "MISSING" in out
        assert "applyr role architect" in out
        assert "applyr cv review-blind" in out
        assert "required artifact(s) missing" in out

    def test_gate_is_read_only(self, offer, tmp_db, capsys, run_cli):
        """The checklist is diagnostic — it must never touch the database."""
        before = open(tmp_db, "rb").read()
        _gate_json(capsys, run_cli, offer)
        assert open(tmp_db, "rb").read() == before
