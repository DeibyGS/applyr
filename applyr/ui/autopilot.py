"""Auto-pilot daemon — watches for user responses and processes them automatically.

Run with: applyr autopilot

Listens to the SSE stream for user.response events. When the user sends a
"process" command (procesala, procesar, etc.) to an agent, the daemon
automatically executes the pipeline: intake → add → score → cv generate.

This daemon must run alongside `applyr ui` (the backend).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

DEFAULT_BACKEND = "http://127.0.0.1:8000"
POLL_INTERVAL = 3  # seconds between SSE reconnect attempts

PROCESS_KEYWORDS = re.compile(
    r"\b(proces[as]?l[ao]?|procesar|process|ejecut[as]?l[ao]?|go|dale|adelante)\b",
    re.IGNORECASE,
)


def _check_backend(url: str) -> bool:
    """Return True if the backend is reachable."""
    try:
        r = requests.get(f"{url}/api/health", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False


def _get_pending_intake(url: str) -> list[dict]:
    """Fetch pending intake items from the backend."""
    try:
        r = requests.get(f"{url}/api/intake", params={"status": "pending"}, timeout=5)
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, json.JSONDecodeError):
        return []


def _process_intake_item(item: dict, url: str) -> bool:
    """Process a single intake item through the pipeline.

    Returns True if processing succeeded.
    """
    intake_id = item["id"]
    raw_text = item["raw_text"]

    # Extract company and title from raw text (first meaningful lines)
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    company = lines[0] if lines else "Unknown"
    title = lines[1] if len(lines) > 1 else "Unknown"

    print(f"  Processing intake #{intake_id}: {title} @ {company}")

    # Step 1: Check duplicates
    result = subprocess.run(
        ["applyr", "search", "--company", company],
        capture_output=True, text=True, timeout=30,
    )
    if "No offers found" not in result.stdout and result.returncode == 0:
        print(f"  ⚠ Duplicate found for {company} — skipping")
        return False

    # Step 2: Add offer with intake_id
    # Build a minimal JSON for applyr add
    add_data = {
        "title": title,
        "company": company,
        "language": "es",
        "work_mode": "remote",  # default, user can update later
        "canal": "linkedin_easy",
        "intake_id": intake_id,
    }

    result = subprocess.run(
        ["applyr", "add", json.dumps(add_data), "--intake-id", str(intake_id)],
        capture_output=True, text=True, timeout=60,
    )

    if result.returncode != 0:
        print(f"  ❌ applyr add failed: {result.stderr[:200]}")
        return False

    # Extract offer ID from output
    match = re.search(r"ID\s*:\s*(\d+)", result.stdout)
    if not match:
        print(f"  ❌ Could not parse offer ID from applyr add output")
        return False

    offer_id = int(match.group(1))
    print(f"  ✅ Offer #{offer_id} created")

    # Step 3: Generate CV
    result = subprocess.run(
        ["applyr", "cv", "generate", str(offer_id)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode == 0:
        print(f"  ✅ CV generated for #{offer_id}")
    else:
        print(f"  ⚠ CV generation had issues: {result.stderr[:100]}")

    return True


def _listen_sse(url: str) -> None:
    """Listen to SSE stream and process user responses."""
    print(f"  Connecting to SSE stream at {url}/api/events/enriched...")

    try:
        with requests.get(
            f"{url}/api/events/enriched",
            stream=True,
            timeout=(5, 600),  # 5s connect, 600s read timeout
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue

                try:
                    event = json.loads(line[6:])  # strip "data: "
                except json.JSONDecodeError:
                    continue

                if event.get("type") != "user.response":
                    continue

                agent_id = event.get("agent_id", "")
                message = event.get("payload", {}).get("message", "")

                print(f"\n📩 Response from user to {agent_id}: \"{message}\"")

                if not PROCESS_KEYWORDS.search(message):
                    print(f"  Not a process command — ignoring")
                    continue

                # Process pending intake items
                pending = _get_pending_intake(url)
                if not pending:
                    print(f"  No pending intake items to process")
                    continue

                for item in pending:
                    _process_intake_item(item, url)

    except requests.RequestException as e:
        print(f"  SSE connection error: {e}")
        raise


def run_autopilot(url: str = DEFAULT_BACKEND) -> None:
    """Main autopilot loop — reconnects on failure."""
    print("🤖 applyr autopilot — watching for user responses")
    print(f"   Backend: {url}")
    print(f"   Send 'procesala' in the UI to trigger processing")
    print()

    if not _check_backend(url):
        print(f"❌ Backend not reachable at {url}")
        print(f"   Start it with: applyr ui")
        sys.exit(1)

    print(f"✅ Backend connected")

    while True:
        try:
            _listen_sse(url)
        except KeyboardInterrupt:
            print("\n👋 Autopilot stopped")
            break
        except requests.RequestException:
            print(f"  Reconnecting in {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)
