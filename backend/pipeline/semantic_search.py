"""
semantic_search.py - Mắt xích 4: Tìm kiếm Ngữ nghĩa Hybrid Tối Ưu Hóa (Matrix Cosine + Cascading Filter)
Chức năng cốt lõi:
1. Lọc phân cấp 3 tầng (Cascading Pre-filtering):
   - Tầng 1: Lọc theo nhóm món/sản phẩm (product_ids, 201 - 220)
   - Tầng 2: Nếu thiếu (< 3 bản ghi) -> Lọc theo mô hình kinh doanh (model_id, 101 - 110)
   - Tầng 3: Nếu vẫn thiếu -> Quét toàn bộ collection (để lấy bài học 5xx ở DB4)
2. Tối ưu hóa tính tương đồng:
   - Thay thế vòng lặp Python đơn chiếc bằng Phép nhân Ma trận NumPy (Vectorized Matrix BLAS)
   - scores = doc_matrix @ query_vec (nhanh hơn 50x - 100x)
3. Hỗ trợ đa CSDL chuẩn hóa:
   - DB3: problems (Rủi ro & Sự cố vận hành)
   - DB4: experiences (Bài học xương máu & Lời thoại thực chiến)
   - DB5: market_segments (Thị trường & Hành vi khách hàng)
"""

import time
import logging
import numpy as np
from typing import Dict, List, Any, Optional
from ..database import get_db
from ..config import EMBEDDING_MODEL, DEVICE

logger = logging.getLogger(__name__)

