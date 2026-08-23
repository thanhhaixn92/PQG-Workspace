import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as dirapApi from '../api/dirap';
import * as hubApi from '../api/memoryHub';
import * as skillsApi from '../api/skills';
import * as actionPackagesApi from '../api/actionPackages';
import { ApiError } from '../api/client';
import { useHermesStore } from '../store/store';
import { ReviewInboxPanel } from './ReviewInboxPanel';

vi.mock('../api/dirap', () => ({ listWorkItems: vi.fn(), listKnowledgeRecords: vi.fn(), approveKnowledgeRecord: vi.fn(), rejectKnowledgeRecord: vi.fn() }));
vi.mock('../api/memoryHub', () => ({ searchMemoryHub: vi.fn(), transitionMemoryHubRecord: vi.fn() }));
vi.mock('../api/skills', () => ({ fetchSkills: vi.fn(), changeSkillStatus: vi.fn() }));
vi.mock('../api/actionPackages', () => ({
  getWorkActionPackages: vi.fn(), approveActionPackage: vi.fn(), denyActionPackage: vi.fn(),
  getActionPackageDecisionBinding: vi.fn(() => ({ expectedRevision: 1, expectedPayloadHash: 'payload-hash' })),
  createActionPackageIdempotencyKey: vi.fn(() => 'test-decision-key'),
}));

describe('ReviewInboxPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ activeSessionId: 'session-1', pendingApproval: null });
    vi.mocked(actionPackagesApi.getWorkActionPackages).mockResolvedValue([]);
  });

  it('projects pending source records and decides through the source lifecycle', async () => {
    vi.mocked(skillsApi.fetchSkills).mockResolvedValue([{ id: 'skill-1', name: 'Soạn báo cáo', description: null, content: 'x', enabled: false, status: 'review_pending', version: 1, updated_at: 1 }]);
    vi.mocked(dirapApi.listWorkItems).mockResolvedValue([{ task_id: 'work-1' }] as dirapApi.DirapWorkItem[]);
    vi.mocked(dirapApi.listKnowledgeRecords).mockResolvedValue([{ id: 'kr-1', status: 'review_pending', content: 'Quy định từ tài liệu' }] as dirapApi.DirapKnowledgeRecord[]);
    vi.mocked(hubApi.searchMemoryHub).mockResolvedValue([{ id: 'hub-1', kind: 'project_context', memory_key: 'Bối cảnh dự án', content: 'x', project_id: 'session-1', task_id: null, lifecycle: 'proposed', sensitivity: 'normal', created_at: 1 }]);
    render(<ReviewInboxPanel />);
    expect(await screen.findByText('Soạn báo cáo')).toBeDefined();
    expect(screen.getByText('Quy định từ tài liệu')).toBeDefined();
    expect(screen.getByText('Bối cảnh dự án')).toBeDefined();
    await waitFor(() => expect(screen.getAllByRole('button', { name: 'Mở khu vực Tri thức' })).toHaveLength(3));
    fireEvent.click(screen.getAllByRole('button', { name: 'Duyệt tại nguồn' })[0]);
    await waitFor(() => expect(skillsApi.changeSkillStatus).toHaveBeenCalledWith('skill-1', 'approved'));
  });

  it('decides an immutable assistant action package through its source lifecycle', async () => {
    vi.mocked(skillsApi.fetchSkills).mockResolvedValue([]);
    vi.mocked(dirapApi.listWorkItems).mockResolvedValue([]);
    vi.mocked(hubApi.searchMemoryHub).mockResolvedValue([]);
    vi.mocked(actionPackagesApi.getWorkActionPackages).mockResolvedValue([{
      id: 'package-1', session_id: 'session-1', title: 'Update test step', description: null,
      package_hash: 'hash', status: 'awaiting_approval', created_at: 1, updated_at: 1,
      steps: [{ id: 'step-1', sort_order: 0, kind: 'work_plan_step_update', risk_level: 'local_mutation', status: 'pending', input: {} }],
    }]);
    render(<ReviewInboxPanel />);
    expect(await screen.findByText('Update test step')).toBeDefined();
    expect(screen.getByText(/1 b.*c .*g.*i b.*t bi.*n/)).toBeDefined();
    expect(screen.getByRole('button', { name: 'Mở đề xuất trong Trợ lý GYO' })).toBeDefined();
    vi.mocked(actionPackagesApi.approveActionPackage).mockResolvedValue({
      id: 'package-1', session_id: 'session-1', title: 'Update test step', description: null,
      package_hash: 'hash', status: 'approved', created_at: 1, updated_at: 2, steps: [],
    });
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt gói đề xuất' }));
    await waitFor(() => expect(actionPackagesApi.approveActionPackage).toHaveBeenCalledWith(
      'package-1', { expectedRevision: 1, expectedPayloadHash: 'payload-hash' }, 'test-decision-key',
    ));
  });

  it('characterization baseline: reloads the authoritative package after assistant-package 409', async () => {
    vi.mocked(skillsApi.fetchSkills).mockResolvedValue([]);
    vi.mocked(dirapApi.listWorkItems).mockResolvedValue([]);
    vi.mocked(hubApi.searchMemoryHub).mockResolvedValue([]);
    const pending = {
      id: 'package-409', session_id: 'session-1', title: 'Gói cạnh tranh', description: null,
      package_hash: 'hash', status: 'awaiting_approval' as const, created_at: 1, updated_at: 1,
      steps: [{ id: 'step-409', sort_order: 0, kind: 'work_plan_step_update', risk_level: 'local_mutation', status: 'pending', input: {} }],
    };
    const decided = { ...pending, status: 'approved' as const, updated_at: 2 };
    vi.mocked(actionPackagesApi.getWorkActionPackages)
      .mockResolvedValueOnce([pending])
      .mockResolvedValueOnce([decided]);
    vi.mocked(actionPackagesApi.approveActionPackage).mockRejectedValue(new ApiError(409, 'already decided'));

    render(<ReviewInboxPanel />);
    expect(await screen.findByText('Gói cạnh tranh')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt gói đề xuất' }));

    expect(await screen.findByText('Mục này đã được xử lý ở nơi khác. Danh sách đang được làm mới.')).toBeDefined();
    await waitFor(() => expect(actionPackagesApi.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('button', { name: 'Duyệt gói đề xuất' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Đã quyết định (1)' }));
    expect(await screen.findByText('approved')).toBeDefined();
  });
});
