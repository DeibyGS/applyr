# API Contract: gaps

## applyr gaps save <offer_id> '<json>'

### Description
Save learning gaps for a job offer to the learning_gaps table.

### Request

**Positional Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| offer_id | integer | yes | ID of the offer |
| gaps_json | string | yes | JSON array of gap objects |

**JSON Schema:**

```json
{
  "gaps": [
    {
      "topic": "tech_stack",
      "gap_detail": "Missing LangChain and RAG experience",
      "severity": "high",
      "suggested_action": "Build a RAG project with LangChain"
    }
  ]
}
```

| Field | Type | Required | Default | Values |
|-------|------|----------|---------|--------|
| topic | string | yes | — | tech_stack, projects, experience, education, english, cultural_fit |
| gap_detail | string | yes | — | Free text description |
| severity | string | no | "medium" | low, medium, high |
| suggested_action | string | no | null | Free text recommendation |

### Response

**Success (stdout):**

```
Saved 3 gaps for offer #42 (American Language Academy)
```

**Success (--json):**

```json
{
  "offer_id": 42,
  "gaps_saved": 3
}
```

**Error Codes:**

| Exit Code | Code | When |
|-----------|------|------|
| 1 | not_found | offer_id does not exist |
| 1 | missing_field | gaps array is empty or missing |
| 1 | invalid_value | topic or severity not in valid set |

---

## applyr gaps list [--topic <topic>] [--severity <severity>]

### Description
List learning gaps with optional filters.

### Request

**Flags:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| --topic | string | no | all | Filter by topic |
| --severity | string | no | all | Filter by severity |
| --json | flag | no | false | Output as JSON |

### Response

**Success (stdout):**

```
Learning Gaps (5 total)

  #  Offer                        Topic       Severity  Gap Detail
  1  American Language Academy    tech_stack  high      Missing LangChain
  2  American Language Academy    english     medium    B1 level, needs B2
  3  Google - Backend             tech_stack  high      No GCP experience
  4  Google - Backend             experience  medium    Junior level expected
  5  Startup XYZ                  projects    low       No open source contributions
```

**Success (--json):**

```json
{
  "total": 5,
  "gaps": [
    {
      "id": 1,
      "offer_id": 42,
      "offer_title": "Programador Junior E-Learning",
      "company": "American Language Academy",
      "topic": "tech_stack",
      "gap_detail": "Missing LangChain",
      "severity": "high",
      "suggested_action": "Build a RAG project",
      "created_at": "2026-08-09"
    }
  ]
}
```

**Empty result:**

```
No learning gaps found.
```

---

## applyr gaps stats

### Description
Show summary statistics of learning gaps.

### Request

**Flags:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| --json | flag | no | false | Output as JSON |

### Response

**Success (stdout):**

```
Learning Gaps Summary

  Total gaps: 12

  By Topic:
    tech_stack     5  ██████████████
    english        3  █████████
    experience     2  ██████
    projects       1  ███
    cultural_fit   1  ███

  By Severity:
    high           6  ██████████████████
    medium         4  ████████████
    low            2  ██████

  Top Gaps (by frequency):
    1. Missing LangChain/RAG experience  (3 offers)
    2. English B1 needs B2               (3 offers)
    3. No cloud platform experience      (2 offers)
```

**Success (--json):**

```json
{
  "total": 12,
  "by_topic": {
    "tech_stack": 5,
    "english": 3,
    "experience": 2,
    "projects": 1,
    "cultural_fit": 1
  },
  "by_severity": {
    "high": 6,
    "medium": 4,
    "low": 2
  },
  "top_gaps": [
    {"detail": "Missing LangChain/RAG experience", "count": 3},
    {"detail": "English B1 needs B2", "count": 3},
    {"detail": "No cloud platform experience", "count": 2}
  ]
}
```
