import React from 'react';
import { Sparkles, Target, RotateCcw, SlidersHorizontal, Lock, Ban } from 'lucide-react';
import type { PreferenceMode } from '../types';

interface WhatIfRetakeControlsProps {
  targetGpa: number;
  onChangeTargetGpa: (val: number) => void;
  maxRetakeCourses: number;
  onChangeMaxRetakes: (val: number) => void;
  preferenceMode: PreferenceMode;
  onChangePreferenceMode: (mode: PreferenceMode) => void;
  pinnedRetakes: string[];
  excludedRetakes: string[];
  onResetWhatIf: () => void;
  onOptimize: () => void;
  optimizing: boolean;
}

const TARGET_CHIPS = [
  { label: 'Khá (2.50)', value: 2.5 },
  { label: 'Giỏi (3.20)', value: 3.2 },
  { label: 'Xuất sắc (3.60)', value: 3.6 },
  { label: 'Đỉnh cao (3.80)', value: 3.8 },
];

export const WhatIfRetakeControls: React.FC<WhatIfRetakeControlsProps> = ({
  targetGpa,
  onChangeTargetGpa,
  maxRetakeCourses,
  onChangeMaxRetakes,
  preferenceMode,
  onChangePreferenceMode,
  pinnedRetakes,
  excludedRetakes,
  onResetWhatIf,
  onOptimize,
  optimizing,
}) => {
  const hasWhatIfOverrides = pinnedRetakes.length > 0 || excludedRetakes.length > 0;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm p-5 sm:p-6 space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-[#034EA2] dark:text-sky-400 uppercase tracking-wider">
            <Target className="w-4 h-4" />
            Target GPA &amp; Joint Optimal Roadmap Studio (MILP)
          </div>
          <h3 className="text-lg sm:text-xl font-extrabold text-slate-900 dark:text-white mt-0.5">
            Thiết lập GPA Mục tiêu &amp; Chiến lược Học cải thiện
          </h3>
        </div>

        <button
          type="button"
          data-testid="optimize-roadmap-btn"
          onClick={onOptimize}
          disabled={optimizing}
          className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-[#034EA2] to-[#1488DB] hover:opacity-95 text-white font-extrabold text-sm shadow-lg shadow-blue-900/20 transition-all cursor-pointer disabled:opacity-50"
        >
          <Sparkles className={`w-4 h-4 ${optimizing ? 'animate-spin' : ''}`} />
          {optimizing ? 'Đang giải MILP toàn cục...' : 'AI Tìm lộ trình tối ưu nhất'}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Column 1: Target GPA Input + Slider + Quick Chips */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between">
            <label
              htmlFor="target-gpa-input"
              className="text-sm font-bold text-slate-800 dark:text-slate-200"
            >
              GPA Tốt nghiệp Mong muốn (Thang 4.0)
            </label>
            <input
              id="target-gpa-input"
              data-testid="target-gpa-input"
              type="number"
              min={1.0}
              max={4.0}
              step={0.01}
              value={targetGpa}
              onChange={(e) => {
                const v = parseFloat(e.target.value);
                if (!Number.isNaN(v)) {
                  onChangeTargetGpa(Math.max(1.0, Math.min(4.0, v)));
                }
              }}
              className="w-24 px-3 py-1.5 text-right text-base font-extrabold rounded-xl border-2 border-[#034EA2] bg-blue-50/60 dark:bg-slate-800 text-[#034EA2] dark:text-sky-300 focus:outline-none"
            />
          </div>

          <input
            type="range"
            min={2.0}
            max={4.0}
            step={0.01}
            value={Math.max(2.0, targetGpa)}
            onChange={(e) => onChangeTargetGpa(parseFloat(e.target.value))}
            className="w-full accent-[#034EA2] cursor-pointer"
          />

          <div className="flex flex-wrap gap-2">
            {TARGET_CHIPS.map((chip) => (
              <button
                key={chip.label}
                type="button"
                data-testid={`target-chip-${chip.value.toFixed(2)}`}
                onClick={() => onChangeTargetGpa(chip.value)}
                className={`px-3 py-1 rounded-lg text-xs font-bold border transition-all cursor-pointer ${
                  Math.abs(targetGpa - chip.value) < 0.005
                    ? 'bg-[#034EA2] text-white border-[#034EA2]'
                    : 'bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                }`}
              >
                {chip.label}
              </button>
            ))}
          </div>
        </div>

        {/* Column 2: Max Retake Courses Budget */}
        <div className="lg:col-span-3 space-y-2.5">
          <div className="flex items-center gap-1.5 text-sm font-bold text-slate-800 dark:text-slate-200">
            <SlidersHorizontal className="w-4 h-4 text-[#034EA2] dark:text-sky-400" />
            Số môn cải thiện tối đa
          </div>
          <div className="grid grid-cols-5 gap-1.5">
            {[0, 1, 2, 3, 4].map((num) => (
              <button
                key={num}
                type="button"
                data-testid={`max-retake-btn-${num}`}
                onClick={() => onChangeMaxRetakes(num)}
                className={`py-2 rounded-xl text-xs font-extrabold border transition-all cursor-pointer ${
                  maxRetakeCourses === num
                    ? 'bg-[#034EA2] text-white border-[#034EA2]'
                    : 'bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                }`}
              >
                {num} môn
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Giới hạn số học phần đã học được phép đăng ký cải thiện điểm.
          </p>
        </div>

        {/* Column 3: Priority Mode */}
        <div className="lg:col-span-4 space-y-2.5">
          <div className="text-sm font-bold text-slate-800 dark:text-slate-200">
            Chế độ Ưu tiên Tối ưu hóa
          </div>
          <div className="grid grid-cols-3 gap-2">
            {(
              [
                { id: 'BALANCED', label: 'Cân bằng' },
                { id: 'MIN_EFFORT', label: 'Nhẹ áp lực nhất' },
                { id: 'NO_RETAKE', label: 'Không học lại' },
              ] as { id: PreferenceMode; label: string }[]
            ).map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => onChangePreferenceMode(opt.id)}
                className={`py-2 px-2.5 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                  preferenceMode === opt.id
                    ? 'bg-[#034EA2] text-white border-[#034EA2]'
                    : 'bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-blue-400'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400">
            Hàm mục tiêu lồi ưu tiên tránh ép điểm A ở các môn độ khó ≥ 8.0.
          </p>
        </div>
      </div>

      {/* Active What-If Locks / Exclusions Strip */}
      {hasWhatIfOverrides && (
        <div className="pt-3 border-t border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-bold text-slate-700 dark:text-slate-300">
              Ràng buộc What-If đang bật:
            </span>
            {pinnedRetakes.map((code) => (
              <span
                key={`pin-${code}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-100 text-[#034EA2] dark:bg-blue-950 dark:text-sky-300 font-bold"
              >
                <Lock className="w-3 h-3" />
                Bắt buộc cải thiện: {code}
              </span>
            ))}
            {excludedRetakes.map((code) => (
              <span
                key={`ex-${code}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 font-bold"
              >
                <Ban className="w-3 h-3" />
                Không học lại: {code}
              </span>
            ))}
          </div>

          <button
            type="button"
            onClick={onResetWhatIf}
            className="inline-flex items-center gap-1 text-xs font-bold text-slate-600 dark:text-slate-300 hover:text-[#034EA2] cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Xóa tùy chỉnh What-If
          </button>
        </div>
      )}
    </div>
  );
};
