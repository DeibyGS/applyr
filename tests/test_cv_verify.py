"""Tests for `cv verify` — the deterministic Evidence Graph truth gate (PR4/4,
docs/adr/011-evidence-based-cv-engine.md)."""

import json

import pytest

from applyr.cv import cmd_cv_verify
from applyr.db import get_conn


@pytest.fixture
def offer_for_verify(tmp_db):
    conn = get_conn(tmp_db)
    conn.execute(
        "INSERT INTO offers (title, company, status, compatibility_pct) VALUES (?, ?, ?, ?)",
        ("Backend Dev", "Acme Corp", "pending", 70),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def cv_master_grounded(tmp_applyr, monkeypatch):
    """A cv-master.md whose evidence supports Python/FastAPI/"Amazon Web
    Services"/the "42%" metric/the "Backend Developer — Acme Corp" entry —
    the exact facts the passing CVs below state."""
    import applyr.cv as cv_mod
    monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)

    cv_master = tmp_applyr / "cv-master.md"
    cv_master.write_text(
        "## WORK EXPERIENCE\n\n"
        "**Backend Developer — Acme Corp** — Remote — 01/2022-01/2025\n"
        "- Built REST APIs with Python and FastAPI\n"
        "- Reduced latency by 42%\n\n"
        "## TECHNICAL SKILLS\n\n"
        "Languages: Python, FastAPI\n"
        "Cloud: Amazon Web Services\n"
    )
    return cv_master


def _cv_md(offer_id: int, body: str) -> str:
    return f"---\noffer_id: {offer_id}\n---\n\n{body}"


PASSING_BODY = """\
# John Doe

## Professional Summary

Backend developer skilled in Python and FastAPI.

## Work Experience

### Backend Developer - Acme Corp, Remote
01/2022 - 01/2025

- Built REST APIs with Python and FastAPI
- Reduced latency by 42%

## Technical Skills

Python, FastAPI
"""


@pytest.mark.unit
class TestCvVerifyPass:

    def test_grounded_cv_passes_and_exits_zero(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded):
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, PASSING_BODY))

        cmd_cv_verify(str(cv_path))  # must not raise SystemExit

    def test_pass_writes_evidence_snapshot_to_offer(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded):
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, PASSING_BODY))
        cmd_cv_verify(str(cv_path))

        conn = get_conn(tmp_db)
        row = conn.execute("SELECT cv_evidence_used FROM offers WHERE id = 1").fetchone()
        conn.close()
        assert row["cv_evidence_used"] is not None
        snapshot = json.loads(row["cv_evidence_used"])
        assert "Python" in snapshot
        assert "42%" in snapshot

    def test_alias_form_in_cv_matches_master_canonical_form(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded):
        # Master says "Amazon Web Services", CV says "AWS" — must still pass.
        body = PASSING_BODY.replace("Backend developer skilled in Python and FastAPI.",
                                     "Backend developer skilled in Python, FastAPI and AWS.")
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        cmd_cv_verify(str(cv_path))  # must not raise — AWS is grounded via alias

    def test_json_output_shape_on_pass(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded, capsys):
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, PASSING_BODY))
        cmd_cv_verify(str(cv_path), as_json=True)

        payload = json.loads(capsys.readouterr().out)
        assert payload["passed"] is True
        assert payload["offer_id"] == 1
        assert payload["unsupported"] == []
        assert isinstance(payload["claims"], list) and payload["claims"]


