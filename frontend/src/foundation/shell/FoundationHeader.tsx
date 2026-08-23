import React from 'react';
import { History, Moon, Sun } from 'lucide-react';
import type { SidebarTab, ThemeMode } from '../../store/store';

export interface FoundationHeaderProps {
  activeTab: SidebarTab;
  currentWorkTitle: string;
  theme: ThemeMode;
  activityOpen: boolean;
  onToggleTheme: () => void;
  onOpenActivity: (event: React.MouseEvent<HTMLButtonElement>) => void;
}

export function FoundationHeader({
  activeTab,
  currentWorkTitle,
  theme,
  activityOpen,
  onToggleTheme,
  onOpenActivity,
}: FoundationHeaderProps) {
  const title = activeTab === 'sessions' ? 'Công việc' : currentWorkTitle === 'Chưa chọn' ? 'Chọn một Công việc' : currentWorkTitle;

  return (
    <div className="workspace-header foundation-header">
      <div className="header-left">
        <button
          className="btn-secondary global-theme-toggle"
          type="button"
          aria-label={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
          title={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'}
          onClick={onToggleTheme}
        >
          {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
        </button>
        <button className="btn-secondary context-drawer-mobile-trigger" type="button" onClick={onOpenActivity} aria-expanded={activityOpen}>
          <History aria-hidden="true" /> Ngữ cảnh
        </button>
      </div>
      <div className="header-center">
        <h1 className="workspace-title">{title}</h1>
      </div>
    </div>
  );
}
