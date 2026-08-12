"""Regression tests for the CV pipeline.

Every test here pins a bug found while generating a real CV end to end.
"""

import json

import pytest

from applyr.cv import _ATS_CSS, _make_slug, _strip_html_tags


class TestMakeSlug:
    """Slugs feed filenames, so they must never need shell quoting."""

    def test_strips_parentheses(self):
        assert _make_slug("Fusuma", "Full Stack (JS)") == "fusuma-full-stack-js"

    def test_strips_accents_and_symbols(self):
        slug = _make_slug("Acme & Co.", "Dev/Ops @ Scale")
        assert all(c.isalnum() or c == "-" for c in slug)

    def test_no_leading_or_trailing_dash(self):
        slug = _make_slug("(Acme)", "(Dev)")
        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_missing_company_falls_back(self):
        assert _make_slug(None, "Backend Dev").startswith("unknown-")

    def test_never_returns_empty(self):
        assert _make_slug("!!!", "???") == "cv"


class TestAtsCss:
    def test_zeroes_the_page_margin(self):
        """Chrome adds a default page margin on top of the body padding,
        which pushes a one-page CV onto a second page."""
        assert "@page" in _ATS_CSS
        assert "margin: 0" in _ATS_CSS

    def test_stays_single_column(self):
        for banned in ("display: flex", "display: grid", "float:"):
            assert banned not in _ATS_CSS


class TestStripHtmlTags:
    def test_removes_style_block(self):
        html = "<style>body { color: red; }</style><p>Real content</p>"
        text = _strip_html_tags(html)
        assert "color" not in text
        assert "Real content" in text

    def test_removes_script_block_without_undoing_style_removal(self):
        """The two substitutions must chain; an early version restarted from
        the original html and silently kept the whole stylesheet."""
        html = "<style>.a{color:red}</style><script>var x=1;</script><p>Keep</p>"
        text = _strip_html_tags(html)
        assert "color" not in text
        assert "var x" not in text
        assert "Keep" in text

    def test_removes_comments(self):
        html = "<!-- internal scoring notes --><p>Visible</p>"
        text = _strip_html_tags(html)
        assert "scoring" not in text
        assert "Visible" in text


@pytest.fixture
def offer_id(tmp_db, tmp_applyr):
    """Register one scored offer and a usable cv-master."""
    from applyr.commands.core import cmd_add

    (tmp_applyr / "cv-master.md").write_text(
        "# CV Master\n\n## Summary\n" + "Fullstack developer. " * 20
    )
    cmd_add(json.dumps({
        "title": "Full Stack (JS)",
        "company": "Fusuma",
        "topics": {"experience": {"score": 20, "detail": "no professional experience"}},
    }))
    return 1


class TestCvGenerate:
    def test_refuses_to_overwrite_existing_cv(self, offer_id, tmp_applyr):
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(offer_id)
        with pytest.raises(SystemExit):
            cmd_cv_generate(offer_id)

    def test_force_overwrites(self, offer_id):
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(offer_id)
        cmd_cv_generate(offer_id, force=True)  # must not raise

    def test_refuses_stub_cv_master(self, offer_id, tmp_applyr):
        """An unfilled template generates a CV nobody can fill in."""
        from applyr.cv import cmd_cv_generate

        (tmp_applyr / "cv-master.md").write_text("# CV Master\n\n## Summary\n...\n")
        with pytest.raises(SystemExit):
            cmd_cv_generate(offer_id)

    def test_refuses_a_stub_that_is_not_small(self, offer_id, tmp_applyr):
        """The refusal must read the file, not weigh it.

        Until v1.0.0 this guard was a size threshold, so a stub padded with
        anything at all — here, a long name and a filled-in contact block —
        passed while every section it would draw from was still empty.
        """
        from applyr.cv import cmd_cv_generate

        (tmp_applyr / "cv-master.md").write_text(
            "# CV Master — Deiby Gorrin Santana\n\n"
            "## Contact\nMadrid, Spain | deiby@example.com | linkedin.com/in/example\n\n"
            "## Summary\n...\n\n## Experience\n...\n"
        )
        with pytest.raises(SystemExit):
            cmd_cv_generate(offer_id)

    def test_keeps_topic_scores_out_of_the_md(self, offer_id, tmp_applyr):
        """Candid self-assessment must not ship inside the recruiter's file."""
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(offer_id)
        md = next((tmp_applyr / "cv").glob("*.md")).read_text()
        assert "no professional experience" not in md
        assert "Topic Scores" not in md

    def test_embeds_offer_id_in_frontmatter(self, offer_id, tmp_applyr):
        """cv review resolves scores from the database through this marker."""
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(offer_id)
        md = next((tmp_applyr / "cv").glob("*.md")).read_text()
        assert f"offer_id: {offer_id}" in md


