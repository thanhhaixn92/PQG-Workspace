import React from 'react';
import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileChartColumn,
  History,
  LayoutDashboard,
  Library,
  Menu,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import { getPrimaryModuleDefinitions, type ModuleId } from '../modules/registry';
import type { SidebarTab } from '../../store/store';
import { PRODUCT_NAME, PRODUCT_SHORT_NAME } from '../../branding';

const iconByModule: Partial<Record<ModuleId, LucideIcon>> = {
  work: BriefcaseBusiness,
  knowledge: Library,
  review: ClipboardCheck,
  reports: FileChartColumn,
};

const titleByTab: Partial<Record<SidebarTab, string>> = {
  sessions: 'Công việc',
  skills: 'Thư viện tri thức',
  review: 'Hộp duyệt',
  reports: 'Báo cáo',
};

export interface LeftNavigationProps {
  activeTab: SidebarTab;
  currentWorkTitle: string;
  mobileMenuOpen: boolean;
  activityOpen: boolean;
  onSelectTab: (tab: SidebarTab) => void;
  onOpenMobileMenu: () => void;
  onCloseMobileMenu: () => void;
  onOpenActivity: (event: React.MouseEvent<HTMLButtonElement>) => void;
}

export function LeftNavigation({
  activeTab,
  currentWorkTitle,
  mobileMenuOpen,
  activityOpen,
  onSelectTab,
  onOpenMobileMenu,
  onCloseMobileMenu,
  onOpenActivity,
}: LeftNavigationProps) {
  const primaryModules = getPrimaryModuleDefinitions();

  return (
    <nav className={`panel sidebar-panel foundation-sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`} aria-label="Điều hướng PQG Workspace">
      <div className="product-identity" aria-label={PRODUCT_NAME}>
        <strong>
          <span className="product-name-full">{PRODUCT_NAME}</span>
          <span className="product-name-compact" aria-hidden="true">{PRODUCT_SHORT_NAME}</span>
        </strong>
        <span>Trợ lý công việc cá nhân chạy trên máy của bạn</span>
      </div>

      <div className="sidebar-tabs">
        <button className={`sidebar-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => onSelectTab('overview')} title="Tổng quan">
          <LayoutDashboard aria-hidden="true" /><span className="nav-label">Tổng quan</span>
        </button>

        {primaryModules.map(module => {
          const Icon = iconByModule[module.id] ?? LayoutDashboard;
          const advancedClass = module.tab === 'review' || module.tab === 'reports' ? ' advanced-tab' : '';
          return (
            <button
              key={module.id}
              className={`sidebar-tab${advancedClass} ${activeTab === module.tab ? 'active' : ''}`.trim()}
              onClick={() => onSelectTab(module.tab)}
              title={titleByTab[module.tab] ?? module.defaultLabel}
            >
              <Icon aria-hidden="true" /><span className="nav-label">{module.defaultLabel}</span>
            </button>
          );
        })}

        <button className="sidebar-tab mobile-more" onClick={onOpenMobileMenu}>
          <Menu aria-hidden="true" /><span className="nav-label">Thêm</span>
        </button>
        <button className="sidebar-tab mobile-close" onClick={onCloseMobileMenu}>
          <Menu aria-hidden="true" /><span className="nav-label">Đóng</span>
        </button>
      </div>

      <div className="navigation-context">
        <span className="navigation-context-label">Công việc hiện tại</span>
        <strong className="navigation-context-work">{currentWorkTitle}</strong>
        <button className="btn-secondary compact-button context-drawer-trigger" type="button" onClick={onOpenActivity} aria-expanded={activityOpen} title="Lịch sử & ngữ cảnh">
          <History aria-hidden="true" /><span>Lịch sử & ngữ cảnh</span>
        </button>
      </div>

      <div className="foundation-sidebar-footer">
        <button className={`sidebar-tab foundation-settings-tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => onSelectTab('settings')} title="Cài đặt">
          <Settings aria-hidden="true" /><span className="nav-label">Cài đặt</span>
        </button>
      </div>
    </nav>
  );
}
