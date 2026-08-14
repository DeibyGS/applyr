<div align="center">

# applyr

**Your AI agent's job application tracker — score offers, detect duplicates, generate ATS-safe CVs, all from the terminal.**

applyr is the storage layer; your AI coding agent is the brain. Paste a job offer, get a weighted 0–100 compatibility score, an APPLY / SKIP recommendation, skill gaps, and a tailored ATS-safe CV — local, private, agent-native.

**Fast to start** — one command. **Local-first** — SQLite on your machine, no API keys, nothing leaves your system.

[![PyPI version](https://img.shields.io/pypi/v/applyr?color=blue)](https://pypi.org/project/applyr/)
[![PyPI downloads](https://img.shields.io/pypi/dm/applyr?color=brightgreen)](https://pypi.org/project/applyr/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![CI](https://github.com/DeibyGS/applyr/actions/workflows/python-package.yml/badge.svg)](https://github.com/DeibyGS/applyr/actions)
[![tests](https://img.shields.io/badge/tests-576%20passed-brightgreen)](https://github.com/DeibyGS/applyr)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-purple)](CONTRIBUTING.md)

[Features](#features) •
[Quick Start](#quick-start) •
[Commands](#commands) •
[Scoring](#scoring) •
[Configuration](#configuration) •
[Contributing](CONTRIBUTING.md)

</div>

```bash
pip install applyr && applyr init && applyr setup-agent
```

> [!NOTE]
> **Requires Python 3.11+** and an AI coding agent ([Claude Code](https://claude.ai/claude-code), [Cursor](https://cursor.sh), [OpenCode](https://opencode.ai), or any agent that reads instruction files).

---

## How it works

```
You: paste a job offer into your AI agent

         |
         v

Agent: reads cv-master.md + evaluates 6 topics
       runs  applyr add '<json>'

         |
         v

applyr:  82% compatibility (>= 80% threshold_apply)
         >> RECOMMENDATION: APPLY
         Skill gaps: English, Experience

         |  (you confirm)
         v

Agent: generates tailored CV from cv-master.md
       runs applyr cv ats-check (ATS compatibility score: 87/100)
       runs applyr cv bullet-optimize (quality: A)
       runs applyr cv cover-letter (tailored letter)
       delivers PDF ready to send
```

applyr is the **storage layer**. Your AI agent is the **brain**.

---

## Features

- **Three-state recommendation** — APPLY (>=80%), MAYBE (60-79%), LOW MATCH (<60%) with configurable thresholds
- **Skill-level breakdown** — Strong/Partial/Missing per topic with icons (✓/△/✕)
- **"Why you match"** — Executive summary of strengths and weaknesses
- **Weighted scoring** — 6 configurable topics (tech stack 30%, projects 20%, experience 15%, education 15%, english 10%, cultural fit 10%)
- **Score breakdown** — Weighted contribution per topic so you understand why 78%
- **CV tailoring hints** — What to emphasize, what to de-emphasize in your CV
- **Duplicate detection** — same company+title? applyr catches it before you waste time
- **ATS-safe CVs** — locked single-column CSS, standard fonts, no images. Your agent fills content, never touches structure
- **ATS compatibility check** — validates CV against ATS rules (headers, formatting, keywords)
- **Keyword extraction** — pulls keywords from job offers and matches against your CV
- **Bullet point optimization** — analyzes weak verbs, suggests strong alternatives, detects missing metrics
- **Cover letter generation** — tailored letters from your profile + offer data
- **CV comparison** — compare two CV versions (ATS compatibility score delta, keyword coverage)
- **Recruiter review** — built-in prompt scores your CV 0-100 with specific improvements
- **Response rate tracking** — measure application performance with monthly trends
- **Score calibration** — `applyr stats` reports real response/interview rates per score band, so you can see whether a higher compatibility score actually predicts a better outcome
- **27 commands** — pipeline, stats, gaps, trends, salary insights, follow-ups, compare, export, and more
- **Local and private** — SQLite on your machine. No API keys, no subscriptions, nothing leaves your system
- **Agent-native** — ships with `AGENT_INSTRUCTIONS.md` that tells Claude/Cursor/OpenCode exactly what to do

---

## Quick start

### 1. Install and initialize

```bash
pip install applyr
applyr init
```

This creates `~/.applyr/` with config, database, CV template, and agent instructions.

### 2. Fill your profile

Edit `~/.applyr/cv-master.md` with your complete professional profile. This is the only source of truth — the agent reads it to score offers and write CVs.

### 3. Connect your agent

```bash
applyr setup-agent                       # Auto-detects Claude/Cursor/OpenCode
applyr setup-agent --agent claude        # Or specify: claude | cursor | opencode | generic
```

**Done.** Paste a job offer into your agent and say "analyze this".

---

## What your agent sees

```
You:   "Analyze this AI Engineer posting at Acme Corp"

Agent: Checks duplicates → none found
       Scores: tech_stack 85%, experience 40%, projects 90%...
       applyr add '<json>'
       → "82% match. APPLY recommended. Generate CV?"

You:   "Yes"

Agent: applyr cv generate 1 → fills from cv-master.md
       applyr cv review → ATS compatibility score: 87/100, READY TO SEND
       applyr cv pdf → delivers PDF

You:   "Analyze this Data Analyst role at SmallCo"

Agent: applyr add '<json>'
       → "42% match. SKIP recommended. Gaps: no R/Tableau, 0 data roles."

You:   "What should I learn?"

Agent: applyr gaps → "Experience: seen in 15 offers, avg gap 20%"
```

---

## Commands

### Tracking

```bash
applyr add '<json>'                # Register offer (agent builds the JSON)
applyr list [--status S]           # All offers or filtered
applyr show <id>                   # Full detail + topic scores
applyr pipeline                    # Grouped by status
applyr update <id> <status>        # Change status, add notes
applyr delete <id>                 # Remove an offer
applyr search <keyword>            # Search by company/title/tech
applyr search --company <name>     # Exact company match (same definition add uses for duplicates)
```

### Analytics

```bash
applyr stats                       # Conversion funnel + metrics
applyr gaps                        # Skills to improve (by frequency)
applyr trends                      # Applications per week
applyr summary --json              # Weekly summary for LLM
applyr compare 1 3 4               # Side-by-side offers
applyr plan                        # Learning priorities
applyr salary [--seniority mid]    # Salary insights
applyr followups                   # Overdue + upcoming
```

### CV pipeline

```bash
applyr cv generate <id>            # Markdown CV with YAML frontmatter
applyr cv review <file.md>         # Recruiter review prompt (accepts .md or .html)
applyr cv review-blind <id>        # Independent CV evaluation (no score bias)
applyr cv pdf <file.md>            # Markdown → ATS-HTML → PDF via Chrome
applyr cv ats-check <file.html>    # Check ATS compatibility (0-100 score)
applyr cv keywords <id>            # Extract & match keywords vs CV
applyr cv bullet-optimize <file>   # Analyze bullet points (weak verbs, metrics)
applyr cv cover-letter <id>        # Generate tailored cover letter
applyr cv compare <v1.html> <v2.html>  # Compare two CV versions
applyr cv stats                    # CV performance analytics
```

### Response tracking

```bash
applyr response-rate               # Application response rate + trends
```

### System

```bash
applyr doctor                      # Health check
applyr export --format json        # Export everything
applyr version                     # Show version
```

<details>
<summary><strong>Aliases and flags</strong></summary>

| Alias | Command | | Flag | Effect |
|-------|---------|-|------|--------|
| `ls` | `list` | | `--json` | Structured JSON output |
| `st` | `stats` | | `--no-color` | Disable colors (also respects `NO_COLOR`) |
| `fu` | `followups` | | | |
| `cmp` | `compare` | | | |
| `sal` | `salary` | | | |

</details>

---

## Scoring

Each topic is scored 0-100 by the AI agent, then weighted:

| Topic | Weight | What it measures |
|-------|:------:|-----------------|
| `tech_stack` | 30% | Required technologies vs. your skills |
| `projects` | 20% | Portfolio relevance to the role |
| `experience` | 15% | Years, seniority, industry match |
| `education` | 15% | Degree level and field |
| `english` | 10% | Language level vs. requirement |
| `cultural_fit` | 10% | Work mode, location, values |

**Formula:** `sum(score * weight) / sum(weights)` — configurable in `~/.applyr/applyr.toml`.

**Thresholds:** score >= 80% → APPLY, 60-79% → MAYBE, below 60% → LOW MATCH. Configurable via `threshold_apply`/`threshold_maybe` in `applyr.toml`.

---

## Status flow

```
pending ──> applied ──> waiting ──> in_process ──> offer
               |            |           |
               v            v           v
           discarded    rejected    rejected
```

---

## Configuration

```toml
# ~/.applyr/applyr.toml

[general]
threshold_apply = 80    # Score >= this → APPLY
threshold_maybe = 60    # Score >= this → MAYBE (below → LOW MATCH)
followup_days = 10      # Days before follow-up reminder

[weights]               # Auto-normalized, no need to sum to 1.0
tech_stack = 30
education = 15
experience = 15
projects = 20
english = 10
cultural_fit = 10
```

---

<details>
<summary><strong>Offer fields reference</strong></summary>

| Field | Type | Valid values | Required |
|-------|------|-------------|:--------:|
| `title` | string | Any | Yes |
| `company` | string | Any | No |
| `summary` | string | Any | No |
| `date_received` | string | `YYYY-MM-DD` | No |
| `date_applied` | string | `YYYY-MM-DD` | No |
| `status` | string | `pending` `applied` `waiting` `in_process` `rejected` `discarded` `offer` | No |
| `canal` | string | `linkedin_easy` `linkedin_direct` `email` `portal` `referral` `other` | No |
| `work_mode` | string | `remote` `hybrid` `onsite` | No |
| `location` | string | Any | No |
| `salary_min` / `salary_max` | integer | Amount | No |
| `salary_period` | string | `annual` `monthly` `hourly` | No |
| `seniority_level` | string | `trainee` `entry_level` `junior` `mid` `senior` `lead` `director` | No |
| `role_category` | string | `backend` `frontend` `fullstack` `ai` `devops` `data` `mobile` `qa` `other` | No |
| `language` | string | `en` `es` — the language the CV is written in. Defaults to `[cv] language` in applyr.toml | No |
| `tech_stack` | string | Comma-separated | No |
| `job_url` | string | URL | No |
| `contact_name` / `contact_role` | string | Any | No |
| `cover_letter` | integer | `0` or `1` | No |
| `notes` | string | Any | No |
| `topics` | object | See Scoring section | No |

</details>

---

## Project structure

```
applyr/
  cli.py                 # Entry point
  config.py              # TOML config
  db.py                  # SQLite schema (offers: 32 columns, 6 tables)
  scoring.py             # Weighted scoring engine
  cv.py                  # Markdown CV + Chrome PDF + recruiter review
  ats.py                 # ATS compatibility checking + keyword matching
  analytics.py           # CV comparison + response rate tracking
  md_render.py           # Narrow markdown → ATS-HTML converter
  commands/
    core.py              # add, list, show, update, delete, search, init, setup-agent
    analytics.py         # stats, gaps, trends, pipeline, compare, plan, salary
    workflow.py          # export, doctor
  templates/
    AGENT_INSTRUCTIONS.md
    ats_rules.json       # ATS validation rules
    bullet_patterns.json # Bullet optimization patterns
    cover_letter.md      # Cover letter template
tests/
  test_cli_routing.py    # CLI router coverage
  test_cv.py             # CV pipeline tests
  test_ats.py            # ATS compatibility tests
  test_analytics.py      # Analytics tests
  test_cv_bullets.py     # Bullet optimization tests
  test_cover_letter.py   # Cover letter tests
  test_md_render.py      # Markdown renderer tests
  test_db.py             # Schema + migration tests
  test_scoring.py        # Scoring engine tests
  test_config.py         # Config loading tests
  test_validators.py     # Input validation tests
  ...
```

## Development

```bash
git clone https://github.com/DeibyGS/applyr.git
cd applyr
pip install -e ".[dev]"
pytest                             # 576 tests, ~4s
```

---

## Built with AI

applyr was designed to work **for** AI agents — it made sense to build it *with* one, as a pair programming partner.

| Human-owned | AI-assisted (human-reviewed) |
|-------------|------------------------------|
| Domain model & 32-column schema | Python implementation |
| Scoring engine & threshold logic | CLI scaffolding |
| ATS CV template & locked CSS | Test suite (576 tests) |
| Architecture & code review | Module split & CI |

**Process:** `Spec (SDD) → AI implementation → Human review → Test → Merge`

<details>
<summary><strong>Principles & metrics</strong></summary>

**Principles:**
1. AI never made product decisions — domain model and UX flow are human-designed.
2. Every feature started from a written spec (SDD) before any code.
3. `AGENT_INSTRUCTIONS.md` is a contract, not a suggestion.
4. PRs follow a 400-line budget with work-unit commits.

**Metrics:**

| | |
|---|---|
| PRs | 42 (all human-reviewed) |
| Tests | 576 (cli, cv, ats, analytics, bullets, cover_letter, md_render, db, scoring, config, validators) |
| Commands | 27 + 5 aliases |
| Schema | 32 columns, 6 tables, migration system |
| Models | Claude Opus 4.6, DeepSeek V4 Flash |

_Measured with [ClaudeStat](https://github.com/DeibyGS/claudestat)._

</details>

---

## License

[MIT](LICENSE) — use it, fork it, improve it.
