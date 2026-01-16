/**
 * 翻译页面组件
 */
import React, { useState, useEffect } from 'react';
import {
  Upload,
  Select,
  Button,
  Progress,
  Card,
  Space,
  Typography,
  Alert,
  Spin,
  message,
  Table,
  Tag,
} from 'antd';
import {
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  ReloadOutlined,
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

const { Title, Text } = Typography;
const { Option } = Select;

const TranslationPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [selectedGlossary, setSelectedGlossary] = useState<string | undefined>(undefined);
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
    refetchInterval: 3000, // 每 3 秒轮询一次
  });

  // 查询当前任务状态
  const { data: currentTask } = useQuery<TranslationTask>({
    queryKey: ['task', currentTaskId],
    queryFn: () => getTaskStatus(currentTaskId!),
    enabled: !!currentTaskId,
    refetchInterval: (query) => {
      const task = query.state.data;
      // 如果任务完成或失败,停止轮询
      if (task && (task.status === 'completed' || task.status === 'failed')) {
        return false;
      }
      return 2000; // 2 秒轮询
    },
  });

  // 创建翻译任务
  const createTaskMutation = useMutation({
    mutationFn: ({ file, glossaryId }: { file: File; glossaryId?: string }) =>
      createTranslationTask(file, glossaryId),
    onSuccess: (task) => {
      message.success('翻译任务已创建');
      setCurrentTaskId(task.task_id);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setFileList([]);
    },
    onError: (error: any) => {
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
    onError: (error: any) => {
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

      setFileList([file as UploadFile]);
      return false; // 阻止自动上传
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
    createTaskMutation.mutate({ file, glossaryId: selectedGlossary });
  };

  // 任务状态标签
  const getStatusTag = (status: string) => {
    const statusMap = {
      pending: { color: 'default', text: '等待中' },
      processing: { color: 'processing', text: '翻译中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
    };
    const config = statusMap[status as keyof typeof statusMap] || statusMap.pending;
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  // 任务列表表格列配置
  const columns = [
    {
      title: '文件名',
      dataIndex: 'filename',
      key: 'filename',
      width: 250,
      ellipsis: true,
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
      width: 200,
      render: (_: any, record: TranslationTask) => (
        <Progress
          percent={Math.round(record.progress.percentage)}
          size="small"
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
      width: 120,
      render: (speed: number) => `${speed.toFixed(1)} 块/分`,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: any, record: TranslationTask) => (
        <Space>
          {record.status === 'completed' && record.result_url && (
            <Button
              type="link"
              size="small"
              icon={<DownloadOutlined />}
              onClick={() => window.open(downloadResult(record.task_id), '_blank')}
            >
              下载
            </Button>
          )}
          {(record.status === 'completed' || record.status === 'failed') && (
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => deleteTaskMutation.mutate(record.task_id)}
            >
              删除
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 页面标题 */}
        <Title level={2}>AI 翻译系统</Title>

        {/* 上传区域 */}
        <Card title="上传文件">
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>

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

            <Button
              type="primary"
              size="large"
              block
              onClick={handleStartTranslation}
              loading={createTaskMutation.isPending}
              disabled={fileList.length === 0}
            >
              开始翻译
            </Button>
          </Space>
        </Card>

        {/* 当前任务进度 */}
        {currentTask && (
          <Card title="当前任务">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Text strong>文件名: </Text>
                <Text>{currentTask.filename}</Text>
              </div>

              <div>
                <Text strong>状态: </Text>
                {getStatusTag(currentTask.status)}
              </div>

              <Progress
                percent={Math.round(currentTask.progress.percentage)}
                status={
                  currentTask.status === 'failed'
                    ? 'exception'
                    : currentTask.status === 'completed'
                    ? 'success'
                    : 'active'
                }
              />

              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <Text type="secondary">
                  进度: {currentTask.progress.current} / {currentTask.progress.total} 块
                </Text>
                <Text type="secondary">速度: {currentTask.progress.speed.toFixed(1)} 块/分钟</Text>
                <Text type="secondary">耗时: {Math.round(currentTask.progress.elapsed)} 秒</Text>
              </div>

              {currentTask.error && <Alert message={currentTask.error} type="error" showIcon />}

              {currentTask.status === 'completed' && currentTask.result_url && (
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  onClick={() => window.open(downloadResult(currentTask.task_id), '_blank')}
                  block
                >
                  下载翻译结果
                </Button>
              )}
            </Space>
          </Card>
        )}

        {/* 任务列表 */}
        <Card
          title="任务列表"
          extra={
            <Button
              icon={<ReloadOutlined />}
              onClick={() => queryClient.invalidateQueries({ queryKey: ['tasks'] })}
            >
              刷新
            </Button>
          }
        >
          <Table
            columns={columns}
            dataSource={taskListData?.tasks || []}
            loading={isLoadingTasks}
            rowKey="task_id"
            pagination={{
              total: taskListData?.total || 0,
              pageSize: 20,
              showTotal: (total) => `共 ${total} 条`,
            }}
          />
        </Card>
      </Space>
    </div>
  );
};

export default TranslationPage;
