import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ModuleInstance } from '../../api/modules';
import { useModuleProjectionStore } from '../modules/store';
import { LeftNavigation } from './LeftNavigation';

const projected = (
  overrides: Partial<ModuleInstance> & Pick<ModuleInstance, 'module_id' | 'display_name'>,
): ModuleInstance => {
  const {
    module_id,
    display_name,
    id = `builtin:${overrides.module_id}`,
    ...rest
  } = overrides;
  return {
    id,
    module_id,
    source_kind: 'builtin',
    package_id: null,
    display_name,
    attached: true,
    sort_order: 10,
    config: {},
    config_version: 1,
    health_state: 'ready',
    revision: 1,
    created_at: 1,
    updated_at: 1,
    ...rest,
  };
};

const unavailableProjectionStatuses = ['idle', 'loading', 'error'] as const;

describe('LeftNavigation', () => {
  beforeEach(() => {
    useModuleProjectionStore.setState({ instances: [], status: 'error', error: 'test fallback' });
  });

  it.each(unavailableProjectionStatuses)('keeps Foundation navigation available but hides Modules while projection is %s', (status) => {
    const onSelectTab = vi.fn();
    useModuleProjectionStore.setState({
      instances: [projected({ module_id: 'documents', display_name: 'Tài liệu' })],
      status,
      error: status === 'error' ? 'projection unavailable' : null,
    });

    render(
      <LeftNavigation
        activeTab="overview"
        currentWorkTitle="Work A"
        mobileMenuOpen={false}
        activityOpen={false}
        onSelectTab={onSelectTab}
        onOpenMobileMenu={vi.fn()}
        onCloseMobileMenu={vi.fn()}
        onOpenActivity={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: 'Tổng quan' })).toBeDefined();
    expect(screen.queryByRole('button', { name: 'Tài liệu' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Công việc' })).toBeNull();

    const settings = screen.getByRole('button', { name: 'Cài đặt' });
    expect(settings.closest('.foundation-sidebar-footer')).not.toBeNull();
    fireEvent.click(settings);
    expect(onSelectTab).toHaveBeenCalledWith('settings');
  });

  it('uses persisted attachment, order and display names when the projection is ready', () => {
    useModuleProjectionStore.setState({
      status: 'ready',
      error: null,
      instances: [
        projected({ module_id: 'reports', display_name: 'Báo cáo quản trị', sort_order: 20 }),
        projected({ module_id: 'documents', display_name: 'Hồ sơ', sort_order: 10 }),
        projected({ module_id: 'knowledge', display_name: 'Không hiển thị', attached: false, sort_order: 30 }),
      ],
    });

    render(
      <LeftNavigation
        activeTab="files"
        currentWorkTitle="Work A"
        mobileMenuOpen={false}
        activityOpen={false}
        onSelectTab={vi.fn()}
        onOpenMobileMenu={vi.fn()}
        onCloseMobileMenu={vi.fn()}
        onOpenActivity={vi.fn()}
      />,
    );

    const buttons = screen.getAllByRole('button');
    const labels = buttons.map(button => button.textContent?.trim()).filter(Boolean);
    expect(labels.indexOf('Hồ sơ')).toBeLessThan(labels.indexOf('Báo cáo quản trị'));
    expect(screen.queryByRole('button', { name: 'Không hiển thị' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Cài đặt' })).toBeDefined();
  });

  it('keeps the current Work and context drawer action visible independently of Module selection', () => {
    const onOpenActivity = vi.fn();
    render(
      <LeftNavigation
        activeTab="reports"
        currentWorkTitle="Đề án nhân lực"
        mobileMenuOpen={false}
        activityOpen={false}
        onSelectTab={vi.fn()}
        onOpenMobileMenu={vi.fn()}
        onCloseMobileMenu={vi.fn()}
        onOpenActivity={onOpenActivity}
      />,
    );

    expect(screen.getByText('Đề án nhân lực')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Lịch sử & ngữ cảnh' }));
    expect(onOpenActivity).toHaveBeenCalledOnce();
  });
});
