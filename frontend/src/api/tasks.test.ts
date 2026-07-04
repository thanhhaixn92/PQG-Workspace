import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as tasksApi from './tasks';
import { apiFetch } from './client';

vi.mock('./client', () => ({
  apiFetch: vi.fn(),
  BASE_URL: 'http://localhost:8000',
  VITE_USE_TASK_API: true,
}));

describe('tasks api wrapper', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('createTask calls POST /api/tasks with correct payload and headers', async () => {
    const mockTask: tasksApi.Task = {
      id: 'task-123',
      status: 'queued',
      task_type: 'prompt',
      created_at: 1000,
      updated_at: 1000,
      duplicate: false,
    };
    vi.mocked(apiFetch).mockResolvedValueOnce(mockTask);

    const req: tasksApi.TaskCreateRequest = {
      session_id: 'session-123',
      title: 'Test task',
    };
    const result = await tasksApi.createTask(req, 'idem-key-123');

    expect(apiFetch).toHaveBeenCalledWith('/api/tasks', {
      method: 'POST',
      headers: { 'Idempotency-Key': 'idem-key-123' },
      body: JSON.stringify(req),
    });
    expect(result).toEqual(mockTask);
  });

  it('listTasks calls GET /api/tasks with correct query params', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce([]);

    await tasksApi.listTasks({
      session_id: 'session-123',
      status: 'running',
      limit: 10,
      offset: 5,
    });

    expect(apiFetch).toHaveBeenCalledWith(
      '/api/tasks?session_id=session-123&status=running&limit=10&offset=5'
    );
  });

  it('getTask calls GET /api/tasks/:id', async () => {
    const mockTask = { id: 'task-123' };
    vi.mocked(apiFetch).mockResolvedValueOnce(mockTask);

    const result = await tasksApi.getTask('task-123');
    expect(apiFetch).toHaveBeenCalledWith('/api/tasks/task-123');
    expect(result).toEqual(mockTask);
  });

  it('listTaskEvents calls GET /api/tasks/:id/events', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce([]);

    const result = await tasksApi.listTaskEvents('task-123');
    expect(apiFetch).toHaveBeenCalledWith('/api/tasks/task-123/events');
    expect(result).toEqual([]);
  });

  it('startTask calls POST /api/tasks/:id/start', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({ id: 'task-123', status: 'running' });

    const result = await tasksApi.startTask('task-123');
    expect(apiFetch).toHaveBeenCalledWith('/api/tasks/task-123/start', {
      method: 'POST',
    });
    expect(result.status).toBe('running');
  });

  it('cancelTask calls POST /api/tasks/:id/cancel', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({ id: 'task-123', status: 'cancelled' });

    const result = await tasksApi.cancelTask('task-123');
    expect(apiFetch).toHaveBeenCalledWith('/api/tasks/task-123/cancel', {
      method: 'POST',
    });
    expect(result.status).toBe('cancelled');
  });

  it('requestTaskAction calls POST /api/tasks/:id/actions', async () => {
    const mockAction = { id: 'act-1' };
    vi.mocked(apiFetch).mockResolvedValueOnce(mockAction);

    const req: tasksApi.TaskActionCreateRequest = {
      tool_name: 'write_file',
      description: 'write plan.txt',
      risk_level: 'write_internal',
    };
    const result = await tasksApi.requestTaskAction('task-123', req);

    expect(apiFetch).toHaveBeenCalledWith('/api/tasks/task-123/actions', {
      method: 'POST',
      body: JSON.stringify(req),
    });
    expect(result).toEqual(mockAction);
  });

  it('decideTaskAction calls POST /api/tasks/:id/actions/:action_id/decision', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({ id: 'task-123' });

    const req: tasksApi.TaskActionDecisionRequest = {
      approved: true,
      output_json: '{}',
    };
    const result = await tasksApi.decideTaskAction('task-123', 'act-1', req);

    expect(apiFetch).toHaveBeenCalledWith('/api/tasks/task-123/actions/act-1/decision', {
      method: 'POST',
      body: JSON.stringify(req),
    });
    expect(result).toBeDefined();
  });
});
