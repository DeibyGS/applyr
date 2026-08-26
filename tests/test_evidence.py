"""Tests for the deterministic Evidence Graph parser (no LLM calls, ADR-011)."""

import pytest

from applyr.evidence import EvidenceClaim, is_evidenced, parse_evidence

SAMPLE_PROFILE = """\
## PROFESSIONAL SUMMARY
...
Backend developer focused on Python APIs.

## WORK EXPERIENCE

**Backend Developer — Acme Corp** — Remote — 01/2022-01/2025
- Built REST APIs with Python and FastAPI
- Reduced API latency by 42%

**Junior Developer — StartupX** — Onsite — 06/2020-12/2021
- Maintained a Django monolith

## PROJECTS

**JobTracker — Python, FastAPI, PostgreSQL** — github.com/example/jobtracker
- Personal project to track job applications

## EDUCATION

**BSc Computer Science — University X** — 09/2016-06/2020

## CERTIFICATIONS

- AWS Certified Developer — Amazon — 2023

## TECHNICAL SKILLS

Languages: Python, JavaScript
Backend: FastAPI, Django
Databases: PostgreSQL

## LANGUAGES

Spanish — Native
English — C1
"""


@pytest.mark.unit
class TestParseEntrySections:
    """WORK EXPERIENCE / PROJECTS / EDUCATION / CERTIFICATIONS: **Bold Title**
    starts an entry, bullets under it become claims tied to that entry."""

    def test_bullets_become_claims_with_entry_context(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        exp_claims = [c for c in claims if c.section == "experience"]
        assert exp_claims[0].text == "Built REST APIs with Python and FastAPI"
        assert exp_claims[0].entry_context == "Backend Developer — Acme Corp"
        assert exp_claims[1].text == "Reduced API latency by 42%"
        assert exp_claims[1].entry_context == "Backend Developer — Acme Corp"

    def test_second_entry_gets_its_own_context(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        exp_claims = [c for c in claims if c.section == "experience"]
        second_entry = [c for c in exp_claims if c.entry_context == "Junior Developer — StartupX"]
        assert len(second_entry) == 1
        assert second_entry[0].text == "Maintained a Django monolith"

    def test_claim_ids_are_stable_within_one_parse(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        exp_ids = [c.id for c in claims if c.section == "experience"]
        assert exp_ids == ["EXP-001-C01", "EXP-001-C02", "EXP-002-C01"]

    def test_tech_stack_in_bold_title_is_captured_as_entry_context(self):
        # PROJECTS entries put the stack in the bold title itself
        # ("**JobTracker — Python, FastAPI, PostgreSQL**"), not always
        # restated in a bullet — entry_context must carry it.
        claims = parse_evidence(SAMPLE_PROFILE)
        proj_claims = [c for c in claims if c.section == "project"]
        assert proj_claims[0].entry_context == "JobTracker — Python, FastAPI, PostgreSQL"

    def test_bullet_before_any_bold_title_gets_null_context(self):
        # CERTIFICATIONS in the sample has no bold-title entries at all.
        claims = parse_evidence(SAMPLE_PROFILE)
        cert_claims = [c for c in claims if c.section == "certification"]
        assert len(cert_claims) == 1
        assert cert_claims[0].entry_context is None
        assert "AWS Certified Developer" in cert_claims[0].text


@pytest.mark.unit
class TestParseFlatSections:
    """TECHNICAL SKILLS / LANGUAGES: comma- or line-separated tokens, no
    entry/bullet structure required."""

    def test_technical_skills_split_on_comma_across_lines(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        skill_texts = {c.text for c in claims if c.section == "skill"}
        assert skill_texts == {"Python", "JavaScript", "FastAPI", "Django", "PostgreSQL"}

    def test_category_label_stripped_for_skills(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        skill_texts = {c.text for c in claims if c.section == "skill"}
        assert "Languages: Python" not in skill_texts
        assert "Backend: FastAPI" not in skill_texts

    def test_languages_are_line_separated_without_colon_stripping(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        lang_texts = {c.text for c in claims if c.section == "language"}
        assert lang_texts == {"Spanish — Native", "English — C1"}


@pytest.mark.unit
class TestParserTolerance:
    """cv-master.md is free text a human edits, not a validated schema —
    deviations must degrade to fewer claims, never raise."""

    def test_missing_section_is_skipped_silently(self):
        profile = "## WORK EXPERIENCE\n\n**Backend Developer — Acme**\n- Built APIs\n"
        claims = parse_evidence(profile)
        assert all(c.section != "certification" for c in claims)
        assert len(claims) == 1

    def test_stray_prose_line_is_ignored_not_crash(self):
        profile = (
            "## WORK EXPERIENCE\n\n"
            "Some leftover prose that matches no pattern.\n"
            "**Backend Developer — Acme**\n"
            "- Built APIs\n"
        )
        claims = parse_evidence(profile)
        assert len(claims) == 1
        assert claims[0].text == "Built APIs"

    def test_leftover_template_ellipsis_line_is_ignored(self):
        profile = "## TECHNICAL SKILLS\n...\nPython, FastAPI\n"
        claims = parse_evidence(profile)
        assert {c.text for c in claims} == {"Python", "FastAPI"}

    def test_empty_profile_returns_no_claims(self):
        assert parse_evidence("") == []

    def test_unrecognized_section_heading_is_ignored(self):
        profile = "## HOBBIES\n- Chess\n- Painting\n"
        assert parse_evidence(profile) == []


@pytest.mark.unit
class TestIsEvidenced:
    """Alias-aware substring matching — deliberately not fuzzy (ADR-011)."""

    def test_direct_term_match(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        assert is_evidenced("FastAPI", claims) is True

    def test_alias_form_in_master_matches_canonical_query(self):
        claims = [EvidenceClaim(id="SKILL-001", section="skill", text="Amazon Web Services", entry_context=None)]
        assert is_evidenced("AWS", claims) is True

    def test_canonical_form_in_master_matches_alias_query(self):
        claims = [EvidenceClaim(id="SKILL-001", section="skill", text="AWS", entry_context=None)]
        assert is_evidenced("Amazon Web Services", claims) is True

    def test_term_absent_from_evidence_is_not_evidenced(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        assert is_evidenced("Kubernetes", claims) is False

    def test_matches_against_entry_context_not_just_text(self):
        # The project's tech stack lives in the bold title (entry_context),
        # not restated in every bullet under it.
        claims = parse_evidence(SAMPLE_PROFILE)
        assert is_evidenced("PostgreSQL", claims) is True

    def test_no_fuzzy_matching_for_unrelated_terms(self):
        claims = parse_evidence(SAMPLE_PROFILE)
        assert is_evidenced("Golang", claims) is False

    def test_short_alias_does_not_substring_match_inside_unrelated_word(self):
        # "JS" is a substring of "JSON", "TS" is a substring of "results" —
        # a bare `in` check would false-positive-match both. Confirmed
        # exploit via /code-review before this fix.
        claims = [EvidenceClaim(id="SKILL-001", section="skill", text="Python, FastAPI, JSON, Django", entry_context=None)]
        assert is_evidenced("JavaScript", claims) is False
        metric_claim = [EvidenceClaim(id="EXP-001-C01", section="experience",
                                       text="Reduced test results turnaround time by 40%", entry_context=None)]
        assert is_evidenced("TypeScript", metric_claim) is False
