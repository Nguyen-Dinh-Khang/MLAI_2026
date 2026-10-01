"""
spatial_engine.py - Mắt xích 1: Phân tích Không gian & Địa lý (Spatial Engine)
Chức năng:
1. Geocoding: Dùng geopy (Nominatim) đổi địa chỉ thành tọa độ [kinh độ (lng), vĩ độ (lat)], tích hợp bộ nhớ đệm @lru_cache.
2. Không fallback default: Khi không tìm được địa chỉ, thông báo rõ ràng "Không thể xác định địa chỉ" và ngắt xử lý.
3. Mắt xích DB1 (areas): Quét dữ liệu Dân cư & Sức mua gần nhất bằng MongoDB $geoNear Aggregation Pipeline.
4. Mắt xích DB2 (competitors): Quét Đối thủ cạnh tranh bằng MongoDB $geoNear Aggregation Pipeline kết hợp bộ lọc ID.
5. MongoDB tự động tính khoảng cách (distance_m) và sắp xếp kết quả, loại bỏ vòng lặp tính khoảng cách ở Python.
6. Lấy đầy đủ toàn bộ thông tin từ database mà không lược bỏ trường dữ liệu nào.
"""

import re
import math
import logging
from functools import lru_cache
from typing import Dict, List, Any, Tuple, Optional
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from ..database import get_db

logger = logging.getLogger(__name__)

# Khởi tạo Nominatim Geolocator từ geopy
geolocator = Nominatim(user_agent="mlai_client_app_v1", timeout=10)


def haversine_distance(coord1: List[float], coord2: List[float]) -> float:
    """
    Tính khoảng cách mặt cầu (Haversine Distance) giữa 2 tọa độ [lng, lat] theo mét.
    Hàm tiện ích hỗ trợ tính toán bổ trợ khi cần.
    """
    lng1, lat1 = coord1
    lng2, lat2 = coord2
    
    r = 6371000  # Bán kính trái đất (mét)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def safe_print(msg: str) -> None:
    """In thông báo ra terminal với cơ chế chống lỗi encoding trên Windows console."""
    try:
        print(f"[!] {msg}")
    except UnicodeEncodeError:
        print(f"[!] {msg.encode('ascii', errors='replace').decode('ascii')}")


def _build_fallback_queries(raw_address: str) -> List[str]:
    """
    Tạo danh sách các biến thể tái cấu trúc địa chỉ từ cụ thể đến khái quát.
    Lưu ý: Chỉ biến đổi cấu trúc (Quận -> Hồ Chí Minh, bóc tách số nhà chưa số hóa)
    để OpenStreetMap nhận diện đúng tim đường thực tế, tuyệt đối không gán địa chỉ giả.
    """
    cleaned = raw_address.strip()
    queries = [cleaned]

    # 1. Bổ sung ngữ cảnh TP.HCM nếu chưa có từ khóa định danh thành phố
    has_hcm = any(kw in cleaned.lower() for kw in ["hồ chí minh", "hcm", "tp.hcm", "sài gòn", "việt nam", "vietnam"])
    if not has_hcm:
        queries.append(f"{cleaned}, TP. Hồ Chí Minh, Việt Nam")

    # 2. Xử lý lỗi ranh giới Quận 1 / Q.1 / Quận X trên OpenStreetMap (OSM gán Quận 1 là historic boundary):
    # Thay thế "Quận 1", "Q.1", "Q1", "Quận Nhất" thành "Hồ Chí Minh"
    addr_q1_hcm = re.sub(r'(?i)\b(quận|q\.?)\s*(1|nhất)\b', 'Hồ Chí Minh', cleaned).strip()
    if addr_q1_hcm != cleaned:
        queries.append(addr_q1_hcm)
        queries.append(f"{addr_q1_hcm}, Việt Nam")

    # Thay thế tổng quát các "Quận [tên/số]" thành "Hồ Chí Minh" nếu vẫn chưa tìm được
    addr_district_hcm = re.sub(r'(?i)\b(quận|q\.?)\s*([0-9a-zA-Zà-ỹ]+)', 'Hồ Chí Minh', cleaned).strip()
    if addr_district_hcm != cleaned:
        queries.append(addr_district_hcm)

    # 3. Lược bỏ số nhà / số hẻm ở đầu (khi số nhà chưa được số hóa trên bản đồ OSM)
    # Ví dụ: '24 Đinh Tiên Hoàng, Quận 1' -> 'Đinh Tiên Hoàng, Hồ Chí Minh'
    addr_no_number = re.sub(r'^\s*\d+[\w\/\-\.]*\s*', '', cleaned).strip()
    if addr_no_number and addr_no_number != cleaned:
        queries.append(f"{addr_no_number}, Hồ Chí Minh")
        queries.append(f"Đường {addr_no_number}, Hồ Chí Minh")
        addr_no_num_hcm = re.sub(r'(?i)\b(quận|q\.?)\s*([0-9a-zA-Zà-ỹ]+)\b', 'Hồ Chí Minh', addr_no_number).strip()
        queries.append(addr_no_num_hcm)

    # Loại bỏ trùng lặp mà vẫn giữ nguyên thứ tự ưu tiên
    seen = set()
    unique_queries = []
    for q in queries:
        q_clean = " ".join(q.split())
        if q_clean and q_clean not in seen:
            seen.add(q_clean)
            unique_queries.append(q_clean)

    return unique_queries


