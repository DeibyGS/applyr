# ADR 009 — Weight versioning, rescore, and rebalanced defaults

**Status:** Accepted
**Supersedes:** [ADR 004](004-weighted-scoring.md) — specifically its "forbidden change"
constraint on `DEFAULT_WEIGHTS`. The weighted-mean formula and per-user configurability
that ADR 004 established are unchanged and not reopened here.
**Date:** 2026-08-15

## Context

[ADR 004](004-weighted-scoring.md) forbids changing `DEFAULT_WEIGHTS` or adding a scoring
topic, because `compatibility_pct` is stored with no record of which weights produced it.
Changing the defaults would silently make every new score incomparable with every score
already sitting in a user's `jobs.db`, with no way to tell the two apart.

Two things pushed on that constraint at the same time:

1. An external review of applyr, followed by 2025-26 recruiter-survey research, made the
   case that the current defaults (`education` and `experience` weighted equally, at 15
   each) don't reflect how hiring actually happens for most roles — technical fit and
   experience should carry more signal, education less.
2. `applyr stats`'s score-calibration feature (`_score_calibration()`, shipped in
   v1.6.0/PR #60) already averages `compatibility_pct` across every applied offer into
   apply/maybe/low bands, with no regard for what weights produced each one. This is the
   exact failure mode ADR 004 warned about — already live, not hypothetical.

The project owner wants the default weights changed for real (not just in his own
`applyr.toml`), which ADR 004 explicitly forbids as written. Overriding an accepted ADR
requires a new ADR, not a silent edit — this is that ADR.

## Decision

Record which weights produced each score, so defaults (and any future re-weighting) can
change without breaking comparability:

1. **`offers.weights_used`** (new nullable `TEXT` column, schema v9): a JSON snapshot of
   the effective `config["weights"]` dict at the moment `compatibility_pct` is computed
   from `topics` via `scoring.calculate_score()`. `NULL` when no weights were involved
   (an explicit `compatibility_pct` override on `add`, or empty `topics`) and for every
   offer scored before this migration — never backfilled or guessed.
2. **`applyr rescore <id>`**: recomputes `compatibility_pct` for one offer from its
   already-judged `offer_topics` (score/detail/confidence — fit is never re-evaluated)
   against the *current* weights, and updates `weights_used` to match. This is what makes
   a weight change (default or personal) actually reach an offer that already exists.
3. **`_score_calibration()`** (`applyr stats`) now excludes offers with `weights_used
   IS NULL` from its apply/maybe/low bands, and reports how many were excluded — fixing
   the live bug described above instead of only preventing new instances of it.
4. **`DEFAULT_WEIGHTS` rebalanced** (`applyr/constants.py`):

   | Topic | Old | New |
   |-------|----:|----:|
   | `tech_stack` | 30 | 35 |
   | `experience` | 15 | 35 |
   | `projects` | 20 | 15 |
   | `education` | 15 | 5 |
   | `english` | 10 | 5 |
   | `cultural_fit` | 10 | 5 |

   No new topic: seniority-fit was considered as a 7th topic but folded into
   `experience`, whose rubric already scores "Wrong seniority/industry" at its midpoint
   anchor — adding a topic is a separate breaking change ADR 004 already calls out
   (normalization redistributes every topic's share), and the project owner chose not to
   take it on here.

## Consequences

### Positive

- `DEFAULT_WEIGHTS` (and any future re-weighting, by this project or a user) can change
  going forward without repeating this problem — every score now says what produced it.
- Fixes a real, already-shipped bug in `stats` score calibration, not just a theoretical
  future one.
- `rescore` gives users an explicit, auditable way to bring an old offer's score forward
  under new weights, rather than the score silently drifting in meaning.

### Negative

- One more column, one more thing every score-producing code path must remember to set
  correctly (`add`'s three branches, `rescore`) — audited explicitly in the implementation
  spec (`specs/weight-versioning-rebalance/spec.md`).
- `rescore` is easy to misread as "re-evaluate whether I'm a fit for this offer." It is
  not — it only re-applies the weighting formula to scores that were already judged. This
  must be explicit in the command's own output and in `AGENT_INSTRUCTIONS.md`.

### Neutral

- Legacy rows (`weights_used = NULL`) are permanently unlabeled — there is no reliable
  way to know what a user's `applyr.toml` looked like in the past, so no attempt is made
  to guess. They simply drop out of calibration/aggregate views and are marked "unknown"
  wherever shown individually (`show`, `compare`).
- The rebalanced defaults are, like the original ones, a calibrated starting point
  informed by general hiring-practice research — not a validated model fit to this
  project's own outcome data. The same caveat ADR 004 placed on its own defaults applies
  here. Users who disagree still override via `[weights]` in `applyr.toml`, unchanged.

## Alternatives considered

**Status quo — leave ADR 004's prohibition in place.** Rejected: does not address that
the current defaults don't reflect current hiring-research consensus, and does not fix
the live `_score_calibration` bug either.

**Personal-config-only change (no code change).** Rejected as the sole action: respects
ADR 004 with zero risk, and remains available to anyone who wants a different split than
this ADR's new defaults — but does not change what a new `applyr init` ships, which was
the actual ask.

**Backfill `weights_used` for existing rows, assuming they used the `DEFAULT_WEIGHTS` of
their time.** Rejected: a user may have already customized `[weights]` before this
migration ships, and there is no record of when. Backfilling would manufacture exactly
the kind of false-precision data ADR 004 already warned does not exist.

**Weight versioning without a rebalance (fix the mechanism, leave `DEFAULT_WEIGHTS`
alone for now).** Considered but not chosen as the final scope: the mechanism exists
specifically to unblock the rebalance the project owner wants now; shipping the plumbing
without the change it exists to enable was judged not worth a second migration later for
the same feature.

Related: [ADR 004](004-weighted-scoring.md), [`contracts.md`](../contracts.md),
[`specs/weight-versioning-rebalance/spec.md`](../../specs/weight-versioning-rebalance/spec.md).
