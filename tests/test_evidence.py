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

    def test_entry_with_no_bullets_or_labels_still_produces_a_claim(self):
        # EDUCATION entries are often just "**Degree**" + a plain
        # institution/dates prose line, with no bullets and no "Stack:"-like
        # labeled line. Without a fallback claim, entry_context would attach
        # to nothing — invisible to any later check (e.g. cv.py's
        # employer/title verification) even though it's a real fact.
        # Confirmed live against a real cv-master.md: "Máster en AI
        # Engineer" was silently unmatchable until this fix.
        profile = (
            "## EDUCATION\n\n"
            "**Grado Superior — DAM**\n"
            "The Power · Madrid · 02/2024 – 06/2026\n\n"
            "**Máster en AI Engineer**\n"
            "The Power · Madrid · 08/2026 – en curso\n"
        )
        claims = parse_evidence(profile)
        contexts = {c.entry_context for c in claims}
        assert "Grado Superior — DAM" in contexts
        assert "Máster en AI Engineer" in contexts
        # The synthetic claim's own text is the entry title itself.
        master_claim = next(c for c in claims if c.entry_context == "Máster en AI Engineer")
        assert master_claim.text == "Máster en AI Engineer"

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


REAL_WORLD_PROFILE = """\
## EXPERIENCIA PROFESIONAL

### Backend Developer
**Acme Corp** · Madrid · Remoto · 01/2022 – 01/2025

Desarrollo de APIs internas para el equipo de pagos.

- Built REST APIs with Python and FastAPI
- Reduced latency by 42%

**Stack:** Python · FastAPI (async) · PostgreSQL · Docker

---

### Freelance Project
Repo: github.com/example/thing

## PROYECTOS

### RAG Pipeline — PDF search
Stack: Python · LangChain · ChromaDB · Google Gemini API
Ingesta de documentos y busqueda semantica con recuperacion aumentada.

## HABILIDADES TECNICAS

**Backend**
Python · FastAPI · Node.js

**IA**
LangChain · RAG · MCP
"""


@pytest.mark.unit
class TestRealWorldStructureVariants:
    """Patterns found in a real, Spanish-language cv-master.md that don't
    match cv-master-template.md's single-line "**Title — Company**"
    convention: Spanish section names, a "### Title" + "**Company**" split
    across two lines, a "Stack:"/"**Stack:**" labeled fact list attached to
    the current entry (not a new empty entry), and "·"-separated skills."""

    def test_spanish_section_names_are_recognized(self):
        claims = parse_evidence(REAL_WORLD_PROFILE)
        assert any(c.section == "experience" for c in claims)
        assert any(c.section == "project" for c in claims)
        assert any(c.section == "skill" for c in claims)

    def test_h3_title_and_bold_company_merge_into_one_entry_context(self):
        claims = parse_evidence(REAL_WORLD_PROFILE)
        exp_claims = [c for c in claims if c.section == "experience"]
        assert exp_claims[0].entry_context == "Backend Developer — Acme Corp"

    def test_stack_label_line_produces_claims_not_a_new_empty_entry(self):
        claims = parse_evidence(REAL_WORLD_PROFILE)
        acme_claims = [c for c in claims if c.entry_context == "Backend Developer — Acme Corp"]
        # Bullets AND the Stack: line's tokens all belong to this ONE entry —
        # the Stack line must not have started a second, separate
        # "Stack:"-titled entry (no claim should have entry_context "Stack").
        texts = {c.text for c in acme_claims}
        assert "PostgreSQL" in texts
        assert "FastAPI (async)" in texts
        assert not any(c.entry_context == "Stack" for c in claims)

    def test_lone_h3_project_entry_with_plain_stack_line(self):
        # PROJECTS-style: "### Name" alone, no bold company line, a PLAIN
        # (non-bold) "Stack:" line, and prose instead of bullets.
        claims = parse_evidence(REAL_WORLD_PROFILE)
        proj_claims = [c for c in claims if c.section == "project"]
        assert proj_claims, "expected claims from the lone-### PROJECTS entry"
        assert all(c.entry_context == "RAG Pipeline — PDF search" for c in proj_claims)
        assert any(c.text == "LangChain" for c in proj_claims)

    def test_middle_dot_separated_skills_split_into_individual_claims(self):
        claims = parse_evidence(REAL_WORLD_PROFILE)
        skill_texts = {c.text for c in claims if c.section == "skill"}
        assert {"Python", "FastAPI", "Node.js", "LangChain", "RAG", "MCP"} <= skill_texts

    def test_bold_category_header_markers_are_stripped(self):
        claims = parse_evidence(REAL_WORLD_PROFILE)
        skill_texts = {c.text for c in claims if c.section == "skill"}
        assert "**Backend**" not in skill_texts
        assert "**IA**" not in skill_texts

    def test_real_world_terms_are_evidenced(self):
        claims = parse_evidence(REAL_WORLD_PROFILE)
        for term in ("Python", "FastAPI", "PostgreSQL", "LangChain", "RAG", "MCP"):
            assert is_evidenced(term, claims), f"{term} should be evidenced"
        assert is_evidenced("Kubernetes", claims) is False


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

    def test_short_alias_does_not_match_inside_unrelated_word(self):
        # Regression: a plain `in` substring check let "TS" (alias of
        # TypeScript) match inside "costs" — confirmed live via /code-review.
        claims = [EvidenceClaim(id="X", section="experience",
                                 text="Reduced infrastructure costs significantly", entry_context=None)]
        assert is_evidenced("TS", claims) is False

    def test_metric_does_not_match_inside_a_longer_number(self):
        # Regression: "99%" substring-matched inside "199%".
        claims = [EvidenceClaim(id="X", section="experience", text="Grew revenue by 199%", entry_context=None)]
        assert is_evidenced("99%", claims) is False

    def test_symbol_suffixed_term_still_matches_at_a_real_boundary(self):
        # The alphanumeric-boundary fix must not accidentally stop matching
        # terms that legitimately end in a non-word character.
        claims = [EvidenceClaim(id="X", section="skill", text="C++", entry_context=None)]
        assert is_evidenced("C++", claims) is True