@pytest.mark.unit
class TestCvVerifyCatchesRealHallucinations:
    """Regression tests for two gaps found testing cv verify live against a
    real cv-master.md: a term with no PROTECTED_FACT_ALIASES entry and not
    in the candidate's own skills was never even checked (vocabulary gap),
    and a fabricated employer/title could word-overlap-pass on a single
    generic role noun shared with an unrelated real entry (stopword gap)."""

    def test_offer_only_term_not_in_alias_dict_is_still_checked(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded):
        # "MLOps" is in neither PROTECTED_FACT_ALIASES nor the candidate's
        # skills — before the fix, _build_tech_vocabulary never considered
        # it a checkable term at all, so a hallucinated claim went
        # undetected. The offer's own tech_stack must extend the vocabulary.
        conn = get_conn(tmp_db)
        conn.execute("UPDATE offers SET tech_stack = 'Python, MLOps' WHERE id = 1")
        conn.commit()
        conn.close()

        body = PASSING_BODY.replace(
            "Backend developer skilled in Python and FastAPI.",
            "Backend developer skilled in Python and MLOps.",
        )
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path), as_json=True)

    def test_fabricated_title_sharing_only_a_role_noun_is_still_blocked(self, tmp_db, tmp_applyr, offer_for_verify, monkeypatch):
        # Reproduces the exact live failure: the candidate's real profile has
        # an unrelated EDUCATION entry containing "Engineer" ("Máster en AI
        # Engineer"), and a fabricated WORK EXPERIENCE title also containing
        # "Engineer" — before the stopword fix, that single shared generic
        # word was enough to word-overlap-pass a completely fabricated
        # employer ("Globex Financial Corp") that shares nothing else real.
        import applyr.cv as cv_mod
        monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
        cv_master = tmp_applyr / "cv-master.md"
        cv_master.write_text(
            "## WORK EXPERIENCE\n\n"
            "**Backend Developer — Acme Corp** — Remote — 01/2022-01/2025\n"
            "- Built REST APIs with Python\n\n"
            "## EDUCATION\n\n"
            "**Master en AI Engineer**\n"
            "The Power · Madrid · 08/2026 – en curso\n"
        )

        body = (
            "# John Doe\n\n"
            "### Senior ML Engineer - Globex Financial Corp, Remote\n"
            "01/2022 - 01/2025\n\n"
            "- Built things\n"
        )
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit) as exc:
            cmd_cv_verify(str(cv_path), as_json=True)
        assert exc.value.code == 1


@pytest.mark.unit
class TestCvVerifyCodeReviewFixes:
    """Regression tests for exploits confirmed live by /code-review against
    the already-committed evidence.py/cv.py: three independent ways a
    fabricated claim passed cv verify's "authoritative" gate unflagged."""

    def test_fabricated_short_company_name_is_blocked(self, tmp_db, tmp_applyr, offer_for_verify, monkeypatch):
        # "CTO - IBM, Remote" against an entirely unrelated real profile:
        # every word in the heading was either a filtered C-level
        # abbreviation, a stopword, or (at the old `> 3` cutoff) too short —
        # heading_words ended up empty, and the old "nothing to check ->
        # True" fallback passed it unconditionally.
        import applyr.cv as cv_mod
        monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
        cv_master = tmp_applyr / "cv-master.md"
        cv_master.write_text(
            "## WORK EXPERIENCE\n\n"
            "**Backend Developer — Acme Corp** — Remote — 01/2022-01/2025\n"
            "- Built REST APIs with Python\n"
        )
        body = (
            "# John Doe\n\n"
            "### CTO - IBM, Remote\n"
            "01/2022 - 01/2025\n\n"
            "- Built things\n"
        )
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit) as exc:
            cmd_cv_verify(str(cv_path), as_json=True)
        assert exc.value.code == 1

    def test_fabricated_decimal_metric_is_not_confused_with_a_real_one(self, tmp_db, tmp_applyr, offer_for_verify, monkeypatch):
        # Master genuinely has "15x" (a real, evidenced metric). The old
        # `\d+x\b` regex extracted a fabricated "2.5x" as just "5x", which
        # then substring-matched inside the real "15x" and passed.
        import applyr.cv as cv_mod
        monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
        cv_master = tmp_applyr / "cv-master.md"
        cv_master.write_text(
            "## WORK EXPERIENCE\n\n"
            "**Backend Developer — Acme Corp** — Remote — 01/2022-01/2025\n"
            "- Scaled throughput 15x under load\n"
        )
        body = (
            "# John Doe\n\n"
            "### Backend Developer - Acme Corp, Remote\n"
            "01/2022 - 01/2025\n\n"
            "- Scaled throughput 2.5x under load\n"
        )
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit) as exc:
            cmd_cv_verify(str(cv_path), as_json=True)
        assert exc.value.code == 1

    def test_symbol_suffixed_tech_term_is_actually_checked(self, tmp_db, tmp_applyr, offer_for_verify, monkeypatch):
        # The old `\b`-based extraction never matched "C++" (a non-word
        # character never satisfies a trailing `\b` before a space), so a
        # fabricated "C++" claim was silently excluded from `results`
        # entirely — never checked, never reported unsupported.
        import applyr.cv as cv_mod
        monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
        cv_master = tmp_applyr / "cv-master.md"
        cv_master.write_text(
            "## WORK EXPERIENCE\n\n"
            "**Backend Developer — Acme Corp** — Remote — 01/2022-01/2025\n"
            "- Built REST APIs with Python\n"
        )
        conn = get_conn(tmp_db)
        conn.execute("UPDATE offers SET tech_stack = 'Python, C++' WHERE id = 1")
        conn.commit()
        conn.close()

        body = (
            "# John Doe\n\n"
            "### Backend Developer - Acme Corp, Remote\n"
            "01/2022 - 01/2025\n\n"
            "- Built systems in Python and C++\n"
        )
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit) as exc:
            cmd_cv_verify(str(cv_path), as_json=True)
        assert exc.value.code == 1


