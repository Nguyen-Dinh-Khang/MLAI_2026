"""
stress_test_engine.py - Mắt xích 3: Bộ Giả lập Thử tải Rủi ro & Hồ sơ Tài chính Động (Dynamic Financial Profiler v3)
Chức năng:
1. Ánh xạ định phí động (mặt bằng, cọc, lương, điện nước, capex sàn/trần) theo 10 Mô hình kinh doanh (Mã 101 - 110).
2. Tính toán kinh tế vi mô (biên lãi gộp, giá trị đơn AOV) theo 20 Nhóm sản phẩm (Mã 201 - 220) & thuật toán đa sản phẩm.
3. Cơ chế Capex Sàn & Trần triệt tiêu ảo tưởng an toàn ("Stress ảo").
4. Kích hoạt Cảnh báo Sinh tử trực diện (Dead-on-Arrival) khi vốn không đủ chạm ngưỡng setup tối thiểu.
5. Đo lường Điểm hòa vốn, Runway (tháng sinh tồn), Giá thuê trần, Cảnh báo DB3.
6. Hỗ trợ Thử tải Kịch bản Kép (Dual Stress-Testing: Lean vs Premium) thích ứng động.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from ..database import get_db

logger = logging.getLogger(__name__)

# ==============================================================================
# HỒ SƠ ĐỊNH PHÍ ĐỘNG THEO 10 MÔ HÌNH KINH DOANH (Mã 101 -> 110)
# ==============================================================================
BUSINESS_MODEL_PROFILES: Dict[int, Dict[str, Any]] = {
    101: {  # Quán ăn sáng
        "desc": "Quán ăn sáng",
        "default_rent": 10_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.45,
        "min_capex": 35_000_000,
        "max_capex": 90_000_000,
        "staff_cost": 12_000_000,       # 2 nhân sự chia ca sáng
        "utilities_cost": 3_000_000,
    },
    102: {  # Quán nước / Cà phê
        "desc": "Quán nước / Cà phê",
        "default_rent": 12_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.50,
        "min_capex": 45_000_000,
        "max_capex": 160_000_000,
        "staff_cost": 14_000_000,       # 2 - 2.5 nhân sự (pha chế + phục vụ)
        "utilities_cost": 4_500_000,    # Điều hòa + máy làm đá + máy pha cafe
    },
    103: {  # Quán cơm / Nhà hàng nhỏ
        "desc": "Quán cơm / Nhà hàng nhỏ",
        "default_rent": 15_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.55,
        "min_capex": 65_000_000,
        "max_capex": 220_000_000,
        "staff_cost": 20_000_000,       # 3 - 3.5 nhân sự (bếp chính, phụ, dọn bàn)
        "utilities_cost": 5_500_000,    # Bếp công nghiệp, bẫy mỡ, tủ đông mát
    },
    104: {  # Quán nhậu / Ăn vặt
        "desc": "Quán nhậu / Ăn vặt",
        "default_rent": 16_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.50,
        "min_capex": 75_000_000,
        "max_capex": 250_000_000,
        "staff_cost": 22_000_000,       # 4 nhân sự
        "utilities_cost": 5_000_000,    # Hút mùi, trữ thực phẩm
    },
    105: {  # Kiosk / Xe đẩy mang đi
        "desc": "Kiosk / Xe đẩy mang đi",
        "default_rent": 5_000_000,
        "deposit_months": 1,
        "capex_ratio": 0.35,
        "min_capex": 18_000_000,
        "max_capex": 45_000_000,
        "staff_cost": 6_000_000,        # 1 nhân sự full-time hoặc chủ tự đứng
        "utilities_cost": 1_200_000,    # Điện tủ mát mini, máy dập miệng ly
    },
    106: {  # Cửa hàng tạp hóa / Đại lý
        "desc": "Cửa hàng tạp hóa / Đại lý",
        "default_rent": 8_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.35,
        "min_capex": 25_000_000,
        "max_capex": 80_000_000,
        "staff_cost": 9_000_000,        # 1.5 nhân sự
        "utilities_cost": 2_500_000,
    },
    107: {  # Cửa hàng chuyên doanh bán lẻ
        "desc": "Cửa hàng chuyên doanh bán lẻ",
        "default_rent": 12_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.45,
        "min_capex": 35_000_000,
        "max_capex": 120_000_000,
        "staff_cost": 9_000_000,        # 1.5 nhân sự
        "utilities_cost": 2_500_000,
    },
    108: {  # Tiệm làm đẹp / Spa
        "desc": "Tiệm làm đẹp / Spa",
        "default_rent": 14_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.55,
        "min_capex": 55_000_000,
        "max_capex": 180_000_000,
        "staff_cost": 16_000_000,       # 2 - 2.5 thợ kỹ thuật
        "utilities_cost": 3_500_000,
    },
    109: {  # Tiệm dịch vụ dân sinh (Giặt ủi, sửa xe)
        "desc": "Tiệm dịch vụ dân sinh",
        "default_rent": 9_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.60,
        "min_capex": 85_000_000,
        "max_capex": 220_000_000,
        "staff_cost": 6_000_000,        # 1 thợ
        "utilities_cost": 7_000_000,    # Ngốn nhiều điện sấy và nước công nghiệp
    },
    110: {  # Siêu thị mini / Tiện lợi
        "desc": "Siêu thị mini / Tiện lợi",
        "default_rent": 18_000_000,
        "deposit_months": 2,
        "capex_ratio": 0.50,
        "min_capex": 80_000_000,
        "max_capex": 280_000_000,
        "staff_cost": 18_000_000,       # 3 nhân sự xoay ca
        "utilities_cost": 6_500_000,    # Dàn tủ mát dài hoạt động 24/7
    },
}

# ==============================================================================
# HỒ SƠ KINH TẾ ĐƠN VỊ THEO 20 NHÓM SẢN PHẨM (Mã 201 -> 220)
# ==============================================================================
PRODUCT_ECONOMICS_PROFILES: Dict[int, Dict[str, Any]] = {
    201: {"name": "Đồ uống", "gross_margin": 0.72, "aov": 32_000},
    202: {"name": "Cơm", "gross_margin": 0.48, "aov": 42_000},
    203: {"name": "Món nước", "gross_margin": 0.50, "aov": 45_000},
    204: {"name": "Bánh mì & Điểm tâm", "gross_margin": 0.55, "aov": 25_000},
    205: {"name": "Đồ ăn vặt", "gross_margin": 0.58, "aov": 30_000},
    206: {"name": "Món nhậu, Lẩu & Nướng", "gross_margin": 0.46, "aov": 160_000},
    207: {"name": "Thực phẩm tươi sống", "gross_margin": 0.30, "aov": 90_000},
    208: {"name": "Tạp hóa & Nhu yếu phẩm", "gross_margin": 0.22, "aov": 65_000},
    209: {"name": "Quần áo thời trang", "gross_margin": 0.60, "aov": 180_000},
    210: {"name": "Giày dép & Túi xách", "gross_margin": 0.58, "aov": 150_000},
    211: {"name": "Mỹ phẩm & Chăm sóc da", "gross_margin": 0.55, "aov": 140_000},
    212: {"name": "Cắt tóc & Làm tóc", "gross_margin": 0.78, "aov": 80_000},
    213: {"name": "Massage & Spa", "gross_margin": 0.75, "aov": 200_000},
    214: {"name": "Làm móng & Nối mi", "gross_margin": 0.80, "aov": 110_000},
    215: {"name": "Thuốc & TPCN", "gross_margin": 0.35, "aov": 95_000},
    216: {"name": "Phụ kiện công nghệ", "gross_margin": 0.62, "aov": 70_000},
    217: {"name": "Đồ gia dụng", "gross_margin": 0.32, "aov": 120_000},
    218: {"name": "Văn phòng phẩm", "gross_margin": 0.50, "aov": 40_000},
    219: {"name": "Giặt ủi & Giặt sấy", "gross_margin": 0.70, "aov": 45_000},
    220: {"name": "Sửa xe & Thiết bị", "gross_margin": 0.65, "aov": 85_000},
}


class StressTestEngine:
    """Class phụ trách mô phỏng bài toán tài chính và thử tải rủi ro sinh tồn."""

    def __init__(self):
        self.db = get_db()

    @staticmethod
    def resolve_unit_economics(product_ids: List[int], default_aov: float = 35_000) -> Tuple[float, float]:
        """
        Thuật toán tổng hợp kinh tế vi mô khi người dùng chọn nhiều sản phẩm.
        - Sản phẩm đầu tiên là sản phẩm chính (60% trọng số biên lãi).
        - Các sản phẩm sau là sản phẩm phụ (40% chia đều).
        - Hiệu ứng bán chéo (Cross-selling) tăng AOV.
        """
        valid_items = [PRODUCT_ECONOMICS_PROFILES[pid] for pid in product_ids if pid in PRODUCT_ECONOMICS_PROFILES]
        if not valid_items:
            return 0.50, default_aov

        if len(valid_items) == 1:
            return valid_items[0]["gross_margin"], float(valid_items[0]["aov"])

        # Đa sản phẩm
        primary = valid_items[0]
        secondary = valid_items[1:]

        sec_avg_margin = sum(p["gross_margin"] for p in secondary) / len(secondary)
        mixed_margin = round(0.60 * primary["gross_margin"] + 0.40 * sec_avg_margin, 2)

        # Hiệu ứng Cross-selling cho AOV (Món phụ đóng góp 35% giá trị vào giỏ hàng chung)
        cross_sell_addon = sum(p["aov"] for p in secondary) * 0.35
        mixed_aov = round(primary["aov"] + cross_sell_addon, -3)

        return mixed_margin, mixed_aov

    def _simulate_scenario(
        self,
        budget: float,
        strategy_label: str,
        capex_val: float,
        monthly_rent: float,
        deposit_months: int,
        staff_cost: float,
        utilities_cost: float,
        avg_order_val: float,
        gross_margin: float = 0.50
    ) -> Dict[str, Any]:
        """Tính toán chi tiết thử tải dòng tiền cho một kịch bản cụ thể."""
        deposit_amount = monthly_rent * deposit_months
        required_opening = capex_val + deposit_amount
        is_doa = budget < required_opening
        deficit = required_opening - budget if is_doa else 0.0

        monthly_fixed_cost = monthly_rent + utilities_cost + staff_cost
        breakeven_revenue = monthly_fixed_cost / max(gross_margin, 0.10)
        breakeven_orders_per_day = round(breakeven_revenue / (avg_order_val * 30))
        max_recommended_rent = round(min(budget * 0.08, breakeven_revenue * 0.22), -5)

        if is_doa:
            # Chết ngay từ vạch xuất phát do thiếu vốn setup & cọc
            working_capital = 0.0
            runway_months = 0.0
            survival_rating = "Báo Động Đỏ (Thiếu Vốn Setup)"
            survival_color = "red"
            verdict = (
                f"🚨 Không khả thi: Thiếu {deficit:,.0f}đ để hoàn tất setup ({capex_val:,.0f}đ) "
                f"và tiền cọc ({deposit_amount:,.0f}đ). Nguy cơ gãy gánh trước khi mở cửa!"
            )
        else:
            working_capital = max(budget - capex_val - deposit_amount, 5_000_000)
            monthly_loss_in_crisis = monthly_fixed_cost - (breakeven_revenue * 0.60 * gross_margin)
            runway_months = round(working_capital / max(monthly_loss_in_crisis, 1_000_000), 1)

            if runway_months >= 6.0:
                survival_rating = "Rất An Toàn"
                survival_color = "green"
                verdict = f"Vốn {budget:,.0f}đ tạo lớp đệm tài chính an toàn trong {runway_months} tháng nếu gặp biến cố."
            elif runway_months >= 3.5:
                survival_rating = "Đủ Khả Năng Cầm Cự"
                survival_color = "yellow"
                verdict = f"Vốn dự phòng cho phép trụ vững {runway_months} tháng. Cần kiểm soát chặt chi phí biến đổi."
            else:
                survival_rating = "Báo Động Đỏ"
                survival_color = "red"
                verdict = f"Cảnh báo: Chỉ chịu lỗ tối đa {runway_months} tháng! Nguy cơ đứt dòng tiền nếu 60 ngày đầu vắng khách."

        return {
            "strategy_label": strategy_label,
            "budget": budget,
            "capex": capex_val,
            "monthly_rent": monthly_rent,
            "deposit_amount": deposit_amount,
            "working_capital": working_capital,
            "monthly_fixed_cost": monthly_fixed_cost,
            "breakeven_revenue": breakeven_revenue,
            "breakeven_orders_per_day": breakeven_orders_per_day,
            "avg_order_value": avg_order_val,
            "gross_margin": gross_margin,
            "runway_months": runway_months,
            "max_recommended_rent": max_recommended_rent,
            "survival_rating": survival_rating,
            "survival_color": survival_color,
            "verdict_text": verdict
        }

    def run_stress_test(
        self,
        budget: float,
        monthly_rent: Optional[float],
        business_model_id: int,
        product_ids: List[int],
        area_name: str = "",
        has_dual_plans: bool = False
    ) -> Dict[str, Any]:
        """
        Thực hiện tính toán thử tải dòng tiền dựa trên số vốn, mô hình kinh doanh, sản phẩm và rủi ro DB3.
        Hỗ trợ tính toán Kịch bản Kép (Lean vs Premium) thích ứng động.
        """
        # Đảm bảo số vốn hợp lệ tối thiểu 10 triệu
        budget = max(float(budget or 50_000_000), 10_000_000)

        # 1. Tra cứu Hồ sơ Mô hình Kinh doanh (Dynamic Business Model Profile)
        model_profile = BUSINESS_MODEL_PROFILES.get(business_model_id, BUSINESS_MODEL_PROFILES[102])
        model_desc = model_profile["desc"]

        user_rent_provided = monthly_rent and monthly_rent > 0
        if not user_rent_provided:
            monthly_rent = float(model_profile["default_rent"])
        else:
            monthly_rent = float(monthly_rent)

        deposit_months = model_profile["deposit_months"]
        deposit_amount = monthly_rent * deposit_months

        # 2. Cơ chế Capex Thực tế (Kẹp giữa Sàn và Trần) triệt tiêu "Stress ảo"
        capex_ratio = model_profile["capex_ratio"]
        min_capex = float(model_profile["min_capex"])
        max_capex = float(model_profile["max_capex"])

        raw_capex = budget * capex_ratio
        actual_capex = min(max(raw_capex, min_capex), max_capex)

        # 3. Tra cứu Kinh tế Vi mô Đa sản phẩm (Gross Margin & AOV)
        gross_margin, avg_order_value = self.resolve_unit_economics(
            product_ids=product_ids,
            default_aov=32_000 if business_model_id == 105 else 40_000
        )

        # 4. Định phí Vận hành Hàng tháng
        staff_cost = float(model_profile["staff_cost"])
        utilities_cost = float(model_profile["utilities_cost"])
        monthly_fixed_cost = monthly_rent + utilities_cost + staff_cost

        # 5. Phân tích Sinh tử & Điểm Hòa Vốn
        required_opening_funds = actual_capex + deposit_amount
        is_dead_on_arrival = budget < required_opening_funds
        capital_deficit = required_opening_funds - budget if is_dead_on_arrival else 0.0

        breakeven_revenue = monthly_fixed_cost / max(gross_margin, 0.10)
        breakeven_orders_per_day = round(breakeven_revenue / (avg_order_value * 30))
        max_recommended_rent = round(min(budget * 0.08, breakeven_revenue * 0.22), -5)

        if is_dead_on_arrival:
            # KÍCH HOẠT: CẢNH BÁO SINH TỬ TRỰC DIỆN (DEAD-ON-ARRIVAL)
            working_capital = 0.0
            runway_months = 0.0
            survival_rating = "BÁO ĐỘNG ĐỎ: KHÔNG ĐỦ VỐN MỞ QUÁN (DEAD-ON-ARRIVAL)"
            survival_color = "red"
            verdict_text = (
                f"🚨 CẢNH BÁO SINH TỬ: Với số vốn {budget:,.0f}đ, bạn còn thiếu {capital_deficit:,.0f}đ "
                f"chỉ để đáp ứng chi phí setup tối thiểu ({actual_capex:,.0f}đ) và tiền cọc nhà ({deposit_amount:,.0f}đ). "
                f"Không thể mở mô hình {model_desc} mà không có nguy cơ đứt gánh ngay trước ngày khai trương! "
                f"Khuyến nghị: Chuyển sang mô hình Kiosk / Xe đẩy mang đi (Mã 105) hoặc huy động thêm vốn tối thiểu {capital_deficit + 30_000_000:,.0f}đ."
            )
        else:
            working_capital = max(budget - actual_capex - deposit_amount, 5_000_000)
            monthly_loss_in_crisis = monthly_fixed_cost - (breakeven_revenue * 0.60 * gross_margin)
            runway_months = round(working_capital / max(monthly_loss_in_crisis, 1_000_000), 1)

            if runway_months >= 6.0:
                survival_rating = "Rất An Toàn"
                survival_color = "green"
                verdict_text = (
                    f"Với số vốn {budget:,.0f}đ, bạn có lớp đệm tài chính an toàn để cầm cự trong {runway_months} tháng "
                    f"nếu thị trường đóng băng hoặc sụt giảm khách."
                )
            elif runway_months >= 3.5:
                survival_rating = "Đủ Khả Năng Cầm Cự"
                survival_color = "yellow"
                verdict_text = (
                    f"Vốn dự phòng cho phép bạn trụ vững trong {runway_months} tháng biến cố. "
                    f"Cần kiểm soát chặt chi phí biến đổi và chuẩn bị phương án bán online."
                )
            else:
                survival_rating = "Báo Động Đỏ (Thiếu Vốn Dự Phòng)"
                survival_color = "red"
                verdict_text = (
                    f"Cảnh báo: Bạn chỉ có thể chịu lỗ tối đa {runway_months} tháng! Nếu vắng khách trong 60 ngày đầu, "
                    f"nguy cơ đứt dòng tiền rất cao. Cần giảm chi phí thuê mặt bằng hoặc tăng vốn dự phòng."
                )

        # 6. KỊCH BẢN KÉP ĐỘNG (DUAL SIMULATION): Kích hoạt khi có cờ hoặc vốn lớn
        dual_simulations = None
        activate_dual = has_dual_plans or (budget >= 300_000_000)

        if activate_dual:
            # Nhánh 1: Ăn Chắc Mặc Bền (Lean Craft Simulation)
            lean_capex = min(actual_capex, 45_000_000)
            lean_rent = min(monthly_rent, 7_000_000) if user_rent_provided else 5_000_000
            lean_staff = round(staff_cost * 0.70)      # Tối ưu tinh gọn nhân sự
            lean_utilities = round(utilities_cost * 0.80)
            lean_aov = round(avg_order_value * 0.90)   # Giá phổ thông tiếp cận nhanh

            lean_sim = self._simulate_scenario(
                budget=budget,
                strategy_label="Nhánh 1: Ăn Chắc Mặc Bền (Lean Craft)",
                capex_val=lean_capex,
                monthly_rent=lean_rent,
                deposit_months=1,
                staff_cost=lean_staff,
                utilities_cost=lean_utilities,
                avg_order_val=lean_aov,
                gross_margin=gross_margin
            )

            # Nhánh 2: Đột Kích Cao Cấp (Premium Attack Simulation)
            premium_capex = min(budget * 0.55, max_capex * 1.5)
            premium_rent = max(monthly_rent, 16_000_000) if user_rent_provided else 18_000_000
            premium_staff = round(staff_cost * 1.35)   # Nhân sự chất lượng cao, phục vụ chuẩn
            premium_utilities = round(utilities_cost * 1.35)
            premium_aov = round(avg_order_value * 1.45) # Định vị cao cấp, AOV cao
            premium_margin = min(gross_margin + 0.05, 0.85) # Biên lãi tốt hơn nhờ giá bán cao

            premium_sim = self._simulate_scenario(
                budget=budget,
                strategy_label="Nhánh 2: Đột Kích Cao Cấp (Premium Attack)",
                capex_val=premium_capex,
                monthly_rent=premium_rent,
                deposit_months=2,
                staff_cost=premium_staff,
                utilities_cost=premium_utilities,
                avg_order_val=premium_aov,
                gross_margin=premium_margin
            )

            dual_simulations = {
                "lean": lean_sim,
                "premium": premium_sim
            }

        # 7. Truy vấn rủi ro DB3 có độ nghiêm trọng cao (severity = 3)
        problems_coll = self.db["problems"]
        severe_problems = list(problems_coll.find({"severity": {"$in": [3, "3"]}}).limit(2))
        problem_warnings = []
        for p in severe_problems:
            problem_warnings.append({
                "title": p.get("title"),
                "summary": p.get("summary")
            })

        return {
            "budget": budget,
            "monthly_rent": monthly_rent,
            "initial_capex": actual_capex,
            "min_capex": min_capex,
            "max_capex": max_capex,
            "deposit_amount": deposit_amount,
            "working_capital": working_capital,
            "monthly_fixed_cost": monthly_fixed_cost,
            "breakeven_revenue": breakeven_revenue,
            "breakeven_orders_per_day": breakeven_orders_per_day,
            "avg_order_value": avg_order_value,
            "gross_margin": gross_margin,
            "runway_months": runway_months,
            "max_recommended_rent": max_recommended_rent,
            "survival_rating": survival_rating,
            "survival_color": survival_color,
            "verdict_text": verdict_text,
            "is_dead_on_arrival": is_dead_on_arrival,
            "capital_deficit": capital_deficit,
            "has_dual_plans": activate_dual,
            "dual_simulations": dual_simulations,
            "severe_risks_from_db3": problem_warnings
        }
