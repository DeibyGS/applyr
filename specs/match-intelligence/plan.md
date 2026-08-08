# Plan: Match Intelligence

## Architecture

All changes are additive. No breaking changes to existing `--json` contracts.

### Data flow

```
User → CLI → cmd_add/cmd_show → Scoring → Recommendation → Output
                                    ↓
                              match_breakdown
                                    ↓
                              why_you_match
                                    ↓
                              score_breakdown
```

### Component breakdown

| Component | Responsibility | Files |
|-----------|---------------|-------|
| Config | Thresholds | config.py, constants.py |
| Scoring | Weighted calc | scoring.py |
| Commands | Output format | commands/core.py, commands/_helpers.py |
| CV | Tailoring hints | cv.py |

### Technology choices

- No new dependencies (ADR 005)
- Existing `_bar()` helper for visual bars
- Existing `TOPIC_LABELS` for display names
- Existing `die()` for errors (ADR 006)

---

## Phase 1 — Three-state recommendation

### Changes

1. **constants.py**: Add `DEFAULT_THRESHOLD_APPLY = 80`, `DEFAULT_THRESHOLD_MAYBE = 60`
2. **config.py**: Add `threshold_apply` and `threshold_maybe` to config template
3. **commands/core.py**: 
   - Add `_get_recommendation(score, config)` helper
   - Modify `cmd_add` output to show three states
   - Add `recommendation` to JSON output
4. **tests**: Add tests for recommendation logic

### Migration

- Backward compatible: if `threshold` exists but `threshold_apply` doesn't, use `threshold` as `threshold_apply` and `threshold - 20` as `threshold_maybe`

---

## Phase 2 — Skill-level breakdown

### Changes

1. **commands/_helpers.py**: Add `_classify_topic(score)` helper returning "strong"/"partial"/"missing"
2. **commands/core.py**:
   - Add `_show_match_breakdown(topics)` helper
   - Modify `cmd_add` to show breakdown
   - Modify `cmd_show` to show breakdown
   - Add `match_breakdown` to JSON output
3. **tests**: Add tests for classification and breakdown

---

## Phase 3 — "Why you match"

### Changes

1. **commands/core.py**:
   - Add `_get_why_you_match(topics)` helper
   - Add `_get_biggest_weakness(topics)` helper
   - Modify `cmd_add` to show summary
   - Add `why_you_match` and `biggest_weakness` to JSON output
2. **tests**: Add tests for summary generation

---

## Phase 4 — CV tailoring hints

### Changes

1. **cv.py**:
   - Add `_get_tailoring_hints(tech_stack, topics)` helper
   - Modify `cmd_cv_generate` to add HTML comments
   - Show tailoring summary in output
2. **tests**: Add tests for hint generation

---

## Phase 5 — Score breakdown

### Changes

1. **commands/_helpers.py**: Add `_show_score_breakdown(topics, weights)` helper
2. **commands/core.py**:
   - Modify `cmd_show` to show breakdown
   - Add `score_breakdown` to JSON output
3. **tests**: Add tests for breakdown display

---

## Risks

| Risk | Mitigation |
|------|------------|
| Breaking `--json` | Add only, never remove |
| Agent workflow | Hints in HTML comments, invisible |
| Config migration | Backward compatible |
