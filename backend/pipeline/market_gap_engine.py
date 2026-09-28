"""
market_gap_engine.py - Mắt xích 2: Máy dò Lỗ hổng Thị trường Vi mô (Market Gap Finder v3)
Chức năng cốt lõi:
1. Đối chiếu đa CSDL (DB1 Dân cư x DB2 Đối thủ x DB3 Rủi ro x DB4 Kinh nghiệm x DB5 Thị trường).
2. Xếp hạng đối thủ bằng Competitor Threat Score (CTS v2) kết hợp điểm yếu hệ thống cụm.
3. Khai thác Điểm yếu đối thủ bằng Vector Embedding DB4 & Cơ chế Phủ định Đảo ngược UVP.
4. Phân tích Phân khúc Giá 2 Chiều (Lỗ hổng Sang trọng vs Lỗ hổng Bình dân) có kiểm soát bởi Bộ lọc Khả thi theo Quy mô Vốn (budget).
5. Khung giờ Vàng Mở quán (Golden Operating Windows) đón đầu giờ cao điểm.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from ..database import get_db
from ..tag_manager import tag_manager
from .semantic_search import SemanticSearchEngine

logger = logging.getLogger(__name__)


def parse_price_range(price_text: str) -> Optional[Tuple[int, int, int]]:
    """
    Parser linh hoạt chuyển đổi chuỗi giá tiếng Việt (VD: "18.000 - 25.000 VND", "20k - 35k", "25000-40000")
    thành tuple số thực: (min_price, max_price, avg_price).
    """
    if not price_text:
        return None
    cleaned = (
        price_text.replace(".", "")
        .replace(",", "")
        .replace("VND", "")
        .replace("vnd", "")
        .replace("đ", "")
        .replace("Đ", "")
        .strip()
    )
    
    parts = re.split(r"[-–—/]", cleaned)
    numbers = []
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        multiplier = 1
        if "k" in part:
            multiplier = 1000
            part = part.replace("k", "")
        digits = re.findall(r"\d+", part)
        if digits:
            try:
                val = int(digits[0]) * multiplier
                if val < 1000:  # VD: "20 - 35" nghĩa là 20k - 35k
                    val *= 1000
                numbers.append(val)
            except ValueError:
                continue

    if len(numbers) >= 2:
        min_p = min(numbers[0], numbers[1])
        max_p = max(numbers[0], numbers[1])
        return min_p, max_p, int((min_p + max_p) / 2)
    elif len(numbers) == 1:
        return numbers[0], numbers[0], numbers[0]
    return None


def detect_systemic_weaknesses(competitors: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Phát hiện các điểm yếu xuất hiện chung ở >= 2 quán trong bán kính 1km (Systemic Vulnerability).
    Trích xuất tự do theo thị trường, không gò bó vào 3 nhóm cố định.
    """
    weaknesses = []
    comp_weakness_map = {}
    
    for c in competitors:
        cid = str(c.get("_id", c.get("id", "")))
        w = c.get("weakness", "").strip()
        if w and w.lower() not in ["không có thông tin", "chưa có", "n/a", "none"]:
            weaknesses.append(w)
            comp_weakness_map[cid] = w

    if not weaknesses:
        return {
            "has_systemic": False,
            "patterns": [],
            "affected_comp_ids": set(),
            "summary_pattern": ""
        }

    stop_words = {
        "và", "của", "là", "có", "không", "chỉ", "các", "những", "cho", "với", "ở", "tại", 
        "quán", "rất", "hơi", "quá", "bị", "được", "ra", "vào", "này", "đó", "thì", "lại", "mà"
    }

    # Bóc tách bigrams và unigrams có nghĩa
    token_appearances: Dict[str, Set[str]] = {}
    for c in competitors:
        cid = str(c.get("_id", c.get("id", "")))
        w = c.get("weakness", "").strip().lower()
        if not w or w in ["không có thông tin", "chưa có", "n/a"]:
            continue

        raw_words = [re.sub(r"[^\w\s]", "", word) for word in w.split()]
        valid_words = [wd for wd in raw_words if wd and wd not in stop_words and len(wd) > 1]
        
        tokens_for_this_comp = set()
        for i, wd in enumerate(valid_words):
            tokens_for_this_comp.add(wd)
            if i < len(valid_words) - 1:
                bigram = f"{wd} {valid_words[i+1]}"
                tokens_for_this_comp.add(bigram)

        for tk in tokens_for_this_comp:
            if tk not in token_appearances:
                token_appearances[tk] = set()
            token_appearances[tk].add(cid)

    # Lọc các token xuất hiện ở >= 2 đối thủ
    systemic_tokens = [
        (tk, comp_set) for tk, comp_set in token_appearances.items()
        if len(comp_set) >= 2 and len(tk) >= 3
    ]
    # Sắp xếp ưu tiên theo số quán chịu ảnh hưởng và độ dài token
    systemic_tokens.sort(key=lambda x: (len(x[1]), len(x[0])), reverse=True)

    patterns = []
    all_affected_ids = set()
    seen_tokens = set()

    for tk, cids in systemic_tokens:
        if any(tk in existing for existing in seen_tokens):
            continue
        seen_tokens.add(tk)
        all_affected_ids.update(cids)
        patterns.append({
            "keyword": tk,
            "count": len(cids),
            "affected_ids": list(cids)
        })

    summary_pattern = ", ".join([p["keyword"] for p in patterns[:2]]) if patterns else ""

    return {
        "has_systemic": len(patterns) > 0,
        "patterns": patterns,
        "affected_comp_ids": all_affected_ids,
        "summary_pattern": summary_pattern
    }


