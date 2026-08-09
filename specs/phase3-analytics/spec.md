## Spec: Phase 3 — Analytics

### Status: DRAFT
### Version: 1.0

### Recovered context
- Project constitution: `constitution.md`
- Relevant ADRs: ADR 003 (No LLM calls)
- Phase 1 spec: `specs/phase1-ats-compatibility/spec.md`
- Phase 2 spec: `specs/phase2-recruiter-experience/spec.md`
- Industry research: A/B testing, response rate tracking, application pipeline analytics

### What does it do?
Adds analytics capabilities for tracking application performance, A/B testing CV variants, and measuring response rates across job applications.

### What files does it touch?
| File | Action | Reason |
|------|--------|--------|
| `applyr/analytics.py` | CREATE | New module: CV comparison, response tracking |
| `applyr/commands/analytics.py` | MODIFY | Add `compare_cvs()`, `response_rate()` functions |
| `applyr/cli.py` | MODIFY | Add `compare-cvs` and `response-rate` commands |
| `applyr/db.py` | MODIFY | Add `cv_versions` table, `response_tracking` table |
| `tests/test_analytics.py` | CREATE | Unit tests for analytics module |

### Dependencies
- APIs / endpoints used: None
- DB tables / relevant RLS: New tables: `cv_versions`, `response_tracking`
- Auth pattern: None
- Reused components: `db.py` (get_conn, migrations), `config.py` (load_config), `ats.py` (ATS scoring from Phase 1)

### Acceptance criteria

#### EARS format:

- `[MUST]` WHEN user runs `applyr cv compare <v1_file> <v2_file>` THE system SHALL compare two CV versions and return ATS score delta, keyword coverage delta, and recommendations
- `[MUST]` WHEN user runs `applyr response-rate` THE system SHALL calculate response rate (applied / responses) and show trends over time
- `[MUST]` THE system shall track which CV version was used for each application
- `[MUST]` THE system shall store application response status (no_response, viewed, contacted, interview, rejected)
- `[SHOULD]` IF user runs `applyr cv compare` with `--json` THEN the system SHALL output structured comparison data
- `[SHOULD]` THE system shall show response rate by: offer status, seniority level, work mode
- `[COULD]` WHERE user runs `applyr response-rate --by tech_stack` THEN the system SHALL break down response rate by technology stack

#### Given/When/Then:

- `[MUST]` Given two CV versions (v1 with 70% ATS score, v2 with 85%), When user runs `compare-cvs`, Then output shows "+15% ATS improvement" with specific keyword gains
- `[MUST]` Given 10 applications with 3 responses, When user runs `response-rate`, Then output shows "30% response rate"
- `[MUST]` Given an offer with cv_used field, When user runs `response-rate --by cv`, Then output groups responses by CV version
- `[SHOULD]` Given applications across 3 months, When user runs `response-rate`, Then shows monthly trend

### Explicit assumptions
- We assume response tracking is manual (user updates status) → if false, need email parsing
- We assume CV comparison is local (no cloud) → if false, need sync service
- We assume response rate is per-application → if false, need per-company aggregation

### Non-functional requirements
- Performance: CV comparison completes in < 5 seconds
- Security: No external API calls, all local SQLite
- Usability: Output readable in terminal and parseable via `--json`

### Edge cases / risks
- Applications with no response status → exclude from rate calculation → mark as "unknown"
- Same CV used for multiple applications → cannot A/B test → warn user
- No applications in database → return empty state with helpful message

### Task breakdown (execution order)
1. Create `applyr/analytics.py` module [S]
2. Add DB migrations for `cv_versions` and `response_tracking` tables [M]
3. Create `tests/test_analytics.py` [S]
4. Implement `compare_cvs()` in `analytics.py` [M]
5. Implement `response_rate()` in `analytics.py` [M]
6. Add CLI routing in `cli.py` [S]
7. Integration test: full flow with real data [S]

### Out of scope
- `[WONT]` Email parsing for automatic response detection
- `[WONT]` Cloud sync of analytics data
- `[WONT]` Machine learning recommendations (keep it simple)
- `[WONT]` Export to external analytics tools

### Open questions
- [NEEDS CLARIFICATION] Should `cv compare` also show word count difference and readability score?
- [NEEDS CLARIFICATION] Should `response-rate` show median days to response?
- [NEEDS CLARIFICATION] Should we track which platform the application came from (linkedin, email, portal)?
