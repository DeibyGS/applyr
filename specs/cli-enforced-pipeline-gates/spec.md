# Spec: CLI-Enforced Pipeline Gates

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context
- Project constitution: no `docs/constitution.md` yet — `AGENTS.md` plus ADRs act as
  the constitution. Binding: [ADR 003](../../docs/adr/003-no-llm-calls.md) (no LLM calls),
  [ADR 006](../../docs/adr/006-errors-to-stderr.md) / [ADR 007](../../docs/adr/007-structured-json-errors.md)
  (errors on stderr, structured error codes), [ADR 011](../../docs/adr/011-evidence-based-cv-engine.md)
  (deterministic `cv verify`).
- Governing decision: [ADR 015](../../docs/adr/015-cli-enforced-pipeline-gates.md).
- Engram: `adr:applyr:next-state-machine-gates` (2026-09-24).
- `pipeline_stage` is owned by `feat/cc-visual-ui` (ADR 013) — not touched here.
- Corrected assumptions (confirmed by Deiby, 2026-09-24):
  - A CV's offer is identified by the offer id embedded in the file, the same way
    `cv verify` does it — not by `cv_used`.
  - `decide` and `review_blind` are indistinguishable from stored data, so they are one
    state: `decide`, which requires the user's confirmation.
  - `cv_review` verdicts use the fixed 80/60 bands `ats-check` already uses;
    `review_blind` verdicts use the configured `threshold_apply` / `threshold_maybe`.
  - A manual `compatibility_pct` without `score_source: "manual"` warns even when
    topics are also present, since the manual value overrides them.

### What does it do?
- `cv pdf` only renders a CV that currently passes `cv verify`. Bypassing that takes an
  explicit `--force`, which leaves a dated trace on the offer.
- The agent can record the score of the review prompts it executes
  (`cv review-blind --record`, `cv review --record`), so applyr knows those steps
  happened.
- `applyr next <id>` tells the agent the next step for an offer and the exact command
  to run, derived from what applyr already knows. It changes nothing.
- A manually supplied compatibility score has to say so (`score_source: "manual"`).
  For now, omitting it only warns.

### Boundaries
**Always do:** derive `next` state on every call; reuse the same verify logic for
`cv verify` and `cv pdf`; derive verdicts from scores inside applyr.
**Ask first:** any schema migration; any change to `pipeline_stage`; turning the
`score_source` warning into an error.
**Never do:** call an LLM; let the agent supply a verdict; rewrite or delete
`cv_iteration_history` entries.

### Acceptance criteria

#### PR 1 — `cv pdf` gate and `score_source`
- `[MUST]` AC-01: WHEN `cv pdf <file>` is run on a CV whose verify check fails
  (an unsupported claim or a leftover placeholder) THE system SHALL exit 1 with error
  code `verify_required`, list the failing claims, and create no PDF.
- `[MUST]` AC-02: WHEN `cv pdf <file>` is run on a CV that passes verify THE system SHALL
  render the PDF exactly as before.
- `[MUST]` AC-03: WHEN `cv pdf <file> --force` is run on a CV that fails verify THE system
  SHALL render the PDF, print a warning on stderr, and append
  `[YYYY-MM-DD] cv pdf --force: verify skipped (<N> unsupported claim(s))` to the linked
  offer's `notes`, keeping any existing notes.
- `[MUST]` AC-04: `cv pdf` SHALL NOT write `cv_evidence_used`. Only `cv verify` does.
- `[MUST]` AC-05: WHEN `add` receives `compatibility_pct` without
  `"score_source": "manual"` THE system SHALL insert the offer and print a deprecation
  warning on stderr saying this becomes an error in the next major version.
- `[MUST]` AC-06: WHEN `add` receives `compatibility_pct` with `"score_source": "manual"`
  THE system SHALL insert it with no warning.
- `[MUST]` AC-07: `examples/` and `llms.txt` SHALL NOT show a `compatibility_pct` without
  `score_source: "manual"`.
- `[MUST]` AC-E1: Given a CV file with no embedded offer id, When `cv pdf` runs without
  `--force`, Then it exits 1 with `verify_required` and a message naming `--force`.
- `[MUST]` AC-E2: Given a CV file with no embedded offer id, When `cv pdf --force` runs,
  Then it renders and warns, and no offer is modified.
