"""
copilot_router.py - Bộ Định tuyến Ý định Thông minh (Agentic Router for Tactical Copilot)
Phân loại câu hỏi của người dùng thành 2 nhánh:
1. COMPETITIVE (Cạnh tranh vi mô): Quán bên cạnh, đối thủ phá giá, giành khách, tiếp thị vi mô 1km
   -> Kích hoạt đồng thời: DB2 (Đối thủ) + DB3 (Rủi ro) + DB4 (Bài học thực chiến) + DB5 (Sức mua thị trường)
2. INTERNAL (Vận hành nội bộ): Nhân sự, quản lý, quy trình bếp, chủ nhà, hao hụt nguyên liệu
   -> Kích hoạt: DB3 (Rủi ro & Sự cố) + DB4 (Bài học xương máu)
"""

import re
import logging
from typing import Dict, Any, List, Optional
import numpy as np

logger = logging.getLogger(__name__)

# Bộ từ khóa chỉ đích danh Cạnh tranh vi mô & Đối thủ F&B
COMPETITIVE_KEYWORDS = [
    "đối thủ", "quán bên cạnh", "sát vách", "phá giá", "bán rẻ hơn", 
    "bán phá giá", "cạnh tranh giá", "giành khách", "cướp khách", 
    "hút khách", "kéo khách", "hút hết khách", "kéo hết khách", 
    "mất khách vào tay", "quán đối diện", "quán mới mở sát", 
    "đè bẹp đối thủ", "combo đè", "đối đầu", "chiêu trò cạnh tranh", 
    "đông hơn quán tôi", "thị phần quanh đây"
]

# Bộ từ khóa chỉ đích danh Vận hành nội bộ, SOP và Chi phí
INTERNAL_KEYWORDS = [
    "đợi lâu", "chờ lâu", "phục vụ chậm", "chủ nhà", "tiền thuê", "tăng giá thuê",
    "giá thuê", "hợp đồng thuê", "nhân viên", "nhân sự", "nghỉ việc", "đi trễ",
    "bảo quản", "hư hỏng", "hao hụt", "công thức", "vệ sinh", "an toàn thực phẩm",
    "bếp", "quá tải", "hết vốn", "thiếu người", "không có người làm", "quản lý"
]

# Anchors cho mô hình Vector BAAI/bge-m3 kiểm tra tương đồng ngữ nghĩa
ANCHOR_COMPETITIVE = "Đối thủ cạnh tranh mở quán xung quanh bán giá rẻ phá giá giành giật khách hàng thị phần F&B"
ANCHOR_INTERNAL = "Vấn đề vận hành nội bộ quán như nhân viên nghỉ việc quản lý kho hao hụt mặt bằng chủ nhà chất lượng công thức"

_cached_anchor_vectors = None


def _get_anchor_vectors():
    """Tải và tính vector sẵn cho 2 anchors đại diện để tiết kiệm thời gian."""
    global _cached_anchor_vectors
    if _cached_anchor_vectors is not None:
        return _cached_anchor_vectors

    try:
        from .semantic_search import get_embedding_model, cosine_similarity
        model = get_embedding_model()
        if model is not None:
            vec_comp = model.encode(ANCHOR_COMPETITIVE, normalize_embeddings=True)
            vec_int = model.encode(ANCHOR_INTERNAL, normalize_embeddings=True)
            _cached_anchor_vectors = (np.array(vec_comp, dtype=np.float32), np.array(vec_int, dtype=np.float32))
            return _cached_anchor_vectors
    except Exception as e:
        logger.warning(f"[!] Không thể khởi tạo vector anchor cho copilot_router: {e}")

    return None


