"""CV system — HTML skeleton generation and Chrome headless PDF export."""

import os
import re
import subprocess
from pathlib import Path

from applyr.config import APPLYR_DIR, load_config
from applyr.constants import CHROME_STDERR_SNIPPET, CHROME_TIMEOUT_SECONDS, CV_MASTER_MIN_SIZE
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


def cmd_cv_pdf(html_file: str, output: str | None = None) -> None:
    """Convert an HTML file to PDF using Chrome headless."""
    config = load_config()
    chrome_path = config["cv"]["chrome_path"]

    if not chrome_path or not os.path.isfile(chrome_path):
        error("Error: Chrome/Chromium not found.")
        error(f"  Set 'chrome_path' in {APPLYR_DIR / 'applyr.toml'} under [cv]")
        die("Chrome/Chromium not found — required for PDF generation.",
            code="chrome_not_found", text="  Or install Google Chrome / Chromium.")

    html_path = Path(html_file).resolve()
    if not html_path.exists():
        die(f"Error: HTML file not found: {html_file}", code="not_found",
            details={"path": html_file})

    if output:
        pdf_path = Path(output).resolve()
    else:
        pdf_path = html_path.with_suffix(".pdf")

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


def cmd_cv_generate(offer_id: int, template: str = "ats", force: bool = False) -> None:
    """Generate an ATS-safe HTML CV skeleton for a specific offer.

    The HTML includes:
    - ATS-safe CSS (locked, never modify)
    - Offer context as HTML comments (company, title, tech_stack, etc.)
    - Placeholder sections for the AI agent to fill from cv-master.md

    The AI agent reads cv-master.md and replaces [PLACEHOLDER] values.
    The CSS and HTML structure must NOT be modified.
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
    cv_master_size = cv_master.stat().st_size
    if cv_master_size < CV_MASTER_MIN_SIZE:
        error(f"Error: cv-master.md looks empty ({cv_master_size} bytes).")
        die("cv-master.md is still the unfilled template.", code="empty_cv_master",
            details={"path": str(cv_master), "size": cv_master_size,
                     "min_size": CV_MASTER_MIN_SIZE},
            text=f"  Fill {cv_master} with your profile before generating a CV.")
    output_dir = get_output_dir()
    slug = _make_slug(row["company"], row["title"])
    html_path = output_dir / f"cv-{slug}.html"

    # Build offer context block for the AI agent
    context_lines = [
        f"    Target Position  : {row['title']}",
        f"    Company          : {row['company'] or 'Not specified'}",
        f"    Work Mode        : {row['work_mode'] or 'Not specified'}",
        f"    Location         : {row['location'] or 'Not specified'}",
        f"    Seniority        : {row['seniority_level'] or 'Not specified'}",
        f"    Role Category    : {row['role_category'] or 'Not specified'}",
        f"    Tech Stack Req.  : {row['tech_stack'] or 'Not specified'}",
        f"    Compatibility    : {row['compatibility_pct']}%",
    ]
    if row["summary"]:
        context_lines.append(f"    Job Summary      : {row['summary']}")

    # Topic scores deliberately stay out of the HTML. They contain candid
    # self-assessment ("no professional experience in this stack") that would
    # ship to the recruiter inside the file. `cv review` reads them from the
    # database via the applyr:offer-id marker below instead.
    context_block = "\n".join(context_lines)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CV for {row['company'] or 'Company'} - {row['title']}</title>
    <style>
{_ATS_CSS}
    </style>
</head>
<body>
<!-- applyr:offer-id={offer_id} -->

<!--
    ================================================================
    ATS CV generated by applyr — Offer #{offer_id}
    https://github.com/DeibyGS/applyr

    OFFER CONTEXT (for AI agent reference):
{context_block}

    INSTRUCTIONS FOR AI AGENT:
    1. Read {cv_master} for all content
    2. Replace every [PLACEHOLDER] below with content from cv-master.md
    3. Prioritize skills and projects relevant to: {row['tech_stack'] or row['title']}
    4. Match keywords from the job description naturally
    5. Keep to 1 page — remove less relevant sections if needed
    6. Include measurable results (%, numbers, scale) in bullet points
    7. NEVER invent content not in cv-master.md
    8. DO NOT modify the CSS or HTML structure above
    9. Show full URLs in links (linkedin.com/in/x, not just "LinkedIn")
    ================================================================
-->

<h1>[FULL NAME]</h1>
<p class="contact">
    [City, Country] |
    <a href="mailto:[EMAIL]">[EMAIL]</a> |
    [PHONE] |
    <a href="https://linkedin.com/in/[PROFILE]">linkedin.com/in/[PROFILE]</a> |
    <a href="https://github.com/[USERNAME]">github.com/[USERNAME]</a> |
    <a href="https://[WEBSITE]">[WEBSITE]</a>
</p>

<h2>Professional Summary</h2>
<p class="summary">
    [2-3 sentences tailored to {row['title']} at {row['company'] or 'this company'}.
    Highlight relevant skills for: {row['tech_stack'] or 'the role'}.
    Match keywords from the job description.
    Include both acronyms and full terms.]
</p>

<h2>Work Experience</h2>

<h3>[Job Title] - [Company], [Location], [Mode]</h3>
<p class="dates">[MM/YYYY - MM/YYYY]</p>
<ul>
    <li>[Achievement with measurable impact]</li>
    <li>[Technology or methodology used with concrete result]</li>
</ul>

<!-- Add more positions from cv-master.md if relevant to {row['title']} -->

<h2>Projects</h2>

<h3>[Project Name]</h3>
<p><strong>Stack:</strong> [Technologies] | <a href="[REPO_URL]">[REPO_URL]</a></p>
<ul>
    <li>[What it does and key technical decisions relevant to {row['tech_stack'] or 'the role'}]</li>
</ul>

<!-- Add more projects from cv-master.md if relevant -->

<h2>Education</h2>

<h3>[Degree]</h3>
<p>[Institution] | <span class="dates">[MM/YYYY - MM/YYYY]</span></p>

<h2>Certifications</h2>
<ul>
    <li>[Certification] - [Issuer] ([MM/YYYY])</li>
</ul>

<!-- Include only certifications relevant to {row['role_category'] or 'the role'} -->

<h2>Technical Skills</h2>
<p><strong>Backend:</strong> [list — prioritize skills matching: {row['tech_stack'] or 'job requirements'}]</p>
<p><strong>Frontend:</strong> [list]</p>
<p><strong>Databases:</strong> [list]</p>
<p><strong>DevOps:</strong> [list]</p>
<p><strong>Other:</strong> [list]</p>

<h2>Languages</h2>
<ul>
    <li>[Language] - [Level]</li>
</ul>

</body>
</html>"""

    # Never clobber a finished CV. Regenerating drops the skeleton back on top
    # of hours of tailored content, and there is no undo.
    if html_path.exists() and not force:
        error(f"Error: {html_path.name} already exists.")
        die(f"CV already exists at {html_path}", code="already_exists",
            details={"path": str(html_path), "offer_id": offer_id},
            text="  It would be overwritten with an empty skeleton.\n"
                 "  Pass --force to replace it, or rename the existing file first.")

    html_path.write_text(html)

    # Record which CV was used for this offer, so `applyr cv stats` can later
    # correlate CVs with outcomes. Without this nothing ever populates cv_used.
    conn = get_conn()
    try:
        conn.execute("UPDATE offers SET cv_used = ? WHERE id = ?",
                     (html_path.name, offer_id))
        conn.commit()
    finally:
        conn.close()

    print(f"CV skeleton generated: {html_path}")
    print(f"  Offer    : #{offer_id} — {row['title']} @ {row['company'] or '?'}")
    print(f"  Template : {template} (ATS-safe)")
    print(f"  CV Master: {cv_master}")
    print(f"  Recorded : cv_used = {html_path.name}")
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


def _extract_offer_context(html: str) -> str:
    """Resolve the offer context for a CV, preferring the database."""
    marker = re.search(r'applyr:offer-id=(\d+)', html)
    if marker:
        context = _offer_context_from_db(int(marker.group(1)))
        if context:
            return context

    # CVs generated before the marker existed still carry the context inline.
    legacy = re.search(r'OFFER CONTEXT.*?:(.*?)INSTRUCTIONS FOR AI AGENT', html, re.DOTALL)
    if legacy:
        return legacy.group(1).strip()
    return "(No offer context found — pass a CV generated by 'applyr cv generate')"


def cmd_cv_review(html_file: str, as_json: bool = False) -> None:
    """Generate a recruiter-review prompt for an HTML CV."""
    import json

    html_path = Path(html_file).resolve()
    if not html_path.exists():
        die(f"Error: HTML file not found: {html_file}")

    html = html_path.read_text(encoding="utf-8")
    cv_text = _strip_html_tags(html)
    offer_context = _extract_offer_context(html)

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
            "cv_file": str(html_path),
            "cv_text": cv_text,
            "offer_context": offer_context,
            "prompt": prompt,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(prompt)
