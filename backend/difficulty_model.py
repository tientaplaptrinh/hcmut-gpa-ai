"""Multi-Factor HCMUT Course Difficulty Predictor (1.0–10.0) & Vietnamese AI Rationale Engine.

Combines:
1. Curriculum Prerequisite DAG structure (chain depth & downstream gatekeeper centrality)
2. Credit load & course level (1xxx–4xxx)
3. Knowledge-block complexity (Toán & KHTN / Cơ sở ngành / Chuyên ngành / Tốt nghiệp vs. Giáo dục chung)
4. Lab / project / capstone intensity
5. Calibrated HCMUT domain priors (Trường điện từ, Giải tích 1/2, Giải tích mạch, Mạch điện tử, Vi xử lý, CTDL&GT, HĐH...)
6. Dynamic per-course user difficulty overrides (`user_difficulty_overrides`)
"""

from __future__ import annotations

import os
import re
from typing import Optional

from backend.contracts import (
    CourseDifficultyPrediction,
    CourseItem,
    CurriculumSchema,
    DifficultyDashboardResponse,
    DifficultyTier,
    SemesterDifficultyTrend,
)
from backend.hcmut_gpa import strip_accents


# Calibrated HCMUT domain priors by exact course code
HCMUT_CODE_PRIORS: dict[str, tuple[float, list[str], str]] = {
    "MT1003": (
        7.8,
        ["Toán nền tảng", "Tốc độ giảng nhanh", "Tự luận/Trắc nghiệm gắt"],
        "Môn cửa ải Toán năm nhất ĐHBK với lượng kiến thức giới hạn, đạo hàm, tích phân suy rộng và phương trình vi phân dày đặc.",
    ),
    "MT1005": (
        8.6,
        ["Môn cửa ải", "Giải tích vector 3D", "Tỷ lệ trượt cao"],
        "Giải tích 2 nổi tiếng nặng tại Bách Khoa với tích phân bội, tích phân đường/mặt, định lý Stokes-Ostrogradsky và chuỗi hàm.",
    ),
    "MT1007": (
        7.4,
        ["Trừu tượng cao", "Không gian vector", "Nền tảng AI/ĐKTĐ"],
        "Đòi hỏi tư duy trừu tượng về không gian vector, trị riêng, chéo hóa ma trận và dạng toàn phương.",
    ),
    "MT1009": (
        7.3,
        ["Giải thuật số", "Sai số hội tụ", "Lập trình tính toán"],
        "Kết hợp giải tích toán học với lập trình xấp xỉ nghiệm, nội suy và giải số phương trình vi phân.",
    ),
    "MT2013": (
        8.0,
        ["Xác suất đa biến", "Kiểm định thống kê", "BTL xử lý dữ liệu"],
        "Xác suất & Thống kê có bài tập lớn xử lý dữ liệu thực tế cùng đề thi phân loại mạnh ở phần biến ngẫu nhiên nhiều chiều.",
    ),
    "PH1003": (
        7.6,
        ["Cơ - Nhiệt đại cương", "Áp dụng vi tích phân", "Đề thi trắc nghiệm bẫy"],
        "Vật lý 1 yêu cầu vận dụng trực tiếp vi tích phân vào cơ học vật rắn và nhiệt động lực học.",
    ),
    "PH1005": (
        8.1,
        ["Điện - Từ - Quang", "Trừu tượng vật lý", "Liên kết Trường điện từ"],
        "Vật lý 2 bao phủ trường tĩnh điện, từ trường, cảm ứng điện từ và cơ học lượng tử với khối lượng công thức lớn.",
    ),
    "EE2009": (
        9.3,
        ["Sát thủ Khoa Điện", "Phương trình Maxwell", "Giải tích vector nặng"],
        "Trường điện từ được xem là môn 'sát thủ' số 1 Khoa Điện - Điện tử: đòi hỏi giải tích vector 3 chiều, phương trình Maxwell và truyền sóng điện từ.",
    ),
    "EE2033": (
        8.5,
        ["Cửa ải Cơ sở ngành", "Biến đổi Laplace/Phasor", "Nền tảng mọi môn Điện"],
        "Giải tích mạch là môn tiên quyết cốt lõi mở khóa hầu hết các môn chuyên ngành Điện - Điện tử, yêu cầu biến đổi miền tần số và miền s thành thạo.",
    ),
    "EE2023": (
        8.4,
        ["Cửa ải Cơ sở ngành", "Mạch xoay chiều 3 pha", "Quá độ mạch"],
        "Mạch điện cơ sở có khối lượng bài tập biến đổi phức, mạng hai cửa và quá trình quá độ rất nặng.",
    ),
    "EE2035": (
        8.4,
        ["Phân tích BJT/MOSFET", "Mạch khuếch đại", "Mô phỏng SPICE"],
        "Mạch điện tử đòi hỏi nắm vững mô hình tín hiệu nhỏ BJT/MOSFET, đáp ứng tần số và hồi tiếp âm.",
    ),
    "EE2037": (
        8.5,
        ["Assembly & C nhúng", "Kiến trúc thanh ghi", "Thí nghiệm phần cứng"],
        "Kỹ thuật Vi xử lý kết hợp lập trình mức thanh ghi/Assembly, ngắt, ngoại vi và bài thí nghiệm/đồ án mạch thực tế.",
    ),
    "EE2039": (
        8.6,
        ["Biến đổi Fourier/Z", "Thiết kế bộ lọc số", "Toán tín hiệu nặng"],
        "Xử lý tín hiệu số có mật độ toán biến đổi Fourier rời rạc (DFT/FFT) và thiết kế lọc IIR/FIR cao.",
    ),
    "EE2005": (
        8.5,
        ["Tích chập liên tục/rời rạc", "Fourier & Laplace", "Trừu tượng cao"],
        "Tín hiệu và hệ thống là nền tảng toán học khắt khe cho Viễn thông, Điều khiển và Vi mạch.",
    ),
    "EE2011": (
        8.4,
        ["Quỹ đạo nghiệm số", "Tiêu chuẩn Nyquist/Bode", "Không gian trạng thái"],
        "Cơ sở điều khiển tự động kết hợp đại số ma trận, biến đổi Laplace và khảo sát ổn định hệ thống động lực.",
    ),
    "EE3011": (
        8.7,
        ["Bộ biến đổi công suất", "Phân tích dạng sóng", "Mô phỏng MATLAB/Simulink"],
        "Điện tử công suất yêu cầu phân tích chi tiết từng chu kỳ đóng cắt linh kiện bán dẫn công suất và điều chế PWM.",
    ),
    "EE3031": (
        8.5,
        ["Mạch từ & Máy điện", "Không gian vector từ thông", "Thí nghiệm tải thực"],
        "Máy điện đòi hỏi hiểu sâu tương tác điện từ cơ trong máy biến áp, động cơ không đồng bộ và đồng bộ.",
    ),
    "EE3019": (
        8.8,
        ["Trào lưu công suất", "Ngắn mạch hệ thống", "Ma trận tổng dẫn lớn"],
        "Giải tích hệ thống điện yêu cầu giải bài toán trào lưu công suất Newton-Raphson và tính toán sự cố lưới điện.",
    ),
    "CO1027": (
        7.7,
        ["C/C++ con trỏ", "Quản lý bộ nhớ", "BTL chấm test tự động"],
        "Kỹ thuật lập trình kiểm tra khắt khe con trỏ, cấp phát động, OOP và hệ thống testcase tự động nghiêm ngặt.",
    ),
    "CO2003": (
        8.7,
        ["Cửa ải KHMT", "Độ phức tạp giải thuật", "Cây cân bằng & Đồ thị"],
        "Cấu trúc dữ liệu & Giải thuật là môn trụ cột phân loại mạnh nhất ngành KHMT/KTMT với BTL cài đặt cấu trúc dữ liệu lớn.",
    ),
    "CO2007": (
        8.2,
        ["Pipeline MIPS/RISC-V", "Bộ nhớ Cache", "Thiết kế datapath"],
        "Kiến trúc máy tính yêu cầu hiểu sâu pipeline, hazard, phân cấp bộ nhớ cache và hợp ngữ.",
    ),
    "CO2017": (
        8.8,
        ["Lập trình nhân HĐH", "Đồng bộ tiến trình", "Quản lý bộ nhớ ảo"],
        "Hệ điều hành nổi tiếng với bài tập lớn can thiệp kernel/thread, giải quyết race condition và cấp phát bộ nhớ ảo.",
    ),
    "CO3005": (
        9.0,
        ["Sát thủ Khoa Máy tính", "ANTLR / Trình biên dịch", "AST & Type Checker"],
        "Nguyên lý ngôn ngữ lập trình có chuỗi 4 bài tập lớn xây dựng lexer, parser, AST và kiểm tra kiểu cực kỳ thử thách.",
    ),
    "CO2013": (
        7.8,
        ["Đại số quan hệ", "Tối ưu truy vấn SQL", "Chuẩn hóa BCNF"],
        "Hệ cơ sở dữ liệu kết hợp lý thuyết chuẩn hóa lược đồ, giao tác ACID và đồ án thiết kế ứng dụng CSDL.",
    ),
    "CO3093": (
        7.9,
        ["Giao thức TCP/IP", "Định tuyến mạng", "Lập trình Socket"],
        "Mạng máy tính bao phủ toàn bộ chồng giao thức OSI/TCP-IP cùng bài tập lớn lập trình mạng phân tán.",
    ),
}


