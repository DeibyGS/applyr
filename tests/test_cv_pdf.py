"""`cv pdf` with Chrome faked: what reaches the browser, and what is left on disk."""

import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

import applyr.cv as cv_mod
from applyr.md_render import render_markdown_to_html


@pytest.fixture
def fake_chrome(monkeypatch):
    """Replace Chrome with a recorder that captures the HTML it was given."""
    seen: dict = {}
    config = cv_mod.load_config()
    config["cv"]["chrome_path"] = sys.executable  # any existing file passes the check
    monkeypatch.setattr(cv_mod, "load_config", lambda: config)

    def fake_run(cmd, **_kwargs):
        uri = cmd[-1]
        seen["uri"] = uri
        seen["html"] = Path(unquote(urlparse(uri).path)).read_text(encoding="utf-8")
        pdf = next(a for a in cmd if a.startswith("--print-to-pdf=")).split("=", 1)[1]
        Path(pdf).write_bytes(b"%PDF-1.4\n")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(cv_mod.subprocess, "run", fake_run)
    return seen


def _cv(dir_: Path, body: str, language: str = "es") -> Path:
    path = dir_ / "cv-acme.md"
    path.write_text(f'---\noffer_id: 1\nlanguage: "{language}"\n---\n\n{body}', encoding="utf-8")
    return path


def test_existing_html_next_to_the_cv_survives(tmp_applyr, tmp_path, fake_chrome):
    cv = _cv(tmp_path, "# Ana\n")
    neighbour = tmp_path / "cv-acme.html"
    neighbour.write_text("my hand-edited version")
    cv_mod.cmd_cv_pdf(str(cv))
    assert neighbour.read_text() == "my hand-edited version"
    assert (tmp_path / "cv-acme.pdf").exists()


def test_temp_html_sits_next_to_the_cv_and_is_removed(tmp_applyr, tmp_path, fake_chrome):
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "# Ana\n")))
    temp = Path(unquote(urlparse(fake_chrome["uri"]).path))
    assert temp.parent == tmp_path.resolve()  # snap Chromium can't read /tmp
    assert not temp.exists()


def test_document_language_follows_the_cv(tmp_applyr, tmp_path, fake_chrome):
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "# Ana\n", language="es")))
    assert '<html lang="es">' in fake_chrome["html"]


def test_path_with_url_syntax_is_encoded(tmp_applyr, tmp_path, fake_chrome):
    folder = tmp_path / "CVs #2 100%"
    folder.mkdir()
    cv_mod.cmd_cv_pdf(str(_cv(folder, "# Ana\n")))
    assert (folder / "cv-acme.pdf").exists()


def test_scaffold_comments_do_not_reach_the_pdf(tmp_applyr, tmp_path, fake_chrome):
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "<!-- TAILOR: secret hint -->\n# Ana\n")))
    assert "TAILOR" not in fake_chrome["html"]


def test_accented_text_survives_utf8(tmp_applyr, tmp_path, fake_chrome):
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "# Formación\n\nGestión de APIs\n")))
    assert "Gestión" in fake_chrome["html"]


class TestEscaping:
    def test_angle_brackets_and_ampersands_are_text(self):
        html = render_markdown_to_html("- Built List<T> helpers for R&D <br>\n")
        assert "List&lt;T&gt;" in html
        assert "R&amp;D" in html
        assert "<br>" not in html

    def test_markup_inside_bold_is_escaped_too(self):
        assert "<strong>a &lt;b&gt;</strong>" in render_markdown_to_html("**a <b>**\n")

    def test_links_still_render(self):
        html = render_markdown_to_html("[repo](https://github.com/x/y?a=1&b=2)\n")
        assert '<a href="https://github.com/x/y?a=1&amp;b=2">repo</a>' in html
