## Contracts: CLI Commands — JSON Output Schema

### Status: DRAFT
### Version: 1.0

### Overview

`--json` output IS the stable contract. These schemas must not change without version bump.
All JSON is pretty-printed (indent=2), ensure_ascii=False.

---

### Common Types

```typescript
type OfferStatus = "pending" | "applied" | "waiting" | "in_process" | "offer" | "rejected" | "discarded";
type WorkMode = "remote" | "hybrid" | "onsite" | null;
type Seniority = "junior" | "mid" | "senior" | "lead" | "director" | null;
type Language = "en" | "es" | null;

interface OfferRow {
  id: number;
  company: string | null;
  title: string;
  compatibility_pct: number;
  status: OfferStatus;
  work_mode: WorkMode;
  date_applied: string | null;  // ISO date
  date_received: string | null;
}

interface TopicScore {
  topic: string;
  score: number;
  detail: string | null;
  confidence: "high" | "medium" | "low" | null;
}

interface WeightsUsed {
  tech_stack: number;
  experience: number;
  projects: number;
  education: number;
  english: number;
  cultural_fit: number;
}
```

---

### `applyr list --json`

**Output:** `OfferRow[]`

```json
[
  {
    "id": 123,
    "company": "Acme Corp",
    "title": "Senior Backend Engineer",
    "compatibility_pct": 87,
    "status": "in_process",
    "work_mode": "remote",
    "date_applied": "2026-01-16",
    "date_received": "2026-01-15"
  }
]
```

---

### `applyr show <id> --json`

**Output:** Single object

```json
{
  "id": 123,
  "company": "Acme Corp",
  "title": "Senior Backend Engineer",
  "job_url": "https://acme.com/jobs/123",
  "job_description": "Full job posting text...",
  "summary": "Great match for Python backend role...",
  "notes": "Applied via referral...",
  "compatibility_pct": 87,
  "status": "in_process",
  "canal": "LinkedIn",
  "work_mode": "remote",
  "location": "Madrid, ES",
  "seniority_level": "senior",
  "role_category": "Backend",
  "tech_stack": "Python, PostgreSQL, AWS, Kubernetes",
  "language": "en",
  "date_received": "2026-01-15",
  "date_applied": "2026-01-16",
  "date_responded": "2026-01-20",
  "salary_min": 60000,
  "salary_max": 80000,
  "salary_period": "annual",
  "contact_name": "Maria Garcia",
  "contact_role": "Tech Lead",
  "cover_letter": true,
  "cover_letter_file": "cover-letter-123.md",
  "cv_used": "cv-acme-corp",
  "cv_evidence_used": ["Python", "AWS", "Kubernetes", "PostgreSQL"],
  "follow_up_date": "2026-01-25",
  "follow_up_done": false,
  "follow_up_notes": "Send portfolio link",
  "rejection_reason": null,
  "weights_used": {
    "tech_stack": 35,
    "experience": 35,
    "projects": 15,
    "education": 5,
    "english": 5,
    "cultural_fit": 5
  },
  "topics": [
    {"topic": "tech_stack", "score": 90, "detail": "Strong Python/AWS match", "confidence": "high"},
    {"topic": "experience", "score": 85, "detail": "5+ years backend", "confidence": "high"},
    {"topic": "projects", "score": 70, "detail": "Relevant side projects", "confidence": "medium"},
    {"topic": "education", "score": 60, "detail": "CS degree", "confidence": "high"},
    {"topic": "english", "score": 80, "detail": "Fluent", "confidence": "high"},
    {"topic": "cultural_fit", "score": 75, "detail": "Remote-first culture match", "confidence": "medium"}
  ],
  "confidence": "high"
}
```

---

### `applyr pipeline --json`

**Output:** Object with status keys

```json
{
  "pending": [],
  "applied": [
    {"id": 127, "compatibility_pct": 75, "company": "CloudNine", "title": "Backend Developer"}
  ],
  "waiting": [
    {"id": 128, "compatibility_pct": 65, "company": "OldCorp", "title": "DevOps Engineer"}
  ],
  "in_process": [
    {"id": 125, "compatibility_pct": 91, "company": "TechStart", "title": "Lead Engineer"},
    {"id": 126, "compatibility_pct": 78, "company": "DataFlow", "title": "Senior Data Engineer"}
  ],
  "offer": [
    {"id": 129, "compatibility_pct": 95, "company": "DreamJob", "title": "Staff Engineer"}
  ],
  "rejected": [
    {"id": 130, "compatibility_pct": 45, "company": "BadFit", "title": "Junior Developer"}
  ],
  "discarded": []
}
```

