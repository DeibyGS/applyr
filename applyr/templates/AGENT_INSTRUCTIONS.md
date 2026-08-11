# applyr — Agent Instructions

> Add this to your AI agent's context (CLAUDE.md, .cursorrules, AGENTS.md, etc.).

## Core Principles

1. **cv-master.md is the only source of truth** — never invent skills, projects, or experience.
2. **Prefer omission over guessing** — if the offer lacks info (salary, work mode), omit the field.
3. **CLI output is authoritative** — trust applyr's scoring, thresholds, and validations.
4. **Respect the user's threshold** — never override the configured minimum compatibility.
5. **Every CV must pass review** — never deliver a CV without running `applyr cv review`.
6. **The Recruiter is blind** — when running `applyr cv review-blind`, do NOT reveal the Matcher's compatibility score.

## Setup

```bash
applyr init
applyr doctor
```

`doctor` is the health check: it verifies the database, config, CV master, agent
instructions and Chrome. **It exits 1 when the setup is unhealthy**, so it is safe to
gate on: `applyr doctor && applyr cv generate 3`. A non-zero exit means applyr found a
problem, not that the command failed — read the report and fix what it names. A CV
master that still holds the empty template is reported here, and every CV generated
from it would be invented.

`applyr doctor --json` returns the same report as `{"healthy", "issues", "checks": [...]}`
for agents that would rather parse than scrape.

Then guide the user through two mandatory steps:

1. **Fill `~/.applyr/cv-master.md`** with their complete professional profile.
2. **Set the threshold** in `~/.applyr/applyr.toml` — ask: "What minimum compatibility score before I recommend applying? Default is 65%."

```toml
[general]
threshold = 65
```

## Workflow

When the user shares a job offer, follow this pipeline in order.

### Step 1 — Health check, then read profile

```bash
applyr doctor
```

Run this first, every session. It exits 1 when something is broken — if that happens,
fix what it names before scoring anything. A `CV Master: WARNING` means the profile is
still the blank template, and a CV built on it will contain invented experience.
Missing Chrome is reported but never blocks: it only stops `cv pdf`.

```bash
cat ~/.applyr/cv-master.md
```

If empty or missing, STOP — tell the user to fill it in first.

### Step 2 — Check duplicates

```bash
applyr search "<company name>"
```

If the company+title already exists: show the existing offer (`applyr show <id>`), STOP.

### Step 3 — Evaluate and register (Matcher role)

Score each topic 0-100 using the rubric, then register:

```bash
applyr add '<json>'
```

The CLI prints a recommendation based on the configured threshold.

#### Scoring rubric

| Topic (default weight) | 0 | 50 | 100 |
|------------------------|---|----|----|
| `tech_stack` (30%) | Knows none required | ~50% of stack | Expert in all |
| `projects` (20%) | No relevant projects | Related but indirect | Directly demonstrates skills |
| `experience` (15%) | Zero relevant exp | Wrong seniority/industry | Exact match |
| `education` (15%) | No relevant education | Related field | Exact degree+level |
| `english` (10%) | Cannot converse | B1/B2 functional | C1+ or native |
| `cultural_fit` (10%) | Incompatible mode/location | Partial match | Perfect alignment |

Weights are configurable in `~/.applyr/applyr.toml` under `[weights]`. The formula is
`sum(topic_score * weight) / sum(weights)`, where **both sums run only over the topics you
provide** — the divisor is not the full 100. Omitting a topic therefore removes it from the
average and redistributes its weight across the rest; it does not count as a zero.

**Scoring rules:** Be honest — inflated scores waste applications.

- Always explain WHY in the `detail` field.
- **If the offer does not mention a topic, omit it entirely. Do not score it 100.** An
  unmentioned requirement is unknown, not satisfied. Scoring it 100 hands out free points
  for a fit nobody verified, and because `education` and `english` alone carry 25% of the
  weight, it puts a 25-point floor under any vaguely written offer — so a vague posting
  outscores a detailed one describing the same job. Omitting is what the formula above
  expects, and it is why the divisor counts only the topics you supply.
- Score what the offer states, not what it implies. If a requirement is mentioned but you
  cannot judge the fit, score it honestly with your uncertainty in `detail` rather than
  dropping it.

