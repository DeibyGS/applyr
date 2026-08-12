## Spec: Onboarding Fixes — 7 bug/UX corrections

### Status: DRAFT
### Version: 1.0

### Recovered context
- Project constitution: `/Users/db/Documents/GitHub/applyr/constitution.md`
- Relevant ADRs: ADR 003 (no LLM calls), ADR 006 (errors to stderr)
- Audit date: 2026-08-10
- Scope: 2 bugs, 1 dead code cleanup, 4 UX improvements

### What does it do?
Fix 7 issues found during onboarding audit: 2 logic bugs that cause incorrect behavior, 1 duplicated function, and 4 UX gaps that confuse new users during first-time setup.

### What files does it touch?
| File | Action | Reason |
|------|--------|--------|
| applyr/cv.py | MODIFY | Fix bug #1 (keywords null check), bug #2 (threshold keys), remove duplicate cmd_cv_ats_check |
| applyr/cli.py | MODIFY | Fix #4 (_is_initialized checks DB) |
| applyr/commands/core.py | MODIFY | Improve cv-master.md template (#5), setup-agent warn on empty profile (#7) |
| applyr/commands/workflow.py | MODIFY | Add cv-master.md validation to doctor (#6) |
| tests/test_cv.py | MODIFY | Add regression tests for bugs #1 and #2 |

### Dependencies
- No new APIs, endpoints, or DB schema changes
- Uses existing `inspect_cv_master()` from `applyr/cv_master.py`
- Uses existing `load_config()` from `applyr/config.py`

### Acceptance criteria

#### Bug #1 — cv keywords null check
- `[MUST]` WHEN `applyr cv keywords <id>` is called with a valid offer_id THAT does NOT exist in the database, THE system SHALL exit with code `not_found` and an error message on stderr
- `[MUST]` WHEN `applyr cv keywords <id>` is called with a valid offer_id that DOES exist, THE system SHALL proceed to keyword extraction without error
- `[MUST]` GIVEN an existing offer with a generated CV, WHEN `applyr cv keywords <id>` runs, THEN it returns matched/missing keywords with `--json` support

#### Bug #2 — review-blind threshold keys
- `[MUST]` WHEN `applyr cv review-blind <id>` runs, THE system SHALL read `threshold_apply` from `config["general"]` (not `"threshold"`)
- `[MUST]` WHEN `applyr cv review-blind <id>` runs, THE system SHALL read `threshold_maybe` from `config["general"]` (not `"maybe_threshold"`)
- `[MUST]` GIVEN a user with `threshold_apply = 80` in applyr.toml, WHEN review-blind outputs thresholds, THEN it shows `APPLY >= 80%` (not `>= 65%`)

#### Cleanup #3 — duplicate cmd_cv_ats_check
- `[MUST]` THE system SHALL have exactly one `cmd_cv_ats_check` function definition in cv.py
- `[MUST]` WHEN `applyr cv ats-check <file>` runs, THE system SHALL produce the same output as before (no behavioral change)

#### UX #4 — _is_initialized checks DB
- `[MUST]` WHEN `_is_initialized()` is called AND `~/.applyr/jobs.db` does not exist AND `~/.applyr/applyr.toml` exists, THE system SHALL return `False`
- `[MUST]` WHEN `_is_initialized()` is called AND `~/.applyr/jobs.db` exists, THE system SHALL return `True`
- `[SHOULD]` WHEN `_is_initialized()` returns False, THE system SHALL show the `_GETTING_STARTED` message suggesting `applyr init`

#### UX #5 — cv-master.md template improvement
- `[MUST]` WHEN `applyr init` creates `cv-master.md` for the first time, THE system SHALL include field labels with examples (name, email, skills, experience, projects)
- `[MUST]` THE new template SHALL be valid markdown that passes `inspect_cv_master()` validation (not flagged as "unfilled template")
- `[SHOULD]` THE template SHALL include 3-5 realistic placeholder examples per section

#### UX #6 — doctor validates cv-master.md
- `[MUST]` WHEN `applyr doctor` runs AND `cv-master.md` is missing or unfilled, THE system SHALL report a warning on stderr
- `[MUST]` WHEN `applyr doctor` runs AND `cv-master.md` is filled with real content, THE system SHALL report OK
- `[SHOULD]` THE doctor output SHALL include the reason when cv-master.md is invalid (missing, unfilled, template-only)

#### UX #7 — setup-agent warns on empty profile
- `[MUST]` WHEN `applyr setup-agent` runs AND `cv-master.md` fails `inspect_cv_master()`, THE system SHALL print a warning before writing agent instructions
- `[MUST]` THE warning SHALL explain that CVs generated without a filled profile will be empty
- `[SHOULD]` THE warning SHALL suggest running a text editor to fill `~/.applyr/cv-master.md`

### Explicit assumptions
- `inspect_cv_master()` correctly detects unfilled templates (already tested in test_cv_master.py)
- The existing doctor command in `workflow.py` is the right place to add cv-master validation
- Users won't be confused by a warning during setup-agent (it's additive, not blocking)

### Edge cases / risks
- Risk: New cv-master.md template might not pass `inspect_cv_master()` if the word count threshold is too high → Mitigation: test the template against the validator before shipping
- Risk: `_is_initialized` change could break existing users who have applyr.toml but no DB → Mitigation: they already can't use any command, so returning False is correct

### Task breakdown (execution order)
1. Fix bug #1: invert null check in cmd_cv_keywords (cv.py:904) [S]
2. Fix bug #2: correct threshold keys in cmd_cv_review_blind (cv.py:725-726) [S]
3. Remove duplicate cmd_cv_ats_check (cv.py:1261-1306) [S]
4. Fix _is_initialized to check DB existence (cli.py:117-120) [S]
5. Improve cv-master.md template (core.py:48-62) [S]
6. Add cv-master.md validation to doctor (workflow.py) [S]
7. Add setup-agent warning for empty profile (core.py:348-397) [S]
8. Write regression tests for bugs #1 and #2 [S]
9. Run full test suite + pylint [S]

### Out of scope
- `[WONT]` Changing the `inspect_cv_master()` logic or thresholds
- `[WONT]` Adding new CLI commands or aliases
- `[WONT]` Modifying the DB schema or migrations
- `[WONT]` Changing AGENT_INSTRUCTIONS.md template

### Open questions
- None — all 7 issues have clear fixes identified in the audit
