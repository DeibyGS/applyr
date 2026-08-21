"""Tests for the language a generated CV is written in.

A CV whose bullets are Spanish under an English heading reads as machine-made to
the recruiter, and an ATS scanning it for "EXPERIENCIA" matches nothing. The
language is therefore a fact recorded on the offer, not a flag passed at
generation time — these tests pin that it reaches the skeleton either way.
"""

import pytest

from applyr.cv import CV_HEADINGS, resolve_cv_language
from applyr.db import VALID_LANGUAGES, get_conn


class TestResolveCvLanguage:
    """Which language wins, and what happens when nobody chose one."""

    def test_offer_language_wins(self, tmp_applyr):
        assert resolve_cv_language("es") == "es"

    def test_falls_back_to_configured_default(self, tmp_applyr):
        """An offer recorded before v1.1.0 carries no language."""
        assert resolve_cv_language(None) == "en"

    def test_unknown_language_falls_back_rather_than_raising(self, tmp_applyr):
        """A hand-edited config must not break a command mid-application."""
        assert resolve_cv_language("klingon") == "en"

    def test_every_valid_language_has_headings(self):
        """VALID_LANGUAGES promises a CV can be written — headings must exist."""
        assert set(VALID_LANGUAGES) == set(CV_HEADINGS)

    def test_all_languages_define_the_same_headings(self):
        """A missing key would raise KeyError halfway through building a CV."""
        keys = [set(headings) for headings in CV_HEADINGS.values()]
        assert all(k == keys[0] for k in keys)


class TestGeneratedSkeletonLanguage:
    """The headings that reach the file the agent fills in."""

    @pytest.fixture
    def spanish_offer(self, tmp_applyr, tmp_db):
        from applyr.commands.core import cmd_add

        (tmp_applyr / "cv-master.md").write_text(
            "# CV Master\n\n## Experiencia\n" + "Experiencia real. " * 40
        )
        cmd_add('{"title": "Programador Junior", "company": "Acme", "language": "es"}')
        conn = get_conn()
        try:
            return conn.execute("SELECT MAX(id) AS id FROM offers").fetchone()["id"]
        finally:
            conn.close()

    def test_spanish_offer_gets_spanish_headings(self, spanish_offer, tmp_applyr):
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(spanish_offer)
        md = next((tmp_applyr / "cv").glob("*.md")).read_text()
        assert "## Experiencia Profesional" in md
        assert "## Formación" in md
        assert "## Habilidades Técnicas" in md

    def test_spanish_offer_keeps_no_english_headings(self, spanish_offer, tmp_applyr):
        """The v1.0.0 bug: Spanish content delivered under English headings."""
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(spanish_offer)
        md = next((tmp_applyr / "cv").glob("*.md")).read_text()
        for english in ("## Work Experience", "## Education", "## Technical Skills",
                        "## Professional Summary", "## Certifications"):
            assert english not in md

    def test_skeleton_states_the_language_for_the_agent(self, spanish_offer, tmp_applyr):
        """The headings alone do not tell the agent what to do with the rest."""
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(spanish_offer)
        md = next((tmp_applyr / "cv").glob("*.md")).read_text()
        assert "write every line of this CV in Spanish" in md
        assert 'language: "es"' in md


class TestLanguageValidation:
    """`add` must refuse a language applyr cannot actually write."""

    def test_rejects_unsupported_language(self, tmp_applyr, tmp_db):
        from applyr.commands.core import cmd_add

        with pytest.raises(SystemExit):
            cmd_add('{"title": "Dev", "language": "de"}')

    def test_accepts_offer_without_language(self, tmp_applyr, tmp_db):
        from applyr.commands.core import cmd_add

        cmd_add('{"title": "Dev", "company": "Acme"}')  # must not raise
