import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as assistantApi from '../api/assistant';
import * as knowledgeApi from '../api/knowledgeSummary';
import * as memoryApi from '../api/memory';
import * as skillsApi from '../api/skills';
import { useHermesStore } from '../store/store';
import { KnowledgePanel } from './KnowledgePanel';

vi.mock('../api/assistant', () => ({ getAssistantContextManifest: vi.fn() }));
vi.mock('../api/knowledgeSummary', () => ({ getKnowledgeSummary: vi.fn() }));
vi.mock('../api/memory', () => ({ fetchGlobalMemory: vi.fn(), fetchSessionMemory: vi.fn() }));
vi.mock('../api/skills', () => ({ fetchSkills: vi.fn() }));

describe('KnowledgePanel summary', () => {
  beforeEach(() => {
    useHermesStore.setState({ activeSessionId: 'work-1', sessions: [{ id: 'work-1', title: 'Pilot', workspace_path: 'x', created_at: 1 }] });
    vi.mocked(skillsApi.fetchSkills).mockResolvedValue([]);
    vi.mocked(memoryApi.fetchSessionMemory).mockResolvedValue([]);
    vi.mocked(assistantApi.getAssistantContextManifest).mockResolvedValue({ work_id: 'work-1', included: [], excluded: [], byte_limit: 12_000, byte_count: 0, memory_hub_auto_injected: false });
    vi.mocked(knowledgeApi.getKnowledgeSummary).mockResolvedValue({ work_id: 'work-1', counts_by_source: {}, counts_by_lifecycle: {}, context_included_count: 3, context_excluded_count: 2, pending_review_count: 4, last_updated_at: 1 });
  });

  it('shows server-owned context and review counts', async () => {
    render(<KnowledgePanel />);
    expect(await screen.findByText('3')).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();
    expect(screen.getByText(/2 mục bị loại/)).toBeDefined();
    expect(knowledgeApi.getKnowledgeSummary).toHaveBeenCalledWith('work-1');
  });
});
