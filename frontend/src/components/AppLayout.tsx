import React, { useEffect, useMemo, useState } from 'react';
import { useHermesStore } from '../store/store';
import { getLatestSessionTaskRun, getSessionMessages, getSessions } from '../api/sessions';
import { fetchHealth } from '../api/health';
import { SessionList } from './SessionList';
import { ChatPanel } from './ChatPanel';
import { ActivityInspector } from './ActivityInspector';
import { ApprovalModal } from './ApprovalModal';
import { FileExplorer } from './FileExplorer';
import { EditorPanel } from './EditorPanel';
import { SkillsPanel } from './SkillsPanel';
import { MemoryPanel } from './MemoryPanel';
import { RuntimeStatusPanel } from './RuntimeStatusPanel';
import { LocalDataPanel } from './LocalDataPanel';
import { subscribeToSessionEvents, unsubscribeFromSessionEvents } from '../api/events';

function taskRunToSessionStatus(status?: string) {
  switch (status) {
    case 'queued':
      return 'queued' as const;
    case 'running':
      return 'running' as const;
    case 'waiting_approval':
      return 'waiting_approval' as const;
    case 'failed':
      return 'error' as const;
    default:
      return 'idle' as const;
  }
}

function taskStartedAtMs(status?: string, startedAt?: number | null): number | null {
  if (status !== 'queued' && status !== 'running' && status !== 'waiting_approval') {
    return null;
  }

  return startedAt ? startedAt * 1000 : Date.now();
}

