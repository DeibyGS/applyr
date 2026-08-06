"""Tests for input validation logic in commands."""

import pytest

from applyr.commands._helpers import _today, _bar, _truncate
from applyr.commands.core import _parse_date


@pytest.mark.unit
class TestToday:

    def test_returns_iso_format(self):
        result = _today()
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"


@pytest.mark.unit
class TestBar:

    def test_full_bar(self):
        result = _bar(100, width=10)
        assert result == "[##########]"

    def test_empty_bar(self):
        result = _bar(0, width=10)
        assert result == "[----------]"

    def test_half_bar(self):
        result = _bar(50, width=10)
        assert result == "[#####-----]"


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

    def test_null_company_match(self, tmp_db):
        from applyr.db import get_conn
        conn = get_conn(tmp_db)
        try:
            conn.execute(
                "INSERT INTO offers (title, company, status) VALUES (?, ?, ?)",
                ("Dev", None, "pending"),
            )
            conn.commit()
            dup = conn.execute(
                """SELECT id FROM offers
                   WHERE LOWER(title) = LOWER(?) AND LOWER(COALESCE(company,'')) = LOWER(COALESCE(?,''))""",
                ("Dev", None),
            ).fetchone()
            assert dup is not None
        finally:
            conn.close()