- `[MUST]` AC-E3: Given `score_source` set to any value other than `"manual"`, When `add`
  runs, Then it exits with `invalid_value` naming `score_source` and inserts nothing.

#### PR 2 — `--record` and `applyr next`
- `[MUST]` AC-08: WHEN `cv review-blind <id> --record <score>` runs THE system SHALL append
  `{"step": "review_blind", "score", "verdict", "at"}` to the offer's
  `cv_iteration_history`. `verdict` is STRONG_MATCH, CLOSE_MATCH or NO_MATCH, following
  the configured thresholds.
- `[MUST]` AC-09: WHEN `cv review <file> --record <score>` runs THE system SHALL append a
  `cv_review` entry (verdict READY TO SEND at 80 or more, NEEDS MINOR EDITS at 60–79,
  NEEDS MAJOR REVISION below 60) to the offer embedded in the file, and increment
  `cv_iteration`.
- `[MUST]` AC-10: Existing `cv_iteration_history` entries SHALL be preserved on every
  append.
- `[MUST]` AC-11: `applyr next <id> [--json]` SHALL return one of `score`, `decide`,
  `generate`, `cv_review`, `verify`, `pdf`, `apply`, `done`, with the exact command to run
  and a one-line reason, and SHALL NOT modify the database or any file.
- `[MUST]` AC-12: Given an offer with neither topics nor a manual score, `next` returns
  `score`.
- `[MUST]` AC-13: Given a scored `pending` offer with no `review_blind` record, `next`
  returns `decide` with `needs_user_confirmation: true` and the command
  `applyr cv review-blind <id> --record <score>`. For LOW MATCH it also suggests
  discarding.
- `[MUST]` AC-14: Given a `review_blind` record and no CV file for the offer, `next`
  returns `generate`, whatever the recruiter verdict was.
- `[MUST]` AC-15: Given a CV file with no `cv_review` record newer than the file's last
  modification, `next` returns `cv_review`.
- `[MUST]` AC-16: Given the newest `cv_review` record is newer than the CV file and is not
  READY TO SEND, and `cv_iteration` < 3, `next` returns `cv_review`, telling the agent to
  edit the file before reviewing again. With `cv_iteration` ≥ 3 it moves on to `verify`
  with a warning.
- `[MUST]` AC-17: Given the review is done and verify fails, `next` returns `verify`,
  listing the failing claims.
- `[MUST]` AC-18: Given verify passes and there is no PDF newer than the CV file, `next`
  returns `pdf`.
- `[MUST]` AC-19: Given a PDF newer than the CV and the offer not yet `applied`, `next`
  returns `apply` with `applyr update <id> applied --canal <channel>`.
- `[MUST]` AC-20: Given status `applied`, `waiting`, `in_process`, `offer`, `rejected` or
  `discarded`, `next` returns `done`.
- `[MUST]` AC-E4: Given `--record` with a value that is not an integer from 0 to 100, Then
  exit `invalid_value` and record nothing.
- `[MUST]` AC-E5: Given `cv review <file> --record` on a file with no embedded offer id,
  Then exit `no_offer_id` and record nothing.
- `[MUST]` AC-E6: Given `next` on an unknown id, Then exit `not_found`.
- `[MUST]` AC-E7: Given `cv_iteration_history` containing invalid JSON, When `next` or
  `--record` runs, Then it reports the corruption as a structured error instead of
  crashing or silently overwriting the history.
- `[SHOULD]` AC-21: `AGENT_INSTRUCTIONS.md` documents `applyr next`, `--record` and the
  `cv pdf` gate, and points agents to `next` as the way to find their place in the
  pipeline.

### Edge cases
- The CV file recorded for the offer was deleted → `next` returns `generate`.
- The CV was edited after a READY review → a new review is required (AC-15).
- A PDF older than the latest CV edit is treated as missing (AC-18).
- A legacy `.html` CV goes through the same gate as `.md`.
- The linked offer was deleted between `cv generate` and `cv pdf --force` → render,
  warn, no note.

### Out of scope
- `[WONT]` Schema migrations or new columns.
- `[WONT]` Reading or writing `pipeline_stage`.
- `[WONT]` Turning the `score_source` warning into an error (next major version).
- `[WONT]` Modeling the Step 6 "generate?" user confirmation in `next`.
- `[WONT]` MCP server, compact instructions, `applyr guide` (audit Phase 4).