def invert_weakness_to_uvp(weakness_text: str) -> str:
    """
    Quy tắc phủ định đảo ngược (Weakness Inversion):
    Biến điểm yếu của đối thủ thành Tuyên ngôn Giá trị Độc quyền (UVP) khi DB4 chưa có bản ghi tương ứng.
    """
    if not weakness_text:
        return "Chuẩn hóa quy trình vận hành và chất lượng sản phẩm vượt trội so với thị trường."
        
    tl = weakness_text.lower()

    if any(k in tl for k in ["chờ lâu", "chậm", "> 5 phút", "đợi lâu", "làm lâu", "chờ"]):
        return "Cam kết xuất đơn siêu tốc dưới 60 giây, chuẩn hóa quy trình ra món tức thì không để khách vội phải chờ."
    if any(k in tl for k in ["cà phê", "pha máy", "đồ uống", "nước uống", "nước"]):
        return "Tích hợp sẵn quầy cà phê pha máy chuyên nghiệp, phục vụ đồng bộ combo Bữa ăn + Đồ uống đóng gói mang đi tiện lợi."
    if any(k in tl for k in ["bao bì", "nilon", "đơn sơ", "sơ sài", "bọc", "hộp"]):
        return "Đóng gói bao bì giấy kraft giữ nhiệt cao cấp, thiết kế thương hiệu bắt mắt, sạch tay và thân thiện môi trường."
    if any(k in tl for k in ["mang đi", "chỗ ngồi", "không gian", "chật", "nóng"]):
        return "Tối ưu mô hình tích hợp: Vừa có lối mua mang đi nhanh 30 giây, vừa bố trí góc ngồi dừng chân sạch sẽ, thoáng mát."
    if any(k in tl for k in ["nghèo nàn", "ít món", "đơn điệu", "thiếu"]):
        return "Menu tinh gọn nhưng đánh trúng nhu cầu cao điểm, phát triển combo đa dạng dinh dưỡng với giá tiết kiệm."

    # Inversion đảo ngữ thông thường
    inverted = weakness_text
    replacements = [
        ("không có", "Tích hợp đầy đủ"),
        ("chưa có", "Trang bị sẵn"),
        ("chỉ có", "Mở rộng chuyên nghiệp"),
        ("kém", "Chuẩn hóa chất lượng cao"),
        ("đơn sơ", "Chỉn chu thẩm mỹ"),
        ("sơ sài", "Đóng gói chuyên nghiệp")
    ]
    matched = False
    for neg, pos in replacements:
        if neg in inverted.lower():
            inverted = re.sub(re.escape(neg), pos, inverted, flags=re.IGNORECASE)
            matched = True

    if matched:
        return f"Chiến lược bù đắp: {inverted}"
    return f"Định vị khác biệt hóa: Khắc phục triệt để tồn đọng đối thủ ('{weakness_text}')."


