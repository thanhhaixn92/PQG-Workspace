import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppLayout } from './AppLayout';
import { useHermesStore } from '../store/store';
import * as healthApi from '../api/health';

vi.mock('../api/sessions', () => ({
  getSessions: vi.fn().mockResolvedValue([]),
  getSessionMessages: vi.fn().mockResolvedValue([]),
  getLatestSessionTaskRun: vi.fn().mockResolvedValue(null),
}));

vi.mock('../api/health', () => ({
  fetchHealth: vi.fn(),
}));

vi.mock('../api/events', () => ({
  subscribeToSessionEvents: vi.fn(),
  unsubscribeFromSessionEvents: vi.fn(),
}));

vi.mock('./SessionList', () => ({
  SessionList: () => <div>Danh sách phiên</div>,
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

describe('AppLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({
      sessions: [],
      activeSessionId: null,
      appError: null,
      sessionStatusById: {},
      sessionErrorById: {},
      latestTaskBySession: {},
    });
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
      .mockResolvedValueOnce({
        status: 'ok',
        version: '0.1.0',
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
});