# Keyword-based HCMUT priors when exact course code varies across cohorts/programs (e.g. CTTT, Vi mạch)
HCMUT_NAME_PRIORS: list[tuple[tuple[str, ...], float, list[str], str]] = [
    (
        ("truong dien tu",),
        9.2,
        ["Sát thủ Khoa Điện", "Phương trình Maxwell", "Giải tích vector 3D"],
        "Trường điện từ đòi hỏi giải tích vector không gian 3 chiều, phương trình Maxwell và lý thuyết truyền sóng điện từ.",
    ),
    (
        ("nguyen ly ngon ngu lap trinh",),
        9.0,
        ["Trình biên dịch", "AST & Parser", "Chuỗi BTL nặng"],
        "Môn học yêu cầu tự xây dựng bộ phân tích từ vựng, cú pháp, cây cú pháp trừu tượng (AST) và kiểm tra ngữ nghĩa.",
    ),
    (
        ("thiet ke vi mach tương tu", "vi mach tuong tu", "analog ic"),
        8.9,
        ["Thiết kế CMOS mức transistor", "Phân tích nhiễu & ổn định", "Cadence Virtuoso"],
        "Thiết kế vi mạch tương tự đòi hỏi cân bằng nhiều thông số vật lý bán dẫn phi tuyến, băng thông, độ lợi và layout.",
    ),
    (
        ("thiet ke vi mach so", "thiet ke vlsi", "he thong vlsi"),
        8.8,
        ["RTL-to-GDSII", "Timing Closure", "Verilog/SystemVerilog"],
        "Thiết kế vi mạch số/VLSI yêu cầu nắm vững tổng hợp logic, phân tích định thời tĩnh (STA) và quy trình vật lý.",
    ),
    (
        ("giai tich mach", "mach dien 1", "mach dien 2"),
        8.4,
        ["Cửa ải Cơ sở ngành", "Miền tần số & Laplace", "Bài tập biến đổi phức"],
        "Môn cơ sở ngành nền tảng của Khoa Điện - Điện tử, mở khóa chuỗi môn chuyên ngành phía sau.",
    ),
    (
        ("mach dien tu", "dien tu co ban", "dien tu tuong tu"),
        8.3,
        ["BJT & MOSFET", "Đáp ứng tần số", "Mô phỏng mạch"],
        "Phân tích chế độ một chiều và tín hiệu nhỏ của mạch bán dẫn nhiều tầng với độ chính xác cao.",
    ),
    (
        ("vi xu ly", "vi dieu khien", "he thong nhung"),
        8.4,
        ["Kiến trúc phần cứng", "Lập trình nhúng C/ASM", "Giao tiếp ngoại vi"],
        "Kết hợp chặt giữa kiến trúc phần cứng vi điều khiển, quản lý ngắt thời gian thực và thực hành mạch.",
    ),
    (
        ("xu ly tin hieu so", "tin hieu va he thong"),
        8.5,
        ["Biến đổi Fourier/Laplace/Z", "Toán tín hiệu", "Thiết kế bộ lọc"],
        "Mật độ toán biến đổi tích phân và chuỗi rời rạc dày đặc, đòi hỏi nền tảng Giải tích vững.",
    ),
    (
        ("dieu khien tu dong", "ly thuyet dieu khien"),
        8.4,
        ["Ổn định hệ thống", "Bode/Nyquist/State-Space", "Mô phỏng điều khiển"],
        "Yêu cầu phân tích động học hệ thống, thiết kế bộ điều khiển PID/không gian trạng thái và khảo sát bền vững.",
    ),
    (
        ("dien tu cong suat",),
        8.6,
        ["Bán dẫn công suất", "Biến đổi DC-DC/Inverter", "Phân tích sóng hài"],
        "Phân tích mạch phi tuyến đóng cắt tần số cao, tổn hao công suất và điều khiển biến tần.",
    ),
    (
        ("giai tich he thong dien", "on dinh he thong dien"),
        8.7,
        ["Trào lưu công suất", "Ngắn mạch & Ổn định", "Hệ phương trình phi tuyến"],
        "Bài toán quy mô lưới điện lớn với ma trận tổng dẫn phức và tính toán quá độ điện cơ.",
    ),
    (
        ("cau truc du lieu va giai thuat",),
        8.7,
        ["Cửa ải KHMT", "Cây & Đồ thị", "Tối ưu độ phức tạp"],
        "Trụ cột thuật toán với yêu cầu cài đặt C++ tối ưu bộ nhớ và thời gian chạy nghiêm ngặt.",
    ),
    (
        ("he dieu hanh",),
        8.7,
        ["Đồng bộ hóa", "Quản lý tiến trình & bộ nhớ", "Lập trình hệ thống"],
        "Khối lượng kiến thức hệ thống sâu kèm bài tập lớn lập trình đa luồng/nhân hệ điều hành.",
    ),
    (
        ("tri tue nhan tao", "hoc may", "machine learning", "deep learning"),
        8.3,
        ["Tối ưu hóa & Ma trận", "Xác suất thống kê", "Đồ án huấn luyện mô hình"],
        "Đòi hỏi nền tảng Đại số tuyến tính, Xác suất thống kê và kỹ năng thực nghiệm mô hình trên dữ liệu lớn.",
    ),
    (
        ("do an tot nghiep", "luan van tot nghiep", "khoa luan tot nghiep"),
        8.2,
        ["Bảo vệ hội đồng", "Nghiên cứu & Triển khai độc lập", "Điểm sàn ≥ C (5.5)"],
        "Học phần tổng hợp cuối khóa yêu cầu hoàn thiện sản phẩm/nghiên cứu hoàn chỉnh và bảo vệ trước hội đồng (điểm sàn đạt ≥ C).",
    ),
    (
        ("do an chuyen nganh", "do an thiet ke", "do an mon hoc"),
        7.5,
        ["Thiết kế kỹ thuật", "Báo cáo & Vấn đáp", "Điểm sàn ≥ C (5.5)"],
        "Đòi hỏi tự thiết kế, mô phỏng/thi công nguyên mẫu và bảo vệ vấn đáp trực tiếp với giảng viên hướng dẫn.",
    ),
    (
        ("thuc tap ngoai truong", "thuc tap tot nghiep"),
        5.2,
        ["Trải nghiệm doanh nghiệp", "Báo cáo thực tập", "Điểm sàn ≥ C (5.5)"],
        "Làm việc thực tế tại doanh nghiệp đối tác; áp lực thi cử thấp nhưng bắt buộc hoàn thành đúng tiến độ và đạt từ điểm C trở lên.",
    ),
    (
        ("triet hoc mac", "kinh te chinh tri", "chu nghia xa hoi", "lich su dang", "tu tuong ho chi minh"),
        3.9,
        ["Lý luận chính trị", "Đọc hiểu giáo trình", "Dễ cải thiện điểm cao"],
        "Môn đại cương lý luận chính trị có cấu trúc đề thi ổn định, phù hợp để đầu tư đạt điểm B+/A kéo GPA tích lũy.",
    ),
    (
        ("phap luat viet nam", "con nguoi va moi truong", "quan tri hoc", "kinh te dai cuong", "khoi nghiep", "ky nang mem", "nhap mon ve ky thuat"),
        3.8,
        ["Giáo dục chung", "Làm việc nhóm", "Cơ hội kéo GPA"],
        "Khối lượng tính toán nhẹ, đánh giá nhiều qua tiểu luận/thuyết trình nhóm, rất thuận lợi để đạt điểm A hoặc học cải thiện.",
    ),
    (
        ("anh van 1", "anh van 2", "anh van 3", "anh van 4", "english"),
        3.9,
        ["Ngoại ngữ học thuật", "4 kỹ năng", "Có thể miễn điểm chuẩn quốc tế"],
        "Môn ngoại ngữ theo chuẩn đầu ra Bách Khoa; sinh viên có nền tảng tiếng Anh tốt dễ đạt điểm cao.",
    ),
    (
        ("giao duc the chat", "the duc", "giao duc quoc phong"),
        2.3,
        ["Không tính vào GPA", "Điều kiện hoàn thành CTĐT"],
        "Học phần rèn luyện thể chất / quốc phòng bắt buộc hoàn thành để xét tốt nghiệp nhưng không tính vào mẫu số GPA.",
    ),
    (
        ("thi nghiem", "thuc hanh"),
        5.8,
        ["Thực hành phòng Lab", "Viết báo cáo chuẩn bị", "Vấn đáp đầu/cuối buổi"],
        "Học phần thí nghiệm 1–2 tín chỉ yêu cầu chuẩn bị bài trước buổi đo đạc và xử lý số liệu cẩn thận.",
    ),
]


