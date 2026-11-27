export type DifficultyTier = 'Dễ' | 'Trung bình' | 'Khó' | 'Rất khó';
export type SpecialStatus = 'NORMAL' | 'FAIL_SPECIAL' | 'EXEMPT_PASS' | 'WITHDRAWN' | 'IN_PROGRESS';
export type MatchTier = 'EXACT_CODE' | 'FUZZY_NAME' | 'ELECTIVE_UNMATCHED' | 'MANUAL';
export type PreferenceMode = 'BALANCED' | 'MIN_EFFORT' | 'NO_RETAKE';
export type StrategyId = 'FORWARD_ONLY' | 'HYBRID_OPTIMAL' | 'CUSTOM_WHAT_IF';

export interface MajorInfo {
  major_code: string;
  major_name: string;
  major_name_en: string;
  faculty: string;
  program_type: string;
  available_cohorts: string[];
  default_cohort: string;
  total_credits: number;
  course_count: number;
}

export interface CourseItem {
  course_code: string;
  course_name: string;
  course_name_en?: string | null;
  credits: number;
  knowledge_block: string;
  recommended_semester: number;
  prerequisites: string[];
  corequisites: string[];
  is_elective: boolean;
  elective_group?: string | null;
  counts_for_gpa: boolean;
  requires_min_c: boolean;
}

export interface CurriculumSchema {
  major_code: string;
  major_name: string;
  major_name_en: string;
  faculty: string;
  cohort: string;
  apply_year: number;
  program_type: string;
  total_credits: number;
  total_gpa_credits: number;
  required_elective_credits: number;
  source_url: string;
  courses: CourseItem[];
}

export interface CourseDifficultyPrediction {
  course_code: string;
  course_name: string;
  credits: number;
  knowledge_block: string;
  recommended_semester: number;
  prerequisites: string[];
  dependent_count: number;
  prereq_chain_depth: number;
  ai_difficulty_score: number;
  effective_difficulty_score: number;
  user_override_score?: number | null;
  tier: DifficultyTier;
  challenge_tags: string[];
  rationale_vi: string;
  factor_breakdown: Record<string, number>;
  counts_for_gpa: boolean;
  is_elective: boolean;
  requires_min_c: boolean;
}

export interface SemesterDifficultyTrend {
  semester: number;
  semester_label: string;
  avg_difficulty: number;
  weighted_difficulty: number;
  total_credits: number;
  course_count: number;
}

export interface DifficultyDashboardResponse {
  major_code: string;
  major_name: string;
  faculty: string;
  cohort: string;
  total_credits: number;
  total_gpa_credits: number;
  average_difficulty: number;
  top_gatekeeper_courses: CourseDifficultyPrediction[];
  block_averages: Record<string, number>;
  semester_trends: SemesterDifficultyTrend[];
  courses: CourseDifficultyPrediction[];
}

export interface RetakeAttempt {
  semester?: string | null;
  raw_score?: string | null;
  score_10?: number | null;
  letter_grade: string;
  gpa_4: number;
  status: SpecialStatus;
}

export interface StudentCourseRecord {
  course_code: string;
  course_name: string;
  credits: number;
  semester?: string | null;
  score_10?: number | null;
  letter_grade?: string | null;
  gpa_4?: number | null;
  status: SpecialStatus;
  counts_for_gpa: boolean;
  is_elective: boolean;
  elective_group?: string | null;
  requires_min_c: boolean;
  passed: boolean;
  match_tier: MatchTier;
  matched_curriculum_code?: string | null;
  match_confidence: number;
  retake_count: number;
  retake_history: RetakeAttempt[];
}

export interface GpaSummaryResponse {
  gpa_4: number;
  gpa_10: number;
  earned_credits: number;
  earned_gpa_credits: number;
  attempted_gpa_credits: number;
  non_gpa_credits: number;
  honors_standing: string;
  ceiling_gpa_no_retake: number;
  ceiling_gpa_with_retake: number;
  remaining_gpa_credits: number;
  total_curriculum_gpa_credits: number;
  selected_elective_codes: string[];
  excluded_extra_elective_codes: string[];
  normalized_courses: StudentCourseRecord[];
}

export interface TranscriptParseResponse {
  parsed_courses: StudentCourseRecord[];
  withdrawn_or_inprogress: StudentCourseRecord[];
  unmatched_courses: StudentCourseRecord[];
  retake_detected_count: number;
  pii_stripped_count: number;
  warnings: string[];
  preview_gpa: GpaSummaryResponse;
}

export interface RetakeRecommendation {
  course_code: string;
  course_name: string;
  credits: number;
  knowledge_block: string;
  difficulty_score: number;
  old_letter_grade: string;
  old_gpa_4: number;
  old_score_10?: number | null;
  target_letter_grade: string;
  target_gpa_4: number;
  min_score_10: number;
  gpa_gain_contribution: number;
  effort_cost: number;
  roi_score: number;
  reason_vi: string;
}

export interface RemainingCoursePlan {
  course_code: string;
  course_name: string;
  recommended_semester: number;
  credits: number;
  knowledge_block: string;
  difficulty_score: number;
  difficulty_tier: DifficultyTier;
  required_letter_grade: string;
  required_gpa_4: number;
  min_score_10: number;
  effort_cost: number;
  requires_min_c: boolean;
  grade_relief_vs_forward?: string | null;
  gpa_delta_vs_forward: number;
}

export interface RoadmapStrategyPlan {
  strategy_id: StrategyId;
  strategy_name_vi: string;
  badge_vi?: string | null;
  is_recommended: boolean;
  feasible: boolean;
  projected_gpa_4: number;
  target_gpa_4: number;
  total_effort_score: number;
  effort_reduction_pct_vs_forward: number;
  hard_courses_requiring_a_or_bplus: number;
  hard_courses_requiring_a: number;
  retake_course_count: number;
  retake_credits: number;
  retake_recommendations: RetakeRecommendation[];
  remaining_course_plans: RemainingCoursePlan[];
  strategic_advice_vi: string;
}

export interface InfeasibleRetakeCandidate {
  course_code: string;
  course_name: string;
  credits: number;
  difficulty_score: number;
  current_letter_grade: string;
  current_gpa_4: number;
  max_gpa_gain: number;
  roi_rank_score: number;
}

export interface RoadmapOptimizationRequest {
  major_code: string;
  cohort: string;
  completed_courses: StudentCourseRecord[];
  target_gpa: number;
  max_retake_courses: number;
  max_retake_credits?: number | null;
  preference_mode: PreferenceMode;
  pinned_retakes: string[];
  excluded_retakes: string[];
  user_difficulty_overrides: Record<string, number>;
}

export interface RoadmapOptimizationResponse {
  major_code: string;
  major_name: string;
  cohort: string;
  current_gpa_4: number;
  target_gpa_4: number;
  completed_gpa_credits: number;
  remaining_gpa_credits: number;
  total_curriculum_gpa_credits: number;
  max_possible_gpa_forward_only: number;
  max_possible_gpa_with_allowed_retakes: number;
  absolute_max_possible_gpa: number;
  recommended_strategy_id?: string | null;
  strategies: RoadmapStrategyPlan[];
  infeasibility_explanation_vi?: string | null;
  top_retake_candidates_if_infeasible: InfeasibleRetakeCandidate[];
}
