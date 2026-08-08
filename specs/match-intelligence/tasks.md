# Tasks: Match Intelligence

## Phase 1 — Three-state recommendation

- [ ] 1.1 Add threshold constants to constants.py [S]
- [ ] 1.2 Update config.py template with new thresholds [S]
- [ ] 1.3 Add _get_recommendation() helper to commands/core.py [M]
- [ ] 1.4 Modify cmd_add output for three states [M]
- [ ] 1.5 Add recommendation to --json output [S]
- [ ] 1.6 Add backward compatibility for old threshold [S]
- [ ] 1.7 Write tests for recommendation logic [M]
- [ ] 1.8 Commit: feat(recommendation): three-state APPLY/MAYBE/LOW MATCH

## Phase 2 — Skill-level breakdown

- [ ] 2.1 Add _classify_topic() helper to commands/_helpers.py [S]
- [ ] 2.2 Add _show_match_breakdown() helper to commands/core.py [M]
- [ ] 2.3 Modify cmd_add to show breakdown [M]
- [ ] 2.4 Modify cmd_show to show breakdown [M]
- [ ] 2.5 Add match_breakdown to --json output [S]
- [ ] 2.6 Write tests for classification [M]
- [ ] 2.7 Commit: feat(breakdown): skill-level Strong/Partial/Missing

## Phase 3 — "Why you match"

- [ ] 3.1 Add _get_why_you_match() helper [S]
- [ ] 3.2 Add _get_biggest_weakness() helper [S]
- [ ] 3.3 Modify cmd_add to show summary [M]
- [ ] 3.4 Add fields to --json output [S]
- [ ] 3.5 Write tests for summary [M]
- [ ] 3.6 Commit: feat(summary): Why you match + Biggest weakness

## Phase 4 — CV tailoring hints

- [ ] 4.1 Add _get_tailoring_hints() helper to cv.py [M]
- [ ] 4.2 Modify cmd_cv_generate to add hints [M]
- [ ] 4.3 Show tailoring summary in output [S]
- [ ] 4.4 Write tests for hints [M]
- [ ] 4.5 Commit: feat(cv): tailoring hints for emphasis/de-emphasis

## Phase 5 — Score breakdown

- [ ] 5.1 Add _show_score_breakdown() helper [M]
- [ ] 5.2 Modify cmd_show to show breakdown [M]
- [ ] 5.3 Add score_breakdown to --json output [S]
- [ ] 5.4 Write tests for breakdown [M]
- [ ] 5.5 Commit: feat(breakdown): weighted score explanation

## Final

- [ ] 5.6 Run full test suite
- [ ] 5.7 Run pylint
- [ ] 5.8 Update CHANGELOG.md
- [ ] 5.9 Update README.md
- [ ] 5.10 Create PR to main
