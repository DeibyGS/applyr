"""CV system — HTML generation helpers and Chrome headless PDF export."""

import os
import subprocess
from pathlib import Path

from applyr.config import load_config, APPLYR_DIR


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
    """Show instructions for generating a tailored CV for an offer.

    The actual CV tailoring is done by the AI agent using cv-master.md
    as source. This command provides the context and instructions.
    """
    from applyr.db import get_conn

    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
        if not row:
            print(f"Error: offer #{offer_id} not found.")
            return

        cv_master = get_cv_master_path()
        output_dir = get_output_dir()

        print(f"\n--- CV Generation for Offer #{offer_id} ---")
        print(f"  Position  : {row['title']}")
        print(f"  Company   : {row['company'] or '?'}")
        print(f"  Tech Stack: {row['tech_stack'] or 'not specified'}")
        print(f"  Seniority : {row['seniority_level'] or 'not specified'}")
        print(f"  Template  : {template}")
        print()
        print(f"  CV Master : {cv_master}")
        print(f"  Output Dir: {output_dir}")
        print()

        if not cv_master.exists():
            print("  Warning: cv-master.md not found. Create it first:")
            print(f"    Edit {cv_master}")
            print()

        slug = f"{row['company'] or 'unknown'}-{row['title']}".lower()
        slug = slug.replace(" ", "-")[:40]
        html_name = f"cv-{slug}.html"
        pdf_name = f"cv-{slug}.pdf"

        print("  To generate:")
        print(f"    1. AI agent reads {cv_master} + this offer's details")
        print(f"    2. AI agent creates {output_dir / html_name}")
        print(f"    3. Run: applyr cv pdf {output_dir / html_name}")
        print(f"    4. Output: {output_dir / pdf_name}")
    finally:
        conn.close()
