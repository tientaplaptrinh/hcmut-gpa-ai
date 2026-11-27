"""FastAPI REST Server for BK-GPA & Optimal Study Roadmap AI (HCMUT Edition)."""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend.contracts import (
    CurriculumSchema,
    DifficultyDashboardResponse,
    DifficultyRequest,
    GpaCalculationRequest,
    GpaSummaryResponse,
    MajorInfo,
    RoadmapOptimizationRequest,
    RoadmapOptimizationResponse,
    TranscriptParseResponse,
    TranscriptParseTextRequest,
)
from backend.difficulty_model import build_difficulty_dashboard
from backend.hcmut_gpa import calculate_gpa_summary
from backend.roadmap_optimizer import optimize_study_roadmap
from backend.transcript_parser import (
    generate_csv_template,
    parse_mybk_text,
    parse_transcript_file,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
CURRICULA_DIRS = [
    ROOT_DIR / "data" / "curricula",
    ROOT_DIR / "data_pipeline" / "curricula",
]

app = FastAPI(
    title="BK-GPA & Optimal Study Roadmap AI (HCMUT Edition)",
    description="Full-stack Course Difficulty Predictor, MyBK Batch Parser, Exact HCMUT GPA Engine & MILP Study Roadmap Optimizer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _find_curricula_dir() -> Path:
    for d in CURRICULA_DIRS:
        if d.exists() and any(d.glob("*.json")):
            return d
    return CURRICULA_DIRS[0]


@lru_cache(maxsize=128)
def load_curriculum(major_code: str, cohort: str = "K2025") -> CurriculumSchema:
    norm_major = major_code.strip()
    norm_cohort = cohort.strip().upper()
    if not norm_cohort.startswith("K") and norm_cohort.isdigit():
        norm_cohort = f"K{norm_cohort}"

    for base_dir in CURRICULA_DIRS:
        if not base_dir.exists():
            continue
        candidates = [
            base_dir / f"{norm_major}_{norm_cohort}.json",
            base_dir / f"{norm_major}.json",
        ]
        # Case-insensitive fallback (e.g. 75202a1 vs 75202A1)
        for cand in candidates:
            if cand.exists():
                raw = json.loads(cand.read_text(encoding="utf-8"))
                return CurriculumSchema.model_validate(raw)
        for p in base_dir.glob("*.json"):
            if p.name.lower() == f"{norm_major.lower()}_{norm_cohort.lower()}.json":
                raw = json.loads(p.read_text(encoding="utf-8"))
                return CurriculumSchema.model_validate(raw)
        for p in base_dir.glob("*.json"):
            if p.name.lower() == f"{norm_major.lower()}.json":
                raw = json.loads(p.read_text(encoding="utf-8"))
                return CurriculumSchema.model_validate(raw)

    raise HTTPException(
        status_code=404,
        detail=f"Không tìm thấy chương trình đào tạo cho ngành '{major_code}' ({cohort}). Hãy chạy data_pipeline/crawl_hcmut.py.",
    )


def list_all_majors() -> list[MajorInfo]:
    cdir = _find_curricula_dir()
    idx_file = cdir / "index.json"
    if idx_file.exists():
        idx_data = json.loads(idx_file.read_text(encoding="utf-8"))
        return [MajorInfo.model_validate(m) for m in idx_data.get("majors", [])]

    majors: dict[str, MajorInfo] = {}
    for p in sorted(cdir.glob("*.json")):
        if p.name == "index.json" or "_" in p.stem:
            continue
        curr = CurriculumSchema.model_validate(json.loads(p.read_text(encoding="utf-8")))
        cohorts = sorted(
            [f.stem.split("_", 1)[1] for f in cdir.glob(f"{curr.major_code}_K*.json")]
        ) or [curr.cohort]
        majors[curr.major_code] = MajorInfo(
            major_code=curr.major_code,
            major_name=curr.major_name,
            major_name_en=curr.major_name_en,
            faculty=curr.faculty,
            program_type=curr.program_type,
            available_cohorts=cohorts,
            default_cohort="K2025" if "K2025" in cohorts else cohorts[-1],
            total_credits=curr.total_credits,
            course_count=len(curr.courses),
        )
    return list(majors.values())


def build_sample_mybk_transcript_text(curriculum: CurriculumSchema) -> str:
    """Construct a realistic MyBK multi-semester transcript yielding ~3.20 GPA for any HCMUT major.

    Includes:
    - PII header lines (automatically stripped by parser)
    - Multi-semester banners (HK241, HK242, HK251) + summary footers
    - Comma decimals (e.g. 8,6 / 5,6), component columns (BT/GK/CK)
    - 1 retaken course (failed 3,5 F in HK241 -> retaken 8,6 A in HK242)
    - 1 MT exempt English course + 1 PE non-GPA course (if present)
    - 3 low-scoring (D+ / C) low-difficulty courses + strong B/B+/A foundational courses -> GPA ~3.20
    """
    diff_dash = build_difficulty_dashboard(curriculum)
    diff_map = {p.course_code: p.ai_difficulty_score for p in diff_dash.courses}

    compulsory_gpa = [
        c for c in curriculum.courses if c.counts_for_gpa and not c.is_elective and c.credits > 0
    ]
    compulsory_gpa.sort(key=lambda c: (c.recommended_semester, diff_map.get(c.course_code, 5.0), c.course_code))

    # Target ~62–65 GPA credits (~48% of curriculum, end of Year 2) so both Forward-Only and Hybrid are feasible for 3.60 with strong Hybrid ROI!
    target_done_credits = min(65, max(50, int(curriculum.total_gpa_credits * 0.485)))
    chosen: list[Any] = []
    acc_cred = 0
    # Prefer semester 1-4 courses first
    for c in compulsory_gpa:
        if acc_cred + c.credits > target_done_credits + 2:
            continue
        chosen.append(c)
        acc_cred += c.credits
        if acc_cred >= target_done_credits:
            break

    # Identify 3 easiest courses with >= 2 credits in `chosen` to assign D / D+ / C (high-ROI retake candidates!)
    chosen_by_ease = sorted(
        [c for c in chosen if c.credits >= 2],
        key=lambda c: (diff_map.get(c.course_code, 5.0), -c.credits),
    )
    low_grade_codes = [c.course_code for c in chosen_by_ease[:3]]

    # Assign initial scores to hit ~3.20 weighted GPA
    # Low courses get: D (4.5 -> 1.0), D+ (5.2 -> 1.5), C (5.7 -> 2.0)
    low_assignments: dict[str, tuple[str, str]] = {}
    if len(low_grade_codes) >= 1:
        low_assignments[low_grade_codes[0]] = ("4,5", "D")
    if len(low_grade_codes) >= 2:
        low_assignments[low_grade_codes[1]] = ("5,2", "D+")
    if len(low_grade_codes) >= 3:
        low_assignments[low_grade_codes[2]] = ("5,7", "C")

    other_courses = [c for c in chosen if c.course_code not in low_assignments]
    low_gpa_map = {"D": 1.0, "D+": 1.5, "C": 2.0}
    low_pts = sum(
        c.credits * low_gpa_map[low_assignments[c.course_code][1]]
        for c in chosen
        if c.course_code in low_assignments
    )
    target_total_pts = 3.20 * acc_cred
    other_Assignments: dict[str, tuple[str, str]] = {}

    # Start all others at B+ (3.5) and adjust up to A (4.0) or down to B (3.0) to match target_total_pts closely
    current_grades = {c.course_code: 3.5 for c in other_courses}

    def current_pts() -> float:
        return low_pts + sum(c.credits * current_grades[c.course_code] for c in other_courses)

    for c in other_courses:
        if current_pts() + c.credits * 0.5 <= target_total_pts + 0.8:
            current_grades[c.course_code] = 4.0
    for c in reversed(other_courses):
        if current_pts() - c.credits * 0.5 >= target_total_pts - 0.8 and current_grades[c.course_code] == 3.5:
            current_grades[c.course_code] = 3.0

    for c in other_courses:
        g = current_grades[c.course_code]
        if g >= 4.0:
            other_Assignments[c.course_code] = ("8,7", "A")
        elif g >= 3.5:
            other_Assignments[c.course_code] = ("8,2", "B+")
        else:
            other_Assignments[c.course_code] = ("7,4", "B")

    all_assignments = {**low_assignments, **other_Assignments}

    # Pick one A-graded course to show a realistic retake history (HK241 failed 3,5 F -> HK242 retaken 8,7 A)
    retake_demo_course = next(
        (c for c in other_courses if other_Assignments[c.course_code][1] == "A"),
        other_courses[0] if other_courses else None,
    )

    # Split into 3 semesters
    hk1 = chosen[: max(1, len(chosen) // 3)]
    hk2 = chosen[max(1, len(chosen) // 3) : max(2, (2 * len(chosen)) // 3)]
    hk3 = chosen[max(2, (2 * len(chosen)) // 3) :]

    lines: list[str] = [
        "TRƯỜNG ĐẠI HỌC BÁCH KHOA - ĐHQG TP.HCM (MYBK TRANSCRIPT)",
        "MSSV: 2311548\tHọ và tên: Nguyễn Minh Khoa\tEmail: khoa.nguyen@hcmut.edu.vn",
        "",
        "Học kỳ 1 - Năm học 2024 - 2025 (HK241)",
        "STT\tMã MH\tTên môn học\tTín chỉ\tĐiểm thành phần\tĐiểm thi\tĐiểm TK\tĐiểm chữ",
    ]

    idx = 1
    for c in hk1:
        if retake_demo_course and c.course_code == retake_demo_course.course_code:
            lines.append(
                f"{idx}\t{c.course_code}\t{c.course_name}\t{c.credits}\tBT:6.0 GK:4.0\t2,5\t3,5\tF"
            )
        else:
            s10, lg = all_assignments[c.course_code]
            lines.append(
                f"{idx}\t{c.course_code}\t{c.course_name}\t{c.credits}\tBT:8.5 GK:7.5\t{s10}\t{s10}\t{lg}"
            )
        idx += 1

    # Add an MT non-GPA English or PE course in HK241
    non_gpa_list = [c for c in curriculum.courses if not c.counts_for_gpa]
    if non_gpa_list:
        ng = non_gpa_list[0]
        lines.append(f"{idx}\t{ng.course_code}\t{ng.course_name}\t{max(1, ng.credits)}\t-\t-\tMT\tMT")
    else:
        lines.append(f"{idx}\tPE1003\tGiáo dục thể chất 1\t1\t8,0\t8,0\t8,0\tB+")

    lines.extend(
        [
            "Tổng số tín chỉ tích lũy học kỳ: 17\tĐiểm trung bình học kỳ: 3.12",
            "",
            "Học kỳ 2 - Năm học 2024 - 2025 (HK242)",
            "STT\tMã MH\tTên môn học\tTín chỉ\tĐiểm thành phần\tĐiểm thi\tĐiểm TK\tĐiểm chữ",
        ]
    )

    idx = 1
    if retake_demo_course:
        s10, lg = all_assignments[retake_demo_course.course_code]
        lines.append(
            f"{idx}\t{retake_demo_course.course_code}\t{retake_demo_course.course_name}\t{retake_demo_course.credits}\tBT:9.0 GK:8.5\t8,8\t{s10}\t{lg}"
        )
        idx += 1

    for c in hk2:
        if retake_demo_course and c.course_code == retake_demo_course.course_code:
            continue
        s10, lg = all_assignments[c.course_code]
        lines.append(
            f"{idx}\t{c.course_code}\t{c.course_name}\t{c.credits}\tBT:8.0 GK:7.5\t{s10}\t{s10}\t{lg}"
        )
        idx += 1

    lines.extend(
        [
            "Điểm trung bình tích lũy: 3.19",
            "",
            "Học kỳ 1 - Năm học 2025 - 2026 (HK251)",
            "STT\tMã MH\tTên môn học\tTín chỉ\tĐiểm thành phần\tĐiểm thi\tĐiểm TK\tĐiểm chữ",
        ]
    )

    idx = 1
    for c in hk3:
        if retake_demo_course and c.course_code == retake_demo_course.course_code:
            continue
        s10, lg = all_assignments[c.course_code]
        lines.append(
            f"{idx}\t{c.course_code}\t{c.course_name}\t{c.credits}\tBT:8.0 GK:8.0\t{s10}\t{s10}\t{lg}"
        )
        idx += 1

    # Add 1 in-progress CH course from remaining to show CH handling cleanly
    rem_sample = next(
        (c for c in compulsory_gpa if c.course_code not in all_assignments),
        None,
    )
    if rem_sample:
        lines.append(
            f"{idx}\t{rem_sample.course_code}\t{rem_sample.course_name}\t{rem_sample.credits}\t-\t-\tCH\tCH"
        )

    lines.append("Tổng số tín chỉ tích lũy: 56\tĐiểm trung bình tích lũy: 3.20")
    return "\n".join(lines)


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    majors = list_all_majors()
    return {
        "status": "ok",
        "service": "hcmut-gpa-ai",
        "majors_loaded": len(majors),
    }


@app.get("/api/majors", response_model=list[MajorInfo])
def get_majors() -> list[MajorInfo]:
    return list_all_majors()


@app.get("/api/curricula/{major_code}", response_model=CurriculumSchema)
def get_curriculum_endpoint(
    major_code: str,
    cohort: str = Query(default="K2025"),
) -> CurriculumSchema:
    return load_curriculum(major_code, cohort)


@app.get("/api/difficulty/{major_code}", response_model=DifficultyDashboardResponse)
def get_difficulty_endpoint(
    major_code: str,
    cohort: str = Query(default="K2025"),
) -> DifficultyDashboardResponse:
    curr = load_curriculum(major_code, cohort)
    return build_difficulty_dashboard(curr)


@app.post("/api/difficulty/predict", response_model=DifficultyDashboardResponse)
def post_difficulty_predict(req: DifficultyRequest) -> DifficultyDashboardResponse:
    curr = load_curriculum(req.major_code, req.cohort)
    return build_difficulty_dashboard(curr, req.user_difficulty_overrides)


@app.post("/api/gpa/calculate", response_model=GpaSummaryResponse)
def post_gpa_calculate(req: GpaCalculationRequest) -> GpaSummaryResponse:
    curr: Optional[CurriculumSchema] = None
    if req.major_code:
        try:
            curr = load_curriculum(req.major_code, req.cohort or "K2025")
        except HTTPException:
            curr = None
    return calculate_gpa_summary(
        courses=req.courses,
        curriculum=curr,
        required_elective_credits=req.required_elective_credits,
        total_curriculum_gpa_credits=req.total_curriculum_gpa_credits,
    )


@app.post("/api/transcript/parse-text", response_model=TranscriptParseResponse)
def post_parse_transcript_text(req: TranscriptParseTextRequest) -> TranscriptParseResponse:
    curr: Optional[CurriculumSchema] = None
    if req.major_code:
        try:
            curr = load_curriculum(req.major_code, req.cohort or "K2025")
        except HTTPException:
            curr = None
    return parse_mybk_text(req.raw_text, curriculum=curr)


@app.post("/api/transcript/parse-file", response_model=TranscriptParseResponse)
async def post_parse_transcript_file(
    file: UploadFile = File(...),
    major_code: Optional[str] = Form(default=None),
    cohort: Optional[str] = Form(default="K2025"),
) -> TranscriptParseResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File tải lên trống.")
    curr: Optional[CurriculumSchema] = None
    if major_code:
        try:
            curr = load_curriculum(major_code, cohort or "K2025")
        except HTTPException:
            curr = None
    return parse_transcript_file(file.filename or "transcript.csv", content, curriculum=curr)


@app.get("/api/transcript/template-csv")
def get_transcript_template_csv() -> PlainTextResponse:
    csv_text = generate_csv_template()
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mau_bang_diem_hcmut.csv"'},
    )


@app.get("/api/transcript/sample-mybk")
def get_sample_mybk_transcript(
    major_code: str = Query(default="7520201"),
    cohort: str = Query(default="K2025"),
) -> dict[str, Any]:
    curr = load_curriculum(major_code, cohort)
    raw_text = build_sample_mybk_transcript_text(curr)
    parsed = parse_mybk_text(raw_text, curriculum=curr)
    return {
        "major_code": curr.major_code,
        "cohort": curr.cohort,
        "raw_text": raw_text,
        "parsed": parsed.model_dump(),
    }


@app.post("/api/roadmap/optimize", response_model=RoadmapOptimizationResponse)
def post_optimize_roadmap(req: RoadmapOptimizationRequest) -> RoadmapOptimizationResponse:
    curr = load_curriculum(req.major_code, req.cohort)
    return optimize_study_roadmap(curr, req)


# Serve built React SPA in single-container deployments (Docker / Render / HF Spaces)
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
