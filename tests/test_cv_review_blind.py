"""Tests for blind recruiter review command."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from applyr.cv import cmd_cv_review_blind
from applyr.db import get_conn


@pytest.fixture
def offer_for_review(tmp_db):
    """Create an offer for review-blind testing."""
    conn = get_conn(tmp_db)
    conn.execute(
        "INSERT INTO offers (title, company, status, compatibility_pct, work_mode, seniority_level, tech_stack) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("Backend Dev", "Acme Corp", "pending", 47, "remote", "mid", "Python, FastAPI, PostgreSQL"),
    )
    conn.execute(
        "INSERT INTO offer_topics (offer_id, topic, score, detail) VALUES (?, ?, ?, ?)",
        (1, "tech_stack", 70, "Strong Python skills"),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def cv_master_valid(tmp_applyr, monkeypatch):
    """Create a valid cv-master.md and patch APPLYR_DIR in cv module."""
    import applyr.cv as cv_mod
    monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)

    cv_master = tmp_applyr / "cv-master.md"
    cv_master.write_text(
        "# John Doe\n\n"
        "## Professional Summary\n"
        "Senior backend developer with 5 years of experience in Python and FastAPI.\n\n"
        "## Work Experience\n"
        "### Backend Developer | Tech Corp | 2021-2024\n"
        "- Built REST APIs with FastAPI serving 10K+ requests/sec\n"
        "- Designed PostgreSQL schemas for high-traffic applications\n\n"
        "## Technical Skills\n"
        "- Languages: Python, JavaScript\n"
        "- Frameworks: FastAPI, Django\n"
        "- Databases: PostgreSQL, Redis\n"
    )
    return cv_master


@pytest.mark.unit
class TestReviewBlind:

    def test_review_blind_missing_offer(self, tmp_db):
        """Should die when offer doesn't exist."""
        with pytest.raises(SystemExit):
            cmd_cv_review_blind(999)

    def test_review_blind_missing_cv_master(self, tmp_db, offer_for_review, tmp_applyr, monkeypatch):
        """Should die when cv-master.md doesn't exist."""
        import applyr.cv as cv_mod
        monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)

        # Remove cv-master.md
        cv_master = tmp_applyr / "cv-master.md"
        if cv_master.exists():
            cv_master.unlink()
        with pytest.raises(SystemExit):
            cmd_cv_review_blind(1)

    def test_review_blind_success_text(self, tmp_db, offer_for_review, cv_master_valid, capsys):
        """Should output review prompt with offer context."""
        cmd_cv_review_blind(1)
        captured = capsys.readouterr()
        assert "Backend Dev" in captured.out
        assert "Acme Corp" in captured.out
        assert "senior technical recruiter" in captured.out.lower()
        # Should NOT include compatibility_pct (blind)
        assert "47%" not in captured.out
        # Should include thresholds
        assert "APPLY >=" in captured.out
        assert "MAYBE >=" in captured.out

    def test_review_blind_success_json(self, tmp_db, offer_for_review, cv_master_valid, capsys):
        """Should output JSON with prompt and thresholds."""
        cmd_cv_review_blind(1, as_json=True)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["offer_id"] == 1
        assert "prompt" in output
        assert "thresholds" in output
        assert "apply" in output["thresholds"]
        assert "maybe" in output["thresholds"]
        # Should NOT include compatibility_pct (blind)
        assert "compatibility_pct" not in output.get("offer_context", "")

    def test_review_blind_includes_cv_master(self, tmp_db, offer_for_review, cv_master_valid, capsys):
        """Should include cv-master.md content in the prompt."""
        cmd_cv_review_blind(1)
        captured = capsys.readouterr()
        # The cv-master.md content should be in the prompt
        assert "Candidate profile" in captured.out
        # Check that the profile is parsed (markdown converted to plain text)
        assert "Professional Summary" in captured.out or "PERFIL PROFESIONAL" in captured.out

    def test_review_blind_blind_property(self, tmp_db, offer_for_review, cv_master_valid, capsys):
        """Should NOT include the Matcher's compatibility_pct in the prompt."""
        cmd_cv_review_blind(1)
        captured = capsys.readouterr()
        # The prompt should not contain the score "45" from the offer
        # It should only contain topic names, not scores
        assert "compatibility_pct" not in captured.out
        # The offer context should not include "Compatibility: 45%"
        assert "Compatibility" not in captured.out

    def test_review_blind_uses_config_thresholds(self, tmp_db, offer_for_review, cv_master_valid, capsys):
        """Should use thresholds from config."""
        cmd_cv_review_blind(1)
        captured = capsys.readouterr()
        # Thresholds are loaded from config (default: 80 apply, 60 maybe)
        assert "APPLY >=" in captured.out
        assert "MAYBE >=" in captured.out
        # Should include the verdict classification instructions
        assert "STRONG_MATCH" in captured.out
        assert "CLOSE_MATCH" in captured.out
        assert "NO_MATCH" in captured.out

    def test_review_blind_reads_apply_threshold_from_config(
        self, tmp_db, offer_for_review, cv_master_valid, tmp_applyr, capsys
    ):
        """Thresholds must come from threshold_apply/threshold_maybe, not legacy keys.

        Until v1.4.0 the command read `general.threshold` (the legacy 65%)
        and a `maybe_threshold` key that does not exist, so its verdicts could
        disagree with the rest of applyr.
        """
        (tmp_applyr / "applyr.toml").write_text(
            "[general]\nthreshold_apply = 90\nthreshold_maybe = 70\n"
        )
        cmd_cv_review_blind(1)
        captured = capsys.readouterr()
        assert "APPLY >= 90%" in captured.out
        assert "MAYBE >= 70%" in captured.out
        assert "STRONG_MATCH  if score >= 90" in captured.out
        assert "CLOSE_MATCH   if score >= 70" in captured.out

    def test_review_blind_does_not_score_finished_document_criteria(
        self, tmp_db, offer_for_review, cv_master_valid, capsys
    ):
        """review-blind runs on the RAW cv-master.md, before any CV is trimmed
        for the offer. "ATS Format Compliance" and "Length & Relevance" (1-2
        pages) only make sense against a finished, tailored CV — scoring them
        here penalized a full career-history source document for not already
        being the 1-page deliverable, regardless of how strong a candidate is.
        """
        cmd_cv_review_blind(1)
        captured = capsys.readouterr()
        assert "ATS COMPLIANCE" not in captured.out
        assert "LENGTH & RELEVANCE" not in captured.out
        assert "RAW, untailored source profile" in captured.out
