import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SessionList } from './SessionList';
import { useHermesStore } from '../store/store';
import * as sessionsApi from '../api/sessions';

vi.mock('../api/sessions', () => ({
  createSession: vi.fn(),
  updateSession: vi.fn(),
  archiveSession: vi.fn(),
  previewSmokeTestCleanup: vi.fn(),
  cleanupSmokeTestSessions: vi.fn(),
}));

describe('SessionList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    useHermesStore.setState({
      sessions: [
        { id: 's1', title: 'Session 1', workspace_path: '/w1', created_at: 1000 },
        { id: 's2', title: 'Session 2', workspace_path: '/w2', created_at: 2000 },
      ],
      latestTaskBySession: {},
      activeSessionId: 's1',
    });
  });

  it('hiển thị empty state và điền form phiên mẫu', () => {
    useHermesStore.setState({
      sessions: [],
      activeSessionId: null,
    });

    render(<SessionList />);
    expect(screen.getByText('Bắt đầu Công việc đầu tiên')).toBeDefined();

    fireEvent.click(screen.getByText('Dùng Công việc mẫu'));
    expect(screen.getByPlaceholderText('Tên Công việc')).toHaveProperty('value', 'Công việc dùng thử Hermes');
    expect(screen.queryByPlaceholderText('Vị trí lưu trữ tùy chọn')).toBeNull();
    fireEvent.click(screen.getByText('Tùy chọn nâng cao'));
    expect(screen.getByPlaceholderText('Vị trí lưu trữ tùy chọn')).toHaveProperty('value', '');
  });

  it('hiển thị các phiên đã có', () => {
    render(<SessionList />);
    expect(screen.getByText('Session 1')).toBeDefined();
    expect(screen.getByText('Session 2')).toBeDefined();
    expect(screen.queryByText(/Vị trí lưu trữ: \/w1/)).toBeNull();
    expect(screen.queryByTitle('Xem vị trí lưu trữ')).toBeNull();
  });

  it('lọc phiên theo tên hoặc mục tiêu, không theo đường dẫn máy', () => {
    render(<SessionList />);
    fireEvent.change(screen.getByPlaceholderText('Tìm Công việc...'), { target: { value: 'Session 2' } });

    expect(screen.queryByText('Session 1')).toBeNull();
    expect(screen.getByText('Session 2')).toBeDefined();

    fireEvent.change(screen.getByPlaceholderText('Tìm Công việc...'), { target: { value: '/w2' } });
    expect(screen.queryByText('Session 2')).toBeNull();
  });

  it('hiển thị trạng thái task gần nhất của phiên', () => {
    useHermesStore.setState({
      latestTaskBySession: {
        s1: {
          id: 't1',
          session_id: 's1',
          status: 'failed',
          started_at: 1000,
          finished_at: 1001,
          error: 'failed',
          retry_count: 0,
        },
      },
    });

    render(<SessionList />);
    expect(screen.getByText('Lỗi')).toBeDefined();
  });

  it('đổi phiên active khi bấm vào phiên khác', () => {
    render(<SessionList />);
    fireEvent.click(screen.getByText('Session 2'));

    expect(useHermesStore.getState().activeSessionId).toBe('s2');
  });

  it('tạo phiên mới và tự chọn phiên đó mà không làm mất phiên cũ', async () => {
    vi.mocked(sessionsApi.createSession).mockResolvedValue({
      id: 's3',
      title: 'New Session',
      workspace_path: '/w3',
      created_at: 3000,
    });

    render(<SessionList />);

    fireEvent.click(screen.getByTitle('Tạo Công việc mới'));
    fireEvent.change(screen.getByPlaceholderText('Tên Công việc'), { target: { value: 'New Session' } });
    fireEvent.click(screen.getByText('Tùy chọn nâng cao'));
    fireEvent.change(screen.getByPlaceholderText('Vị trí lưu trữ tùy chọn'), {
      target: { value: '/w3' },
    });
    fireEvent.click(screen.getByText('Tạo'));

    await waitFor(() => {
      expect(sessionsApi.createSession).toHaveBeenCalledWith('New Session', '/w3', '', 'work_only');
      expect(useHermesStore.getState().sessions.map(session => session.id)).toEqual(['s3', 's1', 's2']);
      expect(useHermesStore.getState().activeSessionId).toBe('s3');
    });
  });

  it('tự dùng workspace mặc định khi tạo phiên mà không nhập đường dẫn', async () => {
    vi.mocked(sessionsApi.createSession).mockResolvedValue({
      id: 's3',
      title: 'New Session',
      workspace_path: 'C:\\Users\\dtron\\Documents\\Hermes\\workspace_outputs\\new-session-s3',
      created_at: 3000,
    });

    render(<SessionList />);

    fireEvent.click(screen.getByTitle('Tạo Công việc mới'));
    fireEvent.change(screen.getByPlaceholderText('Tên Công việc'), { target: { value: 'New Session' } });
    fireEvent.click(screen.getByText('Tạo'));

    await waitFor(() => {
      expect(sessionsApi.createSession).toHaveBeenCalledWith('New Session', '', '', 'work_only');
      expect(useHermesStore.getState().activeSessionId).toBe('s3');
      expect(screen.getByText(/Đã tự tạo nơi lưu trữ riêng/)).toBeDefined();
    });
  });

  it('hiển thị lỗi dễ hiểu khi tạo phiên thất bại', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    useHermesStore.setState({ sessions: [], activeSessionId: null });
    vi.mocked(sessionsApi.createSession).mockRejectedValue(new Error('backend down'));

    render(<SessionList />);
    fireEvent.click(screen.getByText('Dùng Công việc mẫu'));
    fireEvent.click(screen.getByText('Tạo'));

    await waitFor(() => {
      expect(screen.getByText(/Không tạo được Công việc/)).toBeDefined();
    });
    consoleSpy.mockRestore();
  });

  it('đổi tên phiên', async () => {
    vi.mocked(sessionsApi.updateSession).mockResolvedValue({
      id: 's1',
      title: 'Tên mới',
      workspace_path: '/w1',
      created_at: 1000,
    });

    render(<SessionList />);
    fireEvent.click(screen.getAllByTitle('Đổi tên Công việc')[0]);
    fireEvent.change(screen.getByLabelText('Tên Công việc mới'), { target: { value: 'Tên mới' } });
    fireEvent.click(screen.getByTitle('Lưu tên Công việc'));

    await waitFor(() => {
      expect(sessionsApi.updateSession).toHaveBeenCalledWith('s1', { title: 'Tên mới' });
      expect(useHermesStore.getState().sessions[0].title).toBe('Tên mới');
    });
  });

  it('hiển thị lỗi inline khi đổi tên phiên thất bại', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(sessionsApi.updateSession).mockRejectedValue(new Error('rename failed'));

    render(<SessionList />);
    fireEvent.click(screen.getAllByTitle('Đổi tên Công việc')[0]);
    fireEvent.change(screen.getByLabelText('Tên Công việc mới'), { target: { value: 'Tên mới' } });
    fireEvent.click(screen.getByTitle('Lưu tên Công việc'));

    await waitFor(() => {
      expect(screen.getByText('Không đổi tên được Công việc. Hãy thử lại.')).toBeDefined();
    });
    expect(useHermesStore.getState().sessions[0].title).toBe('Session 1');
    consoleSpy.mockRestore();
  });

  it('lưu trữ phiên và chọn phiên còn lại', async () => {
    vi.mocked(sessionsApi.archiveSession).mockResolvedValue(undefined);

    render(<SessionList />);
    fireEvent.click(screen.getAllByTitle('Lưu trữ Công việc')[0]);

    await waitFor(() => {
      expect(sessionsApi.archiveSession).toHaveBeenCalledWith('s1');
      expect(useHermesStore.getState().sessions.map(session => session.id)).toEqual(['s2']);
      expect(useHermesStore.getState().activeSessionId).toBe('s2');
    });
  });

  it('hiển thị lỗi inline khi lưu trữ phiên thất bại', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(sessionsApi.archiveSession).mockRejectedValue(new Error('archive failed'));

    render(<SessionList />);
    fireEvent.click(screen.getAllByTitle('Lưu trữ Công việc')[0]);

    await waitFor(() => {
      expect(screen.getByText('Không lưu trữ được Công việc. Hãy thử lại.')).toBeDefined();
    });
    expect(useHermesStore.getState().sessions.map(session => session.id)).toEqual(['s1', 's2']);
    consoleSpy.mockRestore();
  });

  it('cleanup smoke tests không làm mất phiên không thuộc smoke', async () => {
    vi.mocked(sessionsApi.previewSmokeTestCleanup).mockResolvedValue({
      items: [{ id: 'smoke-1', title: 'Smoke Test 1' }],
      confirmation_token: 'a'.repeat(64),
    });
    vi.mocked(sessionsApi.cleanupSmokeTestSessions).mockResolvedValue({ archived_count: 1 });
    useHermesStore.setState({
      sessions: [
        { id: 'smoke-1', title: 'Smoke Test 1', workspace_path: '/smoke', created_at: 1000 },
        { id: 'keep-1', title: 'Session thật', workspace_path: '/real', created_at: 2000 },
      ],
      activeSessionId: 'smoke-1',
    });

    render(<SessionList />);
    fireEvent.click(screen.getByRole('button', { name: 'Hiện dữ liệu kiểm thử (1)' }));
    fireEvent.click(screen.getByTitle('Lưu trữ dữ liệu thử nghiệm'));

    await waitFor(() => {
      expect(sessionsApi.cleanupSmokeTestSessions).toHaveBeenCalledWith('a'.repeat(64));
      expect(useHermesStore.getState().sessions.map(session => session.id)).toEqual(['keep-1']);
      expect(useHermesStore.getState().activeSessionId).toBe('keep-1');
    });
  });

  it('hiển thị lỗi inline khi dọn phiên test thất bại', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(sessionsApi.previewSmokeTestCleanup).mockRejectedValue(new Error('cleanup failed'));
    useHermesStore.setState({
      sessions: [
        { id: 'smoke-1', title: 'Smoke Test 1', workspace_path: '/smoke', created_at: 1000 },
        { id: 'keep-1', title: 'Session thật', workspace_path: '/real', created_at: 2000 },
      ],
      activeSessionId: 'smoke-1',
    });

    render(<SessionList />);
    fireEvent.click(screen.getByRole('button', { name: 'Hiện dữ liệu kiểm thử (1)' }));
    fireEvent.click(screen.getByTitle('Lưu trữ dữ liệu thử nghiệm'));

    await waitFor(() => {
      expect(screen.getByText('Không dọn được dữ liệu thử nghiệm. Hãy thử lại.')).toBeDefined();
    });
    expect(useHermesStore.getState().sessions.map(session => session.id)).toEqual(['smoke-1', 'keep-1']);
    consoleSpy.mockRestore();
  });

  it('cho phép chọn tri thức đã duyệt một cách tường minh khi tạo Công việc', async () => {
    vi.mocked(sessionsApi.createSession).mockResolvedValue({ id: 's3', title: 'New Session', workspace_path: '/w3', created_at: 3000 });
    render(<SessionList />);
    fireEvent.click(screen.getByTitle('Tạo Công việc mới'));
    fireEvent.change(screen.getByPlaceholderText('Tên Công việc'), { target: { value: 'New Session' } });
    fireEvent.change(screen.getByLabelText('Phạm vi dữ liệu Hermes được dùng'), { target: { value: 'approved_library' } });
    fireEvent.click(screen.getByText('Tạo'));
    await waitFor(() => expect(sessionsApi.createSession).toHaveBeenCalledWith('New Session', '', '', 'approved_library'));
  });

  it('hides marked test work by default and lets users reveal it', () => {
    useHermesStore.setState({
      sessions: [
        { id: 'uat-1', title: 'UAT-Codex regression', workspace_path: '/uat-codex-run', created_at: 1000 },
        { id: 'real-1', title: 'Quarterly plan', workspace_path: '/work', created_at: 2000 },
      ],
      activeSessionId: 'real-1',
    });

    render(<SessionList />);

    expect(screen.queryByText('UAT-Codex regression')).toBeNull();
    expect(screen.getByText('Quarterly plan')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Hiện dữ liệu kiểm thử (1)' }));
    expect(screen.getByText('UAT-Codex regression')).toBeDefined();
  });

  it('does not classify an ordinary numeric title as test data', () => {
    useHermesStore.setState({
      sessions: [
        { id: 'real-123', title: '123', workspace_path: '/workspace_outputs/real-123', created_at: 3000 },
        { id: 'uat-1', title: 'UAT-Codex regression', workspace_path: '/uat-codex-run', created_at: 1000 },
      ],
      activeSessionId: 'real-123',
    });

    render(<SessionList />);

    expect(screen.getByText('123')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Hiện dữ liệu kiểm thử (1)' })).toBeDefined();
  });
});
