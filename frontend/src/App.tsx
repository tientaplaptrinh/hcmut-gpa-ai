import React, { useEffect, useState } from 'react';
import {
  GraduationCap,
  Moon,
  Sun,
  BarChart3,
  Calculator,
  Settings2,
} from 'lucide-react';
import {
  fetchCurriculum,
  fetchDifficultyDashboard,
  fetchMajors,
} from './api';
import type {
  CurriculumSchema,
  DifficultyDashboardResponse,
  MajorInfo,
  StudentCourseRecord,
} from './types';
import { OnboardingPage } from './pages/OnboardingPage';
import { DifficultyDashboard } from './pages/DifficultyDashboard';
import { GpaRoadmapDashboard } from './pages/GpaRoadmapDashboard';

type ActiveView = 'ONBOARDING' | 'DIFFICULTY' | 'GPA_ROADMAP';

const STORAGE_PREFIX = 'hcmut_gpa_ai_v1';

export const App: React.FC = () => {
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    return localStorage.getItem(`${STORAGE_PREFIX}_dark`) === 'true';
  });

  const [majors, setMajors] = useState<MajorInfo[]>([]);
  const [majorCode, setMajorCode] = useState<string>(() => {
    return localStorage.getItem(`${STORAGE_PREFIX}_major`) || '7520201';
  });
  const [cohort, setCohort] = useState<string>(() => {
    return localStorage.getItem(`${STORAGE_PREFIX}_cohort`) || 'K2025';
  });
  const [activeView, setActiveView] = useState<ActiveView>(() => {
    const saved = localStorage.getItem(`${STORAGE_PREFIX}_onboarded`);
    return saved === 'true' ? 'DIFFICULTY' : 'ONBOARDING';
  });

  const [curriculum, setCurriculum] = useState<CurriculumSchema | null>(null);
  const [difficultyData, setDifficultyData] =
    useState<DifficultyDashboardResponse | null>(null);
  const [loadingCurr, setLoadingCurr] = useState<boolean>(false);

  const profileKey = `${STORAGE_PREFIX}_${majorCode}_${cohort}`;

  const [difficultyOverrides, setDifficultyOverrides] = useState<Record<string, number>>(() => {
    try {
      const raw = localStorage.getItem(`${profileKey}_overrides`);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  const [completedCourses, setCompletedCourses] = useState<StudentCourseRecord[]>(() => {
    try {
      const raw = localStorage.getItem(`${profileKey}_grades`);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  });

  // Sync dark mode class on <html>
  useEffect(() => {
    const root = document.documentElement;
    if (darkMode) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem(`${STORAGE_PREFIX}_dark`, String(darkMode));
  }, [darkMode]);

  // Load major catalog once
  useEffect(() => {
    fetchMajors()
      .then(setMajors)
      .catch((err) => console.error('Failed to load majors:', err));
  }, []);

  // Reload scoped localStorage when (majorCode, cohort) changes
  useEffect(() => {
    localStorage.setItem(`${STORAGE_PREFIX}_major`, majorCode);
    localStorage.setItem(`${STORAGE_PREFIX}_cohort`, cohort);
    const key = `${STORAGE_PREFIX}_${majorCode}_${cohort}`;
    try {
      const savedOverrides = localStorage.getItem(`${key}_overrides`);
      setDifficultyOverrides(savedOverrides ? JSON.parse(savedOverrides) : {});
    } catch {
      setDifficultyOverrides({});
    }
    try {
      const savedGrades = localStorage.getItem(`${key}_grades`);
      setCompletedCourses(savedGrades ? JSON.parse(savedGrades) : []);
    } catch {
      setCompletedCourses([]);
    }
  }, [majorCode, cohort]);

  // Persist overrides & completedCourses
  useEffect(() => {
    localStorage.setItem(`${profileKey}_overrides`, JSON.stringify(difficultyOverrides));
  }, [profileKey, difficultyOverrides]);

  useEffect(() => {
    localStorage.setItem(`${profileKey}_grades`, JSON.stringify(completedCourses));
  }, [profileKey, completedCourses]);

  // Fetch curriculum whenever majorCode or cohort changes
  useEffect(() => {
    let cancelled = false;
    setLoadingCurr(true);
    fetchCurriculum(majorCode, cohort)
      .then((curr) => {
        if (!cancelled) setCurriculum(curr);
      })
      .catch((err) => console.error('Curriculum load error:', err))
      .finally(() => {
        if (!cancelled) setLoadingCurr(false);
      });
    return () => {
      cancelled = true;
    };
  }, [majorCode, cohort]);

  // Fetch difficulty predictions whenever majorCode, cohort, or difficultyOverrides changes
  useEffect(() => {
    let cancelled = false;
    fetchDifficultyDashboard(majorCode, cohort, difficultyOverrides)
      .then((res) => {
        if (!cancelled) setDifficultyData(res);
      })
      .catch((err) => console.error('Difficulty dashboard error:', err));
    return () => {
      cancelled = true;
    };
  }, [majorCode, cohort, difficultyOverrides]);

  const handleOnboardingStart = (nextMajor: string, nextCohort: string) => {
    setMajorCode(nextMajor);
    setCohort(nextCohort);
    localStorage.setItem(`${STORAGE_PREFIX}_onboarded`, 'true');
    setActiveView('DIFFICULTY');
  };

  const handleUpdateOverride = (code: string, val: number | null) => {
    setDifficultyOverrides((prev) => {
      const next = { ...prev };
      if (val === null) {
        delete next[code];
      } else {
        next[code] = val;
      }
      return next;
    });
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 h-16 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xs border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto h-full flex items-center justify-between gap-3">
          {/* Brand */}
          <button
            type="button"
            onClick={() => setActiveView('ONBOARDING')}
            className="flex items-center gap-2.5 text-left cursor-pointer"
          >
            <div className="w-9 h-9 rounded-xl bg-[#034EA2] flex items-center justify-center text-white font-extrabold shadow-xs">
              BK
            </div>
            <div className="hidden sm:block">
              <div className="text-sm font-extrabold tracking-tight text-slate-900 dark:text-white leading-none">
                BK-GPA &amp; Roadmap AI
              </div>
              <div className="text-[11px] font-semibold text-[#034EA2] dark:text-sky-400 mt-0.5">
                HCMUT Academic Intelligence
              </div>
            </div>
          </button>

          {/* Center Navigation Tabs */}
          {activeView !== 'ONBOARDING' && (
            <nav className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
              <button
                type="button"
                data-testid="nav-difficulty-tab"
                onClick={() => setActiveView('DIFFICULTY')}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                  activeView === 'DIFFICULTY'
                    ? 'bg-[#034EA2] text-white shadow-xs'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <BarChart3 className="w-4 h-4" />
                <span>1. Dự đoán Độ khó</span>
              </button>

              <button
                type="button"
                data-testid="nav-gpa-roadmap-tab"
                onClick={() => setActiveView('GPA_ROADMAP')}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs sm:text-sm font-bold transition-all cursor-pointer ${
                  activeView === 'GPA_ROADMAP'
                    ? 'bg-[#034EA2] text-white shadow-xs'
                    : 'text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                <Calculator className="w-4 h-4" />
                <span>2. Tính GPA &amp; Lộ trình AI</span>
              </button>
            </nav>
          )}

          {/* Right Quick Switchers & Dark Mode */}
          <div className="flex items-center gap-2">
            {activeView !== 'ONBOARDING' && majors.length > 0 && (
              <div className="hidden xl:flex items-center gap-1.5">
                <select
                  aria-label="Đổi nhanh ngành học"
                  value={majorCode}
                  onChange={(e) => setMajorCode(e.target.value)}
                  className="px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                >
                  {majors.map((m) => (
                    <option key={m.major_code} value={m.major_code}>
                      {m.major_code} - {m.major_name}
                    </option>
                  ))}
                </select>

                <select
                  aria-label="Đổi nhanh khóa"
                  value={cohort}
                  onChange={(e) => setCohort(e.target.value)}
                  className="px-2 py-1.5 text-xs font-bold rounded-lg border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800"
                >
                  {['K2026', 'K2025', 'K2024', 'K2023', 'K2022', 'K2021'].map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  title="Đổi Ngành / Khóa"
                  onClick={() => setActiveView('ONBOARDING')}
                  className="p-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer"
                >
                  <Settings2 className="w-4 h-4" />
                </button>
              </div>
            )}

            <button
              type="button"
              data-testid="dark-mode-toggle"
              aria-label="Chuyển chế độ Sáng/Tối"
              onClick={() => setDarkMode((d) => !d)}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-amber-300 hover:bg-slate-100 dark:hover:bg-slate-700 cursor-pointer"
            >
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1">
        {activeView === 'ONBOARDING' && (
          <OnboardingPage
            majors={majors}
            selectedMajor={majorCode}
            selectedCohort={cohort}
            onStart={handleOnboardingStart}
          />
        )}

        {activeView === 'DIFFICULTY' && (
          <DifficultyDashboard
            data={difficultyData}
            loading={loadingCurr && !difficultyData}
            overrides={difficultyOverrides}
            onUpdateOverride={handleUpdateOverride}
            onResetAllOverrides={() => setDifficultyOverrides({})}
            onGoToGpaDashboard={() => setActiveView('GPA_ROADMAP')}
          />
        )}

        {activeView === 'GPA_ROADMAP' && (
          <GpaRoadmapDashboard
            curriculum={curriculum}
            completedCourses={completedCourses}
            onChangeCompletedCourses={setCompletedCourses}
            difficultyOverrides={difficultyOverrides}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="py-4 px-6 border-t border-slate-200 dark:border-slate-800 text-center text-xs text-slate-500 dark:text-slate-400">
        <span className="inline-flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
          <GraduationCap className="w-3.5 h-3.5 text-[#034EA2] dark:text-sky-400" />
          BK-GPA &amp; Optimal Study Roadmap AI
        </span>{' '}
        • Dữ liệu CTĐT chính thức ĐH Bách Khoa — ĐHQG TP.HCM (hcmut.edu.vn) • Tối ưu hóa MILP (SciPy HiGHS)
      </footer>
    </div>
  );
};

export default App;
