"""Tests for input validation logic in commands."""

import pytest

from applyr.commands._helpers import _today, _bar, _truncate, _classify_icon
from applyr.commands.core import _parse_date


@pytest.mark.unit
class TestBar:

    def test_full_bar(self):
        result = _bar(100, width=10)
        assert "█" in result  # Unicode full block
        assert "100%" in result

    def test_empty_bar(self):
        result = _bar(0, width=10)
        assert "░" in result  # Unicode light shade
        assert "0%" in result

    def test_half_bar(self):
        result = _bar(50, width=10)
        assert "█" in result  # Unicode full block
        assert "░" in result  # Unicode light shade
        assert "50%" in result


@pytest.mark.unit
class TestClassifyIcon:

    def test_strong(self):
        icon, text = _classify_icon("strong")
        assert icon == "✓"
        assert text == "Strong"

    def test_partial(self):
        icon, text = _classify_icon("partial")
        assert icon == "△"
        assert text == "Partial"

    def test_missing(self):
        icon, text = _classify_icon("missing")
        assert icon == "✕"
        assert text == "Missing"


@pytest.mark.unit
class TestTruncate:

    def test_none_returns_empty(self):
        assert _truncate(None, 10) == ""

    def test_empty_returns_empty(self):
        assert _truncate("", 10) == ""

    def test_short_string_unchanged(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length(self):
        assert _truncate("1234567890", 10) == "1234567890"

    def test_long_string_truncated(self):
        result = _truncate("hello world!", 10)
        assert len(result) == 10
        assert result.endswith("…")


@pytest.mark.unit
class TestParseDate:

    def test_iso_format(self):
        assert _parse_date("2026-08-07") == "2026-08-07"

    def test_slash_format(self):
        assert _parse_date("07/08/2026") == "2026-08-07"

    def test_dash_dmy_format(self):
        assert _parse_date("07-08-2026") == "2026-08-07"

    def test_invalid_returns_none(self):
        assert _parse_date("not-a-date") is None

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_empty_returns_none(self):
        assert _parse_date("") is None


@pytest.mark.unit
class TestDuplicateDetection:

    def test_duplicate_detected(self, tmp_db):
        from applyr.db import get_conn
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, status) VALUES (?, ?, ?)",
                ("Backend Dev", "Acme", "applied"),
            )
            conn.commit()
            dup = conn.execute(
                """SELECT id FROM offers
                   WHERE LOWER(title) = LOWER(?) AND LOWER(COALESCE(company,'')) = LOWER(COALESCE(?,''))""",
                ("backend dev", "acme"),
            ).fetchone()
            assert dup is not None
            assert dup["id"] == 1
        finally:
            conn.close()

    def test_different_title_no_duplicate(self, tmp_db):
        from applyr.db import get_conn
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, status) VALUES (?, ?, ?)",
                ("Backend Dev", "Acme", "applied"),
            )
            conn.commit()
            dup = conn.execute(
                """SELECT id FROM offers
                   WHERE LOWER(title) = LOWER(?) AND LOWER(COALESCE(company,'')) = LOWER(COALESCE(?,''))""",
                ("Frontend Dev", "Acme"),
            ).fetchone()
            assert dup is None
        finally:
            conn.close()

    def test_null_company_is_rejected_by_the_db(self, tmp_db):
        """A NULL/empty company used to slip past duplicate detection entirely
        (nothing to match against) and left offers no follow-up could act on
        — see the NOT NULL + non-empty CHECK constraint added in schema v10.
        The COALESCE in the queries above stays as defense in depth, but this
        specific gap can no longer reach the database at all."""
        import sqlite3

        from applyr.db import get_conn
        conn = get_conn(tmp_db)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO offers (title, company, status) VALUES (?, ?, ?)",
                    ("Dev", None, "pending"),
                )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO offers (title, company, status) VALUES (?, ?, ?)",
                    ("Dev", "   ", "pending"),
                )
        finally:
            conn.close()
