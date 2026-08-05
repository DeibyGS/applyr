# applyr

CLI job application tracker designed for AI coding agents.

Track applications, measure your funnel, spot skill gaps, and generate tailored CVs — all from your terminal. Built to work with [Claude Code](https://claude.ai/claude-code), [Cursor](https://cursor.sh), [Aider](https://aider.chat), or any AI coding agent.

## Why applyr?

I built this while applying to **200+ jobs**. Most job trackers are web apps that don't talk to your AI tools. applyr is different:

- **CLI-first** — runs in your terminal, pipes into anything
- **AI-agent native** — your coding agent reads/writes offers, generates CVs, and gives you insights
- **Zero dependencies** — Python 3.10+ stdlib only. No frameworks, no API keys
- **Local & private** — your data stays in a SQLite file on your machine

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

## Quick Start

```bash
# 1. Initialize (creates ~/.applyr/ with config, database, and agent instructions)
applyr init

# 2. Edit your CV master (source of truth for all CVs)
#    Open ~/.applyr/cv-master.md in your editor

# 3. Copy agent instructions into your AI tool's config
#    cp ~/.applyr/AGENT_INSTRUCTIONS.md into CLAUDE.md, .cursorrules, etc.

# 4. Add your first offer
applyr add '{"title": "Backend Developer", "company": "Acme", "work_mode": "remote", "salary_min": 35000, "salary_max": 45000, "seniority_level": "junior", "tech_stack": "Python, FastAPI, PostgreSQL"}'

# 4. Check your pipeline
applyr pipeline

# 5. See your stats
applyr stats
```

## Commands

| Command | Description |
|---------|-------------|
| `applyr init` | Set up ~/.applyr/ (config, database, templates) |
| `applyr add '<json>'` | Register a new job offer |
| `applyr list [--status S] [--sort F]` | List offers (default: last 50) |
| `applyr pipeline [--min-score N]` | View offers grouped by status |
| `applyr show <id>` | Show full offer details |
| `applyr update <id> <status>` | Update offer status |
| `applyr delete <id>` | Delete an offer |
| `applyr search <keyword>` | Search by company/title/notes/tech |
| `applyr stats` | Conversion funnel and metrics |
| `applyr gaps` | Skill gap analysis |
| `applyr followups` | Pending/overdue follow-ups |
| `applyr trends` | Application trends over time |
| `applyr summary [--json]` | Weekly summary (LLM-optimized) |
| `applyr export [--format csv\|json]` | Export all data |
| `applyr cv generate <id>` | Generate CV instructions for an offer |
| `applyr cv pdf <file.html>` | Convert HTML CV to PDF via Chrome |
| `applyr version` | Show version |

## Offer Statuses

`pending` > `applied` > `waiting` > `in_process` > `offer`

Side tracks: `discarded`, `rejected`

## Offer Fields

All fields are optional except `title`. Your AI agent fills in what it can from the job posting:

```json
{
  "title": "AI Engineer",
  "company": "Acme Corp",
  "summary": "Building LLM-powered features...",
  "date_received": "2026-08-06",
  "date_applied": "2026-08-06",
  "compatibility_pct": 78,
  "status": "applied",
  "canal": "linkedin_easy",
  "work_mode": "remote",
  "location": "Madrid",
  "salary_min": 30000,
  "salary_max": 40000,
  "seniority_level": "junior",
  "role_category": "ai",
  "tech_stack": "Python, LangChain, AWS",
  "cover_letter": 1,
  "contact_name": "Ana Garcia",
  "contact_role": "Recruiter",
  "job_url": "https://...",
  "notes": "Referred by John",
  "topics": {
    "tech_stack": {"score": 85, "detail": "Python strong, LangChain learning"},
    "education": {"score": 70, "detail": "DAM completed"},
    "english": {"score": 60, "detail": "B1 level"},
    "experience": {"score": 40, "detail": "6 months internship"},
    "projects": {"score": 90, "detail": "3 production projects"},
    "cultural_fit": {"score": 80, "detail": "Startup culture match"}
  }
}
```

## Scoring

Compatibility is auto-calculated from topic scores using configurable weights:

| Topic | Default Weight |
|-------|---------------|
| Tech Stack | 30% |
| Education | 15% |
| English | 10% |
| Experience | 15% |
| Own Projects | 20% |
| Cultural Fit | 10% |

Customize weights, topic names, and threshold in `~/.applyr/applyr.toml`.

## Using with AI Agents

applyr is designed to be used **through** your AI coding agent. Here's the workflow:

```
You:   "Analyze this job posting for AI Engineer at Acme"
Agent: Reads the posting + your cv-master.md
       Evaluates compatibility per topic
       Runs: applyr add '<json with all fields>'
       Output: "Registered as #42 — 78% match. Gaps: English, Experience"

You:   "What should I focus on improving?"
Agent: Runs: applyr gaps
       Output: "English appears in 15 offers. Consider getting B2 cert."

You:   "Generate a CV for offer #42"
Agent: Runs: applyr cv generate 42
       Reads cv-master.md + offer details
       Creates tailored HTML CV
       Runs: applyr cv pdf cv-acme.html

You:   "Weekly summary"
Agent: Runs: applyr summary --json
       Output: structured JSON with metrics, trends, and recommendations
```

### Agent Instructions

`applyr init` creates `~/.applyr/AGENT_INSTRUCTIONS.md` — a complete step-by-step guide for any AI agent (Claude Code, Cursor, Aider, OpenCode, etc.). It covers:

- How to read `cv-master.md` and evaluate offers
- How to build the JSON for `applyr add` with all valid values
- Rules: never invent content, be honest with scores, leave unknown fields empty
- Which command to run for each type of user question

**Setup:** Copy the instructions into your agent's config file:

```bash
# Claude Code
cat ~/.applyr/AGENT_INSTRUCTIONS.md >> ~/.claude/CLAUDE.md

# Cursor
cat ~/.applyr/AGENT_INSTRUCTIONS.md >> .cursorrules

# Or just include the path in your project's agent config
```

## Configuration

Edit `~/.applyr/applyr.toml`:

```toml
[general]
threshold = 65          # Min compatibility % to recommend applying
followup_days = 10      # Days before follow-up reminder

[weights]
tech_stack = 0.30
education = 0.15
english = 0.10
experience = 0.15
projects = 0.20
cultural_fit = 0.10

[topics]
tech_stack = "Tech Stack"
education = "Education"
english = "English"
experience = "Experience"
projects = "Own Projects"
cultural_fit = "Cultural Fit"

[cv]
# chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# cv_master = "~/.applyr/cv-master.md"
# output_dir = "~/.applyr/cv"
```

## Data Storage

All data is stored locally in `~/.applyr/jobs.db` (SQLite). Export anytime:

```bash
applyr export --format json --file my-applications.json
```

## License

MIT
