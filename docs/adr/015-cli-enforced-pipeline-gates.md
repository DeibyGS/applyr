# ADR 015 — CLI-Enforced Pipeline: `applyr next` and the `cv pdf` Verify Gate

**Status:** Accepted
**Date:** 2026-09-24
**Supersedes:** None (new decision)

> Numbering note: ADRs 012–014 live on the unmerged `feat/cc-visual-ui` branch.
> This ADR takes 015 on `main` so the two sequences never collide when that branch
> eventually merges.

## Context

Almost every quality control in the end-user workflow is enforced by instructing the
calling agent, not by applyr itself. `AGENT_INSTRUCTIONS.md` says so in its own words
about the `cv review` loop: "nothing forces the second call". Concretely:

1. **`cv pdf` renders anything.** A CV that `cv verify` returned BLOCKED on — or never
   ran `verify` on at all — still becomes a PDF the user can send. The one
   deterministic anti-hallucination gate ([ADR 011](011-evidence-based-cv-engine.md))
   is skippable by simply not calling it.
2. **The pipeline order lives only in ~5k tokens of instructions.** Score →
   review-blind → generate → review → verify → pdf is prose. A small model, or any
   agent that loses the instructions to context compaction, has no way to ask applyr
   "what do I do next with offer 42?".
3. **LLM-executed steps leave no trace.** `cv review-blind` and `cv review` print a
   prompt the agent executes itself ([ADR 003](003-no-llm-calls.md)). applyr never
   learns whether that happened or what it scored, so it cannot tell a finished
   review loop from a skipped one.
4. **A manual `compatibility_pct` bypasses scoring silently.** `add` accepts a bare
   number with no topics; `examples/` and `llms.txt` even teach it. The resulting
   offer is indistinguishable from a rubric-scored one.

The schema already carries `cv_iteration` / `cv_iteration_history` (added for
iterative feedback loops, never written) and `pipeline_stage` (owned by
`feat/cc-visual-ui` per ADR 013, see the ownership note in `db.py`).

## Decision

The CLI becomes the barrier; the prompt becomes a hint. Four parts, no new schema
migration.

### 1. `cv pdf` refuses unverified CVs

`cv pdf <file>` re-runs the same deterministic checks as `cv verify` on the file as it
is on disk at call time, plus a leftover-`[PLACEHOLDER]` check. Any failure exits 1
with the structured error code `verify_required` ([ADR 007](007-structured-json-errors.md))
and lists what failed. Nothing is rendered.

Re-running instead of trusting a stored result is deliberate: `verify` is pure,
local, and fast, so a stored "passed" flag would only add a way to go stale (the file
edited after verification) without saving meaningful time.

`cv pdf --force` still renders, prints a stderr warning, and appends a dated line to
the linked offer's `notes` (`[YYYY-MM-DD] cv pdf --force: verify skipped (<reason>)`),
so the bypass is visible in `show`. The offer is found through the offer id
`cv generate` embeds in the file — the same link `cv verify` uses. A file with no
embedded id cannot be verified, so without `--force` it is refused like any other
failure; with `--force` it gets the warning, just no note.

### 2. `--record` for LLM-executed steps

`cv review-blind <id> --record <score>` and `cv review <file> --record <score>`
persist the result of a prompt the agent has just executed. Records are appended to
`cv_iteration_history` as JSON entries:

```json
{"step": "review_blind" | "cv_review", "score": 0-100, "verdict": "<derived>", "at": "<ISO-8601>"}
```

`verdict` is derived by applyr from the configured thresholds, never supplied by the
agent. `cv_iteration` counts `cv_review` records. The history is append-only; nothing
rewrites or deletes entries.

### 3. `applyr next <id> [--json]`

A read-only state machine that returns the next step for one offer and the exact
command to run. It **derives** state from existing data on every call and writes
nothing:

| State | Derived from |
|-------|--------------|
| `score` | no topics and no `score_source: manual` |
| `decide` | scored, status `pending`, no `review_blind` record — returns `needs_user_confirmation: true` and the `cv review-blind --record` command |
| `generate` | `review_blind` recorded, and no `cv_used` or the recorded CV file is missing |
| `cv_review` | no `cv_review` record newer than the CV file's mtime, or last verdict below READY TO SEND with `cv_iteration` < 3 |
| `verify` | live `verify` on the CV file does not pass |
| `pdf` | no PDF next to the CV file, or PDF older than the CV |
| `apply` | PDF exists, status not yet `applied` |
| `done` | status `applied` or later, or `discarded` |

The user's apply/skip decision (Step 4) leaves no trace in the data, so it cannot
be told apart from "blind review not run yet". The two are one state, `decide`, which
is the point where the agent must stop for the user.

`next` does not read or write `pipeline_stage`: that column belongs to the Visual UI
branch, and a second writer would make both unreliable.

### 4. `score_source` for manual scores

`add` with a `compatibility_pct` and no topics must carry `"score_source": "manual"`.
Without it, this minor release prints a deprecation warning and still inserts; the
next major release rejects it with `invalid_value`. `examples/` and `llms.txt` stop
teaching the shortcut. No column is added: `score_source` is validated at the
boundary, and "manual" is already derivable (score present, no topics).

## Consequences

**Positive**
- The one deterministic anti-hallucination check can no longer be skipped by
  omission — only by an explicit, recorded `--force`.
- `applyr next --json` lets a small model run the whole pipeline from one command's
  output, without the full instructions in context. This is the prerequisite for the
  compact instructions planned next (audit Phase 4).
- No migration: avoids adding another schema version while `main` and
  `feat/cc-visual-ui` are already both at v14 with different migrations.

**Negative**
- **Behavior change for `cv pdf`**: scripts or agents that render unverified CVs now
  get exit 1. Mitigated by a message that names `cv verify` and `--force`.
- `--record` is still agent-honesty-based: applyr cannot prove the agent executed the
  prompt it records a score for. It turns a silent skip into a visible absence in
  `next`, which is the achievable improvement under ADR 003.
- `cv_iteration_history` is JSON in a TEXT column — not queryable with plain SQL.
  Acceptable at one offer's scale; revisit if analytics ever need it.

**Neutral**
- `next` duplicates no logic: it calls the same verify function `cv pdf` does.

## Alternatives considered

- **Store a verify hash on the offer and compare in `cv pdf`.** Needs a migration and
  can go stale; rejected in favor of re-running the pure check.
- **Sidecar `.verified` file next to the CV.** No migration, but clutters the output
  folder and is trivially forgeable by any `touch`.
- **`next` persists its state in `pipeline_stage`.** Rejected: two writers to a
  column owned by another branch's design (ADR 013).
- **Advisory-only `next` (no `--record`).** Simpler, but the two LLM steps would be
  permanently invisible, so `next` could never move past them with confidence.
- **Reject manual `compatibility_pct` immediately.** Stricter, but a breaking change
  in a minor release for anyone using the documented shortcut.
