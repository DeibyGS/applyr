"""Regression tests for the CV pipeline.

Every test here pins a bug found while generating a real CV end to end.
"""

import json

import pytest

from applyr.cv import (
    _ATS_CSS,
    _count_pdf_pages,
    _make_slug,
    _page_limit_for,
    _strip_html_tags,
)


class TestMakeSlug:
    """Slugs feed filenames, so they must never need shell quoting.

    Company only, not title — the user wants CV filenames to read as who
    it's going to, not the job title (e.g. cv-acme.md, not
    cv-acme-innovacion-y-personas-desarrollador.md).
    """

    def test_strips_parentheses(self):
        assert _make_slug("Fusuma (Spain)") == "fusuma-spain"

    def test_strips_accents_and_symbols(self):
        slug = _make_slug("Acme & Co.")
        assert all(c.isalnum() or c == "-" for c in slug)

    def test_no_leading_or_trailing_dash(self):
        slug = _make_slug("(Acme)")
        assert not slug.startswith("-")
        assert not slug.endswith("-")

    def test_missing_company_falls_back(self):
        assert _make_slug(None) == "unknown"

    def test_never_returns_empty(self):
        assert _make_slug("!!!") == "cv"


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

    def test_second_offer_at_same_company_gets_id_suffix(self, offer_id, tmp_applyr):
        """Applying to a second role at the same company is normal (see
        duplicates.py) — the second CV must get its own file, not collide
        with or overwrite the first one."""
        from applyr.commands.core import cmd_add
        from applyr.cv import cmd_cv_generate

        cmd_cv_generate(offer_id)  # writes cv-fusuma.md for offer #1

        cmd_add(json.dumps({
            "title": "Backend Lead",
            "company": "Fusuma",
            "topics": {"experience": {"score": 80, "detail": "5 years"}},
        }))
        cmd_cv_generate(2)  # must not raise: different offer, same company

        cv_dir = tmp_applyr / "cv"
        assert (cv_dir / "cv-fusuma.md").exists()
        assert (cv_dir / "cv-fusuma-2.md").exists()

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

    def test_finds_cv_when_output_dir_differs_from_applyr_dir(self, offer_id, tmp_applyr, monkeypatch, tmp_path):
        """The lookup hardcoded APPLYR_DIR / "cv" instead of reading the
        configured output_dir, so it stopped finding CVs the moment CV_HOME
        diverged from APPLYR_DIR — exactly the setup generated CVs now default
        to (they live outside the config directory)."""
        import applyr.config as cfg
        from applyr.cv import cmd_cv_generate, cmd_cv_keywords

        # cv_master defaults under CV_HOME too (matches production: both the
        # profile and generated CVs live outside APPLYR_DIR now), so moving
        # CV_HOME here means the fixture's cv-master.md must move with it.
        other_dir = tmp_path / "elsewhere"
        other_dir.mkdir()
        (other_dir / "cv-master.md").write_text((tmp_applyr / "cv-master.md").read_text())
        monkeypatch.setattr(cfg, "CV_HOME", other_dir)

        cmd_cv_generate(offer_id)
        assert not (tmp_applyr / "cv").exists()
        assert (other_dir / "cv").exists()

        cmd_cv_keywords(offer_id)  # must not raise "No CV found"

    def test_non_utf8_cv_file_dies_with_a_clear_message(self, offer_id, tmp_applyr, capsys):
        """A hand-edited CV saved with the wrong encoding must not crash with
        a raw UnicodeDecodeError — same bug class as ats-check (offer #235,
        2026-08-18), reached here through the DB-resolved path instead of a
        user-supplied one."""
        from applyr.cv import cmd_cv_generate, cmd_cv_keywords

        cmd_cv_generate(offer_id)
        cv_path = next((tmp_applyr / "cv").glob("*.md"))
        cv_path.write_bytes(b"\xff\xfe not valid utf-8")

        with pytest.raises(SystemExit):
            cmd_cv_keywords(offer_id)
        err = capsys.readouterr().err
        assert "not readable as text" in err


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


