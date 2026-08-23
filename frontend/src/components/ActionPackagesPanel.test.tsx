import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ActionPackagesPanel } from './ActionPackagesPanel';
import * as api from '../api/actionPackages';
import { ApiError } from '../api/client';

vi.mock('../api/actionPackages', () => ({
  getWorkActionPackages: vi.fn(),
  approveActionPackage: vi.fn(),
  denyActionPackage: vi.fn(),
  getActionPackageDecisionBinding: vi.fn((item: { revision?: number; payload_hash?: string }) => (
    typeof item.revision === 'number' && item.payload_hash ? { expectedRevision: item.revision, expectedPayloadHash: item.payload_hash } : null
  )),
  createActionPackageIdempotencyKey: vi.fn(() => 'test-decision-key'),
}));

const packageItem = {
  id: 'package-1', session_id: 'work-1', title: 'Cập nhật kế hoạch', description: 'Đánh dấu bước đã xong',
  package_hash: 'hash', payload_hash: 'payload-hash', revision: 1, status: 'awaiting_approval', created_at: 1, updated_at: 1,
  steps: [{ id: 'step-1', sort_order: 0, kind: 'work_plan_step_update', risk_level: 'write', status: 'awaiting_approval', input: {} }],
};

describe('ActionPackagesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getWorkActionPackages).mockResolvedValue([packageItem]);
  });

  it('explains impact and reversibility before the user approves', async () => {
    render(<ActionPackagesPanel workId="work-1" />);
    expect(await screen.findByText(/Cách duyệt:/i)).toBeDefined();
    expect(screen.getByText(/trò chuyện hoặc giao việc không tự thay đổi dữ liệu/i)).toBeDefined();
    expect(await screen.findByText('Tác động')).toBeDefined();
    expect(screen.getByText(/không thay đổi tài liệu hay dữ liệu Công việc khác/i)).toBeDefined();
    expect(screen.getByText('Hoàn tác')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Duyệt' })).toBeDefined();
  });

  it('records the decision only when the user presses approve', async () => {
    vi.mocked(api.approveActionPackage).mockResolvedValue({ ...packageItem, status: 'approved' });
    render(<ActionPackagesPanel workId="work-1" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Duyệt' }));
    await waitFor(() => expect(api.approveActionPackage).toHaveBeenCalledWith('package-1', { expectedRevision: 1, expectedPayloadHash: 'payload-hash' }, 'test-decision-key'));
  });

  it('refreshes authoritative Work package state and removes stale CTA after a 409 decision conflict', async () => {
    vi.mocked(api.getWorkActionPackages)
      .mockResolvedValueOnce([packageItem])
      .mockResolvedValueOnce([{ ...packageItem, status: 'approved', updated_at: 2 }]);
    vi.mocked(api.approveActionPackage).mockRejectedValue(new ApiError(409, 'already decided'));
    render(<ActionPackagesPanel workId="work-1" />);
    expect(await screen.findByRole('button', { name: 'Duyệt' })).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt' }));
    expect(await screen.findByText('Mục đã được xử lý ở nơi khác. Trạng thái đang được làm mới.')).toBeDefined();
    await waitFor(() => expect(api.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('button', { name: 'Duyệt' })).toBeNull();
  });

  it('refreshes authoritative Work package state after a deny 409 decision conflict', async () => {
    vi.mocked(api.getWorkActionPackages)
      .mockResolvedValueOnce([packageItem])
      .mockResolvedValueOnce([{ ...packageItem, status: 'approved', updated_at: 2 }]);
    vi.mocked(api.denyActionPackage).mockRejectedValue(new ApiError(409, 'already decided'));

    render(<ActionPackagesPanel workId="work-1" />);
    expect(await screen.findByRole('button', { name: 'Từ chối' })).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: 'Từ chối' }));

    expect(
      await screen.findByText('Mục đã được xử lý ở nơi khác. Trạng thái đang được làm mới.'),
    ).toBeDefined();
    await waitFor(() => expect(api.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(api.denyActionPackage).toHaveBeenCalledWith('package-1', { expectedRevision: 1, expectedPayloadHash: 'payload-hash' }, 'test-decision-key');
    expect(screen.queryByRole('button', { name: 'Từ chối' })).toBeNull();
  });
});
