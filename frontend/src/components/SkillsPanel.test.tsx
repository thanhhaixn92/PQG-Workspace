import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchSkills, updateSkill } from '../api/skills';
import { useHermesStore } from '../store/store';
import { SkillsPanel } from './SkillsPanel';

vi.mock('../api/skills', () => ({
  fetchSkills: vi.fn(),
  createSkill: vi.fn(),
  updateSkill: vi.fn(),
  deleteSkill: vi.fn(),
}));

describe('SkillsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ skills: [] });
    vi.mocked(fetchSkills).mockResolvedValue([
      {
        id: 's1',
        name: 'Review code',
        description: 'Kiểm tra lỗi',
        content: 'Always review diffs',
        enabled: true,
        updated_at: 1,
      },
      {
        id: 's2',
        name: 'Write docs',
        description: 'Viết tài liệu',
        content: 'Use concise Vietnamese',
        enabled: false,
        updated_at: 1,
      },
    ]);
  });

  it('lọc kỹ năng theo từ khóa', async () => {
    render(<SkillsPanel />);

    expect(await screen.findByText('Review code')).toBeDefined();
    fireEvent.change(screen.getByPlaceholderText('Tìm kỹ năng...'), { target: { value: 'docs' } });

    expect(screen.getByText('Write docs')).toBeDefined();
    expect(screen.queryByText('Review code')).toBeNull();
  });

  it('toggle bật tắt kỹ năng nhanh', async () => {
    vi.mocked(updateSkill).mockResolvedValue({
      id: 's1',
      name: 'Review code',
      description: 'Kiểm tra lỗi',
      content: 'Always review diffs',
      enabled: false,
      updated_at: 2,
    });

    render(<SkillsPanel />);

    await screen.findByText('Review code');
    fireEvent.click(screen.getAllByTitle('Bật/tắt kỹ năng')[0]);

    await waitFor(() => {
      expect(updateSkill).toHaveBeenCalledWith('s1', { enabled: false });
    });
  });
});
