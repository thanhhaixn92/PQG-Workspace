import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HistoryPanel } from './HistoryPanel';

const api = vi.hoisted(() => ({ getWorkAssistantHistory: vi.fn(), updateWorkAssistantHistory: vi.fn() }));
vi.mock('../../api/assistant', () => api);

const first = { id: 'thread-1', title: 'Báo cáo Q2', work_id: 'work-1', conversation_id: 'conv-1', status: 'active', created_at: 10, updated_at: 11, message_count: 2, pinned_at: null };

describe('HistoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getWorkAssistantHistory.mockResolvedValue({ items: [first], next_cursor: 'cursor-2', has_more: true });
  });

  it('loads Work-scoped server history and sends cursor/search/filter', async () => {
    render(<HistoryPanel workId="work-1" workArchived={false} />);
    await screen.findByText('Báo cáo Q2');
    expect(api.getWorkAssistantHistory).toHaveBeenCalledWith('work-1', expect.objectContaining({ limit: 25, includeArchived: true }));
    fireEvent.click(screen.getByRole('button', { name: /Tải thêm/i }));
    await waitFor(() => expect(api.getWorkAssistantHistory).toHaveBeenLastCalledWith('work-1', expect.objectContaining({ cursor: 'cursor-2' })));
  });

  it('uses server mutations for pin and archive', async () => {
    api.updateWorkAssistantHistory.mockResolvedValue({ ...first, pinned_at: 22 });
    render(<HistoryPanel workId="work-1" workArchived={false} />);
    await screen.findByText('Báo cáo Q2');
    fireEvent.click(screen.getByRole('button', { name: 'Ghim' }));
    await waitFor(() => expect(api.updateWorkAssistantHistory).toHaveBeenCalledWith('work-1', 'thread-1', { pinned: true }));
  });

  it('does not expose mutations for an archived Work', async () => {
    render(<HistoryPanel workId="work-1" workArchived />);
    await screen.findByText('Báo cáo Q2');
    expect(screen.queryByRole('button', { name: 'Ghim' })).toBeNull();
    expect(screen.getByText('Chỉ đọc')).toBeDefined();
  });
});
