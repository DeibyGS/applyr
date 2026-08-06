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

Score each topic from 0 to 100 by comparing the offer requirements against cv-master.md.
Use the rubric below for consistent scoring across offers.

#### Scoring rubric

| Topic key | 0 (no match) | 50 (partial) | 100 (full match) |
|-----------|-------------|--------------|-------------------|
| `tech_stack` | Knows none of the required technologies | Knows ~50% of the stack; missing some key ones | Expert in all required technologies |
| `education` | No relevant education at all | Related field but different level/specialization | Exact degree and level requested |
| `english` | Cannot hold a conversation | B1/B2 — functional but not fluent | C1+ or native level |
| `experience` | Zero relevant experience | Some experience but wrong seniority or industry | Exact years, seniority, and industry match |
| `projects` | No relevant projects | Has projects in related area but not direct match | Portfolio directly demonstrates required skills |
| `cultural_fit` | Work mode, location, and culture are incompatible | Partial match (e.g., hybrid when remote preferred) | Perfect alignment on mode, location, and values |

These are the default topics. The user may have customized them in `~/.applyr/applyr.toml` under `[topics]`. If custom topics exist, use those keys instead.

**Rules for scoring:**
- Be honest — inflated scores lead to wasted applications
- Always explain WHY you gave that score in the `detail` field
- If the offer doesn't mention a requirement (e.g., no education requirement), score 100 for that topic
- Apply the same rubric consistently across all offers

### Step 3 — Register the offer

Build a JSON object and run:

```bash
applyr add '<json>'
```