def detect_copilot_intent(query: str) -> Dict[str, Any]:
    """
    Xác định câu hỏi thuộc nhánh Cạnh tranh (COMPETITIVE) hay Nội bộ (INTERNAL).
    Kết hợp 2 tầng:
    1. Heuristic Keyword Matching có phân định ưu tiên
    2. Cosine Similarity với Anchor Vector BAAI/bge-m3 (Chính xác cho câu ẩn dụ)
    """
    cleaned_query = query.lower().strip()

    # Kiểm tra từ khóa cạnh tranh và nội bộ
    comp_matches = [kw for kw in COMPETITIVE_KEYWORDS if kw in cleaned_query]
    internal_matches = [kw for kw in INTERNAL_KEYWORDS if kw in cleaned_query]

    # Nếu có từ khóa cạnh tranh rõ ràng (như đối thủ, phá giá, quán sát vách, hút khách...)
    if comp_matches and not (internal_matches and "đối thủ" not in cleaned_query and "phá giá" not in cleaned_query):
        logger.info(f"[*] Copilot Router phát hiện từ khóa Cạnh tranh: {comp_matches}")
        return {
            "intent": "COMPETITIVE",
            "confidence": 0.95,
            "matched_by": "keyword",
            "matched_keywords": comp_matches,
            "badge_title": "🎯 Chế độ: Phản công Cạnh tranh Vi mô",
            "badge_detail": "Kích hoạt DB2 (Đối thủ 1km), DB3 (Rủi ro), DB4 (Kinh nghiệm) & DB5 (Thị trường)",
            "data_sources": ["DB2", "DB3", "DB4", "DB5"],
            "requires_db2": True
        }

    # Nếu có từ khóa nội bộ rõ ràng (chờ lâu, nhân viên, chủ nhà...) mà không có cạnh tranh trực diện
    if internal_matches:
        logger.info(f"[*] Copilot Router phát hiện từ khóa Nội bộ: {internal_matches}")
        return {
            "intent": "INTERNAL",
            "confidence": 0.95,
            "matched_by": "keyword_internal",
            "matched_keywords": internal_matches,
            "badge_title": "⚙️ Chế độ: Tối ưu Vận hành Nội bộ",
            "badge_detail": "Kích hoạt DB3 (Rủi ro vận hành) & DB4 (Bài học thực chiến)",
            "data_sources": ["DB3", "DB4"],
            "requires_db2": False
        }

    # Tầng 2: Vector Anchor Matching qua bge-m3
    anchors = _get_anchor_vectors()
    if anchors is not None:
        try:
            from .semantic_search import get_embedding_model, cosine_similarity
            model = get_embedding_model()
            q_vec = model.encode(query.strip(), normalize_embeddings=True)
            q_vec = np.array(q_vec, dtype=np.float32)

            vec_comp, vec_int = anchors
            score_comp = cosine_similarity(q_vec, vec_comp)
            score_int = cosine_similarity(q_vec, vec_int)

            logger.info(f"[*] Copilot Router Vector Scores: Cạnh tranh = {score_comp:.3f} | Nội bộ = {score_int:.3f}")

            # Nếu điểm tương đồng với Cạnh tranh cao hơn rõ rệt (ngưỡng chênh lệch >= 0.05)
            if score_comp > score_int + 0.04 and score_comp >= 0.45:
                return {
                    "intent": "COMPETITIVE",
                    "confidence": round(float(score_comp), 2),
                    "matched_by": "vector_anchor",
                    "badge_title": "🎯 Chế độ: Phản công Cạnh tranh Vi mô",
                    "badge_detail": "Kích hoạt DB2 (Đối thủ 1km), DB3 (Rủi ro), DB4 (Kinh nghiệm) & DB5 (Thị trường)",
                    "data_sources": ["DB2", "DB3", "DB4", "DB5"],
                    "requires_db2": True
                }
        except Exception as e:
            logger.warning(f"[!] Lỗi khi tính cosine similarity cho intent router: {e}")

    # Mặc định: Vận hành nội bộ (INTERNAL)
    return {
        "intent": "INTERNAL",
        "confidence": 0.90,
        "matched_by": "default_internal",
        "badge_title": "⚙️ Chế độ: Tối ưu Vận hành Nội bộ",
        "badge_detail": "Kích hoạt DB3 (Rủi ro vận hành) & DB4 (Bài học thực chiến)",
        "data_sources": ["DB3", "DB4"],
        "requires_db2": False
    }
