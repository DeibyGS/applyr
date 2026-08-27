"""Shared helpers used across multiple commands modules."""

from datetime import date

from applyr.colors import color, get_semantic_color, is_enabled
from applyr.constants import (
    get_terminal_context,
    calculate_column_widths,
    PROGRESS_BAR_MIN_WIDTH,
    PROGRESS_BAR_MAX_WIDTH,
    TABLE_MIN_COL_WIDTH,
    TABLE_PADDING,
    LIST_COL_SPECS,
    PIPELINE_COL_SPECS,
    GAPS_COL_SPECS,
    PLAN_COL_SPECS,
    TRENDS_COL_SPECS,
    SALARY_COL_SPECS,
    CATEGORY_SALARY_COL_SPECS,
)
from applyr.errors import die


def _today() -> str:
    """Return today's date as ISO string."""
    return date.today().isoformat()


def _validate_enum(value: str | None, valid: tuple[str, ...], field: str, required: bool = False) -> None:
    """Die with a standard invalid_value error if `value` isn't in `valid`.

    Optional fields (required=False, the default) skip validation when value
    is falsy — an omitted field is not the same as an invalid one. Required
    fields (status, salary_period) always carry a value via their caller's
    default, so there's nothing to skip.
    """
    if not required and not value:
        return
    if value not in valid:
        die(f"Error: invalid {field} '{value}'. Valid: {', '.join(valid)}",
            code="invalid_value",
            details={"field": field, "value": value, "valid": list(valid)})


def _get_terminal_width() -> int:
    """Get current terminal width from context."""
    return get_terminal_context().width


def _colors_enabled() -> bool:
    """Check if colors are enabled from context."""
    return get_terminal_context().colors_enabled