**Set `language` to the language the offer is written in.** It decides the language of the CV `cv generate` produces, headings included — a Spanish vacancy answered with a CV titled "Work Experience" reads as machine-made, and an ATS looking for "EXPERIENCIA" matches nothing. Omit it only when the offer's language is genuinely unclear; applyr then falls back to `[cv] language` in applyr.toml.

#### JSON template

Required: `title`. All others optional — fill what you can extract:

```json
{
  "title": "Backend Developer",
  "company": "Acme Corp",
  "summary": "Python backend role focused on APIs",
  "status": "pending",
  "work_mode": "remote",
  "location": "Berlin",
  "seniority_level": "junior",
  "role_category": "backend",
  "language": "es",
  "tech_stack": "Python, FastAPI, AWS",
  "salary_min": 30000, "salary_max": 40000, "salary_period": "annual",
  "canal": "linkedin_easy",
  "job_url": "https://...",
  "topics": {
    "tech_stack": {"score": 80, "detail": "Knows Python+FastAPI, missing AWS"},
    "experience": {"score": 40, "detail": "1yr exp, they ask 3+"},
    "projects": {"score": 85, "detail": "3 relevant backend projects"},
    "education": {"score": 70, "detail": "CS degree, prefer Master's"},
    "english": {"score": 90, "detail": "B2+, offer requires fluent"},
    "cultural_fit": {"score": 75, "detail": "Hybrid ok, prefers remote"}
  }
}
```

<details>
<summary>Valid enum values</summary>

| Field | Values |
|-------|--------|
| `status` | `pending` `applied` `waiting` `in_process` `rejected` `discarded` `offer` |
| `canal` | `linkedin_easy` `linkedin_direct` `email` `portal` `referral` `other` |
| `work_mode` | `remote` `hybrid` `onsite` |
| `seniority_level` | `trainee` `entry_level` `junior` `mid` `senior` `lead` `director` |
| `role_category` | `backend` `frontend` `fullstack` `ai` `devops` `data` `mobile` `qa` `other` |
| `language` | `en` `es` |
| `salary_period` | `annual` `monthly` `hourly` |

</details>

### Step 4 — Decide

The CLI prints `APPLY` or `SKIP`. Follow it:

- **Score >= threshold** — tell the user the score and recommend applying. Wait for confirmation.
- **Score < threshold** — tell the user the score, list skill gaps, recommend archiving. If they agree: `applyr update <id> discarded --notes "Below threshold"`. If they insist, proceed but warn about gaps.

STOP here if the user decides not to apply.

### Step 5 — Recruiter evaluation (blind)

**This step runs for BOTH scores (>= and < threshold).** The Recruiter evaluates independently without knowing the Matcher's score.

```bash
applyr cv review-blind <id>
```

The command outputs:
1. A review prompt for the Recruiter agent to execute
2. Thresholds from config for verdict classification

Execute the prompt yourself as the Recruiter agent. Parse the ATS SCORE and classify:

| Score Range | Verdict | Action |
|-------------|---------|--------|
| >= threshold_apply (default 80) | STRONG_MATCH | Proceed to Step 6 |
| >= threshold_maybe (default 60) and < threshold_apply | CLOSE_MATCH | Include conditional_advice in Step 6 |
| < threshold_maybe | NO_MATCH | Save gaps (Step 5b), explain why |

#### Step 5b — Save gaps (when NO_MATCH or CLOSE_MATCH)

When the Recruiter identifies gaps, save them for future reference:

```bash
applyr gaps save <id> '{"gaps": [{"topic": "tech_stack", "gap_detail": "Missing LangChain", "severity": "high", "suggested_action": "Build a RAG project"}]}'
```

Valid topics: `tech_stack`, `projects`, `experience`, `education`, `english`, `cultural_fit`
Valid severity: `low`, `medium`, `high`

### Step 6 — Generate and review CV

Only when the user confirms they want to apply:

```bash
applyr update <id> applied --canal <channel>
applyr cv generate <id>
```

Fill all `[PLACEHOLDER]` values from cv-master.md following ATS rules (see below). Apply the Recruiter's recommendations from Step 5. Then:

```bash
applyr cv review <path-to-html>
```

Execute the output prompt yourself. Based on the verdict:

| Verdict | Action |
|---------|--------|
| READY TO SEND | Deliver to user |
| NEEDS MINOR EDITS | Apply top 2-3 fixes, re-review (max 2 iterations) |
| NEEDS MAJOR REVISION | Apply all fixes, re-review (max 2 iterations) |