@pytest.mark.unit
class TestCvVerifyBlocked:

    def test_unevidenced_technology_blocks_with_exit_1(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded):
        body = PASSING_BODY.replace("Python and FastAPI.", "Python, FastAPI and Kubernetes.")
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit) as exc:
            cmd_cv_verify(str(cv_path))
        assert exc.value.code == 1

    def test_unevidenced_metric_is_listed_as_unsupported(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded, capsys):
        body = PASSING_BODY.replace("Reduced latency by 42%", "Reduced latency by 99%")
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path), as_json=True)
        payload = json.loads(capsys.readouterr().out)
        assert payload["passed"] is False
        unsupported_claims = [c["claim"] for c in payload["unsupported"]]
        assert "99%" in unsupported_claims

    def test_blocked_run_does_not_write_evidence_snapshot(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded):
        body = PASSING_BODY.replace("Python and FastAPI.", "Python, FastAPI and Kubernetes.")
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path))

        conn = get_conn(tmp_db)
        row = conn.execute("SELECT cv_evidence_used FROM offers WHERE id = 1").fetchone()
        conn.close()
        assert row["cv_evidence_used"] is None

    def test_fabricated_employer_heading_is_unsupported(self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded, capsys):
        body = PASSING_BODY.replace(
            "### Backend Developer - Acme Corp, Remote",
            "### Principal Engineer - Globex Industries, Onsite",
        )
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, body))

        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path), as_json=True)
        payload = json.loads(capsys.readouterr().out)
        categories = {c["category"] for c in payload["unsupported"]}
        assert "employer_or_title" in categories

    def test_fabricated_employer_heading_is_caught_in_legacy_html_cv(
        self, tmp_db, tmp_applyr, offer_for_verify, cv_master_grounded, capsys
    ):
        # Regression (confirmed via /code-review): _ENTRY_HEADING_RE only
        # matched markdown "### " headings, so a legacy .html CV (ADR-008:
        # .html stays read-compatible) silently skipped the
        # employer_or_title check entirely — a fabricated <h3> heading was
        # never even extracted, let alone flagged.
        html = (
            "<!-- applyr:offer-id=1 -->\n"
            "<html><body>\n"
            "<h3>Principal Engineer - Globex Industries, Onsite</h3>\n"
            "<p>Built REST APIs with Python and FastAPI</p>\n"
            "</body></html>\n"
        )
        cv_path = tmp_applyr / "cv-acme.html"
        cv_path.write_text(html)

        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path), as_json=True)
        payload = json.loads(capsys.readouterr().out)
        categories = {c["category"] for c in payload["unsupported"]}
        assert "employer_or_title" in categories


@pytest.mark.unit
class TestCvVerifyErrors:

    def test_no_offer_id_in_file_dies(self, tmp_db, tmp_applyr, cv_master_grounded):
        cv_path = tmp_applyr / "cv-no-marker.md"
        cv_path.write_text("# John Doe\n\nJust a CV with no offer marker.\n")
        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path))

    def test_offer_not_found_dies(self, tmp_db, tmp_applyr, cv_master_grounded):
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(999, PASSING_BODY))
        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path))

    def test_missing_cv_master_dies(self, tmp_db, tmp_applyr, offer_for_verify, monkeypatch):
        import applyr.cv as cv_mod
        monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
        cv_path = tmp_applyr / "cv-acme.md"
        cv_path.write_text(_cv_md(1, PASSING_BODY))
        with pytest.raises(SystemExit):
            cmd_cv_verify(str(cv_path))