class TestCvCoverLetter:
    """The cover letter writer hardcoded APPLYR_DIR / "cv" too, so it wrote
    outside the folder `applyr cv keywords` and the user were both looking in
    the moment output_dir diverged from APPLYR_DIR."""

    def test_writes_to_configured_output_dir(self, offer_id, tmp_applyr, monkeypatch, tmp_path):
        import applyr.config as cfg
        from applyr.db import get_conn
        from applyr.cv import cmd_cv_cover_letter

        # generate_cover_letter() needs a non-null tech_stack; the shared
        # `offer_id` fixture does not set one.
        conn = get_conn()
        conn.execute("UPDATE offers SET tech_stack = ? WHERE id = ?", ("Python", offer_id))
        conn.commit()
        conn.close()

        other_dir = tmp_path / "elsewhere"
        other_dir.mkdir()
        (other_dir / "cv-master.md").write_text((tmp_applyr / "cv-master.md").read_text())
        monkeypatch.setattr(cfg, "CV_HOME", other_dir)

        cmd_cv_cover_letter(offer_id)

        assert list((other_dir / "cv").glob("cover-letter-*.txt"))
        assert not (tmp_applyr / "cv").exists()


class TestCountPdfPages:
    """No PDF library dependency — pages are counted from raw PDF bytes."""

    def test_counts_page_objects(self, tmp_path):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"1 0 obj <</Type /Page>> endobj 2 0 obj <</Type /Page>> endobj")
        assert _count_pdf_pages(pdf) == 2

    def test_does_not_count_the_pages_tree_root(self, tmp_path):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"1 0 obj <</Type /Pages /Count 1>> endobj 2 0 obj <</Type /Page>> endobj")
        assert _count_pdf_pages(pdf) == 1

    def test_no_match_returns_none(self, tmp_path):
        pdf = tmp_path / "cv.pdf"
        pdf.write_bytes(b"not really a pdf")
        assert _count_pdf_pages(pdf) is None


class TestPageLimitFor:
    """1 page by default, 2 for senior/lead/director — matching the rule
    `cv review` already states in its rubric."""

    def test_html_file_defaults_to_one_page(self, tmp_path):
        html = tmp_path / "cv.html"
        html.write_text("<html></html>")
        assert _page_limit_for(html) == 1

    def test_md_without_offer_id_defaults_to_one_page(self, tmp_path):
        md = tmp_path / "cv.md"
        md.write_text("# CV\n\nNo frontmatter here.")
        assert _page_limit_for(md) == 1

    def test_mid_seniority_gets_one_page(self, tmp_db, tmp_applyr, tmp_path):
        from applyr.commands.core import cmd_add

        cmd_add(json.dumps({"title": "Backend Dev", "company": "Acme", "seniority_level": "mid"}))
        md = tmp_path / "cv.md"
        md.write_text("---\noffer_id: 1\n---\nbody")
        assert _page_limit_for(md) == 1

    def test_senior_seniority_gets_two_pages(self, tmp_db, tmp_applyr, tmp_path):
        from applyr.commands.core import cmd_add

        cmd_add(json.dumps({"title": "Staff Eng", "company": "Acme", "seniority_level": "senior"}))
        md = tmp_path / "cv.md"
        md.write_text("---\noffer_id: 1\n---\nbody")
        assert _page_limit_for(md) == 2


