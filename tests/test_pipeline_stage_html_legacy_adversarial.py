"""Adversarial verification of ADR-013 / specs/visual-ui-applyr-world-phase2's
5 instrumentation call sites.

Contract under test (spec, verbatim):
  - "WHEN applyr cv generate <id> successfully writes a CV draft THE system
    shall set that offer's pipeline_stage to cv."
  - "WHEN applyr cv review <file> completes (prints the review prompt) THE
    system shall set the linked offer's pipeline_stage to ats."
  - "WHEN applyr cv pdf <file> successfully generates a PDF THE system shall
    set the linked offer's pipeline_stage to application."

None of these three clauses carve out an exception for HTML input. But both
cmd_cv_review and cmd_cv_pdf (applyr/cv.py) only ever look for the
`offer_id: N` frontmatter marker — the only thing `_mark_pipeline_stage` can
key off of — when `cv_path.suffix == ".md"`. Both functions' own docstrings
document `.html` as a still-supported, non-deprecated input ("markdown or
HTML" / "legacy support"), so this is a live code path, not dead code. A CV
reviewed or PDF'd from `.html` therefore never reaches `_mark_pipeline_stage`
at all, silently violating the two MUST clauses above.

This is also a real gap in the existing suite:
tests/test_pipeline_stage_instrumentation.py exercises cmd_cv_review only
against the `.md` file cmd_cv_generate produces, and skips calling
cmd_cv_pdf entirely (its own docstring reasons this is "equivalent coverage"
via `_mark_pipeline_stage` — true for the timeout/non-blocking contract, but
it never exercises the `.suffix == ".md"` gate itself).
"""

import json

import pytest

from applyr.commands.core import cmd_add
from applyr.db import get_conn


def _pipeline_stage(tmp_db, offer_id: int) -> str | None:
    conn = get_conn(tmp_db)
    try:
        row = conn.execute(
            "SELECT pipeline_stage FROM offers WHERE id = ?", (offer_id,)
        ).fetchone()
    finally:
        conn.close()
    return row["pipeline_stage"] if row else None


@pytest.fixture
def offer_id(tmp_db, tmp_applyr, monkeypatch):
    """One scored offer, with notify_stage's network leg neutered (points at
    a closed port) so these tests only exercise the DB-write half of the
    contract — never real or accidental network traffic."""
    import applyr.ui_events as ui_events_mod

    monkeypatch.setattr(ui_events_mod, "DEFAULT_UI_PORT", 1)  # port 1: always refused, no listener possible
    cmd_add(json.dumps({"title": "Backend Dev", "company": "Acme"}))
    return 1


class TestCvReviewHtmlLegacyPath:
    def test_html_input_still_marks_pipeline_stage_ats(self, offer_id, tmp_db, tmp_path, capsys):
        from applyr.cv import cmd_cv_review

        # Same offer_id marker cmd_cv_generate embeds in `.md` frontmatter,
        # carried into a legacy `.html` CV instead — a realistic shape for a
        # hand-exported or pre-markdown-rewrite CV that still wants to be
        # traceable back to its offer.
        html_file = tmp_path / "cv-acme.html"
        html_file.write_text(
            f"<!-- offer_id: {offer_id} -->\n<html><body>Backend Dev</body></html>"
        )

        cmd_cv_review(str(html_file))
        capsys.readouterr()

        assert _pipeline_stage(tmp_db, offer_id) == "ats", (
            "cmd_cv_review printed its prompt (the spec's completion signal) "
            "but never called _mark_pipeline_stage because cv_path.suffix != "
            "'.md' — the offer_id frontmatter marker is only ever looked up "
            "under an `if cv_path.suffix == '.md':` guard."
        )


class TestCvPdfHtmlLegacyPath:
    def test_html_input_still_marks_pipeline_stage_application(
        self, offer_id, tmp_db, tmp_path, monkeypatch
    ):
        import applyr.cv as cv_mod

        html_file = tmp_path / "cv-acme.html"
        html_file.write_text(
            f"<!-- offer_id: {offer_id} -->\n<html><body>Backend Dev</body></html>"
        )
        pdf_file = html_file.with_suffix(".pdf")
        pdf_file.write_bytes(b"%PDF-1.4\n%fake\n")  # exists() check only; _count_pdf_pages tolerates non-matching bytes

        fake_chrome = tmp_path / "fake-chrome"
        fake_chrome.write_text("#!/bin/sh\n")  # only needs to satisfy os.path.isfile

        monkeypatch.setattr(
            cv_mod, "load_config", lambda: {"cv": {"chrome_path": str(fake_chrome)}}
        )

        class _FakeResult:
            returncode = 0
            stderr = ""

        monkeypatch.setattr(
            cv_mod.subprocess, "run", lambda *a, **k: _FakeResult()
        )

        cv_mod.cmd_cv_pdf(str(html_file))

        assert _pipeline_stage(tmp_db, offer_id) == "application", (
            "cmd_cv_pdf reported the PDF as generated (pdf_path.exists() was "
            "True) but never called _mark_pipeline_stage because the "
            "offer-id lookup is gated behind `if cv_path.suffix == '.md':` — "
            "the exact same gate as cmd_cv_review, for the `.pdf` sibling of "
            "the same input file."
        )


