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
