"""
test_e2e.py - Script kiểm thử toàn diện End-to-End (E2E) cho Client App
Kiểm tra cả 2 chế độ:
1. Giao diện 1: Thẩm định Ý tưởng (Day 0)
2. Giao diện 2: Trợ lý Giải quyết Sự cố (Day 1 - 365)
"""

import sys
import json
import time

# Đảm bảo in tiếng Việt UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("=" * 75)
print("🧪 BẮT ĐẦU KIỂM THỬ TOÀN DIỆN PIPELINE (FASTAPI + MONGODB + BGE-M3 + QWEN3.5)")
print("=" * 75)

# 1. Test Health Check
print("\n[TEST 1] Kiểm tra /api/health...")
res_health = client.get("/api/health")
print("Status Code:", res_health.status_code)
print("Data:", json.dumps(res_health.json(), ensure_ascii=False, indent=2))
assert res_health.status_code == 200

# 2. Test Metadata
print("\n[TEST 2] Kiểm tra /api/metadata (10 mô hình & 20 sản phẩm)...")
res_meta = client.get("/api/metadata")
print("Status Code:", res_meta.status_code)
meta_data = res_meta.json()
print(f"Số mô hình: {len(meta_data['business_models'])} | Số nhóm sản phẩm: {len(meta_data['products'])}")
assert len(meta_data['business_models']) == 10
assert len(meta_data['products']) == 20

# 3. Test Giao diện 1: Thẩm định Ý tưởng (Day 0)
print("\n[TEST 3] Kiểm tra Chế độ 1: Thẩm định Ý tưởng (Xe bánh mì & Cà phê - ĐH Bách Khoa)...")
start_time = time.time()
res_eval = client.post("/api/scanner/evaluate", json={
    "address": "268 Lý Thường Kiệt, Quận 10, Hồ Chí Minh",
    "model_id": 105,
    "product_ids": [204, 201],
    "budget": 150000000,
    "rent": 8000000
})
print(f"Thời gian xử lý: {time.time() - start_time:.2f}s")
print("Status Code:", res_eval.status_code)

if res_eval.status_code == 200:
    eval_data = res_eval.json()
    print("\n--- KẾT QUẢ THẨM ĐỊNH 4 KHỐI ---")
    print("1. Khu vực khảo sát:", eval_data["demographics"]["name"])
    print("2. Số đối thủ 1km:", eval_data["competitors_summary"]["total_nearby"])
    print("3. Lỗ hổng thị trường phát hiện:", len(eval_data["market_gaps"]["market_gaps"]))
    print("4. Runway cầm cự an toàn:", eval_data["stress_test"]["runway_months"], "tháng")
    print("   Mức giá thuê trần tối đa:", eval_data["stress_test"]["max_recommended_rent"], "VND")
    print("5. Báo cáo AI từ Qwen3.5 4B:")
    print(eval_data["ai_report"][:400] + "...\n")
else:
    print("Lỗi:", res_eval.text)

# 4. Test Giao diện 2: Trợ lý Giải quyết Sự cố & Phản công (Day 1 - 365)
print("\n[TEST 4A] Kiểm tra Chế độ 2 - Nhánh VẬN HÀNH NỘI BỘ (Khách than chờ lâu)...")
start_time = time.time()
res_chat_internal = client.post("/api/copilot/chat", json={
    "query": "Quán tôi mở được 2 tuần cạnh trường Đại học. Mấy hôm nay khách than đợi bánh mì lâu quá nên bỏ đi sang quán khác. Tôi chỉ có 2 người làm, làm sao để phục vụ nhanh hơn mà không cần thuê thêm người?",
    "model_id": 105
})
print(f"Thời gian xử lý: {time.time() - start_time:.2f}s | Status Code: {res_chat_internal.status_code}")
assert res_chat_internal.status_code == 200
data_internal = res_chat_internal.json()
print("Intent nhận diện:", data_internal["intent"])
print("Huy hiệu Badge:", data_internal["intent_badge"])
print("Nguồn CSDL:", data_internal["data_sources"])
assert data_internal["intent"] == "INTERNAL"

print("\n[TEST 4B] Kiểm tra Chế độ 2 - Nhánh PHẢN CÔNG CẠNH TRANH (Đối thủ sát vách phá giá)...")
start_time = time.time()
res_chat_comp = client.post("/api/copilot/chat", json={
    "query": "Có quán mới mở sát vách bán món giống hệt quán tôi nhưng giá rẻ hơn 20% và tặng kèm trà đá. Khách quen của tôi bị hút qua đó khá nhiều, tôi phải đối phó thế nào mà không cần giảm giá?",
    "model_id": 105,
    "address": "268 Lý Thường Kiệt, Quận 10, Hồ Chí Minh",
    "product_ids": [204, 201]
})
print(f"Thời gian xử lý: {time.time() - start_time:.2f}s | Status Code: {res_chat_comp.status_code}")
assert res_chat_comp.status_code == 200
data_comp = res_chat_comp.json()
print("Intent nhận diện:", data_comp["intent"])
print("Huy hiệu Badge:", data_comp["intent_badge"])
print("Nguồn CSDL kích hoạt:", data_comp["data_sources"])
print(f"Số đối thủ quét được (DB2): {data_comp['competitors_count']}")
print(f"Thông tin DB3 (sự cố): {data_comp['matched_insights']['problems_found']} | DB4 (bài học): {data_comp['matched_insights']['lessons_found']}")
assert data_comp["intent"] == "COMPETITIVE"
assert "DB2" in data_comp["data_sources"]
assert "DB3" in data_comp["data_sources"]
assert "DB4" in data_comp["data_sources"]
assert "DB5" in data_comp["data_sources"]

print("\n--- PHẢN HỒI KỊCH BẢN PHẢN CÔNG TỪ QWEN3.5 4B ---")
print(data_comp["ai_response"])

print("\n" + "=" * 75)
print("🎉 HOÀN TẤT KIỂM THỬ E2E CHO CẢ 2 CHẾ ĐỘ!")
print("=" * 75)
