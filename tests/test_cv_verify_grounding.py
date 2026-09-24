"""Regression tests for the 2026-09 `cv verify` grounding audit: false BLOCKED
verdicts (brackets, accents, number formatting) and fabrications that used to
pass (unmatched metrics, shared-word employers, placeholders, template text)."""

import json

import pytest

from applyr.cv import cmd_cv_verify
from applyr.cv_master import inspect_cv_master
from applyr.db import get_conn
from applyr.evidence import fold_accents, is_evidenced, parse_evidence, split_tokens

MASTER = """\
## WORK EXPERIENCE

**Backend Developer — Acme Corp** — Madrid — 01/2022-01/2025
- Gestión de APIs REST con Python y FastAPI
- Redujo la latencia un 35% en 10.000 peticiones diarias
- Monitoriza +450 sesiones al mes

## PROJECTS

**ElectroCycle — Vite SPA**
- Comparison site

## TECHNICAL SKILLS

AI: LLM APIs (tool use, function calling), Python
"""


@pytest.fixture
def offer(tmp_db):
    conn = get_conn(tmp_db)
    conn.execute(
        "INSERT INTO offers (title, company, status, compatibility_pct) VALUES (?, ?, ?, ?)",
        ("Backend Dev", "Acme Corp", "pending", 70),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def master(tmp_applyr, monkeypatch):
    import applyr.cv as cv_mod
    monkeypatch.setattr(cv_mod, "APPLYR_DIR", tmp_applyr)
    path = tmp_applyr / "cv-master.md"
    path.write_text(MASTER, encoding="utf-8")
    return path


def _verify(tmp_applyr, capsys, body: str) -> dict:
    cv_path = tmp_applyr / "cv-acme.md"
    cv_path.write_text(f"---\noffer_id: 1\n---\n\n{body}", encoding="utf-8")
    try:
        cmd_cv_verify(str(cv_path), as_json=True)
    except SystemExit:
        pass
    return json.loads(capsys.readouterr().out)


def _unsupported(result: dict) -> set[str]:
    return {r["claim"] for r in result["unsupported"]}


class TestTokenizer:
    def test_commas_inside_brackets_do_not_split_a_claim(self):
        assert split_tokens("LLM APIs (tool use, function calling), Python") == [
            "LLM APIs (tool use, function calling)", " Python"]

    def test_bracketed_skill_is_evidenced_without_stray_bracket(self):
        claims = parse_evidence(MASTER)
        assert is_evidenced("function calling", claims)
        assert not any(c.text.endswith(")") and "(" not in c.text for c in claims)


class TestAccents:
    def test_fold_accents(self):
        assert fold_accents("Gestión híbrida") == "Gestion hibrida"

    def test_unaccented_term_matches_accented_master(self):
        assert is_evidenced("gestion", parse_evidence(MASTER))


class TestMetrics:
    @pytest.mark.parametrize("line", [
        "- Cut latency by 35 %",
        "- Handled 10,000 daily requests",
        "- Monitors 450+ sessions per month",
    ])
    def test_reformatted_real_metric_passes(self, tmp_db, tmp_applyr, offer, master, capsys, line):
        result = _verify(tmp_applyr, capsys, f"## Work Experience\n\n{line}\n")
        assert result["passed"], result["unsupported"]

    @pytest.mark.parametrize("line, claim", [
        ("- Served 3M users", "3M"),
        ("- 5+ years of Python", "5+"),
        ("- Handled 25,000 requests", "25,000"),
        ("- Saved €40K a year", "€40K"),
        ("- Cut latency by 36 %", "36 %"),
        ("- Saved $41,000.", "$41,000"),
    ])
    def test_invented_metric_is_blocked(self, tmp_db, tmp_applyr, offer, master, capsys, line, claim):
        result = _verify(tmp_applyr, capsys, f"## Work Experience\n\n{line}\n")
        assert not result["passed"]
        assert claim in _unsupported(result)


@pytest.mark.parametrize("text", [
    "Contact: +34 674 633 149",
    "Contact: (+34) 674 633 149",
    "Contact: +34-674-633-149",
    "JavaScript (ES6+), React 19, Python 3.12",
])
def test_phone_numbers_and_versions_are_not_metrics(tmp_db, tmp_applyr, offer, master, capsys, text):
    """Both were false BLOCKED verdicts on real CVs during the 2026-09 audit."""
    result = _verify(tmp_applyr, capsys, f"{text}\n")
    assert not [r for r in result["claims"] if r["category"] == "metric"], result["claims"]


class TestEmployerHeading:
    def test_real_company_with_tailored_title_passes(self, tmp_db, tmp_applyr, offer, master, capsys):
        result = _verify(tmp_applyr, capsys, "### Python Engineer - Acme Corp, Madrid\n")
        assert result["passed"], result["unsupported"]

    def test_fabricated_company_sharing_a_title_word_is_blocked(self, tmp_db, tmp_applyr, offer, master, capsys):
        result = _verify(tmp_applyr, capsys, "### Backend AI Lead - Globex, Remote\n")
        assert not result["passed"]

    def test_project_name_with_description_passes(self, tmp_db, tmp_applyr, offer, master, capsys):
        """Found on a real CV: the description after the dash is not a company."""
        result = _verify(tmp_applyr, capsys, "### ElectroCycle - Comparison site in production\n")
        assert result["passed"], result["unsupported"]

    @pytest.mark.parametrize("heading", ["Vite Developer - Globex, Remote", "SPA Lead - Initech"])
    def test_stack_word_of_a_project_does_not_ground_a_fake_employer(
            self, tmp_db, tmp_applyr, offer, master, capsys, heading):
        result = _verify(tmp_applyr, capsys, f"### {heading}\n")
        assert not result["passed"]

    def test_bracketed_heading_matches_its_entry(self, tmp_db, tmp_applyr, offer, master, capsys):
        result = _verify(tmp_applyr, capsys, "### Backend Developer (Acme), Madrid\n")
        assert result["passed"], result["unsupported"]


class TestPlaceholders:
    def test_unfilled_skeleton_placeholder_blocks(self, tmp_db, tmp_applyr, offer, master, capsys):
        result = _verify(tmp_applyr, capsys, "# [FULL NAME]\n\n- [Achievement with measurable impact]\n")
        assert not result["passed"]
        assert "[FULL NAME]" in _unsupported(result)
        assert any(i["type"] == "unfilled_placeholder" for i in result["issues"])

    def test_markdown_link_is_not_a_placeholder(self, tmp_db, tmp_applyr, offer, master, capsys):
        result = _verify(tmp_applyr, capsys, "Repo: [applyr](https://github.com/x/applyr)\n")
        assert result["passed"], result["unsupported"]


def test_claims_past_the_review_length_cap_are_still_checked(tmp_db, tmp_applyr, offer, master, capsys):
    filler = "- Built REST APIs with Python\n" * 600  # > 10k characters
    result = _verify(tmp_applyr, capsys, f"## Work Experience\n\n{filler}- Served 3M users\n")
    assert "3M" in _unsupported(result)


def test_summary_containing_dashes_does_not_end_frontmatter_early(tmp_db, tmp_applyr, offer, master, capsys):
    cv_path = tmp_applyr / "cv-acme.md"
    cv_path.write_text('---\noffer_id: 1\nsummary: "APIs --- 3M users"\n---\n\nPython\n', encoding="utf-8")
    cmd_cv_verify(str(cv_path), as_json=True)  # would block on "3M" from the frontmatter
    assert json.loads(capsys.readouterr().out)["passed"]


def test_real_money_metric_followed_by_punctuation_passes(tmp_db, tmp_applyr, offer, master, capsys):
    master.write_text(MASTER + "\n## PROJECTS\n\n**Shop — Django**\n- Saved $40,000 per year\n", encoding="utf-8")
    result = _verify(tmp_applyr, capsys, "- Saved $40,000.\n")
    assert result["passed"], result["unsupported"]


def test_crlf_frontmatter_is_stripped(tmp_db, tmp_applyr, offer, master, capsys):
    cv_path = tmp_applyr / "cv-acme.md"
    cv_path.write_bytes(b'---\r\noffer_id: 1\r\nsummary: "3M users"\r\n---\r\n\r\nPython\r\n')
    from applyr.cv import _strip_frontmatter
    assert "3M" not in _strip_frontmatter(cv_path.read_text(encoding="utf-8"))


class TestTemplateGuidance:
    LEGACY = ('## WORK EXPERIENCE\n...\n'
              'then 2-4 bullets with measurable results (e.g. "Cut API latency by 42%").\n'
              '## TECHNICAL SKILLS\n'
              'Grouped by area: Languages, Backend, Frontend, Databases, DevOps.\n')

    def test_legacy_guidance_lines_are_not_evidence(self):
        claims = parse_evidence(self.LEGACY)
        assert not is_evidenced("42%", claims)
        assert not is_evidenced("DevOps", claims)

    def test_commented_guidance_is_not_evidence(self):
        claims = parse_evidence("## TECHNICAL SKILLS\n<!-- Grouped: Kubernetes, DevOps -->\nPython\n")
        assert not is_evidenced("Kubernetes", claims)
        assert is_evidenced("Python", claims)

    def test_guidance_does_not_count_as_profile_content(self):
        assert inspect_cv_master(self.LEGACY).content_words == 0

    def test_shipped_template_is_still_reported_unfilled(self):
        from pathlib import Path
        import applyr
        template = Path(applyr.__file__).parent / "templates" / "cv-master-template.md"
        assert not inspect_cv_master(template.read_text(encoding="utf-8")).filled
