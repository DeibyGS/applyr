## Tasks: Visual/UI Audit & Improvements — applyr

### Status: DRAFT
### Version: 1.0

### Task Breakdown

Each task is atomic, independently verifiable, and maps to acceptance criteria in spec.md.
Complexity: S (<1h) | M (1-3h) | L (3-6h, consider splitting)

---

### Phase 1: Foundation — Terminal Awareness & Constants

#### Task 1.1: Add terminal context detection [S]
**File:** `applyr/constants.py`
**AC:** `[MUST]` Terminal width detection with fallback
**Steps:**
1. Add `get_terminal_context()` → `TerminalContext` dataclass
2. Use `shutil.get_terminal_size()` with try/except
3. Detect TTY via `sys.stdout.isatty()`
4. Read NO_COLOR env, --no-color, --json from global state (set by cli.py)
5. Return clamped width [60, 200], colors_enabled, json_mode
6. Add `MIN_TERMINAL_WIDTH=60`, `MAX_TERMINAL_WIDTH=200`, `DEFAULT_TERMINAL_WIDTH=80`
7. Add unit test in `tests/test_constants.py`

**Depends on:** None

#### Task 1.2: Replace hardcoded column widths with dynamic calculation [M]
**File:** `applyr/constants.py`, `applyr/commands/_helpers.py`
**AC:** `[MUST]` Tables reflow at < 80 cols, use full width at > 120 cols
**Steps:**
1. Add `calculate_column_widths(total_width, col_ratios, min_widths)` in constants.py
2. Replace `LIST_COL_WIDTHS`, `COMPARE_COL_MIN/MAX`, `PIPELINE_COMPANY_WIDTH`, etc. with ratios
3. Define column specs per table as list of `{key, ratio, min_width, align}`
4. Update `_print_table()` to accept column specs and calculate widths at render time
5. Preserve current visual output at 80 cols as baseline

**Depends on:** Task 1.1

#### Task 1.3: Make progress bar width dynamic [S]
**File:** `applyr/constants.py`, `applyr/commands/_helpers.py`
**AC:** `[MUST]` Progress bars scale to terminal width (min 10, max 50)
**Steps:**
1. Add `PROGRESS_BAR_MIN_WIDTH=10`, `PROGRESS_BAR_MAX_WIDTH=50` to constants.py
2. Modify `_bar(score, width=None)` to calculate width from terminal context
3. Width = clamp(terminal_width * 0.25, 10, 50) if not provided
4. Add percentage inside bar: `████░░░░░ 45%` (Unicode: U+2588 full, U+2591 light shade)
5. Ensure `--no-color` shows text-only bar with percentage (ASCII fallback: `[####----] 45%`)

**Depends on:** Task 1.1

#### Task 1.4: Add semantic color palette [S]
**File:** `applyr/colors.py`
**AC:** `[MUST]` Semantic color palette exists with 9 keys
**Steps:**
1. Define `SEMANTIC_COLORS` dict with keys: primary, secondary, success, warning, error, info, muted, dim, reset
2. Map to Colorama Fore/Style constants
3. Add `get_status_display(status_key)` → StatusDisplay dataclass
4. Add `get_status_color(status_key)` → color string
5. Add `get_status_label(status_key)` → human label
6. Ensure `init_colors()` disables all semantic colors when disabled
7. Map all VALID_STATUSES to StatusDisplay (7 entries)

**Depends on:** None

---

### Phase 2: Color Consistency Across Commands

#### Task 2.1: Apply semantic colors to analytics commands [M]
**File:** `applyr/commands/analytics.py`
**AC:** `[MUST]` Status colors consistent across all commands
**Steps:**
1. Import `get_status_color`, `get_status_label` from colors
2. Replace hardcoded status_color dicts in `cmd_pipeline`, `cmd_stats`, `cmd_gaps`, `cmd_plan`, `cmd_trends`, `cmd_summary`, `cmd_compare`, `cmd_salary`
3. Use `get_status_label()` for all status displays
4. Use `get_status_color()` for all colored status output
5. Verify priority colors (HIGH/MEDIUM/LOW) use semantic warning/error/success

**Depends on:** Task 1.4

#### Task 2.2: Apply semantic colors to core commands [M]
**File:** `applyr/commands/core.py`
**AC:** `[MUST]` `list`, `show`, `pipeline` use unified status colors
**Steps:**
1. Import semantic color functions
2. Update `cmd_list`: status column uses `get_status_label()` + color
3. Update `cmd_show`: status field uses `get_status_label()` + color
4. Update `cmd_pipeline` (if not in analytics): same
5. Ensure `cmd_search` output consistent

**Depends on:** Task 1.4

#### Task 2.3: Apply semantic colors to workflow commands [S]
**File:** `applyr/commands/workflow.py`
**AC:** `[MUST]` `export`, `doctor` use unified colors
**Steps:**
1. Update `cmd_doctor` check marks (✓/✗) to use success/error colors
2. Update `cmd_export` success messages

**Depends on:** Task 1.4

