import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client';
import * as modulesApi from '../../api/modules';
import type { ModuleInstance } from '../../api/modules';
import { useModuleProjectionStore } from '../modules/store';
import { ModulesSettings } from './ModulesSettings';

vi.mock('../../api/modules', () => ({
  getModuleInstances: vi.fn(),
  attachModule: vi.fn(),
  detachModule: vi.fn(),
  renameModule: vi.fn(),
  reorderModules: vi.fn(),
}));

const moduleInstance = (
  moduleId: string,
  displayName: string,
  attached: boolean,
  sortOrder: number,
  revision = 1,
): ModuleInstance => ({
  id: `builtin:${moduleId}`,
  module_id: moduleId,
  source_kind: 'builtin',
  package_id: null,
  display_name: displayName,
  attached,
  sort_order: sortOrder,
  config: {},
  config_version: 1,
  health_state: 'ready',
  revision,
  created_at: 1,
  updated_at: 1,
});

const initialInstances = [
  moduleInstance('work', 'Công việc', true, 10),
  moduleInstance('documents', 'Tài liệu', false, 20),
  moduleInstance('reports', 'Báo cáo', true, 30),
];

describe('ModulesSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useModuleProjectionStore.setState({
      instances: initialInstances,
      status: 'ready',
      error: null,
    });
  });

  it('attaches a Module with its current revision and exposes no delete control', async () => {
    vi.mocked(modulesApi.attachModule).mockResolvedValue(
      moduleInstance('documents', 'Tài liệu', true, 40, 2),
    );
    render(<ModulesSettings />);

    const card = screen.getByText('Tài liệu').closest('article');
    expect(card).not.toBeNull();
    fireEvent.click(within(card!).getByRole('button', { name: 'Gắn vào điều hướng' }));

    await waitFor(() => expect(modulesApi.attachModule).toHaveBeenCalledWith('documents', 1));
    expect(screen.queryByRole('button', { name: /xóa|delete|uninstall/i })).toBeNull();
    expect(screen.getAllByText(/không.*xóa dữ liệu/i).length).toBeGreaterThan(0);
  });

  it('detaches without presenting any data deletion action', async () => {
    vi.mocked(modulesApi.detachModule).mockResolvedValue(
      moduleInstance('work', 'Công việc', false, 10, 2),
    );
    render(<ModulesSettings />);

    const card = screen.getByText('Công việc').closest('article');
    fireEvent.click(within(card!).getByRole('button', { name: 'Tháo khỏi điều hướng' }));

    await waitFor(() => expect(modulesApi.detachModule).toHaveBeenCalledWith('work', 1));
    expect(await screen.findByText(/Dữ liệu của Module được giữ nguyên/)).toBeDefined();
  });

  it('renames display text without changing Module identity', async () => {
    vi.mocked(modulesApi.renameModule).mockResolvedValue(
      moduleInstance('documents', 'Hồ sơ', false, 20, 2),
    );
    render(<ModulesSettings />);

    const input = screen.getByLabelText('Tên hiển thị cho documents');
    fireEvent.change(input, { target: { value: 'Hồ sơ' } });
    const card = screen.getByText('Tài liệu').closest('article');
    fireEvent.click(within(card!).getByRole('button', { name: 'Lưu tên' }));

    await waitFor(() => expect(modulesApi.renameModule).toHaveBeenCalledWith('documents', 'Hồ sơ', 1));
    expect(useModuleProjectionStore.getState().instances.find(item => item.module_id === 'documents')?.display_name).toBe('Hồ sơ');
  });

  it('moves attached Modules with explicit Up/Down controls and revision binding', async () => {
    vi.mocked(modulesApi.reorderModules).mockResolvedValue([
      moduleInstance('reports', 'Báo cáo', true, 10, 2),
      moduleInstance('work', 'Công việc', true, 20, 2),
      moduleInstance('documents', 'Tài liệu', false, 20, 1),
    ]);
    render(<ModulesSettings />);

    const reportsCard = screen.getByText('Báo cáo').closest('article');
    fireEvent.click(within(reportsCard!).getByRole('button', { name: 'Lên' }));

    await waitFor(() => expect(modulesApi.reorderModules).toHaveBeenCalledWith(
      ['reports', 'work'],
      { work: 1, reports: 1 },
    ));
  });

  it('surfaces stale revision conflicts instead of retrying silently', async () => {
    vi.mocked(modulesApi.detachModule).mockRejectedValue(new ApiError(409, 'stale'));
    render(<ModulesSettings />);

    const card = screen.getByText('Công việc').closest('article');
    fireEvent.click(within(card!).getByRole('button', { name: 'Tháo khỏi điều hướng' }));

    expect(await screen.findByText(/Trạng thái Module đã thay đổi/)).toBeDefined();
    expect(modulesApi.detachModule).toHaveBeenCalledTimes(1);
  });
});
