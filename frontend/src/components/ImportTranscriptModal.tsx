import React, { useState } from 'react';
import {
  X,
  ClipboardPaste,
  FileSpreadsheet,
  Sparkles,
  Download,
  ShieldCheck,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';
import {
  fetchSampleMybk,
  parseMybkText,
  parseTranscriptFile,
  TEMPLATE_CSV_URL,
} from '../api';
import type {
  CourseItem,
  StudentCourseRecord,
  TranscriptParseResponse,
} from '../types';

interface ImportTranscriptModalProps {
  isOpen: boolean;
  onClose: () => void;
  majorCode: string;
  cohort: string;
  curriculumCourses: CourseItem[];
  onApply: (courses: StudentCourseRecord[], mode: 'OVERWRITE' | 'MERGE') => void;
}

export const ImportTranscriptModal: React.FC<ImportTranscriptModalProps> = ({
  isOpen,
  onClose,
  majorCode,
  cohort,
  curriculumCourses,
  onApply,
}) => {
  const [activeTab, setActiveTab] = useState<'MYBK_TEXT' | 'EXCEL_CSV'>('MYBK_TEXT');
  const [rawText, setRawText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<TranscriptParseResponse | null>(null);
  const [editedCourses, setEditedCourses] = useState<StudentCourseRecord[]>([]);

  if (!isOpen) return null;

  const handleLoadDemoSample = async () => {
    setLoading(true);
    setError(null);
    try {
      const sample = await fetchSampleMybk(majorCode, cohort);
      setRawText(sample.raw_text);
      setPreview(sample.parsed);
      setEditedCourses(sample.parsed.parsed_courses);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể tải dữ liệu mẫu MyBK.');
    } finally {
      setLoading(false);
    }
  };

  const handleParseText = async () => {
    if (!rawText.trim()) {
      setError('Vui lòng dán nội dung bảng điểm từ mybk.hcmut.edu.vn hoặc bấm Nạp mẫu thử.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await parseMybkText(rawText, majorCode, cohort);
      setPreview(res);
      setEditedCourses(res.parsed_courses);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi phân tích bảng điểm.');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await parseTranscriptFile(file, majorCode, cohort);
      setPreview(res);
      setEditedCourses(res.parsed_courses);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi đọc file Excel/CSV.');
    } finally {
      setLoading(false);
    }
  };

  const handleRemapCourse = (idx: number, targetCode: string) => {
    const target = curriculumCourses.find((c) => c.course_code === targetCode);
    if (!target) return;
    setEditedCourses((prev) =>
      prev.map((item, i) =>
        i === idx
          ? {
              ...item,
              course_code: target.course_code,
              course_name: target.course_name,
              credits: target.credits,
              is_elective: target.is_elective,
              counts_for_gpa: target.counts_for_gpa,
              requires_min_c: target.requires_min_c,
              match_tier: 'MANUAL',
              matched_curriculum_code: target.course_code,
            }
          : item
      )
    );
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 backdrop-blur-xs p-4 overflow-y-auto"
      data-testid="import-transcript-modal"
    >
      <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-[#034EA2] to-[#1488DB] text-white flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold">
              Import Bảng điểm Hàng loạt (MyBK Copy-Paste / Excel / CSV)
            </h3>
            <p className="text-xs text-sky-100 flex items-center gap-1.5 mt-0.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              Bảo mật tuyệt đối: Tự động xóa MSSV/Họ tên/Email trên RAM, không lưu file lên máy chủ.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg bg-white/15 hover:bg-white/25 text-white cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Tabs */}
        <div className="px-6 pt-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
          <button
            type="button"
            data-testid="tab-mybk-paste"
            onClick={() => setActiveTab('MYBK_TEXT')}
            className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-bold border-b-2 transition-colors cursor-pointer ${
              activeTab === 'MYBK_TEXT'
                ? 'border-[#034EA2] text-[#034EA2] dark:text-sky-400 dark:border-sky-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <ClipboardPaste className="w-4 h-4" />
            Dán trực tiếp từ MyBK
          </button>
          <button
            type="button"
            data-testid="tab-excel-upload"
            onClick={() => setActiveTab('EXCEL_CSV')}
            className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-bold border-b-2 transition-colors cursor-pointer ${
              activeTab === 'EXCEL_CSV'
                ? 'border-[#034EA2] text-[#034EA2] dark:text-sky-400 dark:border-sky-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
            }`}
          >
            <FileSpreadsheet className="w-4 h-4" />
            Tải file Excel (.xlsx) / CSV
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-5 flex-1">
          {activeTab === 'MYBK_TEXT' ? (
            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Mở trang kết quả học tập trên <code>mybk.hcmut.edu.vn</code>, bôi đen bảng điểm nhiều học kỳ (Ctrl+C) rồi dán vào bên dưới:
                </span>
                <button
                  type="button"
                  data-testid="paste-demo-mybk-btn"
                  onClick={handleLoadDemoSample}
                  disabled={loading}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#034EA2] dark:text-sky-300 border border-blue-200 dark:border-blue-800 text-xs font-bold hover:bg-blue-100 cursor-pointer shrink-0"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Dán mẫu thử MyBK (GPA ~3.20)
                </button>
              </div>

              <textarea
                rows={6}
                data-testid="mybk-paste-textarea"
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder={`Ví dụ dòng copy từ MyBK:\nHọc kỳ 1 - Năm học 2024 - 2025\n1\tMT1003\tGiải tích 1\t4\tBT:8.5 GK:7.5\t8,5\t8,5\tA\n2\tSP1031\tTriết học Mác - Lênin\t3\t6,0\t5,5\t5,7\tC`}
                className="w-full p-3.5 text-xs sm:text-sm font-mono rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#034EA2]"
              />

              <div className="flex justify-end">
                <button
                  type="button"
                  data-testid="parse-mybk-btn"
                  onClick={handleParseText}
                  disabled={loading}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#034EA2] hover:bg-[#023e82] text-white text-xs sm:text-sm font-bold cursor-pointer"
                >
                  <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                  Phân tích &amp; Xem trước bảng điểm
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <span className="text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300">
                  Hỗ trợ định dạng <code>.xlsx</code> và <code>.csv</code> (UTF-8 / Tiếng Việt), tự động nhận diện cột Mã MH, Tên môn, Tín chỉ, Điểm:
                </span>
                <a
                  href={TEMPLATE_CSV_URL}
                  download="mau_bang_diem_hcmut.csv"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-bold hover:bg-emerald-100 shrink-0"
                >
                  <Download className="w-3.5 h-3.5" />
                  Tải file mẫu CSV chuẩn
                </a>
              </div>

              <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-2xl p-8 bg-slate-50/70 dark:bg-slate-800/40 hover:border-[#034EA2] transition-colors cursor-pointer">
                <FileSpreadsheet className="w-10 h-10 text-[#034EA2] dark:text-sky-400 mb-2" />
                <span className="text-sm font-bold text-slate-800 dark:text-slate-100">
                  Nhấn để chọn file Excel (.xlsx) hoặc CSV (.csv)
                </span>
                <span className="text-xs text-slate-500 mt-1">
                  Xử lý hoàn toàn trong bộ nhớ RAM trình duyệt &amp; phản hồi tức thì
                </span>
                <input
                  type="file"
                  data-testid="transcript-file-input"
                  accept=".xlsx,.csv,.tsv,.txt"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </label>
            </div>
          )}

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-xs sm:text-sm text-rose-700 dark:text-rose-300 font-medium">
              {error}
            </div>
          )}

          {/* Interactive Preview Table */}
          {preview && (
            <div className="space-y-4 pt-2 border-t border-slate-200 dark:border-slate-800" data-testid="import-preview-section">
              {/* Preview KPI strip */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800">
                  <div className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">
                    GPA Hệ 4.0 Dự kiến
                  </div>
                  <div className="text-xl font-extrabold text-[#034EA2] dark:text-sky-400 mt-0.5" data-testid="preview-gpa-4">
                    {preview.preview_gpa.gpa_4.toFixed(2)}
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700">
                  <div className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase">
                    Số môn hợp lệ
                  </div>
                  <div className="text-xl font-extrabold text-slate-900 dark:text-white mt-0.5">
                    {editedCourses.length} môn ({preview.preview_gpa.earned_credits} TC)
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800">
                  <div className="text-[11px] font-bold text-amber-700 dark:text-amber-400 uppercase">
                    Gộp môn học lại
                  </div>
                  <div className="text-xl font-extrabold text-amber-800 dark:text-amber-300 mt-0.5" data-testid="preview-retake-count">
                    {preview.retake_detected_count} môn
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800">
                  <div className="text-[11px] font-bold text-emerald-700 dark:text-emerald-400 uppercase">
                    Xếp loại tạm tính
                  </div>
                  <div className="text-lg font-extrabold text-emerald-800 dark:text-emerald-300 mt-0.5">
                    {preview.preview_gpa.honors_standing}
                  </div>
                </div>
              </div>

              {preview.warnings.length > 0 && (
                <div className="space-y-1.5">
                  {preview.warnings.map((w, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 px-3 py-2 rounded-lg"
                    >
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800 max-h-64">
                <table className="w-full text-left border-collapse text-xs sm:text-sm" data-testid="import-preview-table">
                  <thead>
                    <tr className="bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-bold sticky top-0">
                      <th className="py-2.5 px-3">HK</th>
                      <th className="py-2.5 px-3">Mã MH</th>
                      <th className="py-2.5 px-3">Tên học phần</th>
                      <th className="py-2.5 px-2 text-center">TC</th>
                      <th className="py-2.5 px-3 text-center">Điểm 10</th>
                      <th className="py-2.5 px-3 text-center">Điểm chữ</th>
                      <th className="py-2.5 px-3">Trạng thái &amp; Đối chiếu CTĐT</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {editedCourses.map((c, idx) => (
                      <tr key={`${c.course_code}-${idx}`} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="py-2 px-3 text-xs text-slate-500">{c.semester || '—'}</td>
                        <td className="py-2 px-3 font-bold text-[#034EA2] dark:text-sky-400">
                          {c.course_code}
                        </td>
                        <td className="py-2 px-3 font-medium text-slate-900 dark:text-white">
                          {c.course_name}
                        </td>
                        <td className="py-2 px-2 text-center font-semibold">{c.credits}</td>
                        <td className="py-2 px-3 text-center font-semibold">
                          {c.score_10 !== null && c.score_10 !== undefined ? c.score_10.toFixed(1) : '—'}
                        </td>
                        <td className="py-2 px-3 text-center font-extrabold">
                          {c.letter_grade || '—'}
                        </td>
                        <td className="py-2 px-3">
                          <div className="flex flex-wrap items-center gap-1.5">
                            {c.retake_count > 0 && (
                              <span
                                data-testid="retake-badge"
                                className="px-2 py-0.5 text-[11px] font-bold rounded-full bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                              >
                                Đã học cải thiện ({c.retake_history.map((h) => h.letter_grade).join(' → ')})
                              </span>
                            )}
                            {!c.counts_for_gpa && (
                              <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200">
                                Miễn / Không tính GPA
                              </span>
                            )}
                            {c.match_tier === 'EXACT_CODE' && (
                              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                                <CheckCircle2 className="w-3 h-3" />
                                Khớp mã chuẩn
                              </span>
                            )}
                            {c.match_tier === 'FUZZY_NAME' && (
                              <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300">
                                Khớp tên ({c.match_confidence}%)
                              </span>
                            )}
                            {c.match_tier === 'ELECTIVE_UNMATCHED' && (
                              <select
                                aria-label={`Ánh xạ môn ${c.course_code}`}
                                defaultValue=""
                                onChange={(e) => handleRemapCourse(idx, e.target.value)}
                                className="text-[11px] px-2 py-1 rounded border border-amber-300 bg-amber-50 dark:bg-slate-800 text-amber-900 dark:text-amber-200"
                              >
                                <option value="">Tự chọn tự do (Hoặc chọn môn CTĐT...)</option>
                                {curriculumCourses.map((cc) => (
                                  <option key={cc.course_code} value={cc.course_code}>
                                    {cc.course_code} - {cc.course_name}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 bg-slate-50 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs sm:text-sm font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-100 cursor-pointer"
          >
            Hủy bỏ
          </button>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              disabled={!preview || editedCourses.length === 0}
              onClick={() => {
                onApply(editedCourses, 'MERGE');
                onClose();
              }}
              className="px-4 py-2 rounded-xl border border-[#034EA2] text-[#034EA2] dark:text-sky-300 dark:border-sky-400 text-xs sm:text-sm font-bold disabled:opacity-40 hover:bg-blue-50 dark:hover:bg-slate-800 cursor-pointer"
            >
              Gộp thêm vào bảng điểm
            </button>
            <button
              type="button"
              data-testid="apply-imported-grades-btn"
              disabled={!preview || editedCourses.length === 0}
              onClick={() => {
                onApply(editedCourses, 'OVERWRITE');
                onClose();
              }}
              className="px-5 py-2.5 rounded-xl bg-[#034EA2] hover:bg-[#023e82] text-white text-xs sm:text-sm font-bold shadow-md disabled:opacity-40 cursor-pointer"
            >
              Áp dụng bảng điểm ({editedCourses.length} môn)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
