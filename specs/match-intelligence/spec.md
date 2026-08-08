# Spec: Match Intelligence — Product Polish for v1.0.0

### Status: APPROVED
### Version: 1.0
### Target release: v1.0.0

---

## What does it do?

Five improvements to make the match score understandable and actionable:

1. **Three-state recommendation** — APPLY / MAYBE / LOW MATCH (not binary)
2. **Skill-level breakdown** — Strong / Partial / Missing per topic
3. **"Why you match"** — Executive summary of strengths and weaknesses
4. **CV tailoring hints** — What to emphasize, what to de-emphasize
5. **Score breakdown** — Why 78% and not higher

---

## Acceptance criteria

### Phase 1 — Three-state recommendation

- [MUST] Three states: APPLY (>=80%), MAYBE (60-79%), LOW MATCH (<60%)
- [MUST] Configurable thresholds in applyr.toml
- [MUST] Backward compatible: old `threshold` still works
- [MUST] Colored output with icons: ✅ APPLY, ⚠️ MAYBE, ❌ LOW MATCH
- [MUST] `--json` includes `recommendation` field

### Phase 2 — Skill-level breakdown

- [MUST] Classify topics: Strong (>=80%), Partial (50-79%), Missing (<50%)
- [MUST] Show breakdown in `cmd_add` and `cmd_show`
- [MUST] `--json` includes `match_breakdown` object

### Phase 3 — "Why you match"

- [MUST] Top 3 strong topics with scores
- [MUST] Biggest weakness (lowest partial or highest missing)
- [MUST] `--json` includes `why_you_match` and `biggest_weakness`

### Phase 4 — CV tailoring hints

- [MUST] HTML comments in generated CV with hints
- [MUST] Derived from tech_stack and topic scores
- [MUST] Show tailoring summary in output

### Phase 5 — Score breakdown

- [MUST] Weighted contribution per topic
- [MUST] Ordered by weight (highest first)
- [MUST] `--json` includes `score_breakdown` array

---

## Out of scope

- LLM-generated explanations (ADR 003)
- Per-skill matching (agent territory)
- "What if" scenarios
- Job description parsing