BLOCK_BASE_COMPLEXITY: dict[str, float] = {
    "Toán & KHTN": 6.6,
    "Cơ sở ngành": 6.9,
    "Chuyên ngành": 7.1,
    "Tốt nghiệp": 7.0,
    "Giáo dục chung": 3.8,
}


def score_to_tier(score: float) -> DifficultyTier:
    if score < 4.5:
        return "Dễ"
    if score < 6.5:
        return "Trung bình"
    if score < 8.0:
        return "Khó"
    return "Rất khó"


def compute_dag_metrics(courses: list[CourseItem]) -> tuple[dict[str, int], dict[str, int]]:
    """Compute prerequisite chain depth (upstream depth) and downstream dependent count."""
    code_set = {c.course_code for c in courses}
    prereq_map: dict[str, list[str]] = {
        c.course_code: [p for p in c.prerequisites if p in code_set and p != c.course_code]
        for c in courses
    }
    children_map: dict[str, list[str]] = {c.course_code: [] for c in courses}
    for code, plist in prereq_map.items():
        for p in plist:
            children_map[p].append(code)

    depth_memo: dict[str, int] = {}

    def get_upstream_depth(code: str, stack: set[str]) -> int:
        if code in depth_memo:
            return depth_memo[code]
        if code in stack:
            return 0
        stack.add(code)
        preds = prereq_map.get(code, [])
        d = 0 if not preds else 1 + max(get_upstream_depth(p, stack) for p in preds)
        stack.remove(code)
        depth_memo[code] = d
        return d

    def get_downstream_reach(code: str) -> int:
        visited: set[str] = set()
        queue = list(children_map.get(code, []))
        while queue:
            nxt = queue.pop()
            if nxt not in visited and nxt != code:
                visited.add(nxt)
                queue.extend(children_map.get(nxt, []))
        return len(visited)

    depths = {c.course_code: get_upstream_depth(c.course_code, set()) for c in courses}
    dependents = {c.course_code: get_downstream_reach(c.course_code) for c in courses}
    return depths, dependents


