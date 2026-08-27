## Data Model: Visual/UI Audit — applyr

### Status: DRAFT
### Version: 1.0

### Overview

This feature makes **no database schema changes**. All modifications are presentation-layer only. This document describes the *presentation data model* — the structured data that flows through the formatting layer.

### Presentation Entities

#### TerminalContext
```python
@dataclass
class TerminalContext:
    width: int                    # Detected terminal columns (fallback: 80)
    is_tty: bool                  # True if stdout is a TTY
    colors_enabled: bool          # False if NO_COLOR, --no-color, or --json
    json_mode: bool               # True if --json flag present
```

**Source:** `constants.get_terminal_context()` (new function)

#### SemanticColorPalette
```python
@dataclass
class SemanticColorPalette:
    primary: str      # Main brand/actions
    secondary: str    # Supporting actions
    success: str      # Positive states (offer, passed)
    warning: str      # Caution states (waiting, partial)
    error: str        # Negative states (rejected, failed)
    info: str         # Informational (applied, in_process)
    muted: str        # De-emphasized text (labels, metadata)
    dim: str          # Lowest emphasis (disabled, hints)
    reset: str        # Style.RESET_ALL
```

**Source:** `colors.SEMANTIC_COLORS` (new constant)

#### StatusDisplay
```python
@dataclass
class StatusDisplay:
    key: str              # Raw status key (e.g., "in_process")
    label: str            # Human label (e.g., "In Process")
    color: str            # Semantic color key (e.g., "info")
    icon: str             # ASCII icon (e.g., "▶")
```

**Mapping (single source of truth):**
| Key | Label | Color | Icon |
|-----|-------|-------|------|
| pending | Pending | muted | ○ |
| applied | Applied | info | → |
| waiting | Waiting | warning | ⏳ |
| in_process | In Process | info | ▶ |
| offer | Offer | success | ★ |
| rejected | Rejected | error | ✕ |
| discarded | Discarded | dim | ⟳ |

**Source:** `colors.get_status_display(status_key)` (new function)

#### ColumnSpec
```python
@dataclass
class ColumnSpec:
    header: str
    key: str              # Row dict key
    width: int            # Calculated at render time
    min_width: int        # Minimum readable width
    align: str            # "left" | "right" | "center"
    truncate: bool        # Whether to truncate with ellipsis
    color_fn: callable    # Optional: row -> color key
```

**Used by:** `_print_table(rows, columns, context)`

#### ProgressBarSpec
```python
@dataclass
class ProgressBarSpec:
    score: int            # 0-100
    width: int            # Bar width in chars (min 10, max 50)
    show_percentage: bool # Always True in v1
    filled_char: str      # "#" (ASCII)
    empty_char: str       # "-" (ASCII)
```

**Rendered as:** `████░░░░░ 45%`

**Characters:** Full block (U+2588) for filled, Light shade (U+2591) for empty

#### CVTemplateContext
```python
@dataclass
class CVTemplateContext:
    language: str                    # "en" | "es" (from offer)
    headings: dict                   # CV_HEADINGS[language]
    offer: dict                      # Offer row from DB
    topics: dict                     # offer_topics for this offer
    cv_master_text: str              # Raw cv-master.md content
    tailoring_hints: str             # HTML comments (TAILOR, DE-EMPHASIZE, NOT INCLUDED)
    ats_css: str                     # CSS from template file
```

**Source:** `cv.py:cmd_cv_generate()` builds this, passes to template

### Data Flow

```
CLI Command
    ↓
load_config() → TerminalContext (width, colors, json_mode)
    ↓
DB Query → Raw Rows
    ↓
Transform → Display Rows (apply StatusDisplay, truncate, color)
    ↓
Format → Terminal Output (tables, sections, bars)
    ↓
stdout
```

```
cv generate
    ↓
Load offer + topics + cv-master
    ↓
Build CVTemplateContext (resolve language, headings, hints)
    ↓
Render Markdown (YAML frontmatter + sections with placeholders)
    ↓
Write .md file (UTF-8)
    ↓
cv pdf
    ↓
Read .md → render_markdown_file_to_html()
    ↓
Wrap with ats_css (from template file)
    ↓
Chrome headless → PDF
```

### Constants (Presentation-Layer)

| Constant | Type | Description |
|----------|------|-------------|
| `MIN_TERMINAL_WIDTH` | int | 60 — below this, stack layout |
| `MAX_TERMINAL_WIDTH` | int | 200 — cap for very wide terminals |
| `DEFAULT_TERMINAL_WIDTH` | int | 80 — fallback |
| `PROGRESS_BAR_MIN_WIDTH` | int | 10 |
| `PROGRESS_BAR_MAX_WIDTH` | int | 50 |
| `TABLE_MIN_COL_WIDTH` | int | 8 |
| `TABLE_PADDING` | int | 2 — spaces between columns |
| `SECTION_SPACING` | int | 1 — blank lines between sections |

### Validation Rules

- Terminal width ∈ [60, 200] (clamped)
- Progress bar width ∈ [10, 50] (clamped)
- All column widths ≥ `TABLE_MIN_COL_WIDTH`
- Sum of column widths + padding ≤ terminal width
- StatusDisplay exists for every VALID_STATUSES value
- SemanticColorPalette has all 9 keys when colors enabled
- CVTemplateContext.language ∈ CV_HEADINGS.keys()
- ats_css non-empty string