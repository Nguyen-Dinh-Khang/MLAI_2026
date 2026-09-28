# HƯỚNG DẪN SỬ DỤNG: NỀN TẢNG RA QUYẾT ĐỊNH & TRỢ LÝ KINH DOANH THỰC CHIẾN (CLIENT APP)

> **Mô hình Song Trụ (Dual-Engine v3.0)** phục vụ trọn vẹn vòng đời kinh doanh:
> 1. **Giao diện 1 (Day 0 - Trước khi mở quán)**: Máy quét Thẩm định Ý tưởng (Feasibility Scanner).
> 2. **Giao diện 2 (Day 1 đến 365 - Trong khi vận hành)**: Trợ lý Chiến thuật Đồng hành (Tactical Co-pilot).

---

## 1. CÔNG NGHỆ SỬ DỤNG (TECH STACK)

- **Backend**: FastAPI (Python 3.13) chạy trên cổng **`5000`**.
- **Frontend**: React (Vite + Tailwind CSS + Lucide Icons), đã biên dịch sẵn vào `frontend/dist` để FastAPI tự động phục vụ trực tiếp.
- **Vector Embedding**: `BAAI/bge-m3` (chạy trên GPU CUDA qua thư viện `sentence-transformers`).
- **LLM Reasoning**: `Qwen3.5 4B` (chạy cục bộ qua máy chủ Ollama tại cổng 11434).
- **Cơ sở dữ liệu**: MongoDB Atlas (`MLAI_Hackathon_2026`) gồm đủ 5 CSDL chuẩn hóa:
  - `areas` (DB1 - Dân cư & Sức mua khu vực 3km)
  - `competitors` (DB2 - Đối thủ cạnh tranh vi mô trong 1km)
  - `problems` (DB3 - Rủi ro & Sự cố vận hành kèm Vector 1024 chiều)
  - `experiences` (DB4 - Bài học xương máu & Lời thoại thực chiến kèm Vector 1024 chiều)
  - `market_segments` (DB5 - Thị trường & Hành vi khách hàng kèm Vector 1024 chiều)

---

## 2. HƯỚNG DẪN KHỞI CHẠY (QUICK START)

Mọi thư viện cần thiết đã được cài đặt trong môi trường ảo `.venv` của thư mục dự án `MLAI`.

### Bước 1: Đảm bảo dịch vụ Ollama đang chạy
Kiểm tra xem Ollama đã bật mô hình `qwen3.5:4b`:
```bash
ollama run qwen3.5:4b
```

### Bước 2: Khởi động máy chủ Client App
Mở terminal tại thư mục gốc `c:\Users\khang\.vscode\MLAI` và chạy:
```powershell
.\.venv\Scripts\python.exe client_app/run.py
```

