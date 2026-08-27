## Spec: Visual/UI Audit & Improvements — applyr

### Status: DRAFT
### Version: 1.0

### Recovered context
- Project constitution: applyr/AGENTS.md (CLI conventions, NO_COLOR support, English output, constants in constants.py, no DB access outside db.py)
- Relevant ADRs: ADR-003 (no LLM calls), ADR-004 (weighted scoring), ADR-008 (.md primary CV format), ADR-011 (evidence-based CV engine)
- Engram decisions: Terminal color system via colorama, ASCII tables, ATS-optimized CV template
- Corrected assumptions: 
  - CV CSS exists in two places (template file + inline in cv.py) — must unify
  - Progress bar width is fixed at 20 chars — should be terminal-aware
  - Status labels inconsistent between pipeline (raw) and list (abbreviated)

### What does it do? (observable behavior, not implementation)

This spec covers a comprehensive visual/UI refresh of applyr's two output surfaces:

**1. CLI Terminal Output** — All user-facing text, tables, progress bars, colors, and icons
**2. CV Artifacts** — The ATS-optimized HTML template, markdown generation, and PDF output

The goal: make both surfaces feel intentionally designed (not defaulted), consistent, accessible, and terminal-aware.

### What files does it touch?

| File | Action | Reason |
|------|--------|--------|
| `applyr/colors.py` | MODIFY | Extend color palette, add semantic colors for hierarchy |
| `applyr/constants.py` | MODIFY | Add terminal-aware width detection, unify truncation constants |
| `applyr/commands/_helpers.py` | MODIFY | Enhance `_bar()`, `_truncate()`, `_classify_icon()`, add table printing helpers |
| `applyr/commands/analytics.py` | MODIFY | Update pipeline, stats, gaps, trends, summary, compare, plan, salary output |
| `applyr/commands/core.py` | MODIFY | Update list, show, pipeline (via analytics), search output formatting |
| `applyr/commands/workflow.py` | MODIFY | Update export, doctor output formatting |
| `applyr/cv.py` | MODIFY | Unify CSS source, improve markdown→HTML rendering, multilingual headings |
| `applyr/templates/cv-ats.html` | MODIFY | Single source of truth for ATS CSS, update to match cv.py |
| `applyr/templates/cv-master-template.md` | READ | Reference for CV generation |
| `applyr/cli.py` | READ | Verify --no-color, --json, NO_COLOR handling |

### Dependencies
- `colorama` (existing) — color support
- `shutil.get_terminal_size()` (stdlib) — terminal width detection
- Chrome/Chromium (existing) — PDF generation
- No new external dependencies

### Acceptance criteria

#### EARS format (technical/system requirements)

**Terminal Awareness & Responsiveness**
- `[MUST]` WHEN terminal width < 80 chars THEN tables SHALL reflow (hide columns, stack rows, or truncate gracefully)
- `[MUST]` WHEN terminal width >= 120 chars THEN tables SHALL use full width with comfortable padding
- `[MUST]` Progress bars SHALL scale to terminal width (min 10, max 50 chars)
- `[MUST]` Truncation widths SHALL derive from terminal width, not hardcoded constants

**Color System & Hierarchy**
- `[MUST]` Semantic color palette SHALL exist: primary, secondary, success, warning, error, info, muted
- `[MUST]` Status colors SHALL be consistent across ALL commands (pipeline, list, show, stats, gaps, plan)
- `[MUST]` NO_COLOR / --no-color / --json SHALL disable ALL color output (zero ANSI codes)
- `[MUST]` Color contrast SHALL meet WCAG AA for default terminal backgrounds (light & dark)

**Visual Hierarchy & Typography (CLI)**
- `[MUST]` Section headers in `show` output SHALL use visual grouping (borders, spacing, capitalization)
- `[MUST]` Numeric columns (%, ID, salary) SHALL be right-aligned consistently
- `[MUST]` Status labels SHALL use `STATUS_LABELS` mapping everywhere (not raw keys)
- `[SHOULD]` Table headers SHALL have subtle visual separation from data rows

**Icons & Progress Indicators**
- `[MUST]` Progress bars SHALL show percentage inside bar: `[####----] 45%`
- `[MUST]` Classification icons (✓ △ ✕) SHALL have accessible text fallbacks when --no-color
- `[SHOULD]` Spinner/indicator for long-running operations (cv pdf, doctor)

**CV Artifacts — HTML Template & Generation**
- `[MUST]` Single source of truth for ATS CSS — template file read by cv.py, not duplicated
- `[MUST]` CV headings SHALL match offer language (EN/ES) — template placeholders replaced at generation
- `[MUST]` Generated HTML SHALL pass ATS checks: single column, no flex/grid/tables, standard fonts, no images
- `[MUST]` PDF output SHALL respect page limits (1 page standard, 2 pages for senior/lead/director)
- `[SHOULD]` CV markdown generation SHALL include tailoring hints as HTML comments (already implemented)

**CV Artifacts — Multilingual Support**
- `[MUST]` Spanish headings SHALL use correct accents (Formación, Experiencia Profesional, etc.)
- `[MUST]` Date formats SHALL be locale-aware (MM/YYYY vs DD/MM/YYYY)
- `[SHOULD]` Language detection from offer SHALL cascade to all CV sections