You can also save to a file and run `applyr add offer.json` or pipe via `cat offer.json | applyr add -`.

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
    "tech_stack": {"score": 80, "detail": "Knows Python and FastAPI, missing AWS experience"},
    "education": {"score": 70, "detail": "CS degree, they prefer Master's"},
    "english": {"score": 90, "detail": "B2+, offer requires fluent English"},
    "experience": {"score": 40, "detail": "1 year exp, they ask for 3+"},
    "projects": {"score": 85, "detail": "3 relevant backend projects on GitHub"},
    "cultural_fit": {"score": 75, "detail": "Hybrid ok, user prefers remote"}
  }
}
```

### Valid values

| Field | Valid values |
|-------|-------------|
| `status` | `pending`, `applied`, `waiting`, `in_process`, `rejected`, `discarded`, `offer` |
| `canal` | `linkedin_easy`, `linkedin_direct`, `email`, `portal`, `referral`, `other` |
| `work_mode` | `remote`, `hybrid`, `onsite` |
| `seniority_level` | `trainee`, `entry_level`, `junior`, `mid`, `senior`, `lead`, `director` |
| `role_category` | `backend`, `frontend`, `fullstack`, `ai`, `devops`, `data`, `mobile`, `qa`, `other` |
| `salary_period` | `annual`, `monthly`, `hourly` |

### Step 4 — Decide

The default threshold is 65% (configurable in `~/.applyr/applyr.toml`).

- Score **>= threshold** -> recommend applying. Ask the user to confirm.
- Score **< threshold** -> recommend discarding. Explain the main gaps. Let the user decide.

### Step 5 — If applying

#### 5.1 Update status

```bash
applyr update <id> applied --canal linkedin_easy
```

#### 5.2 CV generation flow (4 steps)

If the user wants a CV tailored to this offer, follow this exact sequence:

**1. Generate the skeleton:**
```bash
applyr cv generate <id>
```
This creates an HTML file at `~/.applyr/cv/cv-<company>-<title>.html` with:
- Locked ATS-safe CSS (NEVER modify)
- Offer context in HTML comments (company, tech stack, scores)
- Placeholder sections (`[PLACEHOLDER]`) for you to fill

**2. Fill the placeholders:**
- Read `~/.applyr/cv-master.md` for all content
- Replace every `[PLACEHOLDER]` with real content from cv-master.md
- Prioritize skills and projects relevant to the target role
- Match keywords from the job description naturally
- Include measurable results (%, numbers, scale) in bullet points
- Keep to 1 page — remove less relevant sections if needed
- NEVER invent content not in cv-master.md
- DO NOT modify the CSS or HTML structure

**3. Review the CV:**
```bash
applyr cv review <path-to-html>
```
This outputs a recruiter-review prompt. Execute it to get:
- ATS Score (0-100)
- Keyword match analysis
- Strengths and weaknesses
- Specific improvements ordered by impact
- Verdict: READY TO SEND / NEEDS EDITS / NEEDS REVISION

If the verdict is not READY TO SEND, apply the suggested improvements and review again.

**4. Generate PDF:**
```bash
applyr cv pdf <path-to-html> --output <path-to-pdf>
```

#### 5.3 Cover letter (optional)

If the user wants a cover letter, create it and note it:
```bash
applyr update <id> applied --notes "Cover letter sent"
```

## Querying data

When the user asks about their job search, use these commands:

| User asks | Command to run |
|-----------|---------------|
| "Show me my applications" | `applyr list` or `applyr list --json` |
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
| "Compare two offers" | `applyr compare 3 7` |
| "What should I learn?" | `applyr plan` |
| "Salary stats" | `applyr salary` |
| "Salary for seniors" | `applyr salary --seniority senior` |
| "Review my CV" | `applyr cv review <file.html>` |
| "Check system health" | `applyr doctor` |

**Tip:** Add `--json` to any data command for structured JSON output.

## If a command fails

Do NOT ignore errors. Follow this recovery procedure:

### `applyr add` fails
- Read the error message — it names the **exact field** and valid values
- Fix that specific field in your JSON and retry
- Do NOT invent data to bypass validation

### `applyr cv pdf` fails
- "Chrome not found" -> tell the user to install Chrome or set `chrome_path` in `~/.applyr/applyr.toml`
- "Chrome timed out" -> the HTML may be too complex. Simplify and retry
- Do NOT silently skip PDF generation

### `applyr cv generate` fails
- "cv-master.md not found" -> tell the user to run `applyr init` and fill in their profile
- Do NOT generate a CV without cv-master.md

### Any "offer not found" error
- Run `applyr list` to check available IDs
- The user may have deleted or never created the offer

## Rules

1. **NEVER invent content** — only use what is in cv-master.md
2. **NEVER guess scores** — evaluate honestly using the rubric above
3. **Be specific in topic details** — explain WHY you gave that score, not just a number
4. **If information is missing from the offer** (salary, work mode, etc.), leave the field out rather than guessing
5. **If the user's cv-master.md is empty**, tell them to fill it in before analyzing offers
6. **Salary**: if the offer says "competitive" or doesn't specify, omit salary fields
7. **Follow-ups**: applyr auto-schedules follow-ups when status is set to `applied` or `waiting`
8. **Config**: scoring weights and topic names can be customized in `~/.applyr/applyr.toml`
9. **Topic keys**: use only keys defined in your config. If you get a "topic not in config" warning, check `~/.applyr/applyr.toml` for the correct keys

## ATS CV rules (when generating HTML CVs)

When creating or editing an HTML CV for ATS submission, follow these rules strictly.
Reference: `templates/cv-ats.html` is the only permitted HTML structure.

1. **Single column only** — never use CSS columns, flexbox, grid, or tables
2. **Standard fonts** — Arial, Calibri, or Georgia only. Size: 11-12pt body, 14-16pt headings
3. **No images, icons, or decorative elements** — ATS parsers see zero text from these
4. **No header/footer content** — contact info must be in the body
5. **Standard section headers** — use: Professional Summary, Work Experience, Education, Projects, Certifications, Technical Skills, Languages
6. **Standard bullets** — use `<ul><li>` only, no custom symbols or checkmarks
7. **Include measurable results** — numbers (%, $, Nx, years) in at least 70% of bullets
8. **Match keywords** — use both acronyms and full terms from the job description (e.g., "Artificial Intelligence (AI)")
9. **Use `|` as separator** in contact info, not special characters
10. **Show full URLs** in links (e.g., `linkedin.com/in/username` not just `LinkedIn`) — URLs must be visible in print
11. **Date format** — use `MM/YYYY` or `Month YYYY` consistently
12. **Plain text test** — the CV must read correctly when copy-pasted into a plain text editor
