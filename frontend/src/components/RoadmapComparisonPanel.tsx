import React, { useEffect, useState } from 'react';
import {
  Award,
  CheckCircle2,
  XCircle,
  TrendingDown,
  RefreshCw,
  BookOpen,
  AlertOctagon,
  Sparkles,
} from 'lucide-react';
import type {
  DifficultyTier,
  RoadmapOptimizationResponse,
  RoadmapStrategyPlan,
  StrategyId,
  StudentCourseRecord,
} from '../types';

interface RoadmapComparisonPanelProps {
  result: RoadmapOptimizationResponse | null;
  completedCourses: StudentCourseRecord[];
  excludedRetakes: string[];
  onToggleCourseRetakeWhatIf: (courseCode: string, enableRetake: boolean) => void;
}

const TIER_BADGE: Record<DifficultyTier, string> = {
  'Dễ': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300',
  'Trung bình': 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  'Khó': 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  'Rất khó': 'bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300',
};

export const RoadmapComparisonPanel: React.FC<RoadmapComparisonPanelProps> = ({
  result,
  completedCourses,
  excludedRetakes,
  onToggleCourseRetakeWhatIf,
}) => {
  const [selectedStrategyId, setSelectedStrategyId] = useState<StrategyId>('HYBRID_OPTIMAL');

  useEffect(() => {
    if (!result) return;
    if (result.recommended_strategy_id) {
      setSelectedStrategyId(result.recommended_strategy_id as StrategyId);
    } else {
      setSelectedStrategyId('HYBRID_OPTIMAL');
    }
  }, [result?.recommended_strategy_id]);

  if (!result) return null;

  const selectedPlan: RoadmapStrategyPlan =
    result.strategies.find((s) => s.strategy_id === selectedStrategyId) ||
    result.strategies[1] ||
    result.strategies[0];

  const excludedCourseObjs = completedCourses.filter((c) =>
    excludedRetakes.includes(c.course_code.toUpperCase())
  );

  return (
    <div className="space-y-6" data-testid="roadmap-comparison-panel">
      {/* Global Infeasibility Diagnostic Banner (when even retakes cannot reach target) */}
      {result.infeasibility_explanation_vi && (
        <div
          className="p-5 rounded-2xl bg-rose-50 dark:bg-rose-950/50 border-2 border-rose-300 dark:border-rose-800 space-y-3"
          data-testid="infeasible-diagnostic-banner"
        >
          <div className="flex items-start gap-3">
            <AlertOctagon className="w-6 h-6 text-rose-600 dark:text-rose-400 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-base font-extrabold text-rose-900 dark:text-rose-200">
                Cảnh báo Toán học: Chưa thể chạm ngưỡng GPA {result.target_gpa_4.toFixed(2)} với cấu hình hiện tại
              </h4>
              <p className="text-sm text-rose-800 dark:text-rose-300 mt-1">
                {result.infeasibility_explanation_vi}
              </p>
            </div>
          </div>

          {result.top_retake_candidates_if_infeasible.length > 0 && (
            <div className="pt-2">
              <div className="text-xs font-bold text-rose-900 dark:text-rose-200 uppercase mb-2">
                Top học phần tiềm năng nhất nên ưu tiên học cải thiện (Xếp hạng theo ROI Tăng GPA / Chi phí Độ khó):
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                {result.top_retake_candidates_if_infeasible.map((cand) => (
                  <div
                    key={cand.course_code}
                    className="p-3 rounded-xl bg-white dark:bg-slate-900 border border-rose-200 dark:border-rose-800 text-xs"
                  >
                    <div className="font-extrabold text-[#034EA2] dark:text-sky-400">
                      {cand.course_code} — {cand.course_name}
                    </div>
                    <div className="text-slate-600 dark:text-slate-300 mt-1">
                      Hiện tại: <strong>{cand.current_letter_grade}</strong> ({cand.credits} TC) • Độ khó:{' '}
                      <strong>{cand.difficulty_score.toFixed(1)}</strong>
                    </div>
                    <div className="text-emerald-700 dark:text-emerald-400 font-bold mt-0.5">
                      Tăng tối đa: +{cand.max_gpa_gain.toFixed(2)} GPA
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Side-by-Side Strategy Comparison Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {result.strategies.map((plan) => {
          const isSelected = plan.strategy_id === selectedPlan.strategy_id;
          return (
            <div
              key={plan.strategy_id}
              role="button"
              tabIndex={0}
              data-testid={`strategy-card-${plan.strategy_id}`}
              onClick={() => setSelectedStrategyId(plan.strategy_id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setSelectedStrategyId(plan.strategy_id);
              }}
              className={`text-left p-5 rounded-2xl border-2 transition-all cursor-pointer flex flex-col justify-between ${
                isSelected
                  ? 'border-[#034EA2] bg-blue-50/50 dark:bg-blue-950/30 shadow-lg ring-2 ring-[#034EA2]/20'
                  : 'border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-blue-300'
              }`}
            >
              <div className="space-y-3">
                {/* Top Badges */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {plan.feasible ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Khả thi
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300">
                      <XCircle className="w-3.5 h-3.5" />
                      Bất khả thi
                    </span>
                  )}

                  {plan.is_recommended && (
                    <span
                      data-testid="best-recommended-badge"
                      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-[#034EA2] text-white shadow-xs"
                    >
                      <Award className="w-3.5 h-3.5" />
                      {plan.badge_vi || 'Tối ưu nhất'}
                    </span>
                  )}
                </div>

                <h4 className="text-base font-extrabold text-slate-900 dark:text-white">
                  {plan.strategy_name_vi}
                </h4>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  <div className="p-2.5 rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700">
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">
                      GPA Dự kiến
                    </div>
                    <div className="text-lg font-extrabold text-[#034EA2] dark:text-sky-400">
                      {plan.projected_gpa_4.toFixed(2)}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700">
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">
                      Điểm Áp lực (Effort)
                    </div>
                    <div className="flex items-baseline gap-1.5">
                      <span
                        className="text-lg font-extrabold text-slate-900 dark:text-white"
                        data-testid={`effort-score-${plan.strategy_id}`}
                      >
                        {plan.feasible ? plan.total_effort_score.toFixed(1) : '—'}
                      </span>
                      {plan.effort_reduction_pct_vs_forward > 0 && (
                        <span className="inline-flex items-center text-xs font-extrabold text-emerald-600 dark:text-emerald-400">
                          <TrendingDown className="w-3 h-3 mr-0.5" />-
                          {plan.effort_reduction_pct_vs_forward.toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700">
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">
                      Môn khó cần đạt A
                    </div>
                    <div className="text-sm font-extrabold text-slate-800 dark:text-slate-100">
                      {plan.feasible ? `${plan.hard_courses_requiring_a} môn` : '—'}
                    </div>
                  </div>

                  <div className="p-2.5 rounded-xl bg-white dark:bg-slate-800/90 border border-slate-200/80 dark:border-slate-700">
                    <div className="text-[11px] text-slate-500 dark:text-slate-400 font-semibold">
                      Học cải thiện
                    </div>
                    <div className="text-sm font-extrabold text-amber-700 dark:text-amber-300">
                      {plan.retake_course_count} môn ({plan.retake_credits} TC)
                    </div>
                  </div>
                </div>

                <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed pt-1">
                  {plan.strategic_advice_vi}
                </p>
              </div>

              <div className="mt-4 pt-2.5 border-t border-slate-200/70 dark:border-slate-800 flex items-center justify-between text-xs font-bold text-[#034EA2] dark:text-sky-400">
                <span>
                  {isSelected ? 'Đang xem bảng điểm chi tiết bên dưới' : 'Nhấn để xem chi tiết lộ trình'}
                </span>
                <Sparkles className="w-3.5 h-3.5" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Detailed Tables for Selected Strategy */}
      {selectedPlan && (
        <div className="space-y-6">
          {/* Table 1: Strategic Retake Recommendations + Interactive What-If Checkboxes */}
          {(selectedPlan.retake_recommendations.length > 0 || excludedCourseObjs.length > 0) && (
            <div
              className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden"
              data-testid="retake-recommendations-table"
            >
              <div className="p-4 sm:p-5 bg-amber-50/70 dark:bg-amber-950/30 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h4 className="text-base font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 text-amber-600" />
                    Bảng 1: Danh sách Môn nên Học cải thiện ({selectedPlan.retake_course_count} môn • {selectedPlan.retake_credits} TC)
                  </h4>
                  <p className="text-xs text-slate-600 dark:text-slate-400 mt-0.5">
                    Bật/Tắt ô tick <strong>What-If</strong> ở từng môn để chạy lại MILP tức thì và xem sự thay đổi áp lực trên các môn còn lại.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs sm:text-sm">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800 text-xs font-bold text-slate-600 dark:text-slate-300 uppercase border-b border-slate-200 dark:border-slate-800">
                      <th className="py-3 px-4 text-center">What-If</th>
                      <th className="py-3 px-4">Mã MH</th>
                      <th className="py-3 px-4">Tên học phần</th>
                      <th className="py-3 px-3 text-center">TC</th>
                      <th className="py-3 px-3 text-center">Độ khó AI</th>
                      <th className="py-3 px-4">Điểm hiện tại → Cần cải thiện</th>
                      <th className="py-3 px-4 text-center">Mức tăng GPA</th>
                      <th className="py-3 px-4">Lý do AI chọn</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {selectedPlan.retake_recommendations
                      .filter((rec) => !excludedRetakes.includes(rec.course_code.toUpperCase()))
                      .map((rec) => (
                      <tr key={rec.course_code} className="hover:bg-amber-50/30 dark:hover:bg-slate-800/50">
                        <td className="py-3 px-4 text-center">
                          <input
                            type="checkbox"
                            checked={!excludedRetakes.includes(rec.course_code.toUpperCase())}
                            data-testid={`whatif-retake-checkbox-${rec.course_code}`}
                            aria-label={`What-If học cải thiện ${rec.course_code}`}
                            onChange={(e) =>
                              onToggleCourseRetakeWhatIf(rec.course_code, e.target.checked)
                            }
                            className="w-4 h-4 accent-[#034EA2] cursor-pointer"
                          />
                        </td>
                        <td className="py-3 px-4 font-extrabold text-[#034EA2] dark:text-sky-400">
                          {rec.course_code}
                        </td>
                        <td className="py-3 px-4 font-semibold text-slate-900 dark:text-white">
                          {rec.course_name}
                        </td>
                        <td className="py-3 px-3 text-center font-bold">{rec.credits}</td>
                        <td className="py-3 px-3 text-center">
                          <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                            {rec.difficulty_score.toFixed(1)}
                          </span>
                        </td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="font-bold text-rose-600 dark:text-rose-400">
                            {rec.old_letter_grade} ({rec.old_gpa_4.toFixed(1)})
                          </span>
                          <span className="mx-2 text-slate-400">→</span>
                          <span className="px-2 py-0.5 rounded-md bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 font-extrabold">
                            {rec.target_letter_grade} ({rec.target_gpa_4.toFixed(1)} • ≥ {rec.min_score_10.toFixed(1)})
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-extrabold text-emerald-600 dark:text-emerald-400">
                          +{rec.gpa_gain_contribution.toFixed(2)}
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-600 dark:text-slate-300 max-w-sm">
                          {rec.reason_vi}
                        </td>
                      </tr>
                    ))}

                    {/* Show excluded What-If courses so user can re-enable them with 1 click */}
                    {excludedCourseObjs.map((ex) => (
                      <tr
                        key={`excluded-${ex.course_code}`}
                        className="bg-slate-50/80 dark:bg-slate-800/40 opacity-75"
                      >
                        <td className="py-2.5 px-4 text-center">
                          <input
                            type="checkbox"
                            checked={false}
                            data-testid={`whatif-retake-checkbox-${ex.course_code}`}
                            aria-label={`Bật lại học cải thiện ${ex.course_code}`}
                            onChange={(e) =>
                              onToggleCourseRetakeWhatIf(ex.course_code, e.target.checked)
                            }
                            className="w-4 h-4 accent-[#034EA2] cursor-pointer"
                          />
                        </td>
                        <td className="py-2.5 px-4 font-bold text-slate-500 line-through">
                          {ex.course_code}
                        </td>
                        <td className="py-2.5 px-4 text-slate-500">{ex.course_name}</td>
                        <td className="py-2.5 px-3 text-center text-slate-500">{ex.credits}</td>
                        <td className="py-2.5 px-3 text-center text-slate-400">—</td>
                        <td colSpan={3} className="py-2.5 px-4 text-xs italic text-slate-500">
                          Đã tắt học cải thiện trong thử nghiệm What-If (Tích lại để cho phép AI xét cải thiện).
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Table 2: Minimum Required Grades for Every Remaining Course in Curriculum */}
          {selectedPlan.feasible && (
            <div
              className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden"
              data-testid="remaining-courses-plan-table"
            >
              <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h4 className="text-base font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
                    <BookOpen className="w-4 h-4 text-[#034EA2] dark:text-sky-400" />
                    Bảng 2: Điểm Tối thiểu Cần đạt cho Từng Môn còn lại trong CTĐT ({selectedPlan.remaining_course_plans.length} môn)
                  </h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Phân bổ điểm tối ưu theo từng học kỳ giúp đạt GPA {selectedPlan.projected_gpa_4.toFixed(2)} với áp lực thấp nhất.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs sm:text-sm">
                  <thead>
                    <tr className="bg-slate-50 dark:bg-slate-800 text-xs font-bold text-slate-600 dark:text-slate-300 uppercase border-b border-slate-200 dark:border-slate-800">
                      <th className="py-3 px-4">Mã MH</th>
                      <th className="py-3 px-4">Tên môn học còn lại</th>
                      <th className="py-3 px-3 text-center">HK dự kiến</th>
                      <th className="py-3 px-3 text-center">TC</th>
                      <th className="py-3 px-4">Độ khó AI</th>
                      <th className="py-3 px-4">Điểm tối thiểu cần đạt</th>
                      <th className="py-3 px-4">Giảm tải nhờ Học cải thiện</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {selectedPlan.remaining_course_plans.map((rem) => (
                      <tr key={rem.course_code} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-2.5 px-4 font-bold text-[#034EA2] dark:text-sky-400 whitespace-nowrap">
                          {rem.course_code}
                        </td>
                        <td className="py-2.5 px-4 font-medium text-slate-900 dark:text-white">
                          {rem.course_name}
                          {rem.requires_min_c && (
                            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 font-bold">
                              Sàn ≥ C
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-center text-slate-600 dark:text-slate-300 font-medium">
                          HK{rem.recommended_semester}
                        </td>
                        <td className="py-2.5 px-3 text-center font-bold">{rem.credits}</td>
                        <td className="py-2.5 px-4 whitespace-nowrap">
                          <span className="font-bold mr-1.5">{rem.difficulty_score.toFixed(1)}</span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${
                              TIER_BADGE[rem.difficulty_tier]
                            }`}
                          >
                            {rem.difficulty_tier}
                          </span>
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap">
                          <span className="px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/70 text-[#034EA2] dark:text-sky-300 font-extrabold">
                            {rem.required_letter_grade} ({rem.required_gpa_4.toFixed(1)}) • ≥{' '}
                            {rem.min_score_10.toFixed(1)} hệ 10
                          </span>
                        </td>
                        <td className="py-2.5 px-4 whitespace-nowrap">
                          {rem.grade_relief_vs_forward && rem.gpa_delta_vs_forward < 0 ? (
                            <span className="px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs font-extrabold">
                              Giảm nhẹ: {rem.grade_relief_vs_forward}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-400">Giữ chuẩn tối ưu</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
