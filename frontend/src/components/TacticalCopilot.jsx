import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, Send, Store, Sparkles, AlertCircle, 
  CheckSquare, Copy, Check, Clock, TrendingUp, HelpCircle, 
  BookmarkCheck, MapPin, Edit3, RotateCcw, Utensils, ShieldAlert,
  Share2, PanelLeftClose, PanelLeft, Plus, Bot, User
} from 'lucide-react';
import FormattedMarkdown from './FormattedMarkdown';

/**
 * TacticalCopilot - Giao diện 2: Trợ lý Chiến thuật Đồng hành (Day 1 - 365)
 * Thiết kế giao diện chuẩn phong cách ChatGPT:
 * - Cột bên trái: Toàn bộ thông tin cấu hình quán, hồ sơ, và danh mục kịch bản mẫu.
 * - Phần còn lại bên phải: Khung chat cố định toàn màn hình.
 * - Ô nhập liệu cố định ở dưới cùng (Sticky bottom).
 */
export default function TacticalCopilot({ metadata, currentUser, savedStrategy }) {
  // 1. Quản lý thông tin ngữ cảnh quán
  const [modelId, setModelId] = useState(105); // Mặc định Kiosk / Xe đẩy
  const [address, setAddress] = useState('');
  const [selectedProductIds, setSelectedProductIds] = useState([204, 201]); // Bánh mì & Cà phê
  const [isEditingProfile, setIsEditingProfile] = useState(false);

  // 2. Chat state & UI controls
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const messagesEndRef = useRef(null);

  // Tự động cuộn xuống tin nhắn mới nhất
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Đồng bộ thông tin từ hồ sơ quán đã lưu
  useEffect(() => {
    if (savedStrategy) {
      if (savedStrategy.model_id) setModelId(savedStrategy.model_id);
      if (savedStrategy.address) setAddress(savedStrategy.address);
      if (savedStrategy.product_ids && savedStrategy.product_ids.length > 0) {
        setSelectedProductIds(savedStrategy.product_ids);
      }
      setIsEditingProfile(false);
    } else {
      if (metadata?.suggested_locations && metadata.suggested_locations.length > 0 && !address) {
        setAddress(metadata.suggested_locations[0]);
      }
      setIsEditingProfile(true);
    }
  }, [savedStrategy, metadata]);

  const [chatHistory, setChatHistory] = useState([
    {
      id: 1,
      sender: 'ai',
      text: `Xin chào! Tôi là Trợ lý Cố vấn Kinh doanh thực chiến F&B. 
Bạn đang gặp sự cố hay khúc mắc gì trong quá trình bán hàng (vắng khách, chủ nhà tăng giá, nhân sự nghỉ việc, khách than đợi lâu, đối thủ sát vách phá giá...)? 
Hãy gõ câu hỏi cụ thể, hệ thống sẽ tự động định tuyến và truyền tải phản hồi thời gian thực:
- **Nếu là sự cố cạnh tranh vi mô**: Tự động quét đối thủ 1km và lôi cả 4 CSDL (DB2, DB3, DB4, DB5) để ra kịch bản phản công.
- **Nếu là sự cố vận hành nội bộ**: Kích hoạt DB3 & DB4 để đưa ra checklist quy trình và lời thoại mẫu trong 24h.`,
      intent: 'INTERNAL',
      intentBadge: '⚙️ Chế độ: Tối ưu Vận hành Nội bộ',
      dataSources: ['DB3', 'DB4'],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);

  useEffect(() => {
    scrollToBottom();
  }, [chatHistory, loading]);

  // Tạo cuộc trò chuyện mới
  const handleNewChat = () => {
    setChatHistory([
      {
        id: Date.now(),
        sender: 'ai',
        text: `Xin chào! Tôi là Trợ lý Cố vấn Kinh doanh thực chiến F&B. 
Bạn đang gặp sự cố hay khúc mắc gì trong quá trình bán hàng (vắng khách, chủ nhà tăng giá, nhân sự nghỉ việc, khách than đợi lâu, đối thủ sát vách phá giá...)? 
Hãy gõ câu hỏi cụ thể, hệ thống sẽ tự động định tuyến và truyền tải phản hồi thời gian thực:
- **Nếu là sự cố cạnh tranh vi mô**: Tự động quét đối thủ 1km và lôi cả 4 CSDL (DB2, DB3, DB4, DB5) để ra kịch bản phản công.
- **Nếu là sự cố vận hành nội bộ**: Kích hoạt DB3 & DB4 để đưa ra checklist quy trình và lời thoại mẫu trong 24h.`,
        intent: 'INTERNAL',
        intentBadge: '⚙️ Chế độ: Tối ưu Vận hành Nội bộ',
        dataSources: ['DB3', 'DB4'],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
    setQuery('');
  };

  // Danh sách các tình huống sự cố thực tế phổ biến
  const quickCrises = [
    {
      title: "🎯 Đối thủ sát vách phá giá 20%",
      type: "competitive",
      query: "Có quán mới mở sát vách bán món giống hệt quán tôi nhưng giá rẻ hơn 20% và tặng kèm trà đá. Khách quen của tôi bị hút qua đó khá nhiều, tôi phải đối phó thế nào mà không cần giảm giá?"
    },
    {
      title: "🎯 Kéo khách từ quán đối diện",
      type: "competitive",
      query: "Quán ăn đối diện rất đông khách vào khung giờ trưa và tối. Tôi nên làm combo gì hoặc tạo điểm nhấn nào để thu hút khách của họ sang quán mình?"
    },
    {
      title: "⚙️ Khách chê đợi lâu bỏ đi",
      type: "internal",
      query: "Quán tôi mở được 2 tuần cạnh trường Đại học. Mấy hôm nay khách than đợi lâu quá nên bỏ đi sang quán khác. Tôi chỉ có 2 người làm, làm sao để phục vụ nhanh hơn mà không cần thuê thêm người?"
    },
    {
      title: "⚙️ Chủ nhà đòi tăng giá thuê 30%",
      type: "internal",
      query: "Quán mới bán được 6 tháng vừa có lượng khách quen ổn định thì chủ nhà thông báo tăng tiền thuê thêm 30% vào tháng tới. Tôi nên đàm phán thế nào để giữ giá cũ hoặc không bị mất cọc?"
    }
  ];

  // Toggle chọn sản phẩm
  const toggleProduct = (pid) => {
    if (selectedProductIds.includes(pid)) {
      if (selectedProductIds.length > 1) {
        setSelectedProductIds(selectedProductIds.filter(id => id !== pid));
      }
    } else {
      if (selectedProductIds.length < 3) {
        setSelectedProductIds([...selectedProductIds, pid]);
      }
    }
  };

  // Gửi câu hỏi sự cố tới FastAPI hỗ trợ Streaming SSE và Multi-turn Memory
  const handleSend = async (customQuery = null) => {
    const textToSend = customQuery || query;
    if (!textToSend.trim() || loading) return;

    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Chuẩn bị lịch sử hội thoại gần nhất (Multi-turn Context)
    const conversationHistory = chatHistory
      .filter(m => m.id !== 1 && m.text && !m.isStreaming)
      .slice(-4)
      .map(m => ({
        role: m.sender === 'user' ? 'user' : 'assistant',
        content: m.text
      }));

    const aiMsgId = Date.now() + 1;
    const initialAiMessage = {
      id: aiMsgId,
      sender: 'ai',
      text: '',
      intent: 'INTERNAL',
      intentBadge: '⚙️ Đang phân tích ý định...',
      intentDetail: '',
      dataSources: ['DB3', 'DB4'],
      competitorsCount: 0,
      matched: null,
      isStreaming: true,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatHistory((prev) => [...prev, userMessage, initialAiMessage]);
    setQuery('');
    setLoading(true);

    const token = localStorage.getItem('mlai_user_token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const payload = {
      query: textToSend.trim(),
      model_id: parseInt(modelId),
      address: address,
      product_ids: selectedProductIds,
      conversation_history: conversationHistory
    };

    try {
      const response = await fetch('/api/copilot/chat/stream', {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`Mã lỗi máy chủ: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.slice(6);
            try {
              const eventData = JSON.parse(jsonStr);

              if (eventData.type === 'metadata') {
                setChatHistory((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMsgId
                      ? {
                          ...msg,
                          intent: eventData.intent,
                          intentBadge: eventData.intent_badge,
                          intentDetail: eventData.intent_detail,
                          dataSources: eventData.data_sources || [],
                          competitorsCount: eventData.competitors_count || 0,
                          matched: eventData.matched_insights
                        }
                      : msg
                  )
                );
              } else if (eventData.type === 'chunk') {
                const tokenText = eventData.text || '';
                setChatHistory((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMsgId
                      ? {
                          ...msg,
                          text: msg.text + tokenText
                        }
                      : msg
                  )
                );
              } else if (eventData.type === 'done') {
                setChatHistory((prev) =>
                  prev.map((msg) =>
                    msg.id === aiMsgId
                      ? {
                          ...msg,
                          isStreaming: false
                        }
                      : msg
                  )
                );
              }
            } catch (parseErr) {
              console.warn('Lỗi phân tích cú pháp SSE:', parseErr, jsonStr);
            }
          }
        }
      }
    } catch (err) {
      console.warn('[SSE] Thử fallback về endpoint đồng bộ /api/copilot/chat do:', err);
      try {
        const fallbackRes = await fetch('/api/copilot/chat', {
          method: 'POST',
          headers,
          body: JSON.stringify(payload)
        });

        if (fallbackRes.ok) {
          const fallbackData = await fallbackRes.json();
          setChatHistory((prev) =>
            prev.map((msg) =>
              msg.id === aiMsgId
                ? {
                    ...msg,
                    text: fallbackData.ai_response,
                    intent: fallbackData.intent,
                    intentBadge: fallbackData.intent_badge,
                    intentDetail: fallbackData.intent_detail,
                    dataSources: fallbackData.data_sources || [],
                    competitorsCount: fallbackData.competitors_count || 0,
                    matched: fallbackData.matched_insights,
                    isStreaming: false
                  }
                : msg
            )
          );
        } else {
          throw new Error('Fallback cũng không thành công');
        }
      } catch (fallbackErr) {
        setChatHistory((prev) =>
          prev.map((msg) =>
            msg.id === aiMsgId
              ? {
                  ...msg,
                  text: `⚠️ Rất tiếc, đã có lỗi kết nối tới máy chủ suy luận: ${err.message}. Vui lòng thử lại.`,
                  isStreaming: false
                }
              : msg
          )
        );
      }
    } finally {
      setLoading(false);
    }
  };

  // Nhấn Enter để gửi (Shift+Enter để xuống dòng)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Copy nội dung phản hồi hoặc lời thoại
  const handleCopy = (id, text, isZalo = false) => {
    let copyText = text;
    if (isZalo) {
      copyText = `[KỊCH BẢN THỰC CHIẾN TỪ CỐ VẤN F&B]\n\n${text}\n\n(MLAI Tactical Co-pilot)`;
    }
    navigator.clipboard.writeText(copyText);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const getModelName = (id) => {
    const found = metadata?.business_models?.find(m => m.id === parseInt(id));
    return found ? found.name : `Mô hình ${id}`;
  };

  const getProductNames = () => {
    if (!metadata?.products) return '';
    return selectedProductIds
      .map(id => metadata.products.find(p => p.id === id)?.name || id)
      .join(', ');
  };

  return (
    <div className="flex h-full w-full bg-slate-100 overflow-hidden relative font-sans">
      
      {/* ========================================================================= */}
      {/* CỘT BÊN TRÁI (LEFT SIDEBAR): TOÀN BỘ THÔNG TIN NHẬP & KỊCH BẢN            */}
      {/* ========================================================================= */}
      <aside 
        className={`${
          isSidebarOpen ? 'translate-x-0 w-80 lg:w-[350px]' : '-translate-x-full w-0 md:w-0'
        } fixed md:relative z-30 inset-y-0 left-0 bg-white border-r border-slate-200/90 flex flex-col h-full transition-all duration-300 ease-in-out shrink-0 shadow-lg md:shadow-none overflow-hidden`}
      >
        {/* 1. Header Sidebar: Nút tạo Cuộc trò chuyện mới & đóng sidebar trên mobile */}
        <div className="p-3.5 border-b border-slate-200/80 flex items-center justify-between gap-2 shrink-0 bg-slate-50/60">
          <button
            type="button"
            onClick={handleNewChat}
            className="flex-1 flex items-center justify-center space-x-2 py-2 px-3 bg-white hover:bg-indigo-50/60 text-slate-700 hover:text-indigo-700 border border-slate-200 hover:border-indigo-300 font-semibold text-xs rounded-xl transition shadow-xs cursor-pointer"
            title="Tạo cuộc hội thoại mới"
          >
            <Plus className="w-4 h-4 text-indigo-600" />
            <span>Cuộc trò chuyện mới</span>
          </button>

          {/* Nút đóng Sidebar trên màn hình di động */}
          <button
            type="button"
            onClick={() => setIsSidebarOpen(false)}
            className="md:hidden p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100"
            title="Thu gọn"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>

        {/* 2. Thân Sidebar: Cuộn độc lập (Khuôn thông tin quán + Kịch bản mẫu + Hệ thống) */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs text-slate-600">
          
          {/* KHỐI 1: KHUÔN THÔNG TIN QUÁN CỦA BẠN */}
          <div className="bg-slate-50/90 rounded-2xl border border-slate-200/90 p-3.5 space-y-3 shadow-xs">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200/70">
              <div className="flex items-center space-x-1.5 font-bold text-slate-800 text-[11px] uppercase tracking-wider">
                <Store className="w-3.5 h-3.5 text-indigo-600" />
                <span>Hồ sơ quán F&B</span>
              </div>
              
              {savedStrategy && !isEditingProfile ? (
                <button
                  type="button"
                  onClick={() => setIsEditingProfile(true)}
                  className="text-[10px] text-indigo-600 hover:text-indigo-800 font-bold flex items-center space-x-0.5 hover:underline cursor-pointer"
                >
                  <Edit3 className="w-3 h-3" />
                  <span>Sửa vị trí</span>
                </button>
              ) : savedStrategy && isEditingProfile ? (
                <button
                  type="button"
                  onClick={() => {
                    setModelId(savedStrategy.model_id);
                    setAddress(savedStrategy.address);
                    setSelectedProductIds(savedStrategy.product_ids);
                    setIsEditingProfile(false);
                  }}
                  className="text-[10px] text-slate-500 hover:text-slate-800 font-bold flex items-center space-x-0.5 cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Khôi phục</span>
                </button>
              ) : null}
            </div>

            {/* Trạng thái nạp hồ sơ */}
            {savedStrategy && !isEditingProfile ? (
              <div className="space-y-2">
                <div className="p-2 rounded-xl bg-emerald-50/80 border border-emerald-200/70 text-emerald-800 flex items-start space-x-2">
                  <BookmarkCheck className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                  <div className="text-[11px] leading-tight">
                    <span className="font-semibold block">Đã đồng bộ hồ sơ quán</span>
                    <span className="text-emerald-700/80 text-[10px]">Tự động đối chiếu CSDL theo vị trí này</span>
                  </div>
                </div>

                <div className="space-y-1.5 pt-1 text-[11px]">
                  <div>
                    <span className="text-slate-400 block text-[10px]">Vị trí quán:</span>
                    <span className="font-semibold text-slate-800 block truncate" title={address}>
                      {address || "Chưa xác định địa chỉ"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Mô hình:</span>
                    <span className="font-semibold text-slate-800">
                      {getModelName(modelId)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[10px]">Món chủ đạo:</span>
                    <span className="font-semibold text-slate-800 line-clamp-2">
                      {getProductNames() || "Chưa chọn món"}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Địa chỉ quán */}
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                    Địa chỉ quán (Quét đối thủ 1km)
                  </label>
                  <div className="relative">
                    <MapPin className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5 pointer-events-none" />
                    <input
                      type="text"
                      value={address}
                      onChange={(e) => setAddress(e.target.value)}
                      placeholder="VD: 268 Lý Thường Kiệt, Q10"
                      className="w-full pl-8 pr-2.5 py-1.5 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:ring-2 focus:ring-indigo-500 outline-none transition"
                    />
                  </div>
                </div>

                {/* Mô hình kinh doanh */}
                <div>
                  <label className="block text-[10px] font-bold text-slate-600 uppercase mb-1">
                    Mô hình kinh doanh
                  </label>
                  <div className="relative">
                    <Store className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5 pointer-events-none" />
                    <select
                      value={modelId}
                      onChange={(e) => setModelId(e.target.value)}
                      className="w-full pl-8 pr-2.5 py-1.5 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-800 focus:ring-2 focus:ring-indigo-500 outline-none transition"
                    >
                      {metadata?.business_models?.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Chọn 1-3 món */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-[10px] font-bold text-slate-600 uppercase">
                      Món chủ đạo:
                    </label>
                    <span className="text-[10px] text-slate-400">
                      {selectedProductIds.length}/3
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 max-h-24 overflow-y-auto p-1 bg-white rounded-xl border border-slate-200">
                    {metadata?.products?.map((p) => {
                      const isSelected = selectedProductIds.includes(p.id);
                      return (
                        <button
                          key={p.id}
                          type="button"
                          onClick={() => toggleProduct(p.id)}
                          className={`text-[10px] px-2 py-0.5 rounded-lg font-medium transition cursor-pointer ${
                            isSelected
                              ? 'bg-indigo-600 text-white shadow-xs'
                              : 'bg-slate-50 text-slate-600 border border-slate-200 hover:border-indigo-300'
                          }`}
                        >
                          {p.name}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* KHỐI 2: TÌNH HUỐNG SỰ CỐ KHẨN CẤP (QUICK PROMPTS) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between font-bold text-[11px] text-slate-700 uppercase tracking-wider">
              <div className="flex items-center space-x-1.5">
                <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                <span>Kịch bản sự cố mẫu</span>
              </div>
              <span className="text-[10px] text-slate-400 lowercase font-normal">
                (Click để hỏi)
              </span>
            </div>

            <div className="space-y-1.5">
              {quickCrises.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSend(item.query)}
                  disabled={loading}
                  className={`w-full p-2.5 text-left bg-slate-50/80 hover:bg-white border rounded-xl transition duration-150 group shadow-xs cursor-pointer ${
                    item.type === 'competitive'
                      ? 'border-slate-200 hover:border-amber-300'
                      : 'border-slate-200 hover:border-blue-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-0.5">
                    <span className={`text-[11px] font-bold block truncate ${
                      item.type === 'competitive' ? 'text-amber-900 group-hover:text-amber-700' : 'text-slate-800 group-hover:text-blue-700'
                    }`}>
                      {item.title}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${
                      item.type === 'competitive' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'
                    }`}>
                      {item.type === 'competitive' ? 'DB2-DB5' : 'DB3-DB4'}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-500 block line-clamp-2 leading-relaxed">
                    {item.query}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* KHỐI 3: HẠ TẦNG CSDL & MÔ HÌNH AI */}
          <div className="p-3 bg-slate-50/60 rounded-xl border border-slate-200/80 space-y-1.5 text-[10px] text-slate-500">
            <div className="font-bold text-slate-700 uppercase tracking-wider text-[10px] flex items-center space-x-1">
              <ShieldAlert className="w-3 h-3 text-indigo-500" />
              <span>Nguồn dữ liệu & AI Engine</span>
            </div>
            <div className="grid grid-cols-2 gap-1 text-[10px]">
              <div>• DB1: 24 Quận Huyện</div>
              <div>• DB2: Quét đối thủ 1km</div>
              <div>• DB3: 13 Rủi ro F&B</div>
              <div>• DB4: Bài học thực chiến</div>
              <div>• DB5: Sức mua thị trường</div>
              <div>• Vector: BGE-M3 (1024-d)</div>
            </div>
            <div className="pt-1 border-t border-slate-200/60 text-indigo-700 font-semibold">
              🤖 LLM: Qwen3.5 4B (Ollama Local)
            </div>
          </div>

        </div>

        {/* 3. Footer Sidebar: Thông tin tài khoản người dùng */}
        <div className="p-3 border-t border-slate-200/80 bg-slate-50/90 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
              {currentUser?.username ? currentUser.username[0].toUpperCase() : 'F'}
            </div>
            <div className="leading-tight">
              <span className="font-bold text-xs text-slate-800 block truncate max-w-[150px]">
                {currentUser?.full_name || currentUser?.username || 'Khách trải nghiệm'}
              </span>
              <span className="text-[10px] text-slate-400">
                {currentUser ? 'Chủ quán đã xác thực' : 'Chưa đăng nhập'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Backdrop mờ khi mở Sidebar trên Mobile */}
      {isSidebarOpen && (
        <div 
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 bg-slate-900/30 z-20 md:hidden backdrop-blur-xs"
        />
      )}

      {/* ========================================================================= */}
      {/* PHẦN CÒN LẠI BÊN PHẢI: KHUNG CHAT CỐ ĐỊNH PHONG CÁCH CHATGPT              */}
      {/* ========================================================================= */}
      <div className="flex-1 flex flex-col h-full bg-slate-50 relative overflow-hidden">
        
        {/* 1. Header Khung Chat cố định ở đỉnh */}
        <div className="h-14 px-4 sm:px-6 bg-white border-b border-slate-200 flex items-center justify-between shrink-0 shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-1.5 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition cursor-pointer"
              title={isSidebarOpen ? "Thu gọn cột thông tin" : "Mở rộng cột thông tin"}
            >
              {isSidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeft className="w-5 h-5" />}
            </button>

            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-xs sm:text-sm text-slate-800">
                  Trợ Lý Cố Vấn F&B Thực Chiến
                </span>
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block animate-pulse" title="Hệ thống Sẵn sàng" />
              </div>
              <div className="text-[11px] text-slate-400 hidden sm:block truncate max-w-md">
                {getModelName(modelId)} • {address || "Chưa nhập địa chỉ"}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={handleNewChat}
              className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition cursor-pointer"
              title="Làm mới cuộc trò chuyện"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 2. Vùng hiển thị tin nhắn (Cuộn độc lập, căn giữa chuẩn ChatGPT) */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 overscroll-contain">
          <div className="max-w-3xl mx-auto space-y-5">
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[92%] sm:max-w-[85%] rounded-3xl p-4 sm:p-5 space-y-3 ${
                    msg.sender === 'user'
                      ? 'bg-slate-900 text-white shadow-xs rounded-br-xs'
                      : 'bg-white border border-slate-200/90 text-slate-800 shadow-xs rounded-tl-xs'
                  }`}
                >
                  {/* Header tin nhắn AI */}
                  {msg.sender === 'ai' && (
                    <div className="flex items-center justify-between pb-2 border-b border-slate-200/70 text-xs">
                      <div className="flex items-center space-x-1.5 font-bold text-indigo-700">
                        <Store className="w-4 h-4" />
                        <span>Cố Vấn Thực Chiến (Qwen3.5 4B)</span>
                        {msg.isStreaming && (
                          <span className="text-[10px] font-normal px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 animate-pulse">
                            Đang truyền tải...
                          </span>
                        )}
                      </div>
                      <div className="flex items-center space-x-1">
                        <button
                          onClick={() => handleCopy(msg.id, msg.text, true)}
                          className="px-2 py-1 text-[11px] font-semibold text-slate-500 hover:text-indigo-700 hover:bg-indigo-50 rounded-lg transition flex items-center space-x-1 cursor-pointer"
                          title="Copy định dạng gửi Zalo"
                        >
                          <Share2 className="w-3.5 h-3.5" />
                          <span className="hidden sm:inline">Gửi Zalo</span>
                        </button>
                        <button
                          onClick={() => handleCopy(msg.id, msg.text, false)}
                          className="p-1 text-slate-400 hover:text-slate-700 transition rounded-lg hover:bg-slate-200/50 cursor-pointer"
                          title="Sao chép toàn bộ"
                        >
                          {copiedId === msg.id ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </div>
                  )}

                  {/* BANNER HIỂN THỊ CHẾ ĐỘ AGENT Ở ĐẦU CÂU TRẢ LỜI CỦA AI */}
                  {msg.sender === 'ai' && msg.intent && (
                    msg.intent === 'COMPETITIVE' ? (
                      <div className="p-3 rounded-2xl bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-amber-500/5 border border-amber-300 text-amber-950 text-xs shadow-xs">
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center space-x-1.5 font-bold text-amber-900">
                            <span className="text-base">🎯</span>
                            <span>{msg.intentBadge || "Chế độ: Phản công Cạnh tranh Vi mô"}</span>
                          </div>
                          {msg.competitorsCount > 0 && (
                            <span className="bg-amber-200/80 text-amber-900 text-[10px] px-2 py-0.5 rounded-full font-bold">
                              Quét {msg.competitorsCount} đối thủ 1km
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-amber-800/90 mt-1">
                          ⚡ Đã kích hoạt 4 CSDL: <strong>DB2</strong> (Đối thủ 1km) • <strong>DB3</strong> (Rủi ro F&B) • <strong>DB4</strong> (Kinh nghiệm đàm phán) • <strong>DB5</strong> (Sức mua thị trường).
                        </div>
                      </div>
                    ) : (
                      <div className="p-3 rounded-2xl bg-blue-50/90 border border-blue-200 text-blue-950 text-xs shadow-xs">
                        <div className="flex items-center space-x-1.5 font-bold text-blue-900">
                          <span className="text-base">⚙️</span>
                          <span>{msg.intentBadge || "Chế độ: Tối ưu Vận hành Nội bộ"}</span>
                        </div>
                        <div className="text-[11px] text-blue-800/90 mt-1">
                          ⚡ Đã kích hoạt 2 CSDL: <strong>DB3</strong> (Sự cố vận hành) • <strong>DB4</strong> (Bài học xương máu & Lời thoại thực chiến).
                        </div>
                      </div>
                    )
                  )}

                  {/* Nội dung câu trả lời */}
                  {msg.sender === 'ai' ? (
                    <div>
                      {msg.isStreaming && !msg.text ? (
                        <div className="flex items-center space-x-2 py-3 text-xs text-indigo-600 font-medium">
                          <div className="w-3.5 h-3.5 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                          <span>Đang định tuyến CSDL và khởi tạo kịch bản...</span>
                        </div>
                      ) : (
                        <div className="relative">
                          <FormattedMarkdown content={msg.text} />
                          {msg.isStreaming && (
                            <span className="inline-block w-2 h-4 bg-indigo-600 animate-pulse ml-1 align-middle rounded-xs" />
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-sans">
                      {msg.text}
                    </div>
                  )}

                  {/* Dấu vết tra cứu dữ liệu CSDL */}
                  {msg.matched && (
                    <div className="pt-2 border-t border-slate-200/50 flex flex-wrap gap-2 text-[10px] text-slate-500">
                      {msg.intent === 'COMPETITIVE' && msg.matched.competitors_found > 0 && (
                        <span className="bg-amber-50 text-amber-800 px-2 py-0.5 rounded border border-amber-200 font-medium">
                          DB2: {msg.matched.competitors_found} đối thủ vi mô
                        </span>
                      )}
                      <span className="bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                        DB3: {msg.matched.problems_found} sự cố rủi ro
                      </span>
                      <span className="bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                        DB4: {msg.matched.lessons_found} bài học xương máu
                      </span>
                      {msg.intent === 'COMPETITIVE' && msg.matched.market_found > 0 && (
                        <span className="bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                          DB5: Sức mua & giờ cao điểm
                        </span>
                      )}
                      <span className="bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                        Vector BGE-M3: 1024-d
                      </span>
                    </div>
                  )}

                  <div className={`text-[10px] text-right ${msg.sender === 'user' ? 'text-slate-400' : 'text-slate-400'}`}>
                    {msg.timestamp}
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 3. Khung nhập liệu CỐ ĐỊNH Ở DƯỚI CÙNG (Sticky Bottom Input) */}
        <div className="p-3 sm:p-4 bg-white/95 backdrop-blur-md border-t border-slate-200 shrink-0">
          <div className="max-w-3xl mx-auto">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="relative flex items-end bg-slate-50 border border-slate-300/80 rounded-2xl sm:rounded-3xl shadow-xs focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:bg-white transition p-1.5 sm:p-2"
            >
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Hỏi Cố Vấn F&B về sự cố kinh doanh (Nhấn Enter để gửi, Shift+Enter xuống dòng)..."
                rows={1}
                className="flex-1 max-h-36 resize-none bg-transparent px-3 py-2 text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:outline-none"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className={`p-2.5 sm:p-3 rounded-xl sm:rounded-2xl text-white font-bold flex items-center justify-center transition shadow-sm ${
                  loading || !query.trim()
                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                    : 'bg-indigo-600 hover:bg-indigo-700 text-white active:scale-95 shadow-indigo-600/20 cursor-pointer'
                }`}
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </form>
            <div className="text-[11px] text-slate-400 mt-2 text-center flex items-center justify-center space-x-2 sm:space-x-3">
              <span>⚡ Streaming Real-time SSE</span>
              <span>•</span>
              <span>🧠 Bộ nhớ hội thoại đa lượt</span>
              <span>•</span>
              <span>🎯 Dual-Engine Agentic</span>
            </div>
          </div>
        </div>

      </div>

    </div>
  );
}
