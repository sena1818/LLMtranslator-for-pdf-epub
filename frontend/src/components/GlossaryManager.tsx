/**
 * 术语表管理组件
 */
import React, { useState } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  Modal,
  Form,
  Input,
  Upload,
  message,
  Popconfirm,
  Typography,
  Tag,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  DownloadOutlined,
  UploadOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getGlossaryList,
  getGlossary,
  createGlossary,
  modifyGlossaryTerms,
  deleteGlossary,
  exportGlossary,
  importGlossary,
  type Glossary,
} from '../services/api';

const { Title, Text } = Typography;

const GlossaryManager: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedGlossary, setSelectedGlossary] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();
  const [importForm] = Form.useForm();

  // 获取术语表列表
  const { data: glossaries = [], isLoading } = useQuery<Glossary[]>({
    queryKey: ['glossaries'],
    queryFn: getGlossaryList,
  });

  // 获取选中术语表的详情
  const { data: selectedGlossaryData } = useQuery<Glossary>({
    queryKey: ['glossary', selectedGlossary],
    queryFn: () => getGlossary(selectedGlossary!),
    enabled: !!selectedGlossary,
  });

  // 创建术语表
  const createMutation = useMutation({
    mutationFn: ({ name, terms }: { name: string; terms: Record<string, string> }) =>
      createGlossary(name, terms),
    onSuccess: () => {
      message.success('术语表创建成功');
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      setIsCreateModalOpen(false);
      createForm.resetFields();
    },
    onError: (error: any) => {
      message.error(`创建失败: ${error.message}`);
    },
  });

  // 修改术语
  const modifyMutation = useMutation({
    mutationFn: ({
      glossaryId,
      add,
      remove,
    }: {
      glossaryId: string;
      add?: Record<string, string>;
      remove?: string[];
    }) => modifyGlossaryTerms(glossaryId, add, remove),
    onSuccess: () => {
      message.success('术语已更新');
      queryClient.invalidateQueries({ queryKey: ['glossary', selectedGlossary] });
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      setIsEditModalOpen(false);
      editForm.resetFields();
    },
    onError: (error: any) => {
      message.error(`更新失败: ${error.message}`);
    },
  });

  // 删除术语表
  const deleteMutation = useMutation({
    mutationFn: deleteGlossary,
    onSuccess: () => {
      message.success('术语表已删除');
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      if (selectedGlossary) {
        setSelectedGlossary(null);
      }
    },
    onError: (error: any) => {
      message.error(`删除失败: ${error.message}`);
    },
  });

  // 导入术语表
  const importMutation = useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => importGlossary(file, name),
    onSuccess: () => {
      message.success('术语表导入成功');
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      setIsImportModalOpen(false);
      importForm.resetFields();
    },
    onError: (error: any) => {
      message.error(`导入失败: ${error.message}`);
    },
  });

  // 处理创建术语表
  const handleCreate = () => {
    createForm.validateFields().then((values) => {
      try {
        const terms = JSON.parse(values.terms);
        createMutation.mutate({ name: values.name, terms });
      } catch (e) {
        message.error('术语 JSON 格式错误');
      }
    });
  };

  // 处理添加术语
  const handleAddTerm = () => {
    editForm.validateFields().then((values) => {
      if (!selectedGlossary) return;
      modifyMutation.mutate({
        glossaryId: selectedGlossary,
        add: { [values.source]: values.target },
      });
    });
  };

  // 处理删除术语
  const handleRemoveTerm = (source: string) => {
    if (!selectedGlossary) return;
    modifyMutation.mutate({
      glossaryId: selectedGlossary,
      remove: [source],
    });
  };

  // 处理导入
  const handleImport = () => {
    importForm.validateFields().then((values) => {
      if (!values.file || values.file.length === 0) {
        message.error('请选择文件');
        return;
      }
      const file = values.file[0].originFileObj as File;
      importMutation.mutate({ file, name: values.name });
    });
  };

  // 术语表列表表格列配置
  const glossaryColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '术语数量',
      dataIndex: 'term_count',
      key: 'term_count',
      render: (count: number) => <Tag color="blue">{count} 个术语</Tag>,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: Glossary) => (
        <Space>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => setSelectedGlossary(record.id)}
          >
            编辑
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => window.open(exportGlossary(record.id), '_blank')}
          >
            导出
          </Button>
          <Popconfirm
            title="确定删除此术语表?"
            onConfirm={() => deleteMutation.mutate(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // 术语详情表格列配置
  const termColumns = [
    {
      title: '原文 (English)',
      dataIndex: 'source',
      key: 'source',
      width: '45%',
    },
    {
      title: '译文 (中文)',
      dataIndex: 'target',
      key: 'target',
      width: '45%',
    },
    {
      title: '操作',
      key: 'actions',
      width: '10%',
      render: (_: any, record: { source: string; target: string }) => (
        <Popconfirm
          title="确定删除此术语?"
          onConfirm={() => handleRemoveTerm(record.source)}
          okText="确定"
          cancelText="取消"
        >
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  // 转换术语数据为表格格式
  const termData = selectedGlossaryData?.terms
    ? Object.entries(selectedGlossaryData.terms).map(([source, target]) => ({
        source,
        target,
        key: source,
      }))
    : [];

  return (
    <div style={{ padding: '24px' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Title level={2}>术语表管理</Title>

        {/* 术语表列表 */}
        <Card
          title="术语表列表"
          extra={
            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => setIsCreateModalOpen(true)}
              >
                新建术语表
              </Button>
              <Button icon={<UploadOutlined />} onClick={() => setIsImportModalOpen(true)}>
                导入 JSON
              </Button>
            </Space>
          }
        >
          <Table
            columns={glossaryColumns}
            dataSource={glossaries}
            loading={isLoading}
            rowKey="id"
            pagination={false}
          />
        </Card>

        {/* 术语详情 */}
        {selectedGlossary && selectedGlossaryData && (
          <Card
            title={`术语详情: ${selectedGlossaryData.name}`}
            extra={
              <Button onClick={() => setSelectedGlossary(null)}>关闭</Button>
            }
          >
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Form form={editForm} layout="inline" onFinish={handleAddTerm}>
                <Form.Item
                  name="source"
                  rules={[{ required: true, message: '请输入原文' }]}
                  style={{ flex: 1 }}
                >
                  <Input placeholder="原文 (English)" />
                </Form.Item>
                <Form.Item
                  name="target"
                  rules={[{ required: true, message: '请输入译文' }]}
                  style={{ flex: 1 }}
                >
                  <Input placeholder="译文 (中文)" />
                </Form.Item>
                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    icon={<PlusOutlined />}
                    loading={modifyMutation.isPending}
                  >
                    添加术语
                  </Button>
                </Form.Item>
              </Form>

              <Table
                columns={termColumns}
                dataSource={termData}
                pagination={{ pageSize: 10 }}
                size="small"
              />
            </Space>
          </Card>
        )}
      </Space>

      {/* 创建术语表弹窗 */}
      <Modal
        title="新建术语表"
        open={isCreateModalOpen}
        onOk={handleCreate}
        onCancel={() => setIsCreateModalOpen(false)}
        confirmLoading={createMutation.isPending}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="术语表名称"
            rules={[{ required: true, message: '请输入术语表名称' }]}
          >
            <Input placeholder="例如: 哲学术语" />
          </Form.Item>
          <Form.Item
            name="terms"
            label="术语 (JSON 格式)"
            rules={[{ required: true, message: '请输入术语' }]}
          >
            <Input.TextArea
              rows={6}
              placeholder='{"English Term": "中文译名", "Example": "示例"}'
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 导入术语表弹窗 */}
      <Modal
        title="导入术语表"
        open={isImportModalOpen}
        onOk={handleImport}
        onCancel={() => setIsImportModalOpen(false)}
        confirmLoading={importMutation.isPending}
      >
        <Form form={importForm} layout="vertical">
          <Form.Item
            name="name"
            label="术语表名称"
            rules={[{ required: true, message: '请输入术语表名称' }]}
          >
            <Input placeholder="例如: 导入的术语表" />
          </Form.Item>
          <Form.Item
            name="file"
            label="选择 JSON 文件"
            valuePropName="fileList"
            getValueFromEvent={(e) => (Array.isArray(e) ? e : e?.fileList)}
            rules={[{ required: true, message: '请选择文件' }]}
          >
            <Upload
              beforeUpload={() => false}
              maxCount={1}
              accept=".json"
            >
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default GlossaryManager;
