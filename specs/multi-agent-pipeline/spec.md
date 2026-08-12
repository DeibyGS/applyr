# Multi-Agent Pipeline: Blind Recruiter + Gap Tracking

Status: Draft
Version: 1.0
Last updated: 2026-08-09

## Overview
Evolve applyr from a single-agent workflow to a two-agent blind pipeline where
a Matcher evaluates compatibility and an independent Recruiter analyzes the CV
without knowing the Matcher's score. Gaps are persisted for future consultation.

## User Stories

### Primary
As a job seeker, I want a Recruiter agent to independently evaluate my CV against
a job offer so that I get an unbiased ATS assessment before applying.

### Secondary
As a job seeker, I want my skill gaps saved automatically so that I can track
what to improve across multiple job applications.

## Boundaries

**Always do:**
- Recruiter reads cv-master.md fresh, never the Matcher's score
- Gaps are saved to DB when score < threshold
- conditional_advice is provided when score is near the threshold

**Ask first:**
- Changing the threshold defaults in constants.py
- Adding new topic keys beyond the existing 6

**Never do:**
- Recruiter receives or reads the Matcher's compatibility_pct
- Gaps are deleted when an offer is deleted (CASCADE is acceptable)
- Internet calls for research (agent handles this, not applyr)

## Acceptance Criteria

### AC-1: Blind Recruiter command [MUST]
Given an offer ID in the DB
When `applyr cv review-blind <id>` is executed
Then the system SHALL read cv-master.md fresh and evaluate it against the offer
  independently, returning ats_score (0-100), verdict, strengths, weaknesses,
  recommendations, and conditional_advice

### AC-2: Verdict logic [MUST]
Given the Recruiter's ATS score
When the score is evaluated against thresholds from config
Then the system SHALL classify as:
  - STRONG_MATCH when score >= threshold_apply (default 80)
  - CLOSE_MATCH when score >= threshold_maybe (default 60) and < threshold_apply
  - NO_MATCH when score < threshold_maybe

### AC-3: Conditional advice [SHOULD]
Given a CLOSE_MATCH verdict
When the Recruiter returns its assessment
Then the output SHALL include conditional_advice with specific conditions
  for applying (e.g., "highlight X", "message recruiter about Y")

### AC-4: Gap persistence [MUST]
Given a NO_MATCH or CLOSE_MATCH verdict
When `applyr gaps save <id> '<json>'` is executed
Then the system SHALL store each gap in the learning_gaps table with
  topic, gap_detail, severity, and suggested_action

### AC-5: Gap listing [MUST]
Given gaps stored in the DB
When `applyr gaps list [--topic T] [--severity S]` is executed
Then the system SHALL display matching gaps with offer context (title, company)

### AC-6: Gap stats [SHOULD]
Given gaps stored in the DB
When `applyr gaps stats` is executed
Then the system SHALL show summary: gaps per topic, severity distribution,
  and top gaps across offers

### AC-7: Recruiter reads cv-master.md [MUST]
Given the Recruiter command is executed
When it reads the candidate's profile
Then it SHALL read cv-master.md directly (NOT the generated CV skeleton)
  to ensure independent evaluation

### AC-8: Recruiter is blind [MUST]
Given the Recruiter command receives an offer ID
When it loads offer data from DB
Then it SHALL NOT load or reference the compatibility_pct from the Matcher

### AC-E1: Missing offer [MUST]
Given an invalid offer ID
When `applyr cv review-blind <id>` is executed
Then the system SHALL exit with code 1 and error code "not_found"

### AC-E2: Missing cv-master.md [MUST]
Given cv-master.md is missing or still template
When `applyr cv review-blind <id>` is executed
Then the system SHALL exit with code 1 with appropriate error

### AC-E3: Empty gaps save [MUST]
Given `applyr gaps save <id> '<json>'` with empty gaps array
When executed
Then the system SHALL exit with code 1 and error code "missing_field"

### AC-W1: Workflow integration [SHOULD]
Given the AGENT_INSTRUCTIONS.md template
When updated for v1.2.0
Then it SHALL document the two-agent flow:
  1. Matcher: applyr add (evaluates compatibility)
  2. If score >= 60: Recruiter: applyr cv review-blind (independent analysis)
  3. If CLOSE_MATCH: apply conditional advice
  4. If NO_MATCH: applyr gaps save (persist gaps)
  5. Matcher: apply recommendations, generate final CV

## Out of Scope
- [WONT] Internet research for trends (agent handles this, not applyr)
- [WONT] Multiple Recruiter agents or scoring rounds
- [WONT] Automatic gap resolution (user must act on recommendations)
- [WONT] New topic keys beyond the existing 6

## Open Questions
- [RESOLVED] Should Recruiter read cv-master.md or generated CV? → cv-master.md (independent)
- [RESOLVED] Where to store gaps? → New learning_gaps table
- [RESOLVED] When to trigger Recruiter? → Both above and below threshold
