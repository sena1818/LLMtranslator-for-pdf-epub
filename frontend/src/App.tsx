/**
 * 主应用组件
 */
import React, { useState } from 'react';
import { Layout, Menu, ConfigProvider, theme } from 'antd';
import { TranslationOutlined, BookOutlined } from '@ant-design/icons';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TranslationPage from './components/TranslationPage';
import GlossaryManager from './components/GlossaryManager';
import zhCN from 'antd/locale/zh_CN';

const { Header, Content } = Layout;

// 创建 React Query 客户端
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

type MenuItem = {
  key: string;
  icon: React.ReactNode;
  label: string;
};

const menuItems: MenuItem[] = [
  {
    key: 'translation',
    icon: <TranslationOutlined />,
    label: '翻译',
  },
  {
    key: 'glossary',
    icon: <BookOutlined />,
    label: '术语表管理',
  },
];

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<string>('translation');

  const renderContent = () => {
    switch (currentPage) {
      case 'translation':
        return <TranslationPage />;
      case 'glossary':
        return <GlossaryManager />;
      default:
        return <TranslationPage />;
    }
  };

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        locale={zhCN}
        theme={{
          algorithm: theme.defaultAlgorithm,
          token: {
            colorPrimary: '#1890ff',
          },
        }}
      >
        <Layout style={{ minHeight: '100vh' }}>
          <Header style={{ display: 'flex', alignItems: 'center', background: '#001529' }}>
            <div
              style={{
                color: 'white',
                fontSize: '20px',
                fontWeight: 'bold',
                marginRight: '50px',
              }}
            >
              AI 翻译系统
            </div>
            <Menu
              theme="dark"
              mode="horizontal"
              selectedKeys={[currentPage]}
              items={menuItems}
              onClick={({ key }) => setCurrentPage(key)}
              style={{ flex: 1, minWidth: 0 }}
            />
          </Header>
          <Content style={{ background: '#f0f2f5' }}>
            {renderContent()}
          </Content>
        </Layout>
      </ConfigProvider>
    </QueryClientProvider>
  );
};

export default App;
