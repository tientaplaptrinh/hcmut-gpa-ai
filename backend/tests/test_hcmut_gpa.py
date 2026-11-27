"""Pytest verification of Exact HCMUT Grading Scale, GPA Rules, Retakes & Electives."""

from __future__ import annotations

import pytest

from backend.contracts import StudentCourseRecord
from backend.hcmut_gpa import (
    calculate_gpa_summary,
    classify_honors,
    normalize_course_record,
    score10_to_grade,
)


@pytest.mark.parametrize(
    "raw_score,expected_letter,expected_gpa4",
    [
        (3.9, "F", 0.0),
        (3.94, "F", 0.0),
        (3.95, "D", 1.0),   # Rounds to 4.0 -> D
        (4.0, "D", 1.0),
        (4.9, "D", 1.0),
        (5.0, "D+", 1.5),
        (5.4, "D+", 1.5),
        (5.5, "C", 2.0),
        (6.4, "C", 2.0),
        (6.5, "C+", 2.5),
        (6.9, "C+", 2.5),
        (7.0, "B", 3.0),
        (7.9, "B", 3.0),
        (8.0, "B+", 3.5),
        (8.4, "B+", 3.5),
        (8.45, "A", 4.0),   # ROUND_HALF_UP: 8.45 -> 8.5 -> A
        (8.5, "A", 4.0),
        (9.4, "A", 4.0),
        (9.5, "A+", 4.0),
        (10.0, "A+", 4.0),
    ],
)
def test_exact_hcmut_score_boundaries(raw_score: float, expected_letter: str, expected_gpa4: float):
    letter, gpa4, _ = score10_to_grade(raw_score)
    assert letter == expected_letter
    assert gpa4 == expected_gpa4


def test_capstone_and_internship_minimum_c_floor():
    # D+ (5.2 -> 1.5) on Đồ án tốt nghiệp fails HCMUT >= C (2.0 / 5.5) floor
    failed_capstone = normalize_course_record(
        StudentCourseRecord(
            course_code="EE4339",
            course_name="Đồ án tốt nghiệp",
            credits=4,
            score_10=5.2,
        )
    )
    assert failed_capstone.requires_min_c is True
    assert failed_capstone.letter_grade == "D+"
    assert failed_capstone.gpa_4 == 1.5
    assert failed_capstone.passed is False

    # C (5.5 -> 2.0) on Thực tập ngoài trường passes
    passed_internship = normalize_course_record(
        StudentCourseRecord(
            course_code="EE3335",
            course_name="Thực tập ngoài trường",
            credits=2,
            score_10=5.5,
        )
    )
    assert passed_internship.requires_min_c is True
    assert passed_internship.letter_grade == "C"
    assert passed_internship.gpa_4 == 2.0
    assert passed_internship.passed is True


def test_non_gpa_exclusions_and_retake_no_double_counting():
    records = [
        # Retaken course: first F (3.2), then B+ (8.2) -> keep 3.5 on 4 credits once
        StudentCourseRecord(course_code="MT1003", course_name="Giải tích 1", credits=4, score_10=3.2, semester="HK231"),
        StudentCourseRecord(course_code="MT1003", course_name="Giải tích 1", credits=4, score_10=8.2, semester="HK232"),
        # Normal A course: 3 credits * 4.0
        StudentCourseRecord(course_code="MT1007", course_name="Đại số tuyến tính", credits=3, score_10=8.8, semester="HK231"),
        # Non-GPA courses: GDTC (PE), GDQP (MI), Exempt English (MT)
        StudentCourseRecord(course_code="PE1003", course_name="Giáo dục thể chất 1", credits=1, score_10=9.0),
        StudentCourseRecord(course_code="MI1003", course_name="Giáo dục quốc phòng", credits=0, letter_grade="DT"),
        StudentCourseRecord(course_code="LA1003", course_name="Anh văn 1", credits=2, letter_grade="MT"),
    ]
    summary = calculate_gpa_summary(records, total_curriculum_gpa_credits=132)
    # GPA denominator must be 4 + 3 = 7 credits (NOT 11, NOT 10)
    assert summary.attempted_gpa_credits == 7
    assert summary.earned_gpa_credits == 7
    # Earned credits includes passed non-GPA courses with positive credits (PE 1 + LA 2 = 3) -> 10
    assert summary.earned_credits == 10
    # Expected GPA4 = (4*3.5 + 3*4.0) / 7 = 26.0 / 7 = 3.714 -> 3.71
    assert summary.gpa_4 == 3.71
    assert summary.honors_standing == "Xuất sắc"


def test_extra_electives_selects_highest_scoring_combination():
    records = [
        StudentCourseRecord(course_code="MT1003", course_name="Giải tích 1", credits=4, score_10=8.5, is_elective=False),
        # 4 electives of 3 TC each (12 TC total), required_elective_credits = 6 TC
        StudentCourseRecord(course_code="EE4001", course_name="Tự chọn 1", credits=3, score_10=5.6, is_elective=True),  # C (2.0)
        StudentCourseRecord(course_code="EE4003", course_name="Tự chọn 2", credits=3, score_10=9.0, is_elective=True),  # A (4.0)
        StudentCourseRecord(course_code="EE4005", course_name="Tự chọn 3", credits=3, score_10=8.2, is_elective=True),  # B+ (3.5)
        StudentCourseRecord(course_code="EE4007", course_name="Tự chọn 4", credits=3, score_10=5.1, is_elective=True),  # D+ (1.5)
    ]
    summary = calculate_gpa_summary(records, required_elective_credits=6, total_curriculum_gpa_credits=130)
    assert set(summary.selected_elective_codes) == {"EE4003", "EE4005"}
    assert set(summary.excluded_extra_elective_codes) == {"EE4001", "EE4007"}
    # GPA = (4*4.0 + 3*4.0 + 3*3.5) / 10 = 38.5 / 10 = 3.85
    assert summary.attempted_gpa_credits == 10
    assert summary.gpa_4 == 3.85


def test_honors_standing_tiers():
    assert classify_honors(3.60) == "Xuất sắc"
    assert classify_honors(3.59) == "Giỏi"
    assert classify_honors(3.20) == "Giỏi"
    assert classify_honors(3.19) == "Khá"
    assert classify_honors(2.50) == "Khá"
    assert classify_honors(2.49) == "Trung bình"
    assert classify_honors(2.00) == "Trung bình"
    assert classify_honors(1.95) == "Yếu / Cần cải thiện"
