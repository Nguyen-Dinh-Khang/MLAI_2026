import React, { useState, useEffect } from 'react';
import { 
  Search, MapPin, DollarSign, Store, Tag, AlertTriangle, 
  CheckCircle2, TrendingUp, ShieldAlert, ArrowRight, Sparkles, RefreshCw, BarChart3, Users,
  Bookmark, BookmarkCheck
} from 'lucide-react';
import FormattedMarkdown from './FormattedMarkdown';

/**
 * FeasibilityScanner - Giao diện 1: Máy quét Thẩm định Ý tưởng (Day 0)
 * Giúp người dùng kiểm tra tính khả thi trước khi bỏ vốn.
 * Chạy trọn vẹn pipeline 4 mắt xích và trả về bản phân tích 4 khối chuyên sâu.
 * Hỗ trợ lưu trữ mô hình (1xx), món định bán (2xx), địa chỉ, tọa độ và kế sách vào hồ sơ cá nhân.
 */
export default function FeasibilityScanner({ metadata, currentUser, savedStrategy, onStrategySaved }) {
  // Form State - Không điền sẵn dữ liệu, chỉ hiển thị placeholder
  const [address, setAddress] = useState('');
  const [modelId, setModelId] = useState('');
  const [selectedProductIds, setSelectedProductIds] = useState([]);
  const [budget, setBudget] = useState('');
  const [rent, setRent] = useState(''); // Để trống để hệ thống tự tính

  // Request State
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Trạng thái lưu kế sách chiến lược
  const [showSavePrompt, setShowSavePrompt] = useState(false);
  const [savingStrategy, setSavingStrategy] = useState(false);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState(null);

  // Tự động nạp thông tin cá nhân và kế sách đã lưu khi người dùng đăng nhập
  useEffect(() => {
    if (savedStrategy) {
      if (savedStrategy.address) setAddress(savedStrategy.address);
      if (savedStrategy.model_id) setModelId(savedStrategy.model_id);
      if (savedStrategy.product_ids && Array.isArray(savedStrategy.product_ids)) {
        setSelectedProductIds(savedStrategy.product_ids);
      }
      if (savedStrategy.report_result) {
        setResult(savedStrategy.report_result);
      }
      // Lưu ý: Không tự điền budget và rent để người dùng thoải mái thử tải dòng tiền mới
    }
  }, [savedStrategy]);

  // Toggle chọn sản phẩm (Chọn từ 1 đến 3 món)
  const toggleProduct = (productId) => {
    if (selectedProductIds.includes(productId)) {
      setSelectedProductIds(selectedProductIds.filter(id => id !== productId));
    } else {
      if (selectedProductIds.length < 3) {
        setSelectedProductIds([...selectedProductIds, productId]);
      }
    }
  };

  // Điều kiện kiểm tra đã điền đủ toàn bộ các trường bắt buộc
  const isFormValid = Boolean(
    address.trim() &&
    modelId &&
    selectedProductIds.length > 0 &&
    budget &&
    !isNaN(Number(budget)) &&
    Number(budget) > 0
  );

  // Lưu kế sách chiến lược vào CSDL MongoDB
  const handleSaveStrategy = async () => {
    if (!currentUser || !result) return;
    setSavingStrategy(true);
    try {
      const token = localStorage.getItem('mlai_user_token');
      const coords = result?.location_info?.coordinates;
      const lng = Array.isArray(coords) ? coords[0] : 0.0;
      const lat = Array.isArray(coords) ? coords[1] : 0.0;

      const res = await fetch('/api/user/strategy/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          address: result?.location_info?.recognized_area || address.trim(),
          coordinates: { lng, lat },
          model_id: parseInt(modelId),
          product_ids: selectedProductIds,
          report_result: result
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Lỗi khi lưu kế sách chiến lược');
      }

      setShowSavePrompt(false);
      setSaveSuccessMessage('Đã lưu thành công kế sách chiến lược vào hồ sơ cá nhân của bạn!');
      if (onStrategySaved) {
        onStrategySaved(data.strategy);
      }
    } catch (err) {
      alert(err.message);
    } finally {
      setSavingStrategy(false);
    }
  };

  // Gửi Form thẩm định tới FastAPI
  const handleEvaluate = async (e) => {
    e.preventDefault();
    if (!isFormValid) {
      alert('Vui lòng điền đầy đủ tất cả các trường bắt buộc trước khi thẩm định!');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setShowSavePrompt(false);
    setSaveSuccessMessage(null);

    // Hiệu ứng chuyển bước pipeline trực quan
    const stepsInterval = setInterval(() => {
      setActiveStep((prev) => (prev < 4 ? prev + 1 : prev));
    }, 1800);

    try {
      const response = await fetch('/api/scanner/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: address.trim(),
          model_id: parseInt(modelId),
          product_ids: selectedProductIds,
          budget: parseFloat(budget),
          rent: rent ? parseFloat(rent) : null
        })
      });

      clearInterval(stepsInterval);

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Lỗi xử lý pipeline thẩm định');
      }

      const data = await response.json();
      setResult(data);

      // Nếu người dùng đã đăng nhập, tự động bật thông báo hỏi có muốn lưu kế sách không
      if (currentUser) {
        setShowSavePrompt(true);
      }
    } catch (err) {
      clearInterval(stepsInterval);
      setError(err.message);
    } finally {
      setLoading(false);
      setActiveStep(0);
    }
  };

  const formatVND = (amount) => {
    if (!amount) return '0 đ';
    return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      
      {/* ============================================================= */}
      {/* CỘT TRÁI: FORM ĐIỀN NHANH Ý TƯỞNG KINH DOANH */}
      {/* ============================================================= */}
      <div className="lg:col-span-5 space-y-6">
        <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-5">
          <div>
            <div className="flex items-center space-x-2 text-blue-600 mb-1">
              <Sparkles className="w-5 h-5" />
              <h2 className="font-bold text-slate-900 text-lg">Máy Quét Thẩm Định Ý Tưởng</h2>
            </div>
            <p className="text-xs text-slate-500">
              Kiểm tra tính khả thi trước khi bỏ tiền. Thoải mái đổi vốn và vị trí để thử nghiệm nhiều phương án.
            </p>
          </div>

          <form onSubmit={handleEvaluate} className="space-y-4">
            
            {/* 1. Địa chỉ dự kiến */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                1. Địa chỉ / Vị trí dự kiến <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <MapPin className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="VD: đường, Quận/thành phố"
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition"
                  required
                />
              </div>
            </div>

            {/* 2. Mô hình kinh doanh (10 Mô hình) */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                2. Mô hình kinh doanh <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <Store className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                <select
                  value={modelId}
                  onChange={(e) => setModelId(e.target.value)}
                  className={`w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition appearance-none ${
                    !modelId ? 'text-slate-400' : 'text-slate-900'
                  }`}
                  required
                >
                  <option value="" disabled>-- Chọn mô hình kinh doanh --</option>
                  {metadata?.business_models?.map((m) => (
                    <option key={m.id} value={m.id} className="text-slate-900">
                      {m.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* 3. Nhóm sản phẩm định bán (Top 20) */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">
                  3. Món / Sản phẩm định bán (Chọn 1 - 3) <span className="text-red-500">*</span>
                </label>
                <span className={`text-[11px] font-medium ${selectedProductIds.length === 0 ? 'text-slate-400' : 'text-blue-600 font-semibold'}`}>
                  {selectedProductIds.length === 0 ? 'Chưa chọn món' : `Đã chọn: ${selectedProductIds.length}/3`}
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1.5 bg-slate-50 rounded-xl border border-slate-200">
                {metadata?.products?.map((p) => {
                  const isSelected = selectedProductIds.includes(p.id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => toggleProduct(p.id)}
                      className={`text-xs px-2.5 py-1 rounded-lg font-medium transition ${
                        isSelected
                          ? 'bg-blue-600 text-white shadow-sm'
                          : 'bg-white text-slate-700 hover:bg-slate-200 border border-slate-200'
                      }`}
                    >
                      {p.name}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 4. Số vốn hiện có */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                4. Số vốn khởi nghiệp hiện có (VNĐ) <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <DollarSign className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
                <input
                  type="number"
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  placeholder="Ví dụ: 150000000"
                  step="5000000"
                  min="10000000"
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm font-semibold text-slate-900 focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition"
                  required
                />
              </div>
              {budget && Number(budget) > 0 ? (
                <div className="text-[11px] text-slate-500 mt-1 font-medium">
                  Tương đương: <span className="text-blue-700 font-bold">{formatVND(budget)}</span>
                </div>
              ) : null}
            </div>

            {/* 5. Giá thuê mặt bằng */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                5. Tiền thuê mặt bằng dự kiến (VNĐ/tháng)
              </label>
              <input
                type="number"
                value={rent}
                onChange={(e) => setRent(e.target.value)}
                placeholder="Để trống: Hệ thống tự ước tính theo khu vực"
                step="1000000"
                className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 focus:bg-white outline-none transition"
              />
              {rent && Number(rent) > 0 ? (
                <div className="text-[11px] text-slate-500 mt-1 font-medium">
                  Tương đương: <span className="text-slate-700 font-semibold">{formatVND(rent)}/tháng</span>
                </div>
              ) : null}
            </div>

            {/* Nút bấm chạy Pipeline */}
            <button
              type="submit"
              disabled={loading || !isFormValid}
              className={`w-full py-3.5 px-4 rounded-xl font-bold text-sm text-white flex items-center justify-center space-x-2 shadow-lg transition duration-200 ${
                loading || !isFormValid
                  ? 'bg-slate-300 text-slate-500 cursor-not-allowed shadow-none'
                  : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-blue-500/25 active:scale-[0.99]'
              }`}
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Đang chạy Pipeline 4 mắt xích...</span>
                </>
              ) : (
                <>
                  <span>⚡ Quét Thẩm Định Ý Tưởng Ngay</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
            {!isFormValid && !loading && (
              <p className="text-[11px] text-center text-slate-400">
                * Vui lòng điền đủ các mục (1, 2, 3, 4) để bắt đầu quét
              </p>
            )}

          </form>
        </div>
      </div>

      {/* ============================================================= */}
      {/* CỘT PHẢI: KẾT QUẢ BẢN BÁO CÁO THẨM ĐỊNH 4 PHẦN */}
      {/* ============================================================= */}
      <div className="lg:col-span-7 space-y-6">
        
        {/* TRẠNG THÁI LOADING PIPELINE */}
        {loading && (
          <div className="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm text-center space-y-6 animate-pulse">
            <div className="w-16 h-16 rounded-full bg-blue-50 border-4 border-blue-600 border-t-transparent animate-spin mx-auto flex items-center justify-center"></div>
            <div>
              <h3 className="font-bold text-slate-900 text-base">Hệ Thống Đang Chạy Pipeline Toàn Diện...</h3>
              <p className="text-xs text-slate-500 mt-1">Đang so khớp dữ liệu thời gian thực trên 5 CSDL MongoDB & GPU CUDA</p>
            </div>
            
            {/* Thanh hiển thị các bước */}
            <div className="grid grid-cols-4 gap-2 text-left text-xs pt-4 border-t border-slate-100">
              <div className={`p-2.5 rounded-lg border ${activeStep >= 0 ? 'bg-blue-50 border-blue-200 text-blue-800' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                <div className="font-bold">1. Geocoding</div>
                <div className="text-[10px]">Tọa độ & Dân cư 3km</div>
              </div>
              <div className={`p-2.5 rounded-lg border ${activeStep >= 1 ? 'bg-blue-50 border-blue-200 text-blue-800' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                <div className="font-bold">2. Quét Đối thủ</div>
                <div className="text-[10px]">DB2 Bán kính 1km</div>
              </div>
              <div className={`p-2.5 rounded-lg border ${activeStep >= 2 ? 'bg-blue-50 border-blue-200 text-blue-800' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                <div className="font-bold">3. Dò Lỗ Hổng</div>
                <div className="text-[10px]">So khớp DB2 & DB5</div>
              </div>
              <div className={`p-2.5 rounded-lg border ${activeStep >= 3 ? 'bg-blue-50 border-blue-200 text-blue-800' : 'bg-slate-50 border-slate-200 text-slate-400'}`}>
                <div className="font-bold">4. Thử Tải Vốn</div>
                <div className="text-[10px]">Qwen3.5 Reasoning</div>
              </div>
            </div>
          </div>
        )}

        {/* LỖI NẾU CÓ */}
        {error && (
          <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm flex items-start space-x-3">
            <AlertTriangle className="w-5 h-5 flex-shrink-0 text-red-600 mt-0.5" />
            <div>
              <div className="font-bold">Lỗi xử lý:</div>
              <div>{error}</div>
            </div>
          </div>
        )}

        {/* TRẠNG THÁI CHỜ BAN ĐẦU (EMPTY STATE) */}
        {!loading && !result && (
          <div className="bg-white rounded-2xl p-10 border border-slate-200 border-dashed text-center space-y-4">
            <div className="w-14 h-14 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto">
              <Search className="w-7 h-7" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-base">Chưa có dữ liệu thẩm định</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                Hãy điền địa chỉ, số vốn và mô hình bên cột trái rồi bấm nút <strong>"Quét Thẩm Định Ý Tưởng Ngay"</strong> để nhận bản báo cáo 4 khối thực chiến.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 pt-4 max-w-lg mx-auto text-left">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                <span className="font-bold text-slate-800 block">🎯 Điểm Khả Thi</span>
                <span className="text-[11px] text-slate-500">Chỉ ra 3 ưu thế & 3 cạm bẫy dễ mất tiền</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                <span className="font-bold text-slate-800 block">🔍 Lỗ Hổng Thị Trường</span>
                <span className="text-[11px] text-slate-500">Phát hiện món/combo đối thủ bỏ quên</span>
              </div>
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 text-xs">
                <span className="font-bold text-slate-800 block">⏱️ Thử Tải Sống Sót</span>
                <span className="text-[11px] text-slate-500">Đo số tháng cầm cự an toàn của vốn</span>
              </div>
            </div>
          </div>
        )}

        {/* HIỂN THỊ KẾT QUẢ THẨM ĐỊNH 4 PHẦN */}
        {result && (
          <div className="space-y-6">
            
            {/* 1. THÔNG BÁO NẾU ĐANG XEM CHIẾN LƯỢC ĐÃ LƯU TRƯỚC ĐÓ */}
            {savedStrategy && (
              <div className="p-4 rounded-2xl bg-gradient-to-r from-blue-50 via-indigo-50 to-blue-50 border border-blue-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-sm">
                <div className="flex items-center space-x-3">
                  <div className="p-2.5 bg-blue-600 text-white rounded-xl shadow-sm shrink-0">
                    <BookmarkCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-blue-100 text-blue-800">
                        Kế Sách Đã Lưu Trong CSDL
                      </span>
                      {savedStrategy.updated_at && (
                        <span className="text-[11px] text-slate-500">
                          (Cập nhật: {new Date(savedStrategy.updated_at).toLocaleDateString('vi-VN')})
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-700 mt-0.5">
                      Vị trí: <strong>{savedStrategy.address}</strong> • Mô hình: <strong>{savedStrategy.model_name}</strong>
                    </p>
                  </div>
                </div>
                <div className="text-[11px] text-slate-500 italic">
                  Bạn có thể nhập mức vốn mới bên trái để thử tải lại bất kỳ lúc nào.
                </div>
              </div>
            )}

            {/* 2. PROMPT HỎI LƯU KẾ SÁCH (KHI VỪA THẨM ĐỊNH XONG VÀ ĐÃ ĐĂNG NHẬP) */}
            {showSavePrompt && currentUser && (
              <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border-2 border-amber-300 shadow-md flex flex-col md:flex-row md:items-center md:justify-between gap-4 animate-fade-in">
                <div className="flex items-start space-x-3">
                  <div className="p-2 bg-amber-500 text-white rounded-xl mt-0.5 shrink-0 shadow-sm">
                    <Sparkles className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-slate-900">
                      Bạn có muốn lưu thông tin mô hình và kế sách này vào hồ sơ cá nhân không?
                    </h4>
                    <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                      Hệ thống sẽ lưu địa chỉ, tọa độ [lng, lat], mô hình (1xx), {selectedProductIds.length} món định bán và toàn bộ bản kế sách 4 khối này vào tài khoản <strong>{currentUser.username}</strong> để những lần sau đăng nhập sẽ tự động hiển thị, tránh việc bạn bị quên kế hoạch hành động.
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2 self-end md:self-center shrink-0">
                  <button
                    type="button"
                    onClick={() => setShowSavePrompt(false)}
                    className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-200 transition"
                  >
                    Bỏ qua
                  </button>
                  <button
                    type="button"
                    disabled={savingStrategy}
                    onClick={handleSaveStrategy}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 shadow-md shadow-blue-500/25 flex items-center space-x-1.5 transition active:scale-[0.98] disabled:opacity-50"
                  >
                    {savingStrategy ? (
                      <span>Đang lưu...</span>
                    ) : (
                      <>
                        <Bookmark className="w-4 h-4" />
                        <span>Lưu Kế Sách Ngay</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* 3. THÔNG BÁO LƯU THÀNH CÔNG */}
            {saveSuccessMessage && (
              <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-semibold flex items-center justify-between shadow-xs">
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>{saveSuccessMessage}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setSaveSuccessMessage(null)}
                  className="text-emerald-700 hover:text-emerald-900 text-xs underline font-normal"
                >
                  Đóng
                </button>
              </div>
            )}

            {/* THẺ TỔNG QUAN VỊ TRÍ & DÂN CƯ (DB1) */}
            <div className="bg-gradient-to-r from-blue-900 to-indigo-950 text-white rounded-2xl p-5 shadow-sm space-y-3">
              <div className="flex items-center justify-between text-xs">
                <span className="px-2.5 py-1 rounded-md bg-white/10 text-blue-200 font-semibold uppercase tracking-wider">
                  Khảo sát địa bàn vi mô
                </span>
                <span className="text-slate-300">Tọa độ: [{result.location_info.coordinates.join(', ')}]</span>
              </div>
              <div>
                <h3 className="text-lg font-extrabold">{result.location_info.recognized_area}</h3>
                <p className="text-xs text-blue-200 mt-0.5">
                  Mật độ: <strong>{result.demographics.population_density?.toLocaleString()} người/km²</strong> | Khách chủ lực: <strong>{result.demographics.dominant_age}</strong> | Thu nhập: <strong>{result.demographics.income_level}</strong>
                </p>
              </div>
            </div>

            {/* KHỐI 1: BẢN ĐỒ ĐỐI THỦ 1KM (DB2) */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Store className="w-5 h-5 text-amber-600" />
                  <h4 className="font-bold text-slate-900 text-sm">Bản Đồ Đối Thủ (Bán Kính 1km)</h4>
                </div>
                <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-amber-50 text-amber-700 border border-amber-200">
                  {result.competitors_summary.total_nearby} đối thủ lân cận
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="py-2 px-3">Tên Quán Đối Thủ</th>
                      <th className="py-2 px-3">Khoảng Cách</th>
                      <th className="py-2 px-3">Dải Giá</th>
                      <th className="py-2 px-3">Điểm Yếu Bị Khách Phàn Nàn</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.competitors_summary.list.map((c, idx) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        <td className="py-2.5 px-3 font-semibold text-slate-800">
                          {c.name}
                          {c.is_direct && (
                            <span className="ml-1.5 text-[9px] bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-bold">
                              Trực diện
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 font-medium">{c.distance_m}m</td>
                        <td className="py-2.5 px-3 text-blue-700 font-bold">{c.price_range}</td>
                        <td className="py-2.5 px-3 text-red-600 font-medium italic">{c.weakness}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* KHỐI 2: LỖ HỔNG THỊ TRƯỜNG VI MÔ (MARKET GAP) */}
            <div className="bg-gradient-to-tr from-amber-50 to-orange-50 border border-amber-200 rounded-2xl p-5 shadow-sm space-y-3">
              <div className="flex items-center space-x-2 text-amber-800">
                <TrendingUp className="w-5 h-5 text-amber-600" />
                <h4 className="font-bold text-sm">Lỗ Hổng Thị Trường Phát Hiện Được (Market Gap)</h4>
              </div>
              <p className="text-xs text-slate-600">
                Khoảng trống mà đối thủ quanh 1km bỏ quên, là cơ hội để quán bạn độc chiếm tệp khách này:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {result.market_gaps.market_gaps.map((gap, idx) => (
                  <div key={idx} className="bg-white p-3.5 rounded-xl border border-amber-200/80 shadow-xs space-y-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                      {gap.title}
                    </span>
                    <p className="text-xs text-slate-700 font-medium mt-1 leading-relaxed">
                      {gap.detail}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* KHỐI 3: BỘ GIẢ LẬP THỬ TẢI RỦI RO (STRESS-TEST) */}
            <div className="bg-white rounded-2xl p-5 border border-slate-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <ShieldAlert className="w-5 h-5 text-indigo-600" />
                  <h4 className="font-bold text-slate-900 text-sm">Thử Tải Rủi Ro Tài Chính (Stress-Tester)</h4>
                </div>
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold ${
                  result.stress_test.survival_color === 'green'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : result.stress_test.survival_color === 'yellow'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-red-50 text-red-700 border border-red-200'
                }`}>
                  {result.stress_test.survival_rating}
                </span>
              </div>

              {/* 3 Chỉ số tài chính đo lường */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
                  <span className="text-[11px] text-slate-500 block font-medium">Runway Cầm Cự</span>
                  <span className="text-lg font-black text-blue-600">{result.stress_test.runway_months}</span>
                  <span className="text-[10px] text-slate-400 block font-semibold">tháng an toàn</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
                  <span className="text-[11px] text-slate-500 block font-medium">Giá Thuê Trần</span>
                  <span className="text-sm font-bold text-slate-900 block mt-1">
                    {formatVND(result.stress_test.max_recommended_rent)}
                  </span>
                  <span className="text-[10px] text-slate-400 block">/tháng tối đa</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-center">
                  <span className="text-[11px] text-slate-500 block font-medium">Hòa Vốn Tối Thiểu</span>
                  <span className="text-lg font-black text-emerald-600">{result.stress_test.breakeven_orders_per_day}</span>
                  <span className="text-[10px] text-slate-400 block font-semibold">đơn / ngày</span>
                </div>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl text-xs text-slate-700 font-medium leading-relaxed border border-slate-100">
                {result.stress_test.verdict_text}
              </div>
            </div>

            {/* KHỐI 4: BẢN BÁO CÁO THẨM ĐỊNH THỰC CHIẾN TỪ QWEN3.5 4B */}
            <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
              <div className="flex items-center space-x-2 text-blue-700 pb-2 border-b border-slate-100">
                <CheckCircle2 className="w-5 h-5 text-blue-600" />
                <h4 className="font-bold text-base text-slate-900">Bản Thẩm Định Tổng Hợp (AI Co-pilot Synthesis)</h4>
              </div>
              <FormattedMarkdown content={result.ai_report} />
            </div>

          </div>
        )}

      </div>

    </div>
  );
}
