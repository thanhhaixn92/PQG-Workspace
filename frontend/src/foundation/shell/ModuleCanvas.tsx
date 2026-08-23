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
import { getModuleDefinitionByTab } from '../modules/registry';
import { useModuleProjectionStore } from '../modules/store';

export interface ModuleCanvasProps {
  activeTab: SidebarTab;
  activeWorkId: string | null;
  assistantFocusRoute: boolean;
}

/** First-party ModuleCanvas with persisted attachment eligibility. */
export function ModuleCanvas({ activeTab, activeWorkId, assistantFocusRoute }: ModuleCanvasProps) {
  const activeFile = useHermesStore(state => state.activeFile);
  const openFiles = useHermesStore(state => state.openFiles);
  const setSidebarTab = useHermesStore(state => state.setSidebarTab);
  const moduleInstances = useModuleProjectionStore(state => state.instances);
  const moduleProjectionStatus = useModuleProjectionStore(state => state.status);
  const showEditor = Boolean(activeWorkId && activeFile && openFiles.length > 0);

  if (assistantFocusRoute) return <AssistantChatSidebar surfaceMode="focus" />;

  const moduleDefinition = getModuleDefinitionByTab(activeTab);
  if (moduleDefinition) {
    if (moduleProjectionStatus !== 'ready') {
      const waitingForProjection = moduleProjectionStatus === 'idle' || moduleProjectionStatus === 'loading';
      return (
        <div className="full-surface">
          <div className="empty-state centered-empty-state" role="status">
            <div className="empty-state-title">Chưa thể xác minh trạng thái Module</div>
            <div className="empty-state-text">
              {waitingForProjection
                ? 'PQG Workspace đang tải trạng thái gắn Module. Module chỉ mở sau khi trạng thái được xác minh.'
                : 'Không tải được trạng thái gắn Module. Để tránh hiển thị lại Module đã tháo, nội dung Module tạm thời bị khóa.'}
            </div>
          </div>
        </div>
      );
    }

    const instance = moduleInstances.find(item => item.module_id === moduleDefinition.id);
    if (!instance?.attached) {
      return (
        <div className="full-surface">
          <div className="empty-state centered-empty-state" role="status">
            <div className="empty-state-title">Module đang được tháo khỏi điều hướng</div>
            <div className="empty-state-text">Dữ liệu vẫn được giữ nguyên. Bạn có thể gắn lại Module trong Cài đặt.</div>
            <button className="btn-primary" type="button" onClick={() => setSidebarTab('settings')}>Mở Cài đặt Modules</button>
          </div>
        </div>
      );
    }
  }

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
