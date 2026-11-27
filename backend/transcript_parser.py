"""MyBK Copy-Paste & Excel/CSV Batch Transcript Parser, PII Sanitizer & 3-Tier Matcher.

Features:
- Privacy-first in-memory parsing: strips MSSV, student name, DOB, and email; never touches disk.
- MyBK Text Mode: parses tab-separated or multi-space multi-semester transcripts copied from mybk.hcmut.edu.vn
  (component scores BT/TN/BTL/GK/CK, comma decimals 7,5 -> 7.5, semester headers, summary footers ignored).
- Excel (.xlsx) & CSV (UTF-8-SIG / UTF-8 / CP1258) parser with Vietnamese/English header auto-detection.
- Special HCMUT statuses: VT/CT/KD -> 0.0 (F, FAIL_SPECIAL); MT/BL/DT -> EXEMPT_PASS; RT -> WITHDRAWN; CH/- -> IN_PROGRESS.
- 3-Tier Curriculum Matching: (1) Exact Code, (2) Accent-stripped RapidFuzz >= 85, (3) Elective/Unmatched bucket.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Optional

import openpyxl
from rapidfuzz import fuzz, process

from backend.contracts import (
    CourseItem,
    CurriculumSchema,
    StudentCourseRecord,
    TranscriptParseResponse,
)
from backend.hcmut_gpa import (
    EXEMPT_PASS_CODES,
    FAIL_SPECIAL_CODES,
    IN_PROGRESS_CODES,
    LETTER_TO_GPA4,
    WITHDRAWN_CODES,
    calculate_gpa_summary,
    deduplicate_retakes,
    normalize_course_record,
    strip_accents,
)


COURSE_CODE_TOKEN_RE = re.compile(r"\b([A-Z]{2,3}\d{4})\b")
SEMESTER_HEADER_RE = re.compile(
    r"(?:hoc\s*ky|hk)\s*([0-9]{1,3})(?:\s*[-/–]\s*(?:nam\s*hoc\s*)?([0-9]{4}\s*[-–/]\s*[0-9]{4}|[0-9]{4}))?",
    re.IGNORECASE,
)

# PII patterns stripped in memory
PII_PATTERNS = [
    re.compile(r"\b(?:mssv|ma\s*so\s*sv|student\s*id)\s*[:\-]?\s*\d{6,10}\b", re.IGNORECASE),
    re.compile(r"\b(?:ho\s*va\s*ten|ho\s*ten|sinh\s*vien|full\s*name)\s*[:\-]\s*[^\t\r\n|]+", re.IGNORECASE),
    re.compile(r"\b(?:ngay\s*sinh|dob|date\s*of\s*birth)\s*[:\-]?\s*\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}\b", re.IGNORECASE),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\b(?:19|20|21|22|23|24|25|26)\d{5}\b"),  # 7-digit HCMUT MSSV
]

SUMMARY_FOOTER_KEYWORDS = (
    "tong so tin chi",
    "so tin chi dang ky",
    "so tin chi tich luy",
    "diem trung binh hoc ky",
    "diem trung binh tich luy",
    "diem tb hoc ky",
    "diem tb tich luy",
    "dtb hoc ky",
    "dtb tich luy",
    "xep loai hoc luc",
    "ket qua hoc tap",
)

HEADER_KEYWORDS = (
    "ma mh",
    "ma mon",
    "ten mon hoc",
    "ten hoc phan",
    "diem thanh phan",
    "diem tong ket",
    "course code",
)

ALL_SPECIAL_TOKENS = (
    FAIL_SPECIAL_CODES
    | EXEMPT_PASS_CODES
    | WITHDRAWN_CODES
    | {"CH", "-", "--"}
    | set(LETTER_TO_GPA4.keys())
)


def sanitize_pii_in_memory(text: str) -> tuple[str, int]:
    """Strip student personal identifiers in memory before parsing."""
    stripped_count = 0
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        norm = strip_accents(line)
        # Check standalone PII metadata lines
        line_hits = 0
        mod_line = line
        for pat in PII_PATTERNS:
            matches = pat.findall(norm)
            if matches:
                line_hits += len(matches)
                mod_line = pat.sub("[REDACTED]", mod_line)
        stripped_count += line_hits
        # Skip pure PII banner lines that have no course code
        if line_hits > 0 and not COURSE_CODE_TOKEN_RE.search(line.upper()):
            continue
        cleaned_lines.append(mod_line)
    return "\n".join(cleaned_lines), stripped_count


def parse_float_score(token: str) -> Optional[float]:
    t = token.strip().replace(",", ".")
    if not re.match(r"^\d{1,2}(?:\.\d{1,2})?$", t):
        return None
    val = float(t)
    return val if 0.0 <= val <= 10.0 else None


def detect_semester_banner(line: str) -> Optional[str]:
    norm = strip_accents(line).strip()
    if COURSE_CODE_TOKEN_RE.search(line.upper()):
        return None
    m = SEMESTER_HEADER_RE.search(norm)
    if m:
        hk = m.group(1)
        yr = (m.group(2) or "").replace(" ", "")
        if len(hk) == 3 and hk.isdigit():
            return f"HK{hk}"
        if yr:
            return f"HK{hk} ({yr})"
        return f"HK{hk}"
    # Also support compact semester codes like "20241", "HK241", "231", "232", "241", "242"
    m2 = re.match(r"^(?:hoc\s*ky\s*)?(2[0-6][1-3]|202[0-6][1-3])$", norm, re.IGNORECASE)
    if m2:
        return f"HK{m2.group(1)}"
    return None


def is_ignored_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    norm = strip_accents(s).lower()
    if any(kw in norm for kw in SUMMARY_FOOTER_KEYWORDS):
        return True
    if any(kw in norm for kw in HEADER_KEYWORDS) and not COURSE_CODE_TOKEN_RE.search(s.upper()):
        return True
    return False


def apply_three_tier_matching(
    record: StudentCourseRecord,
    curriculum: Optional[CurriculumSchema],
) -> StudentCourseRecord:
    """Match parsed course against selected HCMUT curriculum via 3-tier resolution."""
    rec = record.model_copy(deep=True)
    if curriculum is None or not curriculum.courses:
        rec.match_tier = "MANUAL"
        return rec

    code_map: dict[str, CourseItem] = {c.course_code.upper(): c for c in curriculum.courses}
    code_up = rec.course_code.strip().upper()

    # Tier 1: Exact course code match
    if code_up in code_map:
        c_item = code_map[code_up]
        rec.course_code = c_item.course_code
        rec.course_name = rec.course_name or c_item.course_name
        rec.credits = c_item.credits
        rec.is_elective = c_item.is_elective
        rec.elective_group = c_item.elective_group
        rec.requires_min_c = c_item.requires_min_c
        rec.counts_for_gpa = c_item.counts_for_gpa
        rec.match_tier = "EXACT_CODE"
        rec.matched_curriculum_code = c_item.course_code
        rec.match_confidence = 100.0
        return rec

    # Tier 2: Accent-stripped fuzzy course name match (rapidfuzz >= 85)
    query_name = strip_accents(rec.course_name).lower().strip()
    if len(query_name) >= 4:
        choices: dict[str, str] = {
            c.course_code: strip_accents(c.course_name).lower().strip()
            for c in curriculum.courses
        }
        best = process.extractOne(
            query_name,
            choices,
            scorer=fuzz.token_sort_ratio,
        )
        if best and best[1] >= 85.0:
            matched_code = best[2]
            c_item = code_map[matched_code]
            rec.matched_curriculum_code = c_item.course_code
            rec.course_code = c_item.course_code
            if not rec.course_name:
                rec.course_name = c_item.course_name
            rec.credits = c_item.credits
            rec.is_elective = c_item.is_elective
            rec.elective_group = c_item.elective_group
            rec.requires_min_c = c_item.requires_min_c
            rec.counts_for_gpa = c_item.counts_for_gpa
            rec.match_tier = "FUZZY_NAME"
            rec.match_confidence = round(float(best[1]), 1)
            return rec

    # Tier 3: Elective / Unmatched bucket for user review in preview modal
    rec.match_tier = "ELECTIVE_UNMATCHED"
    rec.matched_curriculum_code = None
    rec.match_confidence = 0.0
    # Unmatched credit-bearing GPA courses count toward free electives unless non-GPA (PE/MI/LA prep)
    rec.is_elective = True
    return rec


def parse_single_mybk_line(line: str, current_semester: Optional[str]) -> Optional[StudentCourseRecord]:
    """Parse a single MyBK transcript row (tab-separated or multi-space separated)."""
    # Strip inline component score annotations like "BT:8.5 TN:9.0 GK:7.5 CK:8.0"
    cleaned = re.sub(
        r"\b(?:BT|TN|BTL|TL|GK|QT|THI|CK)\s*[:=]\s*(?:\d{1,2}(?:[.,]\d{1,2})?|[A-Z]{1,2})\b",
        " ",
        line,
        flags=re.IGNORECASE,
    )

    # Split columns by tab or 2+ spaces or pipe
    cols = [c.strip() for c in re.split(r"\t+|\s*\|\s*|\s{2,}", cleaned.strip()) if c.strip()]
    if not cols:
        return None

    # Find course code column (or generate synthetic code if row only has course name in fuzzy test)
    code_idx = -1
    course_code = ""
    for idx, col in enumerate(cols):
        m = COURSE_CODE_TOKEN_RE.search(col.upper())
        if m:
            code_idx = idx
            course_code = m.group(1)
            break

    if code_idx == -1:
        # Try token-level search on single-space line: e.g. "1 MT1003 Giải tích 1 4 8,5 A"
        m_any = COURSE_CODE_TOKEN_RE.search(cleaned.upper())
        if not m_any:
            return None
        course_code = m_any.group(1)
        before_after = cleaned[m_any.end():].strip()
        tokens = before_after.split()
        if len(tokens) < 2:
            return None
        # Parse from the right: optional letter/status, final score, component scores, credits, name
        return _parse_tokens_after_code(course_code, tokens, current_semester)

    # Check if an earlier column has semester (e.g. "HK241 | MT1003 | ...")
    row_sem = current_semester
    for idx in range(code_idx):
        cand = cols[idx].upper()
        if re.match(r"^(?:HK)?2\d{2,4}$", cand):
            row_sem = cand if cand.startswith("HK") else f"HK{cand}"

    after_cols = cols[code_idx + 1 :]
    # If the course code column also contained the course name (e.g. "MT1003 - Giải tích 1")
    rem_in_code_col = re.sub(r"^.*?\b" + re.escape(course_code) + r"\b[\s\-–:]*", "", cols[code_idx], flags=re.IGNORECASE).strip()
    if rem_in_code_col:
        after_cols = [rem_in_code_col] + after_cols

    if not after_cols:
        return None

    # First non-numeric column after code is course name (skipping group code like "L01" / "CC01" if after name)
    name_parts: list[str] = []
    idx = 0
    while idx < len(after_cols):
        tok = after_cols[idx]
        # Stop when hitting integer credits (0..15)
        if re.match(r"^\d{1,2}$", tok) and int(tok) <= 15 and name_parts:
            break
        # Ignore class group codes like L01, DT01 if name already captured
        if name_parts and re.match(r"^[A-Z]{1,3}\d{2}$", tok.upper()):
            idx += 1
            continue
        if not re.match(r"^\d{1,2}(?:[.,]\d{1,2})?$", tok):
            name_parts.append(tok)
            idx += 1
        else:
            break

    if not name_parts:
        # Fallback to token parser
        return _parse_tokens_after_code(course_code, " ".join(after_cols).split(), row_sem)

    course_name = " ".join(name_parts).strip()
    tail_tokens: list[str] = []
    for col in after_cols[idx:]:
        tail_tokens.extend(col.split())

    return _extract_credits_and_grade(course_code, course_name, tail_tokens, row_sem)


def _parse_tokens_after_code(
    course_code: str,
    tokens: list[str],
    semester: Optional[str],
) -> Optional[StudentCourseRecord]:
    name_tokens: list[str] = []
    idx = 0
    while idx < len(tokens):
        t = tokens[idx]
        if re.match(r"^\d{1,2}$", t) and int(t) <= 15 and name_tokens:
            break
        name_tokens.append(t)
        idx += 1
    if not name_tokens:
        return None
    return _extract_credits_and_grade(
        course_code,
        " ".join(name_tokens),
        tokens[idx:],
        semester,
    )


def _extract_credits_and_grade(
    course_code: str,
    course_name: str,
    tail_tokens: list[str],
    semester: Optional[str],
) -> Optional[StudentCourseRecord]:
    if not tail_tokens:
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=3,
            semester=semester,
            letter_grade="CH",
            status="IN_PROGRESS",
        )

    # Filter out group codes like L01, TN02
    filtered = [t for t in tail_tokens if not re.match(r"^[A-Z]{1,3}\d{2}$", t.upper())]
    if not filtered:
        filtered = tail_tokens

    credits = 3
    rest = filtered
    if re.match(r"^\d{1,2}$", filtered[0]) and int(filtered[0]) <= 15:
        credits = int(filtered[0])
        rest = filtered[1:]

    if not rest:
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            letter_grade="CH",
            status="IN_PROGRESS",
        )

    # Inspect from the right end: MyBK puts [component scores...] [final_score_10] [letter_grade / special_code]
    last_up = rest[-1].strip().upper()
    second_last_score = parse_float_score(rest[-2]) if len(rest) >= 2 else None
    last_score = parse_float_score(rest[-1])

    letter_grade: Optional[str] = None
    score_10: Optional[float] = None

    if last_up in FAIL_SPECIAL_CODES:
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            score_10=0.0,
            letter_grade=last_up,
            gpa_4=0.0,
            status="FAIL_SPECIAL",
        )
    if last_up in EXEMPT_PASS_CODES:
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            letter_grade=last_up,
            status="EXEMPT_PASS",
            counts_for_gpa=False,
        )
    if last_up in WITHDRAWN_CODES:
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            letter_grade="RT",
            status="WITHDRAWN",
            counts_for_gpa=False,
        )
    if last_up in IN_PROGRESS_CODES:
        # Check if an earlier token was a special code or if all are '-' / 'CH'
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            letter_grade="CH",
            status="IN_PROGRESS",
            counts_for_gpa=False,
        )

    if last_up in LETTER_TO_GPA4:
        letter_grade = last_up
        if second_last_score is not None:
            score_10 = second_last_score
    elif last_score is not None:
        # Check if second-last was a 10-point score and last_score is 4.0-scale (e.g. "8.5  4.0")
        # In MyBK copy-paste without letter column, last numeric column is final 10-point score!
        score_10 = last_score
    else:
        # Scan any token from right to left for valid score or special status
        for tok in reversed(rest):
            tup = tok.upper()
            if tup in FAIL_SPECIAL_CODES:
                return StudentCourseRecord(
                    course_code=course_code,
                    course_name=course_name,
                    credits=credits,
                    semester=semester,
                    score_10=0.0,
                    letter_grade=tup,
                    gpa_4=0.0,
                    status="FAIL_SPECIAL",
                )
            if tup in EXEMPT_PASS_CODES:
                return StudentCourseRecord(
                    course_code=course_code,
                    course_name=course_name,
                    credits=credits,
                    semester=semester,
                    letter_grade=tup,
                    status="EXEMPT_PASS",
                    counts_for_gpa=False,
                )
            if tup in WITHDRAWN_CODES:
                return StudentCourseRecord(
                    course_code=course_code,
                    course_name=course_name,
                    credits=credits,
                    semester=semester,
                    letter_grade="RT",
                    status="WITHDRAWN",
                    counts_for_gpa=False,
                )
            sc = parse_float_score(tok)
            if sc is not None:
                score_10 = sc
                break

    if score_10 is None and letter_grade is None:
        return StudentCourseRecord(
            course_code=course_code,
            course_name=course_name,
            credits=credits,
            semester=semester,
            letter_grade="CH",
            status="IN_PROGRESS",
            counts_for_gpa=False,
        )

    return StudentCourseRecord(
        course_code=course_code,
        course_name=course_name,
        credits=credits,
        semester=semester,
        score_10=score_10,
        letter_grade=letter_grade,
        status="NORMAL",
    )


def finalize_parsed_records(
    raw_records: list[StudentCourseRecord],
    curriculum: Optional[CurriculumSchema],
    pii_stripped_count: int,
    warnings: list[str],
) -> TranscriptParseResponse:
    curr_map = {c.course_code.upper(): c for c in curriculum.courses} if curriculum else None

    matched_records = [apply_three_tier_matching(r, curriculum) for r in raw_records]
    normalized_all = [normalize_course_record(r, curriculum_map=curr_map) for r in matched_records]

    deduped_active, inactive_records, retake_count = deduplicate_retakes(
        normalized_all, curriculum_map=curr_map
    )

    unmatched = [c for c in deduped_active if c.match_tier == "ELECTIVE_UNMATCHED"]
    if unmatched and curriculum is not None:
        warnings.append(
            f"Phát hiện {len(unmatched)} môn chưa khớp mã chuẩn trong CTĐT {curriculum.major_code} (đã xếp vào nhóm Tự chọn / Chờ ánh xạ)."
        )
    if retake_count > 0:
        warnings.append(
            f"Đã tự động gộp {retake_count} môn học lại/cải thiện và giữ mức điểm cao nhất theo quy chế ĐHBK."
        )
    if inactive_records:
        warnings.append(
            f"Đã bỏ qua {len(inactive_records)} môn rút môn (RT) hoặc đang chờ điểm (CH) — giữ nguyên trong danh sách môn còn lại."
        )

    preview_gpa = calculate_gpa_summary(deduped_active, curriculum=curriculum)

    return TranscriptParseResponse(
        parsed_courses=deduped_active,
        withdrawn_or_inprogress=inactive_records,
        unmatched_courses=unmatched,
        retake_detected_count=retake_count,
        pii_stripped_count=pii_stripped_count,
        warnings=warnings,
        preview_gpa=preview_gpa,
    )


def parse_mybk_text(
    raw_text: str,
    curriculum: Optional[CurriculumSchema] = None,
) -> TranscriptParseResponse:
    """Parse raw text copied from mybk.hcmut.edu.vn."""
    sanitized_text, pii_count = sanitize_pii_in_memory(raw_text or "")
    warnings: list[str] = []
    if pii_count > 0:
        warnings.append(f"Bảo mật: Đã tự động ẩn {pii_count} thông tin định danh cá nhân (MSSV/Họ tên/Email) trên bộ nhớ RAM.")

    current_semester: Optional[str] = None
    raw_records: list[StudentCourseRecord] = []

    for line in sanitized_text.splitlines():
        sem_banner = detect_semester_banner(line)
        if sem_banner:
            current_semester = sem_banner
            continue
        if is_ignored_line(line):
            continue
        rec = parse_single_mybk_line(line, current_semester)
        if rec is not None:
            raw_records.append(rec)

    if not raw_records:
        warnings.append("Không tìm thấy dòng điểm hợp lệ. Hãy kiểm tra định dạng Mã MH (VD: MT1003) và cột điểm.")

    return finalize_parsed_records(raw_records, curriculum, pii_count, warnings)


HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "course_code": ("ma mh", "ma mon", "ma hoc phan", "course code", "subject code", "code", "mamh"),
    "course_name": ("ten mh", "ten mon", "ten mon hoc", "ten hoc phan", "course name", "subject name", "name"),
    "credits": ("tin chi", "so tc", "so tin chi", "tc", "credits", "credit"),
    "semester": ("hoc ky", "hk", "nam hoc", "semester", "term"),
    "score_10": ("diem tk", "diem tong ket", "diem he 10", "diem so", "diem 10", "final score", "score", "diem"),
    "letter_grade": ("diem chu", "xep loai", "letter grade", "letter", "grade", "trang thai"),
}


def detect_column_mapping(row_cells: list[str]) -> Optional[dict[str, int]]:
    norm_cells = [strip_accents(str(c or "")).lower().strip() for c in row_cells]
    mapping: dict[str, int] = {}
    for field, aliases in HEADER_ALIASES.items():
        for idx, cell in enumerate(norm_cells):
            if not cell or idx in mapping.values():
                continue
            if any(cell == al or cell.startswith(al + " ") or al in cell for al in aliases):
                mapping[field] = idx
                break
    # Valid header must identify at least course_code or course_name, plus score_10 or letter_grade
    if ("course_code" in mapping or "course_name" in mapping) and (
        "score_10" in mapping or "letter_grade" in mapping or "credits" in mapping
    ):
        return mapping
    return None


def decode_csv_bytes(file_bytes: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"):
        try:
            return file_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def parse_tabular_rows(
    rows: list[list[Any]],
    curriculum: Optional[CurriculumSchema] = None,
) -> TranscriptParseResponse:
    warnings: list[str] = []
    pii_count = 0
    header_map: Optional[dict[str, int]] = None
    start_row = 0

    for r_idx, row in enumerate(rows[:20]):
        str_cells = [str(c if c is not None else "").strip() for c in row]
        row_joined = " | ".join(str_cells)
        _, p_hits = sanitize_pii_in_memory(row_joined)
        pii_count += p_hits
        cand_map = detect_column_mapping(str_cells)
        if cand_map is not None:
            header_map = cand_map
            start_row = r_idx + 1
            break

    if header_map is None:
        # Fallback: join rows as tab-separated text and use MyBK text parser
        joined_text = "\n".join(
            "\t".join(str(c if c is not None else "").strip() for c in r) for r in rows
        )
        return parse_mybk_text(joined_text, curriculum=curriculum)

    raw_records: list[StudentCourseRecord] = []
    syn_counter = 1

    for row in rows[start_row:]:
        cells = [str(c if c is not None else "").strip() for c in row]
        if not any(cells):
            continue
        joined_norm = strip_accents(" ".join(cells)).lower()
        if any(kw in joined_norm for kw in SUMMARY_FOOTER_KEYWORDS):
            continue

        def get_col(field: str) -> str:
            idx = header_map.get(field)
            return cells[idx].strip() if idx is not None and idx < len(cells) else ""

        raw_code = get_col("course_code").upper()
        raw_name = get_col("course_name")
        if not raw_code and not raw_name:
            continue

        m_code = COURSE_CODE_TOKEN_RE.search(raw_code)
        if m_code:
            code = m_code.group(1)
        elif raw_code and re.match(r"^[A-Z0-9_]{4,10}$", raw_code):
            code = raw_code
        elif raw_name:
            code = f"UNM{syn_counter:04d}"
            syn_counter += 1
        else:
            continue

        raw_cred = get_col("credits").replace(",", ".")
        credits = int(float(raw_cred)) if re.match(r"^\d+(?:\.\d+)?$", raw_cred) else 3
        sem = get_col("semester") or None
        raw_s10 = get_col("score_10")
        raw_lg = get_col("letter_grade").upper()

        # Sometimes special status (MT, VT, RT, CH) or letter grade is typed directly inside score_10 column
        score_10 = parse_float_score(raw_s10) if raw_s10 else None
        if score_10 is None and raw_s10.upper() in ALL_SPECIAL_TOKENS and not raw_lg:
            raw_lg = raw_s10.upper()

        status = "NORMAL"
        counts_gpa = True
        if raw_lg in FAIL_SPECIAL_CODES:
            status = "FAIL_SPECIAL"
            score_10 = 0.0
        elif raw_lg in EXEMPT_PASS_CODES:
            status = "EXEMPT_PASS"
            counts_gpa = False
        elif raw_lg in WITHDRAWN_CODES:
            status = "WITHDRAWN"
            counts_gpa = False
        elif score_10 is None and (not raw_lg or raw_lg in IN_PROGRESS_CODES):
            status = "IN_PROGRESS"
            raw_lg = "CH"
            counts_gpa = False

        raw_records.append(
            StudentCourseRecord(
                course_code=code,
                course_name=raw_name,
                credits=credits,
                semester=sem,
                score_10=score_10,
                letter_grade=raw_lg or None,
                status=status,
                counts_for_gpa=counts_gpa,
            )
        )

    if pii_count > 0:
        warnings.append(f"Bảo mật: Đã lọc bỏ {pii_count} trường thông tin cá nhân trên RAM; không lưu file gốc xuống ổ đĩa.")

    return finalize_parsed_records(raw_records, curriculum, pii_count, warnings)


def parse_transcript_file(
    filename: str,
    file_bytes: bytes,
    curriculum: Optional[CurriculumSchema] = None,
) -> TranscriptParseResponse:
    """Parse an uploaded .xlsx or .csv file strictly in memory."""
    lower_name = (filename or "").lower()
    if lower_name.endswith(".xlsx"):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
        ws = wb.active
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        wb.close()
        return parse_tabular_rows(rows, curriculum=curriculum)

    # CSV / TSV fallback
    decoded = decode_csv_bytes(file_bytes)
    sample = decoded[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        delim = "," if sample.count(",") >= sample.count(";") else ";"
    reader = csv.reader(io.StringIO(decoded), delimiter=delim)
    rows = [list(r) for r in reader]
    return parse_tabular_rows(rows, curriculum=curriculum)


def generate_csv_template() -> str:
    """Generate a UTF-8-SIG compatible CSV template for HCMUT students."""
    lines = [
        "Học kỳ,Mã MH,Tên môn học,Số tín chỉ,Điểm hệ 10,Điểm chữ",
        "HK241,MT1003,Giải tích 1,4,7.5,B",
        "HK241,MT1007,Đại số tuyến tính,3,8.2,B+",
        "HK241,PH1003,Vật lý 1,4,7.0,B",
        "HK241,SP1031,Triết học Mác - Lênin,3,5.8,C",
        "HK241,LA1003,Anh văn 1,2,,MT",
        "HK241,PE1003,Giáo dục thể chất 1,1,8.0,B+",
        "HK242,MT1005,Giải tích 2,4,7.2,B",
        "HK242,SP1033,Kinh tế chính trị Mác - Lênin,2,5.6,C",
    ]
    return "\ufeff" + "\n".join(lines) + "\n"
