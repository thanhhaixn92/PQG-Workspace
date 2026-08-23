import { apiFetch } from './client';

export type WorkspaceTaskStatus = 'planned' | 'ready' | 'in_progress' | 'blocked' | 'waiting' | 'done' | 'cancelled';
export type WorkspaceAiEligibility = 'delegatable' | 'assistable' | 'human_only';

export interface WorkspaceTask {
  id: string;
  session_id: string;
  title: string;
  description?: string | null;
  status: WorkspaceTaskStatus;
  priority: number;
  impact: number;
  due_at?: number | null;
  estimate_minutes?: number | null;
  blocked_reason?: string | null;
  ai_eligibility: WorkspaceAiEligibility;
  ai_reason?: string | null;
  version: number;
  created_at: number;
  updated_at: number;
  work_title?: string | null;
}

export interface WorkspaceDashboard {
  generated_at: number;
  recommendation?: WorkspaceTask | null;
  recommendation_reason?: string | null;
  alternatives: WorkspaceTask[];
  timeline: WorkspaceTask[];
  attention_items: Array<{ id: string; type: string; task_id: string; title: string; detail: string }>;
}

export interface WorkspaceAiJob {
  id: string;
  task_id: string;
  task_title: string;
  session_id: string;
  work_title: string;
  status: 'queued' | 'running' | 'waiting_user' | 'completed' | 'failed' | 'cancelled';
  stage_text?: string | null;
  output_summary?: string | null;
  conversation_id?: string | null;
  assistant_thread_id?: string | null;
  created_at: number;
  updated_at: number;
}

export const getWorkspaceToday = () => apiFetch<WorkspaceDashboard>('/api/workspace/today');
export const getWorkspaceUpcoming = () => apiFetch<WorkspaceTask[]>('/api/workspace/upcoming');
export const getWorkspaceHistory = () => apiFetch<WorkspaceTask[]>('/api/workspace/history');
export const getWorkspaceAiJobs = () => apiFetch<WorkspaceAiJob[]>('/api/workspace/ai-jobs');

export const createWorkspaceTask = (payload: Omit<WorkspaceTask, 'id' | 'status' | 'version' | 'created_at' | 'updated_at' | 'work_title'>, idempotencyKey: string) => apiFetch<WorkspaceTask>('/api/workspace/tasks', {
  method: 'POST', headers: { 'Idempotency-Key': idempotencyKey }, body: JSON.stringify(payload),
});

export const updateWorkspaceTask = (taskId: string, payload: Partial<WorkspaceTask> & { version: number }) => apiFetch<WorkspaceTask>(`/api/workspace/tasks/${taskId}`, {
  method: 'PATCH', body: JSON.stringify(payload),
});

export const deleteWorkspaceTask = (taskId: string) => apiFetch<void>(`/api/workspace/tasks/${taskId}`, { method: 'DELETE' });

export const createWorkspaceAiJob = (taskId: string, idempotencyKey: string) => apiFetch<WorkspaceAiJob>(`/api/workspace/tasks/${taskId}/ai-jobs`, { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey } });
