"""
semantic_search.py - Mắt xích 4: Tìm kiếm Ngữ nghĩa Hybrid (BAAI/bge-m3 Vector + Tag Filtering)
Chức năng:
1. Nhận câu hỏi bằng ngôn ngữ tự nhiên từ người dùng (Giao diện 2 - Trợ lý Co-pilot).
2. Sinh vector 1024 chiều bằng mô hình BAAI/bge-m3 (chạy trên GPU CUDA nếu có).
3. Tính toán Cosine Similarity trực tiếp với các vector embedding có sẵn trong MongoDB:
   - DB3: problems (Rủi ro & Sự cố vận hành)
   - DB4: experiences (Bài học xương máu & Lời thoại thực chiến)
   - DB5: market_segments (Thị trường & Hành vi khách hàng)
4. Trích xuất Top 3 - 5 bài học sát sườn nhất cho câu hỏi.
"""

import time
import logging
import numpy as np
from typing import Dict, List, Any, Optional
from ..database import get_db
from ..config import EMBEDDING_MODEL, DEVICE

logger = logging.getLogger(__name__)

# Biến singleton lưu mô hình SentenceTransformer trong bộ nhớ để không phải tải lại mỗi request
_embedding_model = None


def get_embedding_model():
    """Tải và khởi tạo mô hình BAAI/bge-m3 (Singleton)."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    try:
        import torch
        from sentence_transformers import SentenceTransformer

        # Tự động phát hiện GPU CUDA
        target_device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[*] Đang nạp mô hình Embedding '{EMBEDDING_MODEL}' lên [{target_device.upper()}]...")
        start_time = time.time()
        
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=target_device)
        logger.info(f"[✓] Nạp mô hình Embedding hoàn tất trong {time.time() - start_time:.2f}s!")
        return _embedding_model
    except Exception as e:
        logger.error(f"[!] Không thể tải mô hình embedding: {e}")
        return None


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Tính Cosine Similarity giữa 2 vector (đã chuẩn hóa L2)."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


class SemanticSearchEngine:
    """Class phụ trách tìm kiếm tương đồng ngữ nghĩa trên các CSDL DB3, DB4, DB5."""

    def __init__(self):
        self.db = get_db()
        self.model = get_embedding_model()

    def search_collection(
        self,
        collection_name: str,
        query: str,
        top_k: int = 4,
        tag_filter: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm Top K bản ghi có ngữ nghĩa sát nhất với câu truy vấn.
        Hỗ trợ lọc kết hợp (Hybrid Search) bằng tag_ids nếu người dùng có chọn mô hình.
        """
        coll = self.db[collection_name]
        
        # 1. Lọc theo Tag trước (Pre-filtering) nếu có
        query_filter: Dict[str, Any] = {}
        if tag_filter and tag_filter > 0:
            query_filter["tag_ids"] = tag_filter

        # Lấy các bản ghi có trường embedding
        cursor = coll.find(query_filter)
        records = list(cursor)

        # Nếu lọc theo tag_filter mà ra quá ít, mở rộng lấy toàn bộ collection
        if len(records) < 3 and tag_filter:
            records = list(coll.find({}))

        if not records:
            return []

        # 2. Nếu mô hình embedding sẵn sàng, sinh vector cho câu hỏi người dùng
        if self.model is not None and query.strip():
            try:
                query_vec = self.model.encode(
                    query.strip(), 
                    normalize_embeddings=True
                )
                query_vec = np.array(query_vec, dtype=np.float32)

                scored_records = []
                for doc in records:
                    doc_embed = doc.get("embedding")
                    if doc_embed and isinstance(doc_embed, list) and len(doc_embed) > 0:
                        doc_vec = np.array(doc_embed, dtype=np.float32)
                        score = cosine_similarity(query_vec, doc_vec)
                    else:
                        score = 0.1  # Điểm cơ bản nếu không có vector

                    # Xóa vector embedding thô trước khi trả về để tối ưu bộ nhớ
                    cleaned_doc = {k: v for k, v in doc.items() if k != "embedding"}
                    cleaned_doc["_id"] = str(cleaned_doc.get("_id"))
                    cleaned_doc["similarity_score"] = round(score, 4)
                    scored_records.append(cleaned_doc)

                # Sắp xếp theo độ tương đồng giảm dần
                scored_records.sort(key=lambda x: x["similarity_score"], reverse=True)
                return scored_records[:top_k]

            except Exception as embed_err:
                logger.warning(f"[!] Lỗi tính toán vector similarity: {embed_err}. Sử dụng Fallback text search.")

        # 3. Fallback: Nếu không dùng được vector embedding thì trả về các bản ghi tiêu biểu
        fallback_results = []
        for doc in records[:top_k]:
            cleaned_doc = {k: v for k, v in doc.items() if k != "embedding"}
            cleaned_doc["_id"] = str(cleaned_doc.get("_id"))
            cleaned_doc["similarity_score"] = 0.50
            fallback_results.append(cleaned_doc)
        return fallback_results

    def hybrid_search_all(
        self,
        query: str,
        model_id: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Quét đồng thời cả 3 cơ sở dữ liệu:
        - DB3 (problems)
        - DB4 (experiences)
        - DB5 (market_segments)
        """
        top_problems = self.search_collection("problems", query, top_k=3, tag_filter=model_id)
        top_experiences = self.search_collection("experiences", query, top_k=3, tag_filter=model_id)
        top_markets = self.search_collection("market_segments", query, top_k=2, tag_filter=model_id)

        return {
            "problems": top_problems,
            "experiences": top_experiences,
            "market_segments": top_markets
        }