### Bước 3: Mở trình duyệt trải nghiệm
- **Giao diện Web Khách Hàng**: [http://localhost:5000](http://localhost:5000)
- **Tài liệu API tương tác (Swagger UI)**: [http://localhost:5000/docs](http://localhost:5000/docs)
- **Kiểm tra trạng thái kết nối**: [http://localhost:5000/api/health](http://localhost:5000/api/health)

---

## 3. CẤU TRÚC THƯ MỤC VÀ GIẢI THÍCH LOGIC TỪNG FILE

```
client_app/
│
├── .env                              # Cấu hình PORT=5000, MONGO_URI, OLLAMA, BGE-M3
├── requirements.txt                  # Danh sách thư viện Python độc lập của ứng dụng
├── run.py                            # File khởi chạy nhanh máy chủ
├── test_e2e.py                       # Kịch bản kiểm thử tự động toàn diện
│
├── backend/                          # MÃ NGUỒN BACKEND (FASTAPI)
│   ├── config.py                     # Đọc biến môi trường an toàn từ .env
│   ├── database.py                   # Kết nối MongoDB Atlas và lấy 5 collections
│   ├── tag_manager.py                # Quản lý 10 Mô hình (101-110) & 20 Sản phẩm (201-220)
│   ├── tag_map.json                  # File metadata Master Tags chuẩn hóa v3.1.0
│   ├── main.py                       # Máy chủ FastAPI, định tuyến các API và phục vụ React
│   │
│   └── pipeline/                     # 6 MẮT XÍCH PIPELINE TÍNH TOÁN CỐT LÕI
│       ├── spatial_engine.py         # Mắt xích 1: Geocoding, quét Dân cư DB1 & Đối thủ DB2 trong 1km
│       ├── market_gap_engine.py      # Mắt xích 2: So khớp DB2 x DB5 phát hiện Lỗ hổng thị trường
│       ├── stress_test_engine.py     # Mắt xích 3: Giả lập tài chính, tính Runway và giá thuê trần từ DB3
│       ├── semantic_search.py        # Mắt xích 4: BAAI/bge-m3 Cosine Similarity tìm kiếm trên DB3, 4, 5
│       ├── distillation.py           # Mắt xích 5: Chắt lọc dữ liệu, khử trùng lặp, nén 80% Token
│       └── llm_copilot.py            # Mắt xích 6: Gọi Qwen3.5 4B qua Ollama với System Prompt thực chiến
│
└── frontend/                         # MÃ NGUỒN GIAO DIỆN REACT (VITE + TAILWIND)
    ├── package.json                  # Dependencies React & Tailwind
    ├── vite.config.js                # Cấu hình proxy API sang port 5000
    ├── dist/                         # Bản build tĩnh production (FastAPI tự động phục vụ)
    └── src/
        ├── main.jsx                  # Điểm nạp React
        ├── App.jsx                   # Quản lý chuyển đổi Tab (Scanner vs Copilot)
        ├── components/
        │   ├── Navbar.jsx            # Header, bộ chuyển đổi 2 Tab và huy hiệu trạng thái
        │   ├── FeasibilityScanner.jsx# Tab 1: Form thẩm định ý tưởng & Báo cáo trực quan 4 khối
        │   └── TacticalCopilot.jsx   # Tab 2: Chat giải quyết sự cố, Checklist 24h & Lời thoại đàm phán
        └── index.css                 # Phong cách Tailwind CSS hiện đại
```

---

## 4. CHI TIẾT LOGIC HOẠT ĐỘNG CỦA 2 GIAO DIỆN

### Giao diện 1: Máy quét Thẩm định Ý tưởng (Day 0)
1. **Người dùng nhập**: Địa chỉ dự kiến, Mô hình quán (1 trong 10 mô hình), Nhóm món (1-3 nhóm trong 20 nhóm), Số vốn và Giá thuê.
2. **Hệ thống xử lý**:
   - `spatial_engine`: Geocoding ra tọa độ, quét dân cư DB1 quanh 3km, quét đối thủ DB2 trong bán kính 1km.
   - `market_gap_engine`: Đối chiếu giá và điểm yếu của đối thủ với sức mua DB5 => Rút ra khoảng trống đối thủ bỏ quên.
   - `stress_test_engine`: Trừ chi phí đầu tư ban đầu (Capex), tính số tháng sống sót an toàn (Runway) khi sinh viên nghỉ hè hoặc sụt giảm 40% doanh thu.
   - `llm_copilot`: Gọi `qwen3.5:4b` tổng hợp thành bản thẩm định 4 phần: Điểm khả thi /10, Phân tích đối thủ 1km, Lỗ hổng thị trường, và Lời khuyên tài chính sống còn.

### Giao diện 2: Trợ lý Chiến thuật Đồng hành (Day 1 đến 365)
1. **Người dùng nhập**: Chọn nhanh mô hình quán và gõ câu hỏi thực tế (hoặc bấm vào các nút sự cố khẩn cấp: *Chủ nhà đòi tăng giá, Khách chê đợi lâu, Quán vắng hoe sau khai trương...*).
2. **Hệ thống xử lý**:
   - `semantic_search`: Dùng vector `BAAI/bge-m3` tính Cosine Similarity trên DB3, DB4, DB5 để lấy bài học sát nhất.
   - `distillation`: Nén dữ liệu thô, loại bỏ kể lể, gom các bài học tương tự để tiết kiệm token.
   - `llm_copilot`: Gọi `qwen3.5:4b` xuất ra:
     - **Nguyên nhân cốt lõi**: Giải thích lý do xảy ra sự cố theo tâm lý khách hàng.
     - **Checklist 24h**: Các việc cần làm ngay ngày mai kèm **Lời thoại đàm phán từng câu**.
     - **Con số mục tiêu**: Đo lường thành công (giảm thời gian chờ xuống < 60s, tỷ lệ hủy đơn < 2%).