class TestUpdateAppliedStageForcing:
    """Not called out as a bug by the spec, but not proven safe either — the
    spec's wording for `update <id> applied` ("keep pipeline_stage at
    application ... refresh pipeline_stage_at ... not a new zone") implicitly
    assumes the offer already walked there via `cv pdf`. cmd_update's actual
    guard is only `if status == "applied":` — it does not check the offer's
    *current* pipeline_stage before overwriting it, so calling
    `update <id> applied` on an offer that never went through cv generate/
    review/pdf silently fast-forwards it straight to "application", skipping
    cv/ats. This documents that behavior rather than asserting it's wrong —
    UNCLEAR REQUIREMENT, flagged for the user/spec author, not a fix target.
    """

    def test_update_applied_force_sets_stage_even_without_prior_cv_pdf(
        self, offer_id, tmp_db, monkeypatch
    ):
        import applyr.commands.core as core_mod

        monkeypatch.setattr("applyr.ui_events.DEFAULT_UI_PORT", 1)
        assert _pipeline_stage(tmp_db, offer_id) == "matching"  # only cmd_add has run so far

        core_mod.cmd_update(offer_id, "applied")

        stage = _pipeline_stage(tmp_db, offer_id)
        # Documents current behavior. If this assertion is what the spec
        # author intended, fine — but it means an offer can visually
        # teleport from "matching" straight to "application" in the Office
        # scene with no intermediate "cv"/"ats" sprite ever having existed,
        # skipping two zones the spec otherwise treats as real waypoints.
        assert stage == "application"


class TestDiscardedMidFlightLeavesStageUntouched:
    """Spec's explicitly accepted edge case: "An offer discarded/rejected
    mid-flight: pipeline_stage is left as-is (not cleared)." Cheap regression
    guard — cmd_update's dynamic field-list builder is exactly the kind of
    code an unrelated future change could accidentally make discard-aware."""

    def test_discarding_an_offer_does_not_touch_pipeline_stage(
        self, offer_id, tmp_db, monkeypatch
    ):
        import applyr.commands.core as core_mod

        monkeypatch.setattr("applyr.ui_events.DEFAULT_UI_PORT", 1)
        assert _pipeline_stage(tmp_db, offer_id) == "matching"

        core_mod.cmd_update(offer_id, "discarded", notes="not a fit")

        assert _pipeline_stage(tmp_db, offer_id) == "matching"


class TestMigrationAgainstAGenuinePreV12Schema:
    """tests/test_db.py's own TestMigrationV11ToV12 always runs against a
    `tmp_db` that init_db() already created with every v12 column present
    (fresh installs skip the migration path and get SCHEMA_SQL directly) —
    it only resets `schema_version` to 11 afterward. That means its ALTER
    TABLE ADD COLUMN statements always hit the "duplicate column name"
    short-circuit in `_run_migrations` (db.py) rather than genuinely running
    against a table that lacks the columns. This test builds a real
    pre-migration `offers` table by hand — no pipeline_stage/pipeline_stage_at
    columns at all — to prove the actual ALTER TABLE ... CHECK (...) syntax
    parses and enforces on a from-scratch upgrade, not just on an idempotent
    no-op re-run."""

    def test_alter_table_with_check_runs_and_enforces_on_a_real_legacy_table(self, tmp_path):
        import sqlite3

        from applyr.db import _run_migrations

        db_path = tmp_path / "legacy_v11.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            """CREATE TABLE offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL CHECK (length(trim(company)) > 0),
                status TEXT DEFAULT 'pending'
            )"""
        )
        conn.execute("INSERT INTO offers (title, company) VALUES ('Dev', 'Acme')")
        conn.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version (version) VALUES (11)")
        conn.commit()

        _run_migrations(conn, 11, 12)
        conn.commit()

        cols = {r[1] for r in conn.execute("PRAGMA table_info(offers)").fetchall()}
        assert "pipeline_stage" in cols
        assert "pipeline_stage_at" in cols

        row = conn.execute("SELECT pipeline_stage, pipeline_stage_at FROM offers WHERE id = 1").fetchone()
        assert row == (None, None)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE offers SET pipeline_stage = 'recruiter' WHERE id = 1")

        conn.execute("UPDATE offers SET pipeline_stage = 'cv' WHERE id = 1")  # must not raise
        conn.close()
