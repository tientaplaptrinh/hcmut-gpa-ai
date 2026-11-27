"""Exact HCMUT Grading Scale, Retake Deduplication, Elective Selection & GPA Engine.

Implements HCMUT Undergraduate Academic Regulations (QĐ 2931/2933 & QĐ 1259/1260,
Cohorts K2021–K2026+):
- Course score rounded to 0.1 (ROUND_HALF_UP); cumulative GPA rounded to 0.01.
- Exact 10-point -> Letter -> 4.0 conversion.
- Standard pass floor >= D (1.0 / 4.0); Internship/Capstone/Thesis floor >= C (2.0 / 5.5).
- Non-GPA exclusions: GDTC (PE), GDQP (MI), non-credit English prep, and MT/BL/DT.
- Retake rule: keep highest achieved grade without double-counting credits.
- Extra electives: select highest-scoring combination up to required elective credits.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
import unicodedata
from typing import Iterable, Optional

from backend.contracts import (
    CurriculumSchema,
    GpaSummaryResponse,
    RetakeAttempt,
    SpecialStatus,
    StudentCourseRecord,
)


LETTER_TO_GPA4: dict[str, float] = {
    "A+": 4.0,
    "A": 4.0,
    "B+": 3.5,
    "B": 3.0,
    "C+": 2.5,
    "C": 2.0,
    "D+": 1.5,
    "D": 1.0,
    "F": 0.0,
}

# Minimum 10-point score required to achieve each discrete grade tier
GPA4_TO_MIN_SCORE10: dict[float, float] = {
    4.0: 8.5,
    3.5: 8.0,
    3.0: 7.0,
    2.5: 6.5,
    2.0: 5.5,
    1.5: 5.0,
    1.0: 4.0,
    0.0: 0.0,
}

GPA4_TO_LETTER: dict[float, str] = {
    4.0: "A",
    3.5: "B+",
    3.0: "B",
    2.5: "C+",
    2.0: "C",
    1.5: "D+",
    1.0: "D",
    0.0: "F",
}

LETTER_TO_REP_SCORE10: dict[str, float] = {
    "A+": 9.7,
    "A": 8.8,
    "B+": 8.2,
    "B": 7.5,
    "C+": 6.7,
    "C": 6.0,
    "D+": 5.2,
    "D": 4.5,
    "F": 2.0,
}

FAIL_SPECIAL_CODES = {"VT", "CT", "KD"}
EXEMPT_PASS_CODES = {"MT", "BL", "DT", " P", "P", "Đ", "DAT"}
WITHDRAWN_CODES = {"RT", "W"}
IN_PROGRESS_CODES = {"CH", "-", "--", "", "IP", "N/A"}

NON_GPA_PREFIXES = ("PE", "MI", "QP", "GDTC", "GDQP")
NON_CREDIT_ENG_CODES = {"LA0001", "LA0002", "LA1001", "LA1002", "EN0001", "EN0002"}


def strip_accents(text: str) -> str:
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def round_score_10(value: float) -> float:
    """Round a 10-point course final score to 0.1 using ROUND_HALF_UP."""
    clamped = max(0.0, min(10.0, float(value)))
    d = Decimal(str(clamped)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return float(d)


def round_gpa(value: float) -> float:
    """Round a cumulative GPA value to 0.01 using ROUND_HALF_UP."""
    clamped = max(0.0, float(value))
    d = Decimal(str(clamped)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(d)


def is_capstone_or_internship(
    course_code: str = "",
    course_name: str = "",
    knowledge_block: str = "",
) -> bool:
    """Detect Internship / Capstone / Thesis courses requiring >= C (2.0 / 5.5)."""
    if knowledge_block and "tốt nghiệp" in knowledge_block.lower():
        return True
    norm = strip_accents(course_name).lower()
    capstone_keywords = (
        "thuc tap ngoai truong",
        "thuc tap tot nghiep",
        "thuc tap doanh nghiep",
        "thuc tap ky thuat",
        "do an tot nghiep",
        "do an chuyen nganh",
        "do an thiet ke",
        "do an da nganh",
        "do an mon hoc",
        "do an",
        "luan van tot nghiep",
        "khoa luan tot nghiep",
        "capstone",
        "thesis",
        "internship",
    )
    if any(kw in norm for kw in capstone_keywords):
        return True
    # Common HCMUT internship/thesis suffixes (e.g., EE4337, EE4339, CO4337, CO3335)
    code_up = (course_code or "").strip().upper()
    if re.match(r"^[A-Z]{2,3}43\d{2}$", code_up):
        return True
    if norm.strip() == "thuc tap" or norm.startswith("thuc tap "):
        return True
    return False


def is_non_gpa_course(
    course_code: str = "",
    course_name: str = "",
    credits: int = 3,
    status: SpecialStatus = "NORMAL",
    letter_grade: Optional[str] = None,
) -> bool:
    """Determine if a course must be excluded from the HCMUT GPA denominator."""
    if credits <= 0:
        return True
    if status == "EXEMPT_PASS":
        return True
    lg = (letter_grade or "").strip().upper()
    if lg in EXEMPT_PASS_CODES:
        return True

    code_up = (course_code or "").strip().upper()
    if code_up.startswith(NON_GPA_PREFIXES) or code_up in NON_CREDIT_ENG_CODES:
        return True

    norm = strip_accents(course_name).lower()
    non_gpa_keywords = (
        "giao duc the chat",
        "the duc",
        "giao duc quoc phong",
        "quoc phong an ninh",
        "anh van dau vao",
        "tieng anh du bi",
        "anh van can ban",
        "sinh hoat cong dan",
    )
    if any(kw in norm for kw in non_gpa_keywords):
        return True
    return False


def score10_to_grade(score_10: float) -> tuple[str, float, float]:
    """Convert raw 10-point score -> (letter_grade, gpa_4, rounded_score_10)."""
    s = round_score_10(score_10)
    if s >= 9.5:
        return "A+", 4.0, s
    if s >= 8.5:
        return "A", 4.0, s
    if s >= 8.0:
        return "B+", 3.5, s
    if s >= 7.0:
        return "B", 3.0, s
    if s >= 6.5:
        return "C+", 2.5, s
    if s >= 5.5:
        return "C", 2.0, s
    if s >= 5.0:
        return "D+", 1.5, s
    if s >= 4.0:
        return "D", 1.0, s
    return "F", 0.0, s


def classify_honors(gpa_4: float) -> str:
    """Classify HCMUT academic standing on the 4.0 scale."""
    g = round_gpa(gpa_4)
    if g >= 3.60:
        return "Xuất sắc"
    if g >= 3.20:
        return "Giỏi"
    if g >= 2.50:
        return "Khá"
    if g >= 2.00:
        return "Trung bình"
    return "Yếu / Cần cải thiện"


def check_course_passed(
    gpa_4: float,
    requires_min_c: bool = False,
    status: SpecialStatus = "NORMAL",
) -> bool:
    """Check whether a course meets the HCMUT minimum passing floor."""
    if status == "EXEMPT_PASS":
        return True
    if status in ("FAIL_SPECIAL", "WITHDRAWN", "IN_PROGRESS"):
        return False
    floor = 2.0 if requires_min_c else 1.0
    return gpa_4 >= floor - 1e-9


def normalize_course_record(
    record: StudentCourseRecord,
    curriculum_map: Optional[dict[str, object]] = None,
) -> StudentCourseRecord:
    """Normalize a single StudentCourseRecord according to HCMUT grading rules."""
    rec = record.model_copy(deep=True)
    rec.course_code = rec.course_code.strip().upper()

    curr_item = curriculum_map.get(rec.course_code) if curriculum_map else None
    if curr_item is not None:
        if not rec.course_name:
            rec.course_name = getattr(curr_item, "course_name", "")
        rec.credits = getattr(curr_item, "credits", rec.credits)
        rec.is_elective = getattr(curr_item, "is_elective", rec.is_elective)
        rec.elective_group = getattr(curr_item, "elective_group", rec.elective_group)
        rec.requires_min_c = rec.requires_min_c or getattr(curr_item, "requires_min_c", False)
        if not getattr(curr_item, "counts_for_gpa", True):
            rec.counts_for_gpa = False

    rec.requires_min_c = rec.requires_min_c or is_capstone_or_internship(
        rec.course_code, rec.course_name
    )

    raw_letter = (rec.letter_grade or "").strip().upper()

    # Special statuses first
    if raw_letter in FAIL_SPECIAL_CODES or rec.status == "FAIL_SPECIAL":
        rec.status = "FAIL_SPECIAL"
        rec.letter_grade = raw_letter if raw_letter in FAIL_SPECIAL_CODES else "F"
        rec.score_10 = 0.0
        rec.gpa_4 = 0.0
        rec.passed = False
        rec.counts_for_gpa = not is_non_gpa_course(
            rec.course_code, rec.course_name, rec.credits, status="NORMAL"
        )
        return rec

    if raw_letter in EXEMPT_PASS_CODES or rec.status == "EXEMPT_PASS":
        rec.status = "EXEMPT_PASS"
        rec.letter_grade = raw_letter if raw_letter in EXEMPT_PASS_CODES else "MT"
        rec.score_10 = None
        rec.gpa_4 = None
        rec.counts_for_gpa = False
        rec.passed = True
        return rec

    if raw_letter in WITHDRAWN_CODES or rec.status == "WITHDRAWN":
        rec.status = "WITHDRAWN"
        rec.letter_grade = "RT"
        rec.score_10 = None
        rec.gpa_4 = None
        rec.counts_for_gpa = False
        rec.passed = False
        return rec

    if (rec.score_10 is None and raw_letter in IN_PROGRESS_CODES) or rec.status == "IN_PROGRESS":
        rec.status = "IN_PROGRESS"
        rec.letter_grade = "CH"
        rec.score_10 = None
        rec.gpa_4 = None
        rec.counts_for_gpa = False
        rec.passed = False
        return rec

    # Normal numeric or letter grade
    rec.status = "NORMAL"
    if rec.score_10 is not None:
        letter, gpa4, s10 = score10_to_grade(rec.score_10)
        rec.score_10 = s10
        rec.letter_grade = letter
        rec.gpa_4 = gpa4
    elif raw_letter in LETTER_TO_GPA4:
        rec.letter_grade = raw_letter
        rec.gpa_4 = LETTER_TO_GPA4[raw_letter]
        rec.score_10 = LETTER_TO_REP_SCORE10[raw_letter]
    elif rec.gpa_4 is not None:
        g4 = float(rec.gpa_4)
        rec.letter_grade = GPA4_TO_LETTER.get(g4, "C")
        rec.score_10 = GPA4_TO_MIN_SCORE10.get(g4, 5.5)

    # Check if course failed capstone C-floor: in HCMUT a score < 5.5 on capstone/internship
    # is NOT passed (requires retake to achieve >= C).
    rec.passed = check_course_passed(
        rec.gpa_4 or 0.0,
        requires_min_c=rec.requires_min_c,
        status=rec.status,
    )

    if is_non_gpa_course(
        rec.course_code,
        rec.course_name,
        rec.credits,
        status=rec.status,
        letter_grade=rec.letter_grade,
    ):
        rec.counts_for_gpa = False

    return rec


def deduplicate_retakes(
    records: Iterable[StudentCourseRecord],
    curriculum_map: Optional[dict[str, object]] = None,
) -> tuple[list[StudentCourseRecord], list[StudentCourseRecord], int]:
    """Deduplicate multiple attempts of the same course code.

    Keeps the highest achieved grade without double-counting credits,
    attaches full retake_history, and separates WITHDRAWN / IN_PROGRESS records
    unless a valid graded/exempt attempt exists for the same course.
    """
    grouped: dict[str, list[StudentCourseRecord]] = {}
    for raw in records:
        norm = normalize_course_record(raw, curriculum_map=curriculum_map)
        grouped.setdefault(norm.course_code, []).append(norm)

    active_records: list[StudentCourseRecord] = []
    inactive_records: list[StudentCourseRecord] = []
    retake_courses_count = 0

    for code, attempts in grouped.items():
        valid_attempts = [
            a for a in attempts if a.status in ("NORMAL", "FAIL_SPECIAL", "EXEMPT_PASS")
        ]
        if not valid_attempts:
            # Only RT / CH attempts exist -> stays in remaining courses
            inactive_records.append(attempts[-1])
            continue

        # Sort priority: EXEMPT_PASS (if no higher GPA needed) vs highest gpa_4 then highest score_10
        def attempt_sort_key(a: StudentCourseRecord) -> tuple[int, float, float]:
            if a.status == "EXEMPT_PASS":
                return (1, 0.0, 0.0)
            return (2, a.gpa_4 if a.gpa_4 is not None else -1.0, a.score_10 if a.score_10 is not None else -1.0)

        best = max(valid_attempts, key=attempt_sort_key).model_copy(deep=True)
        if len(valid_attempts) > 1 or best.retake_history:
            if len(valid_attempts) > 1:
                retake_courses_count += 1
            history: list[RetakeAttempt] = list(best.retake_history)
            if len(valid_attempts) > 1:
                history = [
                    RetakeAttempt(
                        semester=a.semester,
                        raw_score=str(a.score_10) if a.score_10 is not None else a.letter_grade,
                        score_10=a.score_10,
                        letter_grade=a.letter_grade or "",
                        gpa_4=a.gpa_4 or 0.0,
                        status=a.status,
                    )
                    for a in attempts
                ]
            best.retake_history = history
            best.retake_count = max(best.retake_count, len(valid_attempts) - 1)

        active_records.append(best)

    return active_records, inactive_records, retake_courses_count


def select_optimal_electives(
    elective_courses: list[StudentCourseRecord],
    required_elective_credits: Optional[int],
) -> tuple[list[StudentCourseRecord], list[StudentCourseRecord]]:
    """Select the highest-scoring combination of completed electives when extra electives exist.

    Uses exact 0-1 dynamic programming / subset selection to maximize GPA contribution
    while satisfying >= required_elective_credits (or keeping the minimal excess if indivisible)
    without dragging down GPA with lower-scoring surplus electives.
    """
    if required_elective_credits is None or required_elective_credits <= 0:
        return elective_courses, []

    passed_electives = [c for c in elective_courses if c.passed and c.counts_for_gpa and c.credits > 0]
    other_electives = [c for c in elective_courses if c not in passed_electives]

    total_elec_credits = sum(c.credits for c in passed_electives)
    if total_elec_credits <= required_elective_credits:
        return elective_courses, []

    # Sort descending by (gpa_4, score_10, credits)
    sorted_elec = sorted(
        passed_electives,
        key=lambda c: (c.gpa_4 or 0.0, c.score_10 or 0.0, c.credits),
        reverse=True,
    )

    # Exact subset evaluation when len <= 18 (typical student has 3-10 electives), greedy fallback otherwise
    n = len(sorted_elec)
    if n <= 18:
        best_ratio = -1.0
        best_score10_ratio = -1.0
        best_mask = (1 << n) - 1
        for mask in range(1, 1 << n):
            cred = 0
            pts4 = 0.0
            pts10 = 0.0
            for idx in range(n):
                if mask & (1 << idx):
                    c = sorted_elec[idx]
                    cred += c.credits
                    pts4 += c.credits * (c.gpa_4 or 0.0)
                    pts10 += c.credits * (c.score_10 or 0.0)
            # Valid subset must meet required_elective_credits and not unnecessarily include extra low courses
            # Specifically, check minimal sufficient subsets (no removable element keeps cred >= required unless it improves ratio)
            if cred >= required_elective_credits:
                ratio4 = pts4 / cred
                ratio10 = pts10 / cred
                if (ratio4 > best_ratio + 1e-9) or (
                    abs(ratio4 - best_ratio) <= 1e-9 and ratio10 > best_score10_ratio + 1e-9
                ):
                    best_ratio = ratio4
                    best_score10_ratio = ratio10
                    best_mask = mask

        selected = [sorted_elec[i] for i in range(n) if best_mask & (1 << i)]
        excluded = [sorted_elec[i] for i in range(n) if not (best_mask & (1 << i))]
        return selected + other_electives, excluded

    # Greedy fallback for >18 electives
    selected = []
    excluded = []
    acc = 0
    for c in sorted_elec:
        if acc < required_elective_credits:
            selected.append(c)
            acc += c.credits
        else:
            excluded.append(c)
    return selected + other_electives, excluded


def calculate_gpa_summary(
    courses: Iterable[StudentCourseRecord],
    curriculum: Optional[CurriculumSchema] = None,
    required_elective_credits: Optional[int] = None,
    total_curriculum_gpa_credits: Optional[int] = None,
) -> GpaSummaryResponse:
    """Compute exact HCMUT current GPA (4.0 & 10.0), credits, standing, and GPA ceilings."""
    curr_map = {c.course_code.upper(): c for c in curriculum.courses} if curriculum else None
    req_elec = (
        required_elective_credits
        if required_elective_credits is not None
        else (curriculum.required_elective_credits if curriculum else None)
    )
    tot_curr_gpa_credits = (
        total_curriculum_gpa_credits
        if total_curriculum_gpa_credits is not None
        else (curriculum.total_gpa_credits if curriculum else 132)
    )

    deduped, _inactive, _retakes = deduplicate_retakes(courses, curriculum_map=curr_map)

    electives = [c for c in deduped if c.is_elective]
    non_electives = [c for c in deduped if not c.is_elective]

    selected_elec, excluded_elec = select_optimal_electives(electives, req_elec)
    effective_courses = non_electives + selected_elec

    gpa_bearing = [
        c
        for c in effective_courses
        if c.counts_for_gpa and c.status in ("NORMAL", "FAIL_SPECIAL") and c.credits > 0
    ]

    attempted_gpa_credits = sum(c.credits for c in gpa_bearing)
    earned_gpa_credits = sum(c.credits for c in gpa_bearing if c.passed)
    non_gpa_passed_credits = sum(
        c.credits for c in deduped if (not c.counts_for_gpa) and c.passed and c.credits > 0
    )
    earned_credits = earned_gpa_credits + non_gpa_passed_credits
    non_gpa_credits = sum(c.credits for c in deduped if not c.counts_for_gpa and c.credits > 0)

    if attempted_gpa_credits > 0:
        pts_4 = sum(c.credits * (c.gpa_4 or 0.0) for c in gpa_bearing)
        pts_10 = sum(c.credits * (c.score_10 or 0.0) for c in gpa_bearing)
        gpa_4 = round_gpa(pts_4 / attempted_gpa_credits)
        gpa_10 = round_gpa(pts_10 / attempted_gpa_credits)
    else:
        pts_4 = 0.0
        gpa_4 = 0.0
        gpa_10 = 0.0

    honors = classify_honors(gpa_4) if attempted_gpa_credits > 0 else "Chưa có điểm"

    # Compute remaining GPA credits & ceilings
    effective_total_credits = max(tot_curr_gpa_credits, attempted_gpa_credits)
    remaining_gpa_credits = max(0, effective_total_credits - attempted_gpa_credits)

    if effective_total_credits > 0:
        ceiling_no_retake = round_gpa(
            (pts_4 + remaining_gpa_credits * 4.0) / effective_total_credits
        )
        ceiling_with_retake = 4.00
    else:
        ceiling_no_retake = 4.00
        ceiling_with_retake = 4.00

    return GpaSummaryResponse(
        gpa_4=gpa_4,
        gpa_10=gpa_10,
        earned_credits=earned_credits,
        earned_gpa_credits=earned_gpa_credits,
        attempted_gpa_credits=attempted_gpa_credits,
        non_gpa_credits=non_gpa_credits,
        honors_standing=honors,
        ceiling_gpa_no_retake=ceiling_no_retake,
        ceiling_gpa_with_retake=ceiling_with_retake,
        remaining_gpa_credits=remaining_gpa_credits,
        total_curriculum_gpa_credits=effective_total_credits,
        selected_elective_codes=[c.course_code for c in selected_elec if c.counts_for_gpa],
        excluded_extra_elective_codes=[c.course_code for c in excluded_elec],
        normalized_courses=deduped,
    )
