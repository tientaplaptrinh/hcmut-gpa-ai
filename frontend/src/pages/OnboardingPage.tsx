import React, { useMemo, useState } from 'react';
import {
  GraduationCap,
  Search,
  Sparkles,
  BookOpen,
  Award,
  ArrowRight,
  CheckCircle2,
  Cpu,
} from 'lucide-react';
import type { MajorInfo } from '../types';

interface OnboardingPageProps {
  majors: MajorInfo[];
  selectedMajor: string;
  selectedCohort: string;
  onStart: (majorCode: string, cohort: string) => void;
}

const COHORT_OPTIONS = ['K2026', 'K2025', 'K2024', 'K2023', 'K2022', 'K2021'];

export const OnboardingPage: React.FC<OnboardingPageProps> = ({
  majors,
  selectedMajor,
  selectedCohort,
  onStart,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [majorCode, setMajorCode] = useState(selectedMajor || '7520201');
  const [cohort, setCohort] = useState(selectedCohort || 'K2025');

  const filteredMajors = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return majors;
    return majors.filter(
      (m) =>
        m.major_code.toLowerCase().includes(q) ||
        m.major_name.toLowerCase().includes(q) ||
        m.major_name_en.toLowerCase().includes(q) ||
        m.faculty.toLowerCase().includes(q)
    );
  }, [majors, searchQuery]);

  const currentMajorObj = useMemo(
    () => majors.find((m) => m.major_code === majorCode) || majors[0],
    [majors, majorCode]
  );

  return (
    <div className="min-h-[calc(100vh-4rem)] flex flex-col justify-center py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto w-full">
        {/* Hero Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-blue-100 dark:bg-blue-950/70 text-[#034EA2] dark:text-sky-300 text-xs font-semibold tracking-wide uppercase mb-4 border border-blue-200 dark:border-blue-800">
            <GraduationCap className="w-4 h-4" />
            Trường Đại học Bách Khoa — ĐHQG TP.HCM (HCMUT)
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-white tracking-tight">
            BK-GPA &amp; <span className="text-[#034EA2] dark:text-sky-400">Optimal Study Roadmap AI</span>
          </h1>
          <p className="mt-3 text-base sm:text-lg text-slate-600 dark:text-slate-300 max-w-3xl mx-auto">
            Hệ thống dự đoán độ khó học phần theo đồ thị tiên quyết CTĐT thực tế, tự động đọc bảng điểm{' '}
            <span className="font-semibold text-slate-800 dark:text-slate-100">MyBK</span> và giải bài toán tối ưu{' '}
            <span className="font-semibold text-[#034EA2] dark:text-sky-400">MILP</span> kết hợp học mới &amp; học cải thiện thông minh.
          </p>
        </div>

        {/* Main Onboarding Card */}
        <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
          <div className="bg-gradient-to-r from-[#034EA2] to-[#1488DB] px-6 py-4 text-white flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-5 h-5 text-sky-200" />
              <span className="font-bold text-base">Thiết lập Hồ sơ Chương trình Đào tạo</span>
            </div>
            <span className="text-xs bg-white/15 px-2.5 py-1 rounded-md font-medium">
              Quy chế ĐHBK QĐ 2931 &amp; 1259
            </span>
          </div>

          <div className="p-6 sm:p-8 space-y-6">
            {/* Step 1: Search & Choose Major */}
            <div>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <label
                  htmlFor="major-search-input"
                  className="block text-sm font-bold text-slate-800 dark:text-slate-200"
                >
                  1. Chọn Ngành học / Chương trình đào tạo (HCMUT)
                </label>
                <div className="relative w-full sm:w-72">
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    id="major-search-input"
                    data-testid="onboarding-major-search"
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Tìm mã ngành (VD: 7520201) hoặc tên..."
                    className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#034EA2]"
                  />
                </div>
              </div>

              {/* Accessible native select + rich interactive cards */}
              <select
                aria-label="Ngành học"
                data-testid="onboarding-major-select"
                value={majorCode}
                onChange={(e) => setMajorCode(e.target.value)}
                className="w-full mb-3 px-3.5 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-semibold text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#034EA2]"
              >
                {majors.map((m) => (
                  <option key={m.major_code} value={m.major_code}>
                    {m.major_code} — {m.major_name} ({m.total_credits} TC)
                  </option>
                ))}
              </select>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-72 overflow-y-auto pr-1">
                {filteredMajors.map((m) => {
                  const active = m.major_code === majorCode;
                  return (
                    <button
                      key={m.major_code}
                      type="button"
                      data-testid={`major-card-${m.major_code}`}
                      onClick={() => setMajorCode(m.major_code)}
                      className={`text-left p-3.5 rounded-xl border transition-all flex items-start justify-between gap-3 ${
                        active
                          ? 'border-[#034EA2] bg-blue-50/80 dark:bg-blue-950/40 ring-2 ring-[#034EA2]/30'
                          : 'border-slate-200 dark:border-slate-800 hover:border-blue-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900'
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 text-xs font-bold rounded bg-[#034EA2] text-white">
                            {m.major_code}
                          </span>
                          <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                            {m.total_credits} tín chỉ • {m.course_count} học phần
                          </span>
                        </div>
                        <div className="mt-1.5 font-bold text-sm text-slate-900 dark:text-white">
                          {m.major_name}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                          {m.faculty} • {m.program_type}
                        </div>
                      </div>
                      {active && (
                        <CheckCircle2 className="w-5 h-5 text-[#034EA2] dark:text-sky-400 shrink-0 mt-0.5" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Step 2: Select Cohort */}
            <div>
              <label className="block text-sm font-bold text-slate-800 dark:text-slate-200 mb-2.5">
                2. Chọn Khóa tuyển sinh / Năm áp dụng CTĐT
              </label>
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2.5">
                {COHORT_OPTIONS.map((c) => {
                  const active = cohort === c;
                  return (
                    <button
                      key={c}
                      type="button"
                      data-testid={`cohort-btn-${c}`}
                      onClick={() => setCohort(c)}
                      className={`py-2.5 px-3 rounded-xl font-bold text-sm border transition-all ${
                        active
                          ? 'bg-[#034EA2] text-white border-[#034EA2] shadow-sm'
                          : 'bg-slate-50 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                      }`}
                    >
                      {c}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Summary & Submit CTA */}
            <div className="pt-2 border-t border-slate-200 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
                Đang chọn:{' '}
                <strong className="text-slate-900 dark:text-white">
                  {currentMajorObj
                    ? `${currentMajorObj.major_code} - ${currentMajorObj.major_name}`
                    : majorCode}
                </strong>{' '}
                • Khóa <strong className="text-[#034EA2] dark:text-sky-400">{cohort}</strong>
              </div>

              <button
                type="button"
                data-testid="start-roadmap-btn"
                onClick={() => onStart(majorCode, cohort)}
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-[#034EA2] hover:bg-[#023e82] text-white font-bold text-sm shadow-lg shadow-blue-900/20 transition-all cursor-pointer"
              >
                Bắt đầu lập lộ trình
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* 3 Feature Pillars */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6">
          <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <BookOpen className="w-5 h-5 text-[#034EA2] dark:text-sky-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-xs text-slate-900 dark:text-white">
                CTĐT Chuẩn hcmut.edu.vn
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Đồ thị môn tiên quyết, khối kiến thức và học kỳ khuyến nghị cho từng khóa K2021–K2026.
              </p>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <Award className="w-5 h-5 text-[#034EA2] dark:text-sky-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-xs text-slate-900 dark:text-white">
                Quy chế Học vụ Bách Khoa
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Tự động loại trừ GDTC/GDQP/MT, giữ điểm cao nhất khi học lại và chọn tổ hợp tự chọn tối ưu.
              </p>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex items-start gap-3">
            <Cpu className="w-5 h-5 text-[#034EA2] dark:text-sky-400 shrink-0 mt-0.5" />
            <div>
              <div className="font-bold text-xs text-slate-900 dark:text-white">
                Tối ưu Toàn cục MILP
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Cân bằng giữa học mới và học cải thiện môn nhẹ để giảm áp lực đạt A ở các môn "sát thủ".
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
