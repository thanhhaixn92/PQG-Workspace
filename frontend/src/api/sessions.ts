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
  return apiFetch<ChatMessage[]>(`/api/sessions/${sessionId}/messages`);
};

export const getLatestSessionTaskRun = async (sessionId: string): Promise<TaskRun | null> => {
  return apiFetch<TaskRun | null>(`/api/sessions/${sessionId}/task-runs/latest`);
};

export const createSession = async (title: string, workspace_path?: string): Promise<Session> => {
  return apiFetch<Session>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ title, workspace_path: workspace_path?.trim() || undefined }),
  });
};

export const updateSession = async (
  sessionId: string,
  updates: { title?: string; archived?: boolean },
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

export const cleanupSmokeTestSessions = async (): Promise<{ archived_count: number }> => {
  return apiFetch<{ archived_count: number }>('/api/sessions/cleanup-smoke-tests', {
    method: 'POST',
  });
};

export const submitPrompt = async (sessionId: string, prompt: string): Promise<TaskRun> => {
  return apiFetch<TaskRun>(`/api/sessions/${sessionId}/prompt`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  });
};
