# ADR 018 — Step Handoff Gates: artifacts, not assurances

**Status:** Accepted
**Date:** 2026-10-05
**Supersedes:** None (extends [ADR 015](015-cli-enforced-pipeline-gates.md))

## Context

ADR 015 moved the CV pipeline's quality controls out of prose and into the CLI: `cv pdf`
refuses an unverified CV, `--record` captures the two LLM-executed steps, and `applyr
next` derives the next step from stored data. Its own conclusion still holds though:
*"the pipeline order lives only in ~5k tokens of instructions"* and `next` enumerates
`score → decide → generate → cv_review → verify → pdf → apply`.

Two steps of the workflow are invisible to that machine:

1. **Step 5.7, the CV Architect.** `AGENT_INSTRUCTIONS.md` tells the agent to write a
   tailoring strategy to `cv-<company>-plan.md` including *"Forbidden claims (what the CV
   must NOT say)"*, and then says *"Do NOT fill the CV yourself. You plan. The Writer
   executes."* Nothing in applyr reads that file. It is not a state in `next`, it is not
   checked by `cv generate`, and no test asserts it exists. Skipping it costs nothing.
2. **The Fact Checker role.** The role index maps it to *"Step 6b"*, but Step 6b
   executes the deterministic `cv verify` instead. The adversarial prompt — the only
   place in the product that names `incorrect_seniority: Level inflated from actual` as a
   blocker — is reachable only by typing `applyr role fact-checker` by hand.

