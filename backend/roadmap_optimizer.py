"""Exact MILP Joint Optimal Study Roadmap & Strategic Retake Engine (`scipy.optimize.milp`).

Solves globally and jointly over:
  - Remaining curriculum courses `i in R` via one-hot binary variables `x[i, k] in {0, 1}`
  - Retakeable completed courses `j in C_retake = {j in C_done | g_old[j] < 4.0}`
    via binary retake indicator `r[j] in {0, 1}` and strictly improving grade tiers `y[j, k] in {0, 1}`

Guarantees exact HCMUT retake accounting (no double-counting credits in GPA denominator):
  sum_{j in C_done} c_j * g_old[j]
  + sum_{j in C_retake} sum_{k: g_k > g_old[j]} c_j * (g_k - g_old[j]) * y[j, k]
  + sum_{i in R} sum_k c_i * g_k * x[i, k]
  >= G_target * C_total

Minimizes Convex Difficulty-Weighted Academic Effort:
  effort(D, g) = (0.35 + 0.65 * (D / 10.0)**1.6) * ((g / 4.0)**2.4 * 10.0)
  retake_cost_per_credit(D_j, g_k) = alpha * effort(D_j, g_k) + beta_friction   (alpha = 0.80)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from backend.contracts import (
    CourseDifficultyPrediction,
    CurriculumSchema,
    InfeasibleRetakeCandidate,
    PreferenceMode,
    RemainingCoursePlan,
    RetakeRecommendation,
    RoadmapOptimizationRequest,
    RoadmapOptimizationResponse,
    RoadmapStrategyPlan,
    StrategyId,
    StudentCourseRecord,
)
from backend.difficulty_model import build_difficulty_dashboard
from backend.hcmut_gpa import (
    GPA4_TO_LETTER,
    GPA4_TO_MIN_SCORE10,
    deduplicate_retakes,
    round_gpa,
    select_optimal_electives,
)


DISCRETE_GRADE_TIERS: list[float] = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
PRIOR_KNOWLEDGE_ALPHA: float = 0.80

MODE_FRICTION_BETA: dict[PreferenceMode, float] = {
    "BALANCED": 1.05,
    "MIN_EFFORT": 0.40,
    "NO_RETAKE": 99.0,
}


def compute_per_credit_effort(difficulty: float, grade_4: float) -> float:
    """Convex per-credit academic effort increasing super-linearly with difficulty D and grade g."""
    d = max(1.0, min(10.0, float(difficulty)))
    g = max(0.0, min(4.0, float(grade_4)))
    diff_factor = 0.35 + 0.65 * ((d / 10.0) ** 1.6)
    grade_factor = ((g / 4.0) ** 2.4) * 10.0
    return float(diff_factor * grade_factor)


@dataclass
class PreparedProblem:
    curriculum: CurriculumSchema
    diff_by_code: dict[str, CourseDifficultyPrediction]
    completed_gpa: list[StudentCourseRecord]
    remaining_courses: list[CourseDifficultyPrediction]
    base_points_4: float
    completed_credits: int
    remaining_credits: int
    total_credits: int
    current_gpa_4: float


def prepare_optimization_problem(
    curriculum: CurriculumSchema,
    completed_courses: list[StudentCourseRecord],
    user_difficulty_overrides: dict[str, float],
) -> PreparedProblem:
    diff_dash = build_difficulty_dashboard(curriculum, user_difficulty_overrides)
    diff_by_code = {p.course_code.upper(): p for p in diff_dash.courses}
    curr_map = {c.course_code.upper(): c for c in curriculum.courses}

    deduped, _inactive, _ = deduplicate_retakes(completed_courses, curriculum_map=curr_map)

    electives_done = [c for c in deduped if c.is_elective]
    non_electives_done = [c for c in deduped if not c.is_elective]
    selected_elec, _excluded_elec = select_optimal_electives(
        electives_done, curriculum.required_elective_credits
    )
    effective_done = non_electives_done + selected_elec

    completed_gpa = [
        c
        for c in effective_done
        if c.counts_for_gpa and c.status in ("NORMAL", "FAIL_SPECIAL") and c.credits > 0
    ]
    done_codes = {c.course_code.upper() for c in deduped if c.status in ("NORMAL", "FAIL_SPECIAL", "EXEMPT_PASS")}

    # Remaining compulsory GPA courses
    rem_compulsory: list[CourseDifficultyPrediction] = [
        p
        for p in diff_dash.courses
        if p.counts_for_gpa
        and p.credits > 0
        and not p.is_elective
        and p.course_code.upper() not in done_codes
    ]

    # Remaining required elective GPA courses (up to curriculum.required_elective_credits)
    done_elec_gpa_credits = sum(c.credits for c in selected_elec if c.counts_for_gpa and c.credits > 0)
    rem_elec_needed = max(0, curriculum.required_elective_credits - done_elec_gpa_credits)

    rem_electives: list[CourseDifficultyPrediction] = []
    if rem_elec_needed > 0:
        avail_elec = sorted(
            [
                p
                for p in diff_dash.courses
                if p.counts_for_gpa
                and p.credits > 0
                and p.is_elective
                and p.course_code.upper() not in done_codes
            ],
            key=lambda p: (p.effective_difficulty_score, p.recommended_semester, p.course_code),
        )
        acc = 0
        for p in avail_elec:
            if acc >= rem_elec_needed:
                break
            rem_electives.append(p)
            acc += p.credits

    remaining_courses = sorted(
        rem_compulsory + rem_electives,
        key=lambda p: (p.recommended_semester, p.course_code),
    )

    completed_credits = sum(c.credits for c in completed_gpa)
    remaining_credits = sum(p.credits for p in remaining_courses)
    total_credits = completed_credits + remaining_credits
    base_points_4 = sum(c.credits * (c.gpa_4 or 0.0) for c in completed_gpa)
    current_gpa_4 = round_gpa(base_points_4 / completed_credits) if completed_credits > 0 else 0.0

    return PreparedProblem(
        curriculum=curriculum,
        diff_by_code=diff_by_code,
        completed_gpa=completed_gpa,
        remaining_courses=remaining_courses,
        base_points_4=base_points_4,
        completed_credits=completed_credits,
        remaining_credits=remaining_credits,
        total_credits=total_credits,
        current_gpa_4=current_gpa_4,
    )


def _solve_single_milp(
    prob: PreparedProblem,
    target_gpa: float,
    strategy_id: StrategyId,
    strategy_name_vi: str,
    max_retake_courses: int,
    max_retake_credits: Optional[int],
    beta_friction: float,
    pinned_retakes: set[str],
    excluded_retakes: set[str],
) -> RoadmapStrategyPlan:
    """Solve exact one-hot binary MILP for a specific strategy configuration."""
    if prob.total_credits <= 0:
        return RoadmapStrategyPlan(
            strategy_id=strategy_id,
            strategy_name_vi=strategy_name_vi,
            feasible=False,
            projected_gpa_4=0.0,
            target_gpa_4=target_gpa,
            total_effort_score=0.0,
            strategic_advice_vi="CTĐT chưa có tín chỉ tính GPA để tối ưu hóa.",
        )

    # Identify eligible retake candidates: g_old < 4.0 and not excluded (unless pinned)
    retake_pool: list[StudentCourseRecord] = []
    if max_retake_courses > 0:
        for c in prob.completed_gpa:
            code_u = c.course_code.upper()
            g_old = float(c.gpa_4 or 0.0)
            if g_old < 4.0 - 1e-9 and (code_u not in excluded_retakes or code_u in pinned_retakes):
                retake_pool.append(c)

    # Build variable indexing
    # 1) x[i, k] for i in remaining_courses, k in allowed_tiers(i)
    x_vars: list[tuple[int, float, int, float]] = []  # (rem_idx, grade_k, credits, cost)
    rem_var_slices: list[list[int]] = []

    for i_idx, r_course in enumerate(prob.remaining_courses):
        allowed_g = [
            g for g in DISCRETE_GRADE_TIERS if (g >= 2.0 if r_course.requires_min_c else g >= 1.0)
        ]
        idxs: list[int] = []
        for g in allowed_g:
            v_id = len(x_vars)
            cost = r_course.credits * compute_per_credit_effort(
                r_course.effective_difficulty_score, g
            )
            # Tiny epsilon tie-breaker so ties break smoothly toward balanced grades
            cost -= 1e-5 * r_course.credits * g
            x_vars.append((i_idx, g, r_course.credits, cost))
            idxs.append(v_id)
        rem_var_slices.append(idxs)

    num_x = len(x_vars)

    # 2) r[j] in {0, 1} for j in retake_pool (index offset: num_x + j)
    num_r = len(retake_pool)
    r_offset = num_x

    # 3) y[j, k] in {0, 1} for j in retake_pool, g_k > g_old[j]
    y_vars: list[tuple[int, float, int, float, float]] = []  # (ret_idx, grade_k, credits, delta_g, cost)
    ret_y_slices: list[list[int]] = []
    y_offset = num_x + num_r

    for j_idx, c_done in enumerate(retake_pool):
        g_old = float(c_done.gpa_4 or 0.0)
        min_floor = 2.0 if c_done.requires_min_c else 1.0
        higher_tiers = [g for g in DISCRETE_GRADE_TIERS if g > g_old + 1e-9 and g >= min_floor]
        pred = prob.diff_by_code.get(c_done.course_code.upper())
        d_score = pred.effective_difficulty_score if pred else 5.0

        idxs = []
        for g in higher_tiers:
            y_id = y_offset + len(y_vars)
            per_cred_cost = PRIOR_KNOWLEDGE_ALPHA * compute_per_credit_effort(d_score, g) + beta_friction
            cost = c_done.credits * per_cred_cost - 1e-5 * c_done.credits * (g - g_old)
            y_vars.append((j_idx, g, c_done.credits, g - g_old, cost))
            idxs.append(y_id)
        ret_y_slices.append(idxs)

    total_vars = num_x + num_r + len(y_vars)

    if total_vars == 0:
        # All courses already completed and no retakes allowed/available
        feasible_now = prob.base_points_4 + 1e-7 >= target_gpa * prob.total_credits
        return RoadmapStrategyPlan(
            strategy_id=strategy_id,
            strategy_name_vi=strategy_name_vi,
            feasible=feasible_now,
            projected_gpa_4=prob.current_gpa_4,
            target_gpa_4=target_gpa,
            total_effort_score=0.0,
            strategic_advice_vi=(
                "Bạn đã hoàn thành toàn bộ tín chỉ và đạt mục tiêu GPA!"
                if feasible_now
                else "Đã hoàn thành toàn bộ CTĐT nhưng GPA hiện tại thấp hơn mục tiêu; hãy bật học cải thiện."
            ),
        )

    c_obj = np.zeros(total_vars, dtype=float)
    for idx_v, (_, _, _, cost) in enumerate(x_vars):
        c_obj[idx_v] = cost
    for idx_y, (_, _, _, _, cost) in enumerate(y_vars):
        c_obj[y_offset + idx_y] = cost

    rows_A: list[np.ndarray] = []
    lb_list: list[float] = []
    ub_list: list[float] = []

    # Constraint 1: sum_k x[i, k] == 1 for every remaining course i
    for idxs in rem_var_slices:
        row = np.zeros(total_vars, dtype=float)
        row[idxs] = 1.0
        rows_A.append(row)
        lb_list.append(1.0)
        ub_list.append(1.0)

    # Constraint 2: sum_{k: g_k > g_old} y[j, k] - r[j] == 0 for every retake candidate j
    for j_idx, y_idxs in enumerate(ret_y_slices):
        row = np.zeros(total_vars, dtype=float)
        if y_idxs:
            row[y_idxs] = 1.0
        row[r_offset + j_idx] = -1.0
        rows_A.append(row)
        lb_list.append(0.0)
        ub_list.append(0.0)

    # Constraint 3: Pinned retakes r[j] == 1 (if j in pinned_retakes)
    active_pins = 0
    for j_idx, c_done in enumerate(retake_pool):
        if c_done.course_code.upper() in pinned_retakes and ret_y_slices[j_idx]:
            row = np.zeros(total_vars, dtype=float)
            row[r_offset + j_idx] = 1.0
            rows_A.append(row)
            lb_list.append(1.0)
            ub_list.append(1.0)
            active_pins += 1

    # Constraint 4: Max retake courses: sum_j r[j] <= max(max_retake_courses, active_pins)
    if num_r > 0:
        eff_max_courses = max(max_retake_courses, active_pins)
        row = np.zeros(total_vars, dtype=float)
        row[r_offset : r_offset + num_r] = 1.0
        rows_A.append(row)
        lb_list.append(-np.inf)
        ub_list.append(float(eff_max_courses))

        if max_retake_credits is not None:
            row_cred = np.zeros(total_vars, dtype=float)
            for j_idx, c_done in enumerate(retake_pool):
                row_cred[r_offset + j_idx] = float(c_done.credits)
            rows_A.append(row_cred)
            lb_list.append(-np.inf)
            ub_list.append(float(max_retake_credits))

    # Constraint 5: Exact HCMUT Target GPA Linear Inequality (no double credits!)
    # sum_{i,k} c_i * g_k * x_{i,k} + sum_{j,k} c_j * (g_k - g_old_j) * y_{j,k} >= G_target * C_total - base_points_4
    rhs_needed = target_gpa * prob.total_credits - prob.base_points_4 - 1e-7
    gpa_row = np.zeros(total_vars, dtype=float)
    for idx_v, (_, g, cred, _) in enumerate(x_vars):
        gpa_row[idx_v] = cred * g
    for idx_y, (_, _, cred, delta_g, _) in enumerate(y_vars):
        gpa_row[y_offset + idx_y] = cred * delta_g
    rows_A.append(gpa_row)
    lb_list.append(rhs_needed)
    ub_list.append(np.inf)

    A_mat = np.vstack(rows_A)
    constraints = LinearConstraint(A_mat, np.array(lb_list), np.array(ub_list))
    integrality = np.ones(total_vars, dtype=int)
    bounds = Bounds(np.zeros(total_vars), np.ones(total_vars))

    res = milp(c=c_obj, integrality=integrality, bounds=bounds, constraints=constraints)

    if not res.success or res.x is None:
        # Compute maximum achievable GPA under this strategy's retake limit
        max_pts = prob.base_points_4 + prob.remaining_credits * 4.0
        if num_r > 0 and max_retake_courses > 0:
            gains = sorted(
                [
                    c.credits * (4.0 - float(c.gpa_4 or 0.0))
                    for c in retake_pool
                ],
                reverse=True,
            )
            max_pts += sum(gains[:max_retake_courses])
        max_achievable = round_gpa(max_pts / prob.total_credits)
        gap = round(target_gpa - max_achievable, 2)
        advice = (
            f"Bất khả thi với cấu hình này: Trần GPA tối đa đạt được là {max_achievable:.2f} "
            f"(thiếu {max(0.01, gap):.2f} điểm so với mục tiêu {target_gpa:.2f})."
        )
        if strategy_id == "FORWARD_ONLY":
            advice += " Bắt buộc kết hợp học cải thiện các môn điểm thấp (D/D+/C) để mở trần GPA!"
        return RoadmapStrategyPlan(
            strategy_id=strategy_id,
            strategy_name_vi=strategy_name_vi,
            feasible=False,
            projected_gpa_4=max_achievable,
            target_gpa_4=target_gpa,
            total_effort_score=0.0,
            strategic_advice_vi=advice,
        )

    sol = np.rint(res.x).astype(int)

    # Decode remaining courses
    rem_plans: list[RemainingCoursePlan] = []
    rem_points = 0.0
    total_effort = 0.0
    hard_a_or_bplus = 0
    hard_a = 0

    for i_idx, r_course in enumerate(prob.remaining_courses):
        chosen_g = 4.0
        for v_id in rem_var_slices[i_idx]:
            if sol[v_id] == 1:
                chosen_g = x_vars[v_id][1]
                break
        eff = r_course.credits * compute_per_credit_effort(
            r_course.effective_difficulty_score, chosen_g
        )
        total_effort += eff
        rem_points += r_course.credits * chosen_g
        if r_course.effective_difficulty_score >= 7.5:
            if chosen_g >= 3.5 - 1e-9:
                hard_a_or_bplus += 1
            if chosen_g >= 4.0 - 1e-9:
                hard_a += 1

        rem_plans.append(
            RemainingCoursePlan(
                course_code=r_course.course_code,
                course_name=r_course.course_name,
                recommended_semester=r_course.recommended_semester,
                credits=r_course.credits,
                knowledge_block=r_course.knowledge_block,
                difficulty_score=r_course.effective_difficulty_score,
                difficulty_tier=r_course.tier,
                required_letter_grade=GPA4_TO_LETTER[chosen_g],
                required_gpa_4=chosen_g,
                min_score_10=GPA4_TO_MIN_SCORE10[chosen_g],
                effort_cost=round(eff, 2),
                requires_min_c=r_course.requires_min_c,
            )
        )

    # Decode retake recommendations
    retake_recs: list[RetakeRecommendation] = []
    retake_delta_pts = 0.0

    for j_idx, c_done in enumerate(retake_pool):
        if sol[r_offset + j_idx] != 1:
            continue
        chosen_g = 4.0
        for y_id in ret_y_slices[j_idx]:
            if sol[y_id] == 1:
                chosen_g = y_vars[y_id - y_offset][1]
                break

        g_old = float(c_done.gpa_4 or 0.0)
        pred = prob.diff_by_code.get(c_done.course_code.upper())
        d_score = pred.effective_difficulty_score if pred else 5.0
        kb = pred.knowledge_block if pred else ("Tự chọn" if c_done.is_elective else "Cơ sở ngành")

        eff = c_done.credits * (
            PRIOR_KNOWLEDGE_ALPHA * compute_per_credit_effort(d_score, chosen_g) + beta_friction
        )
        total_effort += eff
        delta_pts = c_done.credits * (chosen_g - g_old)
        retake_delta_pts += delta_pts
        gpa_gain = round(delta_pts / prob.total_credits, 3)
        roi = round((gpa_gain * 100.0) / max(1.0, eff), 3)

        old_letter = c_done.letter_grade or GPA4_TO_LETTER.get(g_old, "F")
        new_letter = GPA4_TO_LETTER[chosen_g]

        retake_recs.append(
            RetakeRecommendation(
                course_code=c_done.course_code,
                course_name=c_done.course_name or (pred.course_name if pred else c_done.course_code),
                credits=c_done.credits,
                knowledge_block=kb,
                difficulty_score=d_score,
                old_letter_grade=old_letter,
                old_gpa_4=g_old,
                old_score_10=c_done.score_10,
                target_letter_grade=new_letter,
                target_gpa_4=chosen_g,
                min_score_10=GPA4_TO_MIN_SCORE10[chosen_g],
                gpa_gain_contribution=gpa_gain,
                effort_cost=round(eff, 2),
                roi_score=roi,
                reason_vi=(
                    f"Độ khó thấp ({d_score:.1f}/10), nâng {old_letter} ({g_old:.1f}) → {new_letter} ({chosen_g:.1f}) "
                    f"cộng trực tiếp +{gpa_gain:.2f} vào GPA toàn khóa, giải phóng áp lực cho các môn chuyên ngành khó."
                ),
            )
        )

    retake_recs.sort(key=lambda r: (r.gpa_gain_contribution, r.roi_score), reverse=True)

    projected_gpa = round_gpa(
        (prob.base_points_4 + retake_delta_pts + rem_points) / prob.total_credits
    )
    retake_credits = sum(r.credits for r in retake_recs)

    return RoadmapStrategyPlan(
        strategy_id=strategy_id,
        strategy_name_vi=strategy_name_vi,
        feasible=True,
        projected_gpa_4=projected_gpa,
        target_gpa_4=target_gpa,
        total_effort_score=round(total_effort, 2),
        hard_courses_requiring_a_or_bplus=hard_a_or_bplus,
        hard_courses_requiring_a=hard_a,
        retake_course_count=len(retake_recs),
        retake_credits=retake_credits,
        retake_recommendations=retake_recs,
        remaining_course_plans=rem_plans,
        strategic_advice_vi="",
    )


def optimize_study_roadmap(
    curriculum: CurriculumSchema,
    request: RoadmapOptimizationRequest,
) -> RoadmapOptimizationResponse:
    """Solve and compare Forward-Only vs. AI Optimal Hybrid vs. Low-Stress/Custom What-If."""
    prob = prepare_optimization_problem(
        curriculum=curriculum,
        completed_courses=request.completed_courses,
        user_difficulty_overrides=request.user_difficulty_overrides,
    )

    pinned_set = {c.strip().upper() for c in request.pinned_retakes if c.strip()}
    excluded_set = {c.strip().upper() for c in request.excluded_retakes if c.strip()} - pinned_set

    # Compute GPA ceilings
    max_pts_forward = prob.base_points_4 + prob.remaining_credits * 4.0
    max_gpa_forward = round_gpa(max_pts_forward / max(1, prob.total_credits))

    eligible_gains: list[tuple[float, StudentCourseRecord, float]] = []
    all_retake_gains: list[float] = []
    for c in prob.completed_gpa:
        g_old = float(c.gpa_4 or 0.0)
        if g_old < 4.0 - 1e-9:
            gain_pts = c.credits * (4.0 - g_old)
            all_retake_gains.append(gain_pts)
            if c.course_code.upper() not in excluded_set:
                pred = prob.diff_by_code.get(c.course_code.upper())
                d_sc = pred.effective_difficulty_score if pred else 5.0
                eligible_gains.append((gain_pts, c, d_sc))

    eligible_gains.sort(key=lambda x: x[0], reverse=True)
    eff_limit = 0 if request.preference_mode == "NO_RETAKE" else request.max_retake_courses
    allowed_gain_pts = sum(x[0] for x in eligible_gains[:eff_limit])
    max_gpa_allowed = round_gpa(
        (max_pts_forward + allowed_gain_pts) / max(1, prob.total_credits)
    )
    abs_max_gpa = round_gpa(
        (max_pts_forward + sum(all_retake_gains)) / max(1, prob.total_credits)
    )

    # 1. Strategy A: Forward-Only (max_retakes = 0)
    plan_a = _solve_single_milp(
        prob=prob,
        target_gpa=request.target_gpa,
        strategy_id="FORWARD_ONLY",
        strategy_name_vi="Lộ trình A — Không học cải thiện (Forward-Only)",
        max_retake_courses=0,
        max_retake_credits=0,
        beta_friction=MODE_FRICTION_BETA["NO_RETAKE"],
        pinned_retakes=set(),
        excluded_retakes=excluded_set,
    )
    if plan_a.feasible:
        plan_a.strategic_advice_vi = (
            f"Không cần tốn tín chỉ học lại, nhưng bạn phải duy trì áp lực cao trên các môn sắp tới "
            f"(cần đạt A/B+ ở {plan_a.hard_courses_requiring_a_or_bplus} môn khó độ khó ≥ 7.5, "
            f"trong đó {plan_a.hard_courses_requiring_a} môn khó bắt buộc đạt A)."
        )

    # 2. Strategy B: AI Optimal Hybrid (respects user max_retake_courses & interactive exclusions/pins)
    hybrid_max_retakes = (
        0
        if request.preference_mode == "NO_RETAKE"
        else max(request.max_retake_courses, len(pinned_set))
    )
    hybrid_beta = MODE_FRICTION_BETA.get(request.preference_mode, MODE_FRICTION_BETA["BALANCED"])
    if request.preference_mode == "NO_RETAKE":
        # Still solve Hybrid with default budget 3 so student can see side-by-side comparison,
        # while honoring NO_RETAKE preference in recommendation badge
        hybrid_max_retakes = max(3, len(pinned_set))
        hybrid_beta = MODE_FRICTION_BETA["BALANCED"]

    plan_b = _solve_single_milp(
        prob=prob,
        target_gpa=request.target_gpa,
        strategy_id="HYBRID_OPTIMAL",
        strategy_name_vi="Lộ trình B — Tối ưu Hỗn hợp (Học mới + Cải thiện thông minh)",
        max_retake_courses=hybrid_max_retakes,
        max_retake_credits=request.max_retake_credits,
        beta_friction=hybrid_beta,
        pinned_retakes=pinned_set,
        excluded_retakes=excluded_set,
    )

    # 3. Strategy C: Low-Stress / Custom What-If
    whatif_max = max(4, hybrid_max_retakes)
    has_custom = bool(pinned_set or excluded_set or request.user_difficulty_overrides)
    c_title = (
        "Lộ trình C — Tùy chỉnh What-If & Giảm tải tối đa"
        if has_custom
        else "Lộ trình C — Nhẹ áp lực nhất (Ưu tiên hạ điểm môn khó)"
    )
    plan_c = _solve_single_milp(
        prob=prob,
        target_gpa=request.target_gpa,
        strategy_id="CUSTOM_WHAT_IF",
        strategy_name_vi=c_title,
        max_retake_courses=whatif_max,
        max_retake_credits=request.max_retake_credits,
        beta_friction=MODE_FRICTION_BETA["MIN_EFFORT"],
        pinned_retakes=pinned_set,
        excluded_retakes=excluded_set,
    )

    # Annotate grade relief vs Forward-Only on Plan B & Plan C
    if plan_a.feasible:
        fwd_grade_by_code = {
            r.course_code: (r.required_gpa_4, r.required_letter_grade)
            for r in plan_a.remaining_course_plans
        }
        for plan in (plan_b, plan_c):
            if not plan.feasible:
                continue
            if plan_a.total_effort_score > 0:
                red_pct = (
                    (plan_a.total_effort_score - plan.total_effort_score)
                    / plan_a.total_effort_score
                ) * 100.0
                plan.effort_reduction_pct_vs_forward = round(red_pct, 1)

            for r_item in plan.remaining_course_plans:
                fwd_info = fwd_grade_by_code.get(r_item.course_code)
                if fwd_info:
                    fwd_g4, fwd_let = fwd_info
                    delta = round(r_item.required_gpa_4 - fwd_g4, 2)
                    r_item.gpa_delta_vs_forward = delta
                    if delta < -1e-9:
                        r_item.grade_relief_vs_forward = f"{fwd_let} → {r_item.required_letter_grade}"
                    elif delta > 1e-9:
                        r_item.grade_relief_vs_forward = f"{fwd_let} ↑ {r_item.required_letter_grade}"

    # Determine Best Recommended Roadmap & craft strategic Vietnamese explanations
    recommended_id: Optional[str] = None

    if not plan_a.feasible and plan_b.feasible:
        plan_b.is_recommended = True
        plan_b.badge_vi = "Tối ưu nhất • Duy nhất khả thi"
        recommended_id = plan_b.strategy_id
        ret_summary = ", ".join(
            f"{r.course_code} ({r.old_letter_grade}→{r.target_letter_grade})"
            for r in plan_b.retake_recommendations
        )
        plan_b.strategic_advice_vi = (
            f"Nếu không học cải thiện, trần GPA tối đa chỉ đạt {max_gpa_forward:.2f} (< {request.target_gpa:.2f}). "
            f"AI khuyến nghị học cải thiện {plan_b.retake_course_count} môn nhẹ ({ret_summary}, {plan_b.retake_credits} TC) "
            f"để mở khóa mục tiêu {plan_b.projected_gpa_4:.2f} với tổng áp lực thấp nhất."
        )
    elif plan_a.feasible and plan_b.feasible:
        if request.preference_mode == "NO_RETAKE":
            plan_a.is_recommended = True
            plan_a.badge_vi = "Đang chọn • Không học lại"
            recommended_id = plan_a.strategy_id
        elif plan_b.retake_course_count > 0 and (
            plan_b.effort_reduction_pct_vs_forward >= 8.0 or bool(pinned_set)
        ):
            plan_b.is_recommended = True
            plan_b.badge_vi = "Tối ưu nhất • AI Khuyên dùng"
            recommended_id = plan_b.strategy_id
            ret_summary = ", ".join(
                f"{r.course_code} ({r.old_letter_grade}→{r.target_letter_grade}, +{r.gpa_gain_contribution:.2f} GPA)"
                for r in plan_b.retake_recommendations
            )
            relieved_count = sum(
                1 for r in plan_b.remaining_course_plans if r.gpa_delta_vs_forward < -1e-9
            )
            plan_b.strategic_advice_vi = (
                f"Chiến lược vượt trội: Học cải thiện {plan_b.retake_course_count} môn ({ret_summary}; {plan_b.retake_credits} TC) "
                f"giúp giảm {plan_b.effort_reduction_pct_vs_forward:.1f}% tổng áp lực học tập so với Lộ trình A, "
                f"hạ chỉ tiêu điểm cho {relieved_count} môn khó phía trước (số môn khó phải đạt A giảm từ "
                f"{plan_a.hard_courses_requiring_a} xuống {plan_b.hard_courses_requiring_a} môn)."
            )
        else:
            plan_a.is_recommended = True
            plan_a.badge_vi = "Tối ưu nhất • AI Khuyên dùng"
            recommended_id = plan_a.strategy_id
            plan_b.badge_vi = "Hiệu suất cải thiện thấp (<8%)"
            plan_b.strategic_advice_vi = (
                f"AI khuyên chọn Lộ trình A (Không học cải thiện): Việc học lại chỉ giúp giảm "
                f"{max(0.0, plan_b.effort_reduction_pct_vs_forward):.1f}% áp lực (< ngưỡng 8%), "
                f"không đáng đánh đổi học phí và thời gian học lại. Hãy tập trung toàn lực cho các môn mới!"
            )
    elif not plan_a.feasible and not plan_b.feasible and plan_c.feasible:
        plan_c.is_recommended = True
        plan_c.badge_vi = "Tối ưu nhất • Khả thi khi mở rộng cải thiện"
        recommended_id = plan_c.strategy_id

    if plan_c.feasible and not plan_c.strategic_advice_vi:
        if plan_c.retake_course_count > 0:
            plan_c.strategic_advice_vi = (
                f"Ưu tiên giảm stress tối đa: Cải thiện {plan_c.retake_course_count} môn ({plan_c.retake_credits} TC) "
                f"để chỉ còn {plan_c.hard_courses_requiring_a} môn khó cần đạt điểm A."
            )
        else:
            plan_c.strategic_advice_vi = (
                "Các môn còn lại đã đủ nhẹ để đạt mục tiêu mà không cần học cải thiện thêm."
            )

    # Infeasibility diagnostics & ROI-ranked retake candidates when target cannot be met
    infeasibility_msg: Optional[str] = None
    top_candidates: list[InfeasibleRetakeCandidate] = []

    if not any(p.feasible for p in (plan_a, plan_b, plan_c)):
        gap_allowed = round(request.target_gpa - max_gpa_allowed, 2)
        gap_abs = round(request.target_gpa - abs_max_gpa, 2)
        if abs_max_gpa >= request.target_gpa:
            infeasibility_msg = (
                f"Mục tiêu GPA {request.target_gpa:.2f} hiện thiếu {max(0.01, gap_allowed):.2f} điểm với giới hạn tối đa "
                f"{request.max_retake_courses} môn cải thiện (trần hiện tại {max_gpa_allowed:.2f}). "
                f"Tuy nhiên nếu tăng giới hạn số môn học cải thiện, trần tuyệt đối có thể đạt {abs_max_gpa:.2f}!"
            )
        else:
            infeasibility_msg = (
                f"Mục tiêu GPA {request.target_gpa:.2f} vượt quá trần toán học tuyệt đối ({abs_max_gpa:.2f}, "
                f"còn thiếu {max(0.01, gap_abs):.2f} điểm ngay cả khi đạt 4.0 toàn bộ các môn còn lại và học cải thiện)."
            )

        for gain_pts, c_rec, d_sc in eligible_gains:
            max_gain_gpa = round(gain_pts / max(1, prob.total_credits), 3)
            eff_cost = c_rec.credits * compute_per_credit_effort(d_sc, 4.0)
            roi_rank = round((max_gain_gpa * 100.0) / max(1.0, eff_cost), 3)
            top_candidates.append(
                InfeasibleRetakeCandidate(
                    course_code=c_rec.course_code,
                    course_name=c_rec.course_name or c_rec.course_code,
                    credits=c_rec.credits,
                    difficulty_score=d_sc,
                    current_letter_grade=c_rec.letter_grade or GPA4_TO_LETTER.get(c_rec.gpa_4 or 0.0, "F"),
                    current_gpa_4=float(c_rec.gpa_4 or 0.0),
                    max_gpa_gain=max_gain_gpa,
                    roi_rank_score=roi_rank,
                )
            )
        top_candidates.sort(key=lambda x: (x.roi_rank_score, x.max_gpa_gain), reverse=True)
        top_candidates = top_candidates[:6]

    return RoadmapOptimizationResponse(
        major_code=curriculum.major_code,
        major_name=curriculum.major_name,
        cohort=curriculum.cohort,
        current_gpa_4=prob.current_gpa_4,
        target_gpa_4=request.target_gpa,
        completed_gpa_credits=prob.completed_credits,
        remaining_gpa_credits=prob.remaining_credits,
        total_curriculum_gpa_credits=prob.total_credits,
        max_possible_gpa_forward_only=max_gpa_forward,
        max_possible_gpa_with_allowed_retakes=max_gpa_allowed,
        absolute_max_possible_gpa=abs_max_gpa,
        recommended_strategy_id=recommended_id,
        strategies=[plan_a, plan_b, plan_c],
        infeasibility_explanation_vi=infeasibility_msg,
        top_retake_candidates_if_infeasible=top_candidates,
    )
