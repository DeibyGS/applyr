# ADR 003 — No LLM API calls

**Status:** Accepted
**Date:** 2026-08-07 (recorded retroactively; decision made at project start)

## Context

Applyr's core operation is judging how well a candidate matches a job offer.
That judgment is exactly what a language model is good at, so the obvious
design is for applyr to call one.

But applyr's users are already running an AI coding agent — Claude Code,
Codex, Cursor, Gemini CLI. That agent has the job posting in its context, has
already read the user's CV, and is the thing invoking applyr in the first
place. Adding a second model call inside applyr would mean paying a model to
re-derive what the model on the outside already knows.

## Decision

Applyr contains no LLM API calls, no API keys, and no network layer at all.
Verifiable:

```bash
grep -rn "openai\|anthropic\|requests\|urllib\|httpx\|socket" applyr/ --include="*.py"
# no matches
```

The reasoning happens in the agent. Applyr stores the result and computes
deterministic aggregates over it. The interface between the two is
`applyr/templates/AGENT_INSTRUCTIONS.md`, which tells the agent how to produce
scores applyr will accept, plus `--json` output for reading data back.

## Consequences

### Positive

- **No API cost.** Not to the author, not to the user. Applyr is free to run
  forever, which matters for a tool used daily during a job search.
- **No key management.** Nothing to store, rotate, leak, or document.
- **Nothing leaves the machine**, preserving [ADR 001](001-local-first.md).
  Sending offers and CV content to a third-party API would have undone it.
- **Model-agnostic and future-proof.** Applyr does not care which agent calls
  it, or which model that agent runs. Model deprecations cannot break it.
- **Deterministic and testable.** The same inputs always produce the same
  score, so the 54 tests need no mocked API responses.
- **Instant.** No network round trip in any command.

### Negative

- Applyr is not useful standalone for scoring. Without an agent, the user must
  supply topic scores by hand.
- The quality of the data depends entirely on the agent's judgment, and applyr
  cannot validate that a `tech_stack` score of 80 is reasonable — only that it
  is an integer in `[0, 100]`.
- The contract with agents is a Markdown file, not a typed API. It can be
  misread.

### Neutral

- This makes applyr a *component* rather than a product. That framing is
  intentional; see [`docs/mental-model.md`](../mental-model.md).

## Alternatives considered

**Built-in LLM calls with a user-supplied key.** Rejected on cost and privacy.
It would charge the user twice for one judgment, require sending CV and offer
text to a third party, and add key management plus provider SDKs to a project
whose whole premise is one dependency.

**Optional LLM mode, off by default.** Rejected as the worst of both. The
dependency, the network layer and the key handling all still exist and must be
maintained and tested, in exchange for a path most users would never take.

**Local model via Ollama.** Rejected. It preserves privacy but not simplicity:
it adds a heavy external runtime the user must install and keep running, to
duplicate reasoning the calling agent has already done.

## Notes

The author's stated drivers, in order: **API cost first, privacy second.**
The architectural elegance — the agent is already there, so let it do the
thinking — reinforced a decision already made on those two grounds.

This is the decision most likely to be challenged by a contributor who assumes
"AI tool" means "calls a model". It does not. Reversing it would change what
applyr is.

Related: [ADR 001](001-local-first.md), [`mental-model.md`](../mental-model.md).