---

### `applyr stats --json`

**Output:**

```json
{
  "total": 42,
  "pending": 5,
  "discarded": 3,
  "avg_compatibility_pct": 73.2,
  "avg_compatibility_pct_excluded_unknown_weights": 2,
  "funnel": {
    "applied": 34,
    "responded": 18,
    "interview": 12,
    "offer": 3
  },
  "channels": {
    "LinkedIn": 18,
    "Company Website": 12,
    "Referral": 7,
    "Job Board": 5
  },
  "work_modes": {
    "Remote": 22,
    "Hybrid": 14,
    "Onsite": 6
  },
  "score_calibration": {
    "apply": {"label": ">= 80%", "total": 12, "responded": 9, "interview": 7, "offer": 3},
    "maybe": {"label": "60-79%", "total": 15, "responded": 7, "interview": 4, "offer": 1},
    "low_match": {"label": "< 60%", "total": 7, "responded": 1, "interview": 0, "offer": 0}
  },
  "excluded_unknown_weights": 2,
  "salary": {"min": 35000, "max": 120000, "avg": 68500}
}
```

---

### `applyr gaps --json`

**Output:** Array of gap objects

```json
[
  {
    "skill": "tech_stack",
    "label": "Technical Skills",
    "frequency": 8,
    "avg_gap": 24,
    "total_gap": 192,
    "priority": "HIGH"
  },
  {
    "skill": "experience",
    "label": "Experience",
    "frequency": 6,
    "avg_gap": 18,
    "total_gap": 108,
    "priority": "MEDIUM"
  }
]
```

---

### `applyr plan --json`

**Output:** Array of plan items

```json
[
  {"rank": 1, "skill": "tech_stack", "label": "Technical Skills", "frequency": 8, "avg_gap": 24, "priority": "HIGH"},
  {"rank": 2, "skill": "experience", "label": "Experience", "frequency": 6, "avg_gap": 18, "priority": "MEDIUM"}
]
```

---

### `applyr trends --json`

**Output:** Array of period objects

```json
[
  {"period": "2026-W01", "count": 8, "growth_pct": 14},
  {"period": "2026-W02", "count": 10, "growth_pct": 25},
  {"period": "2026-W03", "count": 12, "growth_pct": 20}
]
```

---

### `applyr summary --json`

**Output:**

```json
{
  "week": {"start": "2026-01-19", "end": "2026-01-25"},
  "applications_sent": 3,
  "responses_received": 1,
  "response_rate_pct": 33.3,
  "avg_compatibility_pct": 78.5,
  "avg_compatibility_pct_excluded_unknown_weights": 0,
  "top_skill_gap": "Technical Skills",
  "channels": {"LinkedIn": 2, "Referral": 1},
  "work_modes": {"Remote": 2, "Hybrid": 1}
}
```

---

### `applyr compare --json`

**Output:** Array of offer objects

```json
[
  {
    "id": 123,
    "company": "Acme Corp",
    "title": "Senior Backend Engineer",
    "score": 87,
    "weights_used": {"tech_stack": 35, "experience": 35, "projects": 15, "education": 5, "english": 5, "cultural_fit": 5},
    "status": "in_process",
    "seniority": "senior",
    "work_mode": "remote",
    "salary": "60000-80000/ann",
    "tech_stack": "Python, PostgreSQL, AWS, Kubernetes"
  },
  {
    "id": 124,
    "company": "Globex Inc",
    "title": "Full Stack Developer",
    "score": 72,
    "weights_used": {"tech_stack": 35, "experience": 35, "projects": 15, "education": 5, "english": 5, "cultural_fit": 5},
    "status": "applied",
    "seniority": "mid",
    "work_mode": "hybrid",
    "salary": "50000-70000/ann",
    "tech_stack": "JavaScript, React, Node.js, PostgreSQL"
  }
]
```

---

### `applyr salary --json`

**Output:**

