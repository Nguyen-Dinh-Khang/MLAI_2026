"""
distillation.py - Mắt xích 5: Bộ Chắt Lọc & Nén Token Trung Gian (Smart Distillation Engine)
Chức năng:
Dù tìm kiếm theo Tag hay theo Vector, dữ liệu trong CSDL có thể dài dòng, trùng lặp.
Tầng này thực hiện:
1. Bỏ văn phong kể lể: Chỉ giữ lại kết luận hành động (key_takeaway) và tóm tắt sự cố (summary).
2. Khử trùng lặp: Nếu nhiều bài cùng nói về 1 sự cố (ví dụ tăng giá thịt, chờ món lâu), tự gộp lại.
3. Xếp độ ưu tiên: Rủi ro HIGH (Mức 3) đưa lên trước, MEDIUM đưa xuống sau.
4. Tiết kiệm 80% Token: Nén toàn bộ dữ liệu thô thành các gạch đầu dòng cô đọng nhất trước khi nạp vào LLM.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class DistillationEngine:
    """Class chắt lọc dữ liệu cốt lõi, khử trùng lặp và định dạng prompt cho LLM."""

    @staticmethod
    def distill_records(search_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Tiếp nhận kết quả tìm kiếm thô từ DB3, DB4, DB5.
        Chắt lọc hạt nhân thông tin và trả về danh sách các bullet points súc tích.
        """
        problems = search_results.get("problems", [])
        experiences = search_results.get("experiences", [])
        market_segments = search_results.get("market_segments", [])

        # 1. Chắt lọc DB3: Sự cố vận hành
        distilled_problems = []
        seen_problem_titles = set()

        for p in problems:
            title = p.get("title", "").strip()
            title_key = title.lower()
            if title_key not in seen_problem_titles:
                seen_problem_titles.add(title_key)
                
                # Cắt ngắn summary nếu quá dài
                summary = p.get("summary", "")
                if len(summary) > 140:
                    summary = summary[:140].strip() + "..."

                # Chuẩn hóa mức độ nghiêm trọng: 3 -> HIGH, 2 -> MEDIUM, 1 -> LOW
                raw_sev = p.get("severity", 2)
                sev_map = {3: "HIGH", 2: "MEDIUM", 1: "LOW", "3": "HIGH", "2": "MEDIUM", "1": "LOW"}
                sev_label = sev_map.get(raw_sev, "MEDIUM")

                distilled_problems.append({
                    "title": title,
                    "severity": sev_label,
                    "summary": summary
                })

        # Sắp xếp Rủi ro theo độ nghiêm trọng: HIGH -> MEDIUM -> LOW
        severity_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        distilled_problems.sort(key=lambda x: severity_rank.get(x["severity"], 3))

        # 2. Chắt lọc DB4: Bài học thực chiến & Lời thoại
        distilled_lessons = []
        seen_lesson_titles = set()

        for exp in experiences:
            title = exp.get("title", "").strip()
            title_key = title.lower()
            if title_key not in seen_lesson_titles:
                seen_lesson_titles.add(title_key)
                
                # Ưu tiên lấy key_takeaway ngắn gọn thay vì đọc toàn bộ story dài dòng
                takeaway = exp.get("key_takeaway") or exp.get("story", "")
                if len(takeaway) > 160:
                    takeaway = takeaway[:160].strip() + "..."

                dialogue = exp.get("dialogue_script", "").strip()

                distilled_lessons.append({
                    "title": title,
                    "takeaway": takeaway,
                    "dialogue_script": dialogue
                })

        # 3. Chắt lọc DB5: Hành vi & Túi tiền thị trường
        distilled_market = []
        for m in market_segments:
            behavior = m.get("behavior_notes", "")
            if len(behavior) > 140:
                behavior = behavior[:140].strip() + "..."

            distilled_market.append({
                "segment": m.get("segment", "Khách hàng"),
                "budget": m.get("price_tolerance", "Chưa rõ"),
                "peak_hours": m.get("peak_traffic", "Chưa rõ"),
                "behavior": behavior
            })

        return {
            "problems": distilled_problems,
            "lessons": distilled_lessons,
            "market": distilled_market
        }

    @classmethod
    def build_llm_context(cls, distilled_data: Dict[str, Any]) -> str:
        """
        Ghép các bullet points đã chắt lọc thành đoạn văn bản Markdown súc tích cho LLM.
        """
        lines = []

        # Phần 1: Các sự cố đã kiểm chứng (DB3)
        lines.append("### DỮ LIỆU SỰ CỐ & RỦI RO THỰC TẾ (DB3):")
        if not distilled_data["problems"]:
            lines.append("- Không ghi nhận sự cố đặc thù tương tự.")
        else:
            for p in distilled_data["problems"]:
                lines.append(f"- [{p['severity']}] {p['title']}: {p['summary']}")

        # Phần 2: Bài học kinh nghiệm & Lời thoại (DB4)
        lines.append("\n### BÀI HỌC KINH NGHIỆM ĐÃ KIỂM CHỨNG (DB4):")
        if not distilled_data["lessons"]:
            lines.append("- Chưa có tiền lệ xử lý.")
        else:
            for l in distilled_data["lessons"]:
                script_part = f" => Lời thoại mẫu: \"{l['dialogue_script']}\"" if l.get("dialogue_script") else ""
                lines.append(f"- {l['title']}: {l['takeaway']}{script_part}")

        # Phần 3: Hành vi & Sức mua khách hàng (DB5)
        lines.append("\n### HÀNH VI & SỨC MUA KHÁCH HÀNG (DB5):")
        if not distilled_data["market"]:
            lines.append("- Tệp khách hàng chung quanh khu vực.")
        else:
            for m in distilled_data["market"]:
                lines.append(f"- Tệp {m['segment']} (Túi tiền: {m['budget']}, Giờ cao điểm: {m['peak_hours']}): {m['behavior']}")

        return "\n".join(lines)
