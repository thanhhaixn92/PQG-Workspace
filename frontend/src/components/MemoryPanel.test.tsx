import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchGlobalMemory } from '../api/memory';
import { useHermesStore } from '../store/store';
import { MemoryPanel } from './MemoryPanel';

vi.mock('../api/memory', () => ({
  fetchGlobalMemory: vi.fn(),
  fetchSessionMemory: vi.fn(),
  createMemory: vi.fn(),
  deleteMemory: vi.fn(),
}));

describe('MemoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ activeSessionId: 'session-1', memory: [] });
    vi.mocked(fetchGlobalMemory).mockResolvedValue([
      {
        id: 'm1',
        session_id: null,
        key: 'theme',
        value: 'User prefers dark mode',
        kind: 'preference',
        importance_score: 0.9,
        last_accessed_at: null,
        created_at: 1,
      },
      {
        id: 'm2',
        session_id: null,
        key: 'repo',
        value: 'Hermes project path',
        kind: 'project_fact',
        importance_score: 0.5,
        last_accessed_at: 1,
        created_at: 1,
      },
    ]);
  });

  it('hiển thị loại bộ nhớ bằng tiếng Việt', async () => {
    render(<MemoryPanel />);

    expect(await screen.findByText('Sở thích')).toBeDefined();
    expect(screen.getAllByText('Thông tin dự án').length).toBeGreaterThan(0);
  });

  it('lọc bộ nhớ theo từ khóa', async () => {
    render(<MemoryPanel />);

    await screen.findByText('theme');
    fireEvent.change(screen.getByPlaceholderText('Tìm bộ nhớ...'), { target: { value: 'repo' } });

    expect(screen.getByText('repo')).toBeDefined();
    expect(screen.queryByText('theme')).toBeNull();
  });
});