def _bar(score: int, width: int | None = None) -> str:
    """Render a progress bar for a 0-100 score using Unicode blocks.

    Args:
        score: Percentage 0-100
        width: Bar width in characters. If None, calculated from terminal width.

    Returns:
        String like "████░░░░░ 45%" (colored) or "[####----] 45%" (no-color fallback)
    """
    ctx = get_terminal_context()

    if width is None:
        # Use ~25% of terminal width, clamped
        width = max(PROGRESS_BAR_MIN_WIDTH, min(PROGRESS_BAR_MAX_WIDTH, ctx.width // 4))

    filled = round(score * width / 100)
    empty = width - filled

    if ctx.colors_enabled:
        # Unicode blocks: U+2588 (full), U+2591 (light shade)
        bar = "█" * filled + "░" * empty
        # Color the filled portion
        if score >= 80:
            bar = color(bar, "success")
        elif score >= 50:
            bar = color(bar, "warning")
        else:
            bar = color(bar, "error")
        return f"{bar} {score}%"
    else:
        # ASCII fallback
        bar = "#" * filled + "-" * empty
        return f"[{bar}] {score}%"


def _truncate(text: str | None, max_len: int | None = None) -> str:
    """Truncate a string to max_len characters, appending ellipsis if needed.

    If max_len is None, calculates from terminal width (approx 30% of width).
    """
    if not text:
        return ""

    if max_len is None:
        ctx = get_terminal_context()
        max_len = max(TABLE_MIN_COL_WIDTH, ctx.width // 3)

    return text if len(text) <= max_len else text[: max_len - 1] + "…"


_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _derive_confidence(topics: list[dict]) -> str:
    """Derive one overall confidence from per-topic confidence values.

    The weakest signal wins (low < medium < high), same reasoning as a chain
    being as strong as its weakest link. Topics that never provided a
    confidence are excluded from the comparison; if none of them did, the
    result is "unknown" — never a fabricated "medium". Kept out of
    scoring.py: this never feeds calculate_score(), only display.
    """
    ranked = [_CONFIDENCE_RANK[t["confidence"]] for t in topics if t.get("confidence") in _CONFIDENCE_RANK]
    if not ranked:
        return "unknown"
    weakest = min(ranked)
    return next(label for label, rank in _CONFIDENCE_RANK.items() if rank == weakest)


def _classify_topic(score: int) -> str:
    """Classify a topic score into Strong/Partial/Missing/Invalid.

    Returns:
        "invalid" if score is outside [0, 100] (excluded from compatibility% by
        calculate_score() too — see docs/adr/004-weighted-scoring.md), "strong"
        if score >= 80, "partial" if 50-79, else "missing".
    """
    if not 0 <= score <= 100:
        return "invalid"
    elif score >= 80:
        return "strong"
    elif score >= 50:
        return "partial"
    else:
        return "missing"


def _classify_icon(classification: str) -> tuple[str, str]:
    """Get icon and text label for classification.

    Returns:
        Tuple of (icon, text). Icon is empty string when colors disabled.
    """
    icons = {
        "strong": ("✓", "Strong"),
        "partial": ("△", "Partial"),
        "missing": ("✕", "Missing"),
    }
    icon, text = icons.get(classification, ("?", classification.title()))
    if not _colors_enabled():
        return "", text
    return icon, text


def _print_section_header(title: str) -> None:
    """Print a section header with visual separation."""
    ctx = get_terminal_context()
    if ctx.json_mode:
        return
    print()
    if ctx.colors_enabled:
        print(color(f"  {title}", "bold"))
        print(color("  " + "─" * min(len(title) + 2, ctx.width - 4), "muted"))
    else:
        print(f"  {title}")
        print("  " + "-" * min(len(title) + 2, ctx.width - 4))


def _print_kv(label: str, value: str, indent: int = 2, label_width: int = 22) -> None:
    """Print a key-value pair in two-column format.

    Format: "  label │ value" (with U+2502 box-drawing light vertical)
    Falls back to "  label: value" when colors disabled.
    """
    ctx = get_terminal_context()
    if ctx.json_mode:
        return

    prefix = " " * indent
    separator = " │ " if ctx.colors_enabled else ": "
    label_col = f"{label:<{label_width}}"

    if ctx.colors_enabled:
        label_colored = color(label_col, "muted")
        value_colored = color(value, "primary")
        print(f"{prefix}{label_colored}{separator}{value_colored}")
    else:
        print(f"{prefix}{label_col}{separator}{value}")


def _print_field_group(fields: list[tuple[str, str]], indent: int = 2, label_width: int = 22) -> None:
    """Print multiple key-value pairs as a group."""
    for label, value in fields:
        _print_kv(label, value, indent, label_width)


def _print_table(
    rows: list[dict],
    col_specs: list[dict],
    terminal_width: int | None = None,
) -> None:
    """Print a formatted table with dynamic column widths.

    Args:
        rows: List of dicts with column data
        col_specs: List of column spec dicts with keys:
            - key: dict key in row
            - ratio: proportional width (0-1)
            - min_width: minimum column width
            - align: "left" | "right" | "center"
            - color_fn: optional callable(row) -> color_key for row coloring
        terminal_width: Override terminal width (for testing)
    """
    ctx = get_terminal_context()
    if ctx.json_mode:
        return

    width = terminal_width or ctx.width
    # Reserve space for padding between columns
    available = width - TABLE_PADDING * (len(col_specs) - 1)

    ratios = [spec["ratio"] for spec in col_specs]
    min_widths = [spec.get("min_width", TABLE_MIN_COL_WIDTH) for spec in col_specs]
    col_widths = calculate_column_widths(available, ratios, min_widths)

    # Build format strings
    fmt_parts = []
    header_parts = []
    for i, spec in enumerate(col_specs):
        w = col_widths[i]
        align = spec.get("align", "left")
        if align == "right":
            fmt_parts.append(f"{{:{w}}}")
            header_parts.append(f"{{:>{w}}}")
        elif align == "center":
            fmt_parts.append(f"{{:^{w}}}")
            header_parts.append(f"{{:^{w}}}")
        else:
            fmt_parts.append(f"{{:<{w}}}")
            header_parts.append(f"{{:<{w}}}")

    row_fmt = (" " * TABLE_PADDING).join(fmt_parts)
    header_fmt = (" " * TABLE_PADDING).join(header_parts)

    # Print header
    headers = [spec.get("header", spec["key"].upper()) for spec in col_specs]
    print(header_fmt.format(*headers))

    # Print separator
    if ctx.colors_enabled:
        sep = "─"
    else:
        sep = "-"
    sep_line = (sep * width)[:width]
    print(color(sep_line, "muted") if ctx.colors_enabled else sep_line)

    # Print rows
    for row in rows:
        values = []
        row_colors = []
        for i, spec in enumerate(col_specs):
            key = spec["key"]
            val = row.get(key, "")
            if callable(val):
                val = val(row)
            values.append(str(val))
            # Check for row-level color function
            color_fn = spec.get("color_fn")
            if color_fn:
                row_colors.append(color_fn(row))
            else:
                row_colors.append(None)

        formatted = row_fmt.format(*values)

        # Apply row coloring if any column has color_fn
        if ctx.colors_enabled and any(row_colors):
            # Simple approach: color the whole row based on first color_fn
            # More sophisticated: would need per-cell coloring
            primary_color = next((c for c in row_colors if c), None)
            if primary_color:
                formatted = color(formatted, primary_color)

        print(formatted)


def _show_score_breakdown(topics: list[dict], weights: dict) -> None:
    """Show weighted score breakdown per topic."""
    if not topics:
        return

    print("\n  Score breakdown:")
    total_contribution = 0.0
    total_weight = 0.0
    for t in topics:
        score = t.get("score", 0)
        topic = t.get("topic", "")
        if _classify_topic(score) == "invalid":
            continue
        weight = weights.get(topic, 0.1)
        contribution = score * weight
        total_contribution += contribution
        total_weight += weight
        label = {
            "tech_stack": "Technical skills",
            "experience": "Experience",
            "projects": "Projects",
            "education": "Education",
            "english": "Language",
            "cultural_fit": "Industry fit",
        }.get(topic, topic)
        print(f"    {label:<20} {score:>3}% × {weight:.0%} weight = {contribution:.1f} contribution")

    total_pct = total_contribution / total_weight if total_weight else 0.0
    print(f"    {'':─<30}")
    print(f"    {'Total':<20} {total_pct:.1f}%")