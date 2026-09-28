import React, { useState, useEffect } from 'react';
import { 
  MessageSquare, Send, Store, Sparkles, AlertCircle, 
  CheckSquare, Copy, Check, Clock, TrendingUp, HelpCircle, BookmarkCheck
} from 'lucide-react';
import FormattedMarkdown from './FormattedMarkdown';

/**
 * TacticalCopilot - Giao diện 2: Trợ lý Chiến thuật Đồng hành (Day 1 - 365)
 * Dành cho người đã mở quán hoặc đang trong quá trình vận hành hàng ngày.
 * Gặp sự cố thực tế nào, hỏi ngay để nhận Checklist 24h & Lời thoại đàm phán từng câu.
 * Tự động đồng bộ mô hình kinh doanh và chiến lược cá nhân đã lưu.
 */
export default function TacticalCopilot({ metadata, currentUser, savedStrategy }) {
  const [modelId, setModelId] = useState(105); // Mặc định Kiosk / Xe đẩy
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  // Tự động đồng bộ mô hình kinh doanh từ kế sách đã lưu của người dùng
  useEffect(() => {
    if (savedStrategy?.model_id) {
      setModelId(savedStrategy.model_id);
    }
  }, [savedStrategy]);
  const [chatHistory, setChatHistory] = useState([
    {
      id: 1,
      sender: 'ai',
      text: `Xin chào! Tôi là Trợ lý Cố vấn Kinh doanh thực chiến. 
Bạn đang gặp sự cố hay khúc mắc gì trong quá trình bán hàng (vắng khách, chủ nhà tăng giá, nhân sự nghỉ việc, khách than đợi lâu...)? 
Hãy chọn mô hình quán bên trên và gõ câu hỏi cụ thể, tôi sẽ tra cứu bài học xương máu trong CSDL thực tế để đưa ra checklist xử lý ngay trong 24h cho bạn.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [copiedId, setCopiedId] = useState(null);

  // Danh sách các tình huống sự cố thực tế phổ biến để bấm hỏi nhanh
  const quickCrises = [
    {
      title: "Khách chê đợi lâu bỏ đi",
      query: "Quán tôi mở được 2 tuần cạnh trường Đại học. Mấy hôm nay khách than đợi lâu quá nên bỏ đi sang quán khác. Tôi chỉ có 2 người làm, làm sao để phục vụ nhanh hơn mà không cần thuê thêm người?"
    },
    {
      title: "Chủ nhà đòi tăng giá thuê",
      query: "Quán mới bán được 6 tháng vừa có lượng khách quen ổn định thì chủ nhà thông báo tăng tiền thuê thêm 30% vào tháng tới. Tôi nên đàm phán thế nào để giữ giá cũ hoặc không bị mất cọc?"
    },
    {
      title: "Quán vắng hoe sau khai trương",
      query: "Tuần lễ khai trương giảm giá thì đông khách, nhưng vừa hết khuyến mãi là quán vắng hoe, mỗi ngày chỉ lác đác vài người. Làm sao để kéo khách quay lại mà không bị phụ thuộc vào giảm giá?"
    },
    {
      title: "Đối thủ sát vách phá giá",
      query: "Có quán mới mở sát vách bán món giống hệt quán tôi nhưng giá rẻ hơn 20% và tặng kèm trà đá. Khách quen của tôi bị hút qua đó khá nhiều, tôi phải đối phó thế nào?"
    }
  ];

  // Gửi câu hỏi sự cố tới FastAPI
  const handleSend = async (customQuery = null) => {
    const textToSend = customQuery || query;
    if (!textToSend.trim() || loading) return;

    const userMessage = {
      id: Date.now(),
      sender: 'user',
      text: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setChatHistory((prev) => [...prev, userMessage]);
    setQuery('');
    setLoading(true);

    try {
      const response = await fetch('/api/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: textToSend.trim(),
          model_id: modelId ? parseInt(modelId) : null
        })
      });

      if (!response.ok) {
        throw new Error('Không thể nhận phản hồi từ trợ lý AI');
      }

      const data = await response.json();
      const aiMessage = {
        id: Date.now() + 1,
        sender: 'ai',
        text: data.ai_response,
        context: data.distilled_context,
        matched: data.matched_insights,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatHistory((prev) => [...prev, aiMessage]);
    } catch (err) {
      const errorMsg = {
        id: Date.now() + 1,
        sender: 'ai',
        text: `⚠️ Rất tiếc, đã có lỗi kết nối tới máy chủ suy luận: ${err.message}. Vui lòng thử lại.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setChatHistory((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Copy nội dung phản hồi hoặc lời thoại
  const handleCopy = (id, text) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      
      {/* THANH ĐIỀU KHIỂN ĐẦU TRANG: CHỌN NGỮ CẢNH MÔ HÌNH */}
      <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2 text-indigo-700">
          <Store className="w-5 h-5" />
          <span className="font-bold text-sm text-slate-800">Ngữ Cảnh Mô Hình Kinh Doanh:</span>
          {savedStrategy && (
            <span className="text-[10px] px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-semibold flex items-center space-x-1">
              <BookmarkCheck className="w-3 h-3" />
              <span>Đã đồng bộ từ hồ sơ quán</span>
            </span>
          )}
        </div>
        <div className="w-full sm:w-72">
          <select
            value={modelId}
            onChange={(e) => setModelId(e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm font-semibold text-slate-800 focus:ring-2 focus:ring-indigo-500 outline-none transition"
          >
            {metadata?.business_models?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* CÁC NÚT TÌNH HUỐNG SỰ CỐ KHẨN CẤP (QUICK CHIPS) */}
      <div className="space-y-2">
        <div className="flex items-center space-x-2 text-xs font-bold text-slate-500 uppercase tracking-wider">
          <Sparkles className="w-4 h-4 text-indigo-500" />
          <span>Gợi ý các sự cố thực tế thường gặp nhất:</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {quickCrises.map((item, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSend(item.query)}
              disabled={loading}
              className="p-3 text-left bg-white hover:bg-indigo-50/70 border border-slate-200 hover:border-indigo-300 rounded-xl transition duration-150 group shadow-xs"
            >
              <span className="text-xs font-bold text-slate-800 group-hover:text-indigo-700 block">
                {item.title}
              </span>
              <span className="text-[10px] text-slate-500 block truncate mt-0.5">
                {item.query}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* KHUNG CHAT LỊCH SỬ ĐỐI THOẠI */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm flex flex-col h-[560px]">
        
        {/* VÙNG HIỂN THỊ NỘI DUNG CHAT */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {chatHistory.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] sm:max-w-[80%] rounded-2xl p-4 space-y-2 ${
                  msg.sender === 'user'
                    ? 'bg-gradient-to-r from-indigo-600 to-blue-600 text-white shadow-sm rounded-br-none'
                    : 'bg-slate-50 border border-slate-200 text-slate-800 shadow-xs rounded-bl-none'
                }`}
              >
                {/* Header tin nhắn AI */}
                {msg.sender === 'ai' && (
                  <div className="flex items-center justify-between pb-2 border-b border-slate-200/70 text-xs">
                    <div className="flex items-center space-x-1.5 font-bold text-indigo-700">
                      <Store className="w-4 h-4" />
                      <span>Cố Vấn Thực Chiến (Qwen3.5 4B)</span>
                    </div>
                    <button
                      onClick={() => handleCopy(msg.id, msg.text)}
                      className="p-1 text-slate-400 hover:text-slate-700 transition"
                      title="Copy toàn bộ kịch bản"
                    >
                      {copiedId === msg.id ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                )}

                {/* Nội dung câu trả lời */}
                {msg.sender === 'ai' ? (
                  <FormattedMarkdown content={msg.text} />
                ) : (
                  <div className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-sans">
                    {msg.text}
                  </div>
                )}

                {/* Dấu vết tra cứu dữ liệu CSDL nếu có */}
                {msg.matched && (
                  <div className="pt-2 border-t border-slate-200/50 flex flex-wrap gap-2 text-[10px] text-slate-500">
                    <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                      DB3 Sự cố: {msg.matched.problems_found} bài học
                    </span>
                    <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                      DB4 Thực chiến: {msg.matched.lessons_found} case study
                    </span>
                    <span className="bg-white px-2 py-0.5 rounded border border-slate-200">
                      Vector BGE-M3 Cosine Search: Thành công
                    </span>
                  </div>
                )}

                <div className={`text-[10px] text-right ${msg.sender === 'user' ? 'text-blue-100' : 'text-slate-400'}`}>
                  {msg.timestamp}
                </div>
              </div>
            </div>
          ))}

          {/* Loading indicator khi AI đang suy luận */}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-slate-50 border border-slate-200 rounded-2xl rounded-bl-none p-4 text-xs text-slate-600 flex items-center space-x-3 shadow-xs">
                <div className="w-4 h-4 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
                <span>Đang tra cứu bài học trong CSDL & Soạn kịch bản 24h qua Qwen3.5 4B...</span>
              </div>
            </div>
          )}
        </div>

        {/* KHUNG NHẬP LIỆU CÂU HỎI */}
        <div className="p-4 bg-slate-50/80 border-t border-slate-200 rounded-b-2xl">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center space-x-2"
          >
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Nhập bất kỳ sự cố thực tế nào (Ví dụ: Bị bùng đơn trên app, thợ pha chế tự ý nghỉ việc...)"
              className="flex-1 px-4 py-3 bg-white border border-slate-200 rounded-xl text-xs sm:text-sm focus:ring-2 focus:ring-indigo-500 outline-none transition"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !query.trim()}
              className={`p-3 rounded-xl text-white font-bold flex items-center justify-center transition shadow-md ${
                loading || !query.trim()
                  ? 'bg-slate-300 cursor-not-allowed shadow-none'
                  : 'bg-indigo-600 hover:bg-indigo-700 shadow-indigo-500/20 active:scale-95'
              }`}
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
          <div className="text-[11px] text-slate-400 mt-2 text-center">
            Mẹo: Mô tả sự cố càng chi tiết, trợ lý càng trích xuất checklist và lời thoại đàm phán sát thực tế nhất.
          </div>
        </div>

      </div>

    </div>
  );
}
