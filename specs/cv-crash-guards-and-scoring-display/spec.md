## Spec: CV file-read crash guards + scoring display consistency (bug-fix batch)

### Status: IMPLEMENTED
### Version: 1.0

### Recovered context

- **ADR-006** (errors to stderr) and **ADR-007** (structured JSON errors): every failure
  path must end in `die()`, never a bare exception or `return`; `code` is the stable,
  documented part of the contract, `message` wording is not.
- **`docs/contracts.md`**: `unsupported_format` is the documented code for "file exists
  but isn't readable as text, e.g. a rendered PDF passed to a text-reading command."
  `not_found` is reserved for offers/templates; a user-supplied **file path** not existing
  uses `file_not_found` in the actual code (`cv.py:996`, `cv.py:1262`) — the original bug
  report assumed `not_found` for this case, corrected here after reading the real call sites.
- **PR #71** (`applyr cv ats-check`, `cv bullet-optimize`, `cv keywords`): already fixed
  this exact crash class with `try/except UnicodeDecodeError: die(..., code="unsupported_format")`.
  Those three commands are the reference pattern and are **not modified** by this spec —
  only the three call sites that never got the fix are in scope.
- **Corrected assumption from Step 2**: the shared helper (`_read_text_or_die`) is placed
  in `applyr/errors.py`, not `applyr/cv.py`. `compare_cvs()` lives in `applyr/analytics.py`,
  which does not currently import `applyr/cv.py` (and vice versa) — routing the helper
  through `cv.py` would create a new cross-module dependency for no reason. `errors.py` is
  already imported by `cv.py` and has no heavy dependencies, so both `cv.py` and
  `analytics.py` can import `_read_text_or_die` from there without new coupling.
- **Corrected assumption**: `cmd_rescore` (`applyr/commands/analytics.py:776`) reads
  already-stored `offer_topics` rows and only recomputes `calculate_score()` under current
  weights — it performs no new topic-score validation on user input, so BUG-4's new warning
  is added only in `cmd_add`, not in `cmd_rescore` (there is nothing to re-validate there).
- No relevant ADR covers scoring *display* (as opposed to scoring *computation*, which is
  ADR-004/009) — `_show_score_breakdown`'s divergence from `calculate_score()` is a plain
  implementation bug, not a documented, intentional design choice.

### What does it do? (observable behavior, not implementation)

- `applyr cv review`, `applyr cv compare`, and `applyr cv pdf <file.md>` reject a
  missing or non-text (binary/mis-encoded) file with the same clean, structured error every
  other file-reading `cv` command already gives, instead of an unhandled Python traceback.
- `applyr add` warns (without rejecting) when a topic score falls outside `[0, 100]`, the
  same way it already warns for an unrecognized topic key — and the out-of-range topic no
  longer shows up as a false "Strong" or "Missing" skill in `add`/`show`/`gaps`' breakdown,
  so the displayed skill list never contradicts the compatibility percentage next to it.
- `applyr export --redact-fields ""` (an explicit empty string) is rejected the same way
  `--redact-fields ",  ,"` already is, instead of silently exporting unredacted data.
