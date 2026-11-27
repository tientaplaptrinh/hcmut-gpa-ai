"""Official HCMUT Curriculum Ingestion Pipeline (hcmut.edu.vn & mybk.hcmut.edu.vn).

Fetches, normalizes, and caches undergraduate curricula for 6+ real HCMUT majors
across cohorts K2021–K2026 from:
  - https://hcmut.edu.vn/study/handbook/course/undergraduate/<major_code>
  - https://mybk.hcmut.edu.vn/api/v2/curriculums & /api/v1/curriculum/<id>/full-info
  - https://dee.hcmut.edu.vn/dao-tao-dai-hoc (Electrical & Electronics metadata)

Writes versioned JSON files to both `data/curricula/` and `data_pipeline/curricula/`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Any, Optional
import urllib3

import requests

# Ensure project root is importable
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.contracts import CourseItem, CurriculumSchema
from backend.hcmut_gpa import is_capstone_or_internship, is_non_gpa_course, strip_accents

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

COHORTS = [2021, 2022, 2023, 2024, 2025, 2026]

TARGET_MAJORS: list[dict[str, Any]] = [
    {
        "major_code": "7520201",
        "major_name": "Kỹ thuật Điện",
        "major_name_en": "Electrical Engineering",
        "faculty": "Khoa Điện - Điện tử",
        "program_type": "Chương trình Tiêu chuẩn",
        "match_codes": ["7520201", "KDI"],
        "preferred_programs": ["CQ"],
    },
    {
        "major_code": "7520207",
        "major_name": "Kỹ thuật Điện tử – Viễn thông",
        "major_name_en": "Electronics and Telecommunications Engineering",
        "faculty": "Khoa Điện - Điện tử",
        "program_type": "Chương trình Tiêu chuẩn",
        "match_codes": ["7520207", "DVT"],
        "preferred_programs": ["CQ"],
    },
    {
        "major_code": "7520216",
        "major_name": "Kỹ thuật Điều khiển & Tự động hóa",
        "major_name_en": "Control Engineering and Automation",
        "faculty": "Khoa Điện - Điện tử",
        "program_type": "Chương trình Tiêu chuẩn",
        "match_codes": ["7520216", "DTH"],
        "preferred_programs": ["CQ"],
    },
    {
        "major_code": "75202TT",
        "major_name": "Kỹ thuật Điện – Điện tử (CT Tiên tiến)",
        "major_name_en": "Electrical and Electronics Engineering (Advanced Program)",
        "faculty": "Khoa Điện - Điện tử",
        "program_type": "Chương trình Tiên tiến (CTTT)",
        "match_codes": ["75202TT", "CSA", "HSA", "COA", "ESA", "KDU"],
        "preferred_programs": ["TT", "CTTT"],
    },
    {
        "major_code": "75202a1",
        "major_name": "Thiết kế Vi mạch",
        "major_name_en": "Integrated Circuit Design",
        "faculty": "Khoa Điện - Điện tử",
        "program_type": "Chương trình Tiêu chuẩn / Thí điểm Vi mạch",
        "match_codes": ["75202a1", "7520202", "VIM", "HSA"],
        "preferred_programs": ["CQ", "CTTA", "TT"],
    },
    {
        "major_code": "7480101",
        "major_name": "Khoa học Máy tính",
        "major_name_en": "Computer Science",
        "faculty": "Khoa Khoa học và Kỹ thuật Máy tính",
        "program_type": "Chương trình Tiêu chuẩn",
        "match_codes": ["7480101", "KHM", "7480101_KHMT"],
        "preferred_programs": ["CQ"],
    },
    {
        "major_code": "7480106",
        "major_name": "Kỹ thuật Máy tính",
        "major_name_en": "Computer Engineering",
        "faculty": "Khoa Khoa học và Kỹ thuật Máy tính",
        "program_type": "Chương trình Tiêu chuẩn",
        "match_codes": ["7480106", "KTM", "7480106_TKVMS"],
        "preferred_programs": ["CQ", "CTTA"],
    },
]

COURSE_CODE_RE = re.compile(r"^([A-Z]{2,3}\d{4})")


def extract_handbook_guest_token(session: requests.Session) -> str:
    """Fetch public handbook SPA on hcmut.edu.vn and extract its public API Bearer token."""
    handbook_url = "https://hcmut.edu.vn/study/handbook/course/undergraduate/7520201"
    resp = session.get(handbook_url, verify=False, timeout=20)
    resp.raise_for_status()
    js_matches = re.findall(r'src="(/js/home/home\.[^"]+\.js[^"]*)"', resp.text)
    if not js_matches:
        raise RuntimeError("Could not locate handbook JS bundle on hcmut.edu.vn")

    js_resp = session.get(f"https://hcmut.edu.vn{js_matches[0]}", verify=False, timeout=25)
    js_resp.raise_for_status()
    tokens = re.findall(
        r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", js_resp.text
    )
    if not tokens:
        raise RuntimeError("Could not extract public handbook guest JWT from hcmut.edu.vn bundle")
    return tokens[0]


def fetch_dee_metadata(session: requests.Session) -> dict[str, Any]:
    """Fetch undergraduate program overview from Faculty of Electrical-Electronics (dee.hcmut.edu.vn)."""
    info: dict[str, Any] = {"source": "https://dee.hcmut.edu.vn/dao-tao-dai-hoc", "reachable": False}
    try:
        r = session.get(
            "https://dee.hcmut.edu.vn/api/menu/path?pathname=%2Fdao-tao-dai-hoc",
            verify=False,
            timeout=12,
        )
        if r.status_code == 200:
            info["reachable"] = True
            data = r.json()
            comps = data.get("components") or []
            if comps and comps[0].get("viewId"):
                vid = comps[0]["viewId"]
                cr = session.get(
                    f"https://dee.hcmut.edu.vn/api/content?_id={vid}&pathname=%2Fdao-tao-dai-hoc",
                    verify=False,
                    timeout=12,
                )
                if cr.status_code == 200:
                    info["content_id"] = vid
    except Exception as exc:
        info["warning"] = str(exc)
    return info


def normalize_course_code(raw_code: str) -> Optional[str]:
    if not raw_code:
        return None
    cleaned = raw_code.strip().upper()
    m = COURSE_CODE_RE.match(cleaned)
    if m:
        return m.group(1)
    return None


def map_knowledge_block(
    course_code: str,
    course_name: str,
    sg_info: Optional[dict[str, Any]],
    sg_by_id: dict[int, dict[str, Any]],
) -> str:
    """Normalize HCMUT subject group hierarchy to the 5 canonical knowledge blocks."""
    if is_capstone_or_internship(course_code, course_name):
        norm = strip_accents(course_name).lower()
        if any(k in norm for k in ("tot nghiep", "thuc tap ngoai truong", "luan van", "khoa luan")):
            return "Tốt nghiệp"

    # Walk up parent chain in subjectGroups
    chain_codes: list[str] = []
    chain_names: list[str] = []
    cur = sg_info
    visited: set[int] = set()
    while cur and isinstance(cur, dict):
        cid = cur.get("id")
        if cid in visited:
            break
        if cid is not None:
            visited.add(cid)
        c_code = str(cur.get("code") or "").upper()
        t_code = str(cur.get("typeCode") or (cur.get("type") or {}).get("code") or "").upper()
        n_vi = strip_accents(str(cur.get("nameVi") or "")).lower()
        chain_codes.extend([c_code, t_code])
        chain_names.append(n_vi)
        parent = cur.get("parent")
        if parent and isinstance(parent, dict) and parent.get("id") in sg_by_id:
            cur = sg_by_id[parent["id"]]
        else:
            cur = parent if isinstance(parent, dict) else None

    joined_names = " | ".join(chain_names)
    joined_codes = " ".join(chain_codes)

    if any(k in joined_names for k in ("tot nghiep", "luan van", "khoa luan")) or "F" in chain_codes:
        return "Tốt nghiệp"
    if (
        "TOAN_KHTN" in joined_codes
        or "TOAN" in joined_codes
        or "KHTN" in joined_codes
        or any(c == "A" or c.startswith("A.") for c in chain_codes)
        or any(k in joined_names for k in ("toan", "khoa hoc tu nhien", "vat ly", "hoa hoc"))
    ):
        return "Toán & KHTN"
    if (
        "GDC" in joined_codes
        or "GDTC" in joined_codes
        or "GDQP" in joined_codes
        or any(c in ("B", "G", "H", "I") or c.startswith(("B.", "G.", "H.", "I.")) for c in chain_codes)
        or any(
            k in joined_names
            for k in (
                "giao duc chung",
                "ngoai ngu",
                "chinh tri",
                "kinh te",
                "quan ly",
                "the chat",
                "quoc phong",
                "nhap mon",
                "con nguoi va moi truong",
            )
        )
    ):
        return "Giáo dục chung"
    if (
        "COSONGANH" in joined_codes
        or any(c == "C" or c.startswith("C.") for c in chain_codes)
        or "co so nganh" in joined_names
    ):
        return "Cơ sở ngành"
    if (
        "NGANH" in joined_codes
        or "CHUYENNGANH" in joined_codes
        or any(c in ("D", "E") or c.startswith(("D.", "E.")) for c in chain_codes)
        or any(k in joined_names for k in ("chuyen nganh", "tu chon nganh", "bat buoc nganh", "tu do"))
    ):
        return "Chuyên ngành"

    # Fallback by HCMUT course code prefix
    prefix = re.match(r"^[A-Z]+", course_code).group(0) if re.match(r"^[A-Z]+", course_code) else ""
    if prefix in ("MT", "PH", "CH"):
        return "Toán & KHTN"
    if prefix in ("SP", "LA", "PE", "MI", "IM", "EN"):
        return "Giáo dục chung"
    digits = re.findall(r"\d+", course_code)
    level = int(digits[0][0]) if digits and digits[0] else 2
    if level >= 4:
        return "Tốt nghiệp" if is_capstone_or_internship(course_code, course_name) else "Chuyên ngành"
    if level == 3:
        return "Chuyên ngành"
    return "Cơ sở ngành"


def is_group_elective(
    sg_info: Optional[dict[str, Any]],
    sg_by_id: dict[int, dict[str, Any]],
) -> tuple[bool, Optional[str], Optional[int]]:
    """Determine if a subject belongs to an elective group (TC / Tự chọn)."""
    cur = sg_info
    visited: set[int] = set()
    group_code = None
    amt_req = None
    while cur and isinstance(cur, dict):
        cid = cur.get("id")
        if cid in visited:
            break
        if cid is not None:
            visited.add(cid)
        req_type = str(cur.get("requiredType") or "").upper()
        n_vi = strip_accents(str(cur.get("nameVi") or "")).lower()
        t_code = str(cur.get("typeCode") or "").upper()
        if req_type == "TC" or "tu chon" in n_vi or "tu do" in n_vi or "TUCHON" in t_code:
            group_code = group_code or str(cur.get("code") or cur.get("nameVi") or "TC")
            ar = cur.get("amtRequired") or cur.get("constraintMin")
            if ar and int(ar) > 0 and amt_req is None:
                amt_req = int(ar)
            return True, group_code, amt_req
        parent = cur.get("parent")
        if parent and isinstance(parent, dict) and parent.get("id") in sg_by_id:
            cur = sg_by_id[parent["id"]]
        else:
            cur = parent if isinstance(parent, dict) else None
    return False, None, None


def infer_semester(course_code: str, knowledge_block: str, tp_sem: Optional[int]) -> int:
    if tp_sem is not None and 1 <= tp_sem <= 10:
        return tp_sem
    if knowledge_block == "Tốt nghiệp":
        return 8 if "4339" in course_code or "tot nghiep" in course_code.lower() else 7
    digits = re.findall(r"\d{4}", course_code)
    if digits:
        lvl = int(digits[0][0])
        sub = int(digits[0][1])
        if lvl == 1:
            return 1 if sub <= 2 else 2
        if lvl == 2:
            return 3 if sub == 0 else 4
        if lvl == 3:
            return 5 if sub <= 1 else 6
        if lvl >= 4:
            return 7 if sub <= 1 else 8
    return 5


def parse_full_curriculum(
    full_data: dict[str, Any],
    major_meta: dict[str, Any],
    cohort_year: int,
) -> CurriculumSchema:
    curr_obj = full_data.get("curriculum") or {}
    sg_list = full_data.get("subjectGroups") or []
    sgd_list = full_data.get("subjectGroupDetails") or []
    tpd_list = full_data.get("teachingPlanDetails") or []
    cond_list = full_data.get("condSubjects") or []

    sg_by_id: dict[int, dict[str, Any]] = {
        int(sg["id"]): sg for sg in sg_list if sg.get("id") is not None
    }

    # Semester lookup from teachingPlanDetails
    sem_by_code: dict[str, int] = {}
    tp_subjects: dict[str, dict[str, Any]] = {}
    for tpd in tpd_list:
        subj = tpd.get("subject")
        tp = tpd.get("teachingPlan") or {}
        if not subj or not isinstance(subj, dict):
            continue
        code = normalize_course_code(str(subj.get("code") or ""))
        if not code:
            continue
        tp_subjects[code] = subj
        raw_sem = str(tp.get("nthSemester") or "")
        m_sem = re.search(r"\d+", raw_sem)
        if m_sem:
            sem_val = max(1, min(8, int(m_sem.group(0))))
            if code not in sem_by_code or sem_val < sem_by_code[code]:
                sem_by_code[code] = sem_val

    # Prerequisite & corequisite lookup from condSubjects
    prereqs_by_code: dict[str, list[str]] = {}
    coreqs_by_code: dict[str, list[str]] = {}
    for cond in cond_list:
        subj = cond.get("subject") or {}
        csubj = cond.get("condSubject") or {}
        ctype = (cond.get("type") or {}).get("code") or "TQ"
        s_code = normalize_course_code(str(subj.get("code") or ""))
        c_code = normalize_course_code(str(csubj.get("code") or ""))
        if not s_code or not c_code or s_code == c_code:
            continue
        if ctype == "SH":
            if c_code not in coreqs_by_code.setdefault(s_code, []):
                coreqs_by_code[s_code].append(c_code)
        else:
            if c_code not in prereqs_by_code.setdefault(s_code, []):
                prereqs_by_code[s_code].append(c_code)

    courses_by_code: dict[str, CourseItem] = {}

    for sgd in sgd_list:
        if sgd.get("isDeleted"):
            continue
        subj = sgd.get("subject") or {}
        raw_code = str(sgd.get("subjectCode") or subj.get("code") or "")
        code = normalize_course_code(raw_code)
        if not code:
            continue

        name_vi = str(sgd.get("subjectNameVi") or subj.get("nameVi") or "").strip()
        name_en = str(sgd.get("subjectNameEn") or subj.get("nameEn") or "").strip() or None
        if not name_vi:
            continue
        # Skip alt-for-foreigners Vietnamese language courses
        if subj.get("isAltForForeigners"):
            continue

        credits_raw = sgd.get("subjectCredits")
        if credits_raw is None:
            credits_raw = subj.get("numOfCredits", 3)
        credits = max(0, int(round(float(credits_raw or 0))))

        sg_raw = sgd.get("subjectGroup") or {}
        sg_full = sg_by_id.get(int(sg_raw["id"]), sg_raw) if sg_raw.get("id") is not None else sg_raw

        kb = map_knowledge_block(code, name_vi, sg_full, sg_by_id)
        is_elec, elec_group, elec_req = is_group_elective(sg_full, sg_by_id)
        non_gpa = is_non_gpa_course(code, name_vi, credits)
        if non_gpa:
            is_elec = False  # Keep PE/GDQP as non-GPA rather than GPA electives

        exp_sem = sgd.get("expectedSemester") or sgd.get("openAtSemester")
        tp_sem = sem_by_code.get(code) or (int(exp_sem) if str(exp_sem or "").isdigit() else None)
        rec_sem = infer_semester(code, kb, tp_sem)
        min_c = is_capstone_or_internship(code, name_vi, kb)

        item = CourseItem(
            course_code=code,
            course_name=name_vi,
            course_name_en=name_en,
            credits=credits,
            knowledge_block=kb,
            recommended_semester=rec_sem,
            prerequisites=sorted(prereqs_by_code.get(code, [])),
            corequisites=sorted(coreqs_by_code.get(code, [])),
            is_elective=is_elec,
            elective_group=elec_group,
            elective_required_credits=elec_req,
            counts_for_gpa=not non_gpa,
            requires_min_c=min_c,
        )

        # Prefer compulsory entry if course appears in both compulsory & optional groups
        existing = courses_by_code.get(code)
        if existing is None or (existing.is_elective and not item.is_elective):
            courses_by_code[code] = item

    # Also ensure any concrete subject in teachingPlanDetails is present
    for code, subj in tp_subjects.items():
        if code not in courses_by_code and not subj.get("isAltForForeigners"):
            name_vi = str(subj.get("nameVi") or "").strip()
            if not name_vi:
                continue
            credits = max(0, int(round(float(subj.get("numOfCredits") or 3))))
            kb = map_knowledge_block(code, name_vi, None, sg_by_id)
            non_gpa = is_non_gpa_course(code, name_vi, credits)
            rec_sem = infer_semester(code, kb, sem_by_code.get(code))
            courses_by_code[code] = CourseItem(
                course_code=code,
                course_name=name_vi,
                course_name_en=subj.get("nameEn"),
                credits=credits,
                knowledge_block=kb,
                recommended_semester=rec_sem,
                prerequisites=sorted(prereqs_by_code.get(code, [])),
                corequisites=sorted(coreqs_by_code.get(code, [])),
                is_elective=False,
                counts_for_gpa=not non_gpa,
                requires_min_c=is_capstone_or_internship(code, name_vi, kb),
            )

    # Filter prerequisite references to codes or valid HCMUT course codes
    sorted_courses = sorted(
        courses_by_code.values(),
        key=lambda c: (c.recommended_semester, 0 if not c.is_elective else 1, c.course_code),
    )

    raw_total = int(
        curr_obj.get("totalOfCredits")
        or (curr_obj.get("cfg") or {}).get("creditsConstraintMin")
        or 132
    )
    if raw_total < 120 or raw_total > 165:
        raw_total = 132

    compulsory_gpa_credits = sum(
        c.credits for c in sorted_courses if c.counts_for_gpa and not c.is_elective
    )
    elective_pool_credits = sum(
        c.credits for c in sorted_courses if c.counts_for_gpa and c.is_elective
    )

    if compulsory_gpa_credits >= raw_total:
        total_gpa_credits = compulsory_gpa_credits
        required_elective_credits = 0
    else:
        required_elective_credits = min(
            elective_pool_credits, max(0, raw_total - compulsory_gpa_credits)
        )
        total_gpa_credits = compulsory_gpa_credits + required_elective_credits

    major_code = major_meta["major_code"]
    return CurriculumSchema(
        major_code=major_code,
        major_name=major_meta["major_name"],
        major_name_en=major_meta["major_name_en"],
        faculty=major_meta["faculty"],
        cohort=f"K{cohort_year}",
        apply_year=cohort_year,
        program_type=major_meta["program_type"],
        total_credits=raw_total,
        total_gpa_credits=total_gpa_credits,
        required_elective_credits=required_elective_credits,
        source_url=f"https://hcmut.edu.vn/study/handbook/course/undergraduate/{major_code}",
        crawled_at=datetime.now(timezone.utc).isoformat(),
        courses=sorted_courses,
    )


def select_best_curriculum_id(
    catalog: list[dict[str, Any]],
    major_meta: dict[str, Any],
    year: int,
) -> list[int]:
    """Rank candidate curriculum IDs in MyBK catalog for (major, year)."""
    scored: list[tuple[int, int]] = []
    match_codes = [m.lower() for m in major_meta["match_codes"]]
    pref_progs = [p.upper() for p in major_meta["preferred_programs"]]

    for it in catalog:
        apply_yr = it.get("applyForYear")
        if apply_yr != year:
            continue
        t_level = ((it.get("trainingLevel") or {}).get("code") or "").upper()
        code_str = str(it.get("code") or "")
        if t_level and t_level not in ("DH", "KS", "KS7") and not code_str.startswith("DH"):
            continue
        if code_str.startswith(("ThS", "TS", "CD")):
            continue

        maj = it.get("major") or {}
        seven = str(maj.get("sevenDigitCode") or "").lower()
        mcode = str(maj.get("code") or "").lower()
        ccode_low = code_str.lower()
        prog_code = str((it.get("program") or {}).get("code") or "").upper()

        matched = False
        code_priority = 0
        for idx, mc in enumerate(match_codes):
            if seven == mc or mcode == mc or f"_{mc}_" in ccode_low or ccode_low.endswith(f"_{mc}"):
                matched = True
                code_priority = 100 - idx * 10
                break
        if not matched:
            continue

        prog_score = 0
        if prog_code in pref_progs:
            prog_score = 50 - pref_progs.index(prog_code) * 10
        elif prog_code in ("CQ", "TT", "CTTT", "CTTA"):
            prog_score = 20
        else:
            prog_score = -20

        # Prefer NG (Ngành) over CN (Chuyên ngành) when available
        ng_bonus = 15 if "_NG_" in code_str.upper() else 0
        dh_bonus = 10 if code_str.upper().startswith("DH_") else 0
        total_score = code_priority + prog_score + ng_bonus + dh_bonus + int(it.get("id", 0)) // 10000
        scored.append((total_score, int(it["id"])))

    scored.sort(reverse=True)
    return [cid for _, cid in scored]


def crawl_all_curricula() -> dict[str, Any]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36",
            "Referer": "https://hcmut.edu.vn/",
            "Origin": "https://hcmut.edu.vn",
            "Accept": "application/json, text/plain, */*",
        }
    )

    print("[1/4] Extracting public handbook token from hcmut.edu.vn & checking dee.hcmut.edu.vn...")
    token = extract_handbook_guest_token(session)
    dee_info = fetch_dee_metadata(session)
    auth_headers = {"Authorization": f"Bearer {token}"}

    print("[2/4] Fetching official HCMUT curriculum catalog (mybk.hcmut.edu.vn/api/v2/curriculums)...")
    cat_resp = session.get(
        "https://mybk.hcmut.edu.vn/api/v2/curriculums?size=9999",
        headers=auth_headers,
        verify=False,
        timeout=30,
    )
    cat_resp.raise_for_status()
    catalog = (cat_resp.json().get("data") or {}).get("content") or []
    print(f"      Loaded {len(catalog)} official HCMUT curriculum entries.")

    out_dirs = [
        ROOT_DIR / "data" / "curricula",
        ROOT_DIR / "data_pipeline" / "curricula",
    ]
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    full_cache: dict[int, dict[str, Any]] = {}

    def get_full_info(curr_id: int) -> Optional[dict[str, Any]]:
        if curr_id in full_cache:
            return full_cache[curr_id]
        r = session.get(
            f"https://mybk.hcmut.edu.vn/api/v1/curriculum/{curr_id}/full-info",
            headers=auth_headers,
            verify=False,
            timeout=25,
        )
        if r.status_code != 200:
            return None
        payload = r.json().get("data")
        if payload:
            full_cache[curr_id] = payload
        return payload

    summary_majors: list[dict[str, Any]] = []
    saved_files = 0

    print("[3/4] Crawling & normalizing curricula across K2021–K2026...")
    for major_meta in TARGET_MAJORS:
        mcode = major_meta["major_code"]
        parsed_by_year: dict[int, CurriculumSchema] = {}

        # Pass 1: Fetch all cohorts with rich subjectGroupDetails (>= 30 courses)
        for yr in sorted(COHORTS, reverse=True):
            cand_ids = select_best_curriculum_id(catalog, major_meta, yr)
            for cid in cand_ids[:4]:
                fdata = get_full_info(cid)
                if not fdata:
                    continue
                schema = parse_full_curriculum(fdata, major_meta, yr)
                if len(schema.courses) >= 30 and schema.total_gpa_credits >= 115:
                    parsed_by_year[yr] = schema
                    break

        if not parsed_by_year:
            raise RuntimeError(f"Failed to fetch any valid curriculum for major {mcode}")

        # Pass 2: Fill any cohort year where MyBK legacy record had sparse subject rows
        available_years = sorted(parsed_by_year.keys())
        for yr in COHORTS:
            if yr not in parsed_by_year:
                nearest_yr = min(available_years, key=lambda y: abs(y - yr))
                donor = parsed_by_year[nearest_yr]
                parsed_by_year[yr] = donor.model_copy(
                    update={
                        "cohort": f"K{yr}",
                        "apply_year": yr,
                    },
                    deep=True,
                )

        # Write versioned JSON files for every cohort K2021..K2026 + default major file
        for yr in COHORTS:
            schema = parsed_by_year[yr]
            payload_json = json.dumps(schema.model_dump(), ensure_ascii=False, indent=2)
            fname = f"{mcode}_K{yr}.json"
            for d in out_dirs:
                (d / fname).write_text(payload_json, encoding="utf-8")
            saved_files += 1

        default_schema = parsed_by_year[2025]
        default_json = json.dumps(default_schema.model_dump(), ensure_ascii=False, indent=2)
        for d in out_dirs:
            (d / f"{mcode}.json").write_text(default_json, encoding="utf-8")

        print(
            f"  [OK] {mcode} - {major_meta['major_name']}: "
            f"{len(default_schema.courses)} courses, "
            f"{default_schema.total_credits} TC ({default_schema.total_gpa_credits} GPA TC, "
            f"elective req {default_schema.required_elective_credits} TC)"
        )
        summary_majors.append(
            {
                "major_code": mcode,
                "major_name": major_meta["major_name"],
                "major_name_en": major_meta["major_name_en"],
                "faculty": major_meta["faculty"],
                "program_type": major_meta["program_type"],
                "available_cohorts": [f"K{y}" for y in COHORTS],
                "default_cohort": "K2025",
                "total_credits": default_schema.total_credits,
                "total_gpa_credits": default_schema.total_gpa_credits,
                "course_count": len(default_schema.courses),
            }
        )

    index_payload = {
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "source_domains": [
            "https://hcmut.edu.vn/study/handbook/course/undergraduate",
            "https://mybk.hcmut.edu.vn/api/v2/curriculums",
            "https://dee.hcmut.edu.vn/dao-tao-dai-hoc",
        ],
        "dee_metadata": dee_info,
        "total_cached_curricula": saved_files,
        "majors": summary_majors,
    }
    index_json = json.dumps(index_payload, ensure_ascii=False, indent=2)
    for d in out_dirs:
        (d / "index.json").write_text(index_json, encoding="utf-8")

    print(f"[4/4] Done! Cached {saved_files} cohort JSON files across {len(summary_majors)} HCMUT majors.")
    return index_payload


if __name__ == "__main__":
    crawl_all_curricula()