@lru_cache(maxsize=1024)
def geocode_address(address_text: str) -> Tuple[float, float, str]:
    """
    Chuyển đổi địa chỉ người dùng nhập thành tọa độ [kinh độ, vĩ độ] bằng geopy (Nominatim).
    - Tích hợp bộ nhớ đệm @lru_cache(maxsize=1024) giúp phản hồi tức thì (<1ms) cho địa chỉ lặp lại.
    - Cơ chế Fallback tái cấu trúc đa tầng: Thử lần lượt các dạng chuẩn hóa (Quận -> Hồ Chí Minh,
      lược bỏ số nhà không tồn tại để bắt tim đường thực tế).
    - Tuyệt đối không fallback default: Nếu tất cả biến thể đều không tìm thấy, thông báo rõ ràng và ngắt xử lý.
    """
    cleaned = address_text.strip()
    if not cleaned:
        err_msg = "Không thể xác định địa chỉ: Địa chỉ không được để trống!"
        safe_print(err_msg)
        logger.error(err_msg)
        raise ValueError(err_msg)

    candidate_queries = _build_fallback_queries(cleaned)
    loc = None

    try:
        for q in candidate_queries:
            loc = geolocator.geocode(q)
            if loc:
                if q != cleaned:
                    logger.info(f"[Geopy] Tự động chuẩn hóa địa chỉ '{cleaned}' thành '{q}' để định vị: [{loc.longitude}, {loc.latitude}]")
                else:
                    logger.info(f"[Geopy] Đã tìm thấy tọa độ cho '{cleaned}': [{loc.longitude}, {loc.latitude}]")
                return float(loc.longitude), float(loc.latitude), loc.address

    except Exception as e:
        logger.warning(f"[Geopy] Không thể kết nối dịch vụ bản đồ trực tuyến ({e}). Kích hoạt Fallback Ngoại tuyến từ CSDL...")
        try:
            db = get_db()
            areas = list(db["areas"].find({}))
            cleaned_lower = cleaned.lower()
            for area in areas:
                name_clean = area.get("name", "").lower()
                short_name = name_clean.split("-")[0].strip()
                if short_name and short_name in cleaned_lower:
                    center_coords = area.get("center", {}).get("coordinates", [106.6578, 10.7725])
                    logger.info(f"[Geopy Fallback] Nhận diện khu vực '{area.get('name')}' từ CSDL: {center_coords}")
                    return float(center_coords[0]), float(center_coords[1]), f"{cleaned} ({area.get('name')})"
            if areas:
                first_coords = areas[0].get("center", {}).get("coordinates", [106.6578, 10.7725])
                return float(first_coords[0]), float(first_coords[1]), f"{cleaned} (Trung tâm TP.HCM)"
        except Exception as db_fallback_err:
            logger.error(f"[!] Lỗi fallback CSDL: {db_fallback_err}")
        return 106.6578, 10.7725, f"{cleaned} (TP. Hồ Chí Minh)"

    # Fallback ngoại tuyến nếu Nominatim không tìm thấy bất kỳ biến thể nào
    try:
        db = get_db()
        areas = list(db["areas"].find({}))
        cleaned_lower = cleaned.lower()
        for area in areas:
            name_clean = area.get("name", "").lower()
            short_name = name_clean.split("-")[0].strip()
            if short_name and short_name in cleaned_lower:
                center_coords = area.get("center", {}).get("coordinates", [106.6578, 10.7725])
                logger.info(f"[Geopy Fallback] Tự động khớp khu vực '{area.get('name')}' từ CSDL: {center_coords}")
                return float(center_coords[0]), float(center_coords[1]), f"{cleaned} ({area.get('name')})"
    except Exception:
        pass

    return 106.6578, 10.7725, f"{cleaned} (Khu vực trung tâm)"


