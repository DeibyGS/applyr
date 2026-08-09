## Spec: Phase 2 — Recruiter Experience

### Status: DRAFT
### Version: 1.0

### Recovered context
- Project constitution: `constitution.md`
- Relevant ADRs: ADR 003 (No LLM calls)
- Phase 1 spec: `specs/phase1-ats-compatibility/spec.md`
- Industry research: 6-second recruiter scan, F-pattern reading, CAR/X-Y-Z bullet formulas

### What does it do?
Enhances CV quality for recruiter consumption with bullet point optimization, ATS score automation, and cover letter generation.

### What files does it touch?
| File | Action | Reason |
|------|--------|--------|
| `applyr/cv.py` | MODIFY | Add `optimize_bullets()`, `generate_cover_letter()` |
| `applyr/commands/cv.py` | MODIFY | Add `bullet_optimize()`, `cover_letter()` functions |
| `applyr/cli.py` | MODIFY | Add `bullet-optimize` and `cover-letter` commands |
| `applyr/templates/cover_letter.md` | CREATE | Cover letter template |
| `applyr/templates/bullet_patterns.json` | CREATE | Duty→Achievement conversion patterns |
| `tests/test_cv_bullets.py` | CREATE | Tests for bullet optimization |
| `tests/test_cover_letter.py` | CREATE | Tests for cover letter generation |

### Dependencies
- APIs / endpoints used: None
- DB tables / relevant RLS: None
- Auth pattern: None
- Reused components: `cv.py` (CV generation), `cv_master.py` (profile parsing), `ats.py` (keyword matching from Phase 1)

### Acceptance criteria

#### EARS format:

- `[MUST]` WHEN user runs `applyr cv bullet-optimize <file>` THE system SHALL analyze each bullet point and suggest duty→achievement conversions with metrics placeholders
- `[MUST]` WHEN user runs `applyr cv cover-letter <offer_id>` THE system SHALL generate a tailored cover letter from cv-master.md and offer data
- `[MUST]` THE system shall convert "Responsible for X" → "Achieved X as measured by Y by doing Z" pattern
- `[MUST]` THE system shall detect bullets without metrics and suggest where to add numbers
- `[SHOULD]` IF bullet starts with weak verb THEN the system SHALL suggest strong action verbs (Orchestrated, Spearheaded, Optimized)
- `[SHOULD]` THE system shall generate cover letter with: opening hook, 3 relevant achievements, call to action
- `[COULD]` WHERE `--json` flag is provided THEN the system SHALL output structured data for agent consumption

#### Given/When/Then:

- `[MUST]` Given a CV with "Responsible for managing social media", When user runs `bullet-optimize`, Then output suggests "Grew LinkedIn followers by 45% (10K→14.5K) through targeted content strategy"
- `[MUST]` Given an offer for "Full Stack Developer", When user runs `cover-letter <id>`, Then cover letter mentions React, Node.js, TypeScript from cv-master
- `[MUST]` Given a CV with metrics ("665 tests"), When user runs `bullet-optimize`, Then bullet is marked as strong (no optimization needed)
- `[SHOULD]` Given a CV with weak verbs ("Helped", "Worked on"), When user runs `bullet-optimize`, Then system suggests stronger alternatives

### Explicit assumptions
- We assume bullet optimization is suggestion-only → agent applies changes → if false, need auto-apply mode
- We assume cover letter is 1 page max → if false, need length parameter
- We assume cover letter is in English → if false, need language parameter (from offer)

### Non-functional requirements
- Performance: Bullet optimization completes in < 3 seconds for 10 bullets
- Security: No external API calls, all local processing
- Usability: Suggestions readable in terminal and parseable via `--json`

### Edge cases / risks
- CV with no bullets (only paragraphs) → cannot optimize → return warning with no suggestions
- Offer with minimal info (no summary) → cover letter generic → warn user to add offer details
- Bullet already has metrics → skip optimization → mark as strong

### Task breakdown (execution order)
1. Create `applyr/templates/bullet_patterns.json` [S]
2. Create `applyr/templates/cover_letter.md` [S]
3. Create `tests/test_cv_bullets.py` [S]
4. Create `tests/test_cover_letter.py` [S]
5. Implement `optimize_bullets()` in `cv.py` [M]
6. Implement `generate_cover_letter()` in `cv.py` [M]
7. Add CLI routing in `cli.py` [S]
8. Integration test: full flow with real CV and offer [S]

### Out of scope
- `[WONT]` Automatic CV rewriting (agent does this)
- `[WONT]` Multi-language cover letters (English only for now)
- `[WONT]` A/B testing of bullet variants (Phase 3)
- `[WONT]` Cover letter PDF generation (Phase 3)

### Open questions
- [NEEDS CLARIFICATION] Should bullet-optimize suggest 1-2 alternatives or just the best one?
- [NEEDS CLARIFICATION] Should cover letter include salary expectations from offer?
- [NEEDS CLARIFICATION] Should cover letter be saved as .md or .txt?
