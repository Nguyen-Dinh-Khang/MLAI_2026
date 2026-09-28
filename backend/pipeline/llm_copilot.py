"""
llm_copilot.py - Mắt xích 6: Bộ Não Suy Luận Cố Vấn (Qwen3.5 4B qua Ollama)
Chức năng:
1. Kết nối với mô hình Qwen3.5 4B đang chạy cục bộ trên Ollama (cổng 11434).
2. Áp dụng System Prompt chuẩn thực chiến từ Mục 9 của SPEC:
   - Giọng điệu bình dân, trực diện, tuyệt đối không nói lý thuyết sáo rỗng.
   - Luôn đưa ra: Con số, Checklist 24h và Lời thoại đàm phán từng bước.
3. Hỗ trợ 2 chế độ:
   - Chế độ 1: Thẩm định Ý tưởng (Day 0) -> Bản báo cáo 4 khối.
   - Chế độ 2: Trợ lý Giải quyết Sự cố (Day 1 - 365) -> Kịch bản hành động 3 khối.
"""

import json
import logging
import requests
from typing import Dict, List, Any
from ..config import OLLAMA_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Bạn là Trợ lý Cố vấn Kinh doanh F&B và Bán lẻ thực chiến tại Việt Nam.
Phong cách trả lời: Trực diện, bình dân, nói thẳng vào hành động, tuyệt đối không nói lý thuyết sáo rỗng.

NGUYÊN TẮC HOẠT ĐỘNG BẮT BUỘC:
1. CĂN CỨ VÀO SỐ LIỆU ĐƯỢC GIAO: Chỉ lập luận trên dữ liệu đối thủ, nhân khẩu học và bài học trong CONTEXT. Tuyệt đối không bịa đặt số liệu sách vở.
2. NÓI RÕ CON SỐ & HÀNH ĐỘNG: Không khuyên chung chung kiểu "cần marketing", phải nói rõ "làm combo bánh mì + cafe 29k xuất đơn dưới 60 giây".
3. TRẢ LỜI ĐÚNG TRỌNG TÂM CẤU TRÚC:
   - Nếu là Thẩm định ý tưởng: Trả lời đủ 4 phần (1. Điểm khả thi /10 kèm 3 ưu thế & 3 cạm bẫy; 2. Phân tích đối thủ 1km; 3. Lỗ hổng thị trường; 4. Lời khuyên sống sót từ thử tải rủi ro).
   - Nếu là Trợ lý sự cố: Trả lời đủ 3 phần (1. Nguyên nhân cốt lõi; 2. Kịch bản hành động trong 24h kèm Checklist và Lời thoại mẫu; 3. Con số mục tiêu cần theo dõi).
"""


class LLMCopilot:
    """Class điều phối suy luận với mô hình Qwen3.5 4B qua Ollama."""

    def __init__(self):
        self.api_url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
        self.model = LLM_MODEL

    def _call_ollama(self, prompt: str, temperature: float = 0.3) -> str:
        """Gửi request tới Ollama HTTP API và nhận câu trả lời dạng text."""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_ctx": 12288  # Context window 12.288 tokens (gấp 3 lần 4096)
                }
            }
            logger.info(f"[*] Đang gửi prompt tới Ollama ({self.model})...")
            response = requests.post(self.api_url, json=payload, timeout=150)
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                logger.error(f"[!] Ollama trả về mã lỗi: {response.status_code} - {response.text}")
                return "Không thể kết nối với mô hình LLM Ollama. Vui lòng kiểm tra dịch vụ Ollama đang chạy."
        except requests.exceptions.RequestException as e:
            logger.error(f"[!] Lỗi khi gọi Ollama: {e}")
            return f"Lỗi kết nối tới mô hình AI: {e}"

    def evaluate_feasibility(
        self,
        form_data: Dict[str, Any],
        demographics: Dict[str, Any],
        competitors: List[Dict[str, Any]],
        market_gaps: Dict[str, Any],
        stress_test: Dict[str, Any]
    ) -> str:
        """
        Chế độ 1: Thẩm định Ý tưởng (Day 0)
        Tổng hợp kết quả từ 4 mắt xích và yêu cầu LLM viết bản thẩm định súc tích.
        """
        address = form_data.get("address", "")
        model_name = form_data.get("model_name", "")
        products_str = form_data.get("products_str", "")
        budget = form_data.get("budget", 0)
        rent = form_data.get("rent", 0)

        prompt = f"""Hãy thẩm định ý tưởng kinh doanh thực tế sau đây dựa hoàn toàn trên số liệu thực tế được cung cấp:

THÔNG TIN ĐẦU VÀO CỦA NGƯỜI DÙNG:
- Địa điểm dự kiến: {address}
- Mô hình: {model_name}
- Món dự kiến bán: {products_str}
- Số vốn hiện có: {budget:,.0f} VNĐ
- Tiền thuê mặt bằng dự kiến: {rent:,.0f} VNĐ/tháng

