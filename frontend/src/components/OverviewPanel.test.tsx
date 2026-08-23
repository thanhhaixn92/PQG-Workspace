import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OverviewPanel } from './OverviewPanel';
import { useHermesStore } from '../store/store';
import * as overviewApi from '../api/overview';

vi.mock('../api/overview', () => ({ getOverview: vi.fn() }));

describe('OverviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ activeSessionId: null, sidebarTab: 'overview' });
  });

  it('shows end-user progress and opens selected work', async () => {
    vi.mocked(overviewApi.getOverview).mockResolvedValue({
      recent_work: [{ id: 'work-1', title: 'Kế hoạch tuần', goal: 'Chốt ưu tiên', workspace_path: 'hidden', created_at: 1, updated_at: 2, archived: 0, last_opened_at: 3 }],
      active_work_count: 2, pending_approval_count: 1, output_count: 4, latest_backup_at: null,
      blocked_step_count: 0, waiting_confirmation_count: 0, attention_items: [], recent_artifacts: [], latest_work_updates: [],
    });
    render(<OverviewPanel />);
    expect(await screen.findByText('PQG Workspace')).toBeDefined();
    expect(await screen.findByText('Trợ lý công việc cá nhân chạy trên máy của bạn')).toBeDefined();
    expect(screen.getByText('mục chờ bạn duyệt')).toBeDefined();
    expect(screen.getByText((_content, element) =>
      element?.tagName === 'LI' && element.textContent?.includes('chọn tab Trao đổi để giao yêu cầu cho GYO.') === true,
    )).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: /Kế hoạch tuần/ }));
    await waitFor(() => {
      expect(useHermesStore.getState().activeSessionId).toBe('work-1');
      expect(useHermesStore.getState().sidebarTab).toBe('sessions');
    });
    expect(screen.queryByText('hidden')).toBeNull();
  });
});
