import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppLayout } from './AppLayout';
import { useHermesStore } from '../store/store';
import * as healthApi from '../api/health';
import * as sessionsApi from '../api/sessions';
import * as approvalsApi from '../api/approvals';
import { navigateToGyoAssistant } from '../navigation';

vi.mock('../api/sessions', () => ({
  getSessions: vi.fn().mockResolvedValue([]),
  getSessionMessages: vi.fn().mockResolvedValue([]),
  getLatestSessionTaskRun: vi.fn().mockResolvedValue(null),
}));

vi.mock('../api/health', () => ({
  fetchHealth: vi.fn(),
}));

vi.mock('../api/approvals', () => ({
  fetchPendingApprovals: vi.fn().mockResolvedValue([]),
}));

vi.mock('../api/events', () => ({
  subscribeToSessionEvents: vi.fn(),
  unsubscribeFromSessionEvents: vi.fn(),
}));

vi.mock('./SessionList', () => ({
  SessionList: () => <div>Danh sách phiên</div>,
  isTestWork: () => false,
}));

vi.mock('./ChatPanel', () => ({
  ChatPanel: () => <div>Khung trò chuyện</div>,
}));

vi.mock('./ActivityInspector', () => ({
  ActivityInspector: () => <div>Nhật ký hoạt động</div>,
}));

vi.mock('./ApprovalModal', () => ({
  ApprovalModal: () => null,
}));

vi.mock('./AssistantChatSidebar', () => ({
  AssistantChatSidebar: ({ surfaceMode }: { surfaceMode?: string }) => <div>GYO {surfaceMode ?? 'drawer'}</div>,
}));

vi.mock('./FileExplorer', () => ({
  FileExplorer: () => <div>Tệp</div>,
}));

vi.mock('./EditorPanel', () => ({
  EditorPanel: () => <div>Trình soạn thảo</div>,
}));

vi.mock('./SkillsPanel', () => ({
  SkillsPanel: () => <div>Kỹ năng</div>,
}));

vi.mock('./MemoryPanel', () => ({
  MemoryPanel: () => <div>Bộ nhớ</div>,
}));

vi.mock('./RuntimeStatusPanel', () => ({
  RuntimeStatusPanel: () => <div>Tình trạng hệ thống</div>,
}));

vi.mock('./LocalDataPanel', () => ({
  LocalDataPanel: () => <div>Dữ liệu cục bộ</div>,
}));

vi.mock('./OverviewPanel', () => ({
  OverviewPanel: () => <div>Tổng quan</div>,
}));

