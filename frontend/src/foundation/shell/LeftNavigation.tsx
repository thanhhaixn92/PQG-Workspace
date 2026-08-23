import React, { useMemo } from 'react';
import {
  Brain,
  BriefcaseBusiness,
  ClipboardCheck,
  Database,
  FileChartColumn,
  FileText,
  History,
  LayoutDashboard,
  Library,
  Menu,
  Search,
  Settings,
  type LucideIcon,
} from 'lucide-react';
import {
  getModuleDefinitionById,
  type ModuleId,
} from '../modules/registry';
import { useModuleProjectionStore } from '../modules/store';
import type { SidebarTab } from '../../store/store';
import { PRODUCT_NAME, PRODUCT_SHORT_NAME } from '../../branding';

const iconByModule: Partial<Record<ModuleId, LucideIcon>> = {
  work: BriefcaseBusiness,
  documents: FileText,
  knowledge: Library,
  review: ClipboardCheck,
  reports: FileChartColumn,
  memory: Brain,
  'memory-hub': Brain,
  'local-data': Database,
  research: Search,
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
  const moduleInstances = useModuleProjectionStore(state => state.instances);
  const moduleProjectionStatus = useModuleProjectionStore(state => state.status);

  const navigationModules = useMemo(() => {
    if (moduleProjectionStatus !== 'ready') {
      return [];
    }

    return moduleInstances
      .filter(instance => instance.attached)
      .sort((left, right) => left.sort_order - right.sort_order || left.module_id.localeCompare(right.module_id))
      .flatMap(instance => {
        const definition = getModuleDefinitionById(instance.module_id);
        return definition ? [{ definition, label: instance.display_name }] : [];
      });
  }, [moduleInstances, moduleProjectionStatus]);

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

        {navigationModules.map(({ definition, label }) => {
          const Icon = iconByModule[definition.id] ?? LayoutDashboard;
          const advancedClass = !definition.showInPrimaryNavigation || definition.tab === 'review' || definition.tab === 'reports'
            ? ' advanced-tab'
            : '';
          return (
            <button
              key={definition.id}
              className={`sidebar-tab${advancedClass} ${activeTab === definition.tab ? 'active' : ''}`.trim()}
              onClick={() => onSelectTab(definition.tab)}
              title={label}
            >
              <Icon aria-hidden="true" /><span className="nav-label">{label}</span>
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
