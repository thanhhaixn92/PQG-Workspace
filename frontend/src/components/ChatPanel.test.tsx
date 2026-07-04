import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatPanel } from './ChatPanel';
import { useHermesStore } from '../store/store';
import * as sessionsApi from '../api/sessions';

vi.mock('../api/sessions', () => ({
  submitPrompt: vi.fn(),
}));

vi.mock('../api/events', () => ({
  subscribeToSessionEvents: vi.fn(),
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
    expect(screen.getByText('Tạo phiên để bắt đầu')).toBeDefined();
    expect(screen.getByRole('textbox')).toHaveProperty('disabled', true);
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

  it('hiển thị trạng thái Hermes đang xử lý cho phiên đang running', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'running' },
      sessionStartedAtById: { 'session-1': Date.now() },
    });

    render(<ChatPanel />);
    expect(screen.getByText(/Hermes đang xử lý/)).toBeDefined();
  });

  it('hiển thị cảnh báo khi Hermes phản hồi chậm sau 30 giây', () => {
    useHermesStore.setState({
      activeSessionId: 'session-1',
      sessionStatusById: { 'session-1': 'running' },
      sessionStartedAtById: { 'session-1': Date.now() - 31_000 },
    });

    render(<ChatPanel />);
    expect(screen.getByText(/Hermes phản hồi chậm/)).toBeDefined();
    expect(screen.getByText(/model\/provider/)).toBeDefined();
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

  it('hiển thị lịch sử với bong bóng Bạn và Hermes', () => {
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
    expect(screen.getByText('Hermes')).toBeDefined();
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
});
