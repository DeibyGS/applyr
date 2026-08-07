# ADR 004 — Configurable weighted scoring

**Status:** Accepted
**Date:** 2026-08-07 (recorded retroactively; decision made at project start)

## Context

Given [ADR 003](003-no-llm-calls.md), the agent judges each dimension of fit
and applyr combines those judgments into one number. That number drives
`threshold` recommendations, `pipeline --min-score` filtering and `compare`.

Two questions had to be answered: how the dimensions combine, and who decides
their relative importance.

Not all dimensions matter equally, and they do not matter equally to everyone.
A backend role weighs the tech stack heavily; a role at a company with a strong
culture-fit process weighs that instead.

## Decision

A weighted arithmetic mean over six topics, in `applyr/scoring.py`:

```python
score = round(sum(topic_score * weight) / sum(weight))
```

Weights live in `~/.applyr/applyr.toml` under `[weights]`, written as relative
integers and normalized to sum `1.0` at load time. Defaults are
`DEFAULT_WEIGHTS` in `applyr/constants.py`:

| Topic | Default |
|-------|---------|
| `tech_stack` | 30 |
| `projects` | 20 |
| `education` | 15 |
| `experience` | 15 |
| `english` | 10 |
| `cultural_fit` | 10 |

Topics scoring outside `[0, 100]` are skipped rather than clamped, and an
unknown topic falls back to `DEFAULT_TOPIC_WEIGHT` (`0.10`).

## Consequences

### Positive

- **Explainable.** The user can hand-check any score. There is no model, no
  hidden state, no non-linearity to reason about.
- **Deterministic**, which is what makes `tests/test_scoring.py` possible
  without mocks.
- **Adjustable without code.** Editing the TOML changes the ranking.
- **Integer weights are forgiving.** Writing `30, 20, 15, 15, 10, 10` cannot
  produce an invalid config, because normalization happens at load. Users
  never have to make fractions sum to 1.0.
- **Partial data degrades gracefully.** An offer scored on three topics still
  produces a meaningful number, since only supplied weights enter the divisor.

### Negative

- **Linear and independent by assumption.** The formula cannot express "this
  role is disqualifying without Python regardless of everything else". A
  weighted mean has no veto.
- **Scores are only comparable within one config.** Changing weights makes new
  scores incomparable with historical ones, with no record of which weights
  produced a stored `compatibility_pct`. This is why `DEFAULT_WEIGHTS` is a
  forbidden change.
- **Garbage in, garbage out.** The formula cannot detect an agent that scores
  generously.

### Neutral

- Adding a topic changes every existing user's scores, since normalization
  redistributes shares. Treat it as a breaking change.

## Alternatives considered

**Unweighted average.** Rejected. It makes `english` as decisive as
`tech_stack`, which does not match how offers are actually evaluated.

**A single 0–100 score from the agent, stored as-is.** Rejected. It is simpler
but opaque: nothing explains *why* an offer scored 72, so `gaps` and `plan`
have no per-dimension data to work from. The topic breakdown is what makes
those commands possible.

**Learned weights from outcomes.** Rejected for now. It needs a volume of
labeled results a single job search does not produce, and it would reintroduce
non-determinism and a model dependency.

## Notes on the default weights

The defaults come partly from the author's experience of what recruiters
actually respond to and partly from iteration — they were adjusted while using
the tool. **They are a calibrated starting point, not a validated model.** No
outcome data has been used to fit them.

The shape reflects the author's profile: `projects` (20) outweighs both
`experience` and `education` (15 each), which is how a student or junior
candidate is realistically assessed — the portfolio carries more signal than a
short employment history. A senior candidate would likely invert that.

This is precisely why weights are configurable rather than constant, and why
changing the defaults for everyone is a forbidden change.

Related: [ADR 003](003-no-llm-calls.md), [`contracts.md`](../contracts.md).
