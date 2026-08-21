"""Adversarial probes for the confidence feature — run against the real project
via pytest with its existing conftest fixtures (tmp_db, tmp_applyr)."""
import json
import pytest


def _add(title="Backend Dev", **fields):
    from applyr.commands.core import cmd_add
    cmd_add(json.dumps({"title": title, "company": "Acme", **fields}))


class TestAtomicityMultiTopic:
    def test_valid_topic_before_invalid_topic_leaves_no_orphaned_rows(self, tmp_db, tmp_applyr):
        """H2: first topic (valid, inserted) + second topic (invalid) dies.
        Contract requires NO partial insert — neither the offers row nor the
        already-executed first offer_topics INSERT may survive."""
        from applyr.db import get_conn
        with pytest.raises(SystemExit):
            _add(topics={
                "tech_stack": {"score": 80, "detail": "ok", "confidence": "high"},
                "experience": {"score": 40, "detail": "bad", "confidence": "extreme"},
            })
        conn = get_conn()
        try:
            offers = conn.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
            topics = conn.execute("SELECT COUNT(*) FROM offer_topics").fetchone()[0]
        finally:
            conn.close()
        assert offers == 0, f"orphaned offers row(s): {offers}"
        assert topics == 0, f"orphaned offer_topics row(s) from the valid topic inserted before the dying one: {topics}"


class TestDetailEmptyString:
    def test_present_but_empty_detail_warns_and_still_inserts(self, tmp_db, tmp_applyr, capsys):
        """Contract: 'detail missing OR empty' must warn, never die, and the
        row must still be inserted — not just the 'key omitted' case."""
        _add(topics={"tech_stack": {"score": 80, "detail": "", "confidence": "high"}})
        captured = capsys.readouterr()
        assert "no 'detail'" in captured.err  # warn() goes to stderr, not stdout
        assert "Offer added successfully" in captured.out
        from applyr.db import get_conn
        conn = get_conn()
        try:
            row = conn.execute("SELECT score, confidence FROM offer_topics WHERE offer_id = 1").fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row["score"] == 80
        assert row["confidence"] == "high"


class TestConfidenceExplicitNull:
    def test_explicit_json_null_confidence_is_treated_as_omitted(self, tmp_db, tmp_applyr):
        """JSON null for confidence must not be treated as an invalid enum
        value (it should behave like omission, not like a bad string)."""
        _add(topics={"tech_stack": {"score": 80, "detail": "x", "confidence": None}})
        from applyr.db import get_conn
        conn = get_conn()
        try:
            row = conn.execute("SELECT confidence FROM offer_topics WHERE offer_id = 1").fetchone()
        finally:
            conn.close()
        assert row["confidence"] is None


class TestConfidenceNeverAffectsScore:
    def test_score_identical_regardless_of_confidence_values(self, tmp_db, tmp_applyr, capsys):
        """MUST: _derive_confidence / confidence must never influence
        compatibility_pct. Same scores, different confidence -> same score."""
        _add(title="Offer A", company="Acme", topics={
            "tech_stack": {"score": 80, "detail": "x", "confidence": "high"},
            "experience": {"score": 40, "detail": "y", "confidence": "high"},
        })
        out1 = capsys.readouterr().out
        import re
        m1 = re.search(r"Compat\.\s*:\s*(\d+)%", out1)

        # Different company than "Offer A" so the near-duplicate title check
        # doesn't collide the two offers.
        _add(title="Offer B", company="Globex", topics={
            "tech_stack": {"score": 80, "detail": "x", "confidence": "low"},
            "experience": {"score": 40, "detail": "y", "confidence": "low"},
        })
        out2 = capsys.readouterr().out
        m2 = re.search(r"Compat\.\s*:\s*(\d+)%", out2)

        assert m1 and m2
        assert m1.group(1) == m2.group(1)


class TestTopLevelConfidenceIgnored:
    def test_top_level_confidence_key_is_silently_ignored(self, tmp_db, tmp_applyr):
        """[WONT]: a top-level 'confidence' key on the add payload (not inside
        topics) must not error and must not leak into stored per-topic data."""
        _add(confidence="high", topics={"tech_stack": {"score": 80, "detail": "x"}})
        from applyr.db import get_conn
        conn = get_conn()
        try:
            row = conn.execute("SELECT confidence FROM offer_topics WHERE offer_id = 1").fetchone()
        finally:
            conn.close()
        assert row["confidence"] is None


