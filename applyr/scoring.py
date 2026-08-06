"""Scoring engine — configurable weighted compatibility calculation."""

from applyr.config import load_config
from applyr.constants import DEFAULT_TOPIC_WEIGHT


def calculate_score(topics: dict) -> int:
    """Calculate weighted compatibility score from topic scores.

    Args:
        topics: dict like {"tech_stack": {"score": 80, "detail": "..."}, ...}

    Returns:
        Weighted score 0-100, or 0 if no valid topics provided.
    """
    if not topics:
        return 0

    config = load_config()
    weights = config["weights"]

    weighted_sum = 0.0
    total_weight = 0.0

    for topic, values in topics.items():
        score = values.get("score", 0)
        if not isinstance(score, (int, float)) or not 0 <= score <= 100:
            continue
        weight = weights.get(topic, DEFAULT_TOPIC_WEIGHT)
        weighted_sum += score * weight
        total_weight += weight

    if total_weight == 0:
        return 0

    return round(weighted_sum / total_weight)