@pytest.mark.unit
class TestIsEvidencedCompoundTerms:
    """Regression: confirmed 3 of 5 live-tested offers had a multi-word
    offer term ("agentes IA", "agentes de IA") under-credited because the
    candidate's own wording states the same fact with different filler
    words around it ("...entornos de desarrollo con agentes...")."""

    def test_spanish_compound_term_matches_when_words_co_occur_in_one_claim(self):
        # Different filler words around the same two significant words,
        # both present in the SAME claim — this is what the compound
        # fallback exists for.
        claims = [EvidenceClaim(id="X", section="experience",
                                 text="Desarrollo de agentes basados en modelos de IA",
                                 entry_context=None)]
        assert is_evidenced("agentes IA", claims) is True
        assert is_evidenced("agentes de IA", claims) is True

    def test_significant_words_scattered_across_different_claims_do_not_count(self):
        # Regression (confirmed via /code-review): "agentes" evidenced by
        # one claim and "IA" by a totally unrelated one must NOT credit
        # "agentes de IA" — the words have to co-occur in one real claim,
        # not just each be true somewhere in the graph independently.
        claims = [
            EvidenceClaim(id="X", section="experience",
                          text="Coordinacion de agentes de ventas en call center", entry_context=None),
            EvidenceClaim(id="Y", section="certification",
                          text="Curso de IA para principiantes", entry_context=None),
        ]
        assert is_evidenced("agentes de IA", claims) is False

    def test_shared_entry_context_does_not_bridge_unrelated_bullets(self):
        # Regression (confirmed via /code-review): entry_context is shared
        # across every bullet under the same entry — a naive "claim.text +
        # entry_context" haystack per bullet let a compound term borrow one
        # word from the entry's own title/company (never a real skill claim)
        # and an unrelated word from a sibling bullet under the same entry.
        # A company literally named "Kubernetes Solutions Inc" must not
        # credit a fabricated "Kubernetes Python" claim just because
        # "Python" appears in an unrelated bullet under that same job.
        claims = parse_evidence(
            "## WORK EXPERIENCE\n\n"
            "**Backend Developer — Kubernetes Solutions Inc**\n"
            "- Wrote unit tests in Python\n"
            "- Documented API endpoints\n"
        )
        assert is_evidenced("Kubernetes Python", claims) is False

    def test_every_significant_word_must_be_evidenced_not_just_one(self):
        # "Machine" alone being evidenced must not be enough to credit
        # "Machine Learning" — every non-connector word is required.
        claims = [EvidenceClaim(id="X", section="skill", text="Machine repair certification", entry_context=None)]
        assert is_evidenced("Machine Learning", claims) is False

    def test_significant_words_true_independently_but_never_together_do_not_count(self):
        # Regression (confirmed via /code-review): "Machine" evidenced by
        # one unrelated claim and "Learning" by a different unrelated claim
        # must not credit "Machine Learning" — same co-occurrence
        # requirement as the Spanish case above, in English.
        claims = [
            EvidenceClaim(id="X", section="experience",
                          text="Virtual Machine administration", entry_context=None),
            EvidenceClaim(id="Y", section="certification",
                          text="E-Learning platform, Coursera certificate", entry_context=None),
        ]
        assert is_evidenced("Machine Learning", claims) is False

    def test_short_significant_word_is_not_dropped_by_length_cutoff(self):
        # Regression (confirmed via /code-review): a >= 3 length cutoff
        # dropped "IA"/"AI"/"ML" entirely, so a compound term's only
        # remaining "significant" word could be a generic leftover with no
        # actual AI-context confirmation. >= 2 keeps these short but real
        # distinguishing words in the check.
        claims = [EvidenceClaim(id="X", section="skill", text="Python, AI agents with LangChain",
                                 entry_context=None)]
        assert is_evidenced("AI agents", claims) is True
        no_ai_claims = [EvidenceClaim(id="X", section="skill", text="Python agents with LangChain",
                                       entry_context=None)]
        assert is_evidenced("AI agents", no_ai_claims) is False

    def test_translation_gap_still_correctly_fails(self):
        # "GenAI" and "Agentic AI" are different words from "IA Generativa"/
        # "agentes" entirely — not the same words in different order — so
        # the compound fallback must not paper over an actual translation
        # or terminology gap.
        claims = [EvidenceClaim(id="X", section="skill", text="IA Generativa, agentes", entry_context=None)]
        assert is_evidenced("GenAI", claims) is False
        assert is_evidenced("Agentic AI", claims) is False

    def test_different_specific_product_still_correctly_fails(self):
        # A fabricated "GitHub Copilot" claim must not pass just because the
        # candidate has SOME AI pair-programming tool evidenced.
        claims = [EvidenceClaim(id="X", section="skill", text="Claude Code, OpenCode", entry_context=None)]
        assert is_evidenced("GitHub Copilot", claims) is False

    def test_connector_words_in_the_query_do_not_need_their_own_evidence(self):
        # The query term "Fast and Reliable" contains a connector word
        # ("and") that never appears in the claim at all — only "Fast" and
        # "Reliable" (the significant words) need to be independently
        # evidenced, matching how "de"/"IA" are skipped in "agentes de IA".
        claims = [EvidenceClaim(id="X", section="experience",
                                 text="Delivered Fast, Reliable systems for internal tooling",
                                 entry_context=None)]
        assert is_evidenced("Fast and Reliable", claims) is True
