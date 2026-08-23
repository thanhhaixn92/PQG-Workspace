import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { BriefcaseBusiness, ClipboardCheck, FileChartColumn, History, LayoutDashboard, Library, Menu, Moon, Settings, Sun } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { getLatestSessionTaskRun, getSessionMessages, getSessions } from '../api/sessions';
import { fetchHealth } from '../api/health';
import { isTestWork } from './SessionList';
import { ApprovalModal } from './ApprovalModal';
import { FileExplorer } from './FileExplorer';
import { EditorPanel } from './EditorPanel';
import { MemoryPanel } from './MemoryPanel';
import { MemoryHubPanel } from './MemoryHubPanel';
import { LocalDataPanel } from './LocalDataPanel';
import { DirapPanel } from './DirapPanel';
import { ReportsPanel } from './ReportsPanel';
import { OverviewPanel } from './OverviewPanel';
import { KnowledgePanel } from './KnowledgePanel';
import { ReviewInboxPanel } from './ReviewInboxPanel';
import { SettingsPanel } from './SettingsPanel';
import { WorkWorkspace } from './WorkWorkspace';
import { WorkContextDrawer } from './WorkContextDrawer';
import { AssistantChatSidebar } from './AssistantChatSidebar';
import { ContextDrawer } from './ui/ContextDrawer';
import { PRODUCT_NAME, PRODUCT_SHORT_NAME } from '../branding';
import { AppShell } from './ui/AppShell';
import { subscribeToSessionEvents, unsubscribeFromSessionEvents } from '../api/events';
import { fetchPendingApprovals } from '../api/approvals';
import { isGyoAssistantRoute } from '../navigation';

function taskRunToSessionStatus(status?: string) {
  switch (status) {
    case 'queued': return 'queued' as const;
    case 'running': return 'running' as const;
    case 'waiting_approval': return 'waiting_approval' as const;
    case 'failed': return 'error' as const;
    default: return 'idle' as const;
  }
}

function taskStartedAtMs(status?: string, startedAt?: number | null): number | null {
  if (status !== 'queued' && status !== 'running' && status !== 'waiting_approval') return null;
  return startedAt ? startedAt * 1000 : Date.now();
}

const waitBeforeRetry = (milliseconds: number) => new Promise<void>(resolve => window.setTimeout(resolve, milliseconds));

async function fetchHealthWithStartupRetry() {
  try { return await fetchHealth(); }
  catch (firstError) {
    await waitBeforeRetry(700);
    try { return await fetchHealth(); } catch { throw firstError; }
  }
}

