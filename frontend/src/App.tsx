import React, { useState } from 'react';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TranslationPage from './components/TranslationPage';
import GlossaryManager from './components/GlossaryManager';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1 },
  },
});

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<'translation' | 'glossary'>('translation');

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          token: {
            colorPrimary: '#2d4a3e',
            colorBgContainer: '#ffffff',
            borderRadius: 5,
            fontFamily: "'DM Sans', sans-serif",
            colorText: '#1a1816',
            colorTextSecondary: '#5c5751',
            colorBorder: '#e4e0d8',
            colorBgElevated: '#ffffff',
          },
        }}
      >
        <AntApp>
          <div className="app">
            <nav className="topnav">
              <div className="nav-logo">
                <span className="wordmark">Translator</span>
                <span className="edition">LLM Edition</span>
              </div>

              <div className="nav-tabs">
                <button
                  className={`nav-tab ${currentPage === 'translation' ? 'active' : ''}`}
                  onClick={() => setCurrentPage('translation')}
                >
                  翻译
                </button>
                <button
                  className={`nav-tab ${currentPage === 'glossary' ? 'active' : ''}`}
                  onClick={() => setCurrentPage('glossary')}
                >
                  术语表
                </button>
              </div>

              <div className="nav-meta">
                <div className="online-dot" />
                Worker 在线
              </div>
            </nav>

            {currentPage === 'translation' ? <TranslationPage /> : <GlossaryManager />}
          </div>
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
};

export default App;
