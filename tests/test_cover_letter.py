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


class TestCoverLetterNeverClaimsAbsentSkills:
    """The letter took the offer's first three technologies verbatim and wrote
    "my background in <them>" — with no reference to the candidate at all. On a
    real vacancy that produced "my skills in React.js, Redux, Hooks" for a
    profile containing no Redux anywhere. A cover letter is sent to an employer,
    so an invented skill is a false claim made on the candidate's behalf."""

    OFFER = {
        "title": "Frontend Engineer",
        "company": "Acme",
        "tech_stack": "React.js, Redux, Webpack, JavaScript, CSS",
    }
    PROFILE = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+34 600 000 000",
        "skills": "",
        "projects": [],
        "raw": "# Jane Doe\n\nFrontend work with React.js, JavaScript and CSS.\n",
    }

    def _letter(self, **overrides):
        from applyr.cv import generate_cover_letter

        return generate_cover_letter({**self.OFFER, **overrides}, self.PROFILE)

    def test_absent_skills_are_never_claimed(self):
        letter = self._letter()
        assert "Redux" not in letter
        assert "Webpack" not in letter

    def test_evidenced_skills_are_claimed(self):
        letter = self._letter()
        assert "React.js" in letter

    def test_no_overlap_falls_back_instead_of_inventing(self):
        """An offer sharing nothing with the profile must not name its stack."""
        letter = self._letter(tech_stack="COBOL, Fortran")
        assert "COBOL" not in letter
        assert "Fortran" not in letter
        assert "relevant technologies" in letter

    def test_an_offer_without_a_stack_still_produces_a_letter(self):
        letter = self._letter(tech_stack="")
        assert "relevant technologies" in letter
