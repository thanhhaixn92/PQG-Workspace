import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryHubPanel } from './MemoryHubPanel';
import { previewLegacyMemory, searchMemoryHub } from '../api/memoryHub';
import { ApiError } from '../api/client';

vi.mock('../api/memoryHub', () => ({
  searchMemoryHub: vi.fn(),
  createMemoryHubProposal: vi.fn(),
  transitionMemoryHubRecord: vi.fn(),
  previewLegacyMemory: vi.fn(),
  importLegacyMemory: vi.fn(),
}));

describe('MemoryHubPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(searchMemoryHub).mockResolvedValue([{ id: 'global-pref', kind: 'preference', memory_key: 'language', content: 'Vietnamese', project_id: null, task_id: null, lifecycle: 'active', sensitivity: 'normal', created_at: 1 }]);
  });

  it('uses an explicit scope and clears prior results when scope changes', async () => {
    render(<MemoryHubPanel />);
    expect(await screen.findByText('language')).toBeDefined();

    fireEvent.change(screen.getByLabelText('Phạm vi Memory Hub'), { target: { value: 'project' } });
    expect(screen.queryByText('language')).toBeNull();
    expect(screen.getByText(/Chọn phạm vi cụ thể/)).toBeDefined();
  });

  it('shows a local error instead of stale records when loading fails', async () => {
    vi.mocked(searchMemoryHub).mockRejectedValue(new Error('offline'));
    render(<MemoryHubPanel />);
    await waitFor(() => expect(screen.getByText(/Không thể tải Memory Hub/)).toBeDefined());
  });

  it('explains that a non-preference proposal needs Codex review', async () => {
    vi.mocked(searchMemoryHub).mockResolvedValue([{ id: 'technical', kind: 'technical_decision', memory_key: 'api-contract', content: 'Use a versioned contract', project_id: 'project-1', task_id: null, lifecycle: 'proposed', sensitivity: 'normal', created_at: 1 }]);
    render(<MemoryHubPanel />);
    expect(await screen.findByText(/cần Codex review/)).toBeDefined();
  });

  it('gives a clear action for a forbidden backend response', async () => {
    vi.mocked(searchMemoryHub).mockRejectedValue(new ApiError(403, JSON.stringify({ detail: 'Memory Hub operator access is restricted to localhost' })));
    render(<MemoryHubPanel />);
    expect(await screen.findByText(/Bạn không có quyền thực hiện thao tác này/)).toBeDefined();
  });

  it('does not restore a legacy preview after its scope changed', async () => {
    let resolvePreview!: (value: Array<{ legacy_memory_id: string; memory_key: string; content: string; kind: string }>) => void;
    vi.mocked(previewLegacyMemory).mockReturnValue(new Promise(resolve => {
      resolvePreview = resolve;
    }));
    render(<MemoryHubPanel />);

    fireEvent.change(screen.getByLabelText('Phạm vi Memory Hub'), { target: { value: 'project' } });
    fireEvent.change(screen.getByLabelText('Mã dự án'), { target: { value: 'project-a' } });
    fireEvent.change(screen.getByLabelText('ID legacy'), { target: { value: 'legacy-1' } });
    const previewButton = screen.getByRole('button', { name: 'Xem trước' }) as HTMLButtonElement;
    await waitFor(() => expect(previewButton.disabled).toBe(false));
    fireEvent.click(previewButton);
    await waitFor(() => expect(previewLegacyMemory).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('Mã dự án'), { target: { value: 'project-b' } });
    resolvePreview([{ legacy_memory_id: 'legacy-1', memory_key: 'old-scope', content: 'must stay hidden', kind: 'project_fact' }]);

    await Promise.resolve();
    expect(screen.queryByText(/old-scope/)).toBeNull();
    expect(screen.queryByText(/must stay hidden/)).toBeNull();
  });
});
