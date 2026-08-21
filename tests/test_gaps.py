"""Tests for learning gaps commands."""

import json
import pytest

from applyr.commands.analytics import cmd_gaps_save, cmd_gaps_list, cmd_gaps_stats
from applyr.db import get_conn


@pytest.fixture
def offer_with_gap(tmp_db):
    """Create an offer and a learning gap for testing."""
    conn = get_conn(tmp_db)
    conn.execute(
        "INSERT INTO offers (title, company, status, compatibility_pct) VALUES (?, ?, ?, ?)",
        ("Backend Dev", "Acme Corp", "pending", 45),
    )
    conn.execute(
        "INSERT INTO learning_gaps (offer_id, topic, gap_detail, severity, suggested_action) "
        "VALUES (?, ?, ?, ?, ?)",
        (1, "tech_stack", "Missing LangChain experience", "high", "Build a RAG project"),
    )
    conn.commit()
    conn.close()


@pytest.mark.unit
class TestGapsSave:

    def test_save_gaps(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute(
            "INSERT INTO offers (title, company) VALUES (?, ?)",
            ("Test Offer", "Test Corp"),
        )
        conn.commit()
        conn.close()

        gaps_json = json.dumps({
            "gaps": [
                {
                    "topic": "tech_stack",
                    "gap_detail": "Missing Kubernetes",
                    "severity": "medium",
                    "suggested_action": "Study K8s basics",
                }
            ]
        })
        cmd_gaps_save(1, gaps_json)

        conn = get_conn(tmp_db)
        rows = conn.execute("SELECT * FROM learning_gaps WHERE offer_id = 1").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0]["topic"] == "tech_stack"
        assert rows[0]["gap_detail"] == "Missing Kubernetes"
        assert rows[0]["severity"] == "medium"

    def test_save_multiple_gaps(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        gaps_json = json.dumps({
            "gaps": [
                {"topic": "tech_stack", "gap_detail": "Gap 1"},
                {"topic": "english", "gap_detail": "Gap 2", "severity": "high"},
                {"topic": "experience", "gap_detail": "Gap 3", "severity": "low"},
            ]
        })
        cmd_gaps_save(1, gaps_json)

        conn = get_conn(tmp_db)
        rows = conn.execute("SELECT * FROM learning_gaps WHERE offer_id = 1").fetchall()
        conn.close()
        assert len(rows) == 3

    def test_save_empty_gaps_dies(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        gaps_json = json.dumps({"gaps": []})
        with pytest.raises(SystemExit):
            cmd_gaps_save(1, gaps_json)

    def test_save_invalid_json_dies(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        with pytest.raises(SystemExit):
            cmd_gaps_save(1, "not json")

    def test_save_invalid_topic_dies(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        gaps_json = json.dumps({
            "gaps": [{"topic": "invalid_topic", "gap_detail": "test"}]
        })
        with pytest.raises(SystemExit):
            cmd_gaps_save(1, gaps_json)

    def test_save_invalid_severity_dies(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        gaps_json = json.dumps({
            "gaps": [{"topic": "tech_stack", "gap_detail": "test", "severity": "critical"}]
        })
        with pytest.raises(SystemExit):
            cmd_gaps_save(1, gaps_json)

    def test_save_missing_offer_dies(self, tmp_db):
        gaps_json = json.dumps({
            "gaps": [{"topic": "tech_stack", "gap_detail": "test"}]
        })
        with pytest.raises(SystemExit):
            cmd_gaps_save(999, gaps_json)

    def test_save_default_severity(self, tmp_db):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        gaps_json = json.dumps({
            "gaps": [{"topic": "tech_stack", "gap_detail": "test"}]
        })
        cmd_gaps_save(1, gaps_json)

        conn = get_conn(tmp_db)
        row = conn.execute("SELECT * FROM learning_gaps WHERE id = 1").fetchone()
        conn.close()
        assert row["severity"] == "medium"

    def test_save_json_output(self, tmp_db, capsys):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.commit()
        conn.close()

        gaps_json = json.dumps({
            "gaps": [{"topic": "tech_stack", "gap_detail": "test"}]
        })
        cmd_gaps_save(1, gaps_json, as_json=True)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["offer_id"] == 1
        assert output["gaps_saved"] == 1


@pytest.mark.unit
class TestGapsList:

    def test_list_empty(self, tmp_db, capsys):
        cmd_gaps_list()
        captured = capsys.readouterr()
        assert "No learning gaps found" in captured.out

    def test_list_with_data(self, tmp_db, offer_with_gap, capsys):
        cmd_gaps_list()
        captured = capsys.readouterr()
        assert "Missing LangChain experience" in captured.out
        assert "Acme Corp" in captured.out

    def test_list_filter_by_topic(self, tmp_db, offer_with_gap, capsys):
        cmd_gaps_list(topic="english")
        captured = capsys.readouterr()
        assert "No learning gaps found" in captured.out

    def test_list_filter_by_severity(self, tmp_db, offer_with_gap, capsys):
        cmd_gaps_list(severity="high")
        captured = capsys.readouterr()
        assert "Missing LangChain experience" in captured.out

    def test_list_json_output(self, tmp_db, offer_with_gap, capsys):
        cmd_gaps_list(as_json=True)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["total"] == 1
        assert output["gaps"][0]["topic"] == "tech_stack"


@pytest.mark.unit
class TestGapsStats:

    def test_stats_empty(self, tmp_db, capsys):
        cmd_gaps_stats()
        captured = capsys.readouterr()
        assert "No learning gaps recorded" in captured.out

    def test_stats_with_data(self, tmp_db, offer_with_gap, capsys):
        cmd_gaps_stats()
        captured = capsys.readouterr()
        assert "Total gaps: 1" in captured.out
        assert "Tech Stack" in captured.out
        assert "high" in captured.out

    def test_stats_json_output(self, tmp_db, offer_with_gap, capsys):
        cmd_gaps_stats(as_json=True)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["total"] == 1
        assert "tech_stack" in output["by_topic"]
        assert "high" in output["by_severity"]

    def test_stats_multiple_gaps(self, tmp_db, capsys):
        conn = get_conn(tmp_db)
        conn.execute("INSERT INTO offers (title, company) VALUES (?, ?)", ("Test", "Acme"))
        conn.execute(
            "INSERT INTO learning_gaps (offer_id, topic, gap_detail, severity) VALUES (?, ?, ?, ?)",
            (1, "tech_stack", "Gap 1", "high"),
        )
        conn.execute(
            "INSERT INTO learning_gaps (offer_id, topic, gap_detail, severity) VALUES (?, ?, ?, ?)",
            (1, "english", "Gap 2", "medium"),
        )
        conn.execute(
            "INSERT INTO learning_gaps (offer_id, topic, gap_detail, severity) VALUES (?, ?, ?, ?)",
            (1, "tech_stack", "Gap 3", "low"),
        )
        conn.commit()
        conn.close()

        cmd_gaps_stats()
        captured = capsys.readouterr()
        assert "Total gaps: 3" in captured.out
        assert "Tech Stack" in captured.out
        assert "English" in captured.out
