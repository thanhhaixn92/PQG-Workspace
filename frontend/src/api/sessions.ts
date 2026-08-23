import type { Session, TaskRun } from '../store/store';
import { apiFetch } from './client';

export interface ChatMessage {
  id: string;
  session_id: string;
  task_id?: string | null;
  role: 'user' | 'assistant';
  content: string;
  created_at: number;
}

export const getSessions = async (): Promise<Session[]> => {
  return apiFetch<Session[]>('/api/sessions');
};

export const getSessionMessages = async (sessionId: string): Promise<ChatMessage[]> => {
  const page = await getSessionMessagePage(sessionId);
  return page.messages;
};

export interface ChatMessagePage {
  messages: ChatMessage[];
  has_more: boolean;
}

export const getSessionMessagePage = async (
  sessionId: string,
  limit = 100,
  beforeId?: string,
): Promise<ChatMessagePage> => {
  const params = new URLSearchParams({ limit: String(limit) });
  if (beforeId) params.set('before_id', beforeId);
  return apiFetch<ChatMessagePage>(`/api/sessions/${sessionId}/messages/page?${params}`);
};

export const getLatestSessionTaskRun = async (sessionId: string): Promise<TaskRun | null> => {
  return apiFetch<TaskRun | null>(`/api/sessions/${sessionId}/task-runs/latest`);
};

export const createSession = async (
  title: string,
  workspace_path?: string,
  goal?: string,
  data_scope: 'work_only' | 'approved_library' = 'work_only',
): Promise<Session> => {
  return apiFetch<Session>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ title, goal: goal?.trim() || undefined, data_scope, workspace_path: workspace_path?.trim() || undefined }),
  });
};

export const updateSession = async (
  sessionId: string,
  updates: { title?: string; goal?: string; data_scope?: 'work_only' | 'approved_library'; archived?: boolean },
): Promise<Session> => {
  return apiFetch<Session>(`/api/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
};

export const archiveSession = async (sessionId: string): Promise<void> => {
  await apiFetch<void>(`/api/sessions/${sessionId}`, {
    method: 'DELETE',
  });
};

export interface SmokeCleanupPreview {
  items: Array<{ id: string; title: string }>;
  confirmation_token: string;
}

export const previewSmokeTestCleanup = async (): Promise<SmokeCleanupPreview> =>
  apiFetch<SmokeCleanupPreview>('/api/sessions/cleanup-smoke-tests/preview');

export const cleanupSmokeTestSessions = async (confirmationToken: string): Promise<{ archived_count: number }> => {
  return apiFetch<{ archived_count: number }>('/api/sessions/cleanup-smoke-tests', {
    method: 'POST',
    body: JSON.stringify({ confirmation_token: confirmationToken }),
  });
};

export const submitPrompt = async (sessionId: string, prompt: string): Promise<TaskRun> => {
  return apiFetch<TaskRun>(`/api/sessions/${sessionId}/prompt`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
};
