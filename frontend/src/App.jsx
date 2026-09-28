import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import FeasibilityScanner from './components/FeasibilityScanner';
import TacticalCopilot from './components/TacticalCopilot';

/**
 * App - Ứng dụng chính của Nền tảng Ra quyết định (Client App)
 * Tích hợp trọn vẹn mô hình Song Trụ (Dual-Engine):
 * - Tab 1 (Day 0): Máy quét Thẩm định Ý tưởng
 * - Tab 2 (Day 1 - 365): Trợ lý Chiến thuật Đồng hành
 */
export default function App() {
  const [activeTab, setActiveTab] = useState('scanner');
  const [metadata, setMetadata] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);
  const [loadingMeta, setLoadingMeta] = useState(true);

  // User Authentication & Saved Strategy State
  const [currentUser, setCurrentUser] = useState(null);
  const [savedStrategy, setSavedStrategy] = useState(null);

  // Tải Kế sách chiến lược đang áp dụng của người dùng từ MongoDB
  const fetchActiveStrategy = async (token) => {
    try {
      const res = await fetch('/api/user/strategy/active', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        if (data.has_strategy && data.strategy) {
          setSavedStrategy(data.strategy);
        } else {
          setSavedStrategy(null);
        }
      }
    } catch (err) {
      console.error('Lỗi khi tải kế sách cá nhân:', err);
    }
  };

  // Khởi tạo: Nạp metadata, kiểm tra sức khỏe hệ thống và phiên đăng nhập hiện tại
  useEffect(() => {
    const initApp = async () => {
      try {
        const [metaRes, healthRes] = await Promise.all([
          fetch('/api/metadata'),
          fetch('/api/health')
        ]);
        if (metaRes.ok) {
          const metaData = await metaRes.json();
          setMetadata(metaData);
        }
        if (healthRes.ok) {
          const healthData = await healthRes.json();
          setSystemStatus(healthData);
        }

        // Kiểm tra token đăng nhập trong localStorage
        const token = localStorage.getItem('mlai_user_token');
        if (token) {
          const meRes = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (meRes.ok) {
            const userData = await meRes.json();
            setCurrentUser(userData);
            // Tự động tải kế sách chiến lược của user
            await fetchActiveStrategy(token);
          } else {
            localStorage.removeItem('mlai_user_token');
          }
        }
      } catch (err) {
        console.error('Lỗi khi khởi tạo ứng dụng:', err);
      } finally {
        setLoadingMeta(false);
      }
    };

    initApp();
  }, []);

  // Xử lý khi Đăng nhập / Đăng ký thành công
  const handleLoginSuccess = async (token, user) => {
    localStorage.setItem('mlai_user_token', token);
    setCurrentUser(user);
    await fetchActiveStrategy(token);
  };

  // Xử lý khi Đăng xuất
  const handleLogout = async () => {
    const token = localStorage.getItem('mlai_user_token');
    if (token) {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => {});
    }
    localStorage.removeItem('mlai_user_token');
    setCurrentUser(null);
    setSavedStrategy(null);
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      
      {/* 1. Header Điều hướng */}
      <Navbar 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        systemStatus={systemStatus}
        currentUser={currentUser}
        onLoginSuccess={handleLoginSuccess}
        onLogout={handleLogout}
      />

      {/* 2. Vùng nội dung chính */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {loadingMeta ? (
          <div className="h-96 flex flex-col items-center justify-center space-y-4">
            <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-xs text-slate-500 font-medium">Đang khởi tạo danh mục và kết nối CSDL...</p>
          </div>
        ) : (
          <>
            {activeTab === 'scanner' && (
              <FeasibilityScanner 
                metadata={metadata}
                currentUser={currentUser}
                savedStrategy={savedStrategy}
                onStrategySaved={(newStrat) => setSavedStrategy(newStrat)}
              />
            )}

            {activeTab === 'copilot' && (
              <TacticalCopilot 
                metadata={metadata}
                currentUser={currentUser}
                savedStrategy={savedStrategy}
              />
            )}
          </>
        )}

      </main>

      {/* 3. Footer */}
      <footer className="border-t border-slate-200 bg-white py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-500 space-y-1">
          <p className="font-semibold text-slate-700">
            MLAI Decision Intelligence & Tactical Co-pilot Platform © 2026
          </p>
          <p>
            Mô hình Song Trụ (Dual-Engine): Máy quét Thẩm định (Day 0) & Trợ lý Đồng hành (Day 1 - 365).
          </p>
          <p className="text-[11px] text-slate-400">
            Sử dụng 5 CSDL chuẩn hóa (MongoDB Atlas) • Embedding BAAI/bge-m3 • LLM Qwen3.5 4B qua Ollama
          </p>
        </div>
      </footer>

    </div>
  );
}
