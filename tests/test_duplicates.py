"""Tests for duplicate detection — title normalization and similarity matching."""

import pytest

from applyr.constants import DUPLICATE_SIMILARITY_THRESHOLD
from applyr.duplicates import (
    find_company_offers,
    find_exact,
    find_similar,
    normalize_company,
    normalize_title,
    title_similarity,
)


class TestNormalizeTitle:
    def test_lowercases(self):
        assert normalize_title("Backend Engineer") == "backend engineer"

    def test_strips_parenthetical_qualifier(self):
        assert normalize_title("Backend Engineer (Remote)") == "backend engineer"

    def test_strips_brackets_and_braces(self):
        assert normalize_title("Backend Engineer [Madrid]") == "backend engineer"
        assert normalize_title("Backend Engineer {m/f/d}") == "backend engineer"

    def test_strips_punctuation(self):
        assert normalize_title("Back-end Engineer, Senior!") == "back end engineer senior"

    def test_collapses_whitespace(self):
        assert normalize_title("  Backend    Engineer  ") == "backend engineer"

    def test_preserves_seniority(self):
        # Seniority changes the role — it must survive normalization
        assert normalize_title("Senior Backend Engineer") == "senior backend engineer"
        assert normalize_title("Senior Backend Engineer") != normalize_title("Backend Engineer")

    def test_title_that_is_only_a_qualifier_becomes_empty(self):
        assert normalize_title("(Remote)") == ""


class TestTitleSimilarity:
    def test_identical_titles_score_one(self):
        assert title_similarity("Backend Engineer", "Backend Engineer") == 1.0

    def test_remote_variant_is_identical_after_normalization(self):
        assert title_similarity("Backend Engineer", "Backend Engineer (Remote)") == 1.0

    def test_case_and_punctuation_do_not_matter(self):
        assert title_similarity("BACKEND ENGINEER!", "backend engineer") == 1.0

    def test_different_roles_score_low(self):
        assert title_similarity("Backend Engineer", "Marketing Manager") < 0.5

    def test_seniority_difference_stays_below_threshold(self):
        # "Senior Backend Engineer" must not be swallowed as a variant
        score = title_similarity("Backend Engineer", "Senior Backend Engineer")
        assert score < DUPLICATE_SIMILARITY_THRESHOLD

    def test_empty_title_scores_zero(self):
        assert title_similarity("", "Backend Engineer") == 0.0
        assert title_similarity("(Remote)", "Backend Engineer") == 0.0


class FakeRow(dict):
    """Minimal stand-in for sqlite3.Row — supports subscript access."""


class TestFindSimilar:
    def test_returns_none_on_empty_list(self):
        assert find_similar([], "Backend Engineer") is None

    def test_finds_formatting_variant(self):
        rows = [FakeRow(id=1, title="Backend Engineer (Remote)")]
        match = find_similar(rows, "Backend Engineer")
        assert match is not None
        assert match[0]["id"] == 1
        assert match[1] == 1.0

    def test_ignores_unrelated_titles(self):
        rows = [FakeRow(id=1, title="Marketing Manager")]
        assert find_similar(rows, "Backend Engineer") is None

    def test_returns_closest_match_when_several_qualify(self):
        rows = [
            FakeRow(id=1, title="Backend Engineerr"),        # close typo
            FakeRow(id=2, title="Backend Engineer (Remote)"),  # exact after normalization
        ]
        match = find_similar(rows, "Backend Engineer")
        assert match[0]["id"] == 2
        assert match[1] == 1.0

    def test_respects_custom_threshold(self):
        rows = [FakeRow(id=1, title="Senior Backend Engineer")]
        assert find_similar(rows, "Backend Engineer", threshold=0.99) is None
        assert find_similar(rows, "Backend Engineer", threshold=0.5) is not None

    @pytest.mark.parametrize("variant", [
        "Backend Engineer (Remote)",
        "Backend Engineer [Hybrid]",
        "Backend Engineer, Remote",
        "backend engineer",
        "Backend  Engineer",
    ])
    def test_common_posting_variants_are_caught(self, variant):
        rows = [FakeRow(id=1, title=variant)]
        assert find_similar(rows, "Backend Engineer") is not None


class TestNormalizeCompany:
    def test_lowercases(self):
        assert normalize_company("Acme Corp") == "acme corp"

    def test_strips_diacritics(self):
        assert normalize_company("Mática Partners") == "matica partners"

    def test_already_unaccented_is_unchanged_besides_case(self):
        assert normalize_company("Matica Partners") == "matica partners"

    def test_none_becomes_empty_string(self):
        assert normalize_company(None) == ""


class TestFindExactAndFindCompanyOffers:
    """Found via a real offer: "Mática Partners" and "Matica Partners" were
    treated as two different companies because the SQL comparison only
    lowercased, never stripped accents — so add's duplicate warning and
    search --company silently missed real history at the same company.
    """

    @pytest.fixture
    def conn(self, tmp_db):
        from applyr.db import get_conn

        connection = get_conn(tmp_db)
        connection.execute(
            "INSERT INTO offers (title, company) VALUES (?, ?)",
            ("IA Engineer", "Matica Partners"),
        )
        connection.commit()
        return connection

    def test_find_company_offers_ignores_accent_differences(self, conn):
        rows = find_company_offers(conn, "Mática Partners")
        assert len(rows) == 1
        assert rows[0]["title"] == "IA Engineer"

    def test_find_exact_ignores_accent_differences(self, conn):
        row = find_exact(conn, "IA Engineer", "Mática Partners")
        assert row is not None

    def test_find_exact_still_requires_the_same_title(self, conn):
        row = find_exact(conn, "Backend Developer", "Mática Partners")
        assert row is None
