import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LeftNavigation } from './LeftNavigation';

describe('LeftNavigation', () => {
  it('keeps Home fixed, projects primary Modules, and pins Settings outside the Module list', () => {
    const onSelectTab = vi.fn();
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
    expect(screen.getByRole('button', { name: 'Công việc' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Thư viện' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Hộp duyệt' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Báo cáo' })).toBeDefined();

    const settings = screen.getByRole('button', { name: 'Cài đặt' });
    expect(settings.closest('.foundation-sidebar-footer')).not.toBeNull();
    fireEvent.click(settings);
    expect(onSelectTab).toHaveBeenCalledWith('settings');
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
