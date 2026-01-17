/**
 * 翻译页面组件 - 美化版
 */
import React, { useState } from 'react';
import {
  Upload,
  Select,
  Button,
  Progress,
  Card,
  Space,
  Typography,
  Alert,
  message,
  Table,
  Tag,
  Switch,
  Tooltip,
  Row,
  Col,
  Statistic,
} from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  ReloadOutlined,
  FileTextOutlined,
  TranslationOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createTranslationTask,
  getTaskList,
  getTaskStatus,
  deleteTask,
  downloadResult,
  getGlossaryList,
  type TranslationTask,
  type Glossary,
} from '../services/api';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { Dragger } = Upload;

const TranslationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [selectedGlossary, setSelectedGlossary] = useState<string | undefined>(undefined);
  const [bilingual, setBilingual] = useState<boolean>(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  // 获取术语表列表
  const { data: glossaries = [] } = useQuery<Glossary[]>({
    queryKey: ['glossaries'],
    queryFn: getGlossaryList,
  });

  // 获取任务列表
  const { data: taskListData, isLoading: isLoadingTasks } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => getTaskList(0, 20),
    refetchInterval: 3000,
  });

  // 查询当前任务状态
  const { data: currentTask } = useQuery<TranslationTask>({
    queryKey: ['task', currentTaskId],
    queryFn: () => getTaskStatus(currentTaskId!),
    enabled: !!currentTaskId,
    refetchInterval: (query) => {
      const task = query.state.data;
      if (task && (task.status === 'completed' || task.status === 'failed')) {
        return false;
      }
      return 2000;
    },
  });

  // 创建翻译任务
  const createTaskMutation = useMutation({
    mutationFn: ({ file, glossaryId, bilingual }: { file: File; glossaryId?: string; bilingual: boolean }) =>
      createTranslationTask(file, glossaryId, bilingual),
    onSuccess: (task) => {
      message.success('翻译任务已创建');
      setCurrentTaskId(task.task_id);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setFileList([]);
    },
    onError: (error: Error) => {
      message.error(`创建任务失败: ${error.message}`);
    },
  });

  // 删除任务
  const deleteTaskMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      message.success('任务已删除');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: Error) => {
      message.error(`删除失败: ${error.message}`);
    },
  });

  // 文件上传配置
  const uploadProps = {
    fileList,
    beforeUpload: (file: File) => {
      const isValidType =
        file.name.endsWith('.md') ||
        file.name.endsWith('.pdf') ||
        file.name.endsWith('.epub');

      if (!isValidType) {
        message.error('只支持 Markdown (.md), PDF (.pdf), EPUB (.epub) 文件');
        return false;
      }

      setFileList([file as unknown as UploadFile]);
      return false;
    },
    onRemove: () => {
      setFileList([]);
    },
    maxCount: 1,
  };

  // 开始翻译
  const handleStartTranslation = () => {
    if (fileList.length === 0) {
      message.warning('请先上传文件');
      return;
    }

    const file = fileList[0] as unknown as File;
    createTaskMutation.mutate({ file, glossaryId: selectedGlossary, bilingual });
  };

  // 任务状态标签
  const getStatusTag = (status: string) => {
    const statusMap = {
      pending: { color: 'default', text: '等待中', icon: <ClockCircleOutlined /> },
      processing: { color: 'processing', text: '翻译中', icon: <ThunderboltOutlined spin /> },
      completed: { color: 'success', text: '已完成', icon: <CheckCircleOutlined /> },
      failed: { color: 'error', text: '失败', icon: null },
    };
    const config = statusMap[status as keyof typeof statusMap] || statusMap.pending;
    return <Tag color={config.color} icon={config.icon}>{config.text}</Tag>;
  };

  // 统计数据
  const completedTasks = taskListData?.tasks?.filter(t => t.status === 'completed').length || 0;
  const processingTasks = taskListData?.tasks?.filter(t => t.status === 'processing').length || 0;

  // 任务列表表格列配置
  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      width: 200,
      ellipsis: true,
      render: (filename: string, record: TranslationTask) => (
        <Space>
          <FileTextOutlined style={{ color: '#1890ff' }} />
          <span>{filename}</span>
          {record.bilingual && <Tag color="blue" style={{ fontSize: '10px' }}>双语</Tag>}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '进度',
      key: 'progress',
      width: 180,
      render: (_: unknown, record: TranslationTask) => (
        <Progress
          percent={Math.round(record.progress.percentage)}
          size="small"
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
          status={
            record.status === 'failed'
              ? 'exception'
              : record.status === 'completed'
              ? 'success'
              : 'active'
          }
        />
      ),
    },
    {
      title: '速度',
      dataIndex: ['progress', 'speed'],
      key: 'speed',
      width: 100,
      render: (speed: number) => (
        <Text type="secondary">{speed.toFixed(1)} 块/分</Text>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (time: string) => (
        <Text type="secondary" style={{ fontSize: '12px' }}>
          {new Date(time).toLocaleString('zh-CN')}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 140,
      render: (_: unknown, record: TranslationTask) => (
        <Space>
          {record.status === 'completed' && record.result_url && (
            <Button
              type="primary"
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => window.open(downloadResult(record.task_id), '_blank')}
            >
              下载
            </Button>
          )}
          {(record.status === 'completed' || record.status === 'failed') && (
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => deleteTaskMutation.mutate(record.task_id)}
            />
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>

        {/* 页面标题 */}
        <div style={{ textAlign: 'center', marginBottom: '16px' }}>
          <Title level={2} style={{ marginBottom: '8px' }}>
            <TranslationOutlined style={{ marginRight: '12px', color: '#1890ff' }} />
            AI 翻译系统
          </Title>
          <Paragraph type="secondary">
            支持 PDF、EPUB、Markdown 文件翻译，专为哲学文本优化
          </Paragraph>
        </div>

        {/* 统计卡片 */}
        <Row gutter={16}>
          <Col span={8}>
            <Card bordered={false} style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
              <Statistic
                title={<span style={{ color: 'rgba(255,255,255,0.85)' }}>总任务数</span>}
                value={taskListData?.total || 0}
                valueStyle={{ color: '#fff' }}
                prefix={<FileTextOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card bordered={false} style={{ background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)' }}>
              <Statistic
                title={<span style={{ color: 'rgba(255,255,255,0.85)' }}>进行中</span>}
                value={processingTasks}
                valueStyle={{ color: '#fff' }}
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card bordered={false} style={{ background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)' }}>
              <Statistic
                title={<span style={{ color: 'rgba(255,255,255,0.85)' }}>已完成</span>}
                value={completedTasks}
                valueStyle={{ color: '#fff' }}
                prefix={<CheckCircleOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* 上传区域 */}
        <Card
          title={
            <Space>
              <UploadOutlined style={{ color: '#1890ff' }} />
              <span>上传文件</span>
            </Space>
          }
          style={{ borderRadius: '12px' }}
        >
          <Row gutter={24}>
            <Col span={14}>
              <Dragger {...uploadProps} style={{ borderRadius: '8px' }}>
                <p className="ant-upload-drag-icon">
                  <UploadOutlined style={{ fontSize: '48px', color: '#1890ff' }} />
                </p>
                <p className="ant-upload-text">点击或拖拽文件到此区域</p>
                <p className="ant-upload-hint">
                  支持 Markdown (.md)、PDF (.pdf)、EPUB (.epub) 格式
                </p>
              </Dragger>
            </Col>

            <Col span={10}>
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <div>
                  <Text strong style={{ display: 'block', marginBottom: '8px' }}>术语表</Text>
                  <Select
                    placeholder="选择术语表 (可选)"
                    style={{ width: '100%' }}
                    value={selectedGlossary}
                    onChange={setSelectedGlossary}
                    allowClear
                  >
                    {glossaries.map((glossary) => (
                      <Option key={glossary.id} value={glossary.id}>
                        {glossary.name} ({glossary.term_count || 0} 个术语)
                      </Option>
                    ))}
                  </Select>
                </div>

                <div>
                  <Text strong style={{ display: 'block', marginBottom: '8px' }}>输出模式</Text>
                  <div style={{
                    padding: '16px',
                    background: bilingual ? '#e6f7ff' : '#f5f5f5',
                    borderRadius: '8px',
                    border: bilingual ? '1px solid #91d5ff' : '1px solid #d9d9d9',
                    transition: 'all 0.3s'
                  }}>
                    <Space>
                      <Switch
                        checked={bilingual}
                        onChange={setBilingual}
                        checkedChildren="开"
                        unCheckedChildren="关"
                      />
                      <Tooltip title="启用后，输出文件将包含原文和译文对照">
                        <Text strong style={{ color: bilingual ? '#1890ff' : undefined }}>
                          双语对照模式
                        </Text>
                      </Tooltip>
                    </Space>
                    <Paragraph type="secondary" style={{ marginTop: '8px', marginBottom: 0, fontSize: '12px' }}>
                      {bilingual
                        ? '输出格式：原文（引用块）+ 译文，方便对照阅读'
                        : '输出格式：仅包含中文译文'
                      }
                    </Paragraph>
                  </div>
                </div>

                <Button
                  type="primary"
                  size="large"
                  block
                  onClick={handleStartTranslation}
                  loading={createTaskMutation.isPending}
                  disabled={fileList.length === 0}
                  icon={<TranslationOutlined />}
                  style={{
                    height: '48px',
                    borderRadius: '8px',
                    background: fileList.length > 0 ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : undefined,
                    border: 'none'
                  }}
                >
                  {bilingual ? '开始翻译（双语对照）' : '开始翻译'}
                </Button>
              </Space>
            </Col>
          </Row>
        </Card>

        {/* 当前任务进度 */}
        {currentTask && currentTask.status === 'processing' && (
          <Card
            title={
              <Space>
                <ThunderboltOutlined style={{ color: '#faad14' }} />
                <span>正在翻译</span>
                {currentTask.bilingual && <Tag color="blue">双语对照</Tag>}
              </Space>
            }
            style={{ borderRadius: '12px', borderColor: '#faad14' }}
          >
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Text strong>文件: </Text>
                <Text>{currentTask.filename}</Text>
              </div>

              <Progress
                percent={Math.round(currentTask.progress.percentage)}
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
                status="active"
                strokeWidth={12}
              />

              <Row gutter={16}>
                <Col span={8}>
                  <Statistic
                    title="进度"
                    value={currentTask.progress.current}
                    suffix={`/ ${currentTask.progress.total} 块`}
                    valueStyle={{ fontSize: '16px' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="速度"
                    value={currentTask.progress.speed.toFixed(1)}
                    suffix="块/分钟"
                    valueStyle={{ fontSize: '16px' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="耗时"
                    value={Math.round(currentTask.progress.elapsed)}
                    suffix="秒"
                    valueStyle={{ fontSize: '16px' }}
                  />
                </Col>
              </Row>
            </Space>
          </Card>
        )}

        {/* 任务完成提示 */}
        {currentTask && currentTask.status === 'completed' && (
          <Alert
            message="翻译完成"
            description={
              <Space>
                <span>文件 {currentTask.filename} 已翻译完成</span>
                <Button
                  type="primary"
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={() => window.open(downloadResult(currentTask.task_id), '_blank')}
                >
                  立即下载
                </Button>
              </Space>
            }
            type="success"
            showIcon
            closable
            style={{ borderRadius: '8px' }}
          />
        )}

        {currentTask && currentTask.status === 'failed' && (
          <Alert
            message="翻译失败"
            description={currentTask.error || '未知错误'}
            type="error"
            showIcon
            closable
            style={{ borderRadius: '8px' }}
          />
        )}

        {/* 任务列表 */}
        <Card
          title={
            <Space>
              <FileTextOutlined style={{ color: '#1890ff' }} />
              <span>任务列表</span>
            </Space>
          }
          extra={
            <Button
              icon={<ReloadOutlined />}
              onClick={() => queryClient.invalidateQueries({ queryKey: ['tasks'] })}
            >
              刷新
            </Button>
          }
          style={{ borderRadius: '12px' }}
        >
          <Table
            columns={columns}
            dataSource={taskListData?.tasks || []}
            loading={isLoadingTasks}
            rowKey="task_id"
            pagination={{
              total: taskListData?.total || 0,
              pageSize: 10,
              showTotal: (total) => `共 ${total} 条`,
              showSizeChanger: false,
            }}
            style={{ borderRadius: '8px' }}
          />
        </Card>
      </Space>
    </div>
  );
};

export default TranslationPage;
