import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useHermesStore } from '../store/store';
import { getLatestSessionTaskRun, getSessionMessages, getSessions } from '../api/sessions';
import { fetchHealth } from '../api/health';
import { subscribeToSessionEvents, unsubscribeFromSessionEvents } from '../api/events';
import { fetchPendingApprovals } from '../api/approvals';
import { isGyoAssistantRoute } from '../navigation';
import { ApprovalModal } from './ApprovalModal';
import { AssistantChatSidebar } from './AssistantChatSidebar';
import { WorkContextDrawer } from './WorkContextDrawer';
import { ContextDrawer } from './ui/ContextDrawer';
import { AppShell } from './ui/AppShell';
import { isTestWork } from './workTestVisibility';
import { FoundationHeader } from '../foundation/shell/FoundationHeader';
import { LeftNavigation } from '../foundation/shell/LeftNavigation';
import { ModuleCanvas } from '../foundation/shell/ModuleCanvas';

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
  const assistantFocusRoute = isGyoAssistantRoute(locationKey);
  const currentWorkTitle = sessions.find(session => session.id === activeSessionId)?.title || 'Chưa chọn';

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
    <AppShell
      className={`${activityOpen ? 'activity-open' : ''} ${assistantSidebarMode === 'expanded' ? 'assistant-expanded' : assistantSidebarMode === 'collapsed' ? 'assistant-collapsed' : ''}`}
      style={{ '--assistant-panel-width': `${assistantSidebarWidth}px` } as React.CSSProperties}
    >
      <LeftNavigation
        activeTab={activeTab}
        currentWorkTitle={currentWorkTitle}
        mobileMenuOpen={mobileMenuOpen}
        activityOpen={activityOpen}
        onSelectTab={selectSidebarTab}
        onOpenMobileMenu={() => setMobileMenuOpen(true)}
        onCloseMobileMenu={() => setMobileMenuOpen(false)}
        onOpenActivity={openActivityDrawer}
      />

      <main className="panel workspace-panel">
        <FoundationHeader
          activeTab={activeTab}
          currentWorkTitle={currentWorkTitle}
          theme={theme}
          activityOpen={activityOpen}
          onToggleTheme={toggleTheme}
          onOpenActivity={openActivityDrawer}
        />

        {(backendState === 'offline' || workListError) && (
          <div className="app-status-banner" role="status">
            <div>
              <strong>{backendState === 'offline' ? 'Backend chưa sẵn sàng' : 'Cần chú ý'}</strong>
              <span>{backendState === 'offline' ? healthError : workListError}</span>
            </div>
            <button className="btn-secondary" onClick={() => void bootstrap()}>Kiểm tra lại</button>
          </div>
        )}

        <ModuleCanvas activeTab={activeTab} activeWorkId={activeSessionId} assistantFocusRoute={assistantFocusRoute} />
      </main>

      <ContextDrawer open={activityOpen} title="Lịch sử & ngữ cảnh" onClose={closeActivityDrawer} returnFocusRef={drawerReturnFocusRef}>
        <WorkContextDrawer />
      </ContextDrawer>

      <ApprovalModal />
      {!assistantFocusRoute && <AssistantChatSidebar />}
    </AppShell>
  );
};
