# applyr

[![PyPI version](https://img.shields.io/pypi/v/applyr)](https://pypi.org/project/applyr/)
[![PyPI downloads](https://img.shields.io/pypi/dm/applyr)](https://pypi.org/project/applyr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/DeibyGS/applyr/actions/workflows/python-package.yml/badge.svg)](https://github.com/DeibyGS/applyr/actions)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/DeibyGS/applyr/pulls)
[![GitHub Issues](https://img.shields.io/github/issues/DeibyGS/applyr)](https://github.com/DeibyGS/applyr/issues)

**CLI job application tracker designed for AI coding agents.**

Track applications, measure your conversion funnel, spot skill gaps, and generate ATS-optimized CVs — all from your terminal. Built to work with [Claude Code](https://claude.ai/claude-code), [Cursor](https://cursor.sh), [OpenCode](https://opencode.ai), or any AI coding agent.

### Requirements

- **Python 3.12+**
- **An AI coding agent** — [Claude Code](https://claude.ai/claude-code), [Cursor](https://cursor.sh), [OpenCode](https://opencode.ai), or any agent that reads instruction files. applyr provides the storage and structure; the agent does the analysis.

### Quick start

```bash
pip install applyr                        # Install
applyr init                               # Set up config, database, templates
# Edit ~/.applyr/cv-master.md             # Fill in your professional profile
applyr setup-agent --agent claude         # Connect your AI agent
```

Then paste a job offer into your AI agent — it handles the rest.

## Why applyr?

I built this while applying to **200+ jobs**. Most job trackers are web apps that don't talk to your AI tools. applyr is different:

- **CLI-first** — runs in your terminal, pipes into anything
- **AI-agent native** — your coding agent analyzes offers, scores compatibility, and generates CVs
- **ATS-safe CVs** — locked CSS template that passes Applicant Tracking Systems. Your agent fills content, never touches the structure
- **Duplicate detection** — prevents re-applying to the same company+role
- **Threshold-based recommendations** — automatic APPLY/SKIP based on your configured minimum score
- **Zero dependencies** — Python 3.12+ stdlib + colorama. No frameworks, no API keys, no subscriptions
- **Local and private** — your data stays in a SQLite file on your machine

## How it works

```
1. You paste a job offer into your AI agent
2. The agent checks for duplicates — if you already applied, it tells you
3. The agent reads your cv-master.md and evaluates compatibility per topic
4. The agent runs `applyr add` — applyr prints APPLY or SKIP based on your threshold
5. If score >= threshold and you confirm, the agent generates a tailored ATS-safe CV
6. The agent runs a recruiter review, iterates if needed, and delivers the final CV
7. You track everything: pipeline, stats, follow-ups, skill gaps, trends
```

applyr is the **storage and structure layer**. Your AI agent is the **brain** that analyzes and decides.

---

## AI Development Benchmark

applyr was designed to work **for** AI coding agents — it made sense to build it *with* them, as a **pair programming partner**. A human engineer defined the domain model and architecture; AI accelerated implementation, always behind human review.

### How we worked together

| Human-owned | AI-assisted (human-reviewed) |
|-------------|------------------------------|
| Product design & domain model (28-column schema) | Python implementation & refactoring |
| Scoring engine design (weighted topics) | CLI command scaffolding |
| ATS CV template & locked CSS | Test suite (54 pytest tests) |
| Config system (TOML) & threshold logic | Module split (commands/ package) |
| Architecture decisions & code review | Documentation & CI workflows |

**Workflow:** `Idea → Spec (SDD) → AI implementation → Human review → Test → Merge`

The 200+ jobs this tool manages were tracked *by* an AI agent; the code beneath them was built with the same human-in-the-loop discipline.

### AI Development Principles

1. **AI never made product decisions** — domain model, scoring weights, and UX flow are human-designed.
2. **Every feature started from a written spec** — using Spec-Driven Development (SDD) before any code.
3. **Documentation is executable context** — `AGENT_INSTRUCTIONS.md` is a step-by-step contract, not a suggestion.
4. **All generated code required human review** — PRs follow a 400-line budget with work-unit commits.
5. **Architecture over speed** — commands/ split, scoring engine, and config system were designed for maintainability.

<details>
<summary><strong>Supporting metrics</strong></summary>
<br>

| Metric | Value |
|--------|-------|
| Total PRs | 16 (all human-reviewed) |
| Test coverage | 54 unit tests (scoring, config, db, validators) |
| Commands | 21 CLI commands + 5 aliases |
| Schema | 28 columns, 3 tables, migration system |
| Primary model | Claude Opus 4.6 |
| Secondary | DeepSeek V4 Flash (OpenCode) |

_Measured with [ClaudeStat](https://github.com/DeibyGS/claudestat)._

</details>

---

## Install

```bash
pip install applyr
```

Or clone and install locally:

```bash
git clone https://github.com/DeibyGS/applyr.git
cd applyr
pip install .
```

---

## Setup (3 steps)

### Step 1 — Initialize

```bash
applyr init
```

This creates `~/.applyr/` with:
- `applyr.toml` — configuration (scoring weights, thresholds, paths)
- `jobs.db` — SQLite database (empty, ready to use)
- `cv-master.md` — template for your professional profile
- `AGENT_INSTRUCTIONS.md` — step-by-step guide for your AI agent
- `cv/` — directory for generated CVs

### Step 2 — Fill your CV master

Open `~/.applyr/cv-master.md` and fill it with your **complete** professional profile: contact info, experience, projects, skills, education, certifications, languages. This is the source of truth — the AI agent reads this file to evaluate offers and generate CVs. **Never leave it empty.**

### Step 3 — Connect your AI agent

Run `setup-agent` in your project directory:

```bash
applyr setup-agent --agent claude     # Claude Code → CLAUDE.md
applyr setup-agent --agent cursor     # Cursor → .cursorrules
applyr setup-agent --agent opencode   # OpenCode → .opencode/instructions.md
applyr setup-agent --agent generic    # Any agent → AGENTS.md
```

If your project already has an agent config file, `setup-agent` auto-detects it:

```bash
applyr setup-agent                    # Auto-detects and appends instructions
```

This tells your AI agent:
- How to read your cv-master.md and evaluate offers
- How to build the JSON for `applyr add` with all valid field values
- Which command to run for each user question
- Rules: never invent content, be honest with scores, leave unknown fields empty
- ATS rules for CV generation (single column, standard fonts, visible URLs, etc.)

**That's it. You're ready.**

---

## Usage

### Register an offer

Paste a job posting into your AI agent and say "analyze this offer". The agent will:

1. Read your cv-master.md
2. Score each topic (tech stack, experience, education, etc.)
3. Run `applyr add` with all the data:

```bash
applyr add '{"title": "AI Engineer", "company": "Acme Corp", "work_mode": "remote", "location": "Madrid", "salary_min": 30000, "salary_max": 40000, "seniority_level": "junior", "role_category": "ai", "tech_stack": "Python, LangChain, AWS", "canal": "linkedin_easy", "status": "applied", "topics": {"tech_stack": {"score": 85, "detail": "Python strong"}, "education": {"score": 70, "detail": "DAM completed"}, "english": {"score": 60, "detail": "B1"}, "experience": {"score": 40, "detail": "6mo internship"}, "projects": {"score": 90, "detail": "3 production projects"}, "cultural_fit": {"score": 80, "detail": "Good fit"}}}'
```

Output:
```
Offer added successfully.
  ID          : 1
  Title       : AI Engineer
  Company     : Acme Corp
  Compat.     : 74%
  Status      : Applied
  Follow-up   : 2026-08-16
  Skill gaps  : English, Experience

  >> RECOMMENDATION: APPLY (score 74% >= 65% threshold)
     Next: 'applyr cv generate 1' to create a tailored CV
```

If you try to add the same offer again:
```
Duplicate detected — this offer already exists in your database.
  ID          : 1
  Status      : Applied
  Received    : 2026-08-07
  Compat.     : 74%

Use 'applyr show 1' to review or 'applyr update 1 <status>' to change it.
```

All fields are optional except `title`. The agent fills what it can from the posting.

### View your offers

```bash
applyr list                    # All offers (last 50)
applyr list --status applied   # Filter by status
applyr show 1                  # Full detail of offer #1
applyr pipeline                # Grouped by status
```

### Track your progress

```bash
applyr stats                   # Conversion funnel + metrics
applyr gaps                    # Skills you need to improve
applyr followups               # Overdue and upcoming follow-ups
applyr trends                  # Applications per week + growth rate
applyr summary --json          # Weekly summary as structured JSON
```

### Compare, plan, and analyze salaries

```bash
applyr compare 1 3 4           # Side-by-side comparison
applyr plan                    # Prioritized learning plan from skill gaps
applyr salary                  # Salary stats by seniority + category
applyr salary --seniority mid  # Filter by seniority level
```

Example output — `applyr compare`:

```
Field         #1                    #3                    #4
----------------------------------------------------------------------
Company       Acme Corp             DataCo                CloudNet
Title         AI Engineer           Junior Python Dev     Backend Engineer
Score         78%                   92%                   65%
Status        Applied               Applied               In Process
Seniority     mid                   junior                mid
Work Mode     remote                onsite                remote
Salary        35000-45000/ann       22000-28000/ann       38000-48000/ann
Tech Stack    Python, LangChain     Python, Django        Go, Kubernetes
```

Example output — `applyr salary`:

```
--- Salary Insights ---

  Seniority       Count       Min       Max       Avg    Median  Period
  ——————————————  —————  ————————  ————————  ————————  ————————  ——————
  junior              1    22,000    28,000    25,000    25,000  annual
  mid                 2    35,000    48,000    41,500    41,500  annual
  senior              1    40,000    55,000    47,500    47,500  annual
  trainee             1    18,000    22,000    20,000    20,000  annual
```

Example output — `applyr plan`:

```
--- Learning Plan ---

  #     Skill                   Seen  Avg Gap  Priority
  ————  ——————————————————————  ————  ———————  ————————
  1     Experience                 4x      25%  CRITICAL
  2     Tech Stack                 3x      17%  HIGH
  3     English                    4x      10%  MEDIUM

  Focus on CRITICAL and HIGH items first.
```

### Update and manage

```bash
applyr update 1 waiting --notes "Interview scheduled for Monday"
applyr update 1 rejected --notes "They needed 3+ years experience"
applyr search Python           # Search by company/title/tech/notes
applyr delete 5                # Remove an offer
applyr export --format json    # Export everything
```

### Generate ATS-safe CVs

```bash
applyr cv generate 1           # Creates HTML skeleton for offer #1
```

This generates an HTML file with:
- **Locked ATS-safe CSS** — single column, standard fonts, no flex/grid/tables
- **Offer context** — company, title, tech stack, scores embedded as comments
- **Placeholders** — for the AI agent to fill from your cv-master.md

The agent then fills the placeholders and you convert to PDF:

```bash
applyr cv pdf ~/.applyr/cv/cv-acme-ai-engineer.html
```

The PDF is generated with Chrome headless, no headers or footers.

---

## All commands

| Command | Description |
|---------|-------------|
| `applyr init` | Set up ~/.applyr/ (config, database, agent instructions) |
| `applyr setup-agent [--agent NAME]` | Configure AI agent (claude, cursor, opencode, generic) |
| `applyr add '<json>'` | Register a new job offer |
| `applyr list [--status S] [--sort F]` | List offers (default: last 50) |
| `applyr pipeline [--min-score N]` | View offers grouped by status |
| `applyr show <id>` | Show full offer details with topic scores |
| `applyr update <id> <status> [--notes ""]` | Update offer status |
| `applyr delete <id>` | Delete an offer |
| `applyr search <keyword> [--status S]` | Search by company/title/notes/tech |
| `applyr stats` | Conversion funnel, channels, salary, work mode |
| `applyr gaps [--limit N]` | Skill gap analysis by frequency |
| `applyr followups` | Pending/overdue follow-ups with contact info |
| `applyr trends [--period week\|month]` | Application trends over time |
| `applyr summary [--json]` | Weekly summary (JSON for LLM consumption) |
| `applyr compare <id1> <id2> [...]` | Compare offers side by side |
| `applyr plan [--limit N]` | Prioritized learning plan from skill gaps |
| `applyr salary [--seniority S] [--category C]` | Salary insights by seniority/category |
| `applyr export [--format csv\|json\|md]` | Export all data |
| `applyr cv generate <id>` | Generate ATS-safe HTML CV skeleton |
| `applyr cv review <file.html>` | Generate recruiter review prompt (ATS score + feedback) |
| `applyr cv pdf <file.html> [--output f.pdf]` | HTML to PDF via Chrome |
| `applyr doctor` | Check configuration and database health |
| `applyr version` | Show version |
| `applyr help` | Show help |

### Aliases

| Alias | Command |
|-------|---------|
| `ls` | `list` |
| `st` | `stats` |
| `fu` | `followups` |
| `cmp` | `compare` |
| `sal` | `salary` |

### Global flags

| Flag | Description |
|------|-------------|
| `--json` | Output structured JSON (available on all data commands) |
| `--no-color` | Disable colored output (also respects `NO_COLOR` env var) |

---

## Offer fields reference

| Field | Type | Valid values | Required |
|-------|------|-------------|:--------:|
| `title` | string | Any | Yes |
| `company` | string | Any | No |
| `summary` | string | Any | No |
| `date_received` | string | `YYYY-MM-DD` | No |
| `date_applied` | string | `YYYY-MM-DD` | No |
| `status` | string | `pending`, `applied`, `waiting`, `in_process`, `rejected`, `discarded`, `offer` | No |
| `canal` | string | `linkedin_easy`, `linkedin_direct`, `email`, `portal`, `referral`, `other` | No |
| `work_mode` | string | `remote`, `hybrid`, `onsite` | No |
| `location` | string | Any | No |
| `salary_min` | integer | Annual EUR | No |
| `salary_max` | integer | Annual EUR | No |
| `salary_period` | string | `annual`, `monthly`, `hourly` | No |
| `seniority_level` | string | `trainee`, `entry_level`, `junior`, `mid`, `senior`, `lead`, `director` | No |
| `role_category` | string | `backend`, `frontend`, `fullstack`, `ai`, `devops`, `data`, `mobile`, `qa`, `other` | No |
| `tech_stack` | string | Comma-separated | No |
| `cover_letter` | integer | `0` or `1` | No |
| `cover_letter_file` | string | File path | No |
| `contact_name` | string | Any | No |
| `contact_role` | string | Any | No |
| `job_url` | string | URL | No |
| `rejection_reason` | string | Any | No |
| `notes` | string | Any | No |
| `topics` | object | See Scoring section | No |

---

## Scoring

When you provide `topics` in `applyr add`, the compatibility score is auto-calculated using weighted averages:

| Topic | Default Weight | What to evaluate |
|-------|:--------------:|-----------------|
| `tech_stack` | 30% | How much of the required tech does the user know? |
| `education` | 15% | Does the education match what they ask? |
| `english` | 10% | Does the language level meet the requirement? |
| `experience` | 15% | Years, seniority, and industry match? |
| `projects` | 20% | Are the user's projects relevant to this role? |
| `cultural_fit` | 10% | Work mode, company culture, location match? |

Each topic score goes from 0 to 100. The weighted average becomes the compatibility percentage.

Default threshold to recommend applying: **65%** (configurable).

Customize weights, topic names, and threshold in `~/.applyr/applyr.toml`.

---

## Status flow

```
pending ──> applied ──> waiting ──> in_process ──> offer
               |            |           |
               v            v           v
           discarded    rejected    rejected
```

- **pending** — offer registered, not yet applied
- **applied** — application sent (auto-schedules follow-up)
- **waiting** — waiting for company response
- **in_process** — interview stage
- **offer** — offer received
- **discarded** — decided not to apply
- **rejected** — company rejected your application

---

## Configuration

Edit `~/.applyr/applyr.toml`:

```toml
[general]
threshold = 65          # Min compatibility % to recommend applying
followup_days = 10      # Days before follow-up reminder

[weights]
# Relative importance of each topic (auto-normalized, no need to sum to 1.0)
tech_stack = 30
education = 15
experience = 15
projects = 20
english = 10
cultural_fit = 10

[cv]
# cv_master = "~/.applyr/cv-master.md"
# output_dir = "~/.applyr/cv"
```

---

## Project structure

```
applyr/
  __init__.py           # Version
  cli.py                # Entry point, argparse routing
  config.py             # applyr.toml management
  constants.py          # Thresholds, widths, defaults
  colors.py             # Colorama wrapper (NO_COLOR support)
  db.py                 # SQLite schema (28 columns), migrations
  scoring.py            # Weighted compatibility scoring
  cv.py                 # ATS CV generation + Chrome PDF + recruiter review
  commands/
    __init__.py          # Re-exports all cmd_* functions
    _helpers.py          # Shared utilities (_today, _bar, _truncate)
    core.py              # init, add, list, show, update, delete, search, setup-agent
    analytics.py         # pipeline, stats, gaps, followups, trends, summary, compare, plan, salary
    workflow.py          # export, doctor
  templates/
    AGENT_INSTRUCTIONS.md  # Step-by-step guide for AI agents
    cv-ats.html            # ATS-safe HTML template
    cv-master-template.md  # Empty CV master template
tests/
  conftest.py            # Shared fixtures (tmp db, tmp config)
  test_scoring.py        # Scoring engine tests
  test_config.py         # Config loading tests
  test_db.py             # Database schema tests
  test_validators.py     # Input validation tests
```

---

## Testing

```bash
pip install applyr[dev]   # Install with pytest
pytest                    # Run all 54 tests
pytest -v                 # Verbose output
pytest -m unit            # Only unit tests
```

Tests use isolated temporary directories — they never touch `~/.applyr/`.

---

## Data storage

All data is stored locally in `~/.applyr/jobs.db` (SQLite). Nothing leaves your machine.

Export anytime:

```bash
applyr export --format json --file my-applications.json
applyr export --format csv --file my-applications.csv
```

---

## Example conversation with your AI agent

```
You:   "Analyze this job posting for AI Engineer at Acme"
Agent: Checks for duplicates → none found
       Reads cv-master.md + evaluates compatibility
       Runs: applyr add '<json>'
       → "Registered as #42 — 78% match (above 65% threshold). APPLY recommended."
       → "Gaps: English, Experience. Want me to generate a tailored CV?"

You:   "Yes, apply"
Agent: Runs: applyr update 42 applied --canal linkedin_easy
       Runs: applyr cv generate 42
       Fills placeholders from cv-master.md
       Runs: applyr cv review → evaluates as recruiter → ATS score: 82/100
       Applies suggested improvements → re-reviews → READY TO SEND
       Runs: applyr cv pdf ~/.applyr/cv/cv-acme-ai-engineer.html
       → "CV ready. ATS score: 87/100. PDF at ~/.applyr/cv/cv-acme-ai-engineer.pdf"

You:   "Analyze this other posting for Data Analyst at SmallCo"
Agent: Runs: applyr add '<json>'
       → "Registered as #43 — 42% match (below 65% threshold). SKIP recommended."
       → "Main gaps: Tech Stack (no R/Tableau), Experience (0 data roles)."

You:   "What skills should I focus on?"
Agent: Runs: applyr gaps
       → "Experience: 15 offers, avg gap 20%. English: 12 offers, avg gap 15%."
```

---

## License

MIT