class TestCvAtsCheck:
    """`applyr cv ats-check` reads the CV source, not the rendered output.

    Until this fix, passing the .pdf `cv pdf` produces raised a bare
    UnicodeDecodeError from read_text() instead of a clear, actionable error —
    found auditing a real offer (Zinco, #235) on 2026-08-18.
    """

    def test_pdf_input_dies_with_a_clear_message_not_a_stack_trace(self, tmp_path):
        from applyr.cv import cmd_cv_ats_check

        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nnot valid utf-8: \xff\xfe")

        with pytest.raises(SystemExit):
            cmd_cv_ats_check(str(pdf))

    def test_hints_at_the_sibling_md_when_it_exists(self, tmp_path, capsys):
        from applyr.cv import cmd_cv_ats_check

        (tmp_path / "cv-zinco.md").write_text("# CV\n")
        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(b"\xff\xfe not text")

        with pytest.raises(SystemExit):
            cmd_cv_ats_check(str(pdf))
        err = capsys.readouterr().err
        assert str(tmp_path / "cv-zinco.md") in err

    def test_omits_the_hint_when_no_sibling_md_exists(self, tmp_path, capsys):
        from applyr.cv import cmd_cv_ats_check

        pdf = tmp_path / "cv-orphan.pdf"
        pdf.write_bytes(b"\xff\xfe not text")

        with pytest.raises(SystemExit):
            cmd_cv_ats_check(str(pdf))
        err = capsys.readouterr().err
        assert "rendered PDF" in err

    def test_hints_at_the_sibling_html_when_no_md_exists(self, tmp_path, capsys):
        """cv pdf can be run directly on an .html source (legacy support) —
        the hint must not assume .md is the only valid sibling."""
        from applyr.cv import cmd_cv_ats_check

        (tmp_path / "cv-zinco.html").write_text("<html></html>")
        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(b"\xff\xfe not text")

        with pytest.raises(SystemExit):
            cmd_cv_ats_check(str(pdf))
        err = capsys.readouterr().err
        assert str(tmp_path / "cv-zinco.html") in err

    def test_does_not_point_back_at_itself_when_the_md_is_the_broken_file(self, tmp_path, capsys):
        """If cv-acme.md itself is non-UTF-8 (e.g. pasted from Word as
        cp1252), with_suffix('.md') on a path already ending in .md returns
        the same path — the hint must not tell the user to retry the exact
        file that just failed."""
        from applyr.cv import cmd_cv_ats_check

        broken_md = tmp_path / "cv-acme.md"
        broken_md.write_bytes(b"\xff\xfe not utf-8")

        with pytest.raises(SystemExit):
            cmd_cv_ats_check(str(broken_md))
        err = capsys.readouterr().err
        # The message legitimately names the broken file ("X is not a text
        # file") — what must NOT happen is the retry hint suggesting the
        # user run the command again on that same broken file.
        assert f"Try: applyr cv ats-check {broken_md}" not in err
        assert "rendered PDF" in err
        assert "rendered PDF" in err


class TestCvReview:
    """Same bug class as TestCvAtsCheck: `cv review` is the single most-invoked
    command in the documented agent workflow (called in a loop until READY TO
    SEND) and, until this fix, was the one sibling command that never got the
    UnicodeDecodeError guard from PR #71."""

    INVALID_PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nnot valid utf-8: \xff\xfe"

    def test_missing_file_dies_with_a_clear_message_not_a_stack_trace(self, tmp_path):
        from applyr.cv import cmd_cv_review

        missing = tmp_path / "does-not-exist.md"
        with pytest.raises(SystemExit):
            cmd_cv_review(str(missing))

    def test_pdf_input_dies_with_a_clear_message_not_a_stack_trace(self, tmp_path):
        from applyr.cv import cmd_cv_review

        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(self.INVALID_PDF)

        with pytest.raises(SystemExit):
            cmd_cv_review(str(pdf))

    def test_pdf_input_dies_the_same_way_in_json_mode(self, tmp_path, capsys):
        from applyr.cv import cmd_cv_review
        from applyr.errors import set_json_mode

        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(self.INVALID_PDF)

        set_json_mode(True)
        try:
            with pytest.raises(SystemExit):
                cmd_cv_review(str(pdf), as_json=True)
        finally:
            set_json_mode(False)
        payload = json.loads(capsys.readouterr().err)
        assert payload["error"]["code"] == "unsupported_format"


class TestCvBulletOptimize:
    """Same bug class as TestCvAtsCheck: `cv bullet-optimize` also takes a
    user-supplied file path directly and hit the identical bare
    UnicodeDecodeError on a rendered PDF."""

    def test_pdf_input_dies_with_a_clear_message_not_a_stack_trace(self, tmp_path):
        from applyr.cv import cmd_cv_bullet_optimize

        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\nnot valid utf-8: \xff\xfe")

        with pytest.raises(SystemExit):
            cmd_cv_bullet_optimize(str(pdf))

    def test_hints_at_the_sibling_md_when_it_exists(self, tmp_path, capsys):
        from applyr.cv import cmd_cv_bullet_optimize

        (tmp_path / "cv-zinco.md").write_text("# CV\n")
        pdf = tmp_path / "cv-zinco.pdf"
        pdf.write_bytes(b"\xff\xfe not text")

        with pytest.raises(SystemExit):
            cmd_cv_bullet_optimize(str(pdf))
        err = capsys.readouterr().err
        assert str(tmp_path / "cv-zinco.md") in err