vi.mock('./WorkContextDrawer', () => ({
  WorkContextDrawer: () => <button type="button">Nội dung ngăn ngữ cảnh</button>,
}));

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', '/');
    useHermesStore.setState({
      sessions: [],
      activeSessionId: null,
      appError: null,
      sessionStatusById: {},
      sessionErrorById: {},
      latestTaskBySession: {},
      sidebarTab: 'overview',
      theme: 'dark',
    });
  });

  it('toggles and persists theme without an active Work', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({ status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1 });
    render(<AppLayout />);

    fireEvent.click(screen.getByRole('button', { name: 'Chuyển sang giao diện sáng' }));

    await waitFor(() => expect(document.documentElement.getAttribute('data-theme')).toBe('light'));
    expect(window.localStorage.getItem('hermes.theme')).toBe('light');
    expect(screen.getByRole('button', { name: 'Chuyển sang giao diện tối' })).toBeDefined();
  });

  it('identifies PQG Workspace separately from Trợ lý GYO', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({ status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1 });
    render(<AppLayout />);

    expect(screen.getByLabelText('PQG Workspace')).toBeDefined();
    expect(screen.getByText('PQG Workspace')).toBeDefined();
    expect(screen.queryByRole('button', { name: 'Trợ lý GYO' })).toBeNull();
    expect(screen.queryByText('Hermes Local')).toBeNull();
  });

  it('marks the shell for the collapsed GYO rail', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({ status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1 });
    useHermesStore.setState({ assistantSidebarMode: 'collapsed' });
    const { container } = render(<AppLayout />);
    expect(container.querySelector('.app-layout')?.className).toContain('assistant-collapsed');
  });

  it('renders the GYO focus surface after programmatic hand-off navigation', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({ status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1 });
    render(<AppLayout />);
    navigateToGyoAssistant('work-1', 'conv-1', 'thread-1');
    expect(await screen.findByText('GYO focus')).toBeDefined();
  });

  it('hiển thị cảnh báo dễ hiểu khi backend chưa phản hồi', async () => {
    vi.mocked(healthApi.fetchHealth).mockRejectedValue(new Error('offline'));

    render(<AppLayout />);

    expect(await screen.findByText('Backend chưa sẵn sàng')).toBeDefined();
    expect(screen.getByText(/Không kết nối được backend/)).toBeDefined();
  });

  it('cho phép kiểm tra lại backend từ banner', async () => {
    vi.mocked(healthApi.fetchHealth)
      .mockRejectedValueOnce(new Error('offline'))
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({
        status: 'ok',
      version: '2.2.0',
        db: 'ok',
        timestamp: 1,
      });

    render(<AppLayout />);

    const retryButton = await screen.findByText('Kiểm tra lại');
    fireEvent.click(retryButton);

    await waitFor(() => {
      expect(screen.queryByText('Backend chưa sẵn sàng')).toBeNull();
    });
  });

  it('keeps the task state when chat history cannot be restored', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({
      status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1,
    });
    vi.mocked(sessionsApi.getSessions).mockResolvedValueOnce([{
      id: 'session-1', title: 'Work', workspace_path: 'C:/workspace',
      created_at: 1, updated_at: 1, archived: 0,
    }]);
    vi.mocked(sessionsApi.getSessionMessages).mockRejectedValueOnce(new Error('messages unavailable'));
    vi.mocked(sessionsApi.getLatestSessionTaskRun).mockResolvedValueOnce({
      id: 'task-1', session_id: 'session-1', status: 'running', started_at: 1, retry_count: 0,
    });

    render(<AppLayout />);

    await waitFor(() => {
      expect(useHermesStore.getState().sessionStatusById['session-1']).toBe('running');
      expect(useHermesStore.getState().sessionErrorById['session-1']).toContain('lịch sử trò chuyện');
    });
  });

  it('keeps backend ready when only the work list cannot be restored', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({
      status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1,
    });
    vi.mocked(sessionsApi.getSessions).mockRejectedValueOnce(new Error('works unavailable'));

    render(<AppLayout />);

    expect(await screen.findByText('Cần chú ý')).toBeDefined();
    expect(screen.queryByText('Backend chưa sẵn sàng')).toBeNull();
    expect(screen.getByText(/Không tải được danh sách Công việc/)).toBeDefined();
  });

  it('restores a pending approval even when chat history is still slow', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({ status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1 });
    vi.mocked(sessionsApi.getSessions).mockResolvedValueOnce([{
      id: 'session-1', title: 'Work', workspace_path: 'C:/workspace', created_at: 1, updated_at: 1, archived: 0,
    }]);
    vi.mocked(sessionsApi.getSessionMessages).mockImplementationOnce(() => new Promise(() => {}));
    vi.mocked(approvalsApi.fetchPendingApprovals).mockResolvedValueOnce([{
      approval_id: 'approval-1', session_id: 'session-1', action: 'write_workspace_file', target: 'note.md', risk_level: 'write_internal',
    }]);

    render(<AppLayout />);

    await waitFor(() => {
      expect(useHermesStore.getState().pendingApproval?.approval_id).toBe('approval-1');
    });
  });

  it('opens the context drawer as a modal and restores focus when closed', async () => {
    vi.mocked(healthApi.fetchHealth).mockResolvedValue({ status: 'ok', version: '2.2.0', db: 'ok', timestamp: 1 });

    render(<AppLayout />);

    await waitFor(() => {
      expect(healthApi.fetchHealth).toHaveBeenCalled();
      expect(sessionsApi.getSessions).toHaveBeenCalled();
    });

    const trigger = screen.getByRole('button', { name: 'Lịch sử & ngữ cảnh' });
    trigger.focus();
    fireEvent.click(trigger);

    const drawer = screen.getByRole('dialog', { name: 'Lịch sử & ngữ cảnh' });
    expect(drawer).toBeDefined();
    expect(document.activeElement).toBe(within(drawer).getByRole('button', { name: 'Đóng' }));
    expect(document.body.style.overflow).toBe('hidden');

    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Lịch sử & ngữ cảnh' })).toBeNull();
      expect(document.activeElement).toBe(trigger);
    });
  });
});
