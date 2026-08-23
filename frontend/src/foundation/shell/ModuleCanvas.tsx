import React from 'react';
import type { SidebarTab } from '../../store/store';
import { useHermesStore } from '../../store/store';
import { AssistantChatSidebar } from '../../components/AssistantChatSidebar';
import { DirapPanel } from '../../components/DirapPanel';
import { EditorPanel } from '../../components/EditorPanel';
import { FileExplorer } from '../../components/FileExplorer';
import { KnowledgePanel } from '../../components/KnowledgePanel';
import { LocalDataPanel } from '../../components/LocalDataPanel';
import { MemoryHubPanel } from '../../components/MemoryHubPanel';
import { MemoryPanel } from '../../components/MemoryPanel';
import { OverviewPanel } from '../../components/OverviewPanel';
import { ReportsPanel } from '../../components/ReportsPanel';
import { ReviewInboxPanel } from '../../components/ReviewInboxPanel';
import { SettingsPanel } from '../../components/SettingsPanel';
import { WorkWorkspace } from '../../components/WorkWorkspace';

export interface ModuleCanvasProps {
  activeTab: SidebarTab;
  activeWorkId: string | null;
  assistantFocusRoute: boolean;
}

/**
 * Transitional first-party ModuleCanvas. Rendering is still static in Wave 1;
 * registry-backed persistence/attachment is intentionally deferred to F5.
 */
export function ModuleCanvas({ activeTab, activeWorkId, assistantFocusRoute }: ModuleCanvasProps) {
  const activeFile = useHermesStore(state => state.activeFile);
  const openFiles = useHermesStore(state => state.openFiles);
  const showEditor = Boolean(activeWorkId && activeFile && openFiles.length > 0);

  if (assistantFocusRoute) return <AssistantChatSidebar surfaceMode="focus" />;

  if (activeTab === 'overview') return <OverviewPanel />;
  if (activeTab === 'sessions') return <WorkWorkspace />;
  if (activeTab === 'files') {
    return (
      <div className="documents-surface">
        <aside className="documents-rail">
          {activeWorkId ? <FileExplorer /> : <div className="empty-state">Chọn một Công việc để quản lý tài liệu.</div>}
        </aside>
        <section className="document-editor-surface">
          {showEditor ? <EditorPanel /> : (
            <div className="empty-state centered-empty-state">
              <div className="empty-state-title">Tài liệu của Công việc</div>
              <div className="empty-state-text">Nhập, tạo hoặc chọn một tệp ở bên trái để xem và chỉnh sửa.</div>
            </div>
          )}
        </section>
      </div>
    );
  }
  if (activeTab === 'skills') return <div className="full-surface"><KnowledgePanel /></div>;
  if (activeTab === 'reports') return <div className="full-surface"><ReportsPanel /></div>;
  if (activeTab === 'review') return <div className="full-surface"><ReviewInboxPanel /></div>;
  if (activeTab === 'settings') return <div className="full-surface"><SettingsPanel /></div>;
  if (activeTab === 'memory') return <div className="full-surface"><MemoryPanel /></div>;
  if (activeTab === 'memory-hub') return <div className="full-surface"><MemoryHubPanel /></div>;
  if (activeTab === 'data') return <div className="full-surface"><LocalDataPanel /></div>;
  if (activeTab === 'dirap') {
    return <div className="full-surface">{activeWorkId ? <DirapPanel /> : <div className="empty-state">Chọn một Công việc để duyệt tri thức.</div>}</div>;
  }

  return null;
}
