"""Pytest MILP Joint Study Roadmap Proofs & FastAPI Endpoint Verification."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.contracts import (
    CourseItem,
    CurriculumSchema,
    RoadmapOptimizationRequest,
    StudentCourseRecord,
)
from backend.main import app, load_curriculum
from backend.roadmap_optimizer import optimize_study_roadmap


def _build_controlled_hcmut_curriculum() -> CurriculumSchema:
    """Controlled 40-credit HCMUT mini-curriculum for crisp mathematical MILP proof checks."""
    courses = [
        # Completed courses (20 TC): 3 easy courses with C/D+ and 3 core courses with A -> GPA = 3.20
        CourseItem(course_code="SP1031", course_name="Triết học Mác - Lênin", credits=3, knowledge_block="Giáo dục chung", recommended_semester=1),
        CourseItem(course_code="SP1033", course_name="Kinh tế chính trị Mác - Lênin", credits=2, knowledge_block="Giáo dục chung", recommended_semester=2),
        CourseItem(course_code="EE1001", course_name="Nhập môn về kỹ thuật", credits=3, knowledge_block="Giáo dục chung", recommended_semester=1),
        CourseItem(course_code="MT1003", course_name="Giải tích 1", credits=4, knowledge_block="Toán & KHTN", recommended_semester=1),
        CourseItem(course_code="PH1003", course_name="Vật lý 1", credits=4, knowledge_block="Toán & KHTN", recommended_semester=1),
        CourseItem(course_code="EE2033", course_name="Giải tích mạch", credits=4, knowledge_block="Cơ sở ngành", recommended_semester=3),
        # Remaining courses (20 TC): mostly very hard D >= 8.5 courses + capstone
        CourseItem(course_code="EE2009", course_name="Trường điện từ", credits=4, knowledge_block="Cơ sở ngành", recommended_semester=4, prerequisites=["PH1003", "MT1003"]),
        CourseItem(course_code="EE3011", course_name="Điện tử công suất", credits=4, knowledge_block="Chuyên ngành", recommended_semester=5, prerequisites=["EE2033"]),
        CourseItem(course_code="EE3019", course_name="Giải tích hệ thống điện", credits=4, knowledge_block="Chuyên ngành", recommended_semester=6, prerequisites=["EE2033"]),
        CourseItem(course_code="EE2039", course_name="Xử lý tín hiệu số", credits=4, knowledge_block="Cơ sở ngành", recommended_semester=5),
        CourseItem(course_code="EE4339", course_name="Đồ án tốt nghiệp", credits=4, knowledge_block="Tốt nghiệp", recommended_semester=8, requires_min_c=True),
    ]
    return CurriculumSchema(
        major_code="7520201",
        major_name="Kỹ thuật Điện",
        faculty="Khoa Điện - Điện tử",
        cohort="K2025",
        apply_year=2025,
        total_credits=40,
        total_gpa_credits=40,
        required_elective_credits=0,
        source_url="https://hcmut.edu.vn/study/handbook/course/undergraduate/7520201",
        crawled_at="2026-11-27T00:00:00Z",
        courses=courses,
    )


def test_milp_scenario_320_to_360_hybrid_beats_forward_only():
    """Scenario 3.20 -> 3.60:
    Completed = 20 TC with points:
      SP1031 (3 TC, D+ = 1.5 -> 4.5)
      SP1033 (2 TC, C  = 2.0 -> 4.0)
      EE1001 (3 TC, C+ = 2.5 -> 7.5)
      MT1003 (4 TC, A  = 4.0 -> 16.0)
      PH1003 (4 TC, A  = 4.0 -> 16.0)
      EE2033 (4 TC, A  = 4.0 -> 16.0)
    Total completed = 20 TC, 64.0 pts -> Current GPA = exactly 3.20!
    Remaining = 20 TC of very hard courses (D >= 8.2).
    Target = 3.60 (needs 144.0 pts -> Forward-Only needs 80.0 pts on 20 TC = 4.0 A on ALL 5 hard courses!).
    Hybrid retakes easy SP1031/SP1033/EE1001 -> slashes effort & lowers required grades on hard courses!
    """
    curr = _build_controlled_hcmut_curriculum()
    completed = [
        StudentCourseRecord(course_code="SP1031", credits=3, score_10=5.2),  # D+ (1.5)
        StudentCourseRecord(course_code="SP1033", credits=2, score_10=5.8),  # C  (2.0)
        StudentCourseRecord(course_code="EE1001", credits=3, score_10=6.6),  # C+ (2.5)
        StudentCourseRecord(course_code="MT1003", credits=4, score_10=8.8),  # A  (4.0)
        StudentCourseRecord(course_code="PH1003", credits=4, score_10=8.7),  # A  (4.0)
        StudentCourseRecord(course_code="EE2033", credits=4, score_10=8.9),  # A  (4.0)
    ]

    res = optimize_study_roadmap(
        curr,
        RoadmapOptimizationRequest(
            major_code="7520201",
            cohort="K2025",
            completed_courses=completed,
            target_gpa=3.60,
            max_retake_courses=3,
            preference_mode="BALANCED",
        ),
    )

    assert res.current_gpa_4 == 3.20
    assert res.total_curriculum_gpa_credits == 40  # No double-counted credits!

    fwd = next(s for s in res.strategies if s.strategy_id == "FORWARD_ONLY")
    hyb = next(s for s in res.strategies if s.strategy_id == "HYBRID_OPTIMAL")

    assert fwd.feasible is True
    assert hyb.feasible is True
    assert fwd.projected_gpa_4 >= 3.60
    assert hyb.projected_gpa_4 >= 3.60

    # Hybrid strictly reduces total effort vs Forward-Only
    assert hyb.total_effort_score < fwd.total_effort_score
    assert hyb.effort_reduction_pct_vs_forward >= 10.0
    assert res.recommended_strategy_id == "HYBRID_OPTIMAL"
    assert hyb.is_recommended is True

    # Selects high-ROI easier retakes (SP1031 / SP1033 / EE1001)
    retake_codes = {r.course_code for r in hyb.retake_recommendations}
    assert len(retake_codes) >= 1
    assert retake_codes.issubset({"SP1031", "SP1033", "EE1001"})

    # Lowers required grades on the hardest remaining courses (EE2009 Trường điện từ < 4.0)
    assert hyb.hard_courses_requiring_a < fwd.hard_courses_requiring_a
    ee2009_fwd = next(r for r in fwd.remaining_course_plans if r.course_code == "EE2009")
    ee2009_hyb = next(r for r in hyb.remaining_course_plans if r.course_code == "EE2009")
    assert ee2009_fwd.required_gpa_4 == 4.0
    assert ee2009_hyb.required_gpa_4 < 4.0


def test_milp_scenario_infeasible_forward_only_but_feasible_with_retakes():
    curr = _build_controlled_hcmut_curriculum()
    # Current points = 20 TC with lower grades -> 54.0 pts (GPA = 2.70)
    # Max Forward-Only = (54.0 + 20*4.0) / 40 = 134.0 / 40 = 3.35 < Target 3.55!
    completed = [
        StudentCourseRecord(course_code="SP1031", credits=3, score_10=5.0),  # D+ (1.5) -> 4.5
        StudentCourseRecord(course_code="SP1033", credits=2, score_10=4.5),  # D  (1.0) -> 2.0
        StudentCourseRecord(course_code="EE1001", credits=3, score_10=5.2),  # D+ (1.5) -> 4.5
        StudentCourseRecord(course_code="MT1003", credits=4, score_10=8.0),  # B+ (3.5) -> 14.0
        StudentCourseRecord(course_code="PH1003", credits=4, score_10=8.0),  # B+ (3.5) -> 14.0
        StudentCourseRecord(course_code="EE2033", credits=4, score_10=8.2),  # B+ (3.5) -> 14.0 -> sum=53.0
    ]

    res = optimize_study_roadmap(
        curr,
        RoadmapOptimizationRequest(
            major_code="7520201",
            cohort="K2025",
            completed_courses=completed,
            target_gpa=3.55,
            max_retake_courses=3,
            preference_mode="BALANCED",
        ),
    )

    fwd = next(s for s in res.strategies if s.strategy_id == "FORWARD_ONLY")
    hyb = next(s for s in res.strategies if s.strategy_id == "HYBRID_OPTIMAL")

    assert fwd.feasible is False
    assert hyb.feasible is True
    assert hyb.projected_gpa_4 >= 3.55
    assert res.recommended_strategy_id == "HYBRID_OPTIMAL"


def test_milp_scenario_impossible_even_with_retakes_returns_ranked_advice():
    curr = _build_controlled_hcmut_curriculum()
    # All 6 completed courses got D (1.0) -> 20.0 pts; even with 4 retakes max pts < 3.95 * 40 (158 pts)
    completed = [
        StudentCourseRecord(course_code="SP1031", credits=3, score_10=4.2),
        StudentCourseRecord(course_code="SP1033", credits=2, score_10=4.2),
        StudentCourseRecord(course_code="EE1001", credits=3, score_10=4.2),
        StudentCourseRecord(course_code="MT1003", credits=4, score_10=4.2),
        StudentCourseRecord(course_code="PH1003", credits=4, score_10=4.2),
        StudentCourseRecord(course_code="EE2033", credits=4, score_10=4.2),
    ]

    res = optimize_study_roadmap(
        curr,
        RoadmapOptimizationRequest(
            major_code="7520201",
            cohort="K2025",
            completed_courses=completed,
            target_gpa=3.95,
            max_retake_courses=2,
            preference_mode="BALANCED",
        ),
    )

    assert all(not s.feasible for s in res.strategies)
    assert res.infeasibility_explanation_vi is not None
    assert len(res.top_retake_candidates_if_infeasible) >= 3
    # Highest ROI candidate should be an easy course rather than hardest course
    assert res.top_retake_candidates_if_infeasible[0].course_code in {"SP1031", "SP1033", "EE1001"}


def test_capstone_floor_enforced_in_milp_and_full_7520201_e2e_api():
    client = TestClient(app)

    # 1. Health & Majors
    r_majors = client.get("/api/majors")
    assert r_majors.status_code == 200
    assert len(r_majors.json()) >= 6

    # 2. Sample MyBK transcript for 7520201 K2025 (~3.20 GPA)
    r_sample = client.get("/api/transcript/sample-mybk?major_code=7520201&cohort=K2025")
    assert r_sample.status_code == 200
    sample_data = r_sample.json()
    parsed = sample_data["parsed"]
    assert 3.10 <= parsed["preview_gpa"]["gpa_4"] <= 3.30
    assert parsed["retake_detected_count"] >= 1

    # 3. Optimize 3.20 -> 3.60 on real full 132-credit 7520201 K2025 curriculum
    r_opt = client.post(
        "/api/roadmap/optimize",
        json={
            "major_code": "7520201",
            "cohort": "K2025",
            "completed_courses": parsed["parsed_courses"],
            "target_gpa": 3.60,
            "max_retake_courses": 3,
            "preference_mode": "BALANCED",
        },
    )
    assert r_opt.status_code == 200
    opt = r_opt.json()
    fwd = next(s for s in opt["strategies"] if s["strategy_id"] == "FORWARD_ONLY")
    hyb = next(s for s in opt["strategies"] if s["strategy_id"] == "HYBRID_OPTIMAL")
    assert fwd["feasible"] is True
    assert hyb["feasible"] is True
    assert hyb["projected_gpa_4"] >= 3.60
    assert hyb["total_effort_score"] < fwd["total_effort_score"]
    assert len(hyb["retake_recommendations"]) >= 1

    # 4. Verify capstone floor >= 2.0 even when target_gpa is 2.00
    r_low = client.post(
        "/api/roadmap/optimize",
        json={
            "major_code": "7520201",
            "cohort": "K2025",
            "completed_courses": [],
            "target_gpa": 2.00,
            "max_retake_courses": 0,
        },
    )
    assert r_low.status_code == 200
    low_fwd = r_low.json()["strategies"][0]
    for c_plan in low_fwd["remaining_course_plans"]:
        if c_plan["requires_min_c"]:
            assert c_plan["required_gpa_4"] >= 2.0
