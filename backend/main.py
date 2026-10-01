"""
main.py - Máy chủ FastAPI phục vụ Nền Tảng Ra Quyết Định Kinh Doanh (Client App)
Hỗ trợ:
- Giao diện 1: Máy quét Thẩm định Ý tưởng (Day 0) -> POST /api/scanner/evaluate
- Giao diện 2: Trợ lý Chiến thuật Đồng hành (Day 1 - 365) -> POST /api/copilot/chat
- Danh mục 10 Mô hình & 20 Sản phẩm chuẩn hóa -> GET /api/metadata
- Kiểm tra sức khỏe hệ thống -> GET /api/health
"""

import sys
import json
import logging
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

# Đảm bảo console Windows in tiếng Việt chuẩn UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MLAI_ClientApp")

# Import các module nội bộ
from .config import PORT, HOST, LLM_MODEL, EMBEDDING_MODEL
from .database import check_mongo_health, get_db
from .tag_manager import tag_manager
from .pipeline.spatial_engine import SpatialEngine, geocode_address
from .pipeline.market_gap_engine import MarketGapEngine
from .pipeline.stress_test_engine import StressTestEngine
from .pipeline.semantic_search import SemanticSearchEngine
from .pipeline.distillation import DistillationEngine
from .pipeline.llm_copilot import LLMCopilot
from .pipeline.copilot_router import detect_copilot_intent

# Khởi tạo FastAPI app
app = FastAPI(
    title="MLAI Business Decision Co-pilot Platform",
    description="Nền tảng Ra quyết định & Trợ lý Kinh doanh thực chiến F&B / Bán lẻ",
    version="3.0.0"
)

# Cho phép gọi chéo CORS từ Frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo các mắt xích pipeline
spatial_engine = SpatialEngine()
market_gap_engine = MarketGapEngine()
stress_test_engine = StressTestEngine()
semantic_search_engine = SemanticSearchEngine()
distillation_engine = DistillationEngine()
llm_copilot = LLMCopilot()


# =====================================================================
# PYDANTIC SCHEMAS (ĐẶC TẢ DỮ LIỆU ĐẦU VÀO)
# =====================================================================

class FeasibilityRequest(BaseModel):
    """Dữ liệu Form thẩm định ý tưởng (Giao diện 1)"""
    address: str = Field(..., description="Địa chỉ dự kiến mở quán")
    model_id: int = Field(..., description="Mã mô hình kinh doanh (101 - 110)")
    product_ids: List[int] = Field(..., description="Danh sách mã nhóm sản phẩm (201 - 220)")
    budget: float = Field(..., description="Số vốn hiện có (VNĐ)")
    rent: Optional[float] = Field(None, description="Tiền thuê mặt bằng dự kiến (VNĐ/tháng)")


class CopilotChatRequest(BaseModel):
    """Dữ liệu Chat sự cố thực tế (Giao diện 2)"""
    query: str = Field(..., description="Câu hỏi hoặc sự cố thực tế cần tư vấn")
    model_id: Optional[int] = Field(None, description="Mã mô hình quán đang kinh doanh (tùy chọn)")
    address: Optional[str] = Field(None, description="Địa chỉ quán kinh doanh (tùy chọn để quét đối thủ vi mô)")
    coordinates: Optional[Dict[str, float]] = Field(None, description="Tọa độ {'lng': float, 'lat': float} (tùy chọn)")
    product_ids: Optional[List[int]] = Field(None, description="Danh sách mã sản phẩm bán (tùy chọn)")
    conversation_history: Optional[List[Dict[str, str]]] = Field(None, description="Lịch sử đối thoại trước đó")


class RegisterRequest(BaseModel):
    """Dữ liệu đăng ký tài khoản"""
    username: str = Field(..., min_length=3, max_length=50, description="Tên đăng nhập")
    password: str = Field(..., min_length=4, description="Mật khẩu")
    full_name: Optional[str] = Field(None, description="Họ tên hoặc Tên quán")