```json
{
  "by_seniority": [
    {"seniority": "Senior", "count": 12, "min": 60000, "max": 120000, "avg": 85000, "median": 82000, "period": "annual"},
    {"seniority": "Mid", "count": 8, "min": 45000, "max": 80000, "avg": 62000, "median": 60000, "period": "annual"}
  ],
  "by_category": [
    {"category": "Backend", "count": 10, "min": 50000, "max": 110000, "avg": 78000, "median": 75000},
    {"category": "Full Stack", "count": 8, "min": 45000, "max": 90000, "avg": 68000, "median": 65000}
  ]
}
```

---

### `applyr cv review --json`

**Output:**

```json
{
  "cv_file": "/home/user/applyr/cvs/cv-acme-corp.md",
  "cv_text": "Parsed CV text...",
  "offer_context": "Target Position : Senior Backend Engineer\nCompany         : Acme Corp\n...",
  "prompt": "Full recruiter prompt text..."
}
```

---

### `applyr cv review-blind --json`

**Output:**

```json
{
  "offer_id": 123,
  "cv_master_file": "/home/user/applyr/cv-master.md",
  "cv_text": "Parsed cv-master.md text...",
  "offer_context": "Target Position : Senior Backend Engineer\nCompany         : Acme Corp\n...",
  "prompt": "Full blind review prompt text...",
  "thresholds": {"apply": 80, "maybe": 60},
  "instructions": "Parse ATS COMPATIBILITY SCORE from the prompt output..."
}
```

---

### `applyr cv verify --json`

**Output:**

```json
{
  "passed": true,
  "offer_id": 123,
  "claims": [
    {"category": "technology", "claim": "Python", "supported": true},
    {"category": "technology", "claim": "AWS", "supported": true},
    {"category": "metric", "claim": "2.5x", "supported": true},
    {"category": "employer_or_title", "claim": "Senior Backend Engineer - Acme Corp, Remote", "supported": true}
  ],
  "unsupported": []
}
```

---

### `applyr cv ats-check --json`

**Output:**

```json
{
  "cv_file": "/home/user/applyr/cvs/cv-acme-corp.md",
  "score": 92,
  "format_ok": true,
  "issues": [
    {"level": "WARN", "message": "Section \"Certifications\" is empty — consider removing"},
    {"level": "INFO", "message": "Contact info uses full URLs (good)"}
  ]
}
```

---

### `applyr cv keywords --json`

**Output:**

```json
{
  "offer_id": 123,
  "cv_keywords": ["python", "postgresql", "aws", "kubernetes", "docker", "rest", "graphql", "ci/cd"],
  "job_keywords": ["python", "postgresql", "aws", "kubernetes", "graphql", "microservices", "terraform"],
  "match_count": 7,
  "total_job_keywords": 10,
  "match_pct": 70,
  "missing_in_cv": ["microservices", "terraform"],
  "extra_in_cv": ["docker", "rest", "ci/cd"]
}
```

---

### `applyr cv stats --json`

**Output:**

```json
{
  "cvs": [
    {
      "cv_file": "cv-acme-corp.md",
      "offer_id": 123,
      "applications": 1,
      "responses": 1,
      "interviews": 1,
      "offers": 0,
      "response_rate_pct": 100,
      "interview_rate_pct": 100,
      "ats_score": 92,
      "word_count": 450,
      "keywords_matched": 7
    }
  ]
}
```

---

### `applyr cv compare --json`

**Output:**

```json
{
  "v1": {"ats_score": 88, "word_count": 420, "keywords": 6},
  "v2": {"ats_score": 92, "word_count": 450, "keywords": 7},
  "score_delta": 4,
  "keywords_gained": ["terraform"],
  "keywords_lost": [],
  "recommendations": ["Version 2 improves ATS score by 4 points. Keep the terraform keyword."]
}
```

---

### `applyr doctor --json`

**Output:**

```json
{
  "healthy": true,
  "checks": {
    "config_file": {"ok": true, "path": "/home/user/.applyr/applyr.toml"},
    "database": {"ok": true, "path": "/home/user/.applyr/jobs.db", "schema_version": 14},
    "cv_master": {"ok": true, "path": "/home/user/applyr/cv-master.md", "filled": true},
    "chrome": {"ok": true, "path": "/usr/bin/google-chrome", "version": "120.0.6099.109"},
    "output_dir": {"ok": true, "path": "/home/user/applyr/cvs", "writable": true}
  },
  "issues": []
}
```

