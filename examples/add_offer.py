#!/usr/bin/env python3
"""Example: register a job offer programmatically.

This shows all available fields for the add command.
Run: python examples/add_offer.py
"""

import json
import subprocess


def add_offer(offer: dict) -> str:
    """Add an offer via the CLI."""
    result = subprocess.run(
        ["applyr", "add", json.dumps(offer)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def main():
    # Full offer with all optional fields
    full_offer = {
        # Required
        "title": "ML Engineer",
        "company": "TechStart",
        # Optional: description
        "summary": "Build recommendation engine with PyTorch and Redis",
        # Optional: dates
        "date_received": "2026-08-01",
        "date_applied": "2026-08-02",
        # Optional: scoring (usually set by agent)
        "compatibility_pct": 82,
        # Optional: status
        "status": "applied",
        "canal": "linkedin",
        # Optional: location
        "work_mode": "remote",
        "location": "EU",
        # Optional: salary
        "salary_min": 55000,
        "salary_max": 70000,
        "salary_period": "annual",
        # Optional: classification
        "seniority_level": "mid",
        "role_category": "engineering",
        "tech_stack": "Python, PyTorch, Redis, PostgreSQL",
        # Optional: materials
        "cover_letter": 0,
        # Optional: contact
        "contact_name": "Jane Smith",
        "contact_role": "Engineering Manager",
        "job_url": "https://example.com/jobs/ml-engineer",
        # Optional: notes
        "notes": "Series B startup, 50 people, remote-first",
    }

    print("=== Adding offer with all fields ===\n")
    print(json.dumps(full_offer, indent=2))
    print()
    print(add_offer(full_offer))

    # Minimal offer (only required fields)
    minimal_offer = {
        "title": "Backend Developer",
        "company": "SmallCo",
    }

    print("\n=== Adding minimal offer ===\n")
    print(json.dumps(minimal_offer, indent=2))
    print()
    print(add_offer(minimal_offer))


if __name__ == "__main__":
    main()