**What this cost, concretely (2026-10-05, offer #299).** The generated CV's professional
summary read *"…que construye sistemas con LLMs y Retrieval Augmented Generation (RAG)
usando Python y LangChain"*. The candidate's RAG and LangChain work is one exercise of a
master's degree still in progress — a fact his own `cv-master.md` states under
`NOTAS PARA ADAPTAR ESTE CV`: *"formación/práctica en curso, no experiencia profesional
— presentarlo como tal, sin exagerar el nivel de seniority."*

Every check passed: `cv verify` 63/63, `cv review` 86 (READY TO SEND), `cv ats-check`
100/100, `cv keywords` 90%, PDF rendered. The agent had skipped Step 5.7, and no layer
of the system could notice, because:

- `cv verify` is a **lexical** gate — `RAG`, `LangChain` and `LangGraph` really are in the
  profile (skills, a project, a course), so the claims are "grounded".
- `cv review` scores keyword match, ATS, evidence, clarity and length. It has **no honesty
  criterion**, and keyword matching actively rewards the inflated phrasing.
- The three defence layers applyr designed for this (Architect `forbidden_claims`,
  Writer's *"Rewording must not inflate"*, Fact Checker's `incorrect_seniority`) are all
  prose addressed to the LLM. Two were skipped outright; the third is not invoked by any
  step.

This is the failure mode ADR 015 named but only half-closed: it made the *existing*
artifacts enforceable, while two workflow artifacts remained suggestions.

## Decision

The CLI becomes the barrier for the artifacts too — **and an artifact must be readable by
a tool, never a claim that someone worked.** Four parts, still no schema migration.

### 1. The Architect's plan is a required input to generation

`cv generate <id>` refuses (exit 1, `plan_required`) when no valid plan exists for that
offer, and refuses with `plan_invalid` when the file exists but has no `offer_id` match or
declares zero forbidden claims. `cv generate --force` proceeds and appends a dated line to
the offer's notes, exactly like `cv pdf --force`.

A plan with an empty forbidden-claims list is treated as missing: the check must not be
satisfiable by creating a file named like the artifact.

### 2. Two new states: `plan` and `fact_check`

`applyr next` gains `plan` (between `decide` and `generate`) and `fact_check` (after a
ready-to-send `cv_review`, before `verify`). Both are derived at read time from the
filesystem and `cv_iteration_history`, as every other state is.

`plan` only exists on the branch where no CV file is linked to the offer, so offers that
already generated a CV can never be sent back to an earlier step — retro-compatibility is
structural, not a date cutoff.

### 3. `cv gate <id>` — the whole checklist in one read-only command

`cv gate` reports every pipeline step with a status (`ok` / `missing` / `invalid` /
`pending` / `not_applicable`), the current `state`, and the command that fixes the first
problem. Exit 1 when anything required is missing, mirroring `doctor`'s "exit 1 = unhealthy"
contract so agents can gate on it. `--json` returns the same information; those keys are
a public contract from the day it ships.

`cv gate` derives its answer by calling the same `derive_next` that `next` uses, then
layers artifact detail on top — the two commands cannot disagree by construction.

### 4. The Fact Checker returns, as a recorded step with a derived verdict

`cv fact-check <file>` prints the role prompt **from `templates/agents/fact_checker.md`**
(the role file stays the single source — a second copy embedded in `cv.py` is how it got
orphaned) plus a recording appendix. `--record <score>` appends
`{"step": "fact_check", "score", "verdict", "at"}` to `cv_iteration_history`; `verdict` is
derived from `FACT_CHECK_PASS_MIN`, never supplied by the agent. `cv pdf` refuses to
render a CV with no fresh passing fact check (`fact_check_required`), `--force` renders and
notes the bypass.

The density the agent records is defined by the role prompt as "major claims with no open
P0/P1 issue", so PASS means *zero blocking issues* — the same binary semantics
`cv verify` already has.

### 5. A deterministic framing warning (advisory)

`cv verify` prints a `Framing` warning when the CV's professional summary names a
technology that exists in the profile but **never under its experience section** (and has
a non-empty `framing` array in `--json`). It never changes the verdict, the exit code, or
whether a PDF can be produced.

It is a nudge for the writer, not a judge: applyr can prove "your profile only has this
under PROYECTOS", not "you are lying".

## Consequences

**Positive**
- The specific bug of #299 becomes impossible to reproduce silently: no plan, no CV.
- The adversarial seniority check is wired back into the workflow, and a skipped one is
  visible in `next` and `cv gate` instead of being invisible.
- Writers get a deterministic signal for the exact reframe ("project/learning", not
  "experience") that no keyword-based check would ever give them.
- Zero migration: state stays derived, per ADR 015's rationale about the `main` /
  `feat/cc-visual-ui` schema collision.

**Negative**
- **Behaviour change for `cv generate`**: agents that never wrote a plan now get exit 1.
  Mitigated by a message naming the command that produces the plan, and by `--force`.
- **Behaviour change for `cv pdf`**: a CV whose review passed but that was never
  fact-checked is refused. Same mitigation as ADR 015's verify gate (`--force` + note).
- **Still agent-honesty for the LLM steps**: `--record` cannot prove a prompt was
  executed. The gate converts a silent skip into a visible absence — the achievable
  improvement under [ADR 003](003-no-llm-calls.md).
- **The plan gate checks existence, not quality.** A perfunctory plan passes; judging its
  substance stays a human Step 6 responsibility. Documented here so nobody mistakes the
  gate for a guarantee.
- Two new `state` values enter the `next --json` vocabulary. Additive; consumers that
  switch exhaustively on it must handle them.

## Alternatives considered

- **A checklist command only (`cv gate`), no enforcement.** The agent still has to
  remember to call it — this is the shape of the current failure, dressed as a tool.
- **Store a `steps_done` column.** Needs a migration, and can only go stale; rejected on
  the same grounds ADR 015 rejected a stored verify hash.
- **Self-reported handoff marks** ("step N done ✅ written by the agent at the end of its
  turn"). Rejected outright: a mark that the producing agent writes is exactly the claim
  a skipping agent would also write. Only artifacts another process can read count.
- **Make the framing lint a hard block.** Cannot distinguish "learned in a master's" from
  "did at work"; would block honest CVs. Advisory only.
- **Inline the fact-check prompt in `cv.py`** like `cv review` does. Rejected: duplicate
  prompts drift, and the drift already orphaned this role once.
- **Thresholds of 90/95 for the fact check.** Rejected: an arbitrary band lets a single
  P0 through, and nothing in the role output distinguishes "95% of claims fine" from
  "one P0 and twenty trivial claims".