DỮ LIỆU ĐÃ TÍNH TOÁN TỪ HỆ THỐNG:
1. Dân cư khu vực (DB1): {demographics.get('name')} | Mật độ: {demographics.get('population_density'):,} người/km² | Khách chủ lực: {demographics.get('dominant_age')} | Thu nhập: {demographics.get('income_level')}
2. Đối thủ trong bán kính 1km (DB2): Có {len(competitors)} điểm bán tương tự. Giá phổ biến: {market_gaps.get('price_overview', [])}. Điểm yếu lớn nhất của đối thủ: {market_gaps.get('top_weaknesses', [])}
3. Lỗ hổng thị trường phát hiện được (DB5): {json.dumps(market_gaps.get('market_gaps', []), ensure_ascii=False)}
4. Kết quả Thử tải Dòng tiền (DB3):
   - Số tháng cầm cự an toàn (Runway): {stress_test.get('runway_months')} tháng.
   - Đánh giá sức sống vốn: {stress_test.get('survival_rating')}
   - Mức giá thuê mặt bằng tối đa cho phép: {stress_test.get('max_recommended_rent'):,.0f} VNĐ/tháng.
   - Cần bán tối thiểu: {stress_test.get('breakeven_orders_per_day')} đơn/ngày để hòa vốn.

YÊU CẦU TRẢ LỜI CỤ THỂ THEO 4 PHẦN:
### 1. ĐIỂM KHẢ THI TỔNG THỂ (Thang điểm 10)
- Cho điểm số cụ thể (ví dụ: 7.5/10).
- 3 Ưu thế then chốt nhất của ý tưởng này tại vị trí này.
- 3 Cạm bẫy dễ mất tiền nhất mà chủ quán cần tránh.

### 2. PHÂN TÍCH ĐỐI THỦ XUNG QUANH (BÁN KÍNH 1KM)
- Đánh giá mật độ cạnh tranh và điểm yếu của đối thủ mà quán có thể đè bẹp.

### 3. CHIẾN LƯỢC ĐÁNH VÀO LỖ HỔNG THỊ TRƯỜNG (MARKET GAP)
- Đề xuất cụ thể món/combo và mức giá mở bán để hớt trọn khách hàng của đối thủ.

### 4. LỜI KHUYÊN SỐNG SÒN TỪ BÀI TOÁN DÒNG TIỀN (STRESS-TEST)
- Khuyến nghị về giá thuê mặt bằng trần và số đơn cần đạt mỗi ngày để không phá sản.
"""
        return self._call_ollama(prompt, temperature=0.3)

    def answer_tactical_copilot(
        self,
        user_query: str,
        model_name: str,
        context_markdown: str
    ) -> str:
        """
        Chế độ 2: Trợ lý Giải quyết Sự cố Thực chiến (Day 1 - 365)
        Nhận câu hỏi thực tế và bài học CSDL đã nén để xuất kịch bản hành động 24h.
        """
        prompt = f"""Người dùng đang vận hành quán kinh doanh và gặp sự cố thực tế sau:

MÔ HÌNH QUÁN: {model_name or "Kinh doanh F&B / Bán lẻ"}
CÂU HỎI / SỰ CỐ CỦA CHỦ QUÁN:
"{user_query}"

BÀI HỌC VÀ DỮ LIỆU ĐÃ ĐƯỢC CHẮT LỌC TỪ CƠ SỞ DỮ LIỆU THỰC CHIẾN (DB3, DB4, DB5):
{context_markdown}

YÊU CẦU: Hãy vào vai một người anh đi trước dạn dày kinh nghiệm, hướng dẫn người dùng giải quyết dứt điểm sự cố này theo ĐÚNG 3 PHẦN:

### 1. NGUYÊN NHÂN CỐT LÕI (Từ thực tế kinh doanh)
(Chỉ rõ tại sao lại xảy ra tình trạng này dựa vào tâm lý khách hàng và dữ liệu thực tế, giải thích ngắn gọn trong 2-3 câu).

### 2. KỊCH BẢN HÀNH ĐỘNG NGAY TRONG 24H (Checklist việc cần làm)
(Viết dưới dạng checklist rõ ràng từng mốc giờ hoặc từng bước cụ thể người dùng có thể làm ngay ngày mai):
- [ ] Bước 1: ...
- [ ] Bước 2: ...
- [ ] Lời thoại mẫu đàm phán/nói chuyện (Ví dụ nói với nhân viên, chủ nhà hoặc khách hàng): Viết nguyên văn câu thoại ngắn gọn, thực tế.

### 3. CON SỐ MỤC TIÊU CẦN THEO DÕI
(Chỉ ra 1-2 con số cụ thể chủ quán cần đo lường để biết đã xử lý thành công, ví dụ: giảm thời gian xuất đơn xuống < 60s, tỷ lệ hao hụt nguyên liệu < 5%).
"""
        return self._call_ollama(prompt, temperature=0.25)