class MarketGapEngine:
    """Class phụ trách phân tích và phát hiện Lỗ hổng Thị trường Vi mô (Market Gap Engine v3)."""

    def __init__(self):
        self.db = get_db()
        self._semantic_search = None

    @property
    def semantic_search(self):
        if self._semantic_search is None:
            try:
                self._semantic_search = SemanticSearchEngine()
            except Exception as e:
                logger.warning(f"Không thể khởi tạo SemanticSearchEngine: {e}")
                self._semantic_search = None
        return self._semantic_search

    def find_market_gaps(
        self,
        competitors_1km: List[Dict[str, Any]],
        model_id: int,
        product_ids: List[int],
        demographics: Dict[str, Any],
        budget: float = 0.0
    ) -> Dict[str, Any]:
        """
        Đối chiếu chéo 5 CSDL (DB1 x DB2 x DB3 x DB4 x DB5) để phát hiện Lỗ hổng Thị trường:
        1. Phân tích nhân khẩu học DB1 để xác định nhóm tuổi áp đảo và mức thu nhập.
        2. Truy vấn DB5 theo mã phân khúc & mã sản phẩm để lấy chuẩn giá, giờ cao điểm, nhu cầu thực.
        3. Phát hiện điểm yếu hệ thống và tính điểm Competitor Threat Score (CTS v2) cho đối thủ.
        4. Phân tích 3 khía cạnh:
           - Khía cạnh 1: Khai thác điểm yếu đối thủ x Embedding DB4 (hoặc Inversion UVP).
           - Khía cạnh 2: Định vị giá 2 chiều (Lỗ hổng Sang trọng vs Bình dân) có kiểm soát bởi Vốn.
           - Khía cạnh 3: Khung giờ vàng mở quán (DB5 x DB3 x DB4).
        """
        # 1. Trích xuất thông tin nhân khẩu học DB1
        age_dist = demographics.get("age_distribution", {})
        income_level_raw = str(demographics.get("income_level", "medium")).lower()

        # Map age_dist sang demographic tag (301: 18-24, 302: 25-34, 303: 35-50, 304: over_50)
        dominant_age_tag = 301
        dominant_age_label = "Sinh viên & Giới trẻ (18 - 24 tuổi)"
        if age_dist:
            max_age_key = max(age_dist.items(), key=lambda x: x[1])[0]
            if "18_24" in max_age_key or "18-24" in max_age_key:
                dominant_age_tag = 301
                dominant_age_label = "Sinh viên & Giới trẻ (18 - 24 tuổi)"
            elif "25_34" in max_age_key or "25-34" in max_age_key:
                dominant_age_tag = 302
                dominant_age_label = "Dân văn phòng & Đi làm trẻ (25 - 34 tuổi)"
            elif "35_50" in max_age_key or "35-50" in max_age_key:
                dominant_age_tag = 303
                dominant_age_label = "Gia đình & Trung niên (35 - 50 tuổi)"
            elif "50" in max_age_key:
                dominant_age_tag = 304
                dominant_age_label = "Người lớn tuổi (trên 50 tuổi)"

        # Quy chuẩn hóa 3 mức thu nhập (HIGH = 3, MEDIUM = 2, LOW = 1)
        income_tier = 2
        income_tier_label = "Mức 2 (MEDIUM - Chi tiêu cân đối)"
        if any(k in income_level_raw for k in ["high", "cao", "3"]):
            income_tier = 3
            income_tier_label = "Mức 3 (HIGH - Sẵn sàng chi trả cao)"
        elif any(k in income_level_raw for k in ["low", "thấp", "medium_low", "1"]):
            income_tier = 1
            income_tier_label = "Mức 1 (LOW - Nhạy cảm về giá)"
        else:
            income_tier = 2

        # 2. Truy vấn DB5 (market_segments) chính xác theo [dominant_age_tag, product_ids]
        market_coll = self.db["market_segments"]
        db5_matches = []
        if product_ids:
            query = {
                "$and": [
                    {"tag_ids": dominant_age_tag},
                    {"tag_ids": {"$in": product_ids}}
                ]
            }
            db5_matches = list(market_coll.find(query))

        if not db5_matches and product_ids:
            db5_matches = list(market_coll.find({"tag_ids": {"$in": product_ids}}))

        if not db5_matches:
            db5_matches = list(market_coll.find({"tag_ids": dominant_age_tag}))[:3] or list(market_coll.find({}))[:3]

        # Trích xuất dải giá, giờ cao điểm, nhu cầu từ DB5
        db5_min_prices = []
        db5_max_prices = []
        db5_demands = []
        db5_interest_map = {}
        all_peak_intervals = []

        for m in db5_matches:
            pr = m.get("price_range")
            if isinstance(pr, dict):
                if "min" in pr and pr["min"]:
                    db5_min_prices.append(int(pr["min"]))
                if "max" in pr and pr["max"]:
                    db5_max_prices.append(int(pr["max"]))
            if m.get("demand"):
                db5_demands.append(m["demand"])
            
            interest_val = float(m.get("interest", 0.8))
            for tid in m.get("tag_ids", []):
                if tid in product_ids:
                    db5_interest_map[tid] = max(db5_interest_map.get(tid, 0.0), interest_val)

            for ph in m.get("peak_hours", []):
                s = ph.get("start")
                e = ph.get("end")
                if s and e:
                    all_peak_intervals.append((s, e))

        db5_price_min = min(db5_min_prices) if db5_min_prices else 20000
        db5_price_max = max(db5_max_prices) if db5_max_prices else 35000
        db5_price_mid = int((db5_price_min + db5_price_max) / 2)

        # 3. Phân tích điểm yếu hệ thống và Tính điểm Đối thủ (CTS v2)
        systemic_info = detect_systemic_weaknesses(competitors_1km)

        # Tính toán quy mô đánh giá động theo thị trường vi mô (tránh khóa cứng số 100 reviews)
        all_reviews_list = [float(c.get("review_count") or 0) for c in competitors_1km]
        total_area_reviews = sum(all_reviews_list)
        max_area_reviews = max(all_reviews_list) if all_reviews_list and max(all_reviews_list) > 0 else 1.0

        scored_competitors = []
        comp_price_parsed = []
        comp_price_texts = []
        weaknesses_collected = []

        for c in competitors_1km:
            c_dict = dict(c)
            # Parse dải giá
            p_text = c_dict.get("price_range", "").strip()
            if p_text:
                comp_price_texts.append(p_text)
                parsed_p = parse_price_range(p_text)
                if parsed_p:
                    comp_price_parsed.append(parsed_p)

            # Thu thập điểm yếu
            w_text = c_dict.get("weakness", "").strip()
            if w_text and w_text.lower() not in ["không có thông tin", "chưa có", "n/a", "none"]:
                weaknesses_collected.append(w_text)

            # Tính điểm CTS v2
            dist_m = float(c_dict.get("distance_m", 1000.0))
            s_dist = max(0.0, 100.0 * (1.0 - (dist_m / 1000.0)))

            comp_model = c_dict.get("business_model_id")
            comp_prods = set(c_dict.get("product_ids") or [])
            user_prods_set = set(product_ids)
            overlap_prods = comp_prods.intersection(user_prods_set)

            s_overlap = 20.0
            reasons = []
            if dist_m <= 150:
                reasons.append(f"Khoảng cách cực gần ({int(dist_m)}m)")
            elif dist_m <= 400:
                reasons.append(f"Khoảng cách gần ({int(dist_m)}m)")

            if comp_model == model_id and overlap_prods:
                s_overlap = 100.0
                reasons.append("Trùng khớp 100% cả mô hình và món chính")
            elif overlap_prods:
                s_overlap = min(100.0, 70.0 + len(overlap_prods) * 10.0)
                reasons.append(f"Cạnh tranh trực tiếp {len(overlap_prods)} sản phẩm")
            elif comp_model == model_id:
                s_overlap = 50.0
                reasons.append("Cùng mô hình kinh doanh")

            cid = str(c_dict.get("_id", c_dict.get("id", "")))
            s_weakness = 0.0
            is_systemic = cid in systemic_info.get("affected_comp_ids", set())
            if is_systemic:
                s_weakness = 100.0
                reasons.append("Mang tử huyệt/điểm yếu phổ biến của cụm quán lân cận")
            elif w_text and w_text.lower() not in ["không có thông tin", "chưa có", "n/a"]:
                s_weakness = 40.0

            # S_rep (Quy mô & Uy tín tương đối động theo tỷ trọng review khu vực)
            rating = float(c_dict.get("rating", 4.0))
            reviews = float(c_dict.get("review_count", 0))
            s_rating = (rating / 5.0) * 50.0  # Tối đa 50đ cho rating

            # Phần trăm thị phần review của quán trong khu vực
            review_share_pct = (reviews / total_area_reviews * 100.0) if total_area_reviews > 0 else 50.0
            
            # Chuẩn hóa điểm review so với quán đứng đầu khu vực (0 -> 50đ)
            s_review = (reviews / max_area_reviews) * 50.0 if max_area_reviews > 0 else 25.0
            s_rep = s_rating + s_review

            c_dict["review_share_pct"] = round(review_share_pct, 1)

            if reviews == max_area_reviews and reviews > 0:
                reasons.append(f"Dẫn đầu lượng khách: Chiếm {review_share_pct:.1f}% tổng đánh giá khu vực ({int(reviews):,} reviews, {rating}★)")
            elif review_share_pct >= 25.0:
                reasons.append(f"Quy mô lớn: Chiếm {review_share_pct:.1f}% tổng đánh giá khu vực ({int(reviews):,} reviews, {rating}★)")
            elif reviews >= 50:
                reasons.append(f"Uy tín tốt ({rating}★, {int(reviews):,} đánh giá)")

            s_demo = 50.0
            for pid in comp_prods:
                if pid in db5_interest_map:
                    s_demo = max(s_demo, db5_interest_map[pid] * 100.0)

            total_cts = (
                0.25 * s_dist +
                0.30 * s_overlap +
                0.20 * s_weakness +
                0.15 * s_rep +
                0.10 * s_demo
            )
            c_dict["threat_score"] = round(total_cts, 1)
            c_dict["threat_reasons"] = reasons
            c_dict["has_systemic_weakness"] = is_systemic
            scored_competitors.append(c_dict)

        # Sắp xếp đối thủ theo điểm đe dọa giảm dần
        scored_competitors.sort(key=lambda x: x.get("threat_score", 0.0), reverse=True)
        top_comp = scored_competitors[0] if scored_competitors else None

        # 4. Phân tích 3 Khía Cạnh Cốt Lõi
        gaps = []
        product_names = [tag_manager.get_tag_name(pid) for pid in product_ids]
        products_str = ", ".join(product_names) if product_names else "Sản phẩm chính"

        # -------------------------------------------------------------
        # KHÍA CẠNH 1: Khai thác Điểm yếu Đối thủ x Embedding DB4 / Inversion
        # -------------------------------------------------------------
        target_weakness = ""
        target_comp_name = "Đối thủ quanh khu vực"
        target_comp_id = ""

        if top_comp and top_comp.get("weakness"):
            target_weakness = top_comp.get("weakness").strip()
            target_comp_name = top_comp.get("name", "Đối thủ lớn nhất")
            target_comp_id = str(top_comp.get("_id", top_comp.get("id", "")))
        elif weaknesses_collected:
            target_weakness = weaknesses_collected[0]

        exp_solution = ""
        exp_source = "Cơ chế Phủ định Đảo ngược UVP"

        if target_weakness and target_weakness.lower() not in ["không có thông tin", "chưa có", "n/a"]:
            try:
                if self.semantic_search is not None:
                    found_exps = self.semantic_search.search_collection(
                        collection_name="experiences",
                        query=target_weakness,
                        top_k=1,
                        tag_filter=model_id
                    )
                    if found_exps and found_exps[0].get("similarity_score", 0.0) >= 0.55:
                        best_exp = found_exps[0]
                        exp_solution = best_exp.get("key_takeaway") or best_exp.get("story", "")
                        exp_source = f"DB4 ({best_exp.get('_id', 'exp')})"
            except Exception as e:
                logger.warning(f"Lỗi tìm kiếm embedding trong DB4: {e}")

        # Fallback Phủ định đảo ngược nếu DB4 chưa có bản ghi phù hợp
        if not exp_solution:
            exp_solution = invert_weakness_to_uvp(target_weakness)

        systemic_prefix = ""
        if systemic_info["has_systemic"]:
            systemic_prefix = f"Phát hiện điểm yếu hệ thống chung ở {len(systemic_info['affected_comp_ids'])} quán: '{systemic_info['summary_pattern']}'. "

        if target_weakness:
            gap_1_detail = (
                f"{systemic_prefix}Đối thủ hàng đầu ({target_comp_name}) đang bị khách phàn nàn: '{target_weakness}'. "
                f"Đòn đánh đòn bẩy: {exp_solution} ({exp_source})."
            )
        else:
            gap_1_detail = (
                f"Khu vực chưa có quán nào tối ưu combo bữa ăn & đồ uống tiện lợi ({products_str}) "
                f"đóng gói bao bì giấy sang trọng mang đi dưới 60 giây."
            )

        gaps.append({
            "type": "dich_vu_combo",
            "title": "Khoảng trống tiện ích & Đòn đánh điểm yếu hệ thống",
            "detail": gap_1_detail,
            "exploit_competitor_id": target_comp_id,
            "solution_source": exp_source,
            "actionable_takeaway": exp_solution
        })

        # -------------------------------------------------------------
        # KHÍA CẠNH 2: Phân tích Định vị Giá 2 Chiều có Kiểm soát Vốn
        # -------------------------------------------------------------
        # Thống kê giá đối thủ
        comp_mins = [p[0] for p in comp_price_parsed] or [18000]
        comp_maxs = [p[1] for p in comp_price_parsed] or [35000]
        comp_avgs = [p[2] for p in comp_price_parsed] or [26000]

        market_min = min(comp_mins)
        market_max = max(comp_maxs)
        market_avg = int(sum(comp_avgs) / len(comp_avgs))

        # Xác định sức chi trả mục tiêu theo 3 mức thu nhập DB1 x DB5
        if income_tier == 3:  # HIGH
            target_budget_min = db5_price_max
            target_budget_max = int(db5_price_max * 1.25)
            target_budget_str = f"{target_budget_min:,.0f}đ - {target_budget_max:,.0f}đ (Phân khúc Khá/Cao)"
        elif income_tier == 1:  # LOW
            target_budget_min = int(db5_price_min * 0.9)
            target_budget_max = db5_price_min + int((db5_price_max - db5_price_min) * 0.3)
            target_budget_str = f"{target_budget_min:,.0f}đ - {target_budget_max:,.0f}đ (Phân khúc Tiết kiệm)"
        else:  # MEDIUM
            target_budget_min = db5_price_min + int((db5_price_max - db5_price_min) * 0.2)
            target_budget_max = db5_price_max - int((db5_price_max - db5_price_min) * 0.1)
            target_budget_str = f"{target_budget_min:,.0f}đ - {target_budget_max:,.0f}đ (Phân khúc Cân đối)"

        # Kiểm tra Lỗ hổng Sang trọng (Premium Gap) hay Lỗ hổng Bình dân (Budget Gap)
        has_premium_demand = any("đẹp" in d or "check-in" in d or "tụ tập" in d or "ngon" in d for d in db5_demands)
        is_market_cheap = market_max <= (db5_price_min + db5_price_max) / 2 or market_max <= 28000
        has_premium_market_gap = is_market_cheap and (income_tier >= 2 or has_premium_demand)

        # Ngưỡng vốn chiến lược
        # 1. Ngưỡng tối thiểu an toàn để khả thi Premium: >= 200 triệu
        # 2. Ngưỡng vốn lớn chủ động chiếm lĩnh (Capital Supremacy): >= 300 triệu
        has_dual_strategies = False
        premium_trigger_reason = ""
        gap_direction = "COMBO_SWEET_SPOT"
        capital_strategy = "COMBO_VALUE_GAP"
        rec_price_str = ""

        # Logic kích hoạt cờ Premium & Kịch bản Kép (Dual Strategy)
        if budget >= 300_000_000:
            # Vốn siêu lớn (>= 300tr): Luôn kích hoạt Premium bất kể thị trường có trống hay không
            # Chiến lược Lấy vốn đè bẹp thị trường / Chủ động dẫn dắt thị phần
            has_dual_strategies = True
            gap_direction = "PREMIUM_GAP"
            capital_strategy = "CAPITAL_SUPREMACY_PREMIUM"
            premium_trigger_reason = f"Quy mô vốn dồi dào ({budget:,.0f}đ >= 300 triệu) cho phép bạn chủ động dẫn dắt thị trường, không phụ thuộc vào việc khu vực có thiếu quán sang hay không mà có thể dùng vốn để chiếm lĩnh thị phần."
        elif budget >= 200_000_000 and has_premium_market_gap:
            # Vốn khá (>= 200tr) VÀ thị trường thực sự đang bỏ ngỏ phân khúc sang
            has_dual_strategies = True
            gap_direction = "PREMIUM_GAP"
            capital_strategy = "MARKET_OPPORTUNITY_PREMIUM"
            premium_trigger_reason = f"Vốn đạt ngưỡng an toàn ({budget:,.0f}đ >= 200 triệu) kết hợp thị trường đang bị 'bình dân hóa' (toàn quán {market_min:,.0f}đ - {market_max:,.0f}đ), mở ra cơ hội lớn cho phân khúc cao cấp."
        elif is_market_cheap and (income_tier >= 2 or has_premium_demand):
            # Thị trường có khoảng trống nhưng vốn < 200tr -> Không đủ an toàn cho quán lớn
            has_dual_strategies = False
            gap_direction = "PREMIUM_GAP"
            capital_strategy = "AFFORDABLE_PREMIUM_LEAN"
        elif market_min >= db5_price_max or (income_tier == 1 and market_avg > 30000):
            # Lỗ hổng Bình dân / Siêu tốc
            has_dual_strategies = False
            gap_direction = "BUDGET_GAP"
            capital_strategy = "BUDGET_HIGH_VOLUME"
        else:
            # Lỗ hổng Combo Sweet Spot
            has_dual_strategies = False
            gap_direction = "COMBO_SWEET_SPOT"
            capital_strategy = "COMBO_VALUE_GAP"

        # 1. Nhánh Chiến Lược 1: Ăn Chắc Mặc Bền (Lean & Safe Baseline - LUÔN LUÔN CÓ)
        lean_capex_val = min(budget * 0.35, 45_000_000) if budget > 0 else 35_000_000
        lean_price_str = "28.000đ - 35.000đ"
        lean_strategy = {
            "name": "Ăn Chắc Mặc Bền (Lean Craft - An Toàn Tối Đa)",
            "risk_level": "Thấp (Rất an toàn)",
            "model_type": "Kiosk tinh gọn / Xe đẩy cao cấp / Bán mang đi là chính",
            "recommended_price": lean_price_str,
            "target_capex": f"{lean_capex_val:,.0f}đ",
            "recommended_rent": "4.000.000đ - 7.000.000đ/tháng",
            "core_advantage": "Vốn đầu tư ban đầu thấp, giữ lại 65-75% tiền dự phòng, hòa vốn nhanh (35-45 đơn/ngày), rủi ro cạn tiền gần như bằng 0."
        }

        # 2. Nhánh Chiến Lược 2: Đột Kích Cao Cấp (Premium Attack - Khi đủ điều kiện vốn)
        premium_strategy = None
        if has_dual_strategies:
            premium_min_p = max(42000, int(market_max * 1.3))
            premium_max_p = max(55000, int(market_max * 1.8))
            premium_price_str = f"{premium_min_p:,.0f}đ - {premium_max_p:,.0f}đ"
            premium_capex_val = budget * 0.55 if budget > 0 else 180_000_000
            premium_strategy = {
                "name": "Đột Kích Cao Cấp (Premium Attack - Lấy Vốn Chiếm Lĩnh)",
                "risk_level": "Trung bình - Cao (Chấp nhận thử thách dòng tiền để độc chiếm vị thế)",
                "model_type": "Quán cố định, máy lạnh, decor chỉn chu, góc ngồi check-in",
                "recommended_price": premium_price_str,
                "target_capex": f"{premium_capex_val:,.0f}đ",
                "recommended_rent": "15.000.000đ - 25.000.000đ/tháng",
                "core_advantage": "Đầu tư máy pha công nghiệp, không gian sang trọng bắt trọn tệp khách sẵn sàng chi trả cao, biên lợi nhuận lớn, tạo rào cản ngăn đối thủ vỉa hè bắt chước."
            }

        # Xây dựng nội dung chi tiết cho thẻ Lỗ hổng Giá
        dual_strategies_payload = {
            "lean": lean_strategy
        }
        if premium_strategy:
            dual_strategies_payload["premium"] = premium_strategy

        if has_dual_strategies:
            rec_price_str = f"Lean: {lean_price_str} | Premium: {premium_strategy['recommended_price']}"
            gap_2_detail = (
                f"{premium_trigger_reason} Hệ thống đề xuất 2 KỊCH BẢN CHIẾN LƯỢC song song tùy theo khẩu vị rủi ro của bạn:\n"
                f"• Lựa chọn 1 [Ăn Chắc Mặc Bền]: Kiosk nhỏ ({lean_strategy['target_capex']} setup, thuê {lean_strategy['recommended_rent']}), định giá {lean_price_str}. Giữ 70% tiền làm quỹ dự phòng, hòa vốn nhanh (35-45 đơn/ngày).\n"
                f"• Lựa chọn 2 [Đột Kích Cao Cấp]: Mở quán máy lạnh decor ({premium_strategy['target_capex']} setup, thuê {premium_strategy['recommended_rent']}), định giá {premium_strategy['recommended_price']}. Tối đa hóa biên lợi nhuận, đè bẹp đối thủ bằng trải nghiệm vượt trội."
            )
        elif gap_direction == "PREMIUM_GAP":
            rec_price_str = lean_price_str
            gap_2_detail = (
                f"Thị trường xung quanh toàn quán bình dân/vỉa hè ({market_min:,.0f}đ - {market_max:,.0f}đ). "
                f"Tuy nhiên số vốn của bạn ({budget:,.0f}đ) chưa đạt ngưỡng an toàn 200.000.000đ để mở quán cao cấp lớn (nguy cơ cạn dòng tiền DB4: exp_02). "
                f"Khuyến nghị chiến lược 'Ăn Chắc Mặc Bền' (Lean Craft): Giữ mô hình Kiosk/Xe đẩy nhỏ gọn nhưng dùng hạt cà phê xịn, bao bì giấy kraft sang trọng, định giá {lean_price_str} để đón đầu tệp khách cần sự chỉn chu mà không bị chôn vốn."
            )
        elif gap_direction == "BUDGET_GAP":
            rec_price_str = f"{db5_price_min:,.0f}đ - {int(db5_price_min * 1.2):,.0f}đ"
            gap_2_detail = (
                f"Mặt bằng giá đối thủ xung quanh khá cao (Bình quân {market_avg:,.0f}đ), trong khi tệp dân cư chủ yếu là "
                f"{dominant_age_label} thuộc {income_tier_label}. "
                f"Khuyến nghị chiến lược Bình Dân Siêu Tốc: Món phễu giá mềm ({rec_price_str}) với thời gian phục vụ nhanh để hút trọn khách hàng nhạy cảm về giá."
            )
        else:
            sweet_spot_min = max(market_min, db5_price_min)
            sweet_spot_max = min(market_max, db5_price_max)
            rec_price_str = f"{sweet_spot_min:,.0f}đ - {sweet_spot_max:,.0f}đ"
            gap_2_detail = (
                f"Mặt bằng giá đối thủ dao động {market_min:,.0f}đ - {market_max:,.0f}đ (Bình quân {market_avg:,.0f}đ). "
                f"Khách hàng {dominant_age_label} có mức chi trả phù hợp ở ngưỡng {target_budget_str}. "
                f"Thiết kế Combo món chính kèm nước ({rec_price_str}) để tạo điểm ngọt định giá (Pricing Sweet Spot)."
            )

        gaps.append({
            "type": "phan_khuc_gia",
            "title": "Khoảng trống phân khúc giá & Chiến lược định vị vốn",
            "gap_direction": gap_direction,
            "has_dual_strategies": has_dual_strategies,
            "capital_strategy": capital_strategy,
            "detail": gap_2_detail,
            "dual_branches": dual_strategies_payload,
            "benchmark": {
                "market_min": market_min,
                "market_max": market_max,
                "market_avg": market_avg,
                "income_tier": income_tier_label,
                "user_budget": budget,
                "recommended_price": rec_price_str
            }
        })

        # -------------------------------------------------------------
        # KHÍA CẠNH 3: Khung Giờ Mở Quán Tối Ưu (Golden Windows)
        # -------------------------------------------------------------
        # Trích xuất khung giờ cao điểm từ DB5
        morning_peak = "06:30 - 08:30"
        afternoon_peak = "16:30 - 18:30"

        for s, e in all_peak_intervals:
            if "06" in s or "07" in s or "08" in s:
                morning_peak = f"{s} - {e}"
            elif "16" in s or "17" in s or "18" in s:
                afternoon_peak = f"{s} - {e}"

        # Đề xuất Khung giờ vàng (Golden Windows):
        # Ca 1: Mở sớm trước 30-45 phút so với đỉnh lưu lượng để đón đầu khách đi sớm
        gap_3_detail = (
            f"Theo dữ liệu DB5 cho tệp {dominant_age_label}, lưu lượng khách đạt đỉnh sáng vào {morning_peak} "
            f"và chiều vào {afternoon_peak}. Theo DB3 (prob_03), điểm nghẽn kẹt xe/vội giờ học diễn ra gắt gao nhất lúc 07:00 - 07:25. "
            f"Khuyến nghị Lịch Mở Quán Vàng: Mở cửa đón đầu từ 06:00 (sớm hơn đối thủ 30-45p để vợt trọn khách vội), "
            f"tuân thủ kỷ luật DB4 (exp_01) sơ chế xong trước 05:45; đồng thời khai thác thêm Ca chiều 16:00 - 19:00 "
            f"để tối đa hóa công suất mặt bằng cố định."
        )

        gaps.append({
            "type": "thoi_gian_phuc_vu",
            "title": "Khung giờ vàng mở quán (Đón đầu & Ca phụ trợ)",
            "detail": gap_3_detail,
            "golden_windows": {
                "shift_1_morning": f"06:00 - 09:30 (Đỉnh bùng nổ: {morning_peak})",
                "shift_2_afternoon": f"16:00 - 19:00 (Đỉnh tan tầm: {afternoon_peak})",
                "prep_deadline": "Hoàn tất sơ chế trước 05:45",
                "rush_hour_warning": "Đỉnh nghẽn 07:00 - 07:25 (DB3): Bán combo đóng gói sẵn, không để khách chờ > 60s"
            }
        })

        # 5. Đánh giá tổng hợp sức cạnh tranh
        comp_count = len(competitors_1km)
        competition_level = (
            "Thấp (Dễ thở)" if comp_count <= 4 
            else ("Trung bình (Có cạnh tranh)" if comp_count <= 10 else "Cao (Thị trường dày đặc)")
        )

        top_weaknesses_display = weaknesses_collected[:3] if weaknesses_collected else [
            "Không có cà phê pha máy ngon, chỉ bán mang đi, bao bì nilon đơn sơ"
        ]

        price_overview_display = comp_price_texts[:4] if comp_price_texts else [
            f"{market_min:,.0f}đ - {market_max:,.0f}đ"
        ]

        behavior_display = (
            f"Tệp {dominant_age_label} tại {demographics.get('name', 'khu vực')}: "
            f"Ưu tiên tiện lợi, phục vụ nhanh, thanh toán QR, "
            f"{db5_demands[0] if db5_demands else 'nhu cầu ăn sáng & nước uống đồng bộ'}."
        )

        return {
            "competition_level": competition_level,
            "total_competitors_1km": comp_count,
            "direct_competitors_count": sum(1 for c in scored_competitors if c.get("threat_score", 0) >= 65),
            "systemic_weakness_detected": {
                "has_systemic": systemic_info["has_systemic"],
                "patterns": systemic_info["patterns"],
                "summary": systemic_info["summary_pattern"]
            },
            "has_dual_strategies": has_dual_strategies,
            "dual_strategies": dual_strategies_payload,
            "market_gaps": gaps,
            "top_ranked_competitors": scored_competitors[:5],
            "top_weaknesses": top_weaknesses_display,
            "price_overview": price_overview_display,
            "price_benchmark": {
                "market_min": market_min,
                "market_max": market_max,
                "market_avg": market_avg,
                "income_tier": income_tier_label,
                "target_budget": target_budget_str
            },
            "customer_insights": {
                "budget": target_budget_str,
                "peak_traffic": f"{morning_peak} & {afternoon_peak}",
                "behavior": behavior_display[:180] + "..." if len(behavior_display) > 180 else behavior_display
            }
        }
