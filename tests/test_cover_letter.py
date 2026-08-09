"""Tests for cover letter generation."""

import pytest
from applyr.cv import generate_cover_letter


class TestGenerateCoverLetter:
    """Tests for generate_cover_letter()."""

    def test_generates_cover_letter(self):
        offer_data = {
            "title": "Full Stack Developer",
            "company": "Acme Corp",
            "tech_stack": "Python, React, Node.js",
            "summary": "Build modern web applications"
        }
        cv_master = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+34 600 000 000",
            "skills": "Python, React, Node.js, TypeScript",
            "projects": [
                {"name": "Project A", "description": "Built REST API with Python"},
                {"name": "Project B", "description": "Developed React dashboard"}
            ]
        }
        result = generate_cover_letter(offer_data, cv_master)
        assert "Acme Corp" in result
        assert "Full Stack Developer" in result
        assert "John Doe" in result

    def test_includes_achievements(self):
        offer_data = {
            "title": "Backend Developer",
            "company": "TechCo",
            "tech_stack": "Python, FastAPI",
            "summary": "Build APIs"
        }
        cv_master = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "+34 600 111 222",
            "skills": "Python, FastAPI, PostgreSQL",
            "projects": [
                {"name": "API Project", "description": "Built high-performance API serving 10K requests/day"}
            ]
        }
        result = generate_cover_letter(offer_data, cv_master)
        assert "10K requests" in result or "API" in result

    def test_empty_offer(self):
        offer_data = {}
        cv_master = {"name": "Test", "email": "test@test.com"}
        result = generate_cover_letter(offer_data, cv_master)
        assert "Test" in result