#### Task 2.4: Verify NO_COLOR/--no-color/--json paths [S]
**File:** `applyr/cli.py`, `applyr/colors.py`, all commands
**AC:** `[MUST]` Zero ANSI codes when colors disabled
**Steps:**
1. Add test: `NO_COLOR=1 applyr list | grep -c $'\\x1b'` → 0
2. Add test: `applyr --no-color list | grep -c $'\\x1b'` → 0
3. Add test: `applyr --json list | jq .` → valid JSON, no ANSI
4. Fix any commands leaking color codes

**Depends on:** Tasks 2.1, 2.2, 2.3

---

### Phase 3: CLI Output Formatting Enhancements

#### Task 3.1: Enhance progress bar with percentage [S]
**File:** `applyr/commands/_helpers.py`
**AC:** `[MUST]` Progress bars show `[####----] 45%`
**Steps:**
1. Modify `_bar()` to append `f" {score}%"` when colors enabled
2. When disabled: `[####----] 45%` (no color codes)
3. Ensure width calculation accounts for percentage suffix

**Depends on:** Task 1.3

#### Task 3.2: Add section header and field group helpers [S]
**File:** `applyr/commands/_helpers.py`
**AC:** `[MUST]` `show` command has visual hierarchy with two-column layout
**Steps:**
1. Add `_print_section_header(title)` — prints blank line, title in bold/primary, optional underline
2. Add `_print_field_group(fields: list[tuple[label, value, color_key]])` — two-column label │ value pairs
3. Add `_print_kv(label, value, indent=2, label_color="muted", value_color="primary")` — single row
4. Use box-drawing light vertical (U+2502) as column separator: `label │ value`
5. Label width: 22 chars left-aligned, value: remaining width
6. When colors disabled: use `:` instead of `│` for ASCII compatibility

**Depends on:** Task 1.4

#### Task 3.3: Rewrite `cmd_show` with visual hierarchy [M]
**File:** `applyr/commands/core.py`
**AC:** `[MUST]` Related fields grouped with clear separators, two-column layout
**Steps:**
1. Refactor `cmd_show` to use `_print_section_header` and `_print_field_group`
2. Group fields: Core → Work Details → Dates → Salary → Contact → Materials → Follow-up → Rejection → Summary/Notes
3. Two-column format: `label │ value` (U+2502 separator)
4. Right-align numeric values (%, salary, IDs) within value column
5. Omit empty/zero values (current behavior)
6. Use semantic colors for labels (muted) and values (primary)

**Depends on:** Task 3.2

#### Task 3.4: Right-align all numeric columns universally [S]
**File:** `applyr/commands/_helpers.py`, `applyr/commands/analytics.py`, `applyr/commands/core.py`
**AC:** `[MUST]` Numeric columns right-aligned consistently
**Steps:**
1. Add `align` field to ColumnSpec (left/right/center)
2. Default: left for text, right for numeric (%, ID, salary, counts)
3. Update all `_print_table` calls with proper column specs
4. Verify: list (%), pipeline (%), stats (counts), gaps (seen, avg_gap), compare (all numeric)

**Depends on:** Task 1.2

#### Task 3.5: Add table header separator [S]
**File:** `applyr/commands/_helpers.py`
**AC:** `[SHOULD]` Table headers have subtle visual separation
**Steps:**
1. Modify `_print_table` to print separator line after header
2. Separator: `─` (U+2500) or `-` repeated to column width
3. Only when colors enabled (avoids Unicode issues in some terminals)
4. Test at 60, 80, 120 cols

**Depends on:** Task 1.2

#### Task 3.6: Update classification icons with text fallbacks [S]
**File:** `applyr/commands/_helpers.py`
**AC:** `[MUST]` Icons have accessible text fallbacks when --no-color
**Steps:**
1. Modify `_classify_icon(classification)` to return tuple `(icon, text)`
2. When colors enabled: `("✓", "Strong")`, `("△", "Partial")`, `("✕", "Missing")`
3. When disabled: `("", "Strong")`, `("", "Partial")`, `("", "Missing")`
4. Update callers to use text fallback
5. Note: Progress bar uses Unicode blocks (U+2588/U+2591) — ASCII fallback in --no-color

**Depends on:** Task 1.1

---

### Phase 4: CV Template Unification

#### Task 4.1: Extract CSS from template file [M]
**File:** `applyr/cv.py`, `applyr/templates/cv-ats.html`
**AC:** `[MUST]` Single source of truth for ATS CSS
**Steps:**
1. Add `_load_ats_css()` in cv.py: reads template, extracts `<style>...</style>` block
2. Replace inline `_ATS_CSS` constant with call to `_load_ats_css()`
3. Cache result (module-level) to avoid re-reading
4. Fallback to embedded CSS if template missing (defensive)
5. Update template file with current best-practice CSS (10pt body, 0.8cm margins, @page margin: 0)

**Depends on:** None

#### Task 4.2: Verify multilingual heading generation [S]
**File:** `applyr/cv.py`
**AC:** `[MUST]` Spanish offers generate Spanish headings
**Steps:**
1. Verify `resolve_cv_language()` used for all headings in `cmd_cv_generate`
2. Test with offer.language = "es" → headings from CV_HEADINGS["es"]
3. Ensure YAML frontmatter `language` field matches
4. Verify `cv pdf` preserves language in HTML→PDF

