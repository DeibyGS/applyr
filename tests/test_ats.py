"""Tests for ATS compatibility checking."""

import pytest
from applyr.ats import (
    validate_ats_format,
    extract_keywords,
    match_keywords,
    ATSIssue,
    ATSReport,
    KeywordMatch,
    KeywordReport,
)


class TestValidateATSFormat:
    """Tests for validate_ats_format()."""

    def test_clean_cv_passes(self):
        cv = """# John Doe

john@email.com | +34 600 000 000

## Professional Summary

Full stack developer with 5 years experience.

## Work Experience

### Developer - Company, Madrid
01/2020 - 12/2023

- Built REST APIs with Python
- Led team of 3 developers

## Education

### Computer Science Degree
University of Madrid | 2016 - 2020

## Technical Skills

**Backend:** Python, Node.js
**Frontend:** React, TypeScript
"""
        report = validate_ats_format(cv)
        assert report.score >= 80
        assert report.format_ok is True

    def test_tables_detected(self):
        cv = """# John Doe

## Skills

| Skill | Level |
|-------|-------|
| Python | Expert |
| React | Advanced |
"""
        report = validate_ats_format(cv)
        assert report.score < 80
        assert report.format_ok is False
        assert any("Tables" in i.message for i in report.issues)

    def test_images_detected(self):
        cv = """# John Doe

![Photo](photo.png)

## Professional Summary

Developer.
"""
        report = validate_ats_format(cv)
        assert report.format_ok is False
        assert any("Images" in i.message for i in report.issues)

    def test_non_standard_headers(self):
        cv = """# John Doe

## About Me

Developer with experience.

## My Journey

Worked at companies.
"""
        report = validate_ats_format(cv)
        assert report.headers_ok is False
        assert any("non-standard" in i.message.lower() for i in report.issues)

    def test_contact_in_footer(self):
        cv = """# John Doe

## Professional Summary

Developer.

## Work Experience

### Developer - Company
01/2020 - 12/2023

- Built APIs

## Technical Skills

Python, React

---

john@email.com | linkedin.com/in/johndoe
"""
        report = validate_ats_format(cv)
        assert any("Contact info" in i.message for i in report.issues)


class TestExtractKeywords:
    """Tests for extract_keywords()."""

    def test_from_tech_stack(self):
        offer = {"tech_stack": "Python, React, Node.js"}
        keywords = extract_keywords(offer)
        assert "python" in keywords
        assert "react" in keywords
        assert "node.js" in keywords

    def test_from_title(self):
        offer = {"title": "Full Stack Developer"}
        keywords = extract_keywords(offer)
        assert "full" not in keywords  # skip word
        assert "stack" not in keywords  # skip word
        assert "developer" not in keywords  # skip word

    def test_empty_offer(self):
        offer = {}
        keywords = extract_keywords(offer)
        assert keywords == []


class TestMatchKeywords:
    """Tests for match_keywords()."""

    def test_all_matched(self):
        cv = "Python developer with React and Node.js experience"
        keywords = ["python", "react", "node.js"]
        report = match_keywords(cv, keywords)
        assert report.match_rate == 100.0
        assert len(report.matched) == 3
        assert len(report.missing) == 0

    def test_partial_match(self):
        cv = "Python developer with FastAPI"
        keywords = ["python", "react", "node.js"]
        report = match_keywords(cv, keywords)
        assert report.match_rate < 100.0
        assert len(report.matched) == 1
        assert len(report.missing) == 2

    def test_no_match(self):
        cv = "Java developer with Spring"
        keywords = ["python", "react"]
        report = match_keywords(cv, keywords)
        assert report.match_rate == 0.0
        assert len(report.matched) == 0
        assert len(report.missing) == 2

    def test_empty_keywords(self):
        cv = "Python developer"
        report = match_keywords(cv, [])
        assert report.match_rate == 0.0

    def test_case_insensitive(self):
        cv = "PYTHON Developer with React"
        keywords = ["python", "react"]
        report = match_keywords(cv, keywords)
        assert report.match_rate == 100.0