- `applyr show <id>`'s "Score breakdown" table always sums to exactly the same number as
  the "Compatibility" percentage shown earlier in the same command's output, even when
  fewer than all six topics were scored (the common case — the scoring rubric tells agents
  to omit topics the offer doesn't mention).
- `README.md`'s three test-count references agree with each other and with reality.

### Acceptance criteria

#### BUG-1 / BUG-2 / BUG-3 — shared file-read guard

- `[MUST]` The system shall provide `_read_text_or_die(path: Path, *, code_not_found: str = "file_not_found") -> str`
  in `applyr/errors.py`, which: returns the file's UTF-8 text on success; calls
  `die(f"CV file not found: {path}", code=code_not_found)` if the path does not exist;
  calls `die(f"{path} is not a text file.", code="unsupported_format", details={"path": str(path)})`
  if reading raises `UnicodeDecodeError`.
- `[MUST]` WHEN `applyr cv review <file>` is given a path that does not exist or is not
  valid UTF-8 text, THE system SHALL call `_read_text_or_die` and exit via `die()` with the
  matching `code`, both with and without `--json` — never an unhandled traceback.
- `[MUST]` WHEN `applyr cv compare <v1> <v2>` is given a missing path or a non-text file
  for either argument, THE system SHALL exit via `die()` with `file_not_found` or
  `unsupported_format` respectively — currently it has neither check.
- `[MUST]` WHEN `applyr cv pdf <file.md>` is given a `.md` file that is not valid UTF-8,
  THE system SHALL exit via `die(..., code="unsupported_format")` instead of raising
  `UnicodeDecodeError` from `render_markdown_file_to_html`.
- `[MUST]` `cmd_cv_ats_check`, `cmd_cv_bullet_optimize`, `cmd_cv_keywords`, and the existing
  sibling-hint logic inside `cmd_cv_ats_check` are left untouched — their current tests
  (`TestCvAtsCheck`, `TestCvBulletOptimize`) must keep passing unmodified.
- `[SHOULD]` `compare_cvs()` keeps its current signature (`(v1_path: str, v2_path: str) -> dict`)
  and behavior for valid input — only the failure path changes.
- `[WONT]` A sibling-hint (suggesting a `.md`/`.html` file next to a bad path) for
  `cv review`, `cv compare`, or `cv pdf` — that UX only exists today on `ats-check` and is
  out of scope here; the shared helper returns a generic, correct error, not a contextual hint.

#### BUG-4 — out-of-range topic score warning + display consistency

- `[MUST]` WHEN `applyr add` receives a topic with `score` outside `[0, 100]` (and the
  score is numeric), THE system SHALL print `warn(f"  Warning: topic '{topic_key}' score
  {score} is outside 0-100 and will not count toward the compatibility percentage.")` to
  stderr, in the same loop and style as the existing unknown-topic-key warning
  (`applyr/commands/core.py:698`).
- `[MUST]` The out-of-range score shall still be stored in `offer_topics` exactly as today
  (no clamping, no rejection) — this closes the *visibility* gap, not a validation gap.
- `[MUST]` `_classify_topic(score)` in `applyr/commands/_helpers.py` shall return a new
  `"invalid"` classification for `score < 0 or score > 100`, alongside the existing
  `"strong"`/`"partial"`/`"missing"`.
- `[MUST]` `_show_match_breakdown`, `_get_match_breakdown`, and `_get_why_you_match` in
  `applyr/commands/core.py` shall skip any topic classified `"invalid"` entirely — it must
  not appear under Strong, Partial, or Missing in either text or `--json` output.
- `[SHOULD]` Given an offer where one topic scores 150, When `applyr add` runs, Then the
  printed compatibility percentage (already correct today) and the printed Strong/Partial/Missing
  list agree with each other — the 150-scored topic appears in neither.
- `[WONT]` Changing `calculate_score()`'s existing (correct) exclusion behavior.
- `[WONT]` A DB constraint or migration to enforce `score BETWEEN 0 AND 100` — explicitly
  out of scope, this spec closes a display/warning gap only.

#### BUG-5 — `--redact-fields ""` validation

- `[MUST]` WHEN `--redact-fields` is passed with the literal empty string `""`, THE system
  SHALL treat it the same as a non-empty string containing no usable field names (e.g.
  `",  ,"`) and `die("Error: --redact-fields was passed with no field names.", ...)`.
- `[MUST]` The fix shall change the guard from `if redact_fields:` to
  `if redact_fields is not None:` in `applyr/commands/workflow.py` (`cmd_export`), so an
  explicitly-passed empty string reaches the existing `if not requested: die(...)` check
  instead of short-circuiting past it.
- `[SHOULD]` Given `--redact-fields` is omitted entirely (not passed), When `applyr export`
  runs, Then behavior is unchanged (no redaction) — only the explicit-empty-string case changes.

#### BUG-6 — Score breakdown total must equal the displayed Compatibility percentage

- `[MUST]` `_show_score_breakdown(topics, weights)` in `applyr/commands/_helpers.py` shall
  accumulate both `total_contribution` (`score * weight`, as today) and `total_weight`
  (sum of `weight` for each topic actually present), then print
  `Total = total_contribution / total_weight` (0 if `total_weight` is 0) instead of the raw
  `total_contribution` sum.
- `[MUST]` Given the same `topics` dict, `_show_score_breakdown`'s printed "Total" and
  `calculate_score(topics)` (`applyr/scoring.py`) shall always produce the same percentage
  (within rounding to 1 decimal place), for any subset of the six topics.
- `[MUST]` A regression test scoring fewer than all six topics (e.g. the real repro: 4 of
  6 topics, weights 30/15/20/10 summing to 75) shall assert the printed breakdown Total
  matches `calculate_score()`'s output for that same input — this is the exact case that
  silently diverged before the fix (offer #234: header showed 78%, old breakdown Total
  showed 58.2%).
- `[WONT]` Changing the per-topic `contribution` line (`score% × weight% weight = X.X
  contribution`) — only the final `Total` line's formula changes.

#### DRIFT-1 — README test-count accuracy

- `[MUST]` The system shall update `README.md` line 17 (badge), line 351 (`# 576 tests,
  ~4s` comment), and line 364 (`Test suite (576 tests)`) to the verified count from
  `pytest --collect-only -q` at implementation time (691 at spec-writing time; re-verify
  immediately before editing, since new tests are added by this same spec).
- `[WONT]` Wiring the badge to a CI-generated/dynamic source — flagged as a good follow-up
  by the audit but out of scope for this bug-fix batch.

### Affected files

| File | Action | Reason |
|------|--------|--------|
| `applyr/errors.py` | MODIFY | Add `_read_text_or_die()` shared helper (BUG-1/2/3) |
| `applyr/cv.py` | MODIFY | `cmd_cv_review` (~L812-820) and `cmd_cv_pdf`'s `.md` branch (~L290) call the new helper |
| `applyr/analytics.py` | MODIFY | `compare_cvs()` (~L30-33) calls the new helper; add `from applyr.errors import die` if not already imported at this scope |
| `applyr/md_render.py` | MODIFY or bypass | Either add the same guard in `render_markdown_file_to_html` (~L170) or have `cmd_cv_pdf` read via the shared helper before calling it — pick whichever avoids double-reading the file |
| `applyr/commands/core.py` | MODIFY | `cmd_add`'s topic loop (~L702-719) gets the out-of-range warning; `_show_match_breakdown`/`_get_match_breakdown`/`_get_why_you_match` (~L172-280) skip `"invalid"` classification |
| `applyr/commands/_helpers.py` | MODIFY | `_classify_topic` (~L62-73) gains `"invalid"` return; `_show_score_breakdown` (~L86-111) divides by `total_weight` |
| `applyr/commands/workflow.py` | MODIFY | `cmd_export`'s redact-fields guard (~L111-125): `if redact_fields:` → `if redact_fields is not None:` |
| `README.md` | MODIFY | 3 test-count references corrected |
| `tests/test_cv.py` | MODIFY | New tests: `cv review` and `cv compare` binary/missing-file cases (mirroring `TestCvAtsCheck`/`TestCvBulletOptimize`); `cv pdf` `.md` binary case |
| `tests/test_commands.py` | MODIFY | New tests: out-of-range topic score warning + breakdown exclusion (BUG-4); `--redact-fields ""` rejection (BUG-5) |
| `tests/test_scoring.py` (or wherever `_show_score_breakdown` is most naturally tested) | MODIFY | New test: breakdown Total matches `calculate_score()` on a partial-topics input |

### Dependencies

- `applyr.errors.die` — existing, `NoReturn`-typed, safe to call from a helper whose
  return type is `str` (type checkers accept unreachable code after a `NoReturn` call).
- `applyr.scoring.calculate_score` — read, not modified; BUG-6's fix must match its formula
  exactly (`weighted_sum / total_weight`).
- No new external dependency, no DB migration, no schema change.
- **PR budget**: single combined PR per user decision. Estimated diff: helper (~25 lines) +
  3 call-site changes (~15 lines) + BUG-4 (~15 lines) + BUG-5 (~2 lines) + BUG-6 (~10 lines)
  + README (~3 lines) + tests (~150-200 lines across 3 files) ≈ **250-300 lines total** —
  comfortably under the 500-line budget. If implementation reveals it's tracking higher
  (e.g. the `md_render.py` guard turns out to need more rework than expected), stop and
  flag before continuing rather than silently exceeding budget.

### Explicit assumptions

- We assume `render_markdown_file_to_html` is only ever reached from `cmd_cv_pdf`'s `.md`
  branch (confirmed: `applyr/cv.py:290`) → if another call site exists, it needs the same
  guard and isn't currently enumerated here.
- We assume the existing `TestCvAtsCheck`/`TestCvBulletOptimize` test fixtures (binary file
  content, e.g. PNG magic bytes) can be reused/mirrored for the new `cv review`/`cv
  compare`/`cv pdf` tests → if their fixture setup is test-class-local rather than a shared
  fixture, the new tests duplicate a small amount of setup rather than importing it.
- We assume `config.get("weights", {})` (passed into `_show_score_breakdown`) and
  `config["weights"]` (used inside `calculate_score`) are the same dict shape (topic →
  fraction, e.g. `0.30`) → verified true by reading both call sites; if `load_config()`
  ever changes this shape, both functions break together and the new regression test
  catches it immediately.

### Non-functional requirements

- **Consistency**: error codes/messages for the newly-guarded call sites must match the
  existing `docs/contracts.md` vocabulary exactly (`file_not_found`, `unsupported_format`)
  — no new error codes introduced.
- **Backward compatibility**: no change to any currently-passing test's expected output;
  no change to `calculate_score()`'s return value for any existing input.

### Edge cases / risks

- A topic score that is a non-numeric type (e.g. a string) → already handled elsewhere
  (`isinstance(score, (int, float))` guards exist at insert time); BUG-4's new warning only
  fires for numeric out-of-range values, matching the existing skill-gap tracking check at
  `core.py:718` which uses the same `isinstance` guard.
- `total_weight == 0` in `_show_score_breakdown` (all topics have an unrecognized key and
  fall back to `DEFAULT_TOPIC_WEIGHT`, or the topics list is empty) → guard against
  division by zero, print `Total 0%` rather than crashing; the function already returns
  early when `not topics`, so this only matters if every topic's weight resolves to exactly 0.
- `compare_cvs` importing `die` from `applyr.errors` for the first time → confirm no
  circular import (`applyr.errors` has zero project-internal imports today, so this is safe).
- Existing callers of `_classify_topic` outside `core.py` (none found in this repo as of
  this spec, confirmed via grep) → if the audit missed one, it also needs the `"invalid"`
  handling; re-grep at implementation time before considering BUG-4 done.

### Task breakdown (execution order)

1. [x] Create branch `fix/cc-cv-crash-guards-and-scoring` off `main` (not off the
   unrelated, uncommitted `docs/cc-auto-pdf-cover-letter-workflow` branch) [S]
2. [x] Add `_read_text_or_die()` to `applyr/errors.py` (named `read_text_or_die`, public —
   needed by `analytics.py`/`md_render.py` too) + regression tests [S]
3. [x] Wire `cmd_cv_review` to the helper (BUG-1) + regression tests, incl. `--json` mode [S]
4. [x] Wire `compare_cvs` to the helper (BUG-2) + regression tests [S]
5. [x] Wire `render_markdown_file_to_html` (reached from `cmd_cv_pdf`'s `.md` branch) to the
   helper (BUG-3) + regression tests [S]
6. [x] Add out-of-range topic score warning in `cmd_add`, add `"invalid"` classification to
   `_classify_topic` and skip it in the three breakdown functions (BUG-4) + regression tests [M]
7. [x] Fix `--redact-fields ""` guard in `cmd_export` (BUG-5) + regression test [S]
8. [x] Fix `_show_score_breakdown` to divide by `total_weight` (BUG-6) + regression tests
   against `calculate_score()` on partial- and full-topic inputs, plus a strengthened
   existing test (`test_multiple_topics`) now asserting the exact corrected total [S]
9. [x] Update the 3 stale test-count references in `README.md` to the real, re-verified
   count (714 — 691 original + 23 new regression tests) (DRIFT-1) [S]
10. [x] Run full test suite: 714 passed, 0 regressions; 715 after the `/code-review` fix below [S]
11. [x] `/simplify-lean` pass — 3 passes (errors.py; cv.py/analytics.py/md_render.py;
   _helpers.py/core.py/workflow.py) + 1 pass over all 7 test files (extracted one
   `INVALID_PDF` constant in `TestCvReview`, no other changes) [S]
12. [x] `/code-review` pass before PR — found and fixed 1 real gap (see above) [S]

### Traceability matrix

| AC | Priority | Description | Test | Implementation | Status |
|----|----------|--------------|------|-----------------|--------|
| BUG-1/2/3 helper | MUST | `read_text_or_die()` returns text or dies with `file_not_found`/`unsupported_format` | `tests/test_errors.py::TestReadTextOrDie` | `applyr/errors.py:83-99` | PASS |
| BUG-1 | MUST | `cv review` dies cleanly on missing/binary file, text + `--json` | `tests/test_cv.py::TestCvReview` | `applyr/cv.py` (`cmd_cv_review`) | PASS |
| BUG-1 | MUST | `ats-check`/`bullet-optimize`/`keywords` unmodified, own tests still pass | `tests/test_cv.py::TestCvAtsCheck`, `TestCvBulletOptimize` | unchanged | PASS |
| BUG-2 | MUST | `compare_cvs` dies cleanly on missing/binary file | `tests/test_analytics.py::TestCompareCvs` (2 new tests) | `applyr/analytics.py:33-34` | PASS |
| BUG-3 | MUST | `cv pdf <file.md>` dies cleanly on binary markdown | `tests/test_md_render.py::TestRenderMarkdownFileToHtml` (2 new tests) | `applyr/md_render.py:172` | PASS |
| BUG-4 | MUST | Out-of-range score warns at `add` time | `tests/test_commands.py::TestOutOfRangeTopicScoreWarning` | `applyr/commands/core.py` (`cmd_add` topic loop) | PASS |
| BUG-4 | MUST | Out-of-range score stored unclamped (no behavior change to storage) | `tests/test_commands.py::TestOutOfRangeTopicScoreWarning::test_out_of_range_score_is_still_stored_unclamped` | unchanged (INSERT statement) | PASS |
| BUG-4 | MUST | `_classify_topic` returns `"invalid"` outside [0,100] | `tests/test_recommendation.py::TestClassifyTopic` | `applyr/commands/_helpers.py:62-75` | PASS |
| BUG-4 | MUST | Invalid topics excluded from Strong/Partial/Missing + why-you-match/biggest-weakness | `tests/test_recommendation.py::TestGetMatchBreakdown`, `TestGetWhyYouMatch`; `tests/test_commands.py::test_out_of_range_score_does_not_appear_as_strong_or_missing` | `applyr/commands/core.py:172-280` | PASS |
| BUG-5 | MUST | `--redact-fields ""` dies instead of exporting unredacted | `tests/test_commands.py::TestExportRedaction::test_redact_fields_of_literal_empty_string_dies_instead_of_exporting_unredacted` | `applyr/commands/workflow.py:112` | PASS |
| BUG-5 | SHOULD | Omitted `--redact-fields` unchanged (no redaction) | pre-existing `TestExportRedaction` tests, unmodified | unchanged | PASS |
| BUG-6 | MUST | Breakdown Total == `calculate_score()` on partial topics | `tests/test_scoring.py::TestScoreBreakdownMatchesCalculateScore` | `applyr/commands/_helpers.py:86-114` | PASS |
| BUG-6 | MUST | Breakdown Total still correct when all topics scored | `tests/test_scoring.py::test_total_still_correct_when_all_topics_are_scored` | same | PASS |
| BUG-6 | MUST | Live repro pinned (offer #234 shape: 4 topics, weights 30/15/20/10) | `tests/test_recommendation.py::TestShowScoreBreakdown::test_multiple_topics` (strengthened) | same | PASS |
| DRIFT-1 | MUST | README test-count references match reality (714) | manual verification via `pytest --collect-only -q` | `README.md:17,351,364` | PASS |

Every `[MUST]` AC has a test and an implementation. Full suite: **715 passed, 0 failed**.

### `/code-review` finding (fixed before PR)

`/code-review medium` found one real gap: `_show_score_breakdown`'s BUG-6 fix corrected the
*divisor* (`total_weight` instead of raw 100%) but never excluded an out-of-range
("invalid") score from the *numerator* — the same class of topic BUG-4 warns about could
still enter `total_contribution`, pushing `Total` above 100% or otherwise off
`calculate_score()`'s value (repro: `tech_stack=150` alongside `projects=90` printed
`Total 126.0%`). Fixed by skipping `_classify_topic(score) == "invalid"` topics entirely in
`_show_score_breakdown`, matching the exclusion already applied by `calculate_score()` and
the other three breakdown functions. Regression test added:
`tests/test_scoring.py::test_out_of_range_score_excluded_from_total_not_just_the_divisor`.
Suite count updated 714 → 715.

### Out of scope

- `[WONT]` Sibling-hint UX (suggesting a `.md`/`.html` neighbor) for the three newly-guarded
  commands — `ats-check` keeps its hint, the others get a plain, correct error only.
- `[WONT]` DB-level constraint enforcing topic scores in `[0, 100]`.
- `[WONT]` Dynamic/CI-generated README test badge.
- `[WONT]` Any change to `calculate_score()` itself — it is already correct.
- `[WONT]` Fixing the pre-existing `code="not_found"` vs `code="file_not_found"` inconsistency
  on `cmd_cv_pdf`'s top-level file-not-found check (`cv.py:280`) — that check already works
  correctly today (no crash), so it is not part of this bug-fix batch; noting it here only
  so it isn't confused with the in-scope fixes.
