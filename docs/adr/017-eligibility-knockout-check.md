# ADR 017 — Eligibility / Knockout Check

**Status:** Accepted
**Date:** 2026-09-24
**Supersedes:** None (new decision)

> Numbering note: ADRs 012–014 live on the unmerged `feat/cc-visual-ui` branch (see
> ADR 015's note). This ADR continues the `main` sequence.

## Context

The compatibility score ([ADR 004](004-weighted-scoring.md)) is a weighted average. By
construction it cannot express a knockout: an offer that demands "C1 English, mandatory"
from a B1 candidate can still score 85% when the stack and projects match, and applyr
recommends APPLY. Knockout questions (minimum years, mandatory language, on-site city,
driving license) are the most common real reason an application is rejected before a
human reads it, so the recommendation most likely to waste an application is exactly the
one the score is least able to catch.

Adding the requirement as another weighted topic does not fix this: a 0 on one topic
out of seven is diluted by the others, so a hard requirement becomes a soft penalty.

## Decision

Eligibility is a **gate next to the score**, not part of it.

1. **The agent extracts, applyr judges** — the same split as `cv verify`
   ([ADR 011](011-evidence-based-cv-engine.md)). `add` accepts an optional `eligibility`
   block holding only the offer's *mandatory* requirements (`min_years`, `languages`,
   `city`, `driving_license`). applyr compares them deterministically with a new
   `## ELIGIBILITY` section of `cv-master.md` (years, accepted cities, relocation, driving
   license) and with the existing languages table. No LLM call ([ADR 003](003-no-llm-calls.md)).
2. **Four outcomes per item**: `pass`, `warn`, `block`, `unknown`. A shortfall of at most
   one year, or exactly one CEFR level, is `warn` — recruiters are routinely flexible
   there. Missing profile data is `unknown`, and `unknown` never blocks: applyr prefers
   omission over guessing.
3. **A block forces `low_match`, the score is untouched.** `recommendation_for()` takes
   the stored eligibility result and returns `low_match` when any item blocks. The
   recommendation keeps its three values, so no agent, UI or `applyr next` branch breaks;
   the reason travels in a separate `eligibility_block` field. `compatibility_pct` never
   changes, so calibration and trends still measure the score itself.
4. **Stored, re-evaluable.** Schema v15 adds `eligibility_requirements` and
   `eligibility_result` (nullable TEXT, additive). `rescore` re-evaluates against the
   current profile, so filling the section in later fixes existing offers.

## Consequences

**Positive**
- A high score can no longer hide a hard requirement the candidate fails.
- Deterministic and testable: same requirements + same profile = same result.
- Backward compatible: offers and callers without eligibility behave as before.

**Negative**
- Every place that derives a recommendation must pass the stored result; a missed call
  site silently shows the score-only recommendation. Mitigated by a test that reads a
  blocked offer through every listing command.
- The quality of the gate depends on the agent putting only mandatory requirements in the
  block. Nice-to-haves put there would over-block; the `warn` tolerance softens near
  misses but does not remove the risk.
- City matching is literal (case- and accent-insensitive). "Alcobendas" does not match
  "Madrid" unless the user lists it.
- Schema v15 on `main` widens the pending v14 collision with `feat/cc-visual-ui`; that
  branch must renumber its migration before it merges.

**Neutral**
- The `experience` and `english` topics keep scoring fit; eligibility only gates.

## Alternatives considered

- **Seventh weighted topic `eligibility`** — rejected: the weighted average dilutes it,
  which is the problem being solved.
- **Agent decides pass/fail per item** — rejected: moves the guardrail into the LLM,
  unverifiable; contradicts the ADR 011 split.
- **New `ineligible` recommendation value** — rejected: breaks every consumer that
  expects `apply` / `maybe` / `low_match` for a distinction a reason field already carries.
- **Instructions only** — rejected: nothing enforces it.
- **Work permit / salary items** — deferred, not rejected; out of scope for v1.
