"""CV system — HTML skeleton generation and Chrome headless PDF export."""

import os
import subprocess
from pathlib import Path

from applyr.config import load_config, APPLYR_DIR

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
@media print {
    body { padding: 1cm 1.5cm; }
    h2 { page-break-after: avoid; }
}"""


def _make_slug(company: str | None, title: str) -> str:
    """Create a filesystem-safe slug from company and title."""
    raw = f"{company or 'unknown'}-{title}".lower()
    return raw.replace(" ", "-").replace("/", "-")[:40]


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
        print("Error: Chrome/Chromium not found.")
        print("  Set 'chrome_path' in ~/.applyr/applyr.toml under [cv]")
        print("  Or install Google Chrome / Chromium.")
        return

    html_path = Path(html_file).resolve()
    if not html_path.exists():
        print(f"Error: HTML file not found: {html_file}")
        return

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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if pdf_path.exists():
            print(f"PDF generated: {pdf_path}")
        else:
            print("Error: PDF was not generated.")
            if result.stderr:
                print(f"  Chrome stderr: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("Error: Chrome timed out after 30 seconds.")
    except FileNotFoundError:
        print(f"Error: Chrome not found at: {chrome_path}")


def cmd_cv_generate(offer_id: int, template: str = "ats") -> None:
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
            print(f"Error: offer #{offer_id} not found.")
            return

        # Load topic scores if any
        topics = conn.execute(
            "SELECT topic, score, detail FROM offer_topics WHERE offer_id = ? ORDER BY score DESC",
            (offer_id,),
        ).fetchall()
    finally:
        conn.close()

    cv_master = get_cv_master_path()
    if not cv_master.exists():
        print(f"Error: cv-master.md not found at {cv_master}")
        print("  Run 'applyr init' to create a template, then edit it with your profile.")
        return
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
    if topics:
        context_lines.append("")
        context_lines.append("    Topic Scores:")
        for t in topics:
            context_lines.append(f"      {t['topic']}: {t['score']}% — {t['detail'] or ''}")

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

    html_path.write_text(html)

    print(f"CV skeleton generated: {html_path}")
    print(f"  Offer    : #{offer_id} — {row['title']} @ {row['company'] or '?'}")
    print(f"  Template : {template} (ATS-safe)")
    print(f"  CV Master: {cv_master}")
    print()
    print("  Next steps:")
    print(f"    1. AI agent reads {cv_master}")
    print(f"    2. AI agent fills [PLACEHOLDER] values in {html_path}")
    print(f"    3. Run: applyr cv pdf {html_path}")
