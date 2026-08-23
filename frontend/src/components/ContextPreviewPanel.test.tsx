import { act, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as previewApi from '../api/contextPreview';
import { useHermesStore } from '../store/store';
import { ContextPreviewPanel } from './ContextPreviewPanel';

vi.mock('../api/contextPreview', () => ({ getContextPreview: vi.fn() }));

describe('ContextPreviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ activeSessionId: 'session-1' });
  });

  it('explains selected and excluded context without showing content', async () => {
    vi.mocked(previewApi.getContextPreview).mockResolvedValue({
      session_id: 'session-1', memory_hub_injected: false,
      skills: { item_limit: 10, byte_limit: 12000, selected_bytes: 120, items: [
        { id: 's1', label: 'Đã duyệt', selected: true, bytes: 120, reason: 'Sẽ dùng trong yêu cầu tiếp theo' },
        { id: 's2', label: 'Bản nháp', selected: false, bytes: 50, reason: 'Chưa được duyệt' },
      ] },
      memories: { item_limit: 10, byte_limit: 8000, selected_bytes: 0, items: [] },
    });
    render(<ContextPreviewPanel />);
    expect(await screen.findByText('Đã duyệt')).toBeDefined();
    expect(screen.getByText('Bản nháp')).toBeDefined();
    expect(screen.getByText('Memory Hub chưa tự động được đưa vào chat trong giai đoạn này.')).toBeDefined();
  });

  it('ignores a preview returned for the previous work item', async () => {
    let resolveOld!: (value: previewApi.ContextPreview) => void;
    vi.mocked(previewApi.getContextPreview).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve; }));
    vi.mocked(previewApi.getContextPreview).mockResolvedValueOnce({
      session_id: 'session-2', memory_hub_injected: false,
      skills: { item_limit: 10, byte_limit: 12000, selected_bytes: 0, items: [] },
      memories: { item_limit: 10, byte_limit: 8000, selected_bytes: 0, items: [] },
    });
    render(<ContextPreviewPanel />);
    act(() => useHermesStore.getState().setActiveSession('session-2'));
    resolveOld({
      session_id: 'session-1', memory_hub_injected: false,
      skills: { item_limit: 10, byte_limit: 12000, selected_bytes: 1, items: [{ id: 'old', label: 'Old context', selected: true, bytes: 1, reason: 'old' }] },
      memories: { item_limit: 10, byte_limit: 8000, selected_bytes: 0, items: [] },
    });
    await waitFor(() => expect(previewApi.getContextPreview).toHaveBeenCalledWith('session-2'));
    expect(screen.queryByText('Old context')).toBeNull();
  });
});
