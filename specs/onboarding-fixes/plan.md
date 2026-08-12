## Architecture

No new components. All fixes are inline changes to existing functions:

```
cv.py:  3 changes (2 bug fixes + 1 dead code removal)
cli.py: 1 change (_is_initialized)
core.py: 2 changes (template + setup-agent warning)
workflow.py: 1 change (doctor validation)
tests: 2 new test functions
```

## Data Model

No changes. No new tables, columns, or migrations.

## Changes by file

### applyr/cv.py
1. **Line 904**: `if not offer is None:` → `if offer is None:`
2. **Lines 725-726**: Replace config key lookups:
   - `config["general"].get("threshold", 80)` → `config["general"].get("threshold_apply", 80)`
   - `config["general"].get("maybe_threshold", 60)` → `config["general"].get("threshold_maybe", 60)`
3. **Lines 1261-1306**: Delete second `cmd_cv_ats_check` definition (exact duplicate of lines 824-881)

### applyr/cli.py
4. **Lines 117-120**: Rewrite `_is_initialized()`:
   ```python
   def _is_initialized() -> bool:
       from applyr.config import APPLYR_DIR
       return (APPLYR_DIR / "jobs.db").exists()
   ```
   Rationale: TOML alone is insufficient — all commands need the DB. If DB is missing, user must run `applyr init`.

### applyr/commands/core.py
5. **Lines 48-62**: Replace `_CV_MASTER_TEMPLATE` with a richer template that includes:
   - Realistic section headers (Summary, Experience, Education, Skills, Projects)
   - Placeholder examples per section (e.g., "Senior Software Engineer at Acme Corp")
   - Enough content words to pass `inspect_cv_master()` validation
6. **Lines 348-397** (`cmd_setup_agent`): After getting `instructions`, before writing to target file:
   ```python
   cv_master = APPLYR_DIR / "cv-master.md"
   if cv_master.exists():
       report = inspect_cv_master(cv_master.read_text(encoding="utf-8"))
       if not report.filled:
           warn(f"Warning: {cv_master} is {report.reason}.")
           warn(f"  CVs generated without a filled profile will have empty sections.")
           warn(f"  Edit {cv_master} with your professional details before generating CVs.")
   ```

### applyr/commands/workflow.py
7. In `cmd_doctor()`, after existing health checks, add:
   ```python
   from applyr.cv_master import inspect_cv_master
   cv_master = APPLYR_DIR / "cv-master.md"
   if not cv_master.exists():
       warn("cv-master.md not found — run 'applyr init' to create it")
   else:
       report = inspect_cv_master(cv_master.read_text(encoding="utf-8"))
       if not report.filled:
           warn(f"cv-master.md is {report.reason} — fill it before generating CVs")
   ```

## Risks
- Risk: New cv-master.md template has more content → `inspect_cv_master()` might reject it → Mitigation: test the template against the validator in the test suite
- Risk: `_is_initialized` strictness could surface errors for users with partial installs → Mitigation: these users already can't use commands, so this surfaces the real problem earlier
