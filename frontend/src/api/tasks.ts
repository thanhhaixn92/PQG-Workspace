import { apiFetch } from './client';

export interface Task {
  id: string;
  session_id?: string | null;
  parent_task_id?: string | null;
  title?: string | null;
  description?: string | null;
  status: 'queued' | 'running' | 'waiting_approval' | 'succeeded' | 'failed' | 'cancelled';
  task_type: string;
  created_at: number;
  updated_at: number;
  duplicate: boolean;
}

export interface TaskEvent {
  id: string;
  task_id: string;
  run_id?: string | null;
  type: string;
  status: string;
  data_json?: string | null;
  created_at: number;
}

export interface TaskAction {
  id: string;
  task_id: string;
  tool_name: string;
  risk_level: string;
  status: string;
  description?: string | null;
  input_json?: string | null;
  output_json?: string | null;
  created_at: number;
  resolved_at?: number | null;
}

export interface TaskCreateRequest {
  session_id?: string | null;
  title?: string | null;
  description?: string | null;
  task_type?: string;
  parent_task_id?: string | null;
}

export interface TaskActionCreateRequest {
  tool_name: string;
  description: string;
  risk_level?: 'read' | 'write_internal' | 'external_or_destructive';
}

export interface TaskActionDecisionRequest {
  approved: boolean;
  output_json?: string | null;
}

export const createTask = async (
  request: TaskCreateRequest,
  idempotencyKey?: string,
): Promise<Task> => {
  const headers: Record<string, string> = {};
  if (idempotencyKey) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  return apiFetch<Task>('/api/tasks', {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
};

export const listTasks = async (params?: {
  session_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<Task[]> => {
  const searchParams = new URLSearchParams();
  if (params?.session_id) searchParams.append('session_id', params.session_id);
  if (params?.status) searchParams.append('status', params.status);
  if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
  if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());

  const query = searchParams.toString();
  return apiFetch<Task[]>(`/api/tasks${query ? `?${query}` : ''}`);
};

export const getTask = async (taskId: string): Promise<Task> => {
  return apiFetch<Task>(`/api/tasks/${taskId}`);
};

export const listTaskEvents = async (taskId: string): Promise<TaskEvent[]> => {
  return apiFetch<TaskEvent[]>(`/api/tasks/${taskId}/events`);
};

export const startTask = async (taskId: string): Promise<Task> => {
  return apiFetch<Task>(`/api/tasks/${taskId}/start`, {
    method: 'POST',
  });
};

export const cancelTask = async (taskId: string): Promise<Task> => {
  return apiFetch<Task>(`/api/tasks/${taskId}/cancel`, {
    method: 'POST',
  });
};

export const requestTaskAction = async (
  taskId: string,
  request: TaskActionCreateRequest,
): Promise<TaskAction> => {
  return apiFetch<TaskAction>(`/api/tasks/${taskId}/actions`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
};

export const decideTaskAction = async (
  taskId: string,
  actionId: string,
  request: TaskActionDecisionRequest,
): Promise<Task> => {
  return apiFetch<Task>(`/api/tasks/${taskId}/actions/${actionId}/decision`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
};
