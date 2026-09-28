"""
run.py - Điểm khởi chạy chính của Client App (FastAPI + React Frontend)
Cách chạy từ thư mục gốc MLAI:
    .\\.venv\\Scripts\\python.exe client_app/run.py
"""

import sys
from pathlib import Path

# Đảm bảo console Windows in tiếng Việt UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Thêm client_app vào sys.path để import dễ dàng
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

import uvicorn
from backend.config import PORT, HOST, LLM_MODEL

if __name__ == "__main__":
    print("\n" + "=" * 75)
    print("🚀 NỀN TẢNG RA QUYẾT ĐỊNH & TRỢ LÝ KINH DOANH THỰC CHIẾN (CLIENT APP)")
    print(f"👉 Ứng dụng Web (React Frontend): http://localhost:{PORT}")
    print(f"👉 API Documentation (Swagger):   http://localhost:{PORT}/docs")
    print(f"👉 Trạng thái hệ thống:           http://localhost:{PORT}/api/health")
    print(f"🗄️  Cơ sở dữ liệu:                 MongoDB Atlas (5 CSDL)")
    print(f"🧠 Mô hình Vector Embedding:      BAAI/bge-m3 (GPU CUDA)")
    print(f"🤖 Mô hình Trợ lý Suy luận:       {LLM_MODEL} (Ollama Local)")
    print("=" * 75)
    print("Nhấn Ctrl + C để dừng máy chủ bất kỳ lúc nào.\n")

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)
