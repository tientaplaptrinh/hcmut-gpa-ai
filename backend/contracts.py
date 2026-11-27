"""Strict Pydantic v2 API contracts for BK-GPA & Optimal Study Roadmap AI."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


KnowledgeBlockLiteral = Literal[
    "Toán & KHTN",
    "Giáo dục chung",
    "Cơ sở ngành",
    "Chuyên ngành",
    "Tốt nghiệp",
]

DifficultyTier = Literal["Dễ", "Trung bình", "Khó", "Rất khó"]

SpecialStatus = Literal[
    "NORMAL",
    "FAIL_SPECIAL",
    "EXEMPT_PASS",
    "WITHDRAWN",
    "IN_PROGRESS",
]

MatchTier = Literal[
    "EXACT_CODE",
    "FUZZY_NAME",
    "ELECTIVE_UNMATCHED",
    "MANUAL",
]

PreferenceMode = Literal["BALANCED", "MIN_EFFORT", "NO_RETAKE"]

StrategyId = Literal["FORWARD_ONLY", "HYBRID_OPTIMAL", "CUSTOM_WHAT_IF"]


class CourseItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    course_code: str = Field(..., min_length=4, description="HCMUT course code, e.g. MT1003")
    course_name: str = Field(..., description="Vietnamese course title")
    course_name_en: Optional[str] = None
    credits: int = Field(..., ge=0, le=20)
    lecture_hours: int = Field(default=0, ge=0)
    lab_hours: int = Field(default=0, ge=0)
    exercise_hours: int = Field(default=0, ge=0)
    project_hours: int = Field(default=0, ge=0)
    knowledge_block: str = Field(..., description="Normalized HCMUT knowledge block")
    recommended_semester: int = Field(default=1, ge=1, le=12)
    prerequisites: list[str] = Field(default_factory=list)
    corequisites: list[str] = Field(default_factory=list)
    is_elective: bool = False
    elective_group: Optional[str] = None
    elective_required_credits: Optional[int] = None
    counts_for_gpa: bool = True
    requires_min_c: bool = False


class CurriculumSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    major_code: str
    major_name: str
    major_name_en: str = ""
    faculty: str = ""
    cohort: str
    apply_year: int
    program_type: str = "Chương trình Tiêu chuẩn"
    total_credits: int
    total_gpa_credits: int
    required_elective_credits: int = 0
    source_url: str
    crawled_at: str
    courses: list[CourseItem]


class MajorInfo(BaseModel):
    major_code: str
    major_name: str
    major_name_en: str = ""
    faculty: str
    program_type: str = "Chương trình Tiêu chuẩn"
    available_cohorts: list[str]
    default_cohort: str
    total_credits: int
    course_count: int


class CourseDifficultyPrediction(BaseModel):
    course_code: str
    course_name: str
    credits: int
    knowledge_block: str
    recommended_semester: int
    prerequisites: list[str] = Field(default_factory=list)
    dependent_count: int = 0
    prereq_chain_depth: int = 0
    ai_difficulty_score: float = Field(..., ge=1.0, le=10.0)
    effective_difficulty_score: float = Field(..., ge=1.0, le=10.0)
    user_override_score: Optional[float] = Field(default=None, ge=1.0, le=10.0)
    tier: DifficultyTier
    challenge_tags: list[str] = Field(default_factory=list)
    rationale_vi: str
    factor_breakdown: dict[str, float] = Field(default_factory=dict)
    counts_for_gpa: bool = True
    is_elective: bool = False
    requires_min_c: bool = False


class SemesterDifficultyTrend(BaseModel):
    semester: int
    semester_label: str
    avg_difficulty: float
    weighted_difficulty: float
    total_credits: int
    course_count: int


class DifficultyRequest(BaseModel):
    major_code: str
    cohort: str = "K2025"
    user_difficulty_overrides: dict[str, float] = Field(default_factory=dict)


class DifficultyDashboardResponse(BaseModel):
    major_code: str
    major_name: str
    faculty: str
    cohort: str
    total_credits: int
    total_gpa_credits: int
    average_difficulty: float
    top_gatekeeper_courses: list[CourseDifficultyPrediction]
    block_averages: dict[str, float]
    semester_trends: list[SemesterDifficultyTrend]
    courses: list[CourseDifficultyPrediction]


class RetakeAttempt(BaseModel):
    semester: Optional[str] = None
    raw_score: Optional[str] = None
    score_10: Optional[float] = None
    letter_grade: str
    gpa_4: float
    status: SpecialStatus = "NORMAL"


class StudentCourseRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    course_code: str
    course_name: str = ""
    credits: int = Field(default=3, ge=0, le=20)
    semester: Optional[str] = None
    score_10: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    letter_grade: Optional[str] = None
    gpa_4: Optional[float] = Field(default=None, ge=0.0, le=4.0)
    status: SpecialStatus = "NORMAL"
    counts_for_gpa: bool = True
    is_elective: bool = False
    elective_group: Optional[str] = None
    requires_min_c: bool = False
    passed: bool = True
    match_tier: MatchTier = "MANUAL"
    matched_curriculum_code: Optional[str] = None
    match_confidence: float = 100.0
    retake_count: int = 0
    retake_history: list[RetakeAttempt] = Field(default_factory=list)


class GpaCalculationRequest(BaseModel):
    major_code: Optional[str] = None
    cohort: Optional[str] = None
    courses: list[StudentCourseRecord]
    required_elective_credits: Optional[int] = None
    total_curriculum_gpa_credits: Optional[int] = None


class GpaSummaryResponse(BaseModel):
    gpa_4: float
    gpa_10: float
    earned_credits: int
    earned_gpa_credits: int
    attempted_gpa_credits: int
    non_gpa_credits: int
    honors_standing: str
    ceiling_gpa_no_retake: float
    ceiling_gpa_with_retake: float
    remaining_gpa_credits: int
    total_curriculum_gpa_credits: int
    selected_elective_codes: list[str] = Field(default_factory=list)
    excluded_extra_elective_codes: list[str] = Field(default_factory=list)
    normalized_courses: list[StudentCourseRecord] = Field(default_factory=list)


class TranscriptParseTextRequest(BaseModel):
    raw_text: str
    major_code: Optional[str] = None
    cohort: Optional[str] = "K2025"


class TranscriptParseResponse(BaseModel):
    parsed_courses: list[StudentCourseRecord]
    withdrawn_or_inprogress: list[StudentCourseRecord]
    unmatched_courses: list[StudentCourseRecord]
    retake_detected_count: int
    pii_stripped_count: int
    warnings: list[str] = Field(default_factory=list)
    preview_gpa: GpaSummaryResponse


class RetakeRecommendation(BaseModel):
    course_code: str
    course_name: str
    credits: int
    knowledge_block: str
    difficulty_score: float
    old_letter_grade: str
    old_gpa_4: float
    old_score_10: Optional[float] = None
    target_letter_grade: str
    target_gpa_4: float
    min_score_10: float
    gpa_gain_contribution: float
    effort_cost: float
    roi_score: float
    reason_vi: str


class RemainingCoursePlan(BaseModel):
    course_code: str
    course_name: str
    recommended_semester: int
    credits: int
    knowledge_block: str
    difficulty_score: float
    difficulty_tier: DifficultyTier
    required_letter_grade: str
    required_gpa_4: float
    min_score_10: float
    effort_cost: float
    requires_min_c: bool = False
    grade_relief_vs_forward: Optional[str] = None
    gpa_delta_vs_forward: float = 0.0


class RoadmapStrategyPlan(BaseModel):
    strategy_id: StrategyId
    strategy_name_vi: str
    badge_vi: Optional[str] = None
    is_recommended: bool = False
    feasible: bool
    projected_gpa_4: float
    target_gpa_4: float
    total_effort_score: float
    effort_reduction_pct_vs_forward: float = 0.0
    hard_courses_requiring_a_or_bplus: int = 0
    hard_courses_requiring_a: int = 0
    retake_course_count: int = 0
    retake_credits: int = 0
    retake_recommendations: list[RetakeRecommendation] = Field(default_factory=list)
    remaining_course_plans: list[RemainingCoursePlan] = Field(default_factory=list)
    strategic_advice_vi: str


class InfeasibleRetakeCandidate(BaseModel):
    course_code: str
    course_name: str
    credits: int
    difficulty_score: float
    current_letter_grade: str
    current_gpa_4: float
    max_gpa_gain: float
    roi_rank_score: float


class RoadmapOptimizationRequest(BaseModel):
    major_code: str
    cohort: str = "K2025"
    completed_courses: list[StudentCourseRecord] = Field(default_factory=list)
    target_gpa: float = Field(..., ge=1.0, le=4.0)
    max_retake_courses: int = Field(default=3, ge=0, le=10)
    max_retake_credits: Optional[int] = Field(default=None, ge=0)
    preference_mode: PreferenceMode = "BALANCED"
    pinned_retakes: list[str] = Field(default_factory=list)
    excluded_retakes: list[str] = Field(default_factory=list)
    user_difficulty_overrides: dict[str, float] = Field(default_factory=dict)


class RoadmapOptimizationResponse(BaseModel):
    major_code: str
    major_name: str
    cohort: str
    current_gpa_4: float
    target_gpa_4: float
    completed_gpa_credits: int
    remaining_gpa_credits: int
    total_curriculum_gpa_credits: int
    max_possible_gpa_forward_only: float
    max_possible_gpa_with_allowed_retakes: float
    absolute_max_possible_gpa: float
    recommended_strategy_id: Optional[str] = None
    strategies: list[RoadmapStrategyPlan]
    infeasibility_explanation_vi: Optional[str] = None
    top_retake_candidates_if_infeasible: list[InfeasibleRetakeCandidate] = Field(default_factory=list)
