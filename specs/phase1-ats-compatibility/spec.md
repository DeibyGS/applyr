## Spec: Phase 1 — ATS Compatibility

### Status: DRAFT
### Version: 1.0

### Recovered context
- Project constitution: `constitution.md`
- Relevant ADRs: ADR 003 (No LLM calls)
- Engram decisions: v1.2.0 real-world test (5 offers, scoring works, cv generate needs agent fill)

### What does it do?
Adds ATS compatibility checking and keyword matching to the CV pipeline, so users can verify their CV passes ATS parsing before sending.

### What files does it touch?
| File | Action | Reason |
|------|--------|--------|
| `applyr/ats.py` | CREATE | New module: ATS checker + keyword matcher |
| `applyr/cli.py` | MODIFY | Add `ats-check` and `keywords` commands |
| `applyr/commands/cv.py` | MODIFY | Add `ats_check()` and `keywords()` functions |
| `applyr/templates/ats_rules.json` | CREATE | ATS validation rules (headers, formats, forbidden) |
| `tests/test_ats.py` | CREATE | Unit tests for ATS module |

### Dependencies
- APIs / endpoints used: None
- DB tables / relevant RLS: None
- Auth pattern: None
- Reused components: `cv.py` (CV parsing), `config.py` (load_config), `errors.py` (die/error)

### Acceptance criteria

#### EARS format:

- `[MUST]` WHEN user runs `applyr cv ats-check <file>` THE system SHALL parse the CV file and return ATS compatibility score (0-100) with specific issues
- `[MUST]` WHEN user runs `applyr cv keywords <offer_id>` THE system SHALL extract keywords from offer and compare against CV, returning matched/missing/extra keywords
- `[MUST]` THE system shall validate: single column layout, standard headers, no images, no tables, no text boxes, consistent date format
- `[MUST]` THE system shall detect and report: contact info in headers/footers, non-standard section names, complex formatting
- `[SHOULD]` IF CV has missing keywords THEN the system SHALL suggest where to add them
- `[SHOULD]` THE system shall output results in `--json` format for agent consumption
- `[COULD]` WHERE `--fix` flag is provided THEN the system SHALL auto-fix simple issues (standardize headers, date formats)

#### Given/When/Then:

- `[MUST]` Given a valid ATS-friendly CV, When user runs `ats-check`, Then score >= 85 and no critical issues
- `[MUST]` Given a CV with tables/columns, When user runs `ats-check`, Then score < 50 with "tables detected" issue
- `[MUST]` Given an offer with tech_stack "Python, React, Node.js", When user runs `keywords <id>`, Then output shows matched/missing keywords vs CV
- `[SHOULD]` Given a CV with non-standard headers, When user runs `ats-check`, Then system suggests standard alternatives

### Explicit assumptions
- We assume CV files are Markdown (.md) → if false, need to add DOCX/PDF parsing
- We assume ATS rules are static (not per-company) → if false, need company-specific rule sets
- We assume keyword extraction is based on tech_stack field → if false, need full JD parsing

### Non-functional requirements
- Performance: ATS check completes in < 2 seconds for 1-page CV
- Security: No external API calls, all local processing
- Usability: Output readable in terminal and parseable via `--json`

### Edge cases / risks
- CV with non-English text → keyword matching may fail on accented characters → use case-insensitive matching
- CV with code blocks (```) → may be flagged as formatting → allow code blocks in Projects section
- Offer with no tech_stack field → keyword extraction fails → return empty keywords with warning

### Task breakdown (execution order)
1. Create `applyr/ats.py` with ATS validation rules [S]
2. Create `tests/test_ats.py` with test cases [S]
3. Implement `ats_check()` in `commands/cv.py` [M]
4. Implement `keywords()` in `commands/cv.py` [M]
5. Add CLI routing in `cli.py` [S]
6. Integration test: full flow with real CV [S]

### Out of scope
- `[WONT]` Automatic CV rewriting (agent does this)
- `[WONT]` Per-company ATS rules (use generic rules)
- `[WONT]` DOCX/PDF input parsing (Markdown only)
- `[WONT]` Cloud-based ATS simulation (local only)

### Open questions
- [NEEDS CLARIFICATION] Should `ats-check` also verify length (1 page for <5yr exp)?
- [NEEDS CLARIFICATION] Should `keywords` output include frequency count of each keyword?
