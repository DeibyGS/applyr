## Plan: Visual/UI Audit & Improvements — applyr

### Status: DRAFT
### Version: 1.0

### Technical Architecture

**Approach:** Incremental, non-breaking refactor of output formatting. No database changes, no new dependencies. All changes confined to presentation layer.

**Core Principle:** Single source of truth for each visual concern:
- Terminal width → `constants.py:get_terminal_width()`
- Colors → `colors.py` semantic palette
- Status display → `_helpers.py:get_status_color/label()`
- Table rendering → `_helpers.py:_print_table()` enhanced
- CV CSS → `templates/cv-ats.html` (read by `cv.py`)

### Component Breakdown

| Component | Files | Responsibility |
|-----------|-------|----------------|
| **Terminal Awareness** | `constants.py`, `commands/_helpers.py` | Detect width, calculate column widths, bar width |
| **Color System** | `colors.py` | Semantic palette, NO_COLOR handling, status colors |
| **Table/Output Formatting** | `commands/_helpers.py`, `commands/analytics.py`, `commands/core.py` | Unified table printing, section headers, field groups |
| **Progress/Classification** | `commands/_helpers.py` | `_bar()`, `_classify_icon()`, `_classify_topic()` |
| **CV Generation** | `cv.py`, `templates/cv-ats.html` | Single CSS source, multilingual headings, UTF-8 pipeline |

### Technology Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Terminal width detection | `shutil.get_terminal_size()` + fallback | Stdlib, no deps, works in CI |
| Color library | Keep `colorama` | Already in deps, handles Windows |
| Table rendering | Enhanced ASCII (no Unicode box-drawing) | Screen-reader safe, works everywhere |
| CV CSS delivery | Template file read at runtime | Single source, version-controlled |
| Progress bar chars | Unicode blocks `█░` with ASCII fallback | Accessible, visible; fallback for --no-color |

### Tradeoffs

| Tradeoff | Decision | Mitigation |
|----------|----------|------------|
| Dynamic vs fixed column widths | Dynamic (terminal-aware) | Min/max bounds prevent extreme layouts |
| ASCII vs Unicode icons | ASCII (✓△✕) | Text fallbacks when --no-color |
| Single CSS file vs inline | Template file read by cv.py | Eliminates divergence risk |
| Configurable density | Not in v1 — moderate default | Add `display.density` config later if demanded |

### Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Terminal width detection breaks in pipes/CI | Medium | High | Detect non-TTY, fallback to 80 |
| Color contrast fails on custom themes | Medium | Medium | Test light/dark; use relative bright/dim |
| Breaking `--json` consumers | High | Low | Zero changes to JSON schemas |
| CV PDF regression | High | Medium | Test matrix: EN/ES, junior/senior, 1/2 page |
| Divergent status colors persist | Medium | Medium | Single `get_status_color()` function |

### Data Model

No database schema changes. Only presentation-layer constants and helpers.

### Migration Strategy

None required — no data migration. All changes are output formatting.

### API Contracts

No API changes. `--json` output schemas remain identical.

### Implementation Sequence

**Phase 1: Foundation** (Tasks 1-4)
- `constants.py`: `get_terminal_width()`, dynamic truncation constants
- `colors.py`: Semantic palette, `get_status_color()`, `get_status_label()`
- `_helpers.py`: Dynamic `_bar()`, enhanced `_truncate()`

**Phase 2: Color Consistency** (Tasks 5-8)
- Apply semantic colors to all analytics commands
- Apply to core commands (list, show, pipeline)
- Verify NO_COLOR paths

**Phase 3: CLI Formatting** (Tasks 9-13)
- Enhanced progress bars with percentage
- `show` command visual hierarchy (section headers, field groups)
- Right-align numeric columns universally
- Table header separators

**Phase 4: CV Unification** (Tasks 14-17)
- `cv.py` reads CSS from template file
- Template updated with current best practices
- Multilingual verification
- UTF-8 pipeline audit

**Phase 5: Validation** (Tasks 18-21)
- Full command matrix at multiple terminal widths
- NO_COLOR/--json verification
- ATS compliance check

### File-Level Changes

#### `applyr/constants.py`
- Add `get_terminal_width()` → int
- Add `calculate_column_widths(total_width, col_ratios)` → list[int]
- Replace `LIST_COL_WIDTHS`, `PROGRESS_BAR_WIDTH`, `TRUNCATE_*` with functions
- Keep constants as fallbacks for non-TTY

#### `applyr/colors.py`
- Add `SEMANTIC_COLORS = {"primary": "...", "success": "...", ...}`
- Add `get_status_color(status: str) → str`
- Add `get_status_label(status: str) → str` (wraps STATUS_LABELS)
- Ensure `init_colors()` disables all semantic colors when NO_COLOR

#### `applyr/commands/_helpers.py`
- `_bar(score, width=None)` → uses terminal width if None
- `_truncate(text, max_len=None)` → calculates from terminal width
- `_print_table()` → dynamic column sizing
- New: `_print_section_header(title)`, `_print_field_group(fields)`
- New: `_print_kv(label, value, indent=2)` for `show` command

#### `applyr/commands/analytics.py`
- Import `get_status_color`, `get_status_label` from `_helpers` or `colors`
- Replace hardcoded status color dicts with `get_status_color()`
- Use dynamic column widths in `cmd_compare`, `cmd_pipeline`
- Use `_print_section_header` in `cmd_stats`, `cmd_summary`

#### `applyr/commands/core.py`
- `cmd_list`: Use dynamic widths, `get_status_label`
- `cmd_show`: Rewrite with `_print_section_header` + `_print_field_group`
- `cmd_pipeline`: Use `get_status_color`, `get_status_label`

#### `applyr/cv.py`
- `_load_ats_css()` → reads `templates/cv-ats.html`, extracts `<style>` block
- Replace inline `_ATS_CSS` with call to `_load_ats_css()`
- Verify `resolve_cv_language()` drives all headings
- Ensure `write_text(encoding="utf-8")` everywhere

#### `applyr/templates/cv-ats.html`
- Update CSS to match current best practices (10pt body, 0.8cm margins)
- Keep as single source of truth
- Placeholders for multilingual headings (handled by cv.py at generation)

### Testing Strategy

| Test | Command | Verification |
|------|---------|--------------|
| Narrow terminal | `COLUMNS=60 applyr list` | No horizontal overflow |
| Wide terminal | `COLUMNS=160 applyr stats` | Columns use space |
| No color | `NO_COLOR=1 applyr pipeline` | Zero ANSI codes |
| JSON mode | `applyr list --json` | Valid JSON, same schema |
| CV EN | `applyr cv generate 1` | English headings |
| CV ES | `applyr cv generate 2` (Spanish offer) | Spanish headings |
| PDF pages | `applyr cv pdf cv-x.md` | 1 page (2 for senior) |
| ATS check | `applyr cv ats-check cv-x.html` | Pass |

### Dependencies

No new external dependencies. Uses:
- `shutil` (stdlib) — terminal size
- `colorama` (existing) — colors
- `re`, `json`, `pathlib` (stdlib) — CV processing

### Rollback Plan

Each phase is independently revertible via git. No database migrations. `--json` output unchanged throughout.