"""
database.py - Quản lý kết nối Cơ sở dữ liệu MongoDB
Cung cấp kết nối tới 5 CSDL:
1. areas (DB1 - Dân cư & Sức mua khu vực)
2. competitors (DB2 - Đối thủ cạnh tranh vi mô trong 1km)
3. problems (DB3 - Rủi ro & Sự cố vận hành)
4. experiences (DB4 - Bài học xương máu & Kịch bản thực chiến)
5. market_segments (DB5 - Thị trường & Hành vi khách hàng)
"""

import logging
from typing import Optional, Dict, Any
from pymongo import MongoClient
from pymongo.database import Database
from .config import MONGO_URI, DB_NAME

logger = logging.getLogger(__name__)

# Biến toàn cục lưu trữ client và database
_mongo_client: Optional[MongoClient] = None
_mongo_db: Optional[Database] = None


def get_db() -> Database:
    """
    Lấy đối tượng kết nối Database MongoDB.
    Nếu chưa kết nối thì tự động khởi tạo kết nối (Singleton pattern).
    """
    global _mongo_client, _mongo_db
    if _mongo_db is not None:
        return _mongo_db

    try:
        logger.info(f"[*] Đang kết nối tới MongoDB: {DB_NAME}...")
        _mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        # Thử ping để đảm bảo kết nối hoạt động bình thường
        _mongo_client.admin.command('ping')
        _mongo_db = _mongo_client[DB_NAME]
        logger.info("[✓] Kết nối MongoDB THÀNH CÔNG!")
        return _mongo_db
    except Exception as e:
        logger.error(f"[!] Lỗi kết nối MongoDB: {e}")
        raise ConnectionError(f"Không thể kết nối tới cơ sở dữ liệu MongoDB: {e}")


def check_mongo_health() -> Dict[str, Any]:
    """Kiểm tra trạng thái kết nối MongoDB phục vụ endpoint health-check."""
    try:
        db = get_db()
        collections = db.list_collection_names()
        return {
            "status": "connected",
            "database": DB_NAME,
            "collections_count": len(collections),
            "collections": collections
        }
    except Exception as e:
        return {
            "status": "error",
            "database": DB_NAME,
            "error": str(e)
        }
