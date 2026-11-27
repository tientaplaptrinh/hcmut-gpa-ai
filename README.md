# BK-GPA & Optimal Study Roadmap AI (HCMUT Full-Stack Edition)

Ứng dụng thông minh hỗ trợ sinh viên **Trường Đại học Bách Khoa — ĐHQG TP.HCM (HCMUT)** dự đoán độ khó học phần theo đồ thị tiên quyết CTĐT chính thức (`hcmut.edu.vn`), tự động đọc bảng điểm **MyBK / Excel / CSV**, tính GPA chuẩn quy chế học vụ (QĐ 2931/2933 & QĐ 1259/1260) và giải bài toán **Quy hoạch nguyên thực hỗn hợp (MILP)** tối ưu đồng thời lộ trình học mới + học cải thiện điểm.

## Khởi chạy nhanh trên máy cục bộ

### 1. Thu thập dữ liệu CTĐT & Chạy Backend (FastAPI, cổng `8000`)
```powershell
cd "C:\Users\DELL INSPIRON 5515\.gemini\antigravity\scratch\hcmut-gpa-ai"
.\.venv\Scripts\python.exe data_pipeline/crawl_hcmut.py
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Chạy Frontend (React + Vite + TypeScript, cổng `5173`)
```powershell
cd "C:\Users\DELL INSPIRON 5515\.gemini\antigravity\scratch\hcmut-gpa-ai\frontend"
npm.cmd run dev
```
Mở trình duyệt tại: `http://127.0.0.1:5173`

### 3. Chạy Kiểm thử Tự động (Pytest + Playwright E2E)
```powershell
# Kiểm thử Backend & MILP
.\.venv\Scripts\python.exe -m pytest backend/tests -v

# Kiểm thử trình duyệt đầu-cuối Playwright E2E
cd frontend
npx.cmd playwright test
```
