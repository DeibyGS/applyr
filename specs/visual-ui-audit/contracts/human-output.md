## Contracts: CLI Commands — Human Output Format

### Status: DRAFT
### Version: 1.0

### Overview

Human-readable output is **not a stable contract** — it may change for clarity. `--json` output IS the stable contract (see `json-output.md`).

This document specifies the expected visual structure for each command at standard terminal width (80 cols).

---

### `applyr list [--status S] [--sort F] [--limit N]`

**Structure:**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ID  COMPANY                    TITLE                          %  STATUS      │
├──────────────────────────────────────────────────────────────────────────────┤
│   1  Acme Corp                  Senior Backend Engineer        87  In Process │
│   2  Globex Inc                  Full Stack Developer           72  Applied   │
└──────────────────────────────────────────────────────────────────────────────┘
  2 offer(s) shown.
```

**Column Behavior:**
- ID: Right-aligned, fixed 4 chars
- COMPANY: Left-aligned, truncate at `terminal_width * 0.22`
- TITLE: Left-aligned, truncate at `terminal_width * 0.35`
- %: Right-aligned, 3 chars + "%"
- STATUS: Left-aligned, colored label from StatusDisplay

**Narrow (< 80 cols):** Hide TITLE column, show ID COMPANY % STATUS
**Wide (> 120 cols):** Add DATE column, increase COMPANY/TITLE widths

---

### `applyr show <id>`

**Structure (two-column layout):**
```
============================================================
  Offer #123  —  Senior Backend Engineer
============================================================

  Company            │ Acme Corp
  Job URL            │ https://acme.com/jobs/123
  Job Description    │ [stored, 2,450 chars — see --json]
  Status             │ In Process
  Canal              │ LinkedIn
  Compatibility      │ 87%
  Scored Under       │ tech_stack=35, experience=35, projects=15...

  Work Mode          │ Remote
  Location           │ Madrid, ES
  Seniority          │ Senior
  Role Category      │ Backend
  Tech Stack         │ Python, PostgreSQL, AWS, Kubernetes
  Language           │ en

  Date Received      │ 2026-01-15
  Date Applied       │ 2026-01-16
  Date Responded     │ 2026-01-20

  Salary             │ 60,000 – 80,000 (annual)

  Contact Name       │ Maria Garcia
  Contact Role       │ Tech Lead

  CV Used            │ cv-acme-corp

  Follow-up          │ Upcoming (2026-01-25)
  Follow-up Notes    │ Send portfolio link

  Rejection Reason   │ —

  Summary:
    Great match for Python backend role. Strong on AWS/K8s.

  Notes:
    Applied via referral. Recruiter responded in 4 days.
```

**Visual Rules:**
- Two-column: label │ value (box-drawing light vertical U+2502)
- Labels: left-aligned, 22 chars, muted color
- Values: left-aligned, primary color
- Section headers (blank line between groups)
- Empty/zero values: omitted (except explicit —)
- Related fields grouped: Core → Work Details → Dates → Salary → Contact → Materials → Follow-up → Rejection → Summary/Notes

---

### `applyr pipeline [--min-score N]`

**Structure:**
```
--- Pipeline ---

  Offer               (3)
    #123   87%  Acme Corp              Senior Backend Engineer
    #124   82%  Globex Inc             Full Stack Developer

  In Process          (2)
    #125   91%  TechStart              Lead Engineer
    #126   78%  DataFlow               Senior Data Engineer

  Applied             (5)
    #127   75%  CloudNine              Backend Developer
    ...

  Waiting             (1)
    #128   65%  OldCorp                DevOps Engineer

  Rejected            (2)
    #129   45%  BadFit                 Junior Developer

  Discarded           (0)