class TestCvKeywords:
    """`applyr cv keywords <id>` must tell a missing offer apart from a missing CV."""

    def test_missing_offer_dies(self, tmp_db, tmp_applyr):
        """A non-existent offer must fail loudly, not be treated as found.

        Until v1.4.0 the null check was inverted (`if not offer is None`), so a
        missing offer slipped past the guard and crashed on `dict(None)`.
        """
        from applyr.cv import cmd_cv_keywords

        with pytest.raises(SystemExit):
            cmd_cv_keywords(999)

    def test_existing_offer_proceeds_past_null_check(self, offer_id, capsys):
        """The inverted check killed existing offers as 'not found'. An existing
        offer must reach the CV lookup instead, failing there for its own reason."""
        from applyr.cv import cmd_cv_keywords

        with pytest.raises(SystemExit):
            cmd_cv_keywords(offer_id)
        err = capsys.readouterr().err
        assert "not found" not in err
        assert "No CV found" in err


class TestKeywordMatchingIgnoresFrontmatter:
    """`cv keywords` matched the offer's keywords against the whole generated
    file — including the YAML frontmatter, which carries a verbatim copy of the
    offer's own `tech_stack` and `summary`. Every required keyword was therefore
    guaranteed to appear, so every generated CV scored 100% STRONG regardless of
    its content. A real CV mentioning neither AWS nor Redux nor Webpack was
    reported as covering all three."""

    CV = """---
offer_id: 210
tech_stack: "React.js, Redux, Webpack, AWS"
summary: "Frontend con React.js, Redux, Webpack. Cloud-native sobre AWS."
---

# Jane Doe

## Technical Skills

**Frontend:** React.js | TypeScript | CSS
"""

    def test_strip_frontmatter_removes_the_block(self):
        from applyr.cv import _strip_frontmatter

        body = _strip_frontmatter(self.CV)
        assert "tech_stack" not in body
        assert "# Jane Doe" in body

    def test_offer_keywords_do_not_leak_from_frontmatter(self):
        from applyr.ats import match_keywords
        from applyr.cv import _strip_frontmatter

        keywords = ["react.js", "redux", "webpack", "aws"]
        report = match_keywords(_strip_frontmatter(self.CV), keywords)
        matched = {m.keyword.lower() for m in report.matched}

        assert "react.js" in matched, "a skill the CV really lists must still match"
        for absent in ("redux", "webpack", "aws"):
            assert absent not in matched, f"{absent} appears only in the frontmatter"

    def test_a_document_without_frontmatter_is_untouched(self):
        from applyr.cv import _strip_frontmatter

        plain = "# Jane Doe\n\nSome content.\n"
        assert _strip_frontmatter(plain) == plain

    def test_unterminated_frontmatter_is_left_alone(self):
        """A malformed opening must not swallow the entire document."""
        from applyr.cv import _strip_frontmatter

        broken = "---\noffer_id: 1\n\n# Jane Doe\n"
        assert "# Jane Doe" in _strip_frontmatter(broken)
