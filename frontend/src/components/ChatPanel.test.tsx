import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatPanel } from './ChatPanel';
import { useHermesStore } from '../store/store';
import * as sessionsApi from '../api/sessions';
import * as tasksApi from '../api/tasks';
import * as eventsApi from '../api/events';

let mockUseTaskApi = false;
vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal<any>();
  return {
    ...actual,
    get VITE_USE_TASK_API() {
      return mockUseTaskApi;
    }
  };
});

vi.mock('../api/sessions', () => ({
  submitPrompt: vi.fn(),
  getSessionMessagePage: vi.fn(),
}));

vi.mock('../api/tasks', () => ({
  createTask: vi.fn(),
  startTask: vi.fn(),
  cancelTask: vi.fn(),
  decideTaskAction: vi.fn(),
}));

vi.mock('../api/events', () => ({
  subscribeToSessionEvents: vi.fn(),
  subscribeToTaskEvents: vi.fn(),
}));

window.HTMLElement.prototype.scrollIntoView = vi.fn();

const queuedTask = {
  id: 'task-1',
  session_id: 'session-1',
  status: 'queued' as const,
  started_at: 1000,
  finished_at: null,
  error: null,
  retry_count: 0,
};

describe('ChatPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseTaskApi = false;
    useHermesStore.setState({
      activeSessionId: null,
      events: {},
      latestTaskBySession: {},
      sessionStatusById: {},
      sessionErrorById: {},
      sessionStartedAtById: {},
    });
  });

  it('hiển thị hướng dẫn chọn phiên khi chưa có phiên active', () => {
    render(<ChatPanel />);
    expect(screen.getByText('Tạo Công việc để bắt đầu')).toBeDefined();
    expect(screen.getByRole('textbox')).toHaveProperty('disabled', true);
  });

  it('tải và chèn trang tin nhắn cũ hơn theo cursor', async () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      events: { 'session-1': [{ id: 'new-1', type: 'user_message', text: 'Mới', created_at: 2 }] },
      sessionStatusById: { 'session-1': 'idle' },
    });
    vi.mocked(sessionsApi.getSessionMessagePage).mockResolvedValue({
      messages: [{ id: 'old-1', session_id: 'session-1', role: 'assistant', content: 'Cũ', created_at: 1 }],
      has_more: false,
    });
    render(<ChatPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Tải tin nhắn trước' }));
    await waitFor(() => expect(sessionsApi.getSessionMessagePage).toHaveBeenCalledWith('session-1', 100, 'new-1'));
    expect(screen.getByText('Cũ')).toBeDefined();
    expect(screen.queryByRole('button', { name: 'Tải tin nhắn trước' })).toBeNull();
  });

  it('khóa input theo trạng thái của từng phiên', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'running' },
    });
    const { rerender } = render(<ChatPanel />);
    expect(screen.getByRole('textbox')).toHaveProperty('disabled', true);
    expect(screen.getByTitle('Gửi tin nhắn')).toHaveProperty('disabled', true);

    act(() => {
      useHermesStore.setState({
        activeSessionId: 'session-2',
        sessionStatusById: {
          'session-1': 'running',
          'session-2': 'idle',
        },
      });
    });
    rerender(<ChatPanel />);

    expect(screen.getByRole('textbox')).toHaveProperty('disabled', false);
    expect(screen.getByTitle('Gửi tin nhắn')).toHaveProperty('disabled', true);
  });

  it('hiển thị trạng thái Trợ lý GYO đang xử lý cho phiên đang running', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'running' },
      sessionStartedAtById: { 'session-1': Date.now() },
    });

    render(<ChatPanel />);
    expect(screen.getByText(/Trợ lý GYO đang xử lý/)).toBeDefined();
  });

  it('hiển thị cảnh báo khi Trợ lý GYO phản hồi chậm sau 30 giây', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'running' },
      sessionStartedAtById: { 'session-1': Date.now() - 31_000 },
    });

    render(<ChatPanel />);
    expect(screen.getByText(/Trợ lý GYO đang cần thêm thời gian/)).toBeDefined();
    expect(screen.getByText(/đang chờ bạn duyệt quyền/)).toBeDefined();
  });

  it('ưu tiên nhắc xử lý phê duyệt khi session đang chờ quyền', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'waiting_approval' },
      sessionStartedAtById: { 'session-1': Date.now() - 60_000 },
    });

    render(<ChatPanel />);
    expect(screen.getByText(/Hãy xử lý hộp phê duyệt/)).toBeDefined();
  });

  it('cho nhập và gửi prompt khi phiên đang idle', async () => {
    vi.mocked(sessionsApi.submitPrompt).mockResolvedValue(queuedTask);
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'idle' },
    });
    render(<ChatPanel />);

    const input = screen.getByRole('textbox');
    const submitBtn = screen.getByTitle('Gửi tin nhắn');

    fireEvent.change(input, { target: { value: 'Hello agent' } });
    expect(input).toHaveProperty('value', 'Hello agent');

    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(sessionsApi.submitPrompt).toHaveBeenCalledWith('session-1', 'Hello agent');
    });
    expect(useHermesStore.getState().sessionStatusById['session-1']).toBe('queued');
    expect(useHermesStore.getState().latestTaskBySession['session-1']).toEqual(queuedTask);
    expect(useHermesStore.getState().sessionStartedAtById['session-1']).toBeGreaterThan(0);
    expect(screen.getByText('Bạn')).toBeDefined();
  });

  it('hiển thị lịch sử với bong bóng Bạn và Trợ lý GYO', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'idle' },
      events: {
        'session-1': [
          { id: 'u1', type: 'user_message', text: 'Xin chào', created_at: 1000 },
          { id: 'a1', type: 'token', text: 'Chào bạn', created_at: 1001 },
        ],
      },
    });

    render(<ChatPanel />);
    expect(screen.getByText('Bạn')).toBeDefined();
    expect(screen.getByText('Trợ lý GYO')).toBeDefined();
    expect(screen.getByText('Xin chào')).toBeDefined();
    expect(screen.getByText('Chào bạn')).toBeDefined();
  });

  it('hiển thị lỗi workflow tại chat, không đẩy thành lỗi toàn app', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(sessionsApi.submitPrompt).mockRejectedValueOnce(new Error('Hermes missing'));
    vi.mocked(sessionsApi.submitPrompt).mockResolvedValueOnce(queuedTask);
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'idle' },
      appError: null,
    });
    render(<ChatPanel />);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Hello agent' } });
    fireEvent.click(screen.getByTitle('Gửi tin nhắn'));

    expect(await screen.findByText(/Không gửi được yêu cầu/)).toBeDefined();
    expect(screen.getByRole('textbox')).toHaveProperty('value', 'Hello agent');
    expect(useHermesStore.getState().sessionStatusById['session-1']).toBe('error');
    expect(useHermesStore.getState().sessionStartedAtById['session-1']).toBeUndefined();
    expect(useHermesStore.getState().appError).toBeNull();

    useHermesStore.getState().setSessionStatus('session-1', 'idle');
    fireEvent.click(screen.getByText('Gửi lại'));

    await waitFor(() => {
      expect(sessionsApi.submitPrompt).toHaveBeenCalledTimes(2);
    });
    consoleSpy.mockRestore();
  });

  it('hiển thị lỗi task gần nhất sau refresh và cho gửi lại prompt cuối', async () => {
    vi.mocked(sessionsApi.submitPrompt).mockResolvedValue(queuedTask);
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'idle' },
      latestTaskBySession: {
        'session-1': {
          ...queuedTask,
          id: 'task-failed',
          status: 'failed',
          error: 'Hermes failed',
        },
      },
      events: {
        'session-1': [{ id: 'u1', type: 'user_message', text: 'Retry me', created_at: 1000 }],
      },
    });

    render(<ChatPanel />);

    expect(screen.getByText('Hermes failed')).toBeDefined();
    fireEvent.click(screen.getByText('Gửi lại'));

    await waitFor(() => {
      expect(sessionsApi.submitPrompt).toHaveBeenCalledWith('session-1', 'Retry me');
    });
  });

  it('khi VITE_USE_TASK_API=true gửi prompt qua public Task API và hiển thị warning banner', async () => {
    mockUseTaskApi = true;
    const mockCreatedTask = { id: 'task-new', status: 'queued' as const, created_at: 100, task_type: 'prompt', duplicate: false, updated_at: 100 };
    const mockStartedTask = { id: 'task-new', status: 'running' as const, created_at: 100, task_type: 'prompt', duplicate: false, updated_at: 100 };

    vi.mocked(tasksApi.createTask).mockResolvedValueOnce(mockCreatedTask);
    vi.mocked(tasksApi.startTask).mockResolvedValueOnce(mockStartedTask);

    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'idle' },
    });

    render(<ChatPanel />);

    const input = screen.getByRole('textbox');
    const submitBtn = screen.getByTitle('Gửi tin nhắn');

    fireEvent.change(input, { target: { value: 'Run task prompt' } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(tasksApi.createTask).toHaveBeenCalledWith({
        session_id: 'session-1',
        title: 'Run task prompt',
        description: 'Run task prompt',
        task_type: 'prompt',
      });
      expect(tasksApi.startTask).toHaveBeenCalledWith('task-new');
      expect(eventsApi.subscribeToTaskEvents).toHaveBeenCalledWith('session-1', 'task-new');
    });

    expect(screen.getByText(/Chế độ tương thích đang bật/)).toBeDefined();
  });

  it('khi VITE_USE_TASK_API=true và task đang chạy, hiển thị nút Hủy và thực hiện hủy task', async () => {
    mockUseTaskApi = true;
    vi.mocked(tasksApi.cancelTask).mockResolvedValueOnce({
      id: 'task-1',
      status: 'cancelled' as const,
      task_type: 'prompt',
      created_at: 100,
      updated_at: 200,
      duplicate: false,
    });

    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'running' },
      latestTaskBySession: {
        'session-1': {
          id: 'task-1',
          session_id: 'session-1',
          status: 'running',
          started_at: 1000,
          retry_count: 0,
        },
      },
    });

    render(<ChatPanel />);

    const cancelBtn = screen.getByText('Hủy');
    expect(cancelBtn).toBeDefined();

    fireEvent.click(cancelBtn);

    await waitFor(() => {
      expect(tasksApi.cancelTask).toHaveBeenCalledWith('task-1');
    });

    expect(useHermesStore.getState().sessionStatusById['session-1']).toBe('idle');
    expect(useHermesStore.getState().latestTaskBySession['session-1']?.status).toBe('cancelled');
    expect(screen.getByText(/Lưu ý: việc hủy chỉ cập nhật metadata/)).toBeDefined();
  });
});
