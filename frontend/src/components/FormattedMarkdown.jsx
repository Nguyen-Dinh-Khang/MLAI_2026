import React, { useState } from 'react';
import { CheckSquare, Square, ChevronRight, Quote, MessageCircle } from 'lucide-react';

/**
 * FormattedMarkdown - Component render văn bản Markdown thông minh
 * Chuyên xử lý định dạng trả về từ LLM:
 * 1. Tiêu đề "###": Làm lớn hơn, có thanh màu nhấn bên trái, nổi bật rõ ràng
 * 2. In đậm "**": Làm đậm rõ rệt (font-bold text-slate-900)
 * 3. Bullet points "- ", "* ": Biến thành danh sách đẹp mắt có chấm tròn màu
 * 4. Checkbox "- [ ]", "- [x]": Biến thành ô tick tương tác người dùng có thể bấm vào
 * 5. Trích dẫn / Lời thoại "> " hoặc "Lời thoại:": Đóng khung hội thoại nổi bật
 * 6. Danh sách số "1. ", "2. ": Đánh số màu xanh nổi bật
 */
export default function FormattedMarkdown({ content, className = '' }) {
  if (!content) return null;

  // State lưu trữ các checkbox người dùng đã tick chọn
  const [checkedItems, setCheckedItems] = useState({});

  const toggleCheck = (idx) => {
    setCheckedItems(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  /**
   * Phân tích các định dạng nội dòng (Inline Formatting):
   * - **chữ đậm** -> <strong>
   * - *chữ nghiêng* -> <em>
   * - `code` -> <code>
   * - "lời thoại trong ngoặc kép" -> highlight
   */
  const renderInline = (text) => {
    if (!text) return null;

    // Tách chuỗi theo các token **bold**, *italic*, `code`
    const parts = [];
    let remaining = text;
    let keyCounter = 0;

    // Regex tổng hợp bắt: **bold**, *italic*, `code`
    const inlineRegex = /(\*\*.*?\*\*|\*.*?\*|`.*?`)/g;
    const tokens = remaining.split(inlineRegex);

    return tokens.map((token, i) => {
      if (token.startsWith('**') && token.endsWith('**') && token.length >= 4) {
        // XỬ LÝ CHỮ IN ĐẬM **...**
        const innerText = token.slice(2, -2);
        return (
          <strong key={i} className="font-extrabold text-slate-950 bg-amber-50/70 px-1 py-0.5 rounded border border-amber-200/50">
            {innerText}
          </strong>
        );
      } else if (token.startsWith('*') && token.endsWith('*') && token.length >= 2) {
        // XỬ LÝ CHỮ IN NGHIÊNG *...*
        const innerText = token.slice(1, -1);
        return (
          <em key={i} className="italic text-slate-700">
            {innerText}
          </em>
        );
      } else if (token.startsWith('`') && token.endsWith('`') && token.length >= 2) {
        // XỬ LÝ CODE / KEYWORD `...`
        const innerText = token.slice(1, -1);
        return (
          <code key={i} className="font-mono text-xs bg-slate-100 text-blue-700 px-1.5 py-0.5 rounded border border-slate-200">
            {innerText}
          </code>
        );
      }
      return token;
    });
  };

  // Tách văn bản thành các dòng để duyệt
  const lines = content.split('\n');

  return (
    <div className={`space-y-2 text-slate-700 leading-relaxed ${className}`}>
      {lines.map((line, idx) => {
        const trimmed = line.trim();

        // 1. DÒNG TRỐNG
        if (!trimmed) {
          return <div key={idx} className="h-1.5" />;
        }

        // 2. TIÊU ĐỀ CẤP 3: "### " (Làm lớn, đậm, có viền màu xanh nổi bật)
        if (trimmed.startsWith('### ')) {
          const headingText = trimmed.replace(/^###\s+/, '');
          return (
            <div 
              key={idx} 
              className="mt-6 mb-3 pt-2 first:mt-0 first:pt-0"
            >
              <div className="flex items-center space-x-2.5 p-2.5 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50/40 border-l-4 border-blue-600 border border-blue-100 shadow-xs">
                <span className="w-2 h-2 rounded-full bg-blue-600 flex-shrink-0 animate-pulse"></span>
                <h3 className="font-black text-base sm:text-lg text-slate-900 tracking-tight">
                  {renderInline(headingText)}
                </h3>
              </div>
            </div>
          );
        }

        // 3. TIÊU ĐỀ CẤP 2: "## "
        if (trimmed.startsWith('## ')) {
          const headingText = trimmed.replace(/^##\s+/, '');
          return (
            <div key={idx} className="mt-7 mb-3">
              <div className="p-3 rounded-xl bg-indigo-50 border-l-4 border-indigo-600 border border-indigo-100">
                <h2 className="font-black text-lg sm:text-xl text-indigo-950 tracking-tight">
                  {renderInline(headingText)}
                </h2>
              </div>
            </div>
          );
        }

        // 4. TIÊU ĐỀ CẤP 1: "# "
        if (trimmed.startsWith('# ')) {
          const headingText = trimmed.replace(/^#\s+/, '');
          return (
            <h1 key={idx} className="font-black text-xl sm:text-2xl text-blue-900 mt-6 mb-3 pb-2 border-b border-slate-200">
              {renderInline(headingText)}
            </h1>
          );
        }

        // 5. CHECKBOX INTERACTIVE: "- [ ] " hoặc "- [x] "
        if (trimmed.startsWith('- [ ] ') || trimmed.startsWith('- [x] ') || trimmed.startsWith('[ ] ') || trimmed.startsWith('[x] ')) {
          const isInitiallyChecked = trimmed.includes('[x]');
          const isChecked = checkedItems[idx] !== undefined ? checkedItems[idx] : isInitiallyChecked;
          const cleanText = trimmed.replace(/^(-\s*)?\[(x|\s)\]\s*/, '');

          return (
            <div 
              key={idx}
              onClick={() => toggleCheck(idx)}
              className={`flex items-start space-x-3 p-2.5 my-1 rounded-xl border transition-all cursor-pointer select-none ${
                isChecked
                  ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                  : 'bg-white hover:bg-slate-50 border-slate-200 text-slate-800'
              }`}
            >
              <button type="button" className="mt-0.5 flex-shrink-0 text-blue-600">
                {isChecked ? (
                  <CheckSquare className="w-4 h-4 text-emerald-600" />
                ) : (
                  <Square className="w-4 h-4 text-slate-400 hover:text-blue-600" />
                )}
              </button>
              <span className={`text-xs sm:text-sm font-medium leading-relaxed ${isChecked ? 'line-through text-emerald-700/70' : ''}`}>
                {renderInline(cleanText)}
              </span>
            </div>
          );
        }

        // 6. LỜI THOẠI MẪU: Bắt các dòng có chứa "Lời thoại:" hoặc trích dẫn
        if (trimmed.includes('Lời thoại') || trimmed.startsWith('> ')) {
          const cleanText = trimmed.replace(/^>\s*/, '');
          return (
            <div key={idx} className="my-2 p-3 rounded-xl bg-amber-50/80 border-l-4 border-amber-500 border border-amber-200/60 shadow-xs flex items-start space-x-2.5">
              <MessageCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="text-xs sm:text-sm font-medium text-amber-950 italic leading-relaxed">
                {renderInline(cleanText)}
              </div>
            </div>
          );
        }

        // 7. GẠCH ĐẦU DÒNG (BULLET POINTS): "- " hoặc "* "
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          const bulletText = trimmed.replace(/^[-*]\s+/, '');
          return (
            <div key={idx} className="flex items-start space-x-2.5 my-1.5 pl-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-2 flex-shrink-0"></span>
              <div className="text-xs sm:text-sm text-slate-800 leading-relaxed font-normal">
                {renderInline(bulletText)}
              </div>
            </div>
          );
        }

        // 8. DANH SÁCH ĐÁNH SỐ: "1. ", "2. ", v.v.
        const numberedMatch = trimmed.match(/^(\d+)\.\s+(.*)/);
        if (numberedMatch) {
          const num = numberedMatch[1];
          const text = numberedMatch[2];
          return (
            <div key={idx} className="flex items-start space-x-2.5 my-1.5 pl-2">
              <span className="font-extrabold text-blue-600 text-xs sm:text-sm flex-shrink-0 mt-0.5">
                {num}.
              </span>
              <div className="text-xs sm:text-sm text-slate-800 leading-relaxed">
                {renderInline(text)}
              </div>
            </div>
          );
        }

        // 9. ĐƯỜNG PHÂN CÁCH NGANG: "---"
        if (trimmed === '---' || trimmed === '***') {
          return <hr key={idx} className="my-4 border-slate-200" />;
        }

        // 10. ĐOẠN VĂN THÔNG THƯỜNG
        return (
          <p key={idx} className="text-xs sm:text-sm text-slate-800 leading-relaxed my-1">
            {renderInline(line)}
          </p>
        );
      })}
    </div>
  );
}
