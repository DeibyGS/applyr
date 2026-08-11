"""Tests for analytics module — CV comparison and response rate."""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from applyr.analytics import compare_cvs, response_rate


class TestCompareCvs:
    """Test CV comparison functionality."""

    def test_compare_identical_cvs(self, tmp_path):
        html = "<html><body><h1>Test CV</h1><p>Python developer</p></body></html>"
        v1 = tmp_path / "cv1.html"
        v2 = tmp_path / "cv2.html"
        v1.write_text(html)
        v2.write_text(html)

        result = compare_cvs(str(v1), str(v2))
        assert result["score_delta"] == 0
        assert result["keywords_gained"] == []
        assert result["keywords_lost"] == []

    def test_compare_different_cvs(self, tmp_path):
        v1_html = "<html><body><h1>CV</h1><p>Python JavaScript React</p></body></html>"
        v2_html = "<html><body><h1>CV</h1><p>Python JavaScript React Docker Kubernetes</p></body></html>"
        v1 = tmp_path / "cv1.html"
        v2 = tmp_path / "cv2.html"
        v1.write_text(v1_html)
        v2.write_text(v2_html)

        result = compare_cvs(str(v1), str(v2))
        assert len(result["keywords_gained"]) > 0

    def test_compare_word_count(self, tmp_path):
        v1_html = "<html><body><p>Short CV</p></body></html>"
        v2_html = "<html><body><p>This is a much longer CV with many more words added</p></body></html>"
        v1 = tmp_path / "cv1.html"
        v2 = tmp_path / "cv2.html"
        v1.write_text(v1_html)
        v2.write_text(v2_html)

        result = compare_cvs(str(v1), str(v2))
        assert result["v2"]["word_count"] > result["v1"]["word_count"]

    def test_compare_returns_recommendations(self, tmp_path):
        html = "<html><body><p>Test</p></body></html>"
        v1 = tmp_path / "cv1.html"
        v2 = tmp_path / "cv2.html"
        v1.write_text(html)
        v2.write_text(html)

        result = compare_cvs(str(v1), str(v2))
        assert "recommendations" in result
        assert len(result["recommendations"]) > 0


class TestResponseRate:
    """Test response rate calculation."""

    def test_no_applications(self):
        with patch("applyr.analytics.get_conn") as mock:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            mock.return_value = conn

            conn.execute("""CREATE TABLE offers (
                id INTEGER PRIMARY KEY, title TEXT, company TEXT,
                status TEXT, applied INTEGER, date_applied TEXT, response_status TEXT
            )""")

            result = response_rate(as_json=True)
            # The empty payload carries the same keys as a populated one, so a
            # caller needs a single parser. It used to report `total` here and
            # `total_applications` everywhere else.
            assert result["total_applications"] == 0
            assert result["responded"] == 0
            assert result["message"] == "No applications found"

    def test_all_responded(self):
        with patch("applyr.analytics.get_conn") as mock:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            mock.return_value = conn

            conn.execute("""CREATE TABLE offers (
                id INTEGER PRIMARY KEY, title TEXT, company TEXT,
                status TEXT, applied INTEGER, date_applied TEXT, response_status TEXT
            )""")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('A', 'applied', 1, '2026-01-15', 'contacted')")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('B', 'applied', 1, '2026-01-20', 'interview')")
            conn.commit()

            result = response_rate(as_json=True)
            assert result["total_applications"] == 2
            assert result["responded"] == 2
            assert result["response_rate"] == 100.0

    def test_partial_response(self):
        with patch("applyr.analytics.get_conn") as mock:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            mock.return_value = conn

            conn.execute("""CREATE TABLE offers (
                id INTEGER PRIMARY KEY, title TEXT, company TEXT,
                status TEXT, applied INTEGER, date_applied TEXT, response_status TEXT
            )""")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('A', 'applied', 1, '2026-01-15', 'contacted')")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('B', 'applied', 1, '2026-01-20', 'no_response')")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('C', 'applied', 1, '2026-01-25', 'no_response')")
            conn.commit()

            result = response_rate(as_json=True)
            assert result["total_applications"] == 3
            assert result["responded"] == 1
            assert result["response_rate"] == 33.3

    def test_monthly_trend(self):
        with patch("applyr.analytics.get_conn") as mock:
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            mock.return_value = conn

            conn.execute("""CREATE TABLE offers (
                id INTEGER PRIMARY KEY, title TEXT, company TEXT,
                status TEXT, applied INTEGER, date_applied TEXT, response_status TEXT
            )""")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('A', 'applied', 1, '2026-01-15', 'contacted')")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('B', 'applied', 1, '2026-01-20', 'no_response')")
            conn.execute("INSERT INTO offers (title, status, applied, date_applied, response_status) VALUES ('C', 'applied', 1, '2026-02-10', 'interview')")
            conn.commit()

            result = response_rate(as_json=True)
            assert "monthly_trend" in result
            assert "2026-01" in result["monthly_trend"]
            assert "2026-02" in result["monthly_trend"]
            assert result["monthly_trend"]["2026-01"]["rate"] == 50.0
            assert result["monthly_trend"]["2026-02"]["rate"] == 100.0