export const AppLayout: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const sessions = useHermesStore(state => state.sessions);
  const activeFile = useHermesStore(state => state.activeFile);
  const openFiles = useHermesStore(state => state.openFiles);
  const activeTab = useHermesStore(state => state.sidebarTab);
  const setSessions = useHermesStore(state => state.setSessions);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const setActiveTab = useHermesStore(state => state.setSidebarTab);
  const syncSidebarTabFromLocation = useHermesStore(state => state.syncSidebarTabFromLocation);
  const setEvents = useHermesStore(state => state.setEvents);
  const setLatestTask = useHermesStore(state => state.setLatestTask);
  const setSessionStatus = useHermesStore(state => state.setSessionStatus);
  const setSessionError = useHermesStore(state => state.setSessionError);
  const setSessionStartedAt = useHermesStore(state => state.setSessionStartedAt);
  const theme = useHermesStore(state => state.theme);
  const toggleTheme = useHermesStore(state => state.toggleTheme);
  const resetFileState = useHermesStore(state => state.resetFileState);
  const setPendingApproval = useHermesStore(state => state.setPendingApproval);
  const assistantSidebarMode = useHermesStore(state => state.assistantSidebarMode);
  const assistantSidebarWidth = useHermesStore(state => state.assistantSidebarWidth);

  useMemo(() => { document.documentElement.setAttribute('data-theme', theme); }, [theme]);

  const [backendState, setBackendState] = useState<'checking' | 'ready' | 'offline'>('checking');
  const [healthError, setHealthError] = useState<string | null>(null);
  const [workListError, setWorkListError] = useState<string | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [locationKey, setLocationKey] = useState(() => `${window.location.pathname}${window.location.search}`);
  const drawerReturnFocusRef = useRef<HTMLElement | null>(null);
  const bootstrapVersion = useRef(0);
  const showEditor = Boolean(activeSessionId && activeFile && openFiles.length > 0);
  const assistantFocusRoute = isGyoAssistantRoute(locationKey);

  const selectSidebarTab = (tab: typeof activeTab) => { setActiveTab(tab); setMobileMenuOpen(false); };
  const openActivityDrawer = (event: React.MouseEvent<HTMLButtonElement>) => { drawerReturnFocusRef.current = event.currentTarget; setActivityOpen(true); };
  const closeActivityDrawer = useCallback(() => setActivityOpen(false), []);

  const bootstrap = useCallback(async () => {
    const requestVersion = ++bootstrapVersion.current;
    setBackendState('checking'); setHealthError(null); setWorkListError(null);
    const health = fetchHealthWithStartupRetry()
      .then(() => { if (requestVersion !== bootstrapVersion.current) return; setBackendState('ready'); setHealthError(null); })
      .catch(() => { if (requestVersion !== bootstrapVersion.current) return; setBackendState('offline'); setHealthError('Không kết nối được backend local. Hãy kiểm tra dịch vụ đang chạy rồi thử lại.'); });
    const works = getSessions()
      .then((nextSessions) => {
        if (requestVersion !== bootstrapVersion.current) return;
        setSessions(nextSessions);
        const visibleSessions = nextSessions.filter(session => !isTestWork(session));
        const savedSessionId = window.localStorage.getItem('hermes.activeSessionId');
        const currentSessionId = useHermesStore.getState().activeSessionId;
        const sessionToSelect = visibleSessions.find(s => s.id === currentSessionId) || visibleSessions.find(s => s.id === savedSessionId) || visibleSessions[0];
        setActiveSession(sessionToSelect?.id ?? null);
        setWorkListError(null);
      })
      .catch(() => { if (requestVersion !== bootstrapVersion.current) return; setWorkListError('Không tải được danh sách Công việc. Bạn có thể thử lại phần này mà không làm mất nội dung đang mở.'); });
    await Promise.all([health, works]);
  }, [setActiveSession, setSessions]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);
  useEffect(() => {
    const syncLocation = () => {
      setLocationKey(`${window.location.pathname}${window.location.search}`);
      syncSidebarTabFromLocation();
    };
    window.addEventListener('popstate', syncLocation);
    return () => window.removeEventListener('popstate', syncLocation);
  }, [syncSidebarTabFromLocation]);
  useEffect(() => { resetFileState(); setPendingApproval(null); }, [activeSessionId, resetFileState, setPendingApproval]);

  useEffect(() => {
    if (!activeSessionId) { unsubscribeFromSessionEvents(); return; }
    let cancelled = false;
    const sessionId = activeSessionId;
    const failedParts = new Set<string>();
    const isCurrent = () => !cancelled && useHermesStore.getState().activeSessionId === sessionId;
    const updateRestoreError = () => {
      if (!isCurrent()) return;
      setSessionError(sessionId, failedParts.size ? `Chưa tải được ${[...failedParts].join(', ')}. Bạn có thể thử lại phần này.` : null);
    };
    void getSessionMessages(sessionId).then(messages => { if (!isCurrent()) return; setEvents(sessionId, messages.map(m => ({ id: m.id, type: m.role === 'user' ? 'user_message' : 'token', text: m.content, created_at: m.created_at }))); failedParts.delete('lịch sử trò chuyện'); updateRestoreError(); }).catch(() => { if (!isCurrent()) return; failedParts.add('lịch sử trò chuyện'); updateRestoreError(); });
    void getLatestSessionTaskRun(sessionId).then(latestTask => { if (!isCurrent()) return; const sessionStatus = taskRunToSessionStatus(latestTask?.status); setLatestTask(sessionId, latestTask); setSessionStatus(sessionId, sessionStatus); setSessionStartedAt(sessionId, taskStartedAtMs(latestTask?.status, latestTask?.started_at)); failedParts.delete('trạng thái công việc'); updateRestoreError(); if (sessionStatus === 'queued' || sessionStatus === 'running' || sessionStatus === 'waiting_approval') { subscribeToSessionEvents(sessionId); } else { unsubscribeFromSessionEvents(); } }).catch(() => { if (!isCurrent()) return; failedParts.add('trạng thái công việc'); updateRestoreError(); });
    void fetchPendingApprovals(sessionId).then(approvals => { if (!isCurrent()) return; setPendingApproval(approvals[0] ?? null); failedParts.delete('mục chờ duyệt'); updateRestoreError(); }).catch(() => { if (!isCurrent()) return; failedParts.add('mục chờ duyệt'); updateRestoreError(); });
    return () => { cancelled = true; unsubscribeFromSessionEvents(); };
  }, [activeSessionId, setEvents, setLatestTask, setSessionStatus, setSessionError, setSessionStartedAt, setPendingApproval]);

  return (
    <AppShell className={`${activityOpen ? 'activity-open' : ''} ${assistantSidebarMode === 'expanded' ? 'assistant-expanded' : assistantSidebarMode === 'collapsed' ? 'assistant-collapsed' : ''}`} style={{ '--assistant-panel-width': `${assistantSidebarWidth}px` } as React.CSSProperties}>
      <div className={`panel sidebar-panel ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="product-identity" aria-label={PRODUCT_NAME}>
          <strong><span className="product-name-full">{PRODUCT_NAME}</span><span className="product-name-compact" aria-hidden="true">{PRODUCT_SHORT_NAME}</span></strong>
          <span>Trợ lý công việc cá nhân chạy trên máy của bạn</span>
        </div>
        <div className="sidebar-tabs">
          <button className={`sidebar-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => selectSidebarTab('overview')} title="Tổng quan">
            <LayoutDashboard aria-hidden="true" /><span className="nav-label">Tổng quan</span>
          </button>
          <button className={`sidebar-tab ${activeTab === 'sessions' ? 'active' : ''}`} onClick={() => selectSidebarTab('sessions')} title="Công việc">
            <BriefcaseBusiness aria-hidden="true" /><span className="nav-label">Công việc</span>
          </button>
          <button className={`sidebar-tab ${activeTab === 'skills' ? 'active' : ''}`} onClick={() => selectSidebarTab('skills')} title="Thư viện tri thức">
            <Library aria-hidden="true" /><span className="nav-label">Thư viện</span>
          </button>
          <button className={`sidebar-tab advanced-tab ${activeTab === 'review' ? 'active' : ''}`} onClick={() => selectSidebarTab('review')} title="Hộp duyệt">
            <ClipboardCheck aria-hidden="true" /><span className="nav-label">Hộp duyệt</span>
          </button>
          <button className={`sidebar-tab advanced-tab ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => selectSidebarTab('reports')} title="Báo cáo">
            <FileChartColumn aria-hidden="true" /><span className="nav-label">Báo cáo</span>
          </button>
          <button className={`sidebar-tab advanced-tab ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => selectSidebarTab('settings')} title="Cài đặt">
            <Settings aria-hidden="true" /><span className="nav-label">Cài đặt</span>
          </button>
          <button className="sidebar-tab mobile-more" onClick={() => setMobileMenuOpen(true)}>
            <Menu aria-hidden="true" /><span className="nav-label">Thêm</span>
          </button>
          <button className="sidebar-tab mobile-close" onClick={() => setMobileMenuOpen(false)}>
            <Menu aria-hidden="true" /><span className="nav-label">Đóng</span>
          </button>
        </div>
        <div className="navigation-context">
          <span className="navigation-context-label">Công việc hiện tại</span>
          <strong className="navigation-context-work">{sessions.find(s => s.id === activeSessionId)?.title || 'Chưa chọn'}</strong>
          <button className="btn-secondary compact-button context-drawer-trigger" type="button" onClick={openActivityDrawer} aria-expanded={activityOpen} title="Lịch sử & ngữ cảnh">
            <History aria-hidden="true" /><span>Lịch sử & ngữ cảnh</span>
          </button>
        </div>
      </div>

      <main className="panel workspace-panel">
        <div className="workspace-header">
          <div className="header-left">
            <button className="btn-secondary global-theme-toggle" type="button" aria-label={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'} title={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'} onClick={toggleTheme}>
              {theme === 'dark' ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
            </button>
            <button className="btn-secondary context-drawer-mobile-trigger" type="button" onClick={openActivityDrawer} aria-expanded={activityOpen}>
              <History aria-hidden="true" /> Ngữ cảnh
            </button>
          </div>
          <div className="header-center">
            <h1 className="workspace-title">{activeTab === 'sessions' ? 'Công việc' : sessions.find(s => s.id === activeSessionId)?.title || 'Chọn một Công việc'}</h1>
          </div>
        </div>
        {(backendState === 'offline' || workListError) && (
          <div className="app-status-banner" role="status">
            <div><strong>{backendState === 'offline' ? 'Backend chưa sẵn sàng' : 'Cần chú ý'}</strong><span>{backendState === 'offline' ? healthError : workListError}</span></div>
            <button className="btn-secondary" onClick={() => void bootstrap()}>Kiểm tra lại</button>
          </div>
        )}
        {assistantFocusRoute ? <AssistantChatSidebar surfaceMode="focus" /> : <>
        {activeTab === 'overview' && <OverviewPanel />}
        {activeTab === 'sessions' && <WorkWorkspace />}
        {activeTab === 'files' && <div className="documents-surface"><aside className="documents-rail">{activeSessionId ? <FileExplorer /> : <div className="empty-state">Chọn một Công việc để quản lý tài liệu.</div>}</aside><section className="document-editor-surface">{showEditor ? <EditorPanel /> : <div className="empty-state centered-empty-state"><div className="empty-state-title">Tài liệu của Công việc</div><div className="empty-state-text">Nhập, tạo hoặc chọn một tệp ở bên trái để xem và chỉnh sửa.</div></div>}</section></div>}
        {activeTab === 'skills' && <div className="full-surface"><KnowledgePanel /></div>}
        {activeTab === 'reports' && <div className="full-surface"><ReportsPanel /></div>}
        {activeTab === 'review' && <div className="full-surface"><ReviewInboxPanel /></div>}
        {activeTab === 'settings' && <div className="full-surface"><SettingsPanel /></div>}
        {activeTab === 'memory' && <div className="full-surface"><MemoryPanel /></div>}
        {activeTab === 'memory-hub' && <div className="full-surface"><MemoryHubPanel /></div>}
        {activeTab === 'data' && <div className="full-surface"><LocalDataPanel /></div>}
        {activeTab === 'dirap' && <div className="full-surface">{activeSessionId ? <DirapPanel /> : <div className="empty-state">Chọn một Công việc để duyệt tri thức.</div>}</div>}
        </>}
      </main>

      <ContextDrawer open={activityOpen} title="Lịch sử & ngữ cảnh" onClose={closeActivityDrawer} returnFocusRef={drawerReturnFocusRef}>
        <WorkContextDrawer />
      </ContextDrawer>

      <ApprovalModal />

      {/* Assistant Chat Sidebar */}
      {!assistantFocusRoute && <AssistantChatSidebar />}
    </AppShell>
  );
};
