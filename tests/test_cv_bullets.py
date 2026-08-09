"""Tests for bullet point optimization."""

import pytest
from applyr.cv import analyze_bullets, suggest_improvements


class TestAnalyzeBullets:
    """Tests for analyze_bullets()."""

    def test_detects_weak_verbs(self):
        bullets = [
            "Responsible for managing the team",
            "Worked on the project",
            "Helped with documentation"
        ]
        result = analyze_bullets(bullets)
        assert len(result["weak"]) == 3
        assert any("responsible for" in w["original"].lower() for w in result["weak"])

    def test_detects_strong_bullets(self):
        bullets = [
            "Increased sales by 30% in Q2",
            "Led team of 8 developers, reducing delivery time by 25%",
            "Built REST API serving 1000+ requests/day"
        ]
        result = analyze_bullets(bullets)
        assert len(result["strong"]) == 3

    def test_detects_missing_metrics(self):
        bullets = [
            "Developed new features"
        ]
        result = analyze_bullets(bullets)
        assert len(result["no_metrics"]) == 1

    def test_empty_bullets(self):
        result = analyze_bullets([])
        assert result["weak"] == []
        assert result["strong"] == []
        assert result["no_metrics"] == []


class TestSuggestImprovements:
    """Tests for suggest_improvements()."""

    def test_suggests_strong_verbs(self):
        bullet = "Responsible for managing the project"
        suggestions = suggest_improvements(bullet)
        assert len(suggestions) > 0
        assert any("Orchestrated" in s["suggestion"] or "Led" in s["suggestion"] for s in suggestions)

    def test_detects_metric_opportunity(self):
        bullet = "Improved performance of the application"
        suggestions = suggest_improvements(bullet)
        assert any("metric" in s["type"] for s in suggestions)

    def test_strong_bullet_no_suggestions(self):
        bullet = "Increased sales by 30% in Q2, generating €50K additional revenue"
        suggestions = suggest_improvements(bullet)
        assert len(suggestions) == 0
