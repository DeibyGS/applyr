# ADR 011 — Evidence-Based CV Engine

**Status:** Accepted
**Date:** 2026-08-26
**Supersedes:** None (new decision)

## Context

`cv-master.md` is documented as "the only source of truth" (`AGENT_INSTRUCTIONS.md`),
but that principle is enforced only by instructing the calling agent — never verified.
The agent that fills a generated CV skeleton can state a technology, metric, employer,
or date not actually present in the candidate's profile, especially when a job offer
names requirements the profile doesn't cover. Nothing in the pipeline catches this: `cv
review` and `cv review-blind` are both LLM judgment calls on quality/ATS-fit, not
factual verification, and a second LLM checking a first LLM's output does not
guarantee groundedness — both can share the same inference.

The existing partial safeguard, `_get_tailoring_hints` (`applyr/cv.py`), filters offer
`tech_stack` against `cv-master.md` via a raw lowercase substring check. This is real
but fragile: it fails on "AWS" vs "Amazon Web Services" or "Postgres" vs "PostgreSQL",
producing false `NOT INCLUDED` hints for skills the candidate genuinely has.

Separately, the offer's original posting text is not stored at all — `add` persists
only the Matcher's structured interpretation (`tech_stack`, `topics`, etc.), so the raw
source of what the offer actually said does not survive past the initial scoring pass.

This decision does not relax [ADR 003](003-no-llm-calls.md): applyr still makes zero
LLM API calls. Every piece below is deterministic Python.

## Decision

Build an Evidence-Based CV Engine as four chained, independently-mergeable pieces:

1. **Raw job description storage.** `offers.job_description` (nullable TEXT) holds the
   posting text verbatim, set via `add`/`update`. `offers.cv_evidence_used` (nullable
   TEXT, JSON array) is added in the same migration for piece 3 below. Schema v10 → v11.

2. **Evidence Graph parser** (`applyr/evidence.py`, new module). A pure,
   deterministic function `parse_evidence(profile_text: str) -> list[EvidenceClaim]`
   splits `cv-master.md` into typed claims (skills, employer/project entries, bullet
   text) by its existing `## SECTION` / `**Bold Title**` / bullet structure — the same
   structure `cv-master-template.md` already documents. **cv-master.md's file format
   does not change.** No claim IDs are authored by the user; they exist only as
   ephemeral identifiers within a single parse call, never persisted as foreign keys.
   A companion `PROTECTED_FACT_ALIASES` dict in `constants.py` (AWS/Amazon Web
   Services, PostgreSQL/Postgres, etc.) and an `is_evidenced()` matcher replace raw
   substring checks with alias-aware, still-deterministic matching.

3. **Audit snapshot, not a cache.** The Evidence Graph is re-derived at runtime on
   every `cv generate`/`cv verify` call — nothing about it is cached or persisted.
   Only the *result* of verifying one specific generated CV is persisted, as a
   snapshot of claim texts (not ephemeral IDs) written to `offers.cv_evidence_used`.
   This was chosen explicitly over a persisted `evidence_claims` table: a stale cache
   could make a future truth-checking command approve or reject a CV against claims
   that no longer match the live master — exactly the failure mode this decision
   exists to prevent. The audit snapshot carries no such risk because it documents a
   past, immutable event ("this CV was verified against these claims"), not a live
   view of current truth.

4. **`cv verify`, a new deterministic gate command.** Extracts factual claims from a
   generated CV (technology terms, percentage/multiplier metrics, employer and job
   title names) and checks each against the Evidence Graph. Exits 0 (PASS) or 1
   (BLOCKED, listing unsupported claims) — directly authoritative on exit, unlike `cv
   review`/`cv review-blind`, which print a prompt for the calling agent to execute.
   Full acceptance criteria: `specs/evidence-based-cv-engine/spec.md`.

## Consequences

### Positive

- Closes the single largest hallucination surface in the CV pipeline with zero LLM
  calls and zero new dependencies — consistent with ADR 003 and ADR 005.
- `cv-master.md` stays exactly the free-text Markdown it is today. Existing users on
  PyPI v1.11.1 need no profile migration, only the standard additive schema bump.
- The audit snapshot gives after-the-fact traceability ("what evidence backed this
  CV") without introducing a stale-cache correctness risk.
- `_get_tailoring_hints`'s external contract (`<!-- TAILOR -->` / `<!-- NOT INCLUDED
  -->` comments) is unchanged — this hardens its internals, it does not add a new
  user-facing surface.

### Negative

- The parser is heuristic against a documented-but-unenforced Markdown structure. A
  `cv-master.md` that deviates heavily from `cv-master-template.md` yields fewer
  extracted claims, which biases `cv verify` toward over-reporting unsupported claims
  (false positives) rather than missing real ones — the safer failure direction for a
  truth gate, but still a real limitation.
- The protected-fact alias dictionary is a fixed, curated seed set. A legitimate term
  outside it (e.g. an uncommon tool with no seeded alias) is flagged unsupported even
  when true. Mitigated by keeping the dict a plain, easily extended Python constant.
- `cv verify` only checks protected-fact categories (technologies, metrics,
  employer/title names) — not full-sentence or responsibility-level claims (e.g. "led
  a team of 8"). Broader claim verification is out of scope for this decision.

### Neutral

- `cv verify` is not wired into `cv pdf` or `AGENT_INSTRUCTIONS.md` as a mandatory
  gate by this decision. `AGENT_INSTRUCTIONS.md` is a protected, external-agent-facing
  contract file — making verification mandatory there is a separate, explicit decision
  to make once `cv verify` has shipped and been used in practice.
- Date-range claim verification is deferred (documented as `[SHOULD]`, not `[MUST]`,
  in the spec) — free-text date formatting carries more legitimate variation than tech
  terms or percentages, a higher false-positive risk to take on in a first release.

## Alternatives considered

**Claim Verifier without an Evidence Graph** (regex/alias-dict claim extraction run
directly against raw `cv-master.md` text, no typed claims). Rejected: without typed
claims (section, entry context), the extractor cannot distinguish "this term appears
in TECHNICAL SKILLS" from "this term appears inside a stray sentence in PROFESSIONAL
SUMMARY", which weakens the employer/job-title verification category in particular.

**Persisted, cached Evidence Graph table.** Rejected — see Decision, piece 3. A stale
cache risks the exact failure mode (approving unsupported claims) this feature exists
to prevent, for a parsing cost (a few KB of Markdown, re-parsed only on `cv
generate`/`cv verify`) too small to justify the added invalidation logic.

**Structured YAML/claim-ID authoring in cv-master.md.** Rejected. Forces a migration
and a UX change on every existing user for a benefit (stable claim identity across
edits) nothing in the current scope needs — the audit snapshot persists claim *text*,
not IDs, specifically so this isn't required.

**Semantic/fuzzy LLM-based claim verification.** Rejected on two grounds: it violates
ADR 003 (no LLM calls inside applyr), and — even if it didn't — a verifier built from
the same kind of model that produces the hallucination risk can share its inference
errors, undermining the point of having a gate at all.

## Notes

Full acceptance criteria and the four-PR execution breakdown:
`specs/evidence-based-cv-engine/spec.md`.

Related: [ADR 003](003-no-llm-calls.md) (no LLM calls — this decision's parsing and
verification logic is entirely deterministic), [ADR 008](008-md-first-cv-pipeline.md)
(MD-first pipeline — `cv verify` parses the same Markdown format `cv generate`
produces).