class LoginRequest(BaseModel):
    """Dữ liệu đăng nhập"""
    username: str = Field(..., description="Tên đăng nhập")
    password: str = Field(..., description="Mật khẩu")


class SaveStrategyRequest(BaseModel):
    """Dữ liệu lưu kế sách chiến lược (Không lưu budget và rent)"""
    address: str = Field(..., description="Địa chỉ kinh doanh")
    coordinates: Dict[str, float] = Field(..., description="Tọa độ chuẩn xác {'lng': float, 'lat': float}")
    model_id: int = Field(..., description="Mã mô hình (101 - 110)")
    product_ids: List[int] = Field(..., description="Danh sách mã sản phẩm (201 - 220)")
    report_result: Dict[str, Any] = Field(..., description="Bản báo cáo kế sách 4 khối từ Giao diện 1")


# =====================================================================
# XÁC THỰC NGƯỜI DÙNG & BẢO MẬT (AUTH HELPERS)
# =====================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Băm mật khẩu kết hợp Salt bảo mật bằng SHA-256."""
    if not salt:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return pwd_hash, salt


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Xác thực mật khẩu người dùng nhập với hash đã lưu trong DB."""
    pwd_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(pwd_hash, expected_hash)


def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[Dict[str, Any]]:
    """Trích xuất và kiểm tra session người dùng từ Authorization Header."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split("Bearer ", 1)[1].strip()
    if not token:
        return None
    try:
        db = get_db()
        session = db["user_sessions"].find_one({"token": token})
        if not session:
            return None
        user = db["users"].find_one({"username": session["username"]})
        return user
    except Exception as e:
        logger.error(f"Lỗi xác thực người dùng: {e}")
        return None


# =====================================================================
# REST API ENDPOINTS
# =====================================================================

