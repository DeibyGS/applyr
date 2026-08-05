# applyr — Agent Instructions

> Copy this file into your AI agent's context (CLAUDE.md, .cursorrules, AGENTS.md, etc.)
> so it knows how to use applyr automatically.

## What is applyr?

A CLI job application tracker installed via `pip install applyr`. It stores offers in a local SQLite database at `~/.applyr/jobs.db`. You (the AI agent) register, query, and manage job applications through shell commands.

## Setup

If the user hasn't initialized applyr yet, run:

```bash
applyr init
```

This creates `~/.applyr/` with the database, config, and a cv-master template.

## Your source of truth

**`~/.applyr/cv-master.md`** contains the user's complete professional profile: experience, projects, skills, education, certifications, and languages. ALWAYS read this file before evaluating any job offer. NEVER invent skills, projects, or experience that are not in this file.

## Core workflow

When the user shares a job offer (text, URL, screenshot):

### Step 1 — Read cv-master.md

```bash
cat ~/.applyr/cv-master.md
```

### Step 2 — Evaluate compatibility

Score each topic from 0 to 100 by comparing the offer requirements against cv-master.md:

| Topic key | What to evaluate |
|-----------|-----------------|
| `tech_stack` | How much of the required tech stack does the user know? |
| `education` | Does the user's education match what they ask for? |
| `english` | Does the user's language level meet the requirement? |
| `experience` | Does the user's experience (years, seniority, industry) match? |
| `projects` | Are the user's projects relevant to this role? |
| `cultural_fit` | Does the work mode, company culture, and location match the user's preferences? |

These are the default topics. The user may have customized them in `~/.applyr/applyr.toml` under `[topics]`.

### Step 3 — Register the offer

Build a JSON object and run:

```bash
applyr add '<json>'
```

**Required field:** `title`
**All other fields are optional** — fill in everything you can extract from the offer:

```json
{
  "title": "Job title as posted",
  "company": "Company name",
  "summary": "1-2 sentence summary of the role",
  "date_received": "YYYY-MM-DD",
  "date_applied": "YYYY-MM-DD",
  "status": "pending",
  "canal": "linkedin_easy",
  "work_mode": "remote",
  "location": "City or region",
  "salary_min": 30000,
  "salary_max": 40000,
  "salary_period": "annual",
  "seniority_level": "junior",
  "role_category": "backend",
  "tech_stack": "Python, FastAPI, AWS",
  "cover_letter": 0,
  "cover_letter_file": "path/to/file.pdf",
  "contact_name": "Recruiter name",
  "contact_role": "HR Manager",
  "job_url": "https://...",
  "rejection_reason": "Reason if discarded",
  "notes": "Any additional context",
  "topics": {
    "tech_stack": {"score": 80, "detail": "Why this score"},
    "education": {"score": 70, "detail": "Why this score"},
    "english": {"score": 60, "detail": "Why this score"},
    "experience": {"score": 40, "detail": "Why this score"},
    "projects": {"score": 85, "detail": "Why this score"},
    "cultural_fit": {"score": 75, "detail": "Why this score"}
  }
}
```

### Valid values

| Field | Valid values |
|-------|-------------|
| `status` | `pending`, `applied`, `waiting`, `in_process`, `rejected`, `discarded`, `offer` |
| `canal` | `linkedin_easy`, `linkedin_direct`, `email`, `portal`, `referral`, `other` |
| `work_mode` | `remote`, `hybrid`, `onsite` |
| `seniority_level` | `junior`, `mid`, `senior`, `lead`, `director` |
| `role_category` | `backend`, `frontend`, `fullstack`, `ai`, `devops`, `data`, `mobile`, `qa`, `other` |
| `salary_period` | `annual`, `monthly` |

### Step 4 — Decide

The default threshold is 65% (configurable in `~/.applyr/applyr.toml`).

- Score **>= threshold** → recommend applying. Ask the user to confirm.
- Score **< threshold** → recommend discarding. Explain the main gaps. Let the user decide.

### Step 5 — If applying

1. Update the offer status:
   ```bash
   applyr update <id> applied --canal linkedin_easy
   ```

2. If the user wants a CV, generate one:
   ```bash
   applyr cv generate <id>
   ```
   Then read cv-master.md, create an HTML CV tailored to the offer, and convert to PDF:
   ```bash
   applyr cv pdf <path-to-html> --output <path-to-pdf>
   ```

3. If the user wants a cover letter, create it and note it:
   ```bash
   applyr update <id> applied --notes "Cover letter sent"
   ```

## Querying data

When the user asks about their job search, use these commands:

| User asks | Command to run |
|-----------|---------------|
| "Show me my applications" | `applyr list` |
| "What's my pipeline?" | `applyr pipeline` |
| "Show offer #5" | `applyr show 5` |
| "What are my stats?" | `applyr stats` |
| "What skills should I improve?" | `applyr gaps` |
| "Any follow-ups due?" | `applyr followups` |
| "How am I trending?" | `applyr trends` |
| "Give me a weekly summary" | `applyr summary --json` |
| "Search for Python offers" | `applyr search Python` |
| "Export my data" | `applyr export --format json` |
| "Show only rejected" | `applyr list --status rejected` |

## Rules

1. **NEVER invent content** — only use what is in cv-master.md
2. **NEVER guess scores** — evaluate honestly against the offer requirements
3. **Be specific in topic details** — explain WHY you gave that score, not just a number
4. **If information is missing from the offer** (salary, work mode, etc.), leave the field out rather than guessing
5. **If the user's cv-master.md is empty**, tell them to fill it in before analyzing offers
6. **Salary**: if the offer says "competitive" or doesn't specify, omit salary fields
7. **Follow-ups**: applyr auto-schedules follow-ups when status is set to `applied` or `waiting`
8. **Config**: scoring weights and topic names can be customized in `~/.applyr/applyr.toml`
