"""Tests for cv-master.md inspection — the guard that stops a CV built on nothing.

Every claim in a generated CV traces back to cv-master.md, so this check is what
stands between an unfilled template and a CV full of invented experience. The
cases below are written against real user behaviour rather than byte counts: the
v1.0.0 bug was a size threshold that the very first edit a new user makes —
typing their own name — was enough to satisfy.
"""

from applyr.commands.core import _CV_MASTER_TEMPLATE
from applyr.cv_master import MIN_CONTENT_WORDS, inspect_cv_master


def _profile(words: int = 60) -> str:
    """A cv-master with real content and no placeholders."""
    return "# CV Master — Real Person\n\n## Experience\n" + "Shipped a thing. " * words


class TestUnfilledTemplate:
    """The skeleton `applyr init` writes must never read as a profile."""

    def test_shipped_template_is_not_filled(self):
        report = inspect_cv_master(_CV_MASTER_TEMPLATE.format(name="Your Name"))
        assert not report.filled

    def test_naming_the_template_does_not_make_it_filled(self):
        """The v1.0.0 bug: a longer name pushed the file past the size threshold.

        Typing your own name is the first edit anyone makes, and it left the
        sections as empty as before — so it must not flip the verdict.
        """
        report = inspect_cv_master(_CV_MASTER_TEMPLATE.format(name="Deiby Gorrin Santana"))
        assert not report.filled

    def test_names_the_sections_left_unfilled(self):
        """Refusing is not enough — the report has to say what to write."""
        report = inspect_cv_master(_CV_MASTER_TEMPLATE.format(name="Your Name"))
        assert set(report.placeholder_sections) == {"Summary", "Experience", "Education", "Skills"}
        assert "Summary" in report.reason

    def test_one_placeholder_left_among_real_content_still_fails(self):
        """A half-filled profile invents whatever the untouched section covers."""
        report = inspect_cv_master(_profile() + "\n\n## Education\n...\n")
        assert not report.filled
        assert report.placeholder_sections == ("Education",)

    def test_content_without_placeholders_but_too_thin_fails(self):
        report = inspect_cv_master("# CV Master\n\n## Summary\nDeveloper.\n")
        assert not report.filled
        assert "too thin" in report.reason


class TestFilledProfile:
    """A real profile must pass, however it happens to be written."""

    def test_a_real_profile_is_filled(self):
        report = inspect_cv_master(_profile())
        assert report.filled
        assert report.reason is None

    def test_prose_profile_on_a_single_line_is_filled(self):
        """Substance is words, not lines — one long paragraph is a valid CV."""
        report = inspect_cv_master("# CV Master\n\n" + "Real experience. " * 200)
        assert report.filled

    def test_non_english_headings_are_filled(self):
        """Section names are never matched: a Spanish profile is just as valid."""
        report = inspect_cv_master(
            "# CV Master — Deiby\n\n## PERFIL PROFESIONAL\n"
            + "Desarrollador junior con experiencia real. " * 20
        )
        assert report.filled

    def test_headings_do_not_count_as_content(self):
        """A file of nothing but section titles describes no career."""
        headings = "\n".join(f"## Section {n}" for n in range(MIN_CONTENT_WORDS * 2))
        report = inspect_cv_master(headings)
        assert not report.filled
        assert report.content_words == 0
