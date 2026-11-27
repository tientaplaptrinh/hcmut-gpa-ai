import React, { useEffect, useMemo, useState } from 'react';
import {
  Upload,
  Sparkles,
  Plus,
  Trash2,
  Calculator,
  Award,
  Layers,
  Lock,
} from 'lucide-react';
import {
  calculateLiveGpa,
  fetchSampleMybk,
  optimizeRoadmap,
} from '../api';
import type {
  CurriculumSchema,
  GpaSummaryResponse,
  PreferenceMode,
  RoadmapOptimizationResponse,
  StudentCourseRecord,
} from '../types';
import { ImportTranscriptModal } from '../components/ImportTranscriptModal';
import { WhatIfRetakeControls } from '../components/WhatIfRetakeControls';
import { RoadmapComparisonPanel } from '../components/RoadmapComparisonPanel';

interface GpaRoadmapDashboardProps {
  curriculum: CurriculumSchema | null;
  completedCourses: StudentCourseRecord[];
  onChangeCompletedCourses: (courses: StudentCourseRecord[]) => void;
  difficultyOverrides: Record<string, number>;
}

const LETTER_OPTIONS = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F', 'MT', 'DT', 'VT'];

export const GpaRoadmapDashboard: React.FC<GpaRoadmapDashboardProps> = ({
  curriculum,
  completedCourses,
  onChangeCompletedCourses,
  difficultyOverrides,
}) => {
  const [gradeScaleMode, setGradeScaleMode] = useState<'SCALE_10' | 'LETTER'>('SCALE_10');
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [gpaSummary, setGpaSummary] = useState<GpaSummaryResponse | null>(null);
  const [selectedAddCode, setSelectedAddCode] = useState('');

  // Roadmap Optimizer Studio state
  const [targetGpa, setTargetGpa] = useState<number>(3.6);
  const [maxRetakeCourses, setMaxRetakeCourses] = useState<number>(3);
  const [preferenceMode, setPreferenceMode] = useState<PreferenceMode>('BALANCED');
  const [pinnedRetakes, setPinnedRetakes] = useState<string[]>([]);
  const [excludedRetakes, setExcludedRetakes] = useState<string[]>([]);
  const [roadmapResult, setRoadmapResult] = useState<RoadmapOptimizationResponse | null>(null);
  const [optimizing, setOptimizing] = useState(false);

  // Live GPA calculation whenever completedCourses or curriculum changes
  useEffect(() => {
    if (!curriculum) return;
    let cancelled = false;
    calculateLiveGpa(curriculum.major_code, curriculum.cohort, completedCourses)
      .then((res) => {
        if (!cancelled) setGpaSummary(res);
      })
      .catch((err) => console.error('GPA calculation error:', err));
    return () => {
      cancelled = true;
    };
  }, [curriculum, completedCourses]);

  const runOptimization = async (
    customPinned = pinnedRetakes,
    customExcluded = excludedRetakes,
    customMaxRetakes = maxRetakeCourses,
    customMode = preferenceMode,
    customTarget = targetGpa
  ) => {
    if (!curriculum) return;
    setOptimizing(true);
    try {
      const res = await optimizeRoadmap({
        major_code: curriculum.major_code,
        cohort: curriculum.cohort,
        completed_courses: completedCourses,
        target_gpa: customTarget,
        max_retake_courses: customMaxRetakes,
        preference_mode: customMode,
        pinned_retakes: customPinned,
        excluded_retakes: customExcluded,
        user_difficulty_overrides: difficultyOverrides,
      });
      setRoadmapResult(res);
    } catch (err) {
      console.error('Roadmap optimization error:', err);
    } finally {
      setOptimizing(false);
    }
  };

  const handleQuickLoadSample = async () => {
    if (!curriculum) return;
    try {
      const sample = await fetchSampleMybk(curriculum.major_code, curriculum.cohort);
      onChangeCompletedCourses(sample.parsed.parsed_courses);
      setRoadmapResult(null);
      setPinnedRetakes([]);
      setExcludedRetakes([]);
    } catch (err) {
      console.error('Failed to load sample transcript:', err);
    }
  };

  const handleApplyImported = (
    imported: StudentCourseRecord[],
    mode: 'OVERWRITE' | 'MERGE'
  ) => {
    if (mode === 'OVERWRITE') {
      onChangeCompletedCourses(imported);
    } else {
      const mergedMap = new Map<string, StudentCourseRecord>();
      completedCourses.forEach((c) => mergedMap.set(c.course_code.toUpperCase(), c));
      imported.forEach((c) => mergedMap.set(c.course_code.toUpperCase(), c));
      onChangeCompletedCourses(Array.from(mergedMap.values()));
    }
    setRoadmapResult(null);
  };

  const handleScore10Change = (code: string, valStr: string) => {
    const num = parseFloat(valStr);
    onChangeCompletedCourses(
      completedCourses.map((c) =>
        c.course_code === code
          ? {
              ...c,
              score_10: Number.isNaN(num) ? 0 : Math.max(0, Math.min(10, num)),
              letter_grade: undefined,
              status: 'NORMAL',
            }
          : c
      )
    );
  };

  const handleLetterChange = (code: string, letter: string) => {
    onChangeCompletedCourses(
      completedCourses.map((c) =>
        c.course_code === code
          ? {
              ...c,
              score_10: null,
              letter_grade: letter,
              status:
                letter === 'MT' || letter === 'DT'
                  ? 'EXEMPT_PASS'
                  : letter === 'VT'
                  ? 'FAIL_SPECIAL'
                  : 'NORMAL',
            }
          : c
      )
    );
  };

  const handleDeleteCourse = (code: string) => {
    onChangeCompletedCourses(completedCourses.filter((c) => c.course_code !== code));
  };

  const handleAddManualCourse = () => {
    if (!curriculum || !selectedAddCode) return;
    const cItem = curriculum.courses.find((c) => c.course_code === selectedAddCode);
    if (!cItem) return;
    const newRec: StudentCourseRecord = {
      course_code: cItem.course_code,
      course_name: cItem.course_name,
      credits: cItem.credits,
      semester: `HK${cItem.recommended_semester}`,
      score_10: 8.0,
      letter_grade: 'B+',
      gpa_4: 3.5,
      status: 'NORMAL',
      counts_for_gpa: cItem.counts_for_gpa,
      is_elective: cItem.is_elective,
      requires_min_c: cItem.requires_min_c,
      passed: true,
      match_tier: 'MANUAL',
      match_confidence: 100,
      retake_count: 0,
      retake_history: [],
    };
    onChangeCompletedCourses([...completedCourses, newRec]);
    setSelectedAddCode('');
  };

  const handleTogglePinCourse = (code: string) => {
    const up = code.toUpperCase();
    const nextPins = pinnedRetakes.includes(up)
      ? pinnedRetakes.filter((x) => x !== up)
      : [...pinnedRetakes, up];
    const nextEx = excludedRetakes.filter((x) => x !== up);
    setPinnedRetakes(nextPins);
    setExcludedRetakes(nextEx);
    if (roadmapResult) {
      runOptimization(nextPins, nextEx);
    }
  };

  const handleToggleWhatIfRetake = (code: string, enableRetake: boolean) => {
    const up = code.toUpperCase();
    let nextEx = excludedRetakes;
    let nextPins = pinnedRetakes;
    if (!enableRetake) {
      nextEx = Array.from(new Set([...excludedRetakes, up]));
      nextPins = pinnedRetakes.filter((x) => x !== up);
    } else {
      nextEx = excludedRetakes.filter((x) => x !== up);
    }
    setExcludedRetakes(nextEx);
    setPinnedRetakes(nextPins);
    runOptimization(nextPins, nextEx);
  };

  const availableToAdd = useMemo(() => {
    if (!curriculum) return [];
    const existing = new Set(completedCourses.map((c) => c.course_code.toUpperCase()));
    return curriculum.courses.filter((c) => !existing.has(c.course_code.toUpperCase()));
  }, [curriculum, completedCourses]);

  const groupedBySemester = useMemo(() => {
    const displayList = gpaSummary?.normalized_courses || completedCourses;
    const groups: Record<string, StudentCourseRecord[]> = {};
    displayList.forEach((c) => {
      const sem = c.semester || 'Học kỳ đã tích lũy';
      if (!groups[sem]) groups[sem] = [];
      groups[sem].push(c);
    });
    return Object.entries(groups);
  }, [gpaSummary, completedCourses]);

  if (!curriculum) return null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6" data-testid="gpa-roadmap-dashboard">
      {/* Top Toolbar */}
      <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-[#034EA2] dark:text-sky-400 uppercase tracking-wider">
            <Calculator className="w-4 h-4" />
            Dashboard 2 • Tính GPA &amp; Tối ưu Lộ trình Cải thiện
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
            Bảng điểm Tích lũy &amp; AI Roadmap — {curriculum.major_name} ({curriculum.cohort})
          </h2>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="button"
            data-testid="open-import-modal-btn"
            onClick={() => setIsImportOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#034EA2] hover:bg-[#023e82] text-white font-bold text-xs sm:text-sm shadow-md cursor-pointer"
          >
            <Upload className="w-4 h-4" />
            Import bảng điểm MyBK / Excel
          </button>

          <button
            type="button"
            data-testid="quick-load-sample-btn"
            onClick={handleQuickLoadSample}
            className="inline-flex items-center gap-1.5 px-3.5 py-2.5 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#034EA2] dark:text-sky-300 border border-blue-200 dark:border-blue-800 font-bold text-xs sm:text-sm hover:bg-blue-100 cursor-pointer"
          >
            <Sparkles className="w-4 h-4" />
            Nạp bảng điểm mẫu GPA ~3.20
          </button>

          {completedCourses.length > 0 && (
            <button
              type="button"
              onClick={() => {
                onChangeCompletedCourses([]);
                setRoadmapResult(null);
              }}
              className="inline-flex items-center gap-1 px-3 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-slate-800 cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Xóa hết
            </button>
          )}
        </div>
      </div>

      {/* Live Sticky KPI Summary Bar */}
      <div
        className="sticky top-16 z-20 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 bg-slate-50/95 dark:bg-slate-950/95 backdrop-blur-xs py-2"
        data-testid="live-gpa-kpi-bar"
      >
        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="text-[11px] font-bold text-slate-500 uppercase">GPA Hệ 4.0</div>
          <div className="text-2xl font-extrabold text-[#034EA2] dark:text-sky-400 mt-1" data-testid="live-gpa-4">
            {gpaSummary ? gpaSummary.gpa_4.toFixed(2) : '0.00'}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">Quy chế ĐHBK làm tròn 0.01</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="text-[11px] font-bold text-slate-500 uppercase">GPA Hệ 10</div>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1" data-testid="live-gpa-10">
            {gpaSummary ? gpaSummary.gpa_10.toFixed(2) : '0.00'}
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">Điểm TB tích lũy thang 10</div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="text-[11px] font-bold text-slate-500 uppercase">Tín chỉ Tích lũy</div>
          <div className="text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
            {gpaSummary ? gpaSummary.earned_credits : 0}{' '}
            <span className="text-sm font-semibold text-slate-400">
              / {curriculum.total_credits} TC
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">
            Còn lại {gpaSummary ? gpaSummary.remaining_gpa_credits : curriculum.total_gpa_credits} TC tính GPA
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="text-[11px] font-bold text-slate-500 uppercase">Xếp loại Học lực</div>
          <div className="flex items-center gap-1.5 text-lg font-extrabold text-emerald-700 dark:text-emerald-400 mt-1.5">
            <Award className="w-5 h-5 shrink-0" />
            <span>{gpaSummary ? gpaSummary.honors_standing : 'Chưa có điểm'}</span>
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">≥ 3.60 Xuất sắc • ≥ 3.20 Giỏi</div>
        </div>

        <div className="col-span-2 sm:col-span-1 p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs">
          <div className="text-[11px] font-bold text-slate-500 uppercase">Trần GPA Tối đa</div>
          <div className="text-lg font-extrabold text-slate-900 dark:text-white mt-1">
            {gpaSummary ? gpaSummary.ceiling_gpa_no_retake.toFixed(2) : '4.00'}{' '}
            <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
              (Cải thiện: 4.00)
            </span>
          </div>
          <div className="text-[11px] text-slate-500 mt-0.5">Không học lại vs. Có học lại</div>
        </div>
      </div>

      {/* Semester-Grouped Editable Grade Entry Section */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#034EA2] dark:text-sky-400" />
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Bảng điểm các môn đã học ({completedCourses.length} môn)
            </h3>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Toggle 10-point vs Letter grade */}
            <div className="inline-flex rounded-xl border border-slate-200 dark:border-slate-700 p-0.5 bg-slate-100 dark:bg-slate-800">
              <button
                type="button"
                onClick={() => setGradeScaleMode('SCALE_10')}
                className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer ${
                  gradeScaleMode === 'SCALE_10'
                    ? 'bg-white dark:bg-slate-900 text-[#034EA2] dark:text-sky-400 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400'
                }`}
              >
                Nhập Thang 10
              </button>
              <button
                type="button"
                onClick={() => setGradeScaleMode('LETTER')}
                className={`px-3 py-1 rounded-lg text-xs font-bold cursor-pointer ${
                  gradeScaleMode === 'LETTER'
                    ? 'bg-white dark:bg-slate-900 text-[#034EA2] dark:text-sky-400 shadow-xs'
                    : 'text-slate-600 dark:text-slate-400'
                }`}
              >
                Nhập Điểm chữ
              </button>
            </div>

            {/* Quick Manual Add Course */}
            <div className="flex items-center gap-1.5">
              <select
                aria-label="Chọn môn thêm thủ công"
                value={selectedAddCode}
                onChange={(e) => setSelectedAddCode(e.target.value)}
                className="max-w-56 px-3 py-1.5 text-xs rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
              >
                <option value="">+ Chọn môn từ CTĐT...</option>
                {availableToAdd.map((c) => (
                  <option key={c.course_code} value={c.course_code}>
                    {c.course_code} — {c.course_name} ({c.credits} TC)
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={!selectedAddCode}
                onClick={handleAddManualCourse}
                className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#034EA2] text-white text-xs font-bold disabled:opacity-40 cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                Thêm
              </button>
            </div>
          </div>
        </div>

        {groupedBySemester.length === 0 ? (
          <div className="p-10 text-center space-y-3">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Chưa có môn học nào được nhập. Bấm <strong>"Import bảng điểm MyBK / Excel"</strong> hoặc{' '}
              <strong>"Nạp bảng điểm mẫu GPA ~3.20"</strong> để bắt đầu ngay!
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200 dark:divide-slate-800">
            {groupedBySemester.map(([semName, semCourses]) => (
              <div key={semName}>
                <div className="px-4 py-2 bg-slate-100/80 dark:bg-slate-800/70 text-xs font-extrabold text-slate-700 dark:text-slate-200 uppercase tracking-wide">
                  {semName} ({semCourses.length} học phần)
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs sm:text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold text-slate-500 uppercase">
                        <th className="py-2.5 px-4">Mã MH</th>
                        <th className="py-2.5 px-4">Tên học phần</th>
                        <th className="py-2.5 px-3 text-center">TC</th>
                        <th className="py-2.5 px-4 text-center">
                          {gradeScaleMode === 'SCALE_10' ? 'Điểm hệ 10' : 'Điểm chữ'}
                        </th>
                        <th className="py-2.5 px-3 text-center">Hệ 4.0</th>
                        <th className="py-2.5 px-4">Ghi chú Quy chế</th>
                        <th className="py-2.5 px-4 text-right">Thao tác</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                      {semCourses.map((c) => {
                        const isPinned = pinnedRetakes.includes(c.course_code.toUpperCase());
                        const canRetake = c.counts_for_gpa && (c.gpa_4 ?? 0) < 4.0;
                        return (
                          <tr key={c.course_code} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                            <td className="py-2.5 px-4 font-bold text-[#034EA2] dark:text-sky-400">
                              {c.course_code}
                            </td>
                            <td className="py-2.5 px-4 font-medium text-slate-900 dark:text-white">
                              {c.course_name}
                            </td>
                            <td className="py-2.5 px-3 text-center font-semibold">{c.credits}</td>
                            <td className="py-2.5 px-4 text-center">
                              {gradeScaleMode === 'SCALE_10' && c.status !== 'EXEMPT_PASS' ? (
                                <input
                                  type="number"
                                  min={0}
                                  max={10}
                                  step={0.1}
                                  value={c.score_10 ?? 0}
                                  onChange={(e) => handleScore10Change(c.course_code, e.target.value)}
                                  className="w-20 px-2 py-1 text-center font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                                />
                              ) : (
                                <select
                                  value={c.letter_grade || 'B'}
                                  onChange={(e) => handleLetterChange(c.course_code, e.target.value)}
                                  className="px-2.5 py-1 font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800"
                                >
                                  {LETTER_OPTIONS.map((lg) => (
                                    <option key={lg} value={lg}>
                                      {lg}
                                    </option>
                                  ))}
                                </select>
                              )}
                            </td>
                            <td className="py-2.5 px-3 text-center font-extrabold">
                              {c.counts_for_gpa && c.gpa_4 !== null && c.gpa_4 !== undefined
                                ? `${c.letter_grade} (${c.gpa_4.toFixed(1)})`
                                : c.letter_grade || '—'}
                            </td>
                            <td className="py-2.5 px-4">
                              <div className="flex flex-wrap items-center gap-1.5">
                                {!c.counts_for_gpa && (
                                  <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                                    Không tính GPA
                                  </span>
                                )}
                                {c.retake_count > 0 && (
                                  <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                                    Giữ điểm cao nhất ({c.retake_history.map((h) => h.letter_grade).join('→')})
                                  </span>
                                )}
                                {c.requires_min_c && !c.passed && (
                                  <span className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-rose-100 text-rose-800">
                                    Chưa đạt sàn C (≥ 5.5)
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-2.5 px-4 text-right whitespace-nowrap space-x-1.5">
                              {canRetake && (
                                <button
                                  type="button"
                                  title="Ghim bắt buộc học cải thiện môn này"
                                  onClick={() => handleTogglePinCourse(c.course_code)}
                                  className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-bold border cursor-pointer ${
                                    isPinned
                                      ? 'bg-[#034EA2] text-white border-[#034EA2]'
                                      : 'border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-blue-400'
                                  }`}
                                >
                                  <Lock className="w-3 h-3" />
                                  {isPinned ? 'Đã ghim' : 'Ghim cải thiện'}
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => handleDeleteCourse(c.course_code)}
                                className="p-1.5 text-slate-400 hover:text-rose-600 cursor-pointer"
                                title="Xóa môn"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Bottom Section: Target GPA & Optimal Roadmap Studio */}
      <WhatIfRetakeControls
        targetGpa={targetGpa}
        onChangeTargetGpa={setTargetGpa}
        maxRetakeCourses={maxRetakeCourses}
        onChangeMaxRetakes={setMaxRetakeCourses}
        preferenceMode={preferenceMode}
        onChangePreferenceMode={setPreferenceMode}
        pinnedRetakes={pinnedRetakes}
        excludedRetakes={excludedRetakes}
        onResetWhatIf={() => {
          setPinnedRetakes([]);
          setExcludedRetakes([]);
          if (roadmapResult) runOptimization([], []);
        }}
        onOptimize={() => runOptimization()}
        optimizing={optimizing}
      />

      <RoadmapComparisonPanel
        result={roadmapResult}
        completedCourses={gpaSummary?.normalized_courses || completedCourses}
        excludedRetakes={excludedRetakes}
        onToggleCourseRetakeWhatIf={handleToggleWhatIfRetake}
      />

      <ImportTranscriptModal
        isOpen={isImportOpen}
        onClose={() => setIsImportOpen(false)}
        majorCode={curriculum.major_code}
        cohort={curriculum.cohort}
        curriculumCourses={curriculum.courses}
        onApply={handleApplyImported}
      />
    </div>
  );
};
