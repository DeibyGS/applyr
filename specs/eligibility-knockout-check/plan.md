# Plan: Eligibility / Knockout Check

### Affected files
| File | Action | Reason |
|------|--------|--------|
| `applyr/eligibility.py` | CREATE | Pure module: parse `## ELIGIBILITY` + languages table from profile text, validate the `add` block, evaluate items. No DB, no config I/O. |
| `applyr/constants.py` | MODIFY | `ELIGIBILITY_YEARS_TOLERANCE = 1`, CEFR order, language-name aliases, section aliases, result states. |
| `applyr/db.py` | MODIFY | `SCHEMA_VERSION = 15`; migration `(14, 15)`: `ADD COLUMN eligibility_requirements TEXT`, `ADD COLUMN eligibility_result TEXT`; same columns in `SCHEMA_SQL`. |
| `applyr/scoring.py` | MODIFY | `recommendation_for(score, config, eligibility_result=None)` → `low_match` when any item is `block`. The reason text comes from `eligibility.block_reason()` (kept in the pure module). |
| `applyr/commands/core.py` | MODIFY | `cmd_add`: validate the block (before insert), read the profile via `get_cv_master_path()`, evaluate, store, print. `cmd_show` + list/search helper: pass the stored result to `recommendation_for`, expose `eligibility` / `eligibility_block`. |
| `applyr/commands/analytics.py` | MODIFY | `pipeline`, `summary`, calibration bands, `cmd_rescore`: pass the stored result; `rescore` re-evaluates. |
| `applyr/pipeline_next.py` | MODIFY | Decide-step warning uses the eligibility-aware recommendation and names the blocking item. |
| `applyr/commands/workflow.py` | MODIFY | `doctor`: WARNING check when the section is missing — non-fatal. |
| `applyr/templates/cv-master-template.md` | MODIFY | Add the `## ELIGIBILITY` section with the four keys. |
| `applyr/templates/AGENT_INSTRUCTIONS.md` + matcher role text | MODIFY | Document the `eligibility` block (mandatory requirements only). |
| `docs/adr/017-eligibility-knockout-check.md` | CREATE | Governing ADR. |
| `docs/contracts.md`, `docs/cli-reference.md`, `CHANGELOG.md` | MODIFY | Contract + JSON shape. |
| `tests/test_eligibility.py` | CREATE | Unit tests for parser + evaluator (AC-03..09, E1, E4). |
| `tests/test_eligibility_cli.py` | CREATE | CLI-level tests for add/show/list/rescore/next/doctor (AC-01, 02, 10..18, E2, E3). |

### Data shapes
`add` input (all keys optional, unknown keys rejected):
```json
"eligibility": {
  "min_years": 3,
  "languages": [{"language": "english", "level": "C1"}],
  "city": "Madrid",
  "driving_license": true
}
```
Profile section (English or Spanish heading and keys):
```markdown
## ELIGIBILITY
- Relevant experience (years): 1
- Cities: Madrid, Alcalá de Henares
- Relocation: no
- Driving license: yes
```
Stored `eligibility_result` / JSON output:
```json
{"items": [{"item": "min_years", "status": "warn", "required": "3", "profile": "2",
            "detail": "1 year short (tolerance 1)"}],
 "blocked": false}
```
`eligibility_block` (JSON output only, derived): `null` or a short string such as
`"language: english C1 required, profile B1"`.

### Dependencies
- DB: `offers` table, two new nullable TEXT columns (additive, no data transformation).
- Profile: `get_cv_master_path()` from `cv.py`; `strip_template_guidance()` from `cv_master.py`
  so template comments are ignored; `fold_accents()` from `evidence.py` for matching.
- No new third-party dependency.

### Explicit technical assumptions
- Every recommendation call-site has the offer row at hand → if one doesn't (e.g. an
  aggregate query), add the column to that SELECT.
- `work_mode` is already stored by `add` → the location item reads it from the same payload.
- The languages table uses `| Language | Level |` rows; the level cell may carry text after
  the CEFR code ("B1 - Intermedio") → the first A1–C2 token or a native keyword wins.

### Non-functional requirements
- Determinism: evaluator is a pure function of (requirements, profile text); no clock, no config.
- Backward compatibility: `recommendation_for(score, config)` keeps working with two args.

### Edge cases / risks
- Schema v15 on `main` widens the known v14/v15 collision with `feat/cc-visual-ui` → note in
  the ADR and HANDOFF; renumbering stays part of that branch's pending merge work.
- Missed call-site returns the score-only recommendation → a test asserts a blocked offer
  reads `low_match` from every listed command (AC-10), plus a grep in review for
  `recommendation_for(` calls without the result argument.
- Agents putting nice-to-haves in the block → instructions say "mandatory only"; the
  `warn` tolerance softens near misses.
- PR budget: estimated ~700–900 lines including tests → chained PRs (see tasks.md).
