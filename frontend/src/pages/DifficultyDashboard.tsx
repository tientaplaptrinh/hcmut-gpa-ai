import React, { useMemo, useState } from 'react';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
} from 'recharts';
import {
  Flame,
  Search,
  Sliders,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  ArrowRight,
  Layers,
  BookOpen,
  GitBranch,
} from 'lucide-react';
import type {
  CourseDifficultyPrediction,
  DifficultyDashboardResponse,
  DifficultyTier,
} from '../types';

interface DifficultyDashboardProps {
  data: DifficultyDashboardResponse | null;
  loading: boolean;
  overrides: Record<string, number>;
  onUpdateOverride: (courseCode: string, value: number | null) => void;
  onResetAllOverrides: () => void;
  onGoToGpaDashboard: () => void;
}

const TIER_BADGE_CLASSES: Record<DifficultyTier, string> = {
  'Dễ': 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  'Trung bình':
    'bg-sky-100 text-sky-800 dark:bg-sky-950/70 dark:text-sky-300 border-sky-200 dark:border-sky-800',
  'Khó':
    'bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300 border-amber-200 dark:border-amber-800',
  'Rất khó':
    'bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300 border-rose-200 dark:border-rose-800',
};

const TIER_DOT_COLORS: Record<DifficultyTier, string> = {
  'Dễ': '#10b981',
  'Trung bình': '#0ea5e9',
  'Khó': '#f59e0b',
  'Rất khó': '#f43f5e',
};

