/**
 * API 客户端
 * 封装所有后端 API 调用
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============== 类型定义 ==============

export interface TaskProgress {
  current: number;
  total: number;
  percentage: number;
  speed: number;
  elapsed: number;
}

export interface TranslationTask {
  task_id: string;
  filename: string;
  status: 'pending' | 'processing' | 'completed' | 'partial_success' | 'failed';
  glossary_id: string | null;
  bilingual: boolean;
  progress: TaskProgress;
  result_url: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface TaskListResponse {
  tasks: TranslationTask[];
  total: number;
}

export interface Glossary {
  id: string;
  name: string;
  term_count?: number;
  terms?: Record<string, string>;
  updated_at?: string;
}

export interface BilingualParagraph {
  source: string;
  translation: string;
}

export interface BilingualPreview {
  task_id: string;
  filename: string;
  bilingual: boolean;
  count: number;
  paragraphs: BilingualParagraph[];
}

// ============== 翻译任务 API ==============

/**
 * 创建翻译任务
 */
export const createTranslationTask = async (
  file: File,
  glossaryId?: string,
  bilingual: boolean = false
): Promise<TranslationTask> => {
  const formData = new FormData();
  formData.append('file', file);
  if (glossaryId) {
    formData.append('glossary_id', glossaryId);
  }
  formData.append('bilingual', String(bilingual));

  const response = await apiClient.post<TranslationTask>(
    '/api/translation/tasks',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return response.data;
};

/**
 * 查询任务状态
 */
export const getTaskStatus = async (taskId: string): Promise<TranslationTask> => {
  const response = await apiClient.get<TranslationTask>(`/api/translation/tasks/${taskId}`);
  return response.data;
};

/**
 * 获取任务列表
 */
export const getTaskList = async (skip = 0, limit = 20): Promise<TaskListResponse> => {
  const response = await apiClient.get<TaskListResponse>('/api/translation/tasks', {
    params: { skip, limit },
  });
  return response.data;
};

/**
 * 删除任务
 */
export const deleteTask = async (taskId: string): Promise<void> => {
  await apiClient.delete(`/api/translation/tasks/${taskId}`);
};

/**
 * 下载翻译结果
 * @param taskId 任务ID
 * @param format 导出格式: 'md' | 'html' | 'zip'
 * @param variant 结果类型: 'mono' | 'bilingual'
 */
export const downloadResult = (
  taskId: string,
  format: 'md' | 'html' | 'zip' = 'md',
  variant: 'mono' | 'bilingual' = 'mono'
): string => {
  return `${API_BASE_URL}/api/files/results/${taskId}?format=${format}&variant=${variant}`;
};

/**
 * 获取双语对照预览（Web 界面内双栏渲染，无需下载）
 */
export const getBilingualPreview = async (taskId: string): Promise<BilingualPreview> => {
  const response = await apiClient.get<BilingualPreview>(`/api/files/results/${taskId}/preview`);
  return response.data;
};

// ============== 术语表 API ==============

/**
 * 获取术语表列表
 */
export const getGlossaryList = async (): Promise<Glossary[]> => {
  const response = await apiClient.get<Glossary[]>('/api/glossary/');
  return response.data;
};

/**
 * 获取术语表详情
 */
export const getGlossary = async (glossaryId: string): Promise<Glossary> => {
  const response = await apiClient.get<Glossary>(`/api/glossary/${glossaryId}`);
  return response.data;
};

/**
 * 创建术语表
 */
export const createGlossary = async (
  name: string,
  terms: Record<string, string>
): Promise<Glossary> => {
  const response = await apiClient.post<Glossary>('/api/glossary/', {
    name,
    terms,
  });
  return response.data;
};

/**
 * 更新术语表(全量)
 */
export const updateGlossary = async (
  glossaryId: string,
  terms: Record<string, string>
): Promise<void> => {
  await apiClient.put(`/api/glossary/${glossaryId}`, { terms });
};

/**
 * 增量修改术语
 */
export const modifyGlossaryTerms = async (
  glossaryId: string,
  add?: Record<string, string>,
  remove?: string[]
): Promise<number> => {
  const response = await apiClient.patch<{ term_count: number }>(
    `/api/glossary/${glossaryId}/terms`,
    { add, remove }
  );
  return response.data.term_count;
};

/**
 * 删除术语表
 */
export const deleteGlossary = async (glossaryId: string): Promise<void> => {
  await apiClient.delete(`/api/glossary/${glossaryId}`);
};

/**
 * 导入术语表
 */
export const importGlossary = async (file: File, name: string): Promise<Glossary> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);

  const response = await apiClient.post<Glossary>('/api/glossary/import', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

/**
 * 导出术语表
 */
export const exportGlossary = (glossaryId: string): string => {
  return `${API_BASE_URL}/api/glossary/${glossaryId}/export`;
};