**Depends on:** Task 4.1

#### Task 4.3: Audit UTF-8 pipeline [S]
**File:** `applyr/cv.py`
**AC:** `[MUST]` UTF-8 throughout markdown→HTML→PDF
**Steps:**
1. Verify all `write_text(encoding="utf-8")` calls
2. Verify `read_text(encoding="utf-8")` calls
3. Verify Chrome receives UTF-8 HTML (file:// protocol handles this)
4. Test with Spanish accents (Formación, Experiencia Profesional)
5. Test with special chars in cv-master.md (em-dash, bullets, etc.)

**Depends on:** Task 4.1

#### Task 4.4: Verify PDF page limit logic [S]
**File:** `applyr/cv.py`
**AC:** `[MUST]` 1 page standard, 2 pages for senior/lead/director
**Steps:**
1. Test `cmd_cv_pdf` with junior offer markdown → 1 page
2. Test with senior offer markdown → 2 pages allowed
3. Verify warning appears when exceeded
4. Ensure `_page_limit_for()` reads seniority from offer_id in frontmatter

**Depends on:** Task 4.1

---

### Phase 5: Validation & Polish

#### Task 5.1: Full command matrix test [M]
**Files:** All command files
**AC:** All commands produce expected output
**Steps:**
1. Create test script running every command with sample data
2. Verify at terminal widths: 60, 80, 100, 120, 160
3. Verify NO_COLOR, --no-color, --json for each
4. Check for regressions vs baseline screenshots

**Depends on:** All previous tasks

#### Task 5.2: ATS compliance verification [S]
**File:** `applyr/cv.py`, generated CVs
**AC:** `[MUST]` Generated CV HTML passes ATS checks
**Steps:**
1. Run `applyr cv ats-check` on generated CVs (EN and ES)
2. Verify: single column, no flex/grid/tables, standard fonts, no images
3. Verify section headers are standard (Work Experience, Education, etc.)
4. Verify contact info in body, not header/footer

**Depends on:** Task 4.1

#### Task 5.3: Accessibility audit [S]
**Files:** All output
**AC:** `[MUST]` Color-coded info has text/icon alternative
**Steps:**
1. Run all commands with NO_COLOR=1 — verify all info conveyed
2. Check status badges show text + color
3. Check priority badges show text + color
4. Check progress bars show percentage text
5. Verify tables parseable (no box-drawing Unicode)

**Depends on:** Task 2.4

#### Task 5.4: Update documentation [S]
**Files:** `README.md`, `docs/` (if any)
**AC:** Document new behaviors (terminal-aware, dynamic widths)
**Steps:**
1. Update README with terminal width behavior
2. Document --no-color/NO_COLOR behavior
3. Note CV language follows offer language

**Depends on:** All previous tasks

---

### Parallelization Notes

**Can run in parallel (no shared files):**
- Tasks 1.1, 1.4 (different files)
- Tasks 2.1, 2.2, 2.3 (different command files)
- Tasks 3.1, 3.2, 3.4, 3.6 (different helpers)
- Tasks 4.2, 4.3, 4.4 (different aspects of cv.py)

**Sequential dependencies:**
- 1.2, 1.3 → need 1.1
- 2.x → need 1.4
- 3.3 → needs 3.2
- 4.2, 4.3, 4.4 → need 4.1
- 5.1 → needs all implementation tasks
- 5.2, 5.3 → need 4.1, 2.4

---

### Test Mapping

| AC ID | Test File | Test Function |
|-------|-----------|---------------|
| Terminal width | `test_constants.py` | `test_get_terminal_context`, `test_calculate_column_widths` |
| Progress bar | `test_helpers.py` | `test_bar_dynamic_width`, `test_bar_shows_percentage` |
| Semantic colors | `test_colors.py` | `test_semantic_palette`, `test_status_display_mapping` |
| NO_COLOR | `test_cli_routing.py` | `test_no_color_flag`, `test_json_mode_no_ansi` |
| Show hierarchy | `test_commands.py` | `test_show_visual_structure` |
| Numeric alignment | `test_helpers.py` | `test_print_table_numeric_align` |
| CV CSS unification | `test_cv.py` | `test_css_single_source` |
| CV multilingual | `test_cv_language.py` | `test_spanish_headings` |
| PDF page limit | `test_cv.py` | `test_pdf_page_limit_senior` |
| ATS compliance | `test_ats.py` | `test_generated_cv_ats_compliant` |

---

### Definition of Done

- [ ] All Phase 1-4 tasks complete
- [ ] All tests pass (pytest)
- [ ] Pylint score ≥ 7.0
- [ ] Manual verification at 5 terminal widths
- [ ] NO_COLOR/--json verified for 10 commands
- [ ] CV generation tested EN + ES, junior + senior
- [ ] No ANSI codes in --json output
- [ ] JSON schemas unchanged (regression test)