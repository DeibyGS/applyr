# Spec: Eligibility / Knockout Check

### Status: IMPLEMENTED
### Version: 1.1

### Recovered context
- Project constitution: no `docs/constitution.md` — `AGENTS.md` plus ADRs act as the
  constitution. Binding: [ADR 003](../../docs/adr/003-no-llm-calls.md) (no LLM calls),
  [ADR 007](../../docs/adr/007-structured-json-errors.md) (structured error codes),
  [ADR 011](../../docs/adr/011-evidence-based-cv-engine.md) (the agent extracts, applyr
  judges deterministically), [ADR 015](../../docs/adr/015-cli-enforced-pipeline-gates.md)
  (`applyr next` gates).
- Governing decision: [ADR 017](../../docs/adr/017-eligibility-knockout-check.md).
- Engram: `adr:applyr:eligibility-knockout-check` (2026-09-24).
- Origin: 2026-09 audit roadmap, Phase 5.1 — knockout questions are the most common real
  cause of rejection, and a high weighted score currently hides them.
- Decisions confirmed by Deiby (2026-09-24):
  - applyr judges; the agent only extracts the offer's mandatory requirements.
  - A hard block forces the recommendation to `low_match` with an explicit reason. The
    numeric compatibility score is never changed. The recommendation keeps its three values.
  - Missing profile data makes an item `unknown`, which never blocks.
  - v1 items: minimum years of experience, mandatory language level, location/relocation,
    driving license. Work permit is out of scope.
  - Years come from a value the user declares in the profile, not from job dates.
  - Language levels come from the profile's existing languages section.
  - Falling short by at most 1 year, or by exactly one language level, is a warning, not a
    block.
  - Location blocks only for onsite/hybrid offers in a city outside the user's list, when
    the user does not accept relocation. Remote offers never block on location.
  - Eligibility is a gate, separate from the weighted `experience` / `english` topics —
    both stay, and neither changes the other.

### What does it do? (observable behavior)
- When registering an offer, the agent can pass the offer's **mandatory** requirements
  (minimum years, required languages and levels, city, driving license).
- applyr compares each requirement with a new `ELIGIBILITY` section of the user's CV
  master (plus its existing languages section) and classifies each one as `pass`, `warn`,
  `block` or `unknown`.
- If any requirement is `block`, the offer's recommendation is `low_match` everywhere it
  is shown, with the reason, even when the compatibility score is high.
- `rescore` re-runs the check against the current CV master, so filling in the section
  later updates existing offers.
- `doctor` warns (without failing) when the CV master has no eligibility section.

### Boundaries
**Always do:** keep the check deterministic — same requirements + same profile = same result.
**Ask first:** adding any new eligibility item beyond the four v1 items.
**Never do:** change `compatibility_pct` because of eligibility; add a fourth recommendation
value; infer requirements applyr was not given.

### Acceptance criteria

#### Registration and evaluation
- `[MUST]` AC-01: WHEN `add` receives an `eligibility` block THE system SHALL store the
  offer's requirements and a per-item result (`pass` / `warn` / `block` / `unknown`) with
  the offer.
- `[MUST]` AC-02: WHEN `add` receives no `eligibility` block THE system SHALL behave exactly
  as before (no eligibility result, recommendation from the score alone).
- `[MUST]` AC-03: Given the profile declares N relevant years and the offer requires M,
  When the offer is added, Then the years item is `pass` if N ≥ M, `warn` if M − N ≤ 1,
  and `block` if M − N > 1.
- `[MUST]` AC-04: Given the profile's languages section lists a language with a CEFR level
  (A1–C2) or as native, When the offer requires that language at a level, Then the item is
  `pass` if the profile level is equal or higher, `warn` if it is exactly one level lower,
  and `block` if it is two or more levels lower. Native counts as at least C2.
- `[MUST]` AC-05: Language names SHALL match across English and Spanish spellings
  (e.g. "english" / "inglés" / "ingles"), case- and accent-insensitively.