```

**Visual Rules:**
- Status labels colored per StatusDisplay
- Count in parentheses
- Each offer: ID, %, Company (truncated), Title (truncated)
- Items sorted by compatibility_pct DESC within status

---

### `applyr stats`

**Structure:**
```
--- Stats ---

  Total offers    : 42
  Pending         : 5
  Discarded       : 3
  Avg Compat.     : 73.2% (2 excluded, unknown weights)

  Conversion Funnel:
    Applied        34  (81% of total)
    Responded      18  (53% of applied)
    Interview      12  (67% of responded)
    Offer           3  (25% of interviews)

  Channel Breakdown:
    LinkedIn                    18
    Company Website             12
    Referral                     7
    Job Board                    5

  Work Mode Breakdown:
    Remote                      22
    Hybrid                      14
    Onsite                       6

  Salary (salary_min, where provided):
    Min : 35,000
    Max : 120,000
    Avg : 68,500

  Score Calibration:
    >= 80%          12 applied  75% responded  58% interview  25% offer
    60-79%          15 applied  47% responded  27% interview   7% offer
    < 60%            7 applied  14% responded   0% interview   0% offer
```

**Visual Rules:**
- Key:Value pairs aligned at `:`
- Funnel: counts right-aligned, percentages in parentheses
- Breakdowns: label left, count right
- Calibration: fixed-width columns for bands

---

### `applyr gaps [--limit N]`

**Structure:**
```
--- Skill Gaps ---

  [HIGH  ]  Technical Skills      seen 8x  avg gap 24%
  [MEDIUM]  Experience            seen 6x  avg gap 18%
  [LOW   ]  Projects              seen 4x  avg gap 12%
  [LOW   ]  Education             seen 3x  avg gap 8%
```

**Visual Rules:**
- Priority badge: colored, 6 chars padded
- Label: left-aligned, 20 chars
- Seen: right-aligned, "Xx"
- Avg gap: right-aligned, "XX%"

---

### `applyr plan [--limit N]`

**Structure:**
```
--- Learning Plan ---

  #    Skill                     Seen  Avg Gap  Priority
  ---  ----------------------  -----  -------  --------
  1    Technical Skills           8x     24%  HIGH
  2    Experience                 6x     18%  MEDIUM
  3    Projects                   4x     12%  LOW
  4    Education                  3x      8%  LOW

  Focus on HIGH items first.
  Skill gaps update automatically when you add scored offers.
```

**Visual Rules:**
- Table with header separator
- Priority colored per gap_priority

---

### `applyr trends [--period week|month]`

**Structure:**
```
--- Trends by Week ---

  2026-W01  ████████░░░░░░░░░░  8  (+14% vs prev)
  2026-W02  ██████████░░░░░░░░  10  (+25% vs prev)
  2026-W03  ████████████░░░░░░  12  (+20% vs prev)
```

**Visual Rules:**
- Period label left
- Bar: width = `TREND_BAR_WIDTH` (15), scaled to max count
- Count right-aligned
- Growth: "(+XX% vs prev)" or "(-XX% vs prev)"

---

### `applyr summary [--json]`

**Structure:**
```
--- Weekly Summary  (2026-01-19 to 2026-01-25) ---

  Applications sent    : 3
  Responses received   : 1  (33.3% response rate)
  Avg compatibility    : 78.5%
  Top skill gap        : Technical Skills
  Channels used        : LinkedIn: 2, Referral: 1
  Work modes           : Remote: 2, Hybrid: 1
```

---

### `applyr compare <id1> <id2> [<idN>...]`

**Structure:**
```
Field              #123                    #124
Company            Acme Corp               Globex Inc
Title              Senior Backend Engineer Full Stack Developer
Score              87%                     72%
Weights            known                   known
Status             In Process              Applied
Seniority          Senior                  Mid
Work Mode          Remote                  Hybrid
Salary             60000-80000/ann         50000-70000/ann
Tech Stack         Python, PostgreSQL...   JavaScript, React...
```

**Visual Rules:**
- Label column: 12 chars left-aligned
- Value columns: equal width, truncated
- Status: colored labels

---

### `applyr salary [--seniority S] [--category C]`

**Structure:**
```
--- Salary Insights ---

  Seniority        Count     Min       Max       Avg       Median  Period
  ---------------  -----  --------  --------  --------  --------  ------
  Senior               12   60,000   120,000    85,000    82,000  annual
  Mid                   8   45,000    80,000    62,000    60,000  annual
  Junior                3   30,000    45,000    37,000    38,000  annual

  Category           Count     Min       Max       Avg       Median
  ---------------  -----  --------  --------  --------  --------
  Backend               10   50,000   110,000    78,000    75,000
  Full Stack             8   45,000    90,000    68,000    65,000
