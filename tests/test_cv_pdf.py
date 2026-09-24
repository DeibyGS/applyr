"""`cv pdf` with Chrome faked: what reaches the browser, and what is left on disk."""

import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

import applyr.cv as cv_mod
from applyr.md_render import render_markdown_to_html


@pytest.fixture
def chrome(monkeypatch):
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


@pytest.fixture
def fake_chrome(chrome, monkeypatch):
    """Faked Chrome with the verify gate bypassed — for tests about rendering only."""
    monkeypatch.setattr(cv_mod, "_check_pdf_gate", lambda _path, _force: (None, None))
    return chrome


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


# ---------------------------------------------------------------------------
# Verify gate (ADR-015): cv pdf renders only a CV that passes cv verify now
# ---------------------------------------------------------------------------

@pytest.fixture
def gated(tmp_db, tmp_applyr, monkeypatch):
    """A linked offer (#1, with existing notes) and a minimal cv-master.md."""
    from applyr.db import get_conn

    monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
    (tmp_applyr / "cv-master.md").write_text("## TECHNICAL SKILLS\n\nLanguages: Python\n")
    conn = get_conn(tmp_db)
    conn.execute("INSERT INTO offers (title, company, notes) VALUES ('Dev', 'Acme', 'call Monday')")
    conn.commit()
    conn.close()
    return tmp_db


def _offer_row(db):
    from applyr.db import get_conn
    conn = get_conn(db)
    try:
        return conn.execute("SELECT notes, cv_evidence_used FROM offers WHERE id = 1").fetchone()
    finally:
        conn.close()


def _exit_code(capsys, fn):
    from applyr.errors import set_json_mode
    import json
    set_json_mode(True)
    try:
        with pytest.raises(SystemExit) as exc:
            fn()
    finally:
        set_json_mode(False)
    assert exc.value.code == 1
    return json.loads(capsys.readouterr().err.strip().splitlines()[-1])["error"]


def test_unverified_cv_is_refused_and_no_pdf_is_written(gated, tmp_path, chrome, capsys):
    cv = _cv(tmp_path, "# [FULL NAME]\n")
    err = _exit_code(capsys, lambda: cv_mod.cmd_cv_pdf(str(cv)))
    assert err["code"] == "verify_required"
    assert err["details"]["unsupported"][0]["category"] == "placeholder"
    assert not (tmp_path / "cv-acme.pdf").exists()
    assert "uri" not in chrome  # Chrome never ran


def test_verified_cv_renders_without_touching_the_offer(gated, tmp_path, chrome):
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "# Ana\n")))
    assert (tmp_path / "cv-acme.pdf").exists()
    notes, evidence = _offer_row(gated)
    assert notes == "call Monday"
    assert evidence is None  # only `cv verify` snapshots evidence


def test_force_renders_and_appends_a_dated_note(gated, tmp_path, chrome, capsys):
    from datetime import date
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "# [FULL NAME]\n")), force=True)
    assert (tmp_path / "cv-acme.pdf").exists()
    assert "--force" in capsys.readouterr().err
    notes, _ = _offer_row(gated)
    assert notes == (f"call Monday\n[{date.today().isoformat()}] cv pdf --force: "
                     "verify skipped (1 unsupported claim(s))")


def test_cv_without_offer_id_is_refused_naming_force(gated, tmp_path, chrome, capsys):
    cv = tmp_path / "hand.md"
    cv.write_text("# Ana\n", encoding="utf-8")
    err = _exit_code(capsys, lambda: cv_mod.cmd_cv_pdf(str(cv)))
    assert err["code"] == "verify_required"
    assert "no offer id" in err["message"]


def test_force_on_cv_without_offer_id_renders_and_writes_nothing(gated, tmp_path, chrome):
    cv = tmp_path / "hand.md"
    cv.write_text("# Ana\n", encoding="utf-8")
    cv_mod.cmd_cv_pdf(str(cv), force=True)
    assert (tmp_path / "hand.pdf").exists()
    assert _offer_row(gated)[0] == "call Monday"


def test_force_renders_even_without_cv_master(gated, tmp_applyr, tmp_path, chrome):
    (tmp_applyr / "cv-master.md").unlink()
    cv_mod.cmd_cv_pdf(str(_cv(tmp_path, "# Ana\n")), force=True)
    assert (tmp_path / "cv-acme.pdf").exists()
    assert _offer_row(gated)[0].endswith("verify skipped (cv-master.md not found)")