export const AppLayout: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const activeFile = useHermesStore(state => state.activeFile);
  const openFiles = useHermesStore(state => state.openFiles);
  const activeTab = useHermesStore(state => state.sidebarTab);
  const setSessions = useHermesStore(state => state.setSessions);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const setActiveTab = useHermesStore(state => state.setSidebarTab);
  const setEvents = useHermesStore(state => state.setEvents);
  const setLatestTask = useHermesStore(state => state.setLatestTask);
  const setSessionStatus = useHermesStore(state => state.setSessionStatus);
  const setSessionError = useHermesStore(state => state.setSessionError);
  const setSessionStartedAt = useHermesStore(state => state.setSessionStartedAt);
  const appError = useHermesStore(state => state.appError);
  const setAppError = useHermesStore(state => state.setAppError);
  const theme = useHermesStore(state => state.theme);

  useMemo(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const [backendState, setBackendState] = useState<'checking' | 'ready' | 'offline'>('checking');
  const showEditor = Boolean(activeSessionId && activeFile && openFiles.length > 0);

  useEffect(() => {
    fetchHealth()
      .then(() => {
        setBackendState('ready');
        setAppError(null);
      })
      .catch(() => {
        setBackendState('offline');
        setAppError('Không kết nối được backend. Hãy chạy start-dev.ps1 hoặc kiểm tra http://localhost:8000/health.');
      });

    getSessions()
      .then(sessions => {
        setSessions(sessions);
        const savedSessionId = window.localStorage.getItem('hermes.activeSessionId');
        const sessionToSelect = sessions.find(session => session.id === savedSessionId) || sessions[0];
        if (sessionToSelect) {
          setActiveSession(sessionToSelect.id);
        }
        setAppError(null);
      })
      .catch(err => {
        console.error('Failed to load sessions', err);
        setAppError('Không tải được danh sách phiên. Hãy kiểm tra backend đang chạy.');
      });
  }, [setActiveSession, setAppError, setSessions]);

  useEffect(() => {
    if (activeSessionId) {
      window.localStorage.setItem('hermes.activeSessionId', activeSessionId);
    } else {
      window.localStorage.removeItem('hermes.activeSessionId');
    }
  }, [activeSessionId]);

  useEffect(() => {
    if (!activeSessionId) {
      unsubscribeFromSessionEvents();
      return;
    }

    let cancelled = false;
    const sessionId = activeSessionId;

    Promise.all([getSessionMessages(sessionId), getLatestSessionTaskRun(sessionId)])
      .then(([messages, latestTask]) => {
        if (cancelled || useHermesStore.getState().activeSessionId !== sessionId) {
          return;
        }

        setEvents(
          sessionId,
          messages.map(message => ({
            id: message.id,
            type: message.role === 'user' ? 'user_message' : 'token',
            text: message.content,
            created_at: message.created_at,
          })),
        );
        const sessionStatus = taskRunToSessionStatus(latestTask?.status);
        setLatestTask(sessionId, latestTask);
        setSessionStatus(sessionId, sessionStatus);
        setSessionStartedAt(sessionId, taskStartedAtMs(latestTask?.status, latestTask?.started_at));
        setSessionError(sessionId, null);

        if (sessionStatus === 'queued' || sessionStatus === 'running' || sessionStatus === 'waiting_approval') {
          subscribeToSessionEvents(sessionId);
        } else {
          unsubscribeFromSessionEvents();
        }
      })
      .catch(err => {
        if (cancelled || useHermesStore.getState().activeSessionId !== sessionId) {
          return;
        }
        console.error('Failed to load chat history', err);
        setSessionStatus(sessionId, 'error');
        setSessionStartedAt(sessionId, null);
        setSessionError(sessionId, 'Không tải được lịch sử chat của phiên này.');
      });

    return () => {
      cancelled = true;
      unsubscribeFromSessionEvents();
    };
  }, [
    activeSessionId,
    setEvents,
    setLatestTask,
    setSessionError,
    setSessionStartedAt,
    setSessionStatus,
  ]);

  return (
    <div className="app-layout">
      <div className="panel sidebar-panel">
        <div className="sidebar-tabs">
          <button
            className={`sidebar-tab ${activeTab === 'sessions' ? 'active' : ''}`}
            onClick={() => setActiveTab('sessions')}
          >
            Phiên
          </button>
          <button
            className={`sidebar-tab ${activeTab === 'files' ? 'active' : ''}`}
            onClick={() => setActiveTab('files')}
            disabled={!activeSessionId}
          >
            Tệp
          </button>
          <button
            className={`sidebar-tab ${activeTab === 'skills' ? 'active' : ''}`}
            onClick={() => setActiveTab('skills')}
          >
            Kỹ năng
          </button>
          <button
            className={`sidebar-tab ${activeTab === 'memory' ? 'active' : ''}`}
            onClick={() => setActiveTab('memory')}
          >
            Bộ nhớ
          </button>
          <button
            className={`sidebar-tab ${activeTab === 'data' ? 'active' : ''}`}
            onClick={() => setActiveTab('data')}
          >
            Dữ liệu
          </button>
        </div>

        <RuntimeStatusPanel />

        <div className="sidebar-body">
          {activeTab === 'sessions' && <SessionList />}
          {activeTab === 'files' && activeSessionId && <FileExplorer />}
          {activeTab === 'skills' && <SkillsPanel />}
          {activeTab === 'memory' && <MemoryPanel />}
          {activeTab === 'data' && <LocalDataPanel />}
        </div>
      </div>

      <div className="panel chat-panel">
        {(backendState === 'offline' || appError) && (
          <div className="app-status-banner" role="status">
            <div>
              <strong>{backendState === 'offline' ? 'Backend chưa sẵn sàng' : 'Cần chú ý'}</strong>
              <span>{appError}</span>
            </div>
            <button
              className="btn-secondary"
              onClick={() => {
                setAppError(null);
                setBackendState('checking');
                fetchHealth()
                  .then(() => setBackendState('ready'))
                  .catch(() => {
                    setBackendState('offline');
                    setAppError('Backend vẫn chưa phản hồi. Hãy kiểm tra cửa sổ backend hoặc chạy lại start-dev.ps1.');
                  });
              }}
            >
              Kiểm tra lại
            </button>
          </div>
        )}

        {showEditor && (
          <div className="editor-shell">
            <EditorPanel />
          </div>
        )}

        <div className="chat-shell">
          <ChatPanel />
        </div>
      </div>

      <div className="panel activity-inspector-panel">
        <ActivityInspector />
      </div>

      <ApprovalModal />
    </div>
  );
};
