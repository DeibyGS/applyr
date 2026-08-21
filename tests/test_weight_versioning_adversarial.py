"""Adversarial verification for weight-versioning-rebalance
(specs/weight-versioning-rebalance/spec.md).

Independent hostile tests derived from the spec's acceptance criteria, not
from reading the implementation first. See Phase 1/2 in the verifying agent's
report for the contract table and attack hypotheses this file executes.
"""

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


# ---------------------------------------------------------------------------
# H1 — migration backfill (WONT: no backfill, existing rows stay NULL)
# ---------------------------------------------------------------------------

class TestMigrationNoBackfill:
    def test_v8_to_v9_migration_does_not_backfill_existing_rows(self, tmp_applyr):
        """Simulate a real v8 database (no weights_used column), insert rows,
        then run init_db() to trigger the (8, 9) migration. Existing rows
        must read back weights_used = NULL, never a guessed/derived value.
        """
        db_path = str(tmp_applyr / "jobs.db")
        conn = sqlite3.connect(db_path)
        # Full pre-v10 column set: the (9, 10) migration rebuilds this table
        # with an explicit SELECT of every column, so a stripped-down proxy
        # table (as this test used before schema v10 existed) would fail with
        # "no such column" partway through the chained 8 -> 9 -> 10 migration.
        conn.execute(
            """CREATE TABLE offers (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                title             TEXT    NOT NULL,
                company           TEXT,
                summary           TEXT,
                date_received     TEXT,
                date_applied      TEXT,
                date_responded    TEXT,
                compatibility_pct INTEGER DEFAULT 0,
                status            TEXT    DEFAULT 'pending',
                applied           INTEGER DEFAULT 0,
                canal             TEXT,
                cv_used           TEXT,
                follow_up_date    TEXT,
                follow_up_done    INTEGER DEFAULT 0,
                follow_up_notes   TEXT,
                work_mode         TEXT,
                location          TEXT,
                salary_min        INTEGER,
                salary_max        INTEGER,
                salary_period     TEXT    DEFAULT 'annual',
                seniority_level   TEXT,
                role_category     TEXT,
                tech_stack        TEXT,
                language          TEXT,
                cover_letter      INTEGER DEFAULT 0,
                cover_letter_file TEXT,
                contact_name      TEXT,
                contact_role      TEXT,
                job_url           TEXT,
                rejection_reason  TEXT,
                response_status   TEXT    DEFAULT 'no_response',
                notes             TEXT,
                created_at        TEXT    DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (8)")
        conn.execute(
            "INSERT INTO offers (title, company, compatibility_pct, status) VALUES (?, ?, ?, ?)",
            ("Pre-v9 offer", "Acme", 77, "applied"),
        )
        conn.commit()
        conn.close()

        from applyr.db import init_db, SCHEMA_VERSION
        init_db(db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        version = conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        row = conn.execute("SELECT * FROM offers WHERE title = 'Pre-v9 offer'").fetchone()
        conn.close()

        assert version == SCHEMA_VERSION
        assert "weights_used" in row.keys()
        assert row["weights_used"] is None
        # The pre-existing score itself must be untouched by the migration.
        assert row["compatibility_pct"] == 77


class TestFreshInstallSchema:
    def test_fresh_db_has_weights_used_column_at_v9(self, tmp_db, tmp_applyr):
        conn = sqlite3.connect(tmp_db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(offers)").fetchall()}
        version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
        conn.close()
        from applyr.db import SCHEMA_VERSION
        assert "weights_used" in cols
        assert version == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# H2 — weights_used must reflect merged effective config, not the global
# DEFAULT_WEIGHTS constant
# ---------------------------------------------------------------------------

class TestAddCapturesEffectiveConfig:
    def test_weights_used_reflects_custom_toml_not_default_constant(self, tmp_db, tmp_applyr):
        from applyr.constants import DEFAULT_WEIGHTS

        toml_path = tmp_applyr / "applyr.toml"
        toml_path.write_text(
            "[weights]\ntech_stack = 60\nexperience = 20\nprojects = 10\n"
            "education = 5\nenglish = 3\ncultural_fit = 2\n"
        )

        _add(topics={"tech_stack": {"score": 80, "detail": "x"}})

        row = _row(tmp_applyr, 1)
        assert row["weights_used"] is not None
        stored = json.loads(row["weights_used"])
        assert stored == {
            "tech_stack": 60, "experience": 20, "projects": 10,
            "education": 5, "english": 3, "cultural_fit": 2,
        }
        # Must NOT be the untouched global default — proves it reads the
        # merged config, not the constant.
        assert stored != DEFAULT_WEIGHTS

    def test_weights_used_stores_raw_integers_not_normalized_fractions(self, tmp_db, tmp_applyr):
        _add(topics={"tech_stack": {"score": 80, "detail": "x"}})
        row = _row(tmp_applyr, 1)
        stored = json.loads(row["weights_used"])
        # Raw TOML-style integers summing to 100, never fractions like 0.35.
        assert all(isinstance(v, int) for v in stored.values())
        assert sum(stored.values()) == 100


class TestAddBranches:
    def test_explicit_override_stores_null_weights_used(self, tmp_db, tmp_applyr):
        _add(compatibility_pct=42, topics={"tech_stack": {"score": 80, "detail": "x"}})
        row = _row(tmp_applyr, 1)
        assert row["compatibility_pct"] == 42
        assert row["weights_used"] is None

    def test_empty_topics_branch_stores_null_weights_used_and_zero_score(self, tmp_db, tmp_applyr):
        _add()  # no topics, no override
        row = _row(tmp_applyr, 1)
        assert row["compatibility_pct"] == 0
        assert row["weights_used"] is None


# ---------------------------------------------------------------------------
# H4 — rescore must reuse offer_topics unchanged, never re-evaluate fit
# ---------------------------------------------------------------------------

class TestRescoreNeverReevaluatesTopics:
    def test_offer_topics_rows_byte_identical_after_rescore(self, tmp_db, tmp_applyr):
        from applyr.commands.analytics import cmd_rescore

        _add(topics={
            "tech_stack": {"score": 80, "detail": "Knows Python", "confidence": "high"},
            "education": {"score": 40, "detail": "Related field", "confidence": "medium"},
        })

        conn = sqlite3.connect(tmp_applyr / "jobs.db")
        conn.row_factory = sqlite3.Row
        before = [dict(r) for r in conn.execute(
            "SELECT topic, score, detail, confidence FROM offer_topics WHERE offer_id = 1 ORDER BY topic"
        ).fetchall()]
        conn.close()

        toml_path = tmp_applyr / "applyr.toml"
        toml_path.write_text(
            "[weights]\ntech_stack = 90\neducation = 10\nexperience = 0\n"
            "projects = 0\nenglish = 0\ncultural_fit = 0\n"
        )
        cmd_rescore(1)

        conn = sqlite3.connect(tmp_applyr / "jobs.db")
        conn.row_factory = sqlite3.Row
        after = [dict(r) for r in conn.execute(
            "SELECT topic, score, detail, confidence FROM offer_topics WHERE offer_id = 1 ORDER BY topic"
        ).fetchall()]
        conn.close()

        assert before == after


# ---------------------------------------------------------------------------
# H8 — stats/summary aggregation must exclude weights_used IS NULL
# consistently, including overall/weekly averages (the "added after initial
# spec" rule, not just _score_calibration's bands).
# ---------------------------------------------------------------------------

class TestStatsExcludeUnknownWeights:
    def test_overall_avg_compatibility_excludes_null_weight_offers(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_stats

        # Known-weights offer: score 80.
        _add(title="Known Weights Offer", company="Acme", topics={"tech_stack": {"score": 80, "detail": "x"}})
        # Unknown-weights offer (explicit override): score 0, would drag the
        # average down to 40 if wrongly included. Different company so the
        # near-duplicate title check doesn't collide the two offers.
        _add(title="Unknown Weights Offer", company="Globex", compatibility_pct=0)

        capsys.readouterr()
        cmd_stats(as_json=True)
        payload = json.loads(capsys.readouterr().out)

        assert payload["avg_compatibility_pct"] == 80.0
        assert payload["avg_compatibility_pct_excluded_unknown_weights"] == 1

    def test_score_calibration_excludes_null_weight_offers_from_bands(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.analytics import cmd_stats

        # Known-weights offer scored high enough for the "apply" band, with a
        # status that counts toward calibration ("applied", not pending).
        _add(title="Known Weights Offer", company="Acme", topics={"tech_stack": {"score": 95, "detail": "x"}}, status="applied")
        # Unknown-weights offer, also "applied" status, also high score —
        # must be excluded from the apply band's "total". Different company
        # so the near-duplicate title check doesn't collide the two offers.
        _add(title="Unknown Weights Offer", company="Globex", compatibility_pct=95, status="applied")

        capsys.readouterr()
        cmd_stats(as_json=True)
        payload = json.loads(capsys.readouterr().out)

        assert payload["score_calibration"]["apply"]["total"] == 1
        assert payload["excluded_unknown_weights"] == 1


# ---------------------------------------------------------------------------
# H9 — JSON double-encoding on show
# ---------------------------------------------------------------------------

class TestShowJsonNotDoubleEncoded:
    def test_weights_used_is_parsed_object_not_string(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_show

        _add(topics={"tech_stack": {"score": 80, "detail": "x"}})

        capsys.readouterr()
        cmd_show(1, as_json=True)
        payload = json.loads(capsys.readouterr().out)

        assert isinstance(payload["weights_used"], dict)
        assert not isinstance(payload["weights_used"], str)

    def test_weights_used_is_null_not_string_null_when_unknown(self, tmp_db, tmp_applyr, capsys):
        from applyr.commands.core import cmd_show

        _add(compatibility_pct=50)  # override branch -> NULL

        capsys.readouterr()
        cmd_show(1, as_json=True)
        payload = json.loads(capsys.readouterr().out)

        assert payload["weights_used"] is None


# ---------------------------------------------------------------------------
# `add`'s --json contract: spec requires weights_used to surface as a new
# top-level key in `add`'s --json output without disturbing existing keys.
# cmd_add's actual signature is `cmd_add(raw: str, force: bool = False)` —
# no as_json parameter exists, and cli.py's `add` dispatch
# (`cmd_add(raw, force=force)`) never forwards the global --json flag to it.
# This test proves the AC is unmet, whether or not it predates this PR.
# ---------------------------------------------------------------------------

class TestAddJsonContractGap:
    """BUG-001 (adversarial-test, 2026-08-15): `add --json` never had a JSON
    output path — confirmed missing at the time this test was written. Fixed
    same PR, same day, per project-owner triage. See
    tests/test_cli_routing.py::TestGlobalFlags::test_json_flag_add for the
    coverage of the fix itself; this test now guards the regression."""

    def test_add_honors_json_flag(self, tmp_db, tmp_applyr, capsys, monkeypatch):
        import sys
        import applyr.commands.core as core_mod
        monkeypatch.setattr(core_mod, "APPLYR_DIR", tmp_applyr)

        capsys.readouterr()
        monkeypatch.setattr(
            sys, "argv",
            ["applyr", "add", json.dumps({"title": "X", "company": "Acme", "topics": {"tech_stack": {"score": 80, "detail": "d"}}}), "--json"],
        )
        from applyr.cli import main
        main()

        out = capsys.readouterr().out
        data = json.loads(out)
        assert "weights_used" in data
        assert data["weights_used"]["tech_stack"] == 35