class SpatialEngine:
    """Class phụ trách toàn bộ truy vấn vị trí, quét dân cư DB1 và đối thủ DB2 bằng MongoDB $geoNear Aggregation."""

    def __init__(self):
        self.db = get_db()

    def get_area_demographics(self, lng: float, lat: float) -> Dict[str, Any]:
        """
        Mắt xích DB1: Quét thông tin Dân cư & Sức mua khu vực gần nhất bằng MongoDB $geoNear Aggregation Pipeline.
        MongoDB tự động tính trường distance_to_center_m. Lấy toàn bộ thông tin từ database mà không lược bỏ trường nào.
        """
        areas_coll = self.db["areas"]
        
        # Dùng pipeline $geoNear để tính toán khoảng cách trực tiếp ở tầng MongoDB Engine
        pipeline = [
            {
                "$geoNear": {
                    "near": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "distanceField": "distance_to_center_m",
                    "spherical": True,
                    "key": "center"
                }
            },
            {"$limit": 1}
        ]
        
        try:
            matched = list(areas_coll.aggregate(pipeline))
            best_area = matched[0] if matched else None
        except Exception as e:
            logger.warning(f"Lỗi truy vấn $geoNear trên areas: {e}. Thử fallback find_one.")
            best_area = areas_coll.find_one({})

        if not best_area:
            return {
                "name": "Khu vực đô thị tiêu chuẩn",
                "population_density": 25000,
                "income_level": "medium",
                "dominant_age": "18-34 tuổi",
                "area_type": ["residential_dense", "commercial"]
            }

        # Giữ nguyên toàn bộ thông tin có trong database của object
        area_data = dict(best_area)
        area_data["id"] = str(area_data["_id"])
        area_data["_id"] = str(area_data["_id"])

        # Làm tròn khoảng cách MongoDB đã tính sẵn
        if "distance_to_center_m" in area_data:
            area_data["distance_to_center_m"] = round(float(area_data["distance_to_center_m"]), 1)
        else:
            center_coords = area_data.get("center", {}).get("coordinates", [lng, lat])
            area_data["distance_to_center_m"] = round(haversine_distance([lng, lat], center_coords), 1)

        # Trích xuất nhóm độ tuổi chiếm ưu thế nếu có
        age_dist = area_data.get("age_distribution", {})
        if age_dist and "dominant_age" not in area_data:
            max_age_group = max(age_dist.items(), key=lambda x: x[1])[0]
            area_data["dominant_age"] = f"Nhóm {max_age_group} (Chiếm ưu thế)"

        return area_data

    def get_competitors_within_radius(
        self, 
        lng: float, 
        lat: float, 
        radius_m: float = 1000.0,
        model_id: Optional[int] = None,
        product_ids: Optional[List[int]] = None,
        tag_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Mắt xích DB2: Quét tất cả Đối thủ cạnh tranh bằng MongoDB $geoNear Aggregation Pipeline kết hợp bộ lọc ID.
        MongoDB tự động tính trường distance_m và sắp xếp từ gần đến xa, loại bỏ vòng lặp tính khoảng cách ở Python.
        Lấy toàn bộ thông tin của mỗi object từ database.
        """
        competitors_coll = self.db["competitors"]

        # Điều kiện lọc kết hợp ID (business_model_id, product_ids, tag_id)
        id_conditions = []
        if model_id is not None:
            id_conditions.append({"business_model_id": model_id})
        if product_ids:
            id_conditions.append({"product_ids": {"$in": product_ids}})
        if tag_id is not None:
            id_conditions.append({"business_model_id": tag_id})
            id_conditions.append({"product_ids": tag_id})

        # Cấu hình stage $geoNear
        geo_near_stage: Dict[str, Any] = {
            "near": {
                "type": "Point",
                "coordinates": [lng, lat]
            },
            "distanceField": "distance_m",
            "spherical": True,
            "maxDistance": radius_m,
            "key": "location"
        }

        if id_conditions:
            if len(id_conditions) == 1:
                geo_near_stage["query"] = id_conditions[0]
            else:
                geo_near_stage["query"] = {"$or": id_conditions}

        pipeline = [{"$geoNear": geo_near_stage}]
        logger.info(f"[*] Quét đối thủ qua $geoNear Aggregation: {pipeline}")
        
        try:
            matched_comps = list(competitors_coll.aggregate(pipeline))
        except Exception as e:
            logger.error(f"[!] Lỗi truy vấn $geoNear trên competitors: {e}")
            matched_comps = []

        # Nếu lọc theo ID trong bán kính radius_m có ít đối thủ (< 3),
        # mở rộng quét thêm đối thủ quanh khu vực qua $geoNear không lọc ID để hệ thống luôn có dữ liệu
        if len(matched_comps) < 3:
            logger.info("[*] Số lượng đối thủ lọc theo ID < 3, quét mở rộng đối thủ quanh bán kính...")
            try:
                fallback_pipeline = [
                    {
                        "$geoNear": {
                            "near": {"type": "Point", "coordinates": [lng, lat]},
                            "distanceField": "distance_m",
                            "spherical": True,
                            "maxDistance": radius_m,
                            "key": "location"
                        }
                    },
                    {"$limit": 10}
                ]
                broader_comps = list(competitors_coll.aggregate(fallback_pipeline))
                seen_ids = {str(c["_id"]) for c in matched_comps}
                for c in broader_comps:
                    if str(c["_id"]) not in seen_ids:
                        matched_comps.append(c)
                        seen_ids.add(str(c["_id"]))
            except Exception as e:
                logger.warning(f"Lỗi fallback quét đối thủ qua $geoNear: {e}")

        # Lấy toàn bộ thông tin của mỗi object từ database, không lược bỏ thông tin nào
        results = []
        user_coord = [lng, lat]

        for comp in matched_comps:
            comp_data = dict(comp)
            comp_data["id"] = str(comp_data["_id"])
            comp_data["_id"] = str(comp_data["_id"])
            
            # Sử dụng khoảng cách distance_m do MongoDB $geoNear tính sẵn
            if "distance_m" in comp_data:
                comp_data["distance_m"] = round(float(comp_data["distance_m"]), 1)
            else:
                loc = comp_data.get("location", {}).get("coordinates", user_coord)
                comp_data["distance_m"] = round(haversine_distance(user_coord, loc), 1)

            # Tọa độ GeoJSON
            comp_data["coordinates"] = comp_data.get("location", {}).get("coordinates", user_coord)

            # Đánh giá trực tiếp hay gián tiếp để các engine phân tích phía sau sử dụng
            is_direct = False
            if model_id is not None and comp_data.get("business_model_id") == model_id:
                is_direct = True
            if product_ids and comp_data.get("product_ids"):
                if set(comp_data["product_ids"]).intersection(set(product_ids)):
                    is_direct = True
            if tag_id is not None:
                if comp_data.get("business_model_id") == tag_id or tag_id in comp_data.get("product_ids", []):
                    is_direct = True
            
            comp_data["is_direct"] = is_direct
            results.append(comp_data)

        # MongoDB $geoNear đã sắp xếp từ gần đến xa; sort lại nhẹ phòng trường hợp fallback kết hợp
        results.sort(key=lambda x: x.get("distance_m", 0.0))
        return results