export const DifficultyDashboard: React.FC<DifficultyDashboardProps> = ({
  data,
  loading,
  overrides,
  onUpdateOverride,
  onResetAllOverrides,
  onGoToGpaDashboard,
}) => {
  const [search, setSearch] = useState('');
  const [blockFilter, setBlockFilter] = useState<string>('ALL');
  const [tierFilter, setTierFilter] = useState<string>('ALL');
  const [semesterFilter, setSemesterFilter] = useState<string>('ALL');
  const [expandedCodes, setExpandedCodes] = useState<Record<string, boolean>>({});

  const toggleExpand = (code: string) => {
    setExpandedCodes((prev) => ({ ...prev, [code]: !prev[code] }));
  };

  const filteredCourses = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    return data.courses.filter((c) => {
      if (blockFilter !== 'ALL' && c.knowledge_block !== blockFilter) return false;
      if (tierFilter !== 'ALL' && c.tier !== tierFilter) return false;
      if (semesterFilter !== 'ALL' && String(c.recommended_semester) !== semesterFilter)
        return false;
      if (
        q &&
        !c.course_code.toLowerCase().includes(q) &&
        !c.course_name.toLowerCase().includes(q)
      ) {
        return false;
      }
      return true;
    });
  }, [data, search, blockFilter, tierFilter, semesterFilter]);

  const scatterData = useMemo(() => {
    if (!data) return [];
    return data.courses
      .filter((c) => c.counts_for_gpa && c.credits > 0)
      .map((c) => ({
        course_code: c.course_code,
        course_name: c.course_name,
        credits: c.credits,
        difficulty: c.effective_difficulty_score,
        semester: c.recommended_semester,
        tier: c.tier,
      }));
  }, [data]);

  if (loading || !data) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center">
        <div className="inline-block w-8 h-8 border-4 border-[#034EA2] border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
          Đang phân tích đồ thị tiên quyết &amp; dự đoán độ khó môn học...
        </p>
      </div>
    );
  }

  const overrideCount = Object.keys(overrides).length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6" data-testid="difficulty-dashboard">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-[#034EA2] dark:text-sky-400 uppercase tracking-wider">
            <Layers className="w-4 h-4" />
            Dashboard 1 • Phân tích Chương trình Đào tạo ĐHBK
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 dark:text-white mt-1">
            Dự đoán Độ khó Môn học — {data.major_name} ({data.cohort})
          </h2>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {data.faculty} • Mã ngành <strong>{data.major_code}</strong> • Mọi tùy chỉnh độ khó cá nhân của bạn sẽ được đồng bộ trực tiếp sang Bộ tối ưu Lộ trình GPA.
          </p>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          {overrideCount > 0 && (
            <button
              type="button"
              onClick={onResetAllOverrides}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Đặt lại ({overrideCount})
            </button>
          )}
          <button
            type="button"
            data-testid="goto-gpa-dashboard-btn"
            onClick={onGoToGpaDashboard}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#034EA2] hover:bg-[#023e82] text-white font-bold text-xs sm:text-sm shadow-sm transition-all cursor-pointer"
          >
            Tính GPA &amp; Lộ trình Tối ưu
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
        {/* Card 1: Total Credits & Avg Difficulty */}
        <div className="md:col-span-3 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-semibold text-slate-500 dark:text-slate-400">
              <span>TỔNG TÍN CHỈ CTĐT</span>
              <BookOpen className="w-4 h-4 text-[#034EA2] dark:text-sky-400" />
            </div>
            <div className="text-3xl font-extrabold text-slate-900 dark:text-white mt-2">
              {data.total_credits} <span className="text-base font-semibold text-slate-500">TC</span>
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {data.total_gpa_credits} TC tính GPA • {data.courses.length} học phần trong danh mục
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Độ khó TB toàn khóa:</span>
            <span className="text-sm font-extrabold text-[#034EA2] dark:text-sky-400">
              {data.average_difficulty.toFixed(2)} / 10
            </span>
          </div>
        </div>

        {/* Card 2: Knowledge Block Averages */}
        <div className="md:col-span-4 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase mb-3">
            Độ khó TB theo Khối kiến thức
          </div>
          <div className="space-y-2.5">
            {Object.entries(data.block_averages).map(([blk, val]) => (
              <div key={blk} className="space-y-1">
                <div className="flex justify-between text-xs font-semibold">
                  <span className="text-slate-700 dark:text-slate-300">{blk}</span>
                  <span className="text-slate-900 dark:text-white">{val.toFixed(1)} / 10</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      val >= 7.5
                        ? 'bg-rose-500'
                        : val >= 6.0
                        ? 'bg-amber-500'
                        : 'bg-emerald-500'
                    }`}
                    style={{ width: `${Math.min(100, val * 10)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Card 3: Top 5 Hardest Gatekeeper Courses */}
        <div className="md:col-span-5 bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-400 uppercase mb-3">
            <Flame className="w-4 h-4" />
            Top 5 Môn "Cửa ải" Khó nhất CTĐT
          </div>
          <div className="space-y-2">
            {data.top_gatekeeper_courses.map((gk, idx) => (
              <div
                key={gk.course_code}
                className="flex items-center justify-between gap-2 px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/70 border border-slate-200/70 dark:border-slate-700/60"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold text-rose-600 dark:text-rose-400">
                      #{idx + 1}
                    </span>
                    <span className="text-xs font-bold text-[#034EA2] dark:text-sky-400">
                      {gk.course_code}
                    </span>
                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
                      {gk.course_name}
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 text-xs font-extrabold rounded-md bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 shrink-0">
                  {gk.effective_difficulty_score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" data-testid="difficulty-charts-section">
        {/* Chart 1: Semester Difficulty & Credit Load Trend */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1">
            Xu hướng Độ khó &amp; Tải Tín chỉ theo Học kỳ
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
            Độ khó trung bình gia quyền tín chỉ từ HK1 đến HK8
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height={250} minWidth={260}>
              <ComposedChart data={data.semester_trends}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.25} />
                <XAxis dataKey="semester_label" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" domain={[0, 10]} tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar
                  yAxisId="right"
                  dataKey="total_credits"
                  name="Tổng tín chỉ"
                  fill="#93c5fd"
                  radius={[6, 6, 0, 0]}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="weighted_difficulty"
                  name="Độ khó TB"
                  stroke="#034EA2"
                  strokeWidth={3}
                  dot={{ r: 4 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Chart 2: Difficulty vs Credits Scatter */}
        <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1">
            Bản đồ Tương quan Độ khó vs. Số Tín chỉ
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
            Các môn góc trên bên phải (4 TC &amp; Độ khó ≥ 8.0) gây áp lực lớn nhất lên GPA
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height={250} minWidth={260}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.25} />
                <XAxis
                  type="number"
                  dataKey="credits"
                  name="Tín chỉ"
                  domain={[0, 5]}
                  tickCount={6}
                  tick={{ fontSize: 12 }}
                />
                <YAxis
                  type="number"
                  dataKey="difficulty"
                  name="Độ khó"
                  domain={[1, 10]}
                  tick={{ fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  formatter={(value, name) => [String(value), String(name)]}
                />
                <Scatter name="Học phần" data={scatterData}>
                  {scatterData.map((entry, idx) => (
                    <Cell
                      key={`cell-${entry.course_code}-${idx}`}
                      fill={TIER_DOT_COLORS[entry.tier]}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Filterable Course Table */}
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-slate-200 dark:border-slate-800 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-slate-900 dark:text-white">
              Danh mục Học phần &amp; Tùy chỉnh Độ khó Cá nhân ({filteredCourses.length} môn)
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Kéo thanh trượt để điều chỉnh cảm nhận độ khó cá nhân (VD: bạn giỏi Lập trình nhưng ngại Lý thuyết mạch).
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                data-testid="difficulty-course-search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Tìm mã hoặc tên môn..."
                className="pl-9 pr-3 py-1.5 text-xs sm:text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-[#034EA2]"
              />
            </div>

            <select
              aria-label="Lọc khối kiến thức"
              value={blockFilter}
              onChange={(e) => setBlockFilter(e.target.value)}
              className="px-3 py-1.5 text-xs sm:text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            >
              <option value="ALL">Tất cả khối kiến thức</option>
              <option value="Toán & KHTN">Toán &amp; KHTN</option>
              <option value="Giáo dục chung">Giáo dục chung</option>
              <option value="Cơ sở ngành">Cơ sở ngành</option>
              <option value="Chuyên ngành">Chuyên ngành</option>
              <option value="Tốt nghiệp">Tốt nghiệp</option>
            </select>

            <select
              aria-label="Lọc mức độ khó"
              value={tierFilter}
              onChange={(e) => setTierFilter(e.target.value)}
              className="px-3 py-1.5 text-xs sm:text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            >
              <option value="ALL">Mọi mức độ khó</option>
              <option value="Rất khó">Rất khó (≥ 8.0)</option>
              <option value="Khó">Khó (6.5–7.9)</option>
              <option value="Trung bình">Trung bình (4.5–6.4)</option>
              <option value="Dễ">Dễ (&lt; 4.5)</option>
            </select>

            <select
              aria-label="Lọc học kỳ"
              value={semesterFilter}
              onChange={(e) => setSemesterFilter(e.target.value)}
              className="px-3 py-1.5 text-xs sm:text-sm rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
            >
              <option value="ALL">Mọi học kỳ</option>
              {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                <option key={s} value={String(s)}>
                  Học kỳ {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 dark:bg-slate-800/80 text-xs font-bold text-slate-600 dark:text-slate-300 uppercase border-b border-slate-200 dark:border-slate-800">
                <th className="py-3 px-4">Mã MH</th>
                <th className="py-3 px-4">Tên học phần</th>
                <th className="py-3 px-3 text-center">HK</th>
                <th className="py-3 px-3 text-center">TC</th>
                <th className="py-3 px-3">Khối kiến thức</th>
                <th className="py-3 px-4">Độ khó AI &amp; Phân loại</th>
                <th className="py-3 px-4 w-64">Tùy chỉnh độ khó cá nhân</th>
                <th className="py-3 px-3 text-center">Chi tiết AI</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-800 text-sm">
              {filteredCourses.map((course: CourseDifficultyPrediction) => {
                const isExpanded = !!expandedCodes[course.course_code];
                const hasOverride = overrides[course.course_code] !== undefined;
                return (
                  <React.Fragment key={course.course_code}>
                    <tr className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="py-3 px-4 font-bold text-[#034EA2] dark:text-sky-400 whitespace-nowrap">
                        {course.course_code}
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-semibold text-slate-900 dark:text-white">
                          {course.course_name}
                        </div>
                        <div className="flex flex-wrap items-center gap-1.5 mt-1">
                          {course.is_elective && (
                            <span className="text-[11px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-950/70 dark:text-purple-300 font-medium">
                              Tự chọn
                            </span>
                          )}
                          {!course.counts_for_gpa && (
                            <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300 font-medium">
                              Không tính GPA
                            </span>
                          )}
                          {course.dependent_count > 0 && (
                            <span className="inline-flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                              <GitBranch className="w-3 h-3" />
                              Mở khóa {course.dependent_count} môn
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-center font-medium text-slate-600 dark:text-slate-300">
                        HK{course.recommended_semester}
                      </td>
                      <td className="py-3 px-3 text-center font-bold text-slate-800 dark:text-slate-200">
                        {course.credits}
                      </td>
                      <td className="py-3 px-3 text-xs font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">
                        {course.knowledge_block}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="text-base font-extrabold text-slate-900 dark:text-white">
                            {course.effective_difficulty_score.toFixed(1)}
                          </span>
                          <span
                            className={`px-2 py-0.5 text-xs font-bold rounded-full border ${
                              TIER_BADGE_CLASSES[course.tier]
                            }`}
                          >
                            {course.tier}
                          </span>
                        </div>
                        {hasOverride && (
                          <div className="text-[11px] text-blue-600 dark:text-sky-400 font-medium mt-0.5">
                            Mặc định AI: {course.ai_difficulty_score.toFixed(1)}
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <Sliders className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                          <input
                            type="range"
                            min={1.0}
                            max={10.0}
                            step={0.1}
                            aria-label={`Tùy chỉnh độ khó ${course.course_code}`}
                            value={course.effective_difficulty_score}
                            onChange={(e) =>
                              onUpdateOverride(course.course_code, parseFloat(e.target.value))
                            }
                            className="w-full accent-[#034EA2] cursor-pointer"
                          />
                          {hasOverride && (
                            <button
                              type="button"
                              title="Khôi phục độ khó AI"
                              onClick={() => onUpdateOverride(course.course_code, null)}
                              className="text-xs text-slate-400 hover:text-rose-500 cursor-pointer"
                            >
                              <RotateCcw className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <button
                          type="button"
                          onClick={() => toggleExpand(course.course_code)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-blue-100 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 cursor-pointer"
                        >
                          Vì sao?
                          {isExpanded ? (
                            <ChevronUp className="w-3.5 h-3.5" />
                          ) : (
                            <ChevronDown className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </td>
                    </tr>
                    {isExpanded && (
                      <tr className="bg-blue-50/50 dark:bg-slate-800/50">
                        <td colSpan={8} className="px-6 py-3.5 text-xs sm:text-sm">
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                            <div className="space-y-1.5 max-w-4xl">
                              <div className="font-bold text-[#034EA2] dark:text-sky-400">
                                Phân tích AI — Vì sao {course.course_code} ({course.course_name}) có độ khó {course.effective_difficulty_score.toFixed(1)}/10?
                              </div>
                              <p className="text-slate-700 dark:text-slate-200 leading-relaxed">
                                {course.rationale_vi}
                              </p>
                              <div className="flex flex-wrap gap-1.5 pt-1">
                                {course.challenge_tags.map((tag) => (
                                  <span
                                    key={tag}
                                    className="px-2 py-0.5 rounded-md bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-700 dark:text-slate-300"
                                  >
                                    #{tag}
                                  </span>
                                ))}
                                {course.prerequisites.length > 0 && (
                                  <span className="px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 text-xs font-semibold text-amber-800 dark:text-amber-300">
                                    Tiên quyết: {course.prerequisites.join(', ')}
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