**Accessibility**
- `[MUST]` All color-coded information SHALL have text/icon alternative (status, priority, classification)
- `[MUST]` Table output SHALL be parseable by screen readers (no box-drawing Unicode)
- `[SHOULD]` --json output SHALL include all visual metadata (colors, icons, formatting hints)

#### Given/When/Then (user stories)

- `[MUST]` Given a narrow terminal (60 cols), When I run `applyr list`, Then I see a readable table without horizontal scroll
- `[MUST]` Given a wide terminal (160 cols), When I run `applyr stats`, Then columns use available space with comfortable margins
- `[MUST]` Given NO_COLOR=1, When I run any command, Then output contains zero ANSI escape codes
- `[MUST]` Given a Spanish job offer, When I run `applyr cv generate`, Then the markdown has Spanish headings (Perfil Profesional, Experiencia Profesional)
- `[MUST]` Given a senior offer, When I generate PDF, Then output is max 2 pages
- `[MUST]` Given `applyr pipeline`, When I view output, Then status colors match `applyr list` status column colors
- `[SHOULD]` Given `applyr show 123`, When I view output, Then related fields are grouped with clear visual separators

### Explicit assumptions
- Terminal supports ANSI colors (colorama handles Windows)
- User terminal width detectable via `shutil.get_terminal_size()` (fallback to 80)
- CV PDF generation via Chrome headless continues to work
- No breaking changes to `--json` output schemas
- Existing colorama dependency sufficient (no need for rich/textual)

### Non-functional requirements
- Performance: Terminal width detection < 1ms, no perceptible delay
- Backwards compatibility: All existing `--json` schemas unchanged
- Accessibility: WCAG AA contrast for default light/dark terminals
- Maintainability: Single CSS source, constants centralized

### Edge cases / risks
| Risk | Mitigation |
|------|------------|
| Terminal width detection fails (CI, pipes) | Fallback to 80 cols; detect non-TTY |
| Color contrast fails on user's custom terminal theme | Use relative colors (bright/dim) not absolute hex; test on light/dark |
| Breaking existing scripts parsing human output | Keep --json stable; document human output as non-contractual |
| CV CSS divergence between template and inline | Single source: cv.py reads template file |
| Spanish accents corrupt in PDF | Explicit UTF-8 encoding throughout; Chrome supports Unicode |

### Task breakdown (execution order)

#### Phase 1: Foundation — Terminal Awareness & Constants
1. Add `get_terminal_width()` helper in `constants.py` with fallback [S]
2. Replace hardcoded truncation widths with terminal-aware calculations [M]
3. Make `PROGRESS_BAR_WIDTH` dynamic based on terminal width [S]
4. Add semantic color palette to `colors.py` [S]

#### Phase 2: Color System & Status Consistency
5. Define semantic colors: primary, secondary, success, warning, error, info, muted [S]
6. Create `get_status_color(status)` and `get_status_label(status)` single sources [S]
7. Update `pipeline`, `list`, `show`, `stats`, `gaps`, `plan`, `salary` to use unified status colors [M]
8. Verify NO_COLOR/--no-color/--json disables all colors [S]

#### Phase 3: CLI Output Formatting
9. Enhance `_bar()` to show percentage and scale to width [S]
10. Add `_print_section_header()` and `_print_field_group()` for `show` visual hierarchy [S]
11. Right-align all numeric columns consistently across commands [S]
12. Add table header separator line [S]
13. Update `_classify_icon()` to return text fallback when colors disabled [S]

#### Phase 4: CV Template Unification
14. Move ATS CSS to template file as single source; cv.py reads and embeds it [M]
15. Update template with multilingual heading placeholders (already in CV_HEADINGS) [S]
16. Verify PDF page limit logic works for both EN/ES [S]
17. Ensure UTF-8 encoding throughout markdown→HTML→PDF pipeline [S]

#### Phase 5: Polish & Validation
18. Run full command matrix test (list, show, pipeline, stats, gaps, plan, trends, summary, compare, salary, cv generate, cv pdf, cv review) [M]
19. Test at terminal widths: 60, 80, 100, 120, 160 [M]
20. Test with NO_COLOR=1, --no-color, --json [S]
21. Verify ATS compliance of generated CV HTML [S]

### Out of scope
- `[WONT]` Interactive TUI (textual/rich) — applyr stays CLI-first
- `[WONT]` New CV templates (cover letter, alternative layouts) — separate feature
- `[WONT]` Theming/user-customizable colors — config-driven maybe later
- `[WONT]` Animation/transitions in terminal — not applicable
- `[WONT]` Web UI / dashboard — different product

### Open questions
- [RESOLVED] `show` output: two-column layout (label | value) ✓
- [RESOLVED] Default info density: moderate (current spacing) ✓
- [RESOLVED] ASCII box-drawing in `show`: no — use section headers with spacing instead ✓
- [RESOLVED] Progress bar style: `████░░░░░ 45%` (Unicode blocks) ✓
- [RESOLVED] CV languages: EN and ES only ✓