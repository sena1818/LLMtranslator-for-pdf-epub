import React, { useState, useCallback } from 'react';
import { App } from 'antd';
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

const DownloadIcon = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
    <polyline points="7 10 12 15 17 10"/>
    <line x1="12" y1="15" x2="12" y2="3"/>
  </svg>
);

const UploadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
    <polyline points="17 8 12 3 7 8"/>
    <line x1="12" y1="3" x2="12" y2="15"/>
  </svg>
);

const formatTime = (isoStr: string) => {
  const d = new Date(isoStr);
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${m}-${day}  ${h}:${min}`;
};

const ACCEPTED = ['.md', '.pdf', '.epub'];

const isValidFile = (file: File) =>
  ACCEPTED.some(ext => file.name.toLowerCase().endsWith(ext));

const TranslationPage: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [selectedGlossary, setSelectedGlossary] = useState<string>('');
  const [bilingual, setBilingual] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);

  // ── Queries ──
  const { data: glossaries = [] } = useQuery<Glossary[]>({
    queryKey: ['glossaries'],
    queryFn: getGlossaryList,
  });

  const { data: taskListData, isLoading: isLoadingTasks, refetch: refetchTasks, isFetching: isRefetching } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => getTaskList(0, 20),
    refetchInterval: 5000,
  });

  const { data: currentTask } = useQuery<TranslationTask>({
    queryKey: ['task', currentTaskId],
    queryFn: () => getTaskStatus(currentTaskId!),
    enabled: !!currentTaskId,
    refetchInterval: (query) => {
      const t = query.state.data;
      if (t && ['completed', 'partial_success', 'failed'].includes(t.status)) return false;
      return 2000;
    },
  });

  // ── Mutations ──
  const createMutation = useMutation({
    mutationFn: ({ f, glossaryId, bi }: { f: File; glossaryId?: string; bi: boolean }) =>
      createTranslationTask(f, glossaryId || undefined, bi),
    onSuccess: (task) => {
      message.success('翻译任务已创建');
      setCurrentTaskId(task.task_id);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setFile(null);
    },
    onError: (err: Error) => message.error(`创建任务失败: ${err.message}`),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => {
      message.success('任务已删除');
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (err: Error) => message.error(`删除失败: ${err.message}`),
  });

  // ── Drag & Drop ──
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragging(false), []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && isValidFile(dropped)) {
      setFile(dropped);
    } else {
      message.error('仅支持 .md、.pdf、.epub 格式');
    }
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0];
    if (picked && isValidFile(picked)) {
      setFile(picked);
    } else if (picked) {
      message.error('仅支持 .md、.pdf、.epub 格式');
    }
    e.target.value = '';
  }, []);

  const handleSubmit = () => {
    if (!file) { message.warning('请先上传文件'); return; }
    createMutation.mutate({ f: file, glossaryId: selectedGlossary || undefined, bi: bilingual });
  };

  // ── Derived ──
  const tasks = taskListData?.tasks ?? [];
  const totalTasks = taskListData?.total ?? 0;
  const completedCount = tasks.filter(t => t.status === 'completed' || t.status === 'partial_success').length;
  const processingCount = tasks.filter(t => t.status === 'processing').length;

  const activeTask = currentTask && currentTask.status === 'processing' ? currentTask : null;
  const doneTask = currentTask && (currentTask.status === 'completed' || currentTask.status === 'partial_success') ? currentTask : null;
  const failedTask = currentTask && currentTask.status === 'failed' ? currentTask : null;

  const getChipClass = (status: string) => {
    if (status === 'processing') return 'chip chip-running';
    if (status === 'completed')  return 'chip chip-done';
    if (status === 'partial_success') return 'chip chip-warn';
    if (status === 'failed')     return 'chip chip-fail';
    return 'chip chip-pending';
  };

  const getChipLabel = (status: string) => {
    if (status === 'processing') return '翻译中';
    if (status === 'completed')  return '已完成';
    if (status === 'partial_success') return '部分完成';
    if (status === 'failed')     return '失败';
    return '等待中';
  };

  const getBarClass = (status: string) => {
    if (status === 'completed' || status === 'partial_success') return 'bar-fill done';
    if (status === 'failed') return 'bar-fill fail';
    return 'bar-fill';
  };

  return (
    <div className="page">

      {/* ── Hero ── */}
      <div className="hero">
        <div className="hero-text">
          <h1>哲学文本<em>翻译</em></h1>
          <p>专为后现代哲学文本设计的异步翻译系统，支持术语表一致性检查与断点续传。</p>
        </div>
        <div className="hero-stats">
          <div>
            <div className="hero-stat-val">{completedCount}</div>
            <div className="hero-stat-label">已完成</div>
          </div>
          <div>
            <div className={`hero-stat-val ${processingCount > 0 ? 'accent' : ''}`}>{processingCount}</div>
            <div className="hero-stat-label">进行中</div>
          </div>
          <div>
            <div className="hero-stat-val">{totalTasks}</div>
            <div className="hero-stat-label">总任务</div>
          </div>
        </div>
      </div>

      <div className="rule" />

      {/* ── Active Task Progress ── */}
      {activeTask && (
        <div className="progress-banner">
          <div>
            <div className="pb-label">
              <span className="pb-dot" />
              正在翻译
            </div>
            <div className="pb-filename">"{activeTask.filename}"</div>
            <div className="pb-track">
              <div className="pb-fill" style={{ width: `${activeTask.progress.percentage}%` }} />
            </div>
            <div className="pb-meta">
              {activeTask.progress.current} / {activeTask.progress.total} 文本块
              {activeTask.progress.total > 0 && activeTask.progress.speed > 0 && (
                <> · 预计剩余 {Math.ceil((activeTask.progress.total - activeTask.progress.current) / activeTask.progress.speed)} 分钟</>
              )}
            </div>
            <div className="pb-stats">
              <span className="pb-stat"><strong>{activeTask.progress.speed.toFixed(1)}</strong> 块/分钟</span>
              <span className="pb-stat"><strong>{Math.round(activeTask.progress.elapsed)}</strong> 秒已用</span>
              {activeTask.bilingual && <span className="pb-stat"><strong>双语对照</strong>模式</span>}
            </div>
          </div>
          <div className="pb-right">
            <div className="pb-pct">{Math.round(activeTask.progress.percentage)}</div>
            <div className="pb-pct-label">% 完成</div>
          </div>
        </div>
      )}

      {/* ── Completed Alert ── */}
      {doneTask && (
        <div className={`alert-banner ${doneTask.status === 'completed' ? 'success' : 'warn'}`}>
          <div className="alert-body">
            <div className="alert-title">{doneTask.status === 'completed' ? '翻译完成' : '翻译部分完成'}</div>
            <div className="alert-desc">
              {doneTask.status === 'completed'
                ? `${doneTask.filename} 已全部翻译完成`
                : doneTask.error || `${doneTask.filename} 有部分文本块翻译失败`}
            </div>
          </div>
          <div className="alert-actions">
            <button className="btn-download-md" onClick={() => window.open(downloadResult(doneTask.task_id, 'md'), '_blank')}>
              <DownloadIcon /> 下载 Markdown
            </button>
            {doneTask.bilingual && (
              <button className="btn-download-html" onClick={() => window.open(downloadResult(doneTask.task_id, 'html'), '_blank')}>
                <DownloadIcon /> 下载双栏 HTML
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Failed Alert ── */}
      {failedTask && (
        <div className="alert-banner error">
          <div className="alert-body">
            <div className="alert-title">翻译失败</div>
            <div className="alert-desc">{failedTask.error || '未知错误，请查看日志'}</div>
          </div>
        </div>
      )}

      {/* ── Section 01: Upload ── */}
      <div className="section">
        <div className="section-header">
          <span className="section-num">01</span>
          <span className="section-title">上传文件</span>
        </div>
        <div className="upload-grid">

          {/* Dropzone */}
          <label
            className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={(e) => { if ((e.target as HTMLElement).closest('.drop-clear')) e.preventDefault(); }}
          >
            <input
              type="file"
              accept=".md,.pdf,.epub"
              style={{ display: 'none' }}
              onChange={handleFileInput}
            />
            <div className="drop-icon"><UploadIcon /></div>
            {file ? (
              <>
                <div className="drop-title">文件已就绪</div>
                <div className="drop-file-name">{file.name}</div>
                <button
                  className="drop-clear"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); setFile(null); }}
                >
                  ×
                </button>
              </>
            ) : (
              <>
                <div className="drop-title">将文件拖放于此</div>
                <div className="drop-hint">或点击选择 · 每次一个文件</div>
                <div className="format-pills">
                  <span className="pill">markdown</span>
                  <span className="pill">pdf</span>
                  <span className="pill">epub</span>
                </div>
              </>
            )}
          </label>

          {/* Config Panel */}
          <div className="config-panel">
            <div>
              <label className="field-label">术语表</label>
              <div className="select-wrap">
                <select value={selectedGlossary} onChange={e => setSelectedGlossary(e.target.value)}>
                  <option value="">不使用术语表</option>
                  {glossaries.map(g => (
                    <option key={g.id} value={g.id}>
                      {g.name} ({g.term_count ?? 0} 个术语)
                    </option>
                  ))}
                </select>
                <span className="select-arrow">↓</span>
              </div>
            </div>

            <div>
              <label className="field-label">输出模式</label>
              <div
                className={`toggle-row ${bilingual ? 'on' : ''}`}
                onClick={() => setBilingual(v => !v)}
              >
                <div className="toggle-info">
                  <div className="toggle-name">双语对照</div>
                  <div className="toggle-desc">原文与译文并排输出</div>
                </div>
                <div className={`toggle-switch ${bilingual ? 'on' : 'off'}`} />
              </div>
            </div>

            <button
              className="btn-submit"
              onClick={handleSubmit}
              disabled={!file || createMutation.isPending}
            >
              {createMutation.isPending ? '创建中…' : bilingual ? '开始翻译（双语对照）' : '开始翻译'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Section 02: Task List ── */}
      <div className="section">
        <div className="section-header">
          <span className="section-num">02</span>
          <span className="section-title">任务列表</span>
        </div>
        <div className="table-wrap">
          <div className="table-header">
            <span className="table-header-title">历史记录</span>
            <button
              className="btn-refresh"
              onClick={() => refetchTasks()}
              disabled={isRefetching}
            >
              {isRefetching ? '刷新中…' : '刷新'}
            </button>
          </div>
          <table className="task-table">
            <thead>
              <tr>
                <th>文件名</th>
                <th>状态</th>
                <th>进度</th>
                <th>速度</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {isLoadingTasks ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-3)', fontWeight: 300 }}>
                    加载中…
                  </td>
                </tr>
              ) : tasks.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-3)', fontWeight: 300 }}>
                    暂无任务
                  </td>
                </tr>
              ) : tasks.map(task => (
                <tr key={task.task_id}>
                  <td>
                    <div className="td-filename">{task.filename}</div>
                    <div className="td-meta">
                      {task.bilingual && '双语对照 · '}
                      {task.progress.total > 0 && `${task.progress.total} 块`}
                    </div>
                  </td>
                  <td>
                    <span className={getChipClass(task.status)}>
                      {getChipLabel(task.status)}
                    </span>
                  </td>
                  <td>
                    <div className="bar-wrap">
                      <div
                        className={getBarClass(task.status)}
                        style={{ width: `${task.progress.percentage}%` }}
                      />
                    </div>
                    <span className="td-pct">{task.progress.percentage.toFixed(1)}%</span>
                  </td>
                  <td className="td-speed">
                    {task.progress.speed > 0 ? task.progress.speed.toFixed(1) : '—'}
                  </td>
                  <td className="td-time">{formatTime(task.created_at)}</td>
                  <td>
                    <div className="td-actions">
                      {(task.status === 'completed' || task.status === 'partial_success') && task.result_url && (
                        <>
                          <button
                            className="btn-dl-md"
                            onClick={() => window.open(downloadResult(task.task_id, 'md'), '_blank')}
                          >
                            <DownloadIcon /> MD
                          </button>
                          {task.bilingual && (
                            <button
                              className="btn-dl-html"
                              onClick={() => window.open(downloadResult(task.task_id, 'html'), '_blank')}
                            >
                              <DownloadIcon /> HTML
                            </button>
                          )}
                        </>
                      )}
                      {['completed', 'partial_success', 'failed'].includes(task.status) && (
                        <button
                          className="btn-del"
                          onClick={() => deleteMutation.mutate(task.task_id)}
                          disabled={deleteMutation.isPending}
                        >
                          删除
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
};

export default TranslationPage;
