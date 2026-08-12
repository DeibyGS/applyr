# API Contract: review-blind

## applyr cv review-blind <offer_id>

### Description
Independently evaluate cv-master.md against a job offer without referencing the Matcher's compatibility score.

### Authentication
None (local CLI).

### Request

**Positional Arguments:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| offer_id | integer | yes | ID of the offer to evaluate |

**Flags:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| --json | flag | no | false | Output as JSON |

### Response

**Success (stdout):**

```
ATS Score: 74/100

Verdict: CLOSE MATCH

Strengths:
  ✓ Strong Python and FastAPI experience
  ✓ Relevant project portfolio

Weaknesses:
  ✗ No LangChain or RAG experience
  ✗ English level not demonstrated

Recommendations:
  1. Add a LangChain project to your portfolio
  2. Include English certification in CV
  3. Highlight API design experience more prominently

Conditional Advice:
  Consider applying if you:
  - Highlight your Python API experience in the first paragraph
  - Message the recruiter about your passion for AI tooling
```

**Success (--json):**

```json
{
  "offer_id": 42,
  "ats_score": 74,
  "verdict": "CLOSE_MATCH",
  "strengths": [
    "Strong Python and FastAPI experience",
    "Relevant project portfolio"
  ],
  "weaknesses": [
    "No LangChain or RAG experience",
    "English level not demonstrated"
  ],
  "recommendations": [
    "Add a LangChain project to your portfolio",
    "Include English certification in CV",
    "Highlight API design experience more prominently"
  ],
  "conditional_advice": {
    "apply_with_conditions": true,
    "conditions": [
      "Highlight your Python API experience in the first paragraph",
      "Message the recruiter about your passion for AI tooling"
    ]
  }
}
```

**When verdict is NO_MATCH, conditional_advice is null:**

```json
{
  "offer_id": 42,
  "ats_score": 35,
  "verdict": "NO_MATCH",
  "strengths": ["Basic Python knowledge"],
  "weaknesses": [
    "Missing required React experience",
    "No cloud infrastructure skills",
    "English level below requirement"
  ],
  "recommendations": [
    "Build 2-3 React projects before applying",
    "Study AWS or GCP fundamentals",
    "Obtain B2+ English certification"
  ],
  "conditional_advice": null
}
```

**When verdict is STRONG_MATCH, conditional_advice is null:**

```json
{
  "offer_id": 42,
  "ats_score": 85,
  "verdict": "STRONG_MATCH",
  "strengths": ["Expert in all required technologies"],
  "weaknesses": [],
  "recommendations": ["Consider adding metrics to project descriptions"],
  "conditional_advice": null
}
```

**Error Codes:**

| Exit Code | Code | When |
|-----------|------|------|
| 1 | not_found | offer_id does not exist in DB |
| 1 | cv_master_missing | cv-master.md does not exist or is still template |
| 1 | db_error | Database cannot be opened |

### Verdict Logic

| Score Range | Verdict | conditional_advice |
|-------------|---------|-------------------|
| >= 80 | STRONG_MATCH | null |
| 60–79 | CLOSE_MATCH | {apply_with_conditions: true, conditions: [...]} |
| < 60 | NO_MATCH | null |

### AC Coverage

- AC-1: Blind Recruiter command — reads cv-master.md, evaluates independently
- AC-2: Verdict logic — classifies based on thresholds from config
- AC-3: Conditional advice — included only for CLOSE_MATCH
- AC-7: Reads cv-master.md directly — not the generated CV
- AC-8: Blind — does not load compatibility_pct from DB
- AC-E1: Missing offer → exit 1, code "not_found"
- AC-E2: Missing cv-master.md → exit 1, code "cv_master_missing"
