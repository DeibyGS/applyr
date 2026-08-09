"""CV system — markdown-first generation and Chrome headless PDF export."""

import os
import re
import subprocess
from pathlib import Path

from applyr.config import APPLYR_DIR, load_config
from applyr.constants import CHROME_STDERR_SNIPPET, CHROME_TIMEOUT_SECONDS
from applyr.cv_master import inspect_cv_master
from applyr.errors import die, error


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
    font-size: 11pt;
    line-height: 1.5;
    color: #1a1a1a;
    max-width: 21cm;
    margin: 0 auto;
    padding: 1.5cm 2cm;
}
h1 { font-size: 16pt; margin-bottom: 4px; color: #111; }
h2 {
    font-size: 12pt;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-bottom: 1.5px solid #333;
    padding-bottom: 3px;
    margin: 14px 0 8px;
    color: #222;
}
h3 { font-size: 11pt; margin-bottom: 2px; }
.contact { font-size: 10pt; color: #333; margin-bottom: 12px; }
.contact a { color: #333; text-decoration: none; }
.dates { font-size: 10pt; color: #555; }
.summary { margin-bottom: 10px; color: #333; }
ul { padding-left: 18px; margin: 4px 0 10px; }
li { margin-bottom: 3px; }
p { margin-bottom: 4px; }
/* Chrome adds its own default page margin on top of the body padding, which
   silently pushes a one-page CV onto a second page. Zeroing it here makes the
   body padding the single source of truth for margins. */
@page { size: A4; margin: 0; }
@media print {
    body { padding: 1.2cm 1.6cm; }
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


def _make_slug(company: str | None, title: str) -> str:
    """Create a filesystem-safe slug from company and title.

    Keeps only ASCII letters, digits and dashes so titles like "Full Stack (JS)"
    do not produce filenames that need shell quoting.
    """
    raw = f"{company or 'unknown'}-{title}".lower()
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


def _get_tailoring_hints(tech_stack: str | None, topics: dict) -> tuple[list[str], list[str], list[str]]:
    """Generate tailoring hints based on tech_stack and topic scores.

    Returns:
        Tuple of (highlight, de_emphasize, not_included) lists
    """
    highlight = []
    de_emphasize = []
    not_included = []

    if tech_stack:
        # Parse tech_stack from comma-separated string
        skills = [s.strip() for s in tech_stack.split(",") if s.strip()]
        highlight = skills

    # Get strong topics to highlight
    for topic, values in topics.items():
        score = values.get("score", 0)
        if score >= 80:
            label = {
                "tech_stack": "Technical Skills",
                "experience": "Work Experience",
                "projects": "Projects",
                "education": "Education",
                "english": "Languages",
                "cultural_fit": "Work Preferences",
            }.get(topic, topic)
            if label not in highlight:
                highlight.append(label)

    # Get missing topics to de-emphasize
    for topic, values in topics.items():
        score = values.get("score", 0)
        if score < 50:
            label = {
                "tech_stack": "Technical Skills",
                "experience": "Work Experience",
                "projects": "Projects",
                "education": "Education",
                "english": "Languages",
                "cultural_fit": "Work Preferences",
            }.get(topic, topic)
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
    report = inspect_cv_master(cv_master.read_text(encoding="utf-8"))
    if not report.filled:
        error(f"Error: cv-master.md is {report.reason}.")
        die("cv-master.md is still the unfilled template.", code="empty_cv_master",
            details={"path": str(cv_master),
                     "placeholder_sections": list(report.placeholder_sections),
                     "content_words": report.content_words},
            text=f"  Fill {cv_master} with your profile before generating a CV.")
    output_dir = get_output_dir()
    slug = _make_slug(row["company"], row["title"])
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

    highlight, de_emphasize, not_included = _get_tailoring_hints(row["tech_stack"], topics_dict)
    tailoring_hints = _format_tailoring_hints(highlight, de_emphasize, not_included)

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
Highlight relevant skills for: {row['tech_stack'] or 'the role'}.
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

- [What it does and key technical decisions relevant to {row['tech_stack'] or 'the role'}]

<!-- Add more projects from cv-master.md if relevant -->

## {headings['education']}

### [Degree]
[Institution] | [MM/YYYY - MM/YYYY]

## {headings['certifications']}

- [Certification] - [Issuer] ([MM/YYYY])

<!-- Include only certifications relevant to {row['role_category'] or 'the role'} -->

## {headings['skills']}

**{headings['backend']}:** [list — prioritize skills matching: {row['tech_stack'] or 'job requirements'}]
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
ATS SCORE: [0-100]/100

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


def _strip_html_tags(html: str) -> str:
    """Remove markup, styles and comments, returning the readable CV text."""
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
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


def _parse_markdown_for_review(md: str) -> str:
    """Parse markdown content for CV review, extracting readable text.

    Strips YAML frontmatter and HTML comments, converts markdown to plain text.
    """
    # Strip YAML frontmatter
    if md.startswith("---"):
        end = md.find("---", 3)
        if end != -1:
            md = md[end + 3:].lstrip("\n")

    # Strip HTML comments
    text = re.sub(r'<!--.*?-->', '', md, flags=re.DOTALL)

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
    if not cv_path.exists():
        die(f"Error: CV file not found: {cv_file}")

    content = cv_path.read_text(encoding="utf-8")

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

    cv_text = cv_path.read_text()
    report = validate_ats_format(cv_text)

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
        print(f"ATS SCORE: {report.score}/100")
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

    if not offer is None:
        die(f"Offer #{offer_id} not found", code="not_found")

    offer_data = dict(offer)
    keywords = extract_keywords(offer_data)

    if not keywords:
        die("No keywords found in offer (missing tech_stack)", code="no_keywords")

    # Find the CV file for this offer
    cv_dir = APPLYR_DIR / "cv"
    cv_files = list(cv_dir.glob(f"*offer_{offer_id}*"))
    if not cv_files:
        die(f"No CV found for offer #{offer_id}. Run 'applyr cv generate {offer_id}' first.", code="no_cv")

    cv_text = cv_files[0].read_text()
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
            print("KEYWORD STATUS: WEAK — add missing keywords to improve ATS score")
