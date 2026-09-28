"""
tag_manager.py - Quản lý Danh mục Chuẩn hóa
Quản lý:
- 10 Mô hình kinh doanh (Mã 101 - 110)
- 20 Nhóm sản phẩm & dịch vụ phổ biến nhất (Mã 201 - 220)
- 4 Phân khúc độ tuổi khách hàng (Mã 301 - 304)
- Nhóm sự cố (Mã 401 - 408)
- Bài học kinh nghiệm (Mã 501 - 514)
"""

import json
import logging
from typing import Dict, List, Any, Optional
from .config import TAG_MAP_PATH

logger = logging.getLogger(__name__)


class TagManager:
    """Class quản lý và truy xuất danh mục Tag chuẩn hóa của hệ thống."""

    def __init__(self):
        self.tag_data: Dict[str, Any] = {}
        self.id_to_tag: Dict[str, str] = {}
        self.load_tags()

    def load_tags(self):
        """Đọc file tag_map.json vào bộ nhớ."""
        try:
            if TAG_MAP_PATH.exists():
                with open(TAG_MAP_PATH, "r", encoding="utf-8") as f:
                    self.tag_data = json.load(f)
                    self.id_to_tag = self.tag_data.get("id_to_tag", {})
                logger.info(f"[✓] Đã nạp danh mục tag chuẩn hóa ({len(self.id_to_tag)} tags).")
            else:
                logger.warning(f"[!] Không tìm thấy file: {TAG_MAP_PATH}")
        except Exception as e:
            logger.error(f"[!] Lỗi khi nạp tag_map.json: {e}")

    def get_business_models(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách 10 Mô hình kinh doanh phổ biến (Mã 101 -> 110)
        để hiển thị trên Dropdown cho người dùng chọn.
        """
        models = []
        for tid in range(101, 111):
            tag_str = self.id_to_tag.get(str(tid))
            if tag_str:
                # Format trong file thường là "101: Quán ăn sáng"
                name = tag_str.split(":", 1)[-1].strip() if ":" in tag_str else tag_str
                models.append({
                    "id": tid,
                    "name": name,
                    "code": f"model_{tid}"
                })
        return models

    def get_products(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách 20 Nhóm sản phẩm / dịch vụ phổ biến nhất (Mã 201 -> 220)
        để hiển thị dưới dạng Checkbox / Tags cho người dùng bấm chọn.
        """
        products = []
        for tid in range(201, 221):
            tag_str = self.id_to_tag.get(str(tid))
            if tag_str:
                name = tag_str.split(":", 1)[-1].strip() if ":" in tag_str else tag_str
                products.append({
                    "id": tid,
                    "name": name,
                    "code": f"product_{tid}"
                })
        return products

    def get_customer_segments(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách 4 Phân khúc độ tuổi khách hàng (Mã 301 -> 304).
        """
        segments = []
        for tid in range(301, 305):
            tag_str = self.id_to_tag.get(str(tid))
            if tag_str:
                name = tag_str.split(":", 1)[-1].strip() if ":" in tag_str else tag_str
                segments.append({
                    "id": tid,
                    "name": name,
                    "code": f"segment_{tid}"
                })
        return segments

    def get_tag_name(self, tag_id: int) -> str:
        """Lấy tên hiển thị tiếng Việt của một tag theo ID."""
        tag_str = self.id_to_tag.get(str(tag_id))
        if tag_str and ":" in tag_str:
            return tag_str.split(":", 1)[-1].strip()
        return tag_str or f"Tag #{tag_id}"


# Khởi tạo một đối tượng dùng chung
tag_manager = TagManager()
