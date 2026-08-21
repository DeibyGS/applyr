"""Tests for `applyr rescore <id>` — recompute compatibility_pct under the
current weights, from already-judged offer_topics, never re-evaluating fit."""

import json
import sqlite3

import pytest


def _add(**fields):
    from applyr.commands.core import cmd_add
    cmd_add(json.dumps({"title": "Backend Dev", "company": "Acme", **fields}))


def _row(tmp_applyr, offer_id):
    conn = sqlite3.connect(tmp_applyr / "jobs.db")
    conn.row_factory = sqlite3.Row
    try:
        return dict(conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone())
    finally:
        conn.close()


class TestRescoreSuccess:
    def test_recomputes_score_and_weights_used_under_new_weights(self, tmp_db, tmp_applyr, monkeypatch):
        from applyr.commands.analytics import cmd_rescore

        _add(topics={"tech_stack": {"score": 80, "detail": "x"},
                      "education": {"score": 40, "detail": "y"}})
        old_pct = _row(tmp_applyr, 1)["compatibility_pct"]

        # Simulate the user changing their applyr.toml before rescoring.
        # _deep_merge fills any topic not listed here from DEFAULT_WEIGHTS,
        # so all six are given explicitly to make the snapshot unambiguous.
        toml_path = tmp_applyr / "applyr.toml"
        toml_path.write_text(
            "[weights]\ntech_stack = 90\neducation = 10\nexperience = 0\n"
            "projects = 0\nenglish = 0\ncultural_fit = 0\n"
        )

        cmd_rescore(1)

        row = _row(tmp_applyr, 1)
        assert row["compatibility_pct"] != old_pct
        weights_used = json.loads(row["weights_used"])
        assert weights_used["tech_stack"] == 90
        assert weights_used["education"] == 10

    def test_no_change_when_recomputed_value_is_identical(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import cmd_rescore

        _add(topics={"tech_stack": {"score": 80, "detail": "x"}})
        old_pct = _row(tmp_applyr, 1)["compatibility_pct"]

        cmd_rescore(1)  # config unchanged since add

        assert _row(tmp_applyr, 1)["compatibility_pct"] == old_pct

    def test_json_output_shape(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_rescore

        _add(topics={"tech_stack": {"score": 80, "detail": "x"}})
        capsys.readouterr()

        cmd_rescore(1, as_json=True)
        payload = json.loads(capsys.readouterr().out)

        assert payload["id"] == 1
        assert "old_compatibility_pct" in payload
        assert "new_compatibility_pct" in payload
        assert isinstance(payload["weights_used"], dict)


class TestRescoreErrors:
    def test_offer_not_found(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import cmd_rescore

        with pytest.raises(SystemExit) as exc:
            cmd_rescore(999)
        assert exc.value.code != 0

    def test_offer_with_no_topics_dies_with_no_topics_code(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_rescore
        from applyr.errors import set_json_mode

        _add()  # no topics at all

        set_json_mode(True)
        try:
            capsys.readouterr()
            with pytest.raises(SystemExit) as exc:
                cmd_rescore(1)
            assert exc.value.code != 0
            err = json.loads(capsys.readouterr().err)
            assert err["error"]["code"] == "no_topics"
        finally:
            set_json_mode(False)