def maybe_llm_enrich_rationale(course: CourseItem, deterministic_rationale: str) -> str:
    """Optional LLM enrichment hook with zero-latency deterministic HCMUT fallback."""
    if os.getenv("ENABLE_LLM_DIFFICULTY_ENRICHMENT", "").lower() not in ("1", "true", "yes"):
        return deterministic_rationale
    # Deterministic fallback remains authoritative unless external LLM enrichment is explicitly enabled
    return deterministic_rationale


def predict_course_difficulty(
    course: CourseItem,
    prereq_depth: int,
    dependent_count: int,
    override_score: Optional[float] = None,
) -> CourseDifficultyPrediction:
    code = course.course_code.upper()
    norm_name = strip_accents(course.course_name).lower()

    base_block = BLOCK_BASE_COMPLEXITY.get(course.knowledge_block, 6.0)
    credit_adj = min(0.8, max(-0.7, (course.credits - 3) * 0.42)) if course.credits > 0 else -1.5
    dag_adj = min(1.3, prereq_depth * 0.25 + min(dependent_count, 8) * 0.12)

    # Course level adjustment (2xxx/3xxx/4xxx core engineering vs 1xxx intro)
    digits = re.findall(r"\d{4}", code)
    level_digit = int(digits[0][0]) if digits else 2
    level_adj = {1: -0.15, 2: 0.25, 3: 0.45, 4: 0.55}.get(level_digit, 0.2)
    if course.knowledge_block == "Giáo dục chung":
        level_adj = -0.2

    structural_score = base_block + credit_adj + dag_adj + level_adj

    prior_score: Optional[float] = None
    tags: list[str] = []
    rationale: Optional[str] = None

    if code in HCMUT_CODE_PRIORS:
        prior_score, p_tags, rationale = HCMUT_CODE_PRIORS[code]
        tags.extend(p_tags)
    else:
        for kw_tuple, p_sc, p_tags, p_rat in HCMUT_NAME_PRIORS:
            if any(kw in norm_name for kw in kw_tuple):
                prior_score = p_sc
                tags.extend(p_tags)
                rationale = p_rat
                break

    if prior_score is not None:
        raw_ai = 0.72 * prior_score + 0.28 * structural_score
    else:
        raw_ai = structural_score

    if not course.counts_for_gpa and prior_score is None:
        raw_ai = min(raw_ai, 3.0)

    ai_score = round(max(1.0, min(10.0, raw_ai)), 1)

    # Add structural tags if not already rich
    if dependent_count >= 3 and "Môn mở khóa chuỗi" not in tags:
        tags.append(f"Mở khóa {dependent_count} môn sau")
    if prereq_depth >= 2:
        tags.append(f"Chuỗi tiên quyết bậc {prereq_depth}")
    if course.credits >= 4 and "Tín chỉ nặng (4 TC)" not in tags:
        tags.append(f"Trọng số lớn ({course.credits} TC)")
    if course.requires_min_c and "Điểm sàn ≥ C (5.5)" not in tags:
        tags.append("Điểm sàn ≥ C (5.5)")
    if not tags:
        tags.append(course.knowledge_block)

    if not rationale:
        parts = [f"Thuộc khối {course.knowledge_block} ({course.credits} tín chỉ, học kỳ {course.recommended_semester})."]
        if dependent_count > 0:
            parts.append(f"Đóng vai trò học phần nền tảng dẫn tới {dependent_count} môn học kế tiếp trong CTĐT.")
        if prereq_depth > 0:
            parts.append(
                f"Yêu cầu nắm vững chuỗi {len(course.prerequisites)} môn tiên quyết ({', '.join(course.prerequisites[:3])})."
            )
        if ai_score >= 7.5:
            parts.append("Khối lượng lý thuyết chuyên sâu và bài tập phân loại cao; cần phân bổ thời gian ôn tập sớm.")
        elif ai_score < 4.5:
            parts.append("Mức độ áp lực thi cử vừa phải, là cơ hội tốt để tích lũy điểm A/B+ nâng GPA.")
        else:
            parts.append("Độ khó ở ngưỡng trung bình - khá, bám sát bài tập lớn và đề cương giữa/cuối kỳ sẽ đạt kết quả tốt.")
        rationale = " ".join(parts)

    rationale = maybe_llm_enrich_rationale(course, rationale)

    eff_override = (
        round(max(1.0, min(10.0, float(override_score))), 1)
        if override_score is not None
        else None
    )
    effective_score = eff_override if eff_override is not None else ai_score
    tier = score_to_tier(effective_score)

    breakdown = {
        "block_base": round(base_block, 2),
        "dag_centrality": round(dag_adj, 2),
        "credit_load": round(credit_adj, 2),
        "domain_prior": round(prior_score if prior_score is not None else structural_score, 2),
    }

    return CourseDifficultyPrediction(
        course_code=course.course_code,
        course_name=course.course_name,
        credits=course.credits,
        knowledge_block=course.knowledge_block,
        recommended_semester=course.recommended_semester,
        prerequisites=course.prerequisites,
        dependent_count=dependent_count,
        prereq_chain_depth=prereq_depth,
        ai_difficulty_score=ai_score,
        effective_difficulty_score=effective_score,
        user_override_score=eff_override,
        tier=tier,
        challenge_tags=tags[:4],
        rationale_vi=rationale,
        factor_breakdown=breakdown,
        counts_for_gpa=course.counts_for_gpa,
        is_elective=course.is_elective,
        requires_min_c=course.requires_min_c,
    )


