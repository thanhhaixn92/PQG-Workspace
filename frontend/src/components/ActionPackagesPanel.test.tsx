import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ActionPackagesPanel } from './ActionPackagesPanel';
import * as api from '../api/actionPackages';
import { ApiError } from '../api/client';

vi.mock('../api/actionPackages', () => ({
  getWorkActionPackages: vi.fn(),
  getActionPackagePreflight: vi.fn(),
  approveActionPackage: vi.fn(),
  denyActionPackage: vi.fn(),
  getActionPackageDecisionBinding: vi.fn((item: { revision?: number; payload_hash?: string }) => (
    typeof item.revision === 'number' && Number.isInteger(item.revision) && item.revision >= 1 && item.payload_hash
      ? { expectedRevision: item.revision, expectedPayloadHash: item.payload_hash }
      : null
  )),
  getActionPackagePreflightDecisionBinding: vi.fn((preflight: { valid: boolean; revision?: number; payload_hash?: string }) => (
    preflight.valid === true
      && typeof preflight.revision === 'number'
      && Number.isInteger(preflight.revision)
      && preflight.revision >= 1
      && preflight.payload_hash
      ? { expectedRevision: preflight.revision, expectedPayloadHash: preflight.payload_hash }
      : null
  )),
  createActionPackageIdempotencyKey: vi.fn(() => 'test-decision-key'),
}));

const packageItem = {
  id: 'package-1', session_id: 'work-1', title: 'Cập nhật kế hoạch', description: 'Đánh dấu bước đã xong',
  package_hash: 'hash', payload_hash: 'payload-hash', revision: 1, status: 'awaiting_approval', created_at: 1, updated_at: 1,
  steps: [{ id: 'step-1', sort_order: 0, kind: 'work_plan_step_update', risk_level: 'write', status: 'awaiting_approval', input: {} }],
};

const validPreflight = {
  package_id: 'package-1', revision: 1, payload_hash: 'payload-hash', valid: true,
};

describe('ActionPackagesPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getWorkActionPackages).mockResolvedValue([packageItem]);
    vi.mocked(api.getActionPackagePreflight).mockResolvedValue(validPreflight);
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

  it('re-preflights at click time and approves with the exact current canonical binding', async () => {
    vi.mocked(api.approveActionPackage).mockResolvedValue({ ...packageItem, status: 'approved' });
    render(<ActionPackagesPanel workId="work-1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Duyệt' }));

    await waitFor(() => expect(api.getActionPackagePreflight).toHaveBeenCalledWith('package-1'));
    await waitFor(() => expect(api.approveActionPackage).toHaveBeenCalledWith(
      'package-1',
      { expectedRevision: 1, expectedPayloadHash: 'payload-hash' },
      'test-decision-key',
    ));
    expect(api.createActionPackageIdempotencyKey).toHaveBeenCalledAfter(api.getActionPackagePreflight as ReturnType<typeof vi.fn>);
  });

  it('blocks approval when the click-time preflight binding is stale and refreshes authoritative state', async () => {
    vi.mocked(api.getActionPackagePreflight).mockResolvedValue({
      package_id: 'package-1', revision: 2, payload_hash: 'new-payload-hash', valid: true,
    });
    vi.mocked(api.getWorkActionPackages)
      .mockResolvedValueOnce([packageItem])
      .mockResolvedValueOnce([{ ...packageItem, revision: 2, payload_hash: 'new-payload-hash', updated_at: 2 }]);

    render(<ActionPackagesPanel workId="work-1" />);
    fireEvent.click(await screen.findByRole('button', { name: 'Duyệt' }));

    await waitFor(() => expect(api.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(api.approveActionPackage).not.toHaveBeenCalled();
    expect(api.denyActionPackage).not.toHaveBeenCalled();
    expect(api.createActionPackageIdempotencyKey).not.toHaveBeenCalled();
    expect(await screen.findByText(/đã thay đổi, hết hạn hoặc được xử lý ở nơi khác/i)).toBeDefined();
  });

  it('blocks approval when click-time preflight returns 409/expired and refreshes authoritative state', async () => {
    vi.mocked(api.getActionPackagePreflight).mockRejectedValue(new ApiError(409, 'expired'));
    render(<ActionPackagesPanel workId="work-1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Duyệt' }));

    await waitFor(() => expect(api.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(api.approveActionPackage).not.toHaveBeenCalled();
    expect(api.createActionPackageIdempotencyKey).not.toHaveBeenCalled();
  });

  it('blocks approval on invalid preflight without sending a decision', async () => {
    vi.mocked(api.getActionPackagePreflight).mockResolvedValue({ package_id: 'package-1', valid: false, errors: ['invalid'] });
    render(<ActionPackagesPanel workId="work-1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Duyệt' }));

    await waitFor(() => expect(api.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(api.approveActionPackage).not.toHaveBeenCalled();
    expect(api.denyActionPackage).not.toHaveBeenCalled();
    expect(api.createActionPackageIdempotencyKey).not.toHaveBeenCalled();
  });

  it('blocks approval on preflight network failure without sending a decision', async () => {
    vi.mocked(api.getActionPackagePreflight).mockRejectedValue(new Error('network failed'));
    render(<ActionPackagesPanel workId="work-1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Duyệt' }));

    await waitFor(() => expect(api.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(api.approveActionPackage).not.toHaveBeenCalled();
    expect(api.denyActionPackage).not.toHaveBeenCalled();
    expect(await screen.findByText(/Không có quyết định nào được gửi/i)).toBeDefined();
  });

  it('re-preflights deny and uses the exact current canonical binding', async () => {
    vi.mocked(api.denyActionPackage).mockResolvedValue({ ...packageItem, status: 'cancelled' });
    render(<ActionPackagesPanel workId="work-1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Từ chối' }));

    await waitFor(() => expect(api.getActionPackagePreflight).toHaveBeenCalledWith('package-1'));
    await waitFor(() => expect(api.denyActionPackage).toHaveBeenCalledWith(
      'package-1',
      { expectedRevision: 1, expectedPayloadHash: 'payload-hash' },
      'test-decision-key',
    ));
    expect(api.approveActionPackage).not.toHaveBeenCalled();
  });

  it('prevents a double click from duplicating preflight or approval', async () => {
    let resolvePreflight!: (value: typeof validPreflight) => void;
    vi.mocked(api.getActionPackagePreflight).mockReturnValue(new Promise(resolve => { resolvePreflight = resolve; }));
    vi.mocked(api.approveActionPackage).mockResolvedValue({ ...packageItem, status: 'approved' });
    render(<ActionPackagesPanel workId="work-1" />);

    const approve = await screen.findByRole('button', { name: 'Duyệt' });
    fireEvent.click(approve);
    fireEvent.click(approve);

    expect(api.getActionPackagePreflight).toHaveBeenCalledTimes(1);
    expect(api.approveActionPackage).not.toHaveBeenCalled();

    resolvePreflight(validPreflight);
    await waitFor(() => expect(api.approveActionPackage).toHaveBeenCalledTimes(1));
  });
});
