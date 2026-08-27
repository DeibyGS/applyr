"""CV system — markdown-first generation and Chrome headless PDF export."""

import os
import re
import subprocess
import sys
from pathlib import Path

from applyr.config import APPLYR_DIR, load_config
from applyr.constants import CHROME_STDERR_SNIPPET, CHROME_TIMEOUT_SECONDS, PROTECTED_FACT_ALIASES
from applyr.cv_master import inspect_cv_master
from applyr.errors import die, error, read_text_or_die, warn
from applyr.evidence import is_evidenced, parse_evidence


def _die_chrome(message: str, result) -> None:
    """Report a Chrome failure on both output paths, including its stderr."""
    snippet = (result.stderr or "")[:CHROME_STDERR_SNIPPET]
    error(f"Error: {message}")
    if snippet:
        error(f"  Chrome stderr: {snippet}")
    die(message, code="chrome_failed",
        details={"returncode": result.returncode, "chrome_stderr": snippet or None},
        text="")

# ATS-safe CSS — embedded in every generated CV
# Rules: single column, no flex/grid/tables, standard fonts, no images
_ATS_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: Arial, Calibri, sans-serif;
    font-size: 10pt;
    line-height: 1.3;
    color: #1a1a1a;
    max-width: 21cm;
    margin: 0 auto;
    padding: 0.8cm 1.4cm;
}
h1 { font-size: 14pt; margin-bottom: 3px; color: #111; }
h2 {
    font-size: 11pt;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1.2px solid #333;
    padding-bottom: 2px;
    margin: 8px 0 5px;
    color: #222;
}
h3 { font-size: 10pt; margin-bottom: 2px; }
.contact { font-size: 9pt; color: #333; margin-bottom: 8px; }
.contact a { color: #333; text-decoration: none; }
.dates { font-size: 9pt; color: #555; }
.summary { margin-bottom: 6px; color: #333; }
ul { padding-left: 15px; margin: 3px 0 7px; }
li { margin-bottom: 2px; }
p { margin-bottom: 3px; }
/* Chrome adds its own default page margin on top of the body padding, which
   silently pushes a one-page CV onto a second page. Zeroing it here makes the
   body padding the single source of truth for margins. */
@page { size: A4; margin: 0; }
@media print {
    body { padding: 0.8cm 1.4cm; }
    h2 { page-break-after: avoid; }
}"""


# Section headings per language, and the labels that survive into the delivered
# CV rather than being replaced by the agent filling the skeleton.
#
# Until v1.1.0 these were hardcoded in English while the agent wrote the content
# in the language of the offer, so a Spanish application arrived with Spanish
# bullets under "Work Experience". That reads as machine-made to the recruiter,
# and an ATS scanning a Spanish CV for "EXPERIENCIA" matches nothing.
#
# Adding a language means adding an entry here and to VALID_LANGUAGES in db.py.
CV_HEADINGS = {
    "en": {
        "name": "English",
        "summary": "Professional Summary",
        "experience": "Work Experience",
        "projects": "Projects",
        "education": "Education",
        "certifications": "Certifications",
        "skills": "Technical Skills",
        "languages": "Languages",
        "stack": "Stack",
        "backend": "Backend",
        "frontend": "Frontend",
        "databases": "Databases",
        "devops": "DevOps",
        "other": "Other",
    },
    "es": {
        "name": "Spanish",
        "summary": "Perfil Profesional",
        "experience": "Experiencia Profesional",
        "projects": "Proyectos",
        "education": "Formación",
        "certifications": "Certificaciones",
        "skills": "Habilidades Técnicas",
        "languages": "Idiomas",
        "stack": "Stack",
        "backend": "Backend",
        "frontend": "Frontend",
        "databases": "Bases de datos",
        "devops": "DevOps",
        "other": "Otros",
    },
}


def resolve_cv_language(offer_language: str | None) -> str:
    """Pick the language a CV is written in: the offer's, else the configured default.

    The offer wins because the language is a fact about the vacancy, not about
    the machine generating the CV. An unrecognised value — a hand-edited config,
    or a language added to the config before its headings exist — falls back to
    English rather than failing: a CV in the wrong language is recoverable, a
    command that refuses to run mid-application is not.
    """
    if offer_language in CV_HEADINGS:
        return offer_language
    configured = load_config()["cv"].get("language", "en")
    return configured if configured in CV_HEADINGS else "en"


def _make_slug(company: str | None) -> str:
    """Create a filesystem-safe slug from a company name.

    Company only, not title: a CV file is named after who it's going to, not
    the specific role applied for. Keeps only ASCII letters, digits and
    dashes so names like "Acme (Spain)" don't produce filenames that need
    shell quoting. A second offer at the same company gets an id suffix
    instead of colliding — see cmd_cv_generate.
    """
    raw = (company or "unknown").lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return cleaned[:40].strip("-") or "cv"


def get_cv_master_path() -> Path:
    """Return the path to the user's cv-master.md."""
    config = load_config()
    return Path(os.path.expanduser(config["cv"]["cv_master"]))


def get_output_dir() -> Path:
    """Return the CV output directory, creating it if needed."""
    config = load_config()
    output_dir = Path(os.path.expanduser(config["cv"]["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _get_tailoring_hints(
    tech_stack: str | None, topics: dict, profile_text: str = ""
) -> tuple[list[str], list[str], list[str]]:
    """Generate tailoring hints based on tech_stack and topic scores.

    profile_text is cv-master.md's raw text (not lowercased — the Evidence
    Graph parser, applyr/evidence.py, needs original casing for claim text and
    does its own case-insensitive matching internally). Filters tech_stack
    down to what the candidate's profile actually evidences via
    evidence.is_evidenced(), which also expands PROTECTED_FACT_ALIASES (e.g.
    an offer's "AWS" matches a profile written as "Amazon Web Services") —
    the same "never invent skills" check generate_cover_letter already applies
    to its key_skills, now alias-aware instead of a raw substring check.
    Anything not evidenced is surfaced as NOT INCLUDED, so the gap is explicit
    rather than silently dropped.

    Returns:
        Tuple of (highlight, de_emphasize, not_included) lists
    """
    highlight = []
    de_emphasize = []
    not_included = []

    if tech_stack:
        # Parse tech_stack from comma-separated string
        skills = [s.strip() for s in tech_stack.split(",") if s.strip()]
        if profile_text:
            claims = parse_evidence(profile_text)
            highlight = [s for s in skills if is_evidenced(s, claims)]
            not_included = [s for s in skills if not is_evidenced(s, claims)]
        else:
            highlight = skills

    # Get strong topics to highlight
    for topic, values in topics.items():
        score = values.get("score", 0)
        if score >= 80:
            label = _TOPIC_LABELS.get(topic, topic)
            if label not in highlight:
                highlight.append(label)

    # Get missing topics to de-emphasize
    for topic, values in topics.items():
        score = values.get("score", 0)
        if score < 50:
            label = _TOPIC_LABELS.get(topic, topic)
            de_emphasize.append(label)

    return highlight, de_emphasize, not_included


def _format_tailoring_hints(highlight: list[str], de_emphasize: list[str], not_included: list[str]) -> str:
    """Format tailoring hints as HTML comments."""
    lines = []
    if highlight:
        lines.append(f"<!-- TAILOR: Prioritize {', '.join(highlight)} -->")
    if de_emphasize:
        lines.append(f"<!-- DE-EMPHASIZE: {', '.join(de_emphasize)} -->")
    if not_included:
        lines.append(f"<!-- NOT INCLUDED: {', '.join(not_included)} -->")
    return "\n".join(lines)


_SENIOR_LEVELS = {"senior", "lead", "director"}

_TOPIC_LABELS = {
    "tech_stack": "Technical Skills",
    "experience": "Work Experience",
    "projects": "Projects",
    "education": "Education",
    "english": "Languages",
    "cultural_fit": "Work Preferences",
}


def _count_pdf_pages(pdf_path: Path) -> int | None:
    """Count pages in a PDF without adding a PDF library dependency.

    Chrome's --print-to-pdf output keeps page objects as plain, uncompressed
    text, so counting `/Type /Page` occurrences (excluding `/Type /Pages`,
    the tree root) works. Returns None instead of 0 when nothing matched —
    the format assumption broke, so stay silent rather than report a
    misleading count.
    """
    data = pdf_path.read_bytes()
    count = len(re.findall(rb"/Type\s*/Page(?!s)", data))
    return count or None


def _page_limit_for(cv_path: Path) -> int:
    """1 page, or 2 for senior/lead/director — the limit `cv review` already states.

    Falls back to 1 (the stricter rule) whenever the offer's seniority can't
    be resolved: legacy .html input, missing frontmatter, or a deleted offer.
    """
    if cv_path.suffix != ".md":
        return 1
    match = re.search(r"offer_id:\s*(\d+)", cv_path.read_text(encoding="utf-8"))
    if not match:
        return 1

    from applyr.db import get_conn
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT seniority_level FROM offers WHERE id = ?", (int(match.group(1)),)
        ).fetchone()
    finally:
        conn.close()
    seniority = (row["seniority_level"] if row else None) or ""
    return 2 if seniority.lower() in _SENIOR_LEVELS else 1


def cmd_cv_pdf(cv_file: str, output: str | None = None) -> None:
    """Convert a CV file (markdown or HTML) to PDF using Chrome headless.

    For .md files: renders markdown → ATS-safe HTML → PDF in one invocation.
    For .html files: renders directly to PDF (legacy support).
    """
    from applyr.md_render import render_markdown_file_to_html

    config = load_config()
    chrome_path = config["cv"]["chrome_path"]

    if not chrome_path or not os.path.isfile(chrome_path):
        error("Error: Chrome/Chromium not found.")
        error(f"  Set 'chrome_path' in {APPLYR_DIR / 'applyr.toml'} under [cv]")
        die("Chrome/Chromium not found — required for PDF generation.",
            code="chrome_not_found", text="  Or install Google Chrome / Chromium.")

    cv_path = Path(cv_file).resolve()
    if not cv_path.exists():
        die(f"Error: CV file not found: {cv_file}", code="not_found",
            details={"path": cv_file})

    if output:
        pdf_path = Path(output).resolve()
    else:
        pdf_path = cv_path.with_suffix(".pdf")

    # For markdown files, convert to HTML first
    if cv_path.suffix == ".md":
        html_content = render_markdown_file_to_html(str(cv_path))
        # Wrap in full HTML document with ATS-safe CSS
        full_html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV</title>
    <style>
{_ATS_CSS}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
        # Write temporary HTML file
        tmp_html = cv_path.with_suffix(".html")
        tmp_html.write_text(full_html)
        html_path = tmp_html
    else:
        html_path = cv_path

    cmd = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=CHROME_TIMEOUT_SECONDS)
        if result.returncode != 0:
            _die_chrome("Chrome exited with an error.", result)
        if pdf_path.exists():
            print(f"PDF generated: {pdf_path}")
            page_count = _count_pdf_pages(pdf_path)
            if page_count is not None:
                limit = _page_limit_for(cv_path)
                if page_count > limit:
                    warn(f"Warning: PDF is {page_count} page(s) — ATS rule allows "
                         f"{limit} for this profile. Trim content before sending.")
        else:
            _die_chrome("PDF was not generated.", result)
    except subprocess.TimeoutExpired:
        die(f"Error: Chrome timed out after {CHROME_TIMEOUT_SECONDS} seconds.",
            code="chrome_failed", details={"timeout_seconds": CHROME_TIMEOUT_SECONDS})
    except FileNotFoundError:
        die(f"Error: Chrome not found at: {chrome_path}",
            code="chrome_not_found", details={"path": chrome_path})
    finally:
        # Clean up temporary HTML file if we created one
        if cv_path.suffix == ".md" and html_path.exists():
            html_path.unlink()


def cmd_cv_generate(offer_id: int, template: str = "ats", force: bool = False) -> None:
    """Generate an ATS-safe markdown CV draft for a specific offer.

    The markdown includes:
    - YAML frontmatter with offer context (company, title, tech_stack, etc.)
    - Placeholder sections for the AI agent to fill from cv-master.md

    The AI agent reads cv-master.md and replaces [PLACEHOLDER] values.
    Topic scores stay out of the file — they contain candid self-assessment
    that must not reach the recruiter.
    """
    from applyr.db import get_conn

    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            die(f"Error: offer #{offer_id} not found.", code="not_found",
                details={"offer_id": offer_id})
    finally:
        conn.close()

    cv_master = get_cv_master_path()
    if not cv_master.exists():
        error(f"Error: cv-master.md not found at {cv_master}")
        die(f"Error: cv-master.md not found at {cv_master}", code="not_found",
            details={"path": str(cv_master)},
            text="  Run 'applyr init' to create a template, then edit it with your profile.")

    # An unfilled template is worse than a missing one: generation succeeds and
    # the agent has nothing to fill the placeholders from, so the failure is
    # silent. setup-agent already warns about this; refuse it here too.
    cv_master_text = cv_master.read_text(encoding="utf-8")
    report = inspect_cv_master(cv_master_text)
    if not report.filled:
        error(f"Error: cv-master.md is {report.reason}.")
        die("cv-master.md is still the unfilled template.", code="empty_cv_master",
            details={"path": str(cv_master),
                     "placeholder_sections": list(report.placeholder_sections),
                     "content_words": report.content_words},
            text=f"  Fill {cv_master} with your profile before generating a CV.")
    output_dir = get_output_dir()
    slug = _make_slug(row["company"])
    md_path = output_dir / f"cv-{slug}.md"

    # A CV for the same company already sitting on disk from a DIFFERENT
    # offer is not a collision to block — applying to several roles at one
    # company is normal (see duplicates.py). Disambiguate with the offer id
    # instead of overwriting or refusing. Regenerating THIS offer's own CV
    # still falls through to the already_exists guard below.
    if md_path.exists():
        conn = get_conn()
        try:
            other = conn.execute(
                "SELECT id FROM offers WHERE cv_used = ? AND id != ?",
                (md_path.stem, offer_id),
            ).fetchone()
        finally:
            conn.close()
        if other:
            slug = f"{slug}-{offer_id}"
            md_path = output_dir / f"cv-{slug}.md"

    # Build YAML frontmatter with offer context
    context_lines = [
        f"offer_id: {offer_id}",
        f"title: \"{row['title']}\"",
        f"company: \"{row['company'] or 'Not specified'}\"",
        f"work_mode: \"{row['work_mode'] or 'Not specified'}\"",
        f"location: \"{row['location'] or 'Not specified'}\"",
        f"seniority: \"{row['seniority_level'] or 'Not specified'}\"",
        f"role_category: \"{row['role_category'] or 'Not specified'}\"",
        f"language: \"{resolve_cv_language(row['language'])}\"",
        f"tech_stack: \"{row['tech_stack'] or 'Not specified'}\"",
        f"compatibility: {row['compatibility_pct']}",
    ]
    if row["summary"]:
        context_lines.append(f"summary: \"{row['summary']}\"")

    frontmatter = "---\n" + "\n".join(context_lines) + "\n---"

    # Get tailoring hints
    topics_dict = {}
    # Load topics from database
    from applyr.db import get_conn
    conn = get_conn()
    try:
        topic_rows = conn.execute(
            "SELECT topic, score, detail FROM offer_topics WHERE offer_id = ?", (offer_id,)
        ).fetchall()
        for t in topic_rows:
            topics_dict[t["topic"]] = {"score": t["score"], "detail": t["detail"]}
    finally:
        conn.close()

    highlight, de_emphasize, not_included = _get_tailoring_hints(
        row["tech_stack"], topics_dict, cv_master_text
    )
    tailoring_hints = _format_tailoring_hints(highlight, de_emphasize, not_included)

    # Same evidenced list as the TAILOR comment above — the per-section
    # instructions below used to interpolate row["tech_stack"] raw, telling
    # the filling agent to "prioritize" offer tech the profile never
    # evidenced, contradicting the TAILOR/NOT INCLUDED hint right above them.
    evidenced_stack = ", ".join(highlight) if highlight else (row["tech_stack"] or "the role")

    language = resolve_cv_language(row["language"])
    headings = CV_HEADINGS[language]

    md = f"""\
{frontmatter}

{tailoring_hints}
<!-- LANGUAGE: write every line of this CV in {headings['name']}, headings included. -->

# [FULL NAME]

[City, Country] | [EMAIL] | [PHONE] | [linkedin.com/in/PROFILE] | [github.com/USERNAME] | [WEBSITE]

## {headings['summary']}

[2-3 sentences tailored to {row['title']} at {row['company'] or 'this company'}.
Highlight relevant skills for: {evidenced_stack}.
Match keywords from the job description.
Include both acronyms and full terms.]

## {headings['experience']}

### [Job Title] - [Company], [Location], [Mode]
[MM/YYYY - MM/YYYY]

- [Achievement with measurable impact]
- [Technology or methodology used with concrete result]

<!-- Add more positions from cv-master.md if relevant to {row['title']} -->

## {headings['projects']}

### [Project Name]
**{headings['stack']}:** [Technologies] | [REPO_URL]

- [What it does and key technical decisions relevant to {evidenced_stack}]

<!-- Add more projects from cv-master.md if relevant -->

## {headings['education']}

### [Degree]
[Institution] | [MM/YYYY - MM/YYYY]

## {headings['certifications']}

- [Certification] - [Issuer] ([MM/YYYY])

<!-- Include only certifications relevant to {row['role_category'] or 'the role'} -->

## {headings['skills']}

**{headings['backend']}:** [list — prioritize skills matching: {evidenced_stack}]
**{headings['frontend']}:** [list]
**{headings['databases']}:** [list]
**{headings['devops']}:** [list]
**{headings['other']}:** [list]

## {headings['languages']}

- [Language] - [Level]
"""

    # Never clobber a finished CV. Regenerating drops the skeleton back on top
    # of hours of tailored content, and there is no undo.
    if md_path.exists() and not force:
        error(f"Error: {md_path.name} already exists.")
        die(f"CV already exists at {md_path}", code="already_exists",
            details={"path": str(md_path), "offer_id": offer_id},
            text="  It would be overwritten with an empty skeleton.\n"
                 "  Pass --force to replace it, or rename the existing file first.")

    # Explicit UTF-8: the skeleton now carries accented headings ("Formación"),
    # so relying on the platform's default encoding would corrupt or fail to
    # write a CV in every language applyr supports but English.
    md_path.write_text(md, encoding="utf-8")

    # Record which CV was used for this offer, so `applyr cv stats` can later
    # correlate CVs with outcomes. Store basename without extension (AC-3.10).
    conn = get_conn()
    try:
        conn.execute("UPDATE offers SET cv_used = ? WHERE id = ?",
                     (md_path.stem, offer_id))
        conn.commit()
    finally:
        conn.close()

    print(f"CV draft generated: {md_path}")
    print(f"  Offer    : #{offer_id} — {row['title']} @ {row['company'] or '?'}")
    print(f"  Template : {template} (ATS-safe)")
    source = "from the offer" if row["language"] else "configured default"
    print(f"  Language : {headings['name']} ({source})")
    print(f"  CV Master: {cv_master}")
    print(f"  Recorded : cv_used = {md_path.stem}")

    # Show tailoring summary
    if highlight:
        print(f"\n  Tailoring applied:")
        print(f"    ✓ Highlighted: {', '.join(highlight)}")
    if de_emphasize:
        print(f"    ✗ De-emphasized: {', '.join(de_emphasize)}")
    if not_included:
        print(f"    • Not included: {', '.join(not_included)}")

    print()


# ---------------------------------------------------------------------------
# CV review — recruiter prompt generator
# ---------------------------------------------------------------------------

_MAX_CV_TEXT_CHARS = 10_000

_REVIEW_RUBRIC = """\
## Evaluation criteria

This is a heuristic compatibility estimate, not a prediction of how any specific
employer's ATS will actually parse or rank this CV — no such universal score exists.

Score each category 0-100 and provide specific feedback:

### 1. Keyword Match (weight: 30%)
- Compare CV keywords against the job description in the HTML comments
- Check for both acronyms and full terms (e.g., "AI" and "Artificial Intelligence")
- Flag important keywords from the offer that are missing

### 2. ATS Format Compliance (weight: 20%)
- Single column layout (no tables, flexbox, grid)
- Standard fonts (Arial, Calibri)
- Standard section headers (Professional Summary, Work Experience, Education, etc.)
- No images, icons, or decorative elements
- URLs shown in full (linkedin.com/in/x, not "LinkedIn")

### 3. Evidence & Metrics (weight: 20%)
- At least 70% of bullet points should include measurable results (%, $, Nx, users)
- Flag vague claims without evidence ("improved performance" → needs numbers)
- Flag any claim that looks invented or unverifiable

### 4. Clarity & Impact (weight: 20%)
- Bullets start with strong action verbs
- Each bullet communicates ONE clear achievement
- Professional summary is tailored to the target role (not generic)

### 5. Length & Relevance (weight: 10%)
- 1 page maximum for < 5 years experience, 2 pages for 5+
- All sections are relevant to the target role
- No filler content or outdated skills"""

_REVIEW_OUTPUT_FORMAT = """\
## Required output format

```
ATS COMPATIBILITY SCORE: [0-100]/100

KEYWORD MATCH:      [0-100]  [1-sentence explanation]
ATS COMPLIANCE:     [0-100]  [1-sentence explanation]
EVIDENCE & METRICS: [0-100]  [1-sentence explanation]
CLARITY & IMPACT:   [0-100]  [1-sentence explanation]
LENGTH & RELEVANCE: [0-100]  [1-sentence explanation]

STRENGTHS:
- [strength 1]
- [strength 2]

WEAKNESSES:
- [weakness 1 + specific fix]
- [weakness 2 + specific fix]

IMPROVEMENTS (ordered by impact):
1. [most impactful change]
2. [second most impactful]
3. [third]

VERDICT: [READY TO SEND / NEEDS MINOR EDITS / NEEDS MAJOR REVISION]
```"""

# cv review-blind runs on the RAW cv-master.md, before any CV is generated or
# trimmed for the offer (that happens in a later step — see cmd_cv_generate).
# Reusing _REVIEW_RUBRIC here penalized the untrimmed source document against
# criteria that only make sense for a finished, tailored CV: "ATS Format
# Compliance" and "Length & Relevance" (1-2 pages) — a master profile
# spanning a full career history will always fail a page-count check that
# was never meant to apply to it yet. Dropped both and reweighted the rest.
_BLIND_REVIEW_RUBRIC = """\
## Evaluation criteria

This is the RAW, untailored source profile (cv-master.md), evaluated before any CV is
generated or trimmed for this offer. Criteria that only make sense for a finished
document — ATS formatting, page count — do not apply yet; score whether the *material in
the profile* is strong enough to build a great tailored CV from.

This is a heuristic compatibility estimate, not a prediction of how any specific
employer's ATS will actually parse or rank the finished CV — no such universal score exists.

Score each category 0-100 and provide specific feedback:

### 1. Keyword Match (weight: 45%)
- Compare CV keywords against the job description in the HTML comments
- Check for both acronyms and full terms (e.g., "AI" and "Artificial Intelligence")
- Flag important keywords from the offer that are missing

### 2. Evidence & Metrics (weight: 30%)
- Among the material relevant to this offer, do bullets show measurable results (%, $, Nx, users)?
- Flag vague claims without evidence ("improved performance" → needs numbers)
- Flag any claim that looks invented or unverifiable

### 3. Clarity & Impact (weight: 25%)
- Among the material relevant to this offer, do bullets start with strong action verbs
  and communicate ONE clear achievement each?
- Irrelevant history (unrelated past jobs) is expected here and will be cut at generate
  time — do not penalize its presence, only judge whether the relevant material holds up"""

_BLIND_REVIEW_OUTPUT_FORMAT = """\
## Required output format

```
ATS COMPATIBILITY SCORE: [0-100]/100

KEYWORD MATCH:      [0-100]  [1-sentence explanation]
EVIDENCE & METRICS: [0-100]  [1-sentence explanation]
CLARITY & IMPACT:   [0-100]  [1-sentence explanation]

STRENGTHS:
- [strength 1]
- [strength 2]

GAPS:
- [gap 1 — missing from the profile's content, not from formatting]
- [gap 2]

RECOMMENDATION: [what to prioritize when tailoring the CV for this offer]
```"""


def _strip_html_tags(html: str) -> str:
    """Remove markup, styles and comments, returning the readable CV text."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = _strip_html_comments(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:_MAX_CV_TEXT_CHARS]


def _offer_context_from_db(offer_id: int) -> str | None:
    """Build the review context for an offer, scores included, from the database.

    Scores live here rather than in the CV so that candid self-assessment never
    ships inside the file the recruiter receives.
    """
    from applyr.db import get_conn

    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            return None
        topics = conn.execute(
            "SELECT topic, score, detail FROM offer_topics WHERE offer_id = ? ORDER BY score DESC",
            (offer_id,),
        ).fetchall()
    finally:
        conn.close()

    lines = [
        f"Target Position : {row['title']}",
        f"Company         : {row['company'] or 'Not specified'}",
        f"Work Mode       : {row['work_mode'] or 'Not specified'}",
        f"Location        : {row['location'] or 'Not specified'}",
        f"Seniority       : {row['seniority_level'] or 'Not specified'}",
        f"Tech Stack Req. : {row['tech_stack'] or 'Not specified'}",
        f"Compatibility   : {row['compatibility_pct']}%",
    ]
    if row["summary"]:
        lines.append(f"Job Summary     : {row['summary']}")
    if topics:
        lines.append("")
        lines.append("Topic Scores:")
        lines += [f"  {t['topic']}: {t['score']}% — {t['detail'] or ''}" for t in topics]
    return "\n".join(lines)


def _strip_frontmatter(md: str) -> str:
    """Return the document body, dropping any leading YAML frontmatter.

    A generated CV opens with the offer's own context — `tech_stack`, `summary`
    — which is metadata about the vacancy, not content a recruiter or an ATS
    ever sees. Anything measuring what the CV *says* has to read past it.
    """
    if not md.startswith("---"):
        return md
    end = md.find("---", 3)
    return md[end + 3:].lstrip("\n") if end != -1 else md


def _strip_html_comments(text: str) -> str:
    """Remove `<!-- ... -->` blocks, incl. the `TAILOR:`/`NOT INCLUDED:` scaffold
    `cv generate` writes into every file — never content a recruiter, an ATS,
    or any of this module's own analysis passes should see. Shared so every
    command that reads a generated CV's body agrees on what "the CV" is
    (found via /code-review: `cv keywords` and `cv verify` already stripped
    it through independent copies of this same regex; `cv ats-check` did
    not, so a comment line starting with "|" could trip its table-layout
    heuristic while every sibling command saw clean text).
    """
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)


def _parse_markdown_for_review(md: str) -> str:
    """Parse markdown content for CV review, extracting readable text.

    Strips YAML frontmatter and HTML comments, converts markdown to plain text.
    """
    md = _strip_frontmatter(md)
    text = _strip_html_comments(md)

    # Convert markdown to plain text
    # Headers: ## Title → Title
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)
    # Bold: **text** → text
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # Italic: *text* → text
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Links: [text](url) → text (url)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    # List markers: - item → item
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Clean up whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    return text[:_MAX_CV_TEXT_CHARS]


def _extract_offer_context_from_md(md: str) -> str:
    """Resolve the offer context for a CV, preferring the database.

    For markdown files, reads the offer_id from YAML frontmatter.
    For legacy HTML files, reads from HTML comments.
    """
    # Try YAML frontmatter (markdown files)
    frontmatter_match = re.search(r'^---\n(.*?)\n---', md, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        offer_id_match = re.search(r'offer_id:\s*(\d+)', frontmatter)
        if offer_id_match:
            context = _offer_context_from_db(int(offer_id_match.group(1)))
            if context:
                return context

    # Try HTML comment marker (legacy HTML files)
    marker = re.search(r'applyr:offer-id=(\d+)', md)
    if marker:
        context = _offer_context_from_db(int(marker.group(1)))
        if context:
            return context

    # Try legacy HTML context block
    legacy = re.search(r'OFFER CONTEXT.*?:(.*?)INSTRUCTIONS FOR AI AGENT', md, re.DOTALL)
    if legacy:
        return legacy.group(1).strip()

    return "(No offer context found — pass a CV generated by 'applyr cv generate')"


def cmd_cv_review(cv_file: str, as_json: bool = False) -> None:
    """Generate a recruiter-review prompt for a CV file (markdown or HTML)."""
    import json

    cv_path = Path(cv_file).resolve()
    content = read_text_or_die(cv_path)

    # Parse markdown directly (no _strip_html_tags needed)
    if cv_path.suffix == ".md":
        cv_text = _parse_markdown_for_review(content)
    else:
        # Legacy HTML files
        cv_text = _strip_html_tags(content)

    offer_context = _extract_offer_context_from_md(content)

    prompt = f"""\
You are a senior technical recruiter with 10+ years of experience reviewing CVs for tech roles. You are thorough, fair, and direct.

## Task
Review the following CV against the target position and provide a detailed evaluation.

## Target position context
{offer_context}

## CV content
{cv_text}

{_REVIEW_RUBRIC}

{_REVIEW_OUTPUT_FORMAT}

Be specific. Reference exact lines from the CV. Do not be vague."""

    if as_json:
        payload = {
            "cv_file": str(cv_path),
            "cv_text": cv_text,
            "offer_context": offer_context,
            "prompt": prompt,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(prompt)


# ---------------------------------------------------------------------------
# cmd_cv_verify (docs/adr/011-evidence-based-cv-engine.md)
# ---------------------------------------------------------------------------
# Metrics: percentages, multipliers, dollar amounts — the kind of concrete
# number a filling agent is tempted to invent because a CV "expects" one.
# Decimals included in the digit run (\.\d+)? — without it, "2.5x" matched as
# just "5x" (the leading "2." was left outside the match entirely), so a
# fabricated "2.5x" could pass by coincidentally substring-colliding with an
# unrelated real "15x"/"25x" elsewhere — confirmed live via /code-review.
_METRIC_RE = re.compile(r'\$\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?%|\d+(?:\.\d+)?x\b', re.IGNORECASE)
# The CV skeleton's per-entry headings ("### [Job Title] - [Company], ...",
# "### [Project Name]") — see cmd_cv_generate's template below.
_ENTRY_HEADING_RE = re.compile(r'^###\s+(.+)$', re.MULTILINE)
# Legacy .html CVs (ADR-008: .md is the primary format, .html stays
# read-compatible) render the same entries as "<h3>...</h3>" — confirmed
# via /code-review that applying the markdown-only regex above to raw .html
# content always returns zero headings, silently skipping the
# employer_or_title check entirely for that file type.
_ENTRY_HEADING_HTML_RE = re.compile(r'<h3[^>]*>(.*?)</h3>', re.DOTALL | re.IGNORECASE)
# Excluded from the employer/title word-overlap check: too common to mean
# anything on their own (corporate suffixes, work-mode labels, articles,
# generic role nouns). Without the role-noun group, a fabricated title like
# "Senior ML Engineer — Globex Corp" would word-overlap-match ANY unrelated
# real entry that also happens to contain "Engineer" (e.g. a "Máster en AI
# Engineer" education entry) — confirmed live against a real cv-master.md,
# not a hypothetical: a single generic word was enough to pass a genuinely
# fabricated employer/title through unflagged.
_HEADING_STOPWORDS = frozenset({
    "inc", "llc", "corp", "corporation", "ltd", "co", "company",
    "remote", "hybrid", "onsite", "the", "and", "of", "for", "to", "in",
    "at", "on", "is", "an", "as", "by", "or", "it", "be",
    "engineer", "engineering", "developer", "development", "manager",
    "analyst", "specialist", "consultant", "architect", "lead", "senior",
    "junior", "director", "coordinator", "administrator", "technician",
    "cto", "ceo", "cfo", "coo", "vp",
    # Spanish equivalents — cv-master.md's language is unconstrained (see
    # evidence.py's _SECTION_MAP), so a Spanish CV needs the same filter.
    "remoto", "hibrido", "híbrido", "presencial", "empresa",
    "ingeniero", "ingeniera", "desarrollador", "desarrolladora",
    "gerente", "analista", "especialista", "consultor", "consultora",
    "arquitecto", "arquitecta", "coordinador", "coordinadora",
    "administrador", "administradora", "tecnico", "técnico",
    "de", "la", "el", "en", "un", "una", "y", "o", "a",
})


def _extract_offer_id_from_md(md: str) -> int | None:
    """Resolve the offer id linked to a CV — YAML frontmatter (markdown
    files) first, then the legacy HTML comment marker (.html files)."""
    frontmatter_match = re.search(r'^---\n(.*?)\n---', md, re.DOTALL)
    if frontmatter_match:
        offer_id_match = re.search(r'offer_id:\s*(\d+)', frontmatter_match.group(1))
        if offer_id_match:
            return int(offer_id_match.group(1))
    marker = re.search(r'applyr:offer-id=(\d+)', md)
    if marker:
        return int(marker.group(1))
    return None


def _build_tech_vocabulary(claims: list, offer_tech_stack: str | None = None) -> set[str]:
    """Technology terms worth checking a CV for: PROTECTED_FACT_ALIASES'
    canonical names and aliases, every skill claim already in the Evidence
    Graph, AND the target offer's own tech_stack terms.

    The offer's tech_stack matters because it's exactly the set a filling
    agent is most tempted to claim (the job asked for it) and most likely to
    invent if the candidate doesn't actually have it — confirmed live: a
    hallucinated "MLOps" claim went undetected because it wasn't in the
    curated alias dict and wasn't (correctly) in the candidate's own skills,
    so it was never even considered a checkable term at all. Including the
    offer's stack closes that blind spot for the terms that matter most.
    """
    vocabulary: set[str] = set()
    for canonical, aliases in PROTECTED_FACT_ALIASES.items():
        vocabulary.add(canonical)
        vocabulary.update(aliases)
    vocabulary.update(claim.text for claim in claims if claim.section == "skill")
    if offer_tech_stack:
        vocabulary.update(s.strip() for s in offer_tech_stack.split(",") if s.strip())
    return vocabulary


def _extract_tech_claims(cv_text: str, vocabulary: set[str]) -> list[str]:
    """Vocabulary terms that actually appear in the CV, alphanumeric-boundary
    aware (a plain substring check would let short abbreviations like "TS" or
    "JS" match inside unrelated words). Not `\\b`-based: `\\b` requires a
    word/non-word transition, which a term ending in a non-word character
    (e.g. "C++") never gets when followed by a space — the lookaround only
    requires the surrounding characters not be alphanumeric, which covers
    both plain words and symbol-suffixed terms. Same fix as evidence.is_evidenced."""
    return [
        term for term in vocabulary
        if re.search(rf'(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])', cv_text, re.IGNORECASE)
    ]


def _extract_significant_words(text: str) -> set[str]:
    """Extract significant words for employer/title matching.

    Returns words >= 2 characters that are not in _HEADING_STOPWORDS
    (which excludes filler, role nouns, seniority levels, etc.).
    Used by _check_employer_claim to find meaningful overlap between
    heading and evidence context.
    """
    return {
        w.strip(",.") for w in text.lower().split()
        if len(w.strip(",.")) >= 2 and w.strip(",.") not in _HEADING_STOPWORDS
    }


def _check_employer_claim(heading: str, claims: list) -> bool:
    """Whether a CV's ### entry heading (e.g. "Backend Developer - Acme
    Corp, Remote") shares a significant word with some evidence entry's
    context (e.g. "Backend Developer — Acme Corp").

    Word overlap, not exact substring: a generated CV's heading punctuation
    never matches cv-master.md's bold-title punctuation verbatim. This is a
    known, documented limitation (specs/evidence-based-cv-engine § Out of
    scope: no full-sentence claim verification), not a full identity check.

    Length cutoff is >= 2, not > 3: short real company names (IBM, SAP, HP,
    GE) are exactly 2-3 characters, and a `> 3` cutoff filtered them out of
    heading_words entirely — combined with the old "nothing significant ->
    True" fallback below, a fabricated "CTO - IBM, Remote" passed
    unconditionally, since every one of its words was either a filtered
    C-level abbreviation (now in _HEADING_STOPWORDS), a stopword, or too
    short — confirmed live via /code-review. An earlier `>= 3` cutoff still
    excluded 2-letter names (HP, GE) despite this docstring's own claim —
    also confirmed via /code-review — so the cutoff is now >= 2, with the
    2-letter connector words that opens up (to/in/at/on/de/la/el/...) added
    to _HEADING_STOPWORDS instead of relying on length to filter them. The
    fallback itself also flipped from True to False: a heading with nothing
    significant to compare should not be assumed evidenced by default (the
    safer failure direction for a truth gate), and every entry_context
    observed in practice so far still yields at least one real
    distinguishing word.

    Excludes "certification" claims: a generated CV's ### heading only ever
    comes from EXPERIENCE, PROJECTS, or EDUCATION (CERTIFICATIONS renders as
    a plain bullet list, never a ### heading — see cmd_cv_generate's
    skeleton), so a certification's entry_context can never legitimately be
    the thing a heading is verified against. Without this filter, a
    fabricated "### Cloud Engineer - AWS, Remote" heading passed as
    supported whenever cv-master.md merely listed an AWS certification whose
    issuer is "Amazon Web Services" — confirmed via /code-review, and
    reproducible with cv-master.md's pre-existing bullet-style certification
    format too, not just the GFM-table format this release added support
    for.
    """
    heading_words = _extract_significant_words(heading)
    if not heading_words:
        return False  # nothing significant to compare — don't assume evidenced
    for claim in claims:
        if claim.section == "certification" or not claim.entry_context:
            continue
        context_words = _extract_significant_words(claim.entry_context)
        if heading_words & context_words:
            return True
    return False


def cmd_cv_verify(cv_file: str, as_json: bool = False) -> None:
    """Deterministic truth gate for a generated CV.

    Extracts protected-fact claims (technologies, metrics, employer/project/
    title names) from the CV and checks each against the Evidence Graph
    parsed fresh from cv-master.md — no LLM calls (ADR-003), no
    agent-executed prompt. Unlike `cv review`/`cv review-blind`, the result
    here is directly authoritative on exit: 0 for PASS, 1 for BLOCKED (every
    unsupported claim listed). On PASS, the verified claim texts are
    snapshotted to offers.cv_evidence_used for later audit (see cmd_show) —
    an immutable record of what backed this CV, not a live cache.
    """
    import json

    from applyr.db import get_conn

    cv_path = Path(cv_file).resolve()
    content = read_text_or_die(cv_path)

    if cv_path.suffix == ".md":
        cv_text = _parse_markdown_for_review(content)
    else:
        cv_text = _strip_html_tags(content)

    offer_id = _extract_offer_id_from_md(content)
    if offer_id is None:
        die("Error: no offer id found in this CV — pass a file generated by 'applyr cv generate'.",
            code="no_offer_id")

    conn = get_conn()
    try:
        offer = conn.execute("SELECT id, tech_stack FROM offers WHERE id = ?", (offer_id,)).fetchone()
    finally:
        conn.close()
    if not offer:
        die(f"Error: offer #{offer_id} not found.", code="not_found", details={"offer_id": offer_id})

    cv_master = get_cv_master_path()
    if not cv_master.exists():
        die("Error: cv-master.md not found. Run 'applyr init' first.", code="cv_master_missing")
    claims = parse_evidence(cv_master.read_text(encoding="utf-8"))

    vocabulary = _build_tech_vocabulary(claims, offer["tech_stack"])
    no_comments = _strip_html_comments(content)

    results = []
    for term in _extract_tech_claims(cv_text, vocabulary):
        results.append({"category": "technology", "claim": term, "supported": is_evidenced(term, claims)})
    for metric in _METRIC_RE.findall(cv_text):
        results.append({"category": "metric", "claim": metric, "supported": is_evidenced(metric, claims)})
    heading_re = _ENTRY_HEADING_RE if cv_path.suffix == ".md" else _ENTRY_HEADING_HTML_RE
    for heading in heading_re.findall(no_comments):
        heading = re.sub(r'<[^>]+>', ' ', heading)
        heading = re.sub(r'\s+', ' ', heading).strip()
        if not heading:
            continue
        results.append({
            "category": "employer_or_title",
            "claim": heading,
            "supported": _check_employer_claim(heading, claims),
        })

    unsupported = [r for r in results if not r["supported"]]
    passed = not unsupported

    if passed:
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE offers SET cv_evidence_used = ? WHERE id = ?",
                (json.dumps([r["claim"] for r in results]), offer_id),
            )
            conn.commit()
        finally:
            conn.close()

    if as_json:
        payload = {
            "passed": passed,
            "offer_id": offer_id,
            "claims": results,
            "unsupported": unsupported,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*60}")
        print(f"  CV Verify — {cv_path.name}  (offer #{offer_id})")
        print(f"{'='*60}")
        print(f"\n  Claims checked : {len(results)}")
        print(f"  Supported      : {len(results) - len(unsupported)}")
        print(f"  Unsupported    : {len(unsupported)}")
        if unsupported:
            print("\n  UNSUPPORTED CLAIMS:")
            for r in unsupported:
                print(f"    [{r['category']}] {r['claim']}")
            print("\n  >> BLOCKED — remove or ground these claims in cv-master.md before sending this CV.")
        else:
            print("\n  >> PASS — every checked claim is grounded in cv-master.md.")

    if not passed:
        sys.exit(1)


# ---------------------------------------------------------------------------
# cmd_cv_review_blind
# ---------------------------------------------------------------------------

def cmd_cv_review_blind(offer_id: int, as_json: bool = False) -> None:
    """Independently evaluate cv-master.md against a job offer without referencing
    the Matcher's compatibility score.

    This is the Recruiter agent: it reads cv-master.md fresh, evaluates it
    against the offer, and returns an ATS assessment with verdict.
    """
    import json

    from applyr.config import load_config
    from applyr.db import get_conn

    # Load thresholds from config
    config = load_config()
    threshold_apply = config["general"].get("threshold_apply", 80)
    threshold_maybe = config["general"].get("threshold_maybe", 60)

    # 1. Load offer from DB (WITHOUT compatibility_pct — blind)
    conn = get_conn()
    try:
        offer = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not offer:
            die(f"Error: offer #{offer_id} not found.", code="not_found")
        topics = conn.execute(
            "SELECT topic, score, detail FROM offer_topics WHERE offer_id = ? ORDER BY score DESC",
            (offer_id,),
        ).fetchall()
    finally:
        conn.close()

    # 2. Read cv-master.md fresh
    cv_master_path = get_cv_master_path()
    if not cv_master_path.exists():
        die("Error: cv-master.md not found. Run 'applyr init' first.", code="cv_master_missing")

    cv_master_text = cv_master_path.read_text(encoding="utf-8")
    report = inspect_cv_master(cv_master_text)
    if not report.filled:
        die(f"Error: cv-master.md is {report.reason}.", code="cv_master_missing")

    # Parse cv-master.md for review
    cv_text = _parse_markdown_for_review(cv_master_text)

    # 3. Build offer context (WITHOUT compatibility_pct — blind)
    offer_lines = [
        f"Target Position : {offer['title']}",
        f"Company         : {offer['company'] or 'Not specified'}",
        f"Work Mode       : {offer['work_mode'] or 'Not specified'}",
        f"Location        : {offer['location'] or 'Not specified'}",
        f"Seniority       : {offer['seniority_level'] or 'Not specified'}",
        f"Tech Stack Req. : {offer['tech_stack'] or 'Not specified'}",
    ]
    if offer["summary"]:
        offer_lines.append(f"Job Summary     : {offer['summary']}")
    if topics:
        offer_lines.append("")
        offer_lines.append("Required Skills (from job posting):")
        offer_lines += [f"  {t['topic']}: importance implied by job posting" for t in topics]
    offer_context = "\n".join(offer_lines)

    # 4. Generate review prompt (independent evaluation)
    prompt = f"""\
You are a senior technical recruiter with 10+ years of experience reviewing CVs for tech roles. You are thorough, fair, and direct.

## Task
Independently evaluate the following candidate profile against the target position.
You do NOT know the candidate's self-assessed compatibility score — evaluate purely based on the profile and job requirements.

## Target position context
{offer_context}

## Candidate profile (cv-master.md)
{cv_text}

{_BLIND_REVIEW_RUBRIC}

{_BLIND_REVIEW_OUTPUT_FORMAT}

Be specific. Reference exact sections from the profile. Do not be vague."""

    # 5. Determine verdict based on thresholds (from config)
    # The agent will parse the ATS COMPATIBILITY SCORE from the prompt output and classify
    # For JSON output, we include the thresholds so the agent can classify
    if as_json:
        payload = {
            "offer_id": offer_id,
            "cv_master_file": str(cv_master_path),
            "cv_text": cv_text,
            "offer_context": offer_context,
            "prompt": prompt,
            "thresholds": {
                "apply": threshold_apply,
                "maybe": threshold_maybe,
            },
            "instructions": (
                "Parse ATS COMPATIBILITY SCORE from the prompt output. "
                f"If score >= {threshold_apply}: verdict = STRONG_MATCH. "
                f"If score >= {threshold_maybe} and < {threshold_apply}: verdict = CLOSE_MATCH, include conditional_advice. "
                f"If score < {threshold_maybe}: verdict = NO_MATCH, include gaps."
            ),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(prompt)
        print()
        print(f"---")
        print(f"Thresholds from config: APPLY >= {threshold_apply}%, MAYBE >= {threshold_maybe}%")
        print(f"After evaluating, classify as:")
        print(f"  STRONG_MATCH  if score >= {threshold_apply}")
        print(f"  CLOSE_MATCH   if score >= {threshold_maybe} and < {threshold_apply}")
        print(f"  NO_MATCH      if score < {threshold_maybe}")


def cmd_cv_ats_check(cv_file: str, as_json: bool = False) -> None:
    """Check CV for ATS compatibility issues.

    Validates:
    - Single column layout
    - Standard section headers
    - No images, tables, text boxes
    - Contact info placement
    - Date format consistency

    Args:
        cv_file: Path to CV markdown file
        as_json: Output as JSON if True
    """
    from applyr.ats import validate_ats_format

    cv_path = Path(cv_file)
    if not cv_path.exists():
        die(f"CV file not found: {cv_file}", code="file_not_found")

    try:
        cv_text = cv_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # A rendered PDF is the most common accident here: cv pdf deletes the
        # temporary .html it built from, but the .md source usually survives
        # next to it. Exclude cv_path itself from the candidates — if the
        # input already ends in .md or .html, with_suffix() returns the same
        # broken path, which would otherwise point the user right back at it.
        sibling = next(
            (s for ext in (".md", ".html") if (s := cv_path.with_suffix(ext)) != cv_path and s.exists()),
            None,
        )
        hint = (
            f" Try: applyr cv ats-check {sibling}"
            if sibling
            else " ats-check reads the CV source (.md or .html), not a rendered PDF."
        )
        die(f"{cv_file} is not a text file.{hint}", code="unsupported_format",
            details={"path": str(cv_path)})
    report = validate_ats_format(_strip_html_comments(cv_text))

    if as_json:
        payload = {
            "cv_file": str(cv_path),
            "score": report.score,
            "format_ok": report.format_ok,
            "headers_ok": report.headers_ok,
            "content_ok": report.content_ok,
            "issues": [
                {"category": i.category, "severity": i.severity, "message": i.message, "fix": i.fix}
                for i in report.issues
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"ATS COMPATIBILITY SCORE: {report.score}/100")
        print("(heuristic formatting check — not a prediction of any specific employer's ATS)")
        print()

        if report.issues:
            print("ISSUES:")
            for issue in report.issues:
                icon = "✗" if issue.severity == "critical" else "△" if issue.severity == "warning" else "ℹ"
                print(f"  {icon} [{issue.severity}] {issue.message}")
                print(f"    Fix: {issue.fix}")
            print()
        else:
            print("✓ No ATS issues detected")
            print()

        if report.score >= 80:
            print("VERDICT: READY TO SEND")
        elif report.score >= 60:
            print("VERDICT: NEEDS MINOR EDITS")
        else:
            print("VERDICT: NEEDS MAJOR REVISION")


def cmd_cv_keywords(offer_id: int, as_json: bool = False) -> None:
    """Extract keywords from offer and match against CV.

    Shows matched, missing, and extra keywords.

    Args:
        offer_id: Offer ID to extract keywords from
        as_json: Output as JSON if True
    """
    from applyr.ats import extract_keywords, match_keywords
    from applyr.db import get_conn

    conn = get_conn()
    try:
        cursor = conn.execute(
            "SELECT * FROM offers WHERE id = ?", (offer_id,)
        )
        offer = cursor.fetchone()
    finally:
        conn.close()

    if offer is None:
        die(f"Offer #{offer_id} not found", code="not_found")

    offer_data = dict(offer)
    keywords = extract_keywords(offer_data)

    if not keywords:
        die("No keywords found in offer (missing tech_stack)", code="no_keywords")

    # Find the CV file for this offer.
    #
    # This globbed for `*offer_<id>*`, a naming convention nothing produces:
    # `cv generate` names files after the company slug (`cv-<slug>.md`) and
    # records that stem in `cv_used`. The lookup therefore never matched, and
    # the command told users to run the generate step they had just run.
    # `cv_used` is the authoritative link, so read it first and keep the glob
    # as a fallback for hand-named files.
    cv_dir = get_output_dir()
    cv_path = None

    recorded = offer_data.get("cv_used")
    if recorded:
        stem = Path(recorded).stem
        cv_path = next((p for ext in (".md", ".html") if (p := cv_dir / f"{stem}{ext}").exists()), None)

    if cv_path is None:
        cv_files = sorted(cv_dir.glob(f"*offer_{offer_id}*"))
        cv_path = cv_files[0] if cv_files else None

    if cv_path is None:
        die(f"No CV found for offer #{offer_id}. Run 'applyr cv generate {offer_id}' first.", code="no_cv")

    # Match against the CV body only. The generated file opens with YAML
    # frontmatter carrying the offer's own `tech_stack` and `summary`, so
    # matching the whole file compared the offer's keywords against a verbatim
    # copy of themselves: every keyword hit, every CV scored 100% STRONG, and a
    # CV mentioning neither AWS nor Redux nor Webpack was reported as covering
    # all three. The same file also carries an HTML `<!-- TAILOR: ... -->` /
    # `<!-- NOT INCLUDED: ... -->` scaffold comment naming the very keywords
    # the agent chose to leave out — left unstripped, those show up as
    # "matched" too.
    try:
        cv_text = _strip_html_comments(_strip_frontmatter(cv_path.read_text(encoding="utf-8")))
    except UnicodeDecodeError:
        die(f"{cv_path} is not readable as text — check how it was saved (expected UTF-8).",
            code="unsupported_format", details={"path": str(cv_path)})
    report = match_keywords(cv_text, keywords)

    if as_json:
        payload = {
            "offer_id": offer_id,
            "keywords": keywords,
            "match_rate": report.match_rate,
            "matched": [{"keyword": m.keyword, "context": m.context} for m in report.matched],
            "missing": [{"keyword": m.keyword, "suggestion": m.context} for m in report.missing],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"KEYWORD MATCH: {report.match_rate}%")
        print(f"  Matched: {len(report.matched)}/{len(keywords)}")
        print()

        if report.matched:
            print("MATCHED:")
            for m in report.matched:
                print(f"  ✓ {m.keyword}")
            print()

        if report.missing:
            print("MISSING:")
            for m in report.missing:
                print(f"  ✕ {m.keyword}")
                print(f"    Suggestion: {m.context}")
            print()

        if report.match_rate >= 80:
            print("KEYWORD STATUS: STRONG")
        elif report.match_rate >= 60:
            print("KEYWORD STATUS: ADEQUATE — consider adding missing keywords")
        else:
            print("KEYWORD STATUS: WEAK — add missing keywords to improve ATS compatibility score")


def analyze_bullets(bullets: list[str]) -> dict:
    """Analyze bullet points for quality issues.

    Detects:
    - Weak verbs (responsible for, worked on, helped)
    - Missing metrics (no numbers, percentages, amounts)
    - Strong bullets (have action verbs + metrics)

    Args:
        bullets: List of bullet point strings

    Returns:
        Dict with weak, strong, and no_metrics lists
    """
    import json as json_module

    patterns_path = Path(__file__).parent / "templates" / "bullet_patterns.json"
    with open(patterns_path) as f:
        patterns = json_module.load(f)

    weak = []
    strong = []
    no_metrics = []

    for bullet in bullets:
        bullet_lower = bullet.lower()
        has_weak_verb = False
        matched_weak = None

        for weak_verb in patterns["weak_verbs"]:
            if weak_verb in bullet_lower:
                has_weak_verb = True
                matched_weak = weak_verb
                break

        has_metric = False
        for metric in patterns["metric_patterns"]:
            if re.search(metric["pattern"], bullet_lower):
                has_metric = True
                break

        if has_weak_verb:
            weak.append({"original": bullet, "weak_verb": matched_weak})
        elif has_metric:
            strong.append({"original": bullet})
        else:
            no_metrics.append({"original": bullet})

    return {"weak": weak, "strong": strong, "no_metrics": no_metrics}


def suggest_improvements(bullet: str) -> list[dict]:
    """Suggest improvements for a bullet point.

    Args:
        bullet: Single bullet point string

    Returns:
        List of suggestions with type and suggestion text
    """
    import json as json_module

    patterns_path = Path(__file__).parent / "templates" / "bullet_patterns.json"
    with open(patterns_path) as f:
        patterns = json_module.load(f)

    suggestions = []
    bullet_lower = bullet.lower()

    # Check for weak verbs
    for weak_verb, strong_verbs in patterns["strong_verbs"].items():
        if weak_verb in bullet_lower:
            for strong_verb in strong_verbs[:2]:
                suggestions.append({
                    "type": "strong_verb",
                    "original": weak_verb,
                    "suggestion": f"Replace '{weak_verb}' with '{strong_verb}'"
                })
            break

    # Check for missing metrics
    has_metric = False
    for metric in patterns["metric_patterns"]:
        if re.search(metric["pattern"], bullet_lower):
            has_metric = True
            break

    if not has_metric:
        suggestions.append({
            "type": "metric",
            "suggestion": "Add measurable outcome (%, $, users, time saved)"
        })

    return suggestions


def cmd_cv_bullet_optimize(cv_file: str, as_json: bool = False) -> None:
    """Analyze and suggest improvements for CV bullet points.

    Args:
        cv_file: Path to CV markdown file
        as_json: Output as JSON if True
    """
    cv_path = Path(cv_file)
    if not cv_path.exists():
        die(f"CV file not found: {cv_file}", code="file_not_found")

    try:
        cv_text = cv_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        sibling = next(
            (s for ext in (".md", ".html") if (s := cv_path.with_suffix(ext)) != cv_path and s.exists()),
            None,
        )
        hint = (
            f" Try: applyr cv bullet-optimize {sibling}"
            if sibling
            else " bullet-optimize reads the CV source (.md or .html), not a rendered PDF."
        )
        die(f"{cv_file} is not a text file.{hint}", code="unsupported_format",
            details={"path": str(cv_path)})

    # Extract bullet points (lines starting with -)
    bullets = []
    for line in cv_text.split('\n'):
        line = line.strip()
        if line.startswith('- '):
            bullets.append(line[2:])

    if not bullets:
        die("No bullet points found in CV", code="no_bullets")

    analysis = analyze_bullets(bullets)

    if as_json:
        payload = {
            "cv_file": str(cv_path),
            "total_bullets": len(bullets),
            "weak_count": len(analysis["weak"]),
            "strong_count": len(analysis["strong"]),
            "no_metrics_count": len(analysis["no_metrics"]),
            "weak": analysis["weak"],
            "strong": analysis["strong"],
            "no_metrics": analysis["no_metrics"],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"BULLET ANALYSIS: {len(bullets)} bullets found")
        print()

        if analysis["weak"]:
            print(f"WEAK VERBS ({len(analysis['weak'])}):")
            for w in analysis["weak"]:
                print(f"  △ \"{w['original']}\"")
                print(f"    Weak verb: '{w['weak_verb']}'")
                suggestions = suggest_improvements(w["original"])
                for s in suggestions:
                    print(f"    {s['suggestion']}")
            print()

        if analysis["no_metrics"]:
            print(f"MISSING METRICS ({len(analysis['no_metrics'])}):")
            for n in analysis["no_metrics"]:
                print(f"  △ \"{n['original']}\"")
                print(f"    Add: percentage, dollar amount, users served, or time saved")
            print()

        if analysis["strong"]:
            print(f"STRONG ({len(analysis['strong'])}):")
            for s in analysis["strong"]:
                print(f"  ✓ \"{s['original']}\"")
            print()

        total_issues = len(analysis["weak"]) + len(analysis["no_metrics"])
        if total_issues == 0:
            print("VERDICT: ALL BULLETS ARE STRONG")
        elif total_issues <= 2:
            print("VERDICT: NEEDS MINOR EDITS")
        else:
            print("VERDICT: NEEDS SIGNIFICANT IMPROVEMENT")


def _profile_haystack(cv_master: dict) -> str:
    """Everything the profile asserts, flattened for substring checks.

    Prefers the raw cv-master text when the caller supplies it, because the
    parsed dict only captures a few fields and a skill named anywhere else
    would read as absent.
    """
    if cv_master.get("raw"):
        return str(cv_master["raw"])

    parts = [str(cv_master.get("skills") or "")]
    for project in cv_master.get("projects") or []:
        parts += [str(project.get(k) or "") for k in ("name", "description", "stack")]
    return " ".join(parts)


def generate_cover_letter(offer_data: dict, cv_master: dict) -> str:
    """Generate a tailored cover letter from offer and profile data.

    Args:
        offer_data: Dict with offer fields (title, company, tech_stack, summary)
        cv_master: Dict with profile data (name, email, phone, skills, projects)

    Returns:
        Generated cover letter text
    """
    from datetime import datetime

    # Same language the CV is generated in — a letter en inglés for una oferta
    # en español reads as machine-made, same reasoning as resolve_cv_language().
    language = resolve_cv_language(offer_data.get("language"))
    template_name = "cover_letter.md" if language == "en" else f"cover_letter_{language}.md"
    template_path = Path(__file__).parent / "templates" / template_name
    template = template_path.read_text()

    # Key skills to claim: the overlap between what the offer asks for and what
    # the profile actually contains — never the offer's list on its own.
    #
    # This used to take the offer's first three technologies verbatim, so the
    # letter asserted "my background in <whatever the employer wanted>" with no
    # reference to the candidate at all. On a real vacancy that produced "my
    # skills in React.js, Redux, Hooks" for a candidate whose profile has no
    # Redux anywhere. A letter is sent to an employer, which makes an invented
    # skill a false claim on the candidate's behalf, and "never invent skills"
    # is this tool's first rule.
    tech_stack = offer_data.get("tech_stack", "")
    profile_text = _profile_haystack(cv_master).lower()
    wanted = [s.strip() for s in tech_stack.split(",") if s.strip()]
    evidenced = [s for s in wanted if s.lower() in profile_text]
    key_skills = ", ".join(evidenced[:3]) if evidenced else "relevant technologies"

    # Extract top 3 achievements from projects
    projects = cv_master.get("projects", [])
    achievements = []
    for i, project in enumerate(projects[:3]):
        desc = project.get("description", project.get("name", ""))
        achievements.append(f"{i+1}. {project.get('name', 'Project')}: {desc}")

    if language == "es":
        months_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                     "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        today = datetime.now()
        date_str = f"{today.day} de {months_es[today.month - 1]} de {today.year}"
    else:
        date_str = datetime.now().strftime("%B %d, %Y")

    # Fill template
    letter = template.format(
        company=offer_data.get("company", "[Company]"),
        title=offer_data.get("title", "[Position]"),
        date=date_str,
        key_skills=key_skills,
        achievement_1=achievements[0] if len(achievements) > 0 else "1. [Your top achievement]",
        achievement_2=achievements[1] if len(achievements) > 1 else "2. [Your second achievement]",
        achievement_3=achievements[2] if len(achievements) > 2 else "3. [Your third achievement]",
        company_reason=offer_data.get("summary", "your company's mission and values"),
        name=cv_master.get("name", "[Your Name]"),
        email=cv_master.get("email", "[Your Email]"),
        phone=cv_master.get("phone", "[Your Phone]"),
    )

    return letter


def cmd_cv_cover_letter(offer_id: int, as_json: bool = False) -> None:
    """Generate a tailored cover letter for an offer.

    Args:
        offer_id: Offer ID to generate cover letter for
        as_json: Output as JSON if True
    """
    from applyr.db import get_conn

    conn = get_conn()
    try:
        cursor = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,))
        offer = cursor.fetchone()
    finally:
        conn.close()

    if offer is None:
        die(f"Offer #{offer_id} not found", code="not_found")

    offer_data = dict(offer)

    # Load cv-master
    cv_master_path = get_cv_master_path()
    if not cv_master_path.exists():
        die("cv-master.md not found. Run 'applyr init' first.", code="no_cv_master")

    # Parse cv-master (simple extraction)
    cv_text = cv_master_path.read_text()
    cv_master = {
        "name": "",
        "email": "",
        "phone": "",
        "skills": "",
        "projects": [],
        # The full profile, so a skill claim can be checked against everything
        # the candidate actually wrote — not just the few parsed fields.
        "raw": cv_text,
    }

    # Extract name
    name_match = re.search(r'^\*\*(.+?)\*\*', cv_text, re.MULTILINE)
    if name_match:
        cv_master["name"] = name_match.group(1)

    # Extract email
    email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', cv_text)
    if email_match:
        cv_master["email"] = email_match.group(0)

    # Extract phone
    phone_match = re.search(r'\+?\d[\d\s()-]{8,}', cv_text)
    if phone_match:
        cv_master["phone"] = phone_match.group(0)

    # Extract projects (simple: look for ### headers under a ## PROYECTOS/PROJECTS
    # heading). Must match a real `## ` section heading, not any line that
    # merely contains the word "proyectos" in prose (e.g. an intro blurb) —
    # and must turn back off on the next `## ` heading, otherwise every
    # subsequent section (including ## EXPERIENCIA PROFESIONAL's own `### `
    # entries) gets swept in as a "project" too.
    in_projects = False
    current_project = None
    for line in cv_text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('## '):
            in_projects = 'PROYECTOS' in stripped.upper() or 'PROJECTS' in stripped.upper()
            continue
        if in_projects and line.startswith('### '):
            if current_project:
                cv_master["projects"].append(current_project)
            project_name = line[4:].strip()
            current_project = {"name": project_name, "description": ""}
        elif in_projects and current_project:
            # Tolerate "Stack:" written plain or **bold** (both appear in
            # cv-master.md, in different sections).
            stack_line = stripped.lstrip('*').strip()
            if stack_line.startswith('Stack:'):
                current_project["description"] = stack_line[6:].strip()
    if current_project:
        cv_master["projects"].append(current_project)

    # Generate cover letter
    letter = generate_cover_letter(offer_data, cv_master)

    # Save to file
    company_slug = offer_data.get("company", "unknown").lower().replace(" ", "-")
    output_path = get_output_dir() / f"cover-letter-{company_slug}.txt"
    output_path.write_text(letter)

    if as_json:
        payload = {
            "offer_id": offer_id,
            "company": offer_data.get("company"),
            "output_file": str(output_path),
            "letter": letter,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Cover letter generated: {output_path}")
        print()
        print(letter)
