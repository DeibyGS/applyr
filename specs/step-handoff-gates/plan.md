# Plan: Step Handoff Gates

Technical design for `spec.md`. This file can change without re-approving the spec, as
long as every `[MUST]` AC in `spec.md` is still satisfied.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/gates.py` | CREATE | Pure artifact logic: locate/validate the Architect's plan, compute the per-step checklist for one offer. Filesystem reads only — no DB, no config, no LLM. Shared by `cv generate`, `cv gate` and `next`. |
| `applyr/constants.py` | MODIFY | New error codes, plan filename + heading aliases, section display labels, `FACT_CHECK_PASS_MIN`, the pipeline-state list. No magic numbers elsewhere. |
| `applyr/cv.py` | MODIFY | `cmd_cv_generate` refuses without a valid plan (AC-01..04); `_check_pdf_gate` also requires a fresh passing fact check (AC-14/15); new `cmd_cv_fact_check` prints the adversarial prompt and accepts `--record`; `cmd_cv_verify` prints framing warnings (AC-18/19). |
| `applyr/pipeline_next.py` | MODIFY | `derive_next` gains the `plan` state (AC-09/10) and the `fact_check` state (AC-12/16); `review_verdict` derives the fact-check verdict from the score (AC-13). |
| `applyr/commands/workflow.py` | MODIFY | `cmd_next` computes plan validity and passes it into `derive_next`; new `cmd_cv_gate` renders the checklist (human + `--json`, AC-07/08). |
| `applyr/cli.py` | MODIFY | Route `cv gate` and `cv fact-check`; add both to the valid-subcommand list and the help text. |
| `applyr/templates/AGENT_INSTRUCTIONS.md` | MODIFY | Step 5.7 names the plan artifact and the gate; new Step 6c (fact check) between review and verify; Step 6 and 6b reference the checklist; bypasses must leave a trace (AC-22/24). |
| `applyr/templates/agents/*.md` (5 files) | MODIFY | First instruction of every role: run `applyr cv gate <id>` and stop if an earlier artifact is missing (AC-23). |
| `docs/adr/018-step-handoff-gates.md` | CREATE | Governing ADR — required because `AGENT_INSTRUCTIONS.md` is a forbidden change. |
| `docs/contracts.md`, `docs/cli-reference.md`, `CHANGELOG.md` | MODIFY | Contract, command reference, release notes. |
| `tests/test_gates.py` | CREATE | Unit: plan validation states, checklist derivation, framing lint (AC-03, 05, 06, 18..20, E1, E2). |
| `tests/test_gates_cli.py` | CREATE | CLI: `generate` refusal + `--force` note, `cv gate` human/JSON, `next` states, `cv pdf` refusal, `--record` fact check (AC-01, 02, 04, 07..17, E3..E5). |
| `tests/test_cv.py`, `tests/test_cv_language.py` | MODIFY | Their generate tests run through the new gate, so their fixtures now write a plan; `_make_slug` was renamed `make_slug` (a second module needs the same naming rule). |
| `tests/test_agent_instructions.py` | MODIFY | Extend the existing packaging/stamp tests with assertions that the new steps and role first-lines ship (AC-22/23). |

No `data-model.md`: no column, no table, no migration (spec `[WONT]` + Deiby's decision
3A). No `contracts/` directory: the project keeps CLI JSON shapes inside `plan.md`.

### Data shapes

**Plan artifact** — `~/Documents/applyr/cv/cv-<company-slug>-plan.md`, written by the
agent in Step 5.7. Parsed with the same regex approach the CV uses (no YAML dependency
exists in the package):

```markdown
---
offer_id: 299
company: "Teros AI"
---

## Forbidden claims
- Do not present RAG or LangChain as professional experience — master's exercise only.
- Do not claim cloud (AWS/GCP/Azure) — profile has OCI only.

## Positioning
...
```

Validity is a four-state result, never a boolean, so the message can say what to fix:

| State | Meaning | `cv generate` exit |
|-------|---------|--------------------|
| `missing` | file does not exist | 1, `plan_required` |
| `wrong_offer` | `offer_id` absent or ≠ the requested offer | 1, `plan_invalid` |
| `empty` | heading present, zero forbidden claims | 1, `plan_invalid` |
| `unreadable` | decode/IO failure | 1, `plan_invalid` |
| `valid` | everything above holds | proceeds |

Heading aliases (English + Spanish, same bilingual rule as `evidence._SECTION_MAP`):
`forbidden claims`, `claims prohibidas`, `prohibited claims`, `restricciones`.

**`cv gate` JSON** — keys are a public contract (cannot be renamed later):

```json
{
  "offer_id": 299,
  "ok": false,
  "state": "plan",
  "missing": ["plan"],
  "steps": [
    {"step": "score",        "status": "ok",             "detail": "6 topics scored"},
    {"step": "decide",       "status": "ok",             "detail": "review_blind recorded"},
    {"step": "plan",         "status": "missing",        "detail": "no plan for offer 299",
     "command": "applyr role architect"},
    {"step": "generate",     "status": "pending",        "detail": "blocked by: plan"},
    {"step": "cv_review",    "status": "not_applicable", "detail": "no CV file yet"},
    {"step": "fact_check",   "status": "not_applicable", "detail": "no CV file yet"},
    {"step": "verify",       "status": "not_applicable", "detail": "no CV file yet"},
    {"step": "pdf",          "status": "not_applicable", "detail": "no CV file yet"},
    {"step": "apply",        "status": "not_applicable", "detail": "no PDF yet"}
  ]
}
```

`status` vocabulary (additive only): `ok` · `missing` · `invalid` · `pending` ·
`not_applicable`. Exit 1 whenever `missing` or `invalid` is non-empty.

**Fact-check record** — appended to the existing `cv_iteration_history`:

```json
{"step": "fact_check", "score": 100, "verdict": "PASS", "at": "<ISO-8601>"}
```

`score` is the evidence density the agent reports (0-100) — how many major claims are
free of P0/P1 issues. `verdict` is derived by `review_verdict`, never taken from the
agent. `cv_iteration` is incremented only for `cv_review`, unchanged.

**Framing warning** — printed by `cv verify`, added under a `Framing` heading and as a
`framing` array in `--json`:

```
Framing:
  ! 'RAG' is in the CV summary but cv-master only has it under PROYECTOS
    (Pipeline RAG) and FORMACIÓN — reframe as project/course, not experience.
```

### Dependencies

- Reuses `find_cv_for_offer`, `_verify_cv`, `_strip_frontmatter`,
  `_extract_offer_id_from_md`, `_build_tech_vocabulary`, `parse_evidence` and its
  `EvidenceClaim.section` from `cv.py` / `evidence.py`.
- Reuses `_note_forced_pdf`'s note-append SQL for the `cv generate --force` bypass note
  (extracted into a shared helper).
- Reuses `record_review` / `review_verdict` / `derive_next` from `pipeline_next.py`
  (ADR-015) — one more state, one more step name, no second state machine.
- DB: `offers` read (existing columns only) + the `notes` append UPDATE.
- No new third-party dependency, no schema version bump, no LLM call (ADR 003).

### Module structure

`applyr/gates.py` owns everything about "is the previous step's artifact there", so the
three commands that need it agree by construction:

```
plan_path_for(company) -> Path                 # output dir + slug
validate_plan(path, offer_id) -> PlanStatus    # five states above
gate_checklist(...) -> list[GateItem]          # the table in cmd_cv_gate
```

`cv.py` keeps the two hard refusals next to the code they guard (generate, pdf), exactly
as ADR-015 put `verify_required` next to rendering. `pipeline_next.py` keeps owning state
derivation so `next` and `gate` cannot disagree: `cv gate` reports `state` by calling
`derive_next` once, then layers the artifact detail on top.

### Technical decisions

- **Barrier in `cv generate`, not only in `cv gate`** — a command the agent must
  remember to call is a hint, not a barrier (ADR-015's own lesson). `cv gate` is the
  visibility layer; `generate`/`pdf` are the enforcement. *(Alternative: gate-only —
  rejected, it reproduces today's failure.)*
- **Two error codes, `plan_required` vs `plan_invalid`** — an agent branches differently
  on "you skipped a step" than on "the artifact you produced is malformed". *(Alternative:
  one code — rejected, the message would have to guess.)*
- **Fact-check prompt is printed from the role file** (`templates/agents/fact_checker.md`)
  plus a recording appendix generated by the code. The role text is the single source;
  embedding a second copy in `cv.py` is exactly how the fact checker got orphaned in the
  first place. *(Alternative: inline prompt like `cv review` — rejected, drift risk.)*
- **`FACT_CHECK_PASS_MIN = 100`, and the role prompt defines density as "major claims
  with no open P0/P1 issue"** — pass then means "zero blocking issues", the same
  binary semantics `cv verify` already has. *(Alternative: 90/95 thresholds — rejected,
  an arbitrary band would silently let one P0 through.)*
- **Framing lint warns from `cv verify`, never gates** — the deterministic check cannot
  tell "learning" from "lying", only "this term has no experience-section backing".
  Escalating it to a block would fail honest CVs. *(Alternative: block — rejected,
  spec `[WONT]` AC-21.)*
- **Plan validity is computed by the caller and passed into `derive_next`**, keeping
  `derive_next` I/O-free as its docstring promises. *(Alternative: read the filesystem
  inside `derive_next` — rejected, breaks the pure-function test seam.)*
- **The filename is a convention, the `offer_id` is the contract**: `check_plan` reads the
  canonical `cv-<slug>-plan.md` first and then any other `cv-*-plan.md` in the same
  directory, judging every candidate by its frontmatter — the instructions tell agents
  `cv-<company>-plan.md`, which is not always the slug (`Fusuma (Spain)` → `fusuma-spain`).
  *(Alternative: fail on a non-slug name — rejected, the gate would punish agents for
  following the instructions literally.)*
- **`cv cover-letter` inherits the gate** — it calls `cmd_cv_generate` internally, so
  exempting it would leave a side door around the barrier. *(Alternative: force through
  from the cover-letter path — rejected, a bypassable gate is not a gate.)*
- **`plan_path_for` never creates directories** (`get_output_dir(create=False)`): a path
  lookup must not leave an empty `cv/` behind.
- **Retrocompat is structural, not a flag**: the `plan` state only exists on the branch
  where no CV file is linked, so offers that already generated a CV can never be sent
  back. *(Alternative: "grandfather" column or cutoff date — rejected, needs a migration
  and a date to argue about.)*
- **`cv gate` exit 1 on any missing artifact** — mirrors `doctor` (exit 1 = unhealthy),
  which the instructions already teach agents to gate on.

### Explicit technical assumptions

- The plan file lives in the same output directory as the CVs
  (`get_output_dir()`), named from the company slug — if an agent writes it elsewhere,
  the gate reports `missing`, which is the correct answer ("applyr did not receive a
  plan").
- `--record` on `cv fact-check` accepts the same 0-100 validation already used by
  reviews, so no new validation path is needed.
- Agents can produce a frontmatter `offer_id:` line — `cv generate` already writes one
  into the CV, so the convention is familiar.
- `evidence._SECTION_MAP` already maps the profile's experience heading, so "does this
  term have an experience-section claim" needs no new profile parser.
- The 5 role files are packaged data (`applyr/templates/agents/`); tests read them from
  the package, not from the working tree.

### Non-functional requirements

- Determinism: `validate_plan` and the framing lint are pure functions of file contents;
  same bytes in → same result out. No clock, no config, no network.
- Cost: `cv gate` and `next` read at most one plan file, one CV and the offer row;
  neither re-runs `verify` before the earlier states are satisfied (the existing rule in
  `derive_next` is preserved).
- Agent-native: `--json` on both new commands, stable codes on every refusal, all
  diagnostics on stderr.
- Colour/`NO_COLOR`/`--no-color` respected by the human rendering of `cv gate`.

### Edge cases / risks (technical mitigation)

- **Risk: `cv pdf` starts failing for existing users' old CVs** (no fact-check record).
  → Same escape as ADR-015's verify gate: `--force` renders and appends a dated note;
  documented in CHANGELOG and in the ADR's consequences. Offers whose CV predates the
  feature are *not* forced to re-review (AC-05 covers the plan only) — for them `cv gate`
  reports `fact_check` as `pending`, not `missing`, so a checklist never looks red for
  work that predates the feature.
  *Refinement:* `pending` vs `missing` is decided by whether a CV file exists —
  a step that has no input yet is `pending`; a step whose input exists but whose
  artifact does not, is `missing`.
- **Risk: two new `state` values leak into consumers.** → Additive only; the Visual UI
  owns `pipeline_stage` (ADR-013) and does not read `next --json` states. A test asserts
  the full state list so a future rename is caught.
- **Risk: an agent writes a trivial plan ("do not lie") to pass the gate.** → AC-03
  only guarantees ≥1 claim; the plan's *quality* is judged by the human at Step 6, not by
  applyr. Documented as a known limit in the ADR rather than pretending to solve it.
- **Risk: `derive_next` signature change breaks other call sites.** → It has exactly one
  caller (`cmd_next`); the test suite calls it directly with keyword args, so adding a
  keyword-only parameter is backwards compatible for tests written the old way.
- **Risk: framing lint false positives on a profile with no experience section.** →
  Return no warnings when there are no `experience` claims (AC edge case).
- **Risk: pylint pass, CI on 3.11.** → No 3.12-only syntax; build nested f-strings
  outside the literal (known CI trap).

### Test strategy

**Unit (`tests/test_gates.py`, tmp_path, no DB):**
- `validate_plan` for each of the five states, including Spanish heading aliases and a
  plan whose `offer_id` belongs to another offer.
- Framing lint: term only in projects → warning; term in experience → silence; term in
  skills only → warning naming `HABILIDADES TECNICAS`; no experience section → silence;
  project names/employers never flagged.
- `gate_checklist` status derivation for: fresh offer, offer mid-pipeline, offer with a
  CV (retro-compat → `not_applicable`/`pending`, never `missing` for `plan`).

**CLI (`tests/test_gates_cli.py`, sandboxed `APPLYR_HOME` + output dir):**
- AC-01/E1: `cv generate` without plan → exit 1, code `plan_required`, no file written.
- AC-02: with a valid plan → file written, exit 0.
- AC-04: `--force` → file written, note appended, second run shows it in `show`.
- AC-07/08: `cv gate` human and `--json` shapes; exit 1 with a missing artifact, exit 0
  when complete; AC-E3 unknown offer; AC-E4 no CV linked.
- AC-09/10/16: `next` returns `plan`, then `generate`, then `fact_check` at the right
  moments; AC-05 retro-compat on an offer with `cv_used`.
- AC-14/15: `cv pdf` refuses without a fresh passing fact check (`fact_check_required`),
  `--force` renders and notes it.
- AC-13: recorded verdict derives from the score, not from anything the agent supplies.
- AC-E5: CV without an embedded offer id behaves as today.

**Existing suites that must stay green:** `test_cv_verify*`, `test_cv_pdf`,
`test_cv_review_blind`, `test_cli_routing` (subcommand list), `test_agent_instructions`,
`test_errors` (code catalogue). Full `pytest` + `pylint --fail-under=7.0` locally, then
CI on 3.11/3.12/3.13.
