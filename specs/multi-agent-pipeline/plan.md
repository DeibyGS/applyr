# Technical Plan: Multi-Agent Pipeline

## Spec Reference
Implements: `specs/multi-agent-pipeline/spec.md`

## Architecture Overview

The pipeline adds two new capabilities to applyr:
1. A `review-blind` command that independently evaluates cv-master.md against a job offer
   without referencing the Matcher's compatibility score.
2. A `learning_gaps` table and CRUD commands to persist skill gaps for future consultation.

The agent calling applyr orchestrates the flow: Matcher → Recruiter → apply recommendations.
Applyr remains a CLI storage layer — no LLM calls, no internet, no orchestration logic.

## Component Breakdown

### Blind Recruiter (`review-blind`)
- **Responsibility:** Read cv-master.md fresh, evaluate against offer, return ATS assessment
- **Location:** `applyr/cv.py` (new function `review_blind()`) + `applyr/commands/workflow.py` (routing)
- **Accepts:** offer_id (int)
- **Returns:** JSON with ats_score, verdict, strengths, weaknesses, recommendations, conditional_advice
- **AC Coverage:** AC-1, AC-2, AC-3, AC-7, AC-8

### Gap Management (`gaps save/list/stats`)
- **Responsibility:** Persist and query learning gaps across offers
- **Location:** `applyr/commands/analytics.py` (new functions) + `applyr/db.py` (new table)
- **Accepts:** offer_id, gaps JSON (save); filters (list); none (stats)
- **Returns:** Confirmation (save); table/JSON (list); summary (stats)
- **AC Coverage:** AC-4, AC-5, AC-6

### Schema Migration v5
- **Responsibility:** Add learning_gaps table to existing databases
- **Location:** `applyr/db.py` (MIGRATIONS dict, SCHEMA_SQL, SCHEMA_VERSION)
- **Accepts:** N/A (automatic on first run)
- **Returns:** N/A
- **AC Coverage:** AC-4

### AGENT_INSTRUCTIONS.md Update
- **Responsibility:** Document the two-agent workflow for external agents
- **Location:** `applyr/templates/AGENT_INSTRUCTIONS.md`
- **Accepts:** N/A (template)
- **Returns:** N/A
- **AC Coverage:** AC-W1

## Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Blind review location | cv.py (new function) | Review logic already lives here |
| Gap storage | New table (not extending offer_topics) | Cleaner separation, avoids NULL columns |
| Verdict thresholds | Read from config (existing thresholds) | User-configurable, consistent with Matcher |
| JSON output | Same pattern as other commands | Agent-consumable, backward compatible |

## Integration Points

- `applyr add` → saves offer with compatibility_pct (existing, unchanged)
- `applyr cv review-blind` → reads offer from DB, reads cv-master.md, returns assessment
- `applyr gaps save` → writes to learning_gaps table
- `applyr gaps list/stats` → reads from learning_gaps + offers
- `applyr cv generate` → unchanged, called after Recruiter recommendations applied

## AC Coverage Map

| AC | Component(s) | Contract(s) |
|----|-------------|-------------|
| AC-1 | Blind Recruiter | contracts/review-blind.md |
| AC-2 | Blind Recruiter | contracts/review-blind.md |
| AC-3 | Blind Recruiter | contracts/review-blind.md |
| AC-4 | Gap Management | contracts/gaps.md |
| AC-5 | Gap Management | contracts/gaps.md |
| AC-6 | Gap Management | contracts/gaps.md |
| AC-7 | Blind Recruiter | contracts/review-blind.md |
| AC-8 | Blind Recruiter | contracts/review-blind.md |
| AC-E1 | Blind Recruiter | contracts/review-blind.md |
| AC-E2 | Blind Recruiter | contracts/review-blind.md |
| AC-E3 | Gap Management | contracts/gaps.md |
| AC-W1 | AGENT_INSTRUCTIONS | N/A (template update) |

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Recruiter accidentally reads Matcher's score | Low | High | Code review: review_blind() must not query compatibility_pct |
| Migration v5 fails on existing DB | Low | High | Test with DB at each previous version |
| Agent doesn't follow two-agent sequence | Medium | Medium | AGENT_INSTRUCTIONS.md documents exact flow |
| Gap table grows unbounded | Low | Low | CASCADE on offer delete; no auto-cleanup needed |

## Out of Scope (Technical)
- No new dependencies (stdlib only)
- No network calls
- No changes to existing scoring formula
- No changes to cv generate or cv review (existing commands)
