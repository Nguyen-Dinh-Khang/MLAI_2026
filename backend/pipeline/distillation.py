"""
distillation.py - Mắt xích 5: Bộ Chắt Lọc & Nén Token Trung Gian (Smart Distillation Engine)
Chức năng:
Dù tìm kiếm theo Tag hay theo Vector, dữ liệu trong CSDL có thể dài dòng, trùng lặp.
Tầng này thực hiện:
1. Bỏ văn phong kể lể: Chỉ giữ lại kết luận hành động (key_takeaway) và tóm tắt sự cố (summary).
2. Khử trùng lặp: Nếu nhiều bài cùng nói về 1 sự cố (ví dụ tăng giá thịt, chờ món lâu), tự gộp lại.
3. Xếp độ ưu tiên: Rủi ro HIGH (Mức 3) đưa lên trước, MEDIUM đưa xuống sau.
4. Tiết kiệm 80% Token: Nén toàn bộ dữ liệu thô thành các gạch đầu dòng cô đọng nhất trước khi nạp vào LLM.
5. Hỗ trợ đa nhánh: 
   - Nhánh Cạnh tranh (COMPETITIVE): Chắt lọc đồng thời DB2 (Đối thủ) + DB3 (Rủi ro) + DB4 (Kinh nghiệm) + DB5 (Thị trường)
   - Nhánh Nội bộ (INTERNAL): Chắt lọc DB3 (Sự cố) + DB4 (Bài học thực chiến)
"""

import logging
from typing import Dict, List, Any, Optional
from ..tag_manager import tag_manager

logger = logging.getLogger(__name__)


class DistillationEngine:
    """Class chắt lọc dữ liệu cốt lõi, khử trùng lặp và định dạng prompt cho LLM."""

    @staticmethod
    def distill_records(
        search_results: Dict[str, List[Dict[str, Any]]],
        competitors: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Tiếp nhận kết quả tìm kiếm thô từ DB3, DB4, DB5 (và tùy chọn DB2 đối thủ).
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

        # 3. Chắt lọc DB5: Hành vi & Túi tiền thị trường (Lọc theo Tag IDs)
        distilled_market = []
        for m in market_segments:
            behavior = m.get("demand") or m.get("behavior_notes", "")
            if len(behavior) > 140:
                behavior = behavior[:140].strip() + "..."

            # Lấy tên phân khúc khách hàng từ tag_ids (Mã 301 - 304) hoặc trường segment
            segment_name = m.get("segment")
            if not segment_name:
                for tid in m.get("tag_ids", []):
                    if 301 <= tid <= 304:
                        segment_name = tag_manager.get_tag_name(tid)
                        break
            if not segment_name:
                segment_name = "Khách hàng mục tiêu"

            # Lấy dải giá / ngân sách chi tiêu
            budget_str = m.get("price_tolerance")
            if not budget_str:
                pr = m.get("price_range")
                if isinstance(pr, dict) and "min" in pr and "max" in pr:
                    budget_str = f"{pr['min']:,}đ - {pr['max']:,}đ"
                else:
                    budget_str = "Chưa rõ"

            # Lấy khung giờ cao điểm
            peak_str = m.get("peak_traffic")
            if not peak_str:
                ph = m.get("peak_hours")
                if isinstance(ph, list) and ph:
                    peak_str = ", ".join(
                        f"{p.get('start', '')} - {p.get('end', '')}"
                        for p in ph if isinstance(p, dict) and p.get("start")
                    )
                else:
                    peak_str = "Chưa rõ"

            distilled_market.append({
                "segment": segment_name,
                "budget": budget_str,
                "peak_hours": peak_str,
                "behavior": behavior
            })

        # 4. Chắt lọc DB2: Đối thủ cạnh tranh trong 1km (nếu có)
        distilled_competitors = []
        if competitors:
            for c in competitors[:5]:  # Lấy 5 đối thủ tiêu biểu nhất
                name = c.get("name", "Quán lân cận")
                dist = round(c.get("distance_m", 0))
                price = c.get("price_range", "Chưa rõ")
                weakness = c.get("weakness", "Chưa có thông tin")
                distilled_competitors.append({
                    "name": name,
                    "distance_m": dist,
                    "price_range": price,
                    "weakness": weakness
                })

        return {
            "problems": distilled_problems,
            "lessons": distilled_lessons,
            "market": distilled_market,
            "competitors": distilled_competitors
        }

    @classmethod
    def build_llm_context(cls, distilled_data: Dict[str, Any], intent: str = "INTERNAL") -> str:
        """
        Ghép các bullet points đã chắt lọc thành đoạn văn bản Markdown súc tích cho LLM.
        Phân tách rõ ràng giữa chế độ Cạnh tranh (COMPETITIVE) và Nội bộ (INTERNAL).
        """
        lines = []

        # Nếu là nhánh Cạnh tranh: Đưa dữ liệu Đối thủ DB2 và Sức mua DB5 lên đầu
        if intent == "COMPETITIVE" and distilled_data.get("competitors"):
            lines.append("### ĐỐI THỦ CẠNH TRANH THỰC TẾ TRONG BÁN KÍNH 1KM (DB2):")
            for c in distilled_data["competitors"]:
                lines.append(f"- Quán '{c['name']}' (Cách {c['distance_m']}m, Giá: {c['price_range']}) => Điểm yếu bị khách chê: \"{c['weakness']}\"")
            lines.append("")

        # Dữ liệu Sự cố & Rủi ro (DB3)
        lines.append("### DỮ LIỆU SỰ CỐ & RỦI RO THỰC TẾ LIÊN QUAN (DB3):")
        if not distilled_data["problems"]:
            lines.append("- Không ghi nhận rủi ro đặc thù tương tự.")
        else:
            for p in distilled_data["problems"]:
                lines.append(f"- [{p['severity']}] {p['title']}: {p['summary']}")

        # Bài học kinh nghiệm & Lời thoại (DB4)
        lines.append("\n### BÀI HỌC KINH NGHIỆM ĐÃ KIỂM CHỨNG & LỜI THOẠI ĐÀM PHÁN (DB4):")
        if not distilled_data["lessons"]:
            lines.append("- Chưa có tiền lệ xử lý.")
        else:
            for l in distilled_data["lessons"]:
                script_part = f" => Lời thoại mẫu: \"{l['dialogue_script']}\"" if l.get("dialogue_script") else ""
                lines.append(f"- {l['title']}: {l['takeaway']}{script_part}")

        # Hành vi & Sức mua khách hàng (DB5)
        lines.append("\n### HÀNH VI & SỨC MUA KHÁCH HÀNG (DB5):")
        if not distilled_data["market"]:
            lines.append("- Tệp khách hàng chung quanh khu vực.")
        else:
            for m in distilled_data["market"]:
                lines.append(f"- Tệp {m['segment']} (Túi tiền: {m['budget']}, Giờ cao điểm: {m['peak_hours']}): {m['behavior']}")

        return "\n".join(lines)
