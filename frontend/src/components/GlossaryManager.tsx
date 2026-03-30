import React, { useState } from 'react';
import { Modal, Form, Input, Upload, App } from 'antd';
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

const GlossaryManager: React.FC = () => {
  const { message, modal } = App.useApp();
  const queryClient = useQueryClient();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [sourceInput, setSourceInput] = useState('');
  const [targetInput, setTargetInput] = useState('');
  const [createForm] = Form.useForm();
  const [importForm] = Form.useForm();

  // ── Queries ──
  const { data: glossaries = [], isLoading } = useQuery<Glossary[]>({
    queryKey: ['glossaries'],
    queryFn: getGlossaryList,
  });

  const { data: selectedData } = useQuery<Glossary>({
    queryKey: ['glossary', selectedId],
    queryFn: () => getGlossary(selectedId!),
    enabled: !!selectedId,
  });

  // ── Mutations ──
  const createMutation = useMutation({
    mutationFn: ({ name, terms }: { name: string; terms: Record<string, string> }) =>
      createGlossary(name, terms),
    onSuccess: () => {
      message.success('术语表创建成功');
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      setIsCreateOpen(false);
      createForm.resetFields();
    },
    onError: (err: Error) => message.error(`创建失败: ${err.message}`),
  });

  const modifyMutation = useMutation({
    mutationFn: ({ glossaryId, add, remove }: { glossaryId: string; add?: Record<string, string>; remove?: string[] }) =>
      modifyGlossaryTerms(glossaryId, add, remove),
    onSuccess: () => {
      message.success('术语已更新');
      queryClient.invalidateQueries({ queryKey: ['glossary', selectedId] });
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
    },
    onError: (err: Error) => message.error(`更新失败: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteGlossary,
    onSuccess: () => {
      message.success('术语表已删除');
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      setSelectedId(null);
    },
    onError: (err: Error) => message.error(`删除失败: ${err.message}`),
  });

  const importMutation = useMutation({
    mutationFn: ({ file, name }: { file: File; name: string }) => importGlossary(file, name),
    onSuccess: () => {
      message.success('术语表导入成功');
      queryClient.invalidateQueries({ queryKey: ['glossaries'] });
      setIsImportOpen(false);
      importForm.resetFields();
    },
    onError: (err: Error) => message.error(`导入失败: ${err.message}`),
  });

  // ── Handlers ──
  const handleCreate = () => {
    createForm.validateFields().then(values => {
      try {
        const terms = JSON.parse(values.terms);
        createMutation.mutate({ name: values.name, terms });
      } catch {
        message.error('术语 JSON 格式错误');
      }
    });
  };

  const handleAddTerm = () => {
    if (!selectedId || !sourceInput.trim() || !targetInput.trim()) {
      message.warning('请填写原文和译文');
      return;
    }
    modifyMutation.mutate({
      glossaryId: selectedId,
      add: { [sourceInput.trim()]: targetInput.trim() },
    });
    setSourceInput('');
    setTargetInput('');
  };

  const handleRemoveTerm = (source: string) => {
    if (!selectedId) return;
    modal.confirm({
      title: '删除术语',
      content: `确定删除术语 "${source}"？`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => modifyMutation.mutate({ glossaryId: selectedId, remove: [source] }),
    });
  };

  const handleDeleteGlossary = (id: string, name: string) => {
    modal.confirm({
      title: '删除术语表',
      content: `确定删除术语表 "${name}"？此操作不可恢复。`,
      okText: '确定删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => deleteMutation.mutate(id),
    });
  };

  const handleImport = () => {
    importForm.validateFields().then(values => {
      if (!values.file?.length) { message.error('请选择文件'); return; }
      const file = values.file[0].originFileObj as File;
      importMutation.mutate({ file, name: values.name });
    });
  };

  // ── Terms data ──
  const termEntries = selectedData?.terms
    ? Object.entries(selectedData.terms)
    : [];

  const formatDate = (str?: string) =>
    str ? new Date(str).toLocaleDateString('zh-CN') : '—';

  return (
    <div className="page">

      {/* ── Hero ── */}
      <div className="hero" style={{ marginBottom: 40 }}>
        <div className="hero-text">
          <h1>术语表<em>管理</em></h1>
          <p>统一管理翻译术语，确保专业词汇在全文中保持一致的译名。</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignSelf: 'flex-end' }}>
          <button className="btn-outline" onClick={() => setIsImportOpen(true)}>
            导入 JSON
          </button>
          <button className="btn-accent" onClick={() => setIsCreateOpen(true)}>
            + 新建术语表
          </button>
        </div>
      </div>

      <div className="rule" />

      {/* ── Main Layout ── */}
      <div className="glossary-layout">

        {/* Sidebar */}
        <div className="glossary-sidebar">
          <div className="glossary-sidebar-header">
            <span className="glossary-sidebar-title">术语表</span>
            <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 11, color: 'var(--text-3)', fontWeight: 300 }}>
              共 {glossaries.length} 个
            </span>
          </div>

          {isLoading ? (
            <div className="glossary-empty">加载中…</div>
          ) : glossaries.length === 0 ? (
            <div className="glossary-empty">暂无术语表</div>
          ) : (
            glossaries.map(g => (
              <div
                key={g.id}
                className={`glossary-item ${selectedId === g.id ? 'active' : ''}`}
                onClick={() => setSelectedId(g.id)}
              >
                <div className="glossary-item-name">{g.name}</div>
                <div className="glossary-item-meta">{g.term_count ?? 0} 个术语 · {formatDate(g.updated_at)}</div>
              </div>
            ))
          )}
        </div>

        {/* Detail Panel */}
        <div className="glossary-detail">
          {!selectedId ? (
            <div className="glossary-empty">← 从左侧选择一个术语表查看详情</div>
          ) : !selectedData ? (
            <div className="glossary-empty">加载中…</div>
          ) : (
            <>
              <div className="glossary-detail-header">
                <span className="glossary-detail-title">{selectedData.name}</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button
                    className="btn-outline"
                    onClick={() => window.open(exportGlossary(selectedId), '_blank')}
                  >
                    导出 JSON
                  </button>
                  <button
                    className="btn-outline"
                    style={{ color: 'var(--red)', borderColor: 'rgba(139,32,32,0.3)' }}
                    onClick={() => handleDeleteGlossary(selectedId, selectedData.name)}
                  >
                    删除
                  </button>
                </div>
              </div>

              {/* Add Term Row */}
              <div className="add-term-form">
                <input
                  className="term-input"
                  placeholder="原文 (English)"
                  value={sourceInput}
                  onChange={e => setSourceInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddTerm()}
                />
                <input
                  className="term-input"
                  placeholder="译文 (中文)"
                  value={targetInput}
                  onChange={e => setTargetInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAddTerm()}
                />
                <button
                  className="btn-accent"
                  onClick={handleAddTerm}
                  disabled={modifyMutation.isPending}
                >
                  添加
                </button>
              </div>

              {/* Terms Table */}
              {termEntries.length === 0 ? (
                <div className="glossary-empty">暂无术语，从上方添加</div>
              ) : (
                <table className="terms-table">
                  <thead>
                    <tr>
                      <th>原文 (English)</th>
                      <th>译文 (中文)</th>
                      <th style={{ width: 60 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {termEntries.map(([source, target]) => (
                      <tr key={source}>
                        <td className="term-en">{source}</td>
                        <td className="term-zh">{target}</td>
                        <td>
                          <button
                            className="btn-del"
                            onClick={() => handleRemoveTerm(source)}
                            style={{ fontSize: 12, padding: '4px 8px' }}
                          >
                            删除
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── Create Modal ── */}
      <Modal
        title="新建术语表"
        open={isCreateOpen}
        onOk={handleCreate}
        onCancel={() => { setIsCreateOpen(false); createForm.resetFields(); }}
        confirmLoading={createMutation.isPending}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="术语表名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：Cyclonopedia 术语表" />
          </Form.Item>
          <Form.Item name="terms" label="术语 (JSON 格式)" rules={[{ required: true, message: '请输入术语' }]}>
            <Input.TextArea
              rows={7}
              placeholder={'{\n  "Hyperstition": "超虚构 (Hyperstition)",\n  "War Machine": "战争机器 (War Machine)"\n}'}
              style={{ fontFamily: 'DM Mono, monospace', fontSize: 13 }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* ── Import Modal ── */}
      <Modal
        title="导入术语表"
        open={isImportOpen}
        onOk={handleImport}
        onCancel={() => { setIsImportOpen(false); importForm.resetFields(); }}
        confirmLoading={importMutation.isPending}
        okText="导入"
        cancelText="取消"
      >
        <Form form={importForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item name="name" label="术语表名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：导入的术语表" />
          </Form.Item>
          <Form.Item
            name="file"
            label="选择 JSON 文件"
            valuePropName="fileList"
            getValueFromEvent={e => Array.isArray(e) ? e : e?.fileList}
            rules={[{ required: true, message: '请选择文件' }]}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept=".json">
              <button className="btn-outline" type="button">选择文件</button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>

    </div>
  );
};

export default GlossaryManager;
