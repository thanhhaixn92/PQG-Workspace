import { useEffect, useState } from 'react';
import type { ComponentType } from 'react';
import type { SidebarTab } from '../../store/store';
import { useHermesStore } from '../../store/store';
import { AssistantChatSidebar } from '../../components/AssistantChatSidebar';
import { OverviewPanel } from '../../components/OverviewPanel';
import { SettingsPanel } from '../../components/SettingsPanel';
import { getModuleDefinitionByTab } from '../modules/registry';
import { useModuleProjectionStore } from '../modules/store';

export type SurfaceLoader = () => Promise<{ default: ComponentType }>;

export interface ModuleCanvasLoaders {
  work: SurfaceLoader;
  fileExplorer: SurfaceLoader;
  editor: SurfaceLoader;
  knowledge: SurfaceLoader;
  reports: SurfaceLoader;
  review: SurfaceLoader;
  memory: SurfaceLoader;
  memoryHub: SurfaceLoader;
  localData: SurfaceLoader;
  research: SurfaceLoader;
}

export const DEFAULT_MODULE_CANVAS_LOADERS: ModuleCanvasLoaders = {
  work: () => import('../../components/WorkWorkspace').then(module => ({ default: module.WorkWorkspace })),
  fileExplorer: () => import('../../components/FileExplorer').then(module => ({ default: module.FileExplorer })),
  editor: () => import('../../components/EditorPanel').then(module => ({ default: module.EditorPanel })),
  knowledge: () => import('../../components/KnowledgePanel').then(module => ({ default: module.KnowledgePanel })),
  reports: () => import('../../components/ReportsPanel').then(module => ({ default: module.ReportsPanel })),
  review: () => import('../../components/ReviewInboxPanel').then(module => ({ default: module.ReviewInboxPanel })),
  memory: () => import('../../components/MemoryPanel').then(module => ({ default: module.MemoryPanel })),
  memoryHub: () => import('../../components/MemoryHubPanel').then(module => ({ default: module.MemoryHubPanel })),
  localData: () => import('../../components/LocalDataPanel').then(module => ({ default: module.LocalDataPanel })),
  research: () => import('../../components/DirapPanel').then(module => ({ default: module.DirapPanel })),
};

interface LazySurfaceProps {
  loader: SurfaceLoader;
  loadingLabel?: string;
}

function LazySurface({ loader, loadingLabel = 'Đang tải Module...' }: LazySurfaceProps) {
  const [attempt, setAttempt] = useState(0);
  const [component, setComponent] = useState<ComponentType | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    setComponent(null);
    setError(null);

    void loader()
      .then(module => {
        if (!current) return;
        setComponent(() => module.default);
      })
      .catch(err => {
        if (!current) return;
        setError(err instanceof Error ? err.message : 'Không tải được nội dung Module');
      });

    return () => {
      current = false;
    };
  }, [attempt, loader]);

  if (error) {
    return (
      <div className="empty-state centered-empty-state" role="alert">
        <div className="empty-state-title">Không tải được nội dung Module</div>
        <div className="empty-state-text">{error}</div>
        <button className="btn-primary" type="button" onClick={() => setAttempt(value => value + 1)}>Thử lại</button>
      </div>
    );
  }

  if (!component) {
    return <div className="runtime-guidance" role="status">{loadingLabel}</div>;
  }

  const Component = component;
  return <Component />;
}

export interface ModuleCanvasProps {
  activeTab: SidebarTab;
  activeWorkId: string | null;
  assistantFocusRoute: boolean;
  loaders?: ModuleCanvasLoaders;
}

/** First-party ModuleCanvas with persisted attachment eligibility and post-authorization lazy loading. */
export function ModuleCanvas({
  activeTab,
  activeWorkId,
  assistantFocusRoute,
  loaders = DEFAULT_MODULE_CANVAS_LOADERS,
}: ModuleCanvasProps) {
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
  if (activeTab === 'sessions') return <LazySurface loader={loaders.work} loadingLabel="Đang tải Công việc..." />;
  if (activeTab === 'files') {
    return (
      <div className="documents-surface">
        <aside className="documents-rail">
          {activeWorkId
            ? <LazySurface loader={loaders.fileExplorer} loadingLabel="Đang tải danh sách tài liệu..." />
            : <div className="empty-state">Chọn một Công việc để quản lý tài liệu.</div>}
        </aside>
        <section className="document-editor-surface">
          {showEditor ? <LazySurface loader={loaders.editor} loadingLabel="Đang tải trình soạn thảo..." /> : (
            <div className="empty-state centered-empty-state">
              <div className="empty-state-title">Tài liệu của Công việc</div>
              <div className="empty-state-text">Nhập, tạo hoặc chọn một tệp ở bên trái để xem và chỉnh sửa.</div>
            </div>
          )}
        </section>
      </div>
    );
  }
  if (activeTab === 'skills') return <div className="full-surface"><LazySurface loader={loaders.knowledge} /></div>;
  if (activeTab === 'reports') return <div className="full-surface"><LazySurface loader={loaders.reports} /></div>;
  if (activeTab === 'review') return <div className="full-surface"><LazySurface loader={loaders.review} /></div>;
  if (activeTab === 'settings') return <div className="full-surface"><SettingsPanel /></div>;
  if (activeTab === 'memory') return <div className="full-surface"><LazySurface loader={loaders.memory} /></div>;
  if (activeTab === 'memory-hub') return <div className="full-surface"><LazySurface loader={loaders.memoryHub} /></div>;
  if (activeTab === 'data') return <div className="full-surface"><LazySurface loader={loaders.localData} /></div>;
  if (activeTab === 'dirap') {
    return (
      <div className="full-surface">
        {activeWorkId
          ? <LazySurface loader={loaders.research} loadingLabel="Đang tải Nghiên cứu..." />
          : <div className="empty-state">Chọn một Công việc để duyệt tri thức.</div>}
      </div>
    );
  }

  return null;
}
