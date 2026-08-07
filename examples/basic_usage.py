#!/usr/bin/env python3
"""Basic usage examples for applyr.

Run from the repo root:
    python examples/basic_usage.py

Or use the CLI directly:
    applyr init
    applyr add '{"title":"Engineer","company":"Acme"}'
    applyr list
"""

import json
import subprocess
import sys


def run(cmd: str) -> str:
    """Run a shell command and return stdout."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=30
    )
    return result.stdout.strip()


def main():
    print("=== applyr basic usage ===\n")

    # 1. Initialize
    print("1. applyr init")
    print(run("applyr init"))

    # 2. Add an offer
    offer = {
        "title": "Senior Python Engineer",
        "company": "Acme Corp",
        "summary": "Build data pipelines with FastAPI and PostgreSQL",
        "work_mode": "hybrid",
        "location": "Madrid",
        "seniority_level": "senior",
        "tech_stack": "Python, FastAPI, PostgreSQL, Docker",
        "compatibility_pct": 78,
        "status": "pending",
    }
    print("\n2. applyr add '<json>'")
    print(run(f"applyr add '{json.dumps(offer)}'"))

    # 3. List offers
    print("\n3. applyr list")
    print(run("applyr list"))

    # 4. Show details
    print("\n4. applyr show 1")
    print(run("applyr show 1"))

    # 5. Stats
    print("\n5. applyr stats")
    print(run("applyr stats"))

    # 6. JSON output (for agent integration)
    print("\n6. applyr list --json")
    output = run("applyr list --json")
    if output:
        data = json.loads(output)
        print(json.dumps(data, indent=2)[:500])


if __name__ == "__main__":
    main()
