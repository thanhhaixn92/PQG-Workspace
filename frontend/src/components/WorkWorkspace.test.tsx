import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useHermesStore } from '../store/store';
import { parseWorkspaceTaskInput, WorkWorkspace } from './WorkWorkspace';

const api = vi.hoisted(() => ({ getWorkspaceToday: vi.fn(), getWorkspaceUpcoming: vi.fn(), getWorkspaceHistory: vi.fn(), getWorkspaceAiJobs: vi.fn(), createWorkspaceTask: vi.fn(), deleteWorkspaceTask: vi.fn(), createWorkspaceAiJob: vi.fn(), updateWorkspaceTask: vi.fn() }));
const sessionsApi = vi.hoisted(() => ({ createSession: vi.fn() }));
vi.mock('../api/workspace', () => api);
vi.mock('../api/sessions', () => sessionsApi);
vi.mock('./WorkHub', () => ({ WorkHub: () => <div>Chi tiết Work</div> }));

const task = { id: 'workspace-task-1', session_id: 'work-1', title: 'Hoàn thiện PRD', status: 'ready', priority: 5, impact: 4, ai_eligibility: 'delegatable', version: 1, created_at: 1, updated_at: 1, work_title: 'Workspace' };

describe('WorkWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/work?tab=today');
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Workspace', workspace_path: 'C:/workspace', created_at: 1, updated_at: 1, archived: 0 }], activeSessionId: null, assistantSidebarMode: 'collapsed' });
    api.getWorkspaceToday.mockResolvedValue({ generated_at: 1, recommendation: task, recommendation_reason: 'Ưu tiên theo hạn.', alternatives: [], timeline: [task], attention_items: [] });
    api.getWorkspaceUpcoming.mockResolvedValue([task]); api.getWorkspaceHistory.mockResolvedValue([]); api.getWorkspaceAiJobs.mockResolvedValue([]);
    api.createWorkspaceAiJob.mockResolvedValue({ id: 'job-1', conversation_id: 'conversation-1', assistant_thread_id: 'thread-1' }); api.updateWorkspaceTask.mockResolvedValue({ ...task, status: 'in_progress', version: 2 });
  });

  it('renders the Today recommendation and opens GYO only for eligible tasks', async () => {
    render(<WorkWorkspace />);
    expect((await screen.findAllByText('Hoàn thiện PRD')).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /Giao GYO/i }));
    await waitFor(() => expect(window.location.pathname).toBe('/work/work-1/assistant'));
    expect(window.location.search).toContain('conversation=conversation-1');
    expect(window.location.search).toContain('thread=thread-1');
    expect(api.createWorkspaceAiJob).toHaveBeenCalledWith('workspace-task-1', expect.stringMatching(/^workspace-ai-job-/));
    expect(useHermesStore.getState().activeSessionId).toBe('work-1');
  });

  it('shows a handed-off job that is waiting for the user\'s GYO prompt', async () => {
    api.getWorkspaceAiJobs.mockResolvedValue([{
      id: 'workspace-ai-1', task_id: 'workspace-task-1', task_title: 'Hoàn thiện PRD', session_id: 'work-1', work_title: 'Workspace',
      status: 'waiting_user', stage_text: 'Sẵn sàng nhận yêu cầu cho GYO.', output_summary: null,
      conversation_id: 'conversation-1', assistant_thread_id: 'thread-1', created_at: '2026-08-23T04:00:00Z', updated_at: '2026-08-23T04:00:00Z',
    }]);
    render(<WorkWorkspace />);

    fireEvent.click(await screen.findByRole('button', { name: 'AI đang làm' }));

    expect(await screen.findByText('Chờ bạn gửi yêu cầu cho GYO')).toBeTruthy();
    expect(screen.getByText('Sẵn sàng nhận yêu cầu cho GYO.')).toBeTruthy();
  });

  it('opens the selected Work detail from a task', async () => {
    render(<WorkWorkspace />);
    await screen.findAllByText('Hoàn thiện PRD');
    fireEvent.click(screen.getByRole('button', { name: /Hoàn thiện PRD/i }));
    await waitFor(() => expect(screen.getByText('Chi tiết Work')).toBeDefined());
  });

  it('closes the Work drawer with Escape without changing the selected Work', async () => {
    render(<WorkWorkspace />);
    await screen.findAllByText('Hoàn thiện PRD');
    fireEvent.click(screen.getByRole('button', { name: /Hoàn thiện PRD/i }));
    await screen.findByText('Chi tiết Work');
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByText('Chi tiết Work')).toBeNull());
    expect(useHermesStore.getState().activeSessionId).toBe('work-1');
  });

  it('stores the selected Workspace tab in the URL', async () => {
    render(<WorkWorkspace />);

    fireEvent.click(await screen.findByRole('button', { name: 'Sắp tới' }));

    await screen.findByRole('heading', { name: 'Sắp tới' });
    expect(window.location.pathname).toBe('/work');
    expect(window.location.search).toBe('?tab=upcoming');
  });

  it('preselects the active Work and focuses task creation from the empty state', async () => {
    useHermesStore.setState({ activeSessionId: 'work-1' });
    api.getWorkspaceToday.mockResolvedValue({ generated_at: 1, recommendation: null, recommendation_reason: '', alternatives: [], timeline: [], attention_items: [] });
    render(<WorkWorkspace />);
    const workSelect = await screen.findByRole('combobox', { name: 'Công việc của việc' }) as HTMLSelectElement;
    expect(workSelect.value).toBe('work-1');
    fireEvent.click(screen.getByRole('button', { name: 'Tạo việc đầu tiên' }));
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('textbox', { name: 'Tên việc mới' })));
  });

  it('creates the first Work instead of leaving a task form disabled without a parent Work', async () => {
    useHermesStore.setState({ sessions: [], activeSessionId: null });
    api.getWorkspaceToday.mockResolvedValue({ generated_at: 1, recommendation: null, recommendation_reason: '', alternatives: [], timeline: [], attention_items: [] });
    sessionsApi.createSession.mockResolvedValue({ id: 'work-new', title: 'Kế hoạch tháng 9', workspace_path: 'C:/workspace', created_at: 1, updated_at: 1, archived: 0 });
    render(<WorkWorkspace />);

    expect((await screen.findByRole('button', { name: 'Tạo Công việc mới' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole('textbox', { name: 'Tên việc mới' })).toBeNull();
    fireEvent.change(screen.getByRole('textbox', { name: 'Tên Công việc mới' }), { target: { value: 'Kế hoạch tháng 9' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo Công việc mới' }));

    await waitFor(() => expect(sessionsApi.createSession).toHaveBeenCalledWith('Kế hoạch tháng 9'));
    const taskInput = await screen.findByRole('textbox', { name: 'Tên việc mới' });
    expect(taskInput).toBeTruthy();
    await waitFor(() => expect(document.activeElement).toBe(taskInput));
    expect((screen.getByRole('combobox', { name: 'Công việc của việc' }) as HTMLSelectElement).value).toBe('work-new');
  });

  it('parses an explicit tomorrow deadline and duration before creating, then exposes Undo', async () => {
    api.createWorkspaceTask.mockResolvedValue({ ...task, id: 'workspace-task-created', title: 'Hoàn thiện báo cáo tháng trước' });
    api.deleteWorkspaceTask.mockResolvedValue(undefined);
    render(<WorkWorkspace />);
    const input = await screen.findByRole('textbox', { name: 'Tên việc mới' });
    fireEvent.change(input, { target: { value: 'Hoàn thiện báo cáo tháng trước 16:00 ngày mai, khoảng 2 giờ' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Công việc của việc' }), { target: { value: 'work-1' } });
    expect(screen.getByText(/Nhận diện: hạn .*ước lượng 2 giờ/i)).toBeDefined();
    fireEvent.click(screen.getAllByRole('button', { name: /^Tạo việc$/ }).at(-1)!);
    await waitFor(() => expect(api.createWorkspaceTask).toHaveBeenCalledWith(expect.objectContaining({
      session_id: 'work-1', title: 'Hoàn thiện báo cáo tháng trước', estimate_minutes: 120, due_at: expect.any(Number),
    }), expect.any(String)));
    expect(await screen.findByText('Đã tạo “Hoàn thiện báo cáo tháng trước”.')).toBeDefined();
    expect(screen.queryByRole('textbox', { name: 'Tên việc mới' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Hoàn tác' }));
    await waitFor(() => expect(api.deleteWorkspaceTask).toHaveBeenCalledWith('workspace-task-created'));
  });

  it('keeps a normal title untouched when there is no unambiguous time expression', () => {
    expect(parseWorkspaceTaskInput('Chuẩn bị bài phát biểu dài').title).toBe('Chuẩn bị bài phát biểu dài');
    expect(parseWorkspaceTaskInput('Chuẩn bị bài phát biểu dài').dueAt).toBeNull();
  });
});