---

### `applyr export --json --format json`

**Output:** Full database dump (same as `applyr list --json` with all fields)

```json
[
  {
    "id": 123,
    "company": "Acme Corp",
    "title": "Senior Backend Engineer",
    "job_url": "https://acme.com/jobs/123",
    "job_description": "Full text...",
    "summary": "Summary...",
    "notes": "Notes...",
    "compatibility_pct": 87,
    "status": "in_process",
    "canal": "LinkedIn",
    "work_mode": "remote",
    "location": "Madrid, ES",
    "seniority_level": "senior",
    "role_category": "Backend",
    "tech_stack": "Python, PostgreSQL, AWS, Kubernetes",
    "language": "en",
    "date_received": "2026-01-15",
    "date_applied": "2026-01-16",
    "date_responded": "2026-01-20",
    "salary_min": 60000,
    "salary_max": 80000,
    "salary_period": "annual",
    "contact_name": "Maria Garcia",
    "contact_role": "Tech Lead",
    "cover_letter": true,
    "cover_letter_file": "cover-letter-123.md",
    "cv_used": "cv-acme-corp",
    "cv_evidence_used": ["Python", "AWS", "Kubernetes"],
    "follow_up_date": "2026-01-25",
    "follow_up_done": false,
    "follow_up_notes": "Send portfolio link",
    "rejection_reason": null,
    "weights_used": {"tech_stack": 35, "experience": 35, "projects": 15, "education": 5, "english": 5, "cultural_fit": 5},
    "created_at": "2026-01-15T10:30:00",
    "updated_at": "2026-01-20T14:22:00"
  }
]
```

---

### `applyr response-rate --json`

**Output:**

```json
{
  "overall": {"sent": 34, "responses": 18, "rate_pct": 52.9},
  "by_month": [
    {"month": "2026-01", "sent": 12, "responses": 7, "rate_pct": 58.3},
    {"month": "2026-02", "sent": 10, "responses": 5, "rate_pct": 50.0},
    {"month": "2026-03", "sent": 12, "responses": 6, "rate_pct": 50.0}
  ],
  "by_channel": {
    "LinkedIn": {"sent": 18, "responses": 10, "rate_pct": 55.6},
    "Referral": {"sent": 7, "responses": 5, "rate_pct": 71.4},
    "Company Website": {"sent": 12, "responses": 3, "rate_pct": 25.0}
  }
}
```

---

### `applyr gaps save --json`

**Output:**

```json
{
  "offer_id": 123,
  "gaps_saved": 3
}
```

---

### `applyr gaps list --json`

**Output:**

```json
{
  "total": 15,
  "gaps": [
    {
      "id": 1,
      "offer_id": 123,
      "offer_title": "Senior Backend Engineer",
      "company": "Acme Corp",
      "topic": "tech_stack",
      "gap_detail": "Missing GraphQL experience",
      "severity": "high",
      "suggested_action": "Build a GraphQL API project",
      "created_at": "2026-01-20T10:00:00"
    }
  ]
}
```

---

### `applyr gaps stats --json`

**Output:**

```json
{
  "total": 15,
  "by_topic": {"tech_stack": 8, "experience": 4, "projects": 3},
  "by_severity": {"high": 6, "medium": 5, "low": 4},
  "top_gaps": [
    {"detail": "Missing GraphQL experience", "count": 3},
    {"detail": "No Kubernetes production experience", "count": 2}
  ]
}
```

---

### `applyr rescore --json`

**Output:**

```json
{
  "id": 123,
  "old_compatibility_pct": 85,
  "new_compatibility_pct": 87,
  "weights_used": {"tech_stack": 35, "experience": 35, "projects": 15, "education": 5, "english": 5, "cultural_fit": 5}
}
```

---

### Error Response (all commands)

**On error, exit code != 0, JSON to stdout:**

```json
{
  "error": "offer #999 not found",
  "code": "not_found",
  "details": {"offer_id": 999}
}
```

**Error codes:** `not_found`, `not_initialized`, `invalid_value`, `invalid_argument`, `missing_arguments`, `missing_value`, `db_error`, `chrome_not_found`, `chrome_failed`, `cv_master_missing`, `empty_cv_master`, `already_exists`, `no_offer_id`, `invalid_json`, `unknown_command`, `unsupported_format`, `file_not_found`