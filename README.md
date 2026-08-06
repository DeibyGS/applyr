# applyr

CLI job application tracker designed for AI coding agents.

Track applications, measure your conversion funnel, spot skill gaps, and generate ATS-optimized CVs — all from your terminal. Built to work with [Claude Code](https://claude.ai/claude-code), [Cursor](https://cursor.sh), [Aider](https://aider.chat), or any AI coding agent.

## Why applyr?

I built this while applying to **200+ jobs**. Most job trackers are web apps that don't talk to your AI tools. applyr is different:

- **CLI-first** — runs in your terminal, pipes into anything
- **AI-agent native** — your coding agent analyzes offers, scores compatibility, and generates CVs
- **ATS-safe CVs** — locked CSS template that passes Applicant Tracking Systems. Your agent fills content, never touches the structure
- **Zero dependencies** — Python 3.12+ stdlib only. No frameworks, no API keys, no subscriptions
- **Local and private** — your data stays in a SQLite file on your machine

## How it works

```
1. You paste a job offer into your AI agent
2. The agent reads your cv-master.md (your complete professional profile)
3. The agent evaluates your compatibility per topic (tech stack, experience, etc.)
4. The agent runs `applyr add` to register the offer with all data
5. If you want to apply, the agent generates an ATS-safe CV tailored to the offer
6. You track everything: pipeline, stats, follow-ups, skill gaps, trends
```

applyr is the **storage and structure layer**. Your AI agent is the **brain** that analyzes and decides.

---

## AI Development Benchmark

applyr was designed to work **for** AI coding agents — it made sense to build it *with* them, as a **pair programming partner**. A human engineer defined the domain model and architecture; AI accelerated implementation, always behind human review.

### How we worked together

| Human-owned | AI implemented, always human-reviewed |
|-------------|-------------------------------------|
| Product design & data model (28-column schema) | Python logic generation |
| Atomic QoL commands design | CLI command scaffolding |
| ATS CV template structure | Refactoring, test scaffolding |
| Config (TOML) design | Auxiliary docs, type checking |
| Code review & final acceptance | Documentation, auxiliary scripts |

**Workflow:** `Idea → Spec → AI implementation → Human review → Test → Refine → Merge`

The 200+ jobs this tool manages were tracked *by* an AI agent; the code beneath them was built with the same human-in-the-loop discipline.

### AI Development Principles

- AI never made product decisions.
- Every implementation started from a written specification.
- Documentation was treated as executable context for AI.
- All generated code required human review.
- Architecture was preserved over implementation speed.

<details>
<summary><strong>Supporting metrics</strong></summary>
<br>

| Metric | Value |
|--------|-------|
| AI sessions | 12 logged (11 on predecessor + applyr) |
| Measured development time | ~2 h tracked; earlier work pre-dates session logs |
| Primary model | Claude Opus 4.6 |
| Secondary | DeepSeek V4 Flash (OpenCode) |

_Measured with [ClaudeStat](https://github.com/DeibyGS/claudestat). Approximate values; early work was built before exhaustive session logging._

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

Copy the agent instructions into your AI tool's config:

```bash
# Claude Code
cat ~/.applyr/AGENT_INSTRUCTIONS.md >> ~/.claude/CLAUDE.md

# Cursor
cat ~/.applyr/AGENT_INSTRUCTIONS.md >> .cursorrules

# Aider / OpenCode / others
# Add the content to whatever file your agent reads for instructions
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
| `applyr export [--format csv\|json]` | Export all data |
| `applyr cv generate <id>` | Generate ATS-safe HTML CV skeleton |
| `applyr cv pdf <file.html> [--output f.pdf]` | HTML to PDF via Chrome |
| `applyr version` | Show version |
| `applyr help` | Show help |

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
| `salary_period` | string | `annual`, `monthly` | No |
| `seniority_level` | string | `junior`, `mid`, `senior`, `lead`, `director` | No |
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
Agent: Reads the posting + your cv-master.md
       Evaluates compatibility per topic
       Runs: applyr add '<json with all fields>'
       → "Registered as #42 — 78% match. Gaps: English, Experience"

You:   "Apply to it"
Agent: Runs: applyr update 42 applied --canal linkedin_easy
       Runs: applyr cv generate 42
       Fills placeholders from cv-master.md
       Runs: applyr cv pdf ~/.applyr/cv/cv-acme-ai-engineer.html
       → "CV generated. PDF ready at ~/.applyr/cv/cv-acme-ai-engineer.pdf"

You:   "What skills should I focus on improving?"
Agent: Runs: applyr gaps
       → "Experience appears in 15 offers (avg gap 20%). English in 12 offers."

You:   "How am I doing this month?"
Agent: Runs: applyr summary --json
       → Structured JSON with applications sent, response rate, trends

You:   "Any follow-ups due?"
Agent: Runs: applyr followups
       → "3 overdue: Acme (#42, 5 days ago), Beta (#38, 3 days ago)..."
```

---

## License

MIT