class TestShowAfterMigrationNullConfidence:
    def test_show_json_on_pre_migration_row_reads_null_and_unknown(self, tmp_db, tmp_applyr, capsys):
        """A topic row inserted directly (simulating pre-migration / no
        confidence ever recorded) must show confidence None and derive
        'unknown', exercised through cmd_show rather than cmd_add."""
        from applyr.db import get_conn
        from applyr.commands.core import cmd_show
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO offers (title, company, compatibility_pct) VALUES ('Legacy', 'Acme', 50)"
            )
            conn.execute(
                "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (1, 'tech_stack', 50, 'no confidence col written')"
            )
            conn.commit()
        finally:
            conn.close()
        cmd_show(1, as_json=True)
        data = json.loads(capsys.readouterr().out)
        assert data["confidence"] == "unknown"
        assert data["topics"][0]["confidence"] is None


class TestMigrationIdempotency:
    def test_init_db_twice_on_already_v8_db_does_not_crash(self, tmp_db):
        """General data-integrity expectation: init_db() must be safe to call
        repeatedly on a database already at SCHEMA_VERSION without erroring
        or destructively re-applying the ALTER TABLE."""
        from applyr.db import init_db, get_conn, get_schema_version, SCHEMA_VERSION
        init_db(tmp_db)  # tmp_db fixture already ran init_db once
        conn = get_conn(tmp_db)
        try:
            version = get_schema_version(conn)
            cols = [r[1] for r in conn.execute("PRAGMA table_info(offer_topics)").fetchall()]
        finally:
            conn.close()
        assert version == SCHEMA_VERSION
        assert cols.count("confidence") == 1  # not duplicated by a second ADD COLUMN


class TestMigrationFromV7ZeroDataLoss:
    def test_v7_database_with_real_rows_migrates_without_losing_data(self, tmp_path):
        """General data-integrity expectation: a schema-v7 database with
        pre-existing offers/offer_topics rows (no confidence column yet) must
        migrate cleanly to v8 with zero data loss, and existing topic rows
        must read back confidence=NULL (no backfill, no fabricated default)."""
        import sqlite3
        from applyr.db import init_db, get_conn, get_schema_version, SCHEMA_VERSION

        db_path = str(tmp_path / "v7.db")
        conn = sqlite3.connect(db_path)
        # Full pre-v10 column set: the (9, 10) migration rebuilds this table
        # with an explicit SELECT of every column, so a stripped-down proxy
        # table would fail with "no such column" partway through the chained
        # 7 -> 8 -> 9 -> 10 migration.
        conn.executescript("""
            CREATE TABLE offers (
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
            );
            CREATE TABLE offer_topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER REFERENCES offers(id) ON DELETE CASCADE,
                topic TEXT,
                score INTEGER,
                detail TEXT
            );
            CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
        """)
        conn.execute("INSERT INTO offers (title, company, compatibility_pct, status) VALUES (?, ?, ?, ?)",
                     ("Pre-existing Offer", "RealCo", 91, "applied"))
        conn.execute("INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (1, 'tech_stack', 90, 'strong fit')")
        conn.execute("INSERT INTO schema_version (version) VALUES (7)")
        conn.commit()
        conn.close()

        init_db(db_path)

        conn = get_conn(db_path)
        try:
            assert get_schema_version(conn) == SCHEMA_VERSION
            offer = conn.execute("SELECT * FROM offers WHERE id = 1").fetchone()
            topic = conn.execute("SELECT * FROM offer_topics WHERE offer_id = 1").fetchone()
        finally:
            conn.close()
        assert offer["title"] == "Pre-existing Offer"
        assert offer["company"] == "RealCo"
        assert offer["compatibility_pct"] == 91
        assert topic["score"] == 90
        assert topic["detail"] == "strong fit"
        assert topic["confidence"] is None  # no backfill, ever


class TestShowJsonPreservesExistingKeys:
    def test_existing_json_keys_survive_the_confidence_addition(self, tmp_db, tmp_applyr, capsys):
        """MUST: existing --json keys are not renamed or removed by adding
        confidence support."""
        _add(company="Acme", topics={"tech_stack": {"score": 80, "detail": "x"}})
        capsys.readouterr()
        from applyr.commands.core import cmd_show
        cmd_show(1, as_json=True)
        data = json.loads(capsys.readouterr().out)
        for key in ("id", "title", "company", "status", "compatibility_pct"):
            assert key in data, f"pre-existing key '{key}' missing from --json output"
        assert data["topics"][0]["topic"] == "tech_stack"
        assert data["topics"][0]["score"] == 80
        assert data["topics"][0]["detail"] == "x"


class TestConfidenceCaseSensitivity:
    def test_capitalized_confidence_is_rejected_not_silently_normalized(self, tmp_db, tmp_applyr):
        """Contract enum is exactly ('high','medium','low'); a caller sending
        'High' must be rejected like any other invalid value, not silently
        lowercased/accepted (consistent with how every other enum field in
        this codebase performs an exact, case-sensitive match)."""
        with pytest.raises(SystemExit):
            _add(topics={"tech_stack": {"score": 80, "detail": "x", "confidence": "High"}})