def build_difficulty_dashboard(
    curriculum: CurriculumSchema,
    user_difficulty_overrides: Optional[dict[str, float]] = None,
) -> DifficultyDashboardResponse:
    overrides = {
        k.strip().upper(): float(v)
        for k, v in (user_difficulty_overrides or {}).items()
    }
    depths, dependents = compute_dag_metrics(curriculum.courses)

    predictions = [
        predict_course_difficulty(
            course=c,
            prereq_depth=depths.get(c.course_code, 0),
            dependent_count=dependents.get(c.course_code, 0),
            override_score=overrides.get(c.course_code.upper()),
        )
        for c in curriculum.courses
    ]

    gpa_preds = [p for p in predictions if p.counts_for_gpa and p.credits > 0]
    if gpa_preds:
        tot_w = sum(p.credits for p in gpa_preds)
        avg_diff = round(
            sum(p.effective_difficulty_score * p.credits for p in gpa_preds) / max(1, tot_w),
            2,
        )
    else:
        avg_diff = 5.0

    # Top 5 gatekeeper courses: ranked by effective difficulty + gatekeeper bonus for compulsory courses
    compulsory_gpa = [p for p in gpa_preds if not p.is_elective] or gpa_preds
    top_gatekeepers = sorted(
        compulsory_gpa,
        key=lambda p: (
            p.effective_difficulty_score + min(p.dependent_count, 5) * 0.08,
            p.credits,
        ),
        reverse=True,
    )[:5]

    # Knowledge-block averages
    block_buckets: dict[str, list[CourseDifficultyPrediction]] = {}
    for p in gpa_preds:
        block_buckets.setdefault(p.knowledge_block, []).append(p)

    canonical_blocks = [
        "Toán & KHTN",
        "Giáo dục chung",
        "Cơ sở ngành",
        "Chuyên ngành",
        "Tốt nghiệp",
    ]
    block_averages: dict[str, float] = {}
    for blk in canonical_blocks:
        items = block_buckets.get(blk, [])
        if items:
            w = sum(x.credits for x in items)
            block_averages[blk] = round(
                sum(x.effective_difficulty_score * x.credits for x in items) / max(1, w),
                2,
            )

    # Semester trend (for compulsory + core semester plan so credit sums look realistic per semester)
    sem_buckets: dict[int, list[CourseDifficultyPrediction]] = {}
    for p in gpa_preds:
        if not p.is_elective or p.recommended_semester <= 6:
            sem_buckets.setdefault(p.recommended_semester, []).append(p)
    # Include semester 7-8 courses even if elective when a semester would otherwise be sparse
    for p in gpa_preds:
        if p.is_elective and p.recommended_semester >= 7:
            cur_list = sem_buckets.setdefault(p.recommended_semester, [])
            if sum(x.credits for x in cur_list) < 15:
                cur_list.append(p)

    semester_trends: list[SemesterDifficultyTrend] = []
    for sem in sorted(sem_buckets.keys()):
        s_items = sem_buckets[sem]
        s_cred = sum(x.credits for x in s_items)
        mean_d = round(sum(x.effective_difficulty_score for x in s_items) / len(s_items), 2)
        weighted_d = round(
            sum(x.effective_difficulty_score * x.credits for x in s_items) / max(1, s_cred),
            2,
        )
        semester_trends.append(
            SemesterDifficultyTrend(
                semester=sem,
                semester_label=f"HK {sem}",
                avg_difficulty=mean_d,
                weighted_difficulty=weighted_d,
                total_credits=s_cred,
                course_count=len(s_items),
            )
        )

    return DifficultyDashboardResponse(
        major_code=curriculum.major_code,
        major_name=curriculum.major_name,
        faculty=curriculum.faculty,
        cohort=curriculum.cohort,
        total_credits=curriculum.total_credits,
        total_gpa_credits=curriculum.total_gpa_credits,
        average_difficulty=avg_diff,
        top_gatekeeper_courses=top_gatekeepers,
        block_averages=block_averages,
        semester_trends=semester_trends,
        courses=predictions,
    )
