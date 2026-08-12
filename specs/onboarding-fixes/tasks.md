## Tasks — Onboarding Fixes

### TASK-001: Fix cmd_cv_keywords null check [S]
**File:** `applyr/cv.py:904`
**Change:** `if not offer is None:` → `if offer is None:`
**Test:** Add test in `tests/test_cv.py` — call `cmd_cv_keywords` with non-existent offer_id, assert exits with `not_found`

### TASK-002: Fix cmd_cv_review_blind threshold keys [S]
**File:** `applyr/cv.py:725-726`
**Change:**
- `config["general"].get("threshold", 80)` → `config["general"].get("threshold_apply", 80)`
- `config["general"].get("maybe_threshold", 60)` → `config["general"].get("threshold_maybe", 60)`
**Test:** Add test in `tests/test_cv.py` — mock config with custom thresholds, verify review-blind output shows correct values

### TASK-003: Remove duplicate cmd_cv_ats_check [S]
**File:** `applyr/cv.py:1261-1306`
**Change:** Delete the second `cmd_cv_ats_check` function definition
**Test:** Run existing `tests/test_ats.py` — all tests must still pass (function at lines 824-881 is the canonical one)

### TASK-004: Fix _is_initialized to check DB [S]
**File:** `applyr/cli.py:117-120`
**Change:** Rewrite to only check for `jobs.db` existence
**Test:** Add test in `tests/test_cli_routing.py` — scenario: applyr.toml exists but jobs.db missing → `_is_initialized()` returns False

### TASK-005: Improve cv-master.md template [S]
**File:** `applyr/commands/core.py:48-62`
**Change:** Replace `_CV_MASTER_TEMPLATE` with richer template containing realistic examples
**Test:** Add test in `tests/test_cv_master.py` — new template passes `inspect_cv_master()` (report.filled == True or at least not "unfilled template")

### TASK-006: Add cv-master.md validation to doctor [S]
**File:** `applyr/commands/workflow.py` (in `cmd_doctor`)
**Change:** After existing checks, validate cv-master.md existence and content
**Test:** Add test in existing test file — doctor warns when cv-master.md is missing, doctor warns when cv-master.md is unfilled template

### TASK-007: Add setup-agent warning for empty profile [S]
**File:** `applyr/commands/core.py:348-397` (in `cmd_setup_agent`)
**Change:** After getting instructions, before writing target file, check cv-master.md and warn if unfilled
**Test:** Add test in `tests/test_commands.py` — setup-agent with unfilled cv-master.md prints warning

### TASK-008: Run full test suite + pylint [S]
**Command:** `pytest && pylint applyr/ --disable=C0114,C0115,C0116,R0913,R0914,R0801 --fail-under=7.0`
**Expected:** All tests pass, pylint >= 7.0

## Execution order
```
TASK-001 → TASK-002 → TASK-003 → TASK-004 → TASK-005 → TASK-006 → TASK-007 → TASK-008
```
All tasks are sequential (each touches a different file section, no conflicts, but testing needs the fixes in place first).