### Step 7 — Deliver

Present the final CV with:
1. ATS score from last review
2. Changes made during iterations (if any)
3. Remaining recommendations
4. PDF generation command: `applyr cv pdf <path-to-html>`

## Agent response format

When evaluating an offer, always respond in this structure:

```
COMPATIBILITY: X% (threshold: Y%)
CONFIDENCE: high | medium | low

STRENGTHS:
- [strength 1]
- [strength 2]

GAPS:
- [gap 1 — impact on score]
- [gap 2 — impact on score]

RECOMMENDATION: APPLY | SKIP
NEXT ACTION: [what to do next]
```

Use `confidence: low` when the offer has sparse information (no tech stack, no requirements listed).

## Example flow

```
User: "Here's a Python backend job at Acme Corp [paste]"

Agent (Matcher):
1. cat ~/.applyr/cv-master.md
2. applyr search "Acme"               → no duplicates
3. Evaluate topics against cv-master
4. applyr add '{"title":"...","topics":{...}}'
   → CLI prints: APPLY (78% >= 65%)
5. Response:
   COMPATIBILITY: 78% (threshold: 65%)
   CONFIDENCE: high
   STRENGTHS: Python expert, 3 relevant projects
   GAPS: Missing AWS (tech_stack -20%)
   RECOMMENDATION: APPLY
   NEXT ACTION: Run blind recruiter evaluation?

User: "yes"

Agent (Recruiter — blind):
6. applyr cv review-blind 42
   → Execute the review prompt
   → ATS SCORE: 74/100 → CLOSE_MATCH
   → Recommendations: highlight Python API experience, add LangChain project

Agent (Matcher — apply recommendations):
7. Apply Recruiter's recommendations to CV
8. applyr cv review cv-acme-backend.md
   → READY TO SEND (ATS: 87/100)
9. applyr gaps save 42 '{"gaps":[{"topic":"tech_stack","gap_detail":"Missing LangChain","severity":"medium"}]}'
10. Deliver CV with score and recommendations
```

## Command reference

| User asks | Command |
|-----------|---------|
| Health check / "is this set up?" | `applyr doctor` |
| Show applications | `applyr list [--json]` |
| Pipeline view | `applyr pipeline` |
| Offer details | `applyr show <id>` |
| Stats / funnel | `applyr stats` |
| Skill gaps | `applyr gaps` |
| Save learning gaps | `applyr gaps save <id> '<json>'` |
| List learning gaps | `applyr gaps list [--topic T] [--severity S]` |
| Gap stats | `applyr gaps stats` |
| Follow-ups due | `applyr followups` |
| Trends | `applyr trends` |
| Weekly summary | `applyr summary [--json]` |
| Search | `applyr search <term>` |
| Compare offers | `applyr compare <id1> <id2>` |
| Learning plan | `applyr plan` |
| Salary stats | `applyr salary [--seniority X]` |
| Export | `applyr export --format json` |
| Review CV | `applyr cv review <file>` |
| Blind recruiter evaluation | `applyr cv review-blind <id>` |
| Discover commands | `applyr --help` |

## Error recovery

| Error | Fix |
|-------|-----|
| Anything unexpected, or unsure of the setup | Run `applyr doctor` first — it names the broken piece. |
| `applyr add` field error | Read the message — it names the field. Fix and retry. |
| Duplicate detected | Do not re-add. Show existing offer. |
| cv-master.md not found | Tell user to run `applyr init` and fill their profile. |
| Chrome not found | User must install Chrome or set `chrome_path` in applyr.toml. |
| Chrome timeout | Simplify HTML and retry. |
| Offer not found | Run `applyr list` to check IDs. |

## ATS CV rules

1. Single column — no flexbox, grid, or tables
2. Fonts: Arial or Calibri, 11-12pt body, 14-16pt headings
3. No images, icons, or decorative elements
4. Standard headers: Professional Summary, Work Experience, Education, Projects, Certifications, Technical Skills, Languages
5. Measurable results in 70%+ of bullets (%, $, Nx, users)
6. Match keywords: both acronyms and full terms (e.g., "Artificial Intelligence (AI)")
7. Separator: `|` in contact info. Show full URLs. Date format: `MM/YYYY`
8. Must read correctly when copy-pasted as plain text
9. Do NOT modify the generated CSS
