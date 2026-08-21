"""Shared helpers used across multiple commands modules."""

from datetime import date

from applyr.constants import PROGRESS_BAR_WIDTH
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


def _bar(score: int, width: int = PROGRESS_BAR_WIDTH) -> str:
    """Render a simple ASCII progress bar for a 0-100 score."""
    filled = round(score * width / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _truncate(text: str | None, max_len: int) -> str:
    """Truncate a string to max_len characters, appending ellipsis if needed."""
    if not text:
        return ""
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


def _classify_icon(classification: str) -> str:
    """Get icon for classification."""
    icons = {
        "strong": "✓",
        "partial": "△",
        "missing": "✕",
    }
    return icons.get(classification, "?")


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
            # Same exclusion calculate_score() and the Strong/Partial/Missing
            # breakdown already apply — an out-of-range score must not shift
            # Total away from the compatibility% shown next to it (it could
            # even push Total above 100%).
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

    # Divide by total_weight actually used (not 100%) so this matches
    # calculate_score() — omitting topics is expected (see scoring rubric),
    # and a raw sum of contributions silently diverges from the compatibility
    # percentage shown above whenever fewer than all topics are scored.
    total_pct = total_contribution / total_weight if total_weight else 0.0
    print(f"    {'':─<30}")
    print(f"    {'Total':<20} {total_pct:.1f}%")