@app.post("/api/auth/register")
def register_user(req: RegisterRequest):
    """Đăng ký tài khoản người dùng mới."""
    db = get_db()
    clean_username = req.username.strip().lower()
    if not clean_username:
        raise HTTPException(status_code=400, detail="Tên đăng nhập không được để trống!")
    
    existing = db["users"].find_one({"username": clean_username})
    if existing:
        raise HTTPException(status_code=400, detail="Tên đăng nhập này đã được sử dụng!")
    
    pwd_hash, salt = hash_password(req.password)
    user_doc = {
        "username": clean_username,
        "password_hash": pwd_hash,
        "salt": salt,
        "full_name": req.full_name.strip() if req.full_name else clean_username,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    db["users"].insert_one(user_doc)
    
    # Tự động tạo token session sau khi đăng ký thành công
    token = secrets.token_hex(32)
    db["user_sessions"].insert_one({
        "token": token,
        "username": clean_username,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    logger.info(f"[✓] Đăng ký thành công tài khoản: {clean_username}")
    return {
        "status": "success",
        "message": "Đăng ký tài khoản thành công!",
        "token": token,
        "user": {
            "username": clean_username,
            "full_name": user_doc["full_name"]
        }
    }


@app.post("/api/auth/login")
def login_user(req: LoginRequest):
    """Đăng nhập tài khoản người dùng."""
    db = get_db()
    clean_username = req.username.strip().lower()
    user = db["users"].find_one({"username": clean_username})
    if not user:
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác!")
    
    if not verify_password(req.password, user["salt"], user["password_hash"]):
        raise HTTPException(status_code=401, detail="Tài khoản hoặc mật khẩu không chính xác!")
    
    # Tạo token phiên đăng nhập
    token = secrets.token_hex(32)
    db["user_sessions"].insert_one({
        "token": token,
        "username": clean_username,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    logger.info(f"[✓] Đăng nhập thành công: {clean_username}")
    return {
        "status": "success",
        "message": "Đăng nhập thành công!",
        "token": token,
        "user": {
            "username": clean_username,
            "full_name": user.get("full_name", clean_username)
        }
    }


@app.get("/api/auth/me")
def get_user_profile(authorization: Optional[str] = Header(None)):
    """Lấy thông tin tài khoản hiện tại từ session token."""
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập hết hạn hoặc không hợp lệ!")
    
    return {
        "username": user["username"],
        "full_name": user.get("full_name", user["username"])
    }


@app.post("/api/auth/logout")
def logout_user(authorization: Optional[str] = Header(None)):
    """Đăng xuất tài khoản, hủy session token."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        db = get_db()
        db["user_sessions"].delete_many({"token": token})
    return {"status": "success", "message": "Đã đăng xuất thành công!"}


@app.post("/api/user/strategy/save")
def save_user_strategy(req: SaveStrategyRequest, authorization: Optional[str] = Header(None)):
    """
    Lưu trữ cấu hình mô hình (1xx), món định bán (2xx), địa chỉ, tọa độ [lng, lat]
    và toàn bộ Kế sách chiến lược (báo cáo 4 khối) của người dùng vào MongoDB.
    Lưu ý: Không lưu budget và rent để người dùng linh hoạt thử nghiệm dòng tiền.
    """
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để lưu kế sách chiến lược!")
    
    db = get_db()
    
    # Tra cứu tên mô hình và nhóm sản phẩm từ tag_manager
    business_models = {m["id"]: m["name"] for m in tag_manager.get_business_models()}
    products_map = {p["id"]: p["name"] for p in tag_manager.get_products()}
    
    model_name = business_models.get(req.model_id, f"Mô hình {req.model_id}")
    product_names = [products_map.get(pid, f"Sản phẩm {pid}") for pid in req.product_ids]
    
    strategy_doc = {
        "username": user["username"],
        "address": req.address.strip(),
        "coordinates": {
            "lng": float(req.coordinates.get("lng", 0.0)),
            "lat": float(req.coordinates.get("lat", 0.0))
        },
        "model_id": req.model_id,
        "model_name": model_name,
        "product_ids": req.product_ids,
        "product_names": product_names,
        "report_result": req.report_result,
        "is_active": True,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    db["user_strategies"].update_one(
        {"username": user["username"]},
        {"$set": strategy_doc},
        upsert=True
    )
    
    logger.info(f"[✓] Đã lưu kế sách cho user '{user['username']}' tại '{strategy_doc['address']}'.")
    return {
        "status": "success",
        "message": "Đã lưu kế sách chiến lược thành công vào hồ sơ cá nhân của bạn!",
        "strategy": {
            "address": strategy_doc["address"],
            "coordinates": strategy_doc["coordinates"],
            "model_id": strategy_doc["model_id"],
            "model_name": strategy_doc["model_name"],
            "product_ids": strategy_doc["product_ids"],
            "product_names": strategy_doc["product_names"],
            "updated_at": strategy_doc["updated_at"]
        }
    }


@app.get("/api/user/strategy/active")
def get_active_strategy(authorization: Optional[str] = Header(None)):
    """
    Truy xuất kế sách chiến lược đang áp dụng của người dùng đã đăng nhập.
    Tự động phục vụ việc hiển thị lại thông tin cá nhân và kế hoạch hành động.
    """
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập để xem kế sách!")
    
    db = get_db()
    doc = db["user_strategies"].find_one({"username": user["username"]})
    if not doc:
        return {"has_strategy": False, "strategy": None}
    
    return {
        "has_strategy": True,
        "strategy": {
            "address": doc.get("address", ""),
            "coordinates": doc.get("coordinates", {}),
            "model_id": doc.get("model_id"),
            "model_name": doc.get("model_name", ""),
            "product_ids": doc.get("product_ids", []),
            "product_names": doc.get("product_names", []),
            "report_result": doc.get("report_result", {}),
            "updated_at": doc.get("updated_at", "")
        }
    }

@app.get("/api/health")
def health_check():
    """Kiểm tra trạng thái kết nối MongoDB, Ollama và mô hình Embedding."""
    mongo_status = check_mongo_health()
    return {
        "status": "online",
        "mongo": mongo_status,
        "llm_model": LLM_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "port": PORT
    }


@app.get("/api/metadata")
def get_metadata():
    """
    Trả về danh mục:
    - 10 Mô hình kinh doanh
    - 20 Nhóm sản phẩm chuẩn hóa
    - Danh sách gợi ý các địa chỉ phổ biến tại TP.HCM
    """
    suggested_locations = [
        "Cổng ĐH Bách Khoa, Tô Hiến Thành, Quận 10",
        "Gần Chợ Bến Thành, Quận 1",
        "Khu Phố Tây Thảo Điền, Quận 2",
        "Đường Tú Xương / Hồ Con Rùa, Quận 3",
        "Phố ẩm thực Tôn Đản / Vĩnh Khánh, Quận 4"
    ]
    return {
        "business_models": tag_manager.get_business_models(),
        "products": tag_manager.get_products(),
        "suggested_locations": suggested_locations
    }


@app.post("/api/scanner/evaluate")
def evaluate_business_feasibility(req: FeasibilityRequest):
    """
    GIAO DIỆN 1: MÁY QUÉT THẨM ĐỊNH Ý TƯỞNG (DAY 0)
    Chạy trọn vẹn quy trình 4 mắt xích:
    1. Geocoding -> Tọa độ & Dân cư 3km (DB1)
    2. Quét Đối thủ 1km (DB2)
    3. So khớp tìm Lỗ hổng thị trường (DB2 x DB5)
    4. Thử tải tài chính & Runway (DB3)
    5. LLM Qwen3.5 4B tổng hợp ra bản báo cáo 4 khối súc tích.
    """
    try:
        logger.info(f"[*] Bắt đầu thẩm định cho địa chỉ: {req.address} | Vốn: {req.budget:,.0f}đ")
        
        # Mắt xích 1: Geocoding & Dân cư (DB1)
        lng, lat, display_addr = geocode_address(req.address)
        demographics = spatial_engine.get_area_demographics(lng, lat)

        # Mắt xích 1b: Quét Đối thủ trong 1km (DB2)
        competitors = spatial_engine.get_competitors_within_radius(
            lng, lat, radius_m=1000.0,
            model_id=req.model_id,
            product_ids=req.product_ids
        )

        # Mắt xích 2: Máy dò Lỗ hổng Thị trường (DB2 x DB5)
        market_gaps = market_gap_engine.find_market_gaps(
            competitors_1km=competitors,
            model_id=req.model_id,
            product_ids=req.product_ids,
            demographics=demographics,
            budget=req.budget
        )

        # Mắt xích 3: Bộ Thử tải Rủi ro & Đo Sức sống Vốn (DB3)
        stress_test = stress_test_engine.run_stress_test(
            budget=req.budget,
            monthly_rent=req.rent,
            business_model_id=req.model_id,
            product_ids=req.product_ids,
            area_name=display_addr,
            has_dual_plans=market_gaps.get("has_dual_strategies", False)
        )

        # Mắt xích 6: LLM Reasoning (Qwen3.5 4B qua Ollama)
        model_name = tag_manager.get_tag_name(req.model_id)
        product_names = [tag_manager.get_tag_name(pid) for pid in req.product_ids]
        products_str = ", ".join(product_names)

        form_summary = {
            "address": display_addr,
            "model_name": model_name,
            "products_str": products_str,
            "budget": req.budget,
            "rent": req.rent or stress_test.get("monthly_rent", 0)
        }

        ai_report = llm_copilot.evaluate_feasibility(
            form_data=form_summary,
            demographics=demographics,
            competitors=competitors,
            market_gaps=market_gaps,
            stress_test=stress_test
        )

        return {
            "success": True,
            "location_info": {
                "input_address": req.address,
                "recognized_area": display_addr,
                "coordinates": [lng, lat]
            },
            "demographics": demographics,
            "competitors_summary": {
                "total_nearby": len(competitors),
                "list": competitors[:8]  # Trả về 8 đối thủ tiêu biểu
            },
            "market_gaps": market_gaps,
            "stress_test": stress_test,
            "ai_report": ai_report
        }

    except Exception as e:
        logger.error(f"[!] Lỗi trong quá trình thẩm định: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi phân tích pipeline: {str(e)}")


@app.post("/api/copilot/chat")
def copilot_chat(req: CopilotChatRequest, authorization: Optional[str] = Header(None)):
    """
    GIAO DIỆN 2: TRỢ LÝ CHIẾN THUẬT ĐỒNG HÀNH (DAY 1 - 365)
    Bộ định tuyến Agentic Router:
    1. Phân loại ý định: CẠNH TRANH (COMPETITIVE) vs NỘI BỘ (INTERNAL).
    2. Nếu CẠNH TRANH:
       - Lấy vị trí quán (từ user_strategies hoặc input người dùng).
       - Quét DB2 (Đối thủ 1km) + DB3 (Rủi ro) + DB4 (Kinh nghiệm) + DB5 (Sức mua thị trường).
       - LLM xuất đòn phản công combo, giữ giá và khai thác điểm yếu đối thủ.
    3. Nếu NỘI BỘ:
       - Quét DB3 (Rủi ro & sự cố) + DB4 (Bài học xương máu & lời thoại).
       - LLM xuất checklist SOP quy trình & đàm phán nội bộ.
    """
    try:
        query_text = req.query.strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="Câu hỏi không được để trống")

        logger.info(f"[*] Nhận câu hỏi Co-pilot: '{query_text}' | Model ID: {req.model_id}")

        # Lấy thông tin kế sách đã lưu của người dùng (nếu có đăng nhập)
        user = get_current_user(authorization) if authorization else None
        saved_strategy = None
        if user:
            db = get_db()
            saved_strategy = db["user_strategies"].find_one({"username": user["username"]})

        # Ưu tiên dữ liệu người dùng truyền từ giao diện, sau đó đến hồ sơ đã lưu
        model_id = req.model_id or (saved_strategy.get("model_id") if saved_strategy else None) or 105
        product_ids = req.product_ids or (saved_strategy.get("product_ids") if saved_strategy else None) or []
        address = req.address or (saved_strategy.get("address") if saved_strategy else "")
        req_coords = req.coordinates or (saved_strategy.get("coordinates") if saved_strategy else None)

        # Xác định tọa độ quán phục vụ việc quét đối thủ 1km
        lng, lat = 106.6578, 10.7725  # Tọa độ mặc định: Cổng ĐH Bách Khoa, Q10
        if req_coords and "lng" in req_coords and "lat" in req_coords and float(req_coords.get("lng", 0)) != 0:
            lng = float(req_coords["lng"])
            lat = float(req_coords["lat"])
        elif address:
            try:
                calc_lng, calc_lat, _ = geocode_address(address)
                if calc_lng != 0:
                    lng, lat = calc_lng, calc_lat
            except Exception as geo_err:
                logger.warning(f"Lỗi geocoding địa chỉ copilot: {geo_err}")

        # Mắt xích Định tuyến Ý định (Agentic Intent Router)
        intent_info = detect_copilot_intent(query_text)
        intent = intent_info.get("intent", "INTERNAL")

        competitors = []
        if intent == "COMPETITIVE":
            # Quét DB2: Đối thủ trong bán kính 1km
            try:
                competitors = spatial_engine.get_competitors_within_radius(
                    lng=lng,
                    lat=lat,
                    radius_m=1000.0,
                    model_id=model_id,
                    product_ids=product_ids
                )
            except Exception as comp_err:
                logger.warning(f"[!] Lỗi quét đối thủ DB2: {comp_err}")
                competitors = []

            # Quét đồng thời cả DB3, DB4, DB5 có lọc phân cấp
            raw_search = semantic_search_engine.hybrid_search_all(
                query=query_text,
                model_id=model_id,
                product_ids=product_ids
            )

            # Chắt lọc đồng thời DB2 + DB3 + DB4 + DB5
            distilled = distillation_engine.distill_records(raw_search, competitors=competitors)
            context_md = distillation_engine.build_llm_context(distilled, intent="COMPETITIVE")
        else:
            # Nhánh Nội bộ: Quét DB3, DB4 có lọc phân cấp
            raw_search = semantic_search_engine.hybrid_search_all(
                query=query_text,
                model_id=model_id,
                product_ids=product_ids
            )
            distilled = distillation_engine.distill_records(raw_search)
            context_md = distillation_engine.build_llm_context(distilled, intent="INTERNAL")

        # Mắt xích 6: LLM Reasoning (kèm lịch sử đa lượt)
        model_name = tag_manager.get_tag_name(model_id) if model_id else "Chung các mô hình"
        ai_advice = llm_copilot.answer_tactical_copilot(
            user_query=query_text,
            model_name=model_name,
            context_markdown=context_md,
            intent=intent,
            conversation_history=req.conversation_history
        )

        return {
            "success": True,
            "query": query_text,
            "model_name": model_name,
            "intent": intent,
            "intent_badge": intent_info.get("badge_title", "⚙️ Chế độ: Tối ưu Vận hành Nội bộ"),
            "intent_detail": intent_info.get("badge_detail", ""),
            "data_sources": intent_info.get("data_sources", ["DB3", "DB4"]),
            "competitors_count": len(competitors),
            "matched_insights": {
                "problems_found": len(distilled.get("problems", [])),
                "lessons_found": len(distilled.get("lessons", [])),
                "market_found": len(distilled.get("market", [])),
                "competitors_found": len(distilled.get("competitors", []))
            },
            "distilled_context": context_md,
            "ai_response": ai_advice
        }

    except Exception as e:
        logger.error(f"[!] Lỗi trong quá trình tư vấn Co-pilot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý trợ lý: {str(e)}")


@app.post("/api/copilot/chat/stream")
def copilot_chat_stream(req: CopilotChatRequest, authorization: Optional[str] = Header(None)):
    """
    GIAO DIỆN 2: TRỢ LÝ STREAMING REAL-TIME (SERVER-SENT EVENTS - SSE)
    Truyền tải token-by-token giúp người dùng thấy kết quả ngay sau 1-2 giây.
    Hỗ trợ Lọc phân cấp 3 tầng, Ma trận Vector và Bộ nhớ hội thoại đa lượt.
    """
    try:
        query_text = req.query.strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="Câu hỏi không được để trống")

        logger.info(f"[*] Nhận câu hỏi Co-pilot Streaming: '{query_text}' | Model ID: {req.model_id}")

        # Lấy thông tin kế sách đã lưu của người dùng (nếu có đăng nhập)
        user = get_current_user(authorization) if authorization else None
        saved_strategy = None
        if user:
            db = get_db()
            saved_strategy = db["user_strategies"].find_one({"username": user["username"]})

        # Ưu tiên dữ liệu người dùng truyền từ giao diện, sau đó đến hồ sơ đã lưu
        model_id = req.model_id or (saved_strategy.get("model_id") if saved_strategy else None) or 105
        product_ids = req.product_ids or (saved_strategy.get("product_ids") if saved_strategy else None) or []
        address = req.address or (saved_strategy.get("address") if saved_strategy else "")
        req_coords = req.coordinates or (saved_strategy.get("coordinates") if saved_strategy else None)

        # Xác định tọa độ quán phục vụ việc quét đối thủ 1km
        lng, lat = 106.6578, 10.7725
        if req_coords and "lng" in req_coords and "lat" in req_coords and float(req_coords.get("lng", 0)) != 0:
            lng = float(req_coords["lng"])
            lat = float(req_coords["lat"])
        elif address:
            try:
                calc_lng, calc_lat, _ = geocode_address(address)
                if calc_lng != 0:
                    lng, lat = calc_lng, calc_lat
            except Exception as geo_err:
                logger.warning(f"Lỗi geocoding địa chỉ copilot stream: {geo_err}")

        # Mắt xích Định tuyến Ý định (Agentic Intent Router)
        intent_info = detect_copilot_intent(query_text)
        intent = intent_info.get("intent", "INTERNAL")

        competitors = []
        if intent == "COMPETITIVE":
            try:
                competitors = spatial_engine.get_competitors_within_radius(
                    lng=lng,
                    lat=lat,
                    radius_m=1000.0,
                    model_id=model_id,
                    product_ids=product_ids
                )
            except Exception as comp_err:
                logger.warning(f"[!] Lỗi quét đối thủ DB2: {comp_err}")
                competitors = []

            raw_search = semantic_search_engine.hybrid_search_all(
                query=query_text,
                model_id=model_id,
                product_ids=product_ids
            )
            distilled = distillation_engine.distill_records(raw_search, competitors=competitors)
            context_md = distillation_engine.build_llm_context(distilled, intent="COMPETITIVE")
        else:
            raw_search = semantic_search_engine.hybrid_search_all(
                query=query_text,
                model_id=model_id,
                product_ids=product_ids
            )
            distilled = distillation_engine.distill_records(raw_search)
            context_md = distillation_engine.build_llm_context(distilled, intent="INTERNAL")

        model_name = tag_manager.get_tag_name(model_id) if model_id else "Chung các mô hình"

        def sse_event_stream():
            # 1. Gửi event metadata đầu tiên chứa các thông tin trạng thái
            meta_event = {
                "type": "metadata",
                "query": query_text,
                "model_name": model_name,
                "intent": intent,
                "intent_badge": intent_info.get("badge_title", "⚙️ Chế độ: Tối ưu Vận hành Nội bộ"),
                "intent_detail": intent_info.get("badge_detail", ""),
                "data_sources": intent_info.get("data_sources", ["DB3", "DB4"]),
                "competitors_count": len(competitors),
                "matched_insights": {
                    "problems_found": len(distilled.get("problems", [])),
                    "lessons_found": len(distilled.get("lessons", [])),
                    "market_found": len(distilled.get("market", [])),
                    "competitors_found": len(distilled.get("competitors", []))
                }
            }
            yield f"data: {json.dumps(meta_event, ensure_ascii=False)}\n\n"

            # 2. Streaming từng token từ LLM Qwen3.5 4B qua Ollama
            for token in llm_copilot.stream_tactical_copilot(
                user_query=query_text,
                model_name=model_name,
                context_markdown=context_md,
                intent=intent,
                conversation_history=req.conversation_history
            ):
                yield f"data: {json.dumps({'type': 'chunk', 'text': token}, ensure_ascii=False)}\n\n"

            # 3. Gửi event kết thúc
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        return StreamingResponse(
            sse_event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"[!] Lỗi trong quá trình stream Co-pilot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý trợ lý: {str(e)}")


# =====================================================================
# PHỤC VỤ GIAO DIỆN REACT (KHI ĐÃ BUILD)
# =====================================================================

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # Trả về các file tĩnh nếu tồn tại, ngược lại trả về index.html (SPA routing)
        file_candidate = FRONTEND_DIST / full_path
        if file_candidate.is_file():
            return FileResponse(file_candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def root_dev():
        return {
            "message": "MLAI Business Co-pilot Backend đang chạy!",
            "port": PORT,
            "frontend_status": "Vui lòng build React frontend hoặc chạy Vite dev server ở port 3000/5173",
            "api_docs": f"http://localhost:{PORT}/docs"
        }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 70)
    print(f"🚀 KHỞI ĐỘNG MÁY CHỦ FASTAPI TẠI: http://localhost:{PORT}")
    print(f"👉 API Docs (Swagger UI): http://localhost:{PORT}/docs")
    print(f"👉 CSDL: MongoDB Atlas (5 collections) | LLM: {LLM_MODEL}")
    print("=" * 70 + "\n")
    uvicorn.run("client_app.backend.main:app", host=HOST, port=PORT, reload=False)
