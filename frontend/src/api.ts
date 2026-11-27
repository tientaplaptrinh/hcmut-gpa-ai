import type {
  CurriculumSchema,
  DifficultyDashboardResponse,
  GpaSummaryResponse,
  MajorInfo,
  RoadmapOptimizationRequest,
  RoadmapOptimizationResponse,
  StudentCourseRecord,
  TranscriptParseResponse,
} from './types';

const API_BASE = '/api';

async function checkResp<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(errText || `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export async function fetchMajors(): Promise<MajorInfo[]> {
  const resp = await fetch(`${API_BASE}/majors`);
  return checkResp<MajorInfo[]>(resp);
}

export async function fetchCurriculum(majorCode: string, cohort: string): Promise<CurriculumSchema> {
  const resp = await fetch(
    `${API_BASE}/curricula/${encodeURIComponent(majorCode)}?cohort=${encodeURIComponent(cohort)}`
  );
  return checkResp<CurriculumSchema>(resp);
}

export async function fetchDifficultyDashboard(
  majorCode: string,
  cohort: string,
  overrides: Record<string, number>
): Promise<DifficultyDashboardResponse> {
  const resp = await fetch(`${API_BASE}/difficulty/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      major_code: majorCode,
      cohort,
      user_difficulty_overrides: overrides,
    }),
  });
  return checkResp<DifficultyDashboardResponse>(resp);
}

export async function calculateLiveGpa(
  majorCode: string,
  cohort: string,
  courses: StudentCourseRecord[]
): Promise<GpaSummaryResponse> {
  const resp = await fetch(`${API_BASE}/gpa/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      major_code: majorCode,
      cohort,
      courses,
    }),
  });
  return checkResp<GpaSummaryResponse>(resp);
}

export async function parseMybkText(
  rawText: string,
  majorCode: string,
  cohort: string
): Promise<TranscriptParseResponse> {
  const resp = await fetch(`${API_BASE}/transcript/parse-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_text: rawText,
      major_code: majorCode,
      cohort,
    }),
  });
  return checkResp<TranscriptParseResponse>(resp);
}

export async function parseTranscriptFile(
  file: File,
  majorCode: string,
  cohort: string
): Promise<TranscriptParseResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('major_code', majorCode);
  form.append('cohort', cohort);

  const resp = await fetch(`${API_BASE}/transcript/parse-file`, {
    method: 'POST',
    body: form,
  });
  return checkResp<TranscriptParseResponse>(resp);
}

export async function fetchSampleMybk(
  majorCode: string,
  cohort: string
): Promise<{ raw_text: string; parsed: TranscriptParseResponse }> {
  const resp = await fetch(
    `${API_BASE}/transcript/sample-mybk?major_code=${encodeURIComponent(
      majorCode
    )}&cohort=${encodeURIComponent(cohort)}`
  );
  return checkResp<{ raw_text: string; parsed: TranscriptParseResponse }>(resp);
}

export async function optimizeRoadmap(
  req: RoadmapOptimizationRequest
): Promise<RoadmapOptimizationResponse> {
  const resp = await fetch(`${API_BASE}/roadmap/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  return checkResp<RoadmapOptimizationResponse>(resp);
}

export const TEMPLATE_CSV_URL = `${API_BASE}/transcript/template-csv`;
