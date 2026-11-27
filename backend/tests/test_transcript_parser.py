"""Pytest verification of MyBK Copy-Paste, CSV/Excel Batch Parser, Special Statuses & Fuzzy Matching."""

from __future__ import annotations

import io
import openpyxl

from backend.main import load_curriculum
from backend.transcript_parser import (
    generate_csv_template,
    parse_mybk_text,
    parse_transcript_file,
)


def test_mybk_copy_paste_multi_semester_special_statuses_and_pii():
    curr = load_curriculum("7520201", "K2025")
    sample_text = """
    TRƯỜNG ĐẠI HỌC BÁCH KHOA - ĐHQG TP.HCM
    MSSV: 2213456    Họ và tên: Trần Văn Bách    Ngày sinh: 15/08/2004    Email: bach.tran@hcmut.edu.vn

    Học kỳ 1 - Năm học 2024 - 2025
    STT\tMã MH\tTên môn học\tTín chỉ\tĐiểm thành phần\tĐiểm thi\tĐiểm tổng kết\tĐiểm chữ
    1\tMT1003\tGiải tích 1\t4\tBT:8.0 GK:6.5\t4,0\t5,2\tD+
    2\tMT1007\tĐại số tuyến tính\t3\tBT:9.0 GK:8.5\t8,5\t8,6\tA
    3\tLA1003\tAnh văn 1\t2\t-\t-\tMT\tMT
    4\tPH1003\tVật lý 1\t4\t-\t-\tVT\tVT
    5\tPE1003\tGiáo dục thể chất 1\t1\t8,0\t8,0\t8,0\tB+
    Tổng số tín chỉ tích lũy học kỳ: 9\tĐiểm trung bình học kỳ: 2.15

    Học kỳ 2 - Năm học 2024 - 2025
    1\tMT1003\tGiải tích 1\t4\tBT:9.0 GK:8.0\t8,0\t8,2\tB+
    2\tSP1031\tTriết học Mác - Lênin\t3\t7,0\t6,0\t6,2\tC
    3\tMT1005\tGiải tích 2\t4\t-\t-\tRT\tRT
    4\tEE2033\tGiải tích mạch\t4\t-\t-\tCH\tCH
    Điểm trung bình tích lũy: 2.65
    """

    res = parse_mybk_text(sample_text, curriculum=curr)
    assert res.pii_stripped_count >= 3
    assert res.retake_detected_count == 1

    by_code = {c.course_code: c for c in res.parsed_courses}
    # MT1003 retaken: 5.2 (D+) -> 8.2 (B+), keeps 8.2 (3.5)
    assert by_code["MT1003"].score_10 == 8.2
    assert by_code["MT1003"].gpa_4 == 3.5
    assert by_code["MT1003"].retake_count == 1
    assert len(by_code["MT1003"].retake_history) == 2

    # PH1003 VT -> 0.0 (F, FAIL_SPECIAL)
    assert by_code["PH1003"].status == "FAIL_SPECIAL"
    assert by_code["PH1003"].gpa_4 == 0.0
    assert by_code["PH1003"].passed is False

    # LA1003 MT -> EXEMPT_PASS, counts_for_gpa == False
    assert by_code["LA1003"].status == "EXEMPT_PASS"
    assert by_code["LA1003"].counts_for_gpa is False
    assert by_code["LA1003"].passed is True

    # RT and CH courses placed in withdrawn_or_inprogress (stay in remaining courses)
    inactive_codes = {c.course_code for c in res.withdrawn_or_inprogress}
    assert "MT1005" in inactive_codes
    assert "EE2033" in inactive_codes
    assert "MT1005" not in by_code
    assert "EE2033" not in by_code


def test_csv_and_xlsx_upload_and_fuzzy_matching():
    curr = load_curriculum("7480101", "K2025")

    # Test CSV template round-trip
    csv_tpl = generate_csv_template()
    res_csv = parse_transcript_file("template.csv", csv_tpl.encode("utf-8-sig"), curriculum=curr)
    assert len(res_csv.parsed_courses) >= 6

    # Test CP1258 / UTF-8 CSV with unaccented fuzzy course name and unknown elective
    fuzzy_csv = (
        "Ma MH,Ten mon hoc,So TC,Diem TK,Diem chu\n"
        "OLD999,Cau truc du lieu va giai thuat,4,8.5,A\n"
        "FREE01,Chuyen de tu chon ngoai nganh,3,7.6,B\n"
    ).encode("utf-8")
    res_fuzzy = parse_transcript_file("fuzzy.csv", fuzzy_csv, curriculum=curr)
    by_code = {c.course_code: c for c in res_fuzzy.parsed_courses}

    # Fuzzy matched "Cau truc du lieu va giai thuat" -> CO2003
    assert "CO2003" in by_code
    assert by_code["CO2003"].match_tier == "FUZZY_NAME"
    assert by_code["CO2003"].match_confidence >= 85.0

    # Unmatched course placed in unmatched_courses bucket
    assert any(c.course_code == "FREE01" for c in res_fuzzy.unmatched_courses)

    # Test real .xlsx workbook in memory
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["MSSV: 2310999", "Họ tên: Lê Hoàng Nam"])
    ws.append(["Học kỳ", "Mã MH", "Tên môn học", "Tín chỉ", "Điểm hệ 10", "Điểm chữ"])
    ws.append(["HK241", "MT1003", "Giải tích 1", 4, 8.0, "B+"])
    ws.append(["HK241", "MT1007", "Đại số tuyến tính", 3, 9.0, "A"])
    ws.append(["HK241", "SP1031", "Triết học Mác - Lênin", 3, "KD", "KD"])
    buf = io.BytesIO()
    wb.save(buf)

    res_xlsx = parse_transcript_file("bang_diem.xlsx", buf.getvalue(), curriculum=curr)
    assert res_xlsx.pii_stripped_count >= 1
    xlsx_map = {c.course_code: c for c in res_xlsx.parsed_courses}
    assert xlsx_map["MT1003"].gpa_4 == 3.5
    assert xlsx_map["MT1007"].gpa_4 == 4.0
    assert xlsx_map["SP1031"].status == "FAIL_SPECIAL"
    assert xlsx_map["SP1031"].gpa_4 == 0.0