- `[MUST]` AC-06: Given the offer's work mode is `onsite` or `hybrid` and it states a city,
  When that city is not in the profile's accepted cities (case- and accent-insensitive)
  and the profile declares relocation as not accepted, Then the location item is `block`.
  It is `pass` when the city is listed or relocation is accepted.
- `[MUST]` AC-07: WHEN the offer's work mode is `remote` THE location item SHALL never be
  `block`.
- `[MUST]` AC-08: Given the offer requires a driving license, When the profile declares
  having one, Then the item is `pass`; when it declares not having one, Then it is `block`.
- `[MUST]` AC-09: IF the profile has no eligibility section, or lacks the value an item
  needs, THEN that item SHALL be `unknown`, and `unknown` SHALL never block.

#### Recommendation effect
- `[MUST]` AC-10: WHILE an offer has at least one `block` item THE system SHALL report its
  recommendation as `low_match` wherever a recommendation is reported — `add` and `show`
  (text and `--json`), `list`, `search`, `pipeline` and `rescore` (`--json`) — and SHALL
  show which requirement blocked it. (v1.1: `summary` and the list/search/pipeline text
  tables never report a recommendation, so they are unaffected.)
- `[MUST]` AC-11: The compatibility score of a blocked offer SHALL be identical to the score
  it would have without the eligibility block.
- `[MUST]` AC-12: The recommendation SHALL remain one of `apply`, `maybe`, `low_match`.
- `[MUST]` AC-13: `--json` output of `add` and `show` SHALL include the per-item eligibility
  result and the blocking reason (`null` when not blocked).
- `[SHOULD]` AC-14: `warn` items SHALL be shown to the user but SHALL NOT change the
  recommendation.
- `[SHOULD]` AC-15: WHEN `applyr next` reaches the decide step for a blocked offer THE system
  SHALL add the same archive suggestion it gives for a low score, naming the blocking
  requirement.
- `[SHOULD]` AC-16: Score calibration SHALL count a blocked offer in the `low_match` band.

#### Re-evaluation and health
- `[MUST]` AC-17: WHEN `rescore <id>` runs on an offer with stored requirements THE system
  SHALL re-evaluate them against the current CV master and update the stored result.
- `[MUST]` AC-18: WHEN the CV master has no eligibility section THE `doctor` command SHALL
  report a warning naming the missing section, and SHALL NOT mark the setup unhealthy
  (exit code unchanged).
- `[SHOULD]` AC-19: The CV master template and the agent instructions SHALL document the
  eligibility section and the `eligibility` block of `add` (only mandatory requirements).

#### Error cases
- `[MUST]` AC-E1: Given an `eligibility` block with an unknown key, a negative or
  non-numeric `min_years`, a language level outside A1–C2/native, or a non-boolean
  `driving_license`, When `add` runs, Then it fails with error code `invalid_eligibility`
  naming the field, and no offer is stored.
- `[MUST]` AC-E2: Given an unreadable or missing CV master file, When `add` runs with an
  `eligibility` block, Then the offer is still stored and every item is `unknown`.
- `[MUST]` AC-E3: Given offers created before this feature, When they are read or listed,
  Then they behave as before (no eligibility, recommendation from the score).
- `[SHOULD]` AC-E4: Given a profile eligibility line with an unparseable value (e.g.
  `Relevant experience (years): some`), When evaluating, Then that item is `unknown`.

### Edge cases (business-observable)
- Offer requires several languages → each is its own item; any one `block` blocks the offer.
- Offer requires 0 years → always `pass`.
- Hybrid offer with no city stated → location is `unknown`.
- Both `warn` and `block` present → blocked; the reason lists the blocking item(s).
- Profile section written in Spanish (`## ELEGIBILIDAD`) → recognized like the English one.

### Out of scope
- `[WONT]` Work permit / visa items.
- `[WONT]` Salary expectations as a knockout.
- `[WONT]` Computing years from job dates.
- `[WONT]` Backfilling eligibility for existing offers (only `rescore` re-evaluates, and only
  when requirements were stored).
- `[WONT]` Changes to `feat/cc-visual-ui`.