# Biến singleton lưu mô hình SentenceTransformer trong bộ nhớ để không nạp lại mỗi request
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
    """Tính Cosine Similarity giữa 2 vector đơn (chuẩn hóa L2)."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


class SemanticSearchEngine:
    """Class phụ trách tìm kiếm tương đồng ngữ nghĩa ma trận hóa trên các CSDL DB3, DB4, DB5."""

    def __init__(self):
        self.db = get_db()
        self.model = get_embedding_model()

    def search_collection(
        self,
        collection_name: str,
        query: str,
        top_k: int = 4,
        tag_filter: Optional[int] = None,
        product_ids: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm Top K bản ghi có ngữ nghĩa sát nhất với câu truy vấn.
        Cơ chế Lọc Phân Cấp (Cascading Pre-filtering):
        1. Lọc theo product_ids (2xx)
        2. Nếu thiếu (< 3 bản ghi) -> Lọc theo tag_filter (mô hình 1xx)
        3. Nếu vẫn thiếu -> Quét toàn bộ collection
        
        Cơ chế Ma trận hóa (Vectorized Matrix):
        scores = normalized_doc_matrix @ normalized_query_vec
        """
        coll = self.db[collection_name]

        # DB5 (market_segments) được thiết kế chuyên biệt để lọc theo Tag IDs, không dùng embedding
        if collection_name == "market_segments":
            return self.search_market_segments(product_ids=product_ids, tag_filter=tag_filter, top_k=top_k)

        records: List[Dict[str, Any]] = []

        # Tầng 1: Lọc theo product_ids nếu có
        if product_ids and len(product_ids) > 0:
            query_products = [int(pid) for pid in product_ids if pid]
            if query_products:
                cursor_p = coll.find({"tag_ids": {"$in": query_products}})
                records = list(cursor_p)

        # Tầng 2: Nếu Tầng 1 trả về ít hơn 3 bản ghi và có tag_filter (mã mô hình 101 - 110)
        if len(records) < 3 and tag_filter and tag_filter > 0:
            cursor_m = coll.find({"tag_ids": int(tag_filter)})
            records_m = list(cursor_m)
            # Gộp và khử trùng lặp theo _id
            seen_ids = {str(r.get("_id")) for r in records}
            for rm in records_m:
                if str(rm.get("_id")) not in seen_ids:
                    records.append(rm)
                    seen_ids.add(str(rm.get("_id")))

        # Tầng 3: Nếu Tầng 2 vẫn ít hơn 3 bản ghi (như experiences DB4 không có tag 1xx/2xx)
        if len(records) < 3:
            records = list(coll.find({}))

        if not records:
            return []

        # TÍNH TOÁN COSINE SIMILARITY BẰNG MA TRẬN NUMPY
        if self.model is not None and query.strip():
            try:
                # 1. Mã hóa câu hỏi thành vector (1024,)
                q_raw = self.model.encode(query.strip(), normalize_embeddings=True)
                q_vec = np.array(q_raw, dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    q_vec = q_vec / q_norm

                # 2. Tách các document có vector hợp lệ để đưa vào ma trận
                valid_docs: List[Dict[str, Any]] = []
                embed_list: List[List[float]] = []

                for doc in records:
                    doc_embed = doc.get("embedding")
                    if doc_embed and isinstance(doc_embed, list) and len(doc_embed) == len(q_vec):
                        valid_docs.append(doc)
                        embed_list.append(doc_embed)

                if embed_list:
                    # Tạo ma trận kích thước (N, 1024)
                    doc_matrix = np.array(embed_list, dtype=np.float32)
                    
                    # Chuẩn hóa L2 norm từng hàng của ma trận
                    row_norms = np.linalg.norm(doc_matrix, axis=1, keepdims=True)
                    row_norms[row_norms == 0] = 1.0
                    doc_matrix = doc_matrix / row_norms

                    # 3. PHÉP NHÂN MA TRẬN DUY NHẤT: (N, 1024) @ (1024,) -> (N,)
                    scores = doc_matrix.dot(q_vec)

                    # Lấy Top K chỉ số có điểm cao nhất
                    top_indices = np.argsort(scores)[::-1][:top_k]

                    scored_records = []
                    for idx in top_indices:
                        doc = valid_docs[idx]
                        cleaned_doc = {k: v for k, v in doc.items() if k != "embedding"}
                        cleaned_doc["_id"] = str(cleaned_doc.get("_id"))
                        cleaned_doc["similarity_score"] = round(float(scores[idx]), 4)
                        scored_records.append(cleaned_doc)

                    return scored_records

            except Exception as embed_err:
                logger.warning(f"[!] Lỗi tính toán ma trận vector similarity: {embed_err}. Sử dụng Fallback.")

        # Fallback an toàn nếu không dùng được vector embedding
        fallback_results = []
        for doc in records[:top_k]:
            cleaned_doc = {k: v for k, v in doc.items() if k != "embedding"}
            cleaned_doc["_id"] = str(cleaned_doc.get("_id"))
            cleaned_doc["similarity_score"] = 0.50
            fallback_results.append(cleaned_doc)
        return fallback_results

    def search_market_segments(
        self,
        product_ids: Optional[List[int]] = None,
        tag_filter: Optional[int] = None,
        top_k: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Lọc dữ liệu DB5 (market_segments) thuần túy theo Tag IDs và xếp hạng theo độ quan tâm (Interest).
        Vì DB5 được thiết kế chuyên biệt để phân tích hành vi theo mã món (2xx) và phân khúc độ tuổi (3xx),
        không sử dụng vector embedding để tối ưu tốc độ và độ chuẩn xác danh mục.
        """
        coll = self.db["market_segments"]
        records: List[Dict[str, Any]] = []

        # Tầng 1: Lọc theo mã món (product_ids, 201 - 220)
        if product_ids and len(product_ids) > 0:
            clean_pids = [int(pid) for pid in product_ids if pid]
            if clean_pids:
                cursor = coll.find({"tag_ids": {"$in": clean_pids}}).sort("interest", -1)
                records = list(cursor)

        # Tầng 2: Nếu chưa có sản phẩm hoặc không tìm thấy, lấy các phân khúc có interest cao nhất
        if not records:
            records = list(coll.find({}).sort("interest", -1).limit(top_k))

        cleaned_records = []
        for doc in records[:top_k]:
            cleaned_doc = {k: v for k, v in doc.items() if k != "embedding"}
            cleaned_doc["_id"] = str(cleaned_doc.get("_id"))
            cleaned_doc["similarity_score"] = float(doc.get("interest", 0.90))
            cleaned_records.append(cleaned_doc)

        return cleaned_records

    def hybrid_search_all(
        self,
        query: str,
        model_id: Optional[int] = None,
        product_ids: Optional[List[int]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Quét đồng thời cả 3 cơ sở dữ liệu:
        - DB3 (problems): Vector Cosine + Lọc phân cấp theo Tag
        - DB4 (experiences): Vector Cosine + Lọc phân cấp theo Tag
        - DB5 (market_segments): Lọc thuần túy theo Tag IDs & Xếp hạng theo độ quan tâm (Interest)
        """
        top_problems = self.search_collection(
            "problems", query, top_k=3, tag_filter=model_id, product_ids=product_ids
        )
        top_experiences = self.search_collection(
            "experiences", query, top_k=3, tag_filter=model_id, product_ids=product_ids
        )
        top_markets = self.search_market_segments(
            product_ids=product_ids, tag_filter=model_id, top_k=2
        )

        return {
            "problems": top_problems,
            "experiences": top_experiences,
            "market_segments": top_markets
        }
