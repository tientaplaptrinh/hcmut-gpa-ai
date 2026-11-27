"""Pytest verification of crawled real HCMUT curricula & Course Difficulty Predictor."""

from __future__ import annotations

import re

from backend.difficulty_model import build_difficulty_dashboard
from backend.main import list_all_majors, load_curriculum


REQUIRED_MAJORS = [
    "7520201",
    "7520207",
    "7520216",
    "75202TT",
    "75202a1",
    "7480101",
]

REQUIRED_COHORTS = ["K2021", "K2022", "K2023", "K2024", "K2025", "K2026"]

VALID_BLOCKS = {
    "Toán & KHTN",
    "Giáo dục chung",
    "Cơ sở ngành",
    "Chuyên ngành",
    "Tốt nghiệp",
}


def test_all_six_hcmut_majors_and_cohorts_cached():
    majors = list_all_majors()
    loaded_codes = {m.major_code for m in majors}
    for req_code in REQUIRED_MAJORS:
        assert req_code in loaded_codes, f"Missing required HCMUT major {req_code}"

    for mcode in REQUIRED_MAJORS:
        for cohort in REQUIRED_COHORTS:
            curr = load_curriculum(mcode, cohort)
            assert curr.major_code == mcode
            assert curr.cohort == cohort
            assert len(curr.courses) >= 35, f"Too few courses in {mcode} {cohort}"
            assert 120 <= curr.total_credits <= 165
            assert 115 <= curr.total_gpa_credits <= 165

            for c in curr.courses:
                assert re.match(r"^[A-Z]{2,3}\d{4}$", c.course_code), f"Invalid code {c.course_code}"
                assert c.credits >= 0
                assert c.knowledge_block in VALID_BLOCKS, f"Invalid block {c.knowledge_block}"
                assert 1 <= c.recommended_semester <= 10


def test_difficulty_predictor_priors_and_user_overrides():
    curr = load_curriculum("7520201", "K2025")
    dash = build_difficulty_dashboard(curr)

    assert dash.major_code == "7520201"
    assert len(dash.courses) == len(curr.courses)
    assert len(dash.top_gatekeeper_courses) == 5
    assert len(dash.semester_trends) >= 6

    by_code = {p.course_code: p for p in dash.courses}
    for p in dash.courses:
        assert 1.0 <= p.ai_difficulty_score <= 10.0
        assert p.tier in ("Dễ", "Trung bình", "Khó", "Rất khó")
        assert len(p.rationale_vi) >= 20

    # Verify domain calibration: Calculus / Core Engineering strictly harder than Political Philosophy
    if "MT1005" in by_code and "SP1031" in by_code:
        assert by_code["MT1005"].ai_difficulty_score >= 8.0
        assert by_code["SP1031"].ai_difficulty_score <= 5.0
        assert by_code["MT1005"].ai_difficulty_score > by_code["SP1031"].ai_difficulty_score + 2.5

    # Verify user difficulty override dynamically updates score and tier
    sample_code = dash.courses[0].course_code
    dash_override = build_difficulty_dashboard(curr, {sample_code: 9.4})
    overridden = next(p for p in dash_override.courses if p.course_code == sample_code)
    assert overridden.user_override_score == 9.4
    assert overridden.effective_difficulty_score == 9.4
    assert overridden.tier == "Rất khó"
