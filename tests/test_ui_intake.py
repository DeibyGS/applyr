"""Tests for applyr/intake.py — the ui_intake CRUD used by the Visual UI."""

import json
import sys

import pytest

from applyr.db import get_conn
from applyr.intake import create_intake, get_intake, list_intake, mark_intake_promoted


@pytest.mark.unit
class TestCreateIntake:

    def test_creates_pending_row(self, tmp_db):
        row = create_intake("Senior Backend Dev at Acme...", db_path=tmp_db)
        assert row["status"] == "pending"
        assert row["raw_text"] == "Senior Backend Dev at Acme..."
        assert row["offer_id"] is None
        assert row["promoted_at"] is None

    def test_stores_optional_source_note(self, tmp_db):
        row = create_intake("Some job text", source_note="LinkedIn", db_path=tmp_db)
        assert row["source_note"] == "LinkedIn"

    def test_blank_raw_text_is_rejected(self, tmp_db):
        with pytest.raises(ValueError):
            create_intake("   ", db_path=tmp_db)

    def test_empty_raw_text_is_rejected(self, tmp_db):
        with pytest.raises(ValueError):
            create_intake("", db_path=tmp_db)


@pytest.mark.unit
class TestCreateIntakeIdempotency:
    """ADR-014: a double 'Enviar' click must not create two intake/job pairs."""

    def test_same_text_within_window_returns_existing_row(self, tmp_db):
        first = create_intake("dup text", db_path=tmp_db)
        second = create_intake("dup text", db_path=tmp_db)
        assert first["id"] == second["id"]

    def test_different_text_creates_a_new_row(self, tmp_db):
        first = create_intake("text a", db_path=tmp_db)
        second = create_intake("text b", db_path=tmp_db)
        assert first["id"] != second["id"]

    def test_promoted_row_does_not_shadow_a_new_submission(self, tmp_db):
        # The idempotency guard only matches status='pending' — once a row
        # is promoted, resubmitting the same text is a legitimate new offer.
        first = create_intake("reused text", db_path=tmp_db)
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(first["id"], offer_id=1, conn=conn)
            conn.commit()
        finally:
            conn.close()
        second = create_intake("reused text", db_path=tmp_db)
        assert second["id"] != first["id"]
        assert second["status"] == "pending"

    def test_accepts_an_external_connection_without_committing(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            row = create_intake("shared-transaction text", conn=conn)
            # Not committed yet — invisible on a separate connection.
            other_conn = get_conn(tmp_db)
            try:
                assert other_conn.execute(
                    "SELECT COUNT(*) as n FROM ui_intake WHERE id = ?", (row["id"],)
                ).fetchone()["n"] == 0
            finally:
                other_conn.close()
            conn.commit()
        finally:
            conn.close()
        assert get_intake(row["id"], db_path=tmp_db) is not None


@pytest.mark.unit
class TestListIntake:

    def test_lists_newest_first(self, tmp_db):
        create_intake("first", db_path=tmp_db)
        create_intake("second", db_path=tmp_db)
        rows = list_intake(db_path=tmp_db)
        assert [r["raw_text"] for r in rows] == ["second", "first"]

    def test_filters_by_status(self, tmp_db):
        pending = create_intake("still pending", db_path=tmp_db)
        promoted = create_intake("will be promoted", db_path=tmp_db)
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(promoted["id"], offer_id=1, conn=conn)
            conn.commit()
        finally:
            conn.close()

        pending_rows = list_intake(status="pending", db_path=tmp_db)
        promoted_rows = list_intake(status="promoted", db_path=tmp_db)
        assert [r["id"] for r in pending_rows] == [pending["id"]]
        assert [r["id"] for r in promoted_rows] == [promoted["id"]]


@pytest.mark.unit
class TestGetIntake:

    def test_returns_none_for_missing_id(self, tmp_db):
        assert get_intake(999, db_path=tmp_db) is None

    def test_returns_the_row(self, tmp_db):
        created = create_intake("some text", db_path=tmp_db)
        fetched = get_intake(created["id"], db_path=tmp_db)
        assert fetched["id"] == created["id"]
        assert fetched["raw_text"] == "some text"


@pytest.mark.unit
class TestMarkIntakePromoted:

    def test_promotes_a_pending_row(self, tmp_db):
        intake = create_intake("job text", db_path=tmp_db)
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(intake["id"], offer_id=1, conn=conn)
            conn.commit()
        finally:
            conn.close()

        row = get_intake(intake["id"], db_path=tmp_db)
        assert row["status"] == "promoted"
        assert row["offer_id"] == 1
        assert row["promoted_at"] is not None

    def test_raises_on_missing_intake_id(self, tmp_db):
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            with pytest.raises(ValueError, match="No ui_intake row"):
                mark_intake_promoted(999, offer_id=1, conn=conn)
        finally:
            conn.close()

    def test_raises_on_already_promoted_row(self, tmp_db):
        intake = create_intake("job text", db_path=tmp_db)
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(intake["id"], offer_id=1, conn=conn)
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev2', 'Acme2')")
            with pytest.raises(ValueError, match="already 'promoted'"):
                mark_intake_promoted(intake["id"], offer_id=2, conn=conn)
            conn.commit()
        finally:
            conn.close()

    def test_does_not_promote_across_transactions_on_failure(self, tmp_db):
        """The offer insert and the promotion flip share one connection —
        if the caller never commits (e.g. it aborts after this raises), the
        promotion never lands, matching the 'succeed or fail together'
        contract from the spec."""
        intake = create_intake("job text", db_path=tmp_db)
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(intake["id"], offer_id=1, conn=conn)
            # no commit — simulates the caller aborting before commit
        finally:
            conn.close()

        row = get_intake(intake["id"], db_path=tmp_db)
        assert row["status"] == "pending"


@pytest.mark.unit
class TestAddIntakeIdFlag:
    """`applyr add ... --intake-id <id>` — the CLI-level linkage."""

    def test_promotes_the_intake_row_on_success(self, tmp_db, run_cli, capsys):
        intake = create_intake("Backend Dev at Acme", db_path=tmp_db)
        run_cli(["--json", "add", json.dumps({"title": "Backend Dev", "company": "Acme"}),
                 "--intake-id", str(intake["id"])])
        payload = json.loads(capsys.readouterr().out)
        offer_id = payload["id"]

        row = get_intake(intake["id"], db_path=tmp_db)
        assert row["status"] == "promoted"
        assert row["offer_id"] == offer_id

    def test_add_without_intake_id_is_unaffected(self, tmp_db, run_cli, capsys):
        """Existing usage (no --intake-id) must behave exactly as before."""
        run_cli(["--json", "add", json.dumps({"title": "Backend Dev", "company": "Acme"})])
        payload = json.loads(capsys.readouterr().out)
        assert payload["title"] == "Backend Dev"
        assert list_intake(db_path=tmp_db) == []

    def test_missing_intake_id_fails_the_whole_add(self, tmp_db, run_cli, capsys):
        with pytest.raises(SystemExit) as exc_info:
            run_cli(["--json", "add", json.dumps({"title": "Backend Dev", "company": "Acme"}),
                     "--intake-id", "999"])
        assert exc_info.value.code != 0
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "invalid_intake_id"

        conn = get_conn(tmp_db)
        try:
            count = conn.execute("SELECT COUNT(*) AS n FROM offers").fetchone()["n"]
        finally:
            conn.close()
        assert count == 0, "the offer insert must roll back when the intake linkage fails"

    def test_already_promoted_intake_id_fails_the_whole_add(self, tmp_db, run_cli, capsys):
        intake = create_intake("Backend Dev at Acme", db_path=tmp_db)
        conn = get_conn(tmp_db)
        try:
            conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
            mark_intake_promoted(intake["id"], offer_id=1, conn=conn)
            conn.commit()
        finally:
            conn.close()

        with pytest.raises(SystemExit):
            run_cli(["--json", "add", json.dumps({"title": "Backend Dev 2", "company": "Acme"}),
                     "--intake-id", str(intake["id"])])
        capsys.readouterr()

        conn = get_conn(tmp_db)
        try:
            count = conn.execute("SELECT COUNT(*) AS n FROM offers").fetchone()["n"]
        finally:
            conn.close()
        assert count == 1, "only the pre-existing offer should exist — the second add must not commit"