```

---

### `applyr cv generate <id> [--template ats] [--force]`

**Output:**
```
CV draft generated: /home/user/applyr/cvs/cv-acme-corp.md
  Offer    : #123 — Senior Backend Engineer @ Acme Corp
  Template : ats (ATS-safe)
  Language : Spanish (from the offer)
  CV Master: /home/user/applyr/cv-master.md
  Recorded : cv_used = cv-acme-corp

  Tailoring applied:
    ✓ Highlighted: Python, AWS, Kubernetes, Technical Skills
    ✗ De-emphasized: Education
    • Not included: GraphQL, TypeScript
```

---

### `applyr cv review <file>`

**Output:** Recruiter prompt (long text) — see `cv.py:_REVIEW_RUBRIC`

---

### `applyr cv review-blind <id>`

**Output:** Blind recruiter prompt — see `cv.py:_BLIND_REVIEW_RUBRIC`

---

### `applyr cv verify <file>`

**Structure (PASS):**
```
============================================================
  CV Verify — cv-acme-corp.md  (offer #123)
============================================================

  Claims checked : 23
  Supported      : 23
  Unsupported    : 0

  >> PASS — every checked claim is grounded in cv-master.md.
```

**Structure (BLOCKED):**
```
============================================================
  CV Verify — cv-acme-corp.md  (offer #123)
============================================================

  Claims checked : 23
  Supported      : 20
  Unsupported    : 3

  UNSUPPORTED CLAIMS:
    [technology] GraphQL
    [metric] 2.5x
    [employer_or_title] Senior ML Engineer - Acme Corp, Remote

  >> BLOCKED — remove or ground these claims in cv-master.md before sending this CV.
```

---

### `applyr cv pdf <html-file> [--output f.pdf]`

**Output:**
```
PDF generated: /home/user/applyr/cvs/cv-acme-corp.pdf
Warning: PDF is 2 page(s) — ATS rule allows 1 for this profile. Trim content before sending.
```

---

### `applyr cv ats-check <file>`

**Structure:**
```
ATS Check: cv-acme-corp.md
Score: 92/100
Format: OK

Issues:
  [WARN] Section "Certifications" is empty — consider removing
  [INFO] Contact info uses full URLs (good)
```

---

### `applyr cv keywords <id>`

**Structure:**
```
Keyword Match for Offer #123 (Senior Backend Engineer @ Acme Corp)

CV Keywords (from cv-master.md):
  python, postgresql, aws, kubernetes, docker, rest, graphql, ci/cd

Job Keywords (from offer):
  python, postgresql, aws, kubernetes, graphql, microservices, terraform

Match: 7/10 (70%)
Missing in CV: microservices, terraform
Extra in CV: docker, rest, ci/cd
```

---

### `applyr cv bullet-optimize <file>`

**Output:** Optimized bullet suggestions (long text)

---

### `applyr cv cover-letter <id>`

**Output:** Cover letter markdown (long text)

---

### `applyr doctor [--json]`

**Structure:**
```
applyr Doctor — Health Check

✓ Config file: /home/user/.applyr/applyr.toml
✓ Database: /home/user/.applyr/jobs.db (schema v14)
✓ CV Master: /home/user/applyr/cv-master.md (filled)
✓ Chrome: /usr/bin/google-chrome (120.0.6099.109)
✓ Output dir: /home/user/applyr/cvs
✓ Write permissions: OK

No issues found.
```

---

### `applyr export [--format csv|json|md] [--redact]`

**Output:** File written + confirmation message
```
Exported 42 offers to /home/user/applyr/export/offers-2026-01-25.csv
Redacted: job_url, job_description, contact_name, contact_role, notes
```