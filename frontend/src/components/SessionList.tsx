import React, { useMemo, useState } from 'react';
import { Archive, Check, MessageSquare, Pencil, PlayCircle, Plus, Search, Trash2, X } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { archiveSession, cleanupSmokeTestSessions, createSession, updateSession } from '../api/sessions';

const DEFAULT_DEMO_WORKSPACE =
  (import.meta.env.VITE_DEMO_WORKSPACE_PATH as string | undefined) ||
  '';

function taskStatusLabel(status?: string): string | null {
  switch (status) {
    case 'queued':
      return 'Đang chờ';
    case 'running':
      return 'Đang chạy';
    case 'waiting_approval':
      return 'Chờ duyệt';
    case 'completed':
      return 'Hoàn tất';
    case 'failed':
      return 'Lỗi';
    case 'cancelled':
      return 'Đã hủy';
    default:
      return null;
  }
}

function resolveWorkspacePath(value: string): { path: string; usedDefault: boolean } {
  const trimmed = value.trim();
  if (trimmed) {
    return { path: trimmed, usedDefault: false };
  }
  return { path: '', usedDefault: true };
}

function isCodeWorkspacePath(path: string): boolean {
  const normalized = path.replace(/\\/g, '/').toLowerCase();
  return (
    normalized.endsWith('/hermes') ||
    normalized.includes('/hermes/backend') ||
    normalized.includes('/hermes/frontend') ||
    normalized.includes('/hermes/infra')
  );
}

export const SessionList: React.FC = () => {
  const sessions = useHermesStore(state => state.sessions);
  const latestTaskBySession = useHermesStore(state => state.latestTaskBySession);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const updateSessionInStore = useHermesStore(state => state.updateSession);

  const [isCreating, setIsCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [workspace, setWorkspace] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const filteredSessions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return sessions;
    }
    return sessions.filter(session =>
      session.title.toLowerCase().includes(normalized) ||
      session.workspace_path.toLowerCase().includes(normalized),
    );
  }, [query, sessions]);

  const smokeSessionCount = sessions.filter(session => session.title.startsWith('Smoke Test')).length;

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) {
      setError('Tên phiên không được để trống.');
      return;
    }

    const resolvedWorkspace = resolveWorkspacePath(workspace);

    try {
      setError(null);
      setNotice(null);
      const newSession = await createSession(nextTitle, resolvedWorkspace.path);
      useHermesStore.setState(state => ({
        sessions: [newSession, ...state.sessions.filter(session => session.id !== newSession.id)],
        activeSessionId: newSession.id,
      }));
      setIsCreating(false);
      setTitle('');
      setWorkspace('');
      setQuery('');
      if (resolvedWorkspace.usedDefault) {
        setNotice(`Đã tự tạo workspace: ${newSession.workspace_path}`);
      }
    } catch (err) {
      console.error('Failed to create session', err);
      setError('Không tạo được phiên. Hãy kiểm tra backend đang chạy và workspace có thể truy cập.');
    }
  };

  const startDemoSession = () => {
    setIsCreating(true);
    setError(null);
    setNotice(null);
    setTitle('Phiên dùng thử Hermes');
    setWorkspace(DEFAULT_DEMO_WORKSPACE);
  };

  const startRename = (sessionId: string, currentTitle: string) => {
    setEditingId(sessionId);
    setEditingTitle(currentTitle);
    setError(null);
    setNotice(null);
  };

  const saveRename = async (sessionId: string) => {
    const nextTitle = editingTitle.trim();
    if (!nextTitle) {
      setError('Tên phiên không được để trống.');
      return;
    }

    try {
      setError(null);
      setNotice(null);
      const updated = await updateSession(sessionId, { title: nextTitle });
      updateSessionInStore(sessionId, updated);
      setEditingId(null);
      setEditingTitle('');
      setNotice('Đã đổi tên phiên.');
    } catch (err) {
      console.error('Failed to rename session', err);
      setError('Không đổi tên được phiên. Hãy thử lại.');
    }
  };

  const handleArchive = async (sessionId: string) => {
    const confirmed = window.confirm('Lưu trữ phiên này? Dữ liệu chat vẫn được giữ trong SQLite.');
    if (!confirmed) {
      return;
    }

    try {
      setError(null);
      setNotice(null);
      await archiveSession(sessionId);
      useHermesStore.setState(state => {
        const remainingSessions = state.sessions.filter(session => session.id !== sessionId);
        const nextActiveSessionId =
          state.activeSessionId === sessionId ? (remainingSessions[0]?.id ?? null) : state.activeSessionId;
        return {
          sessions: remainingSessions,
          activeSessionId: nextActiveSessionId,
        };
      });
      setNotice('Đã lưu trữ phiên.');
    } catch (err) {
      console.error('Failed to archive session', err);
      setError('Không lưu trữ được phiên. Hãy thử lại.');
    }
  };

  const handleCleanupSmokeTests = async () => {
    if (smokeSessionCount === 0) {
      setNotice('Không có phiên Smoke Test cần dọn.');
      return;
    }

    const confirmed = window.confirm(
      `Lưu trữ ${smokeSessionCount} phiên Smoke Test? Dữ liệu sẽ không bị xóa vĩnh viễn.`,
    );
    if (!confirmed) {
      return;
    }

    try {
      setError(null);
      setNotice(null);
      const result = await cleanupSmokeTestSessions();
      useHermesStore.setState(state => {
        const remainingSessions = state.sessions.filter(session => !session.title.startsWith('Smoke Test'));
        const nextActiveSessionId =
          state.activeSessionId && remainingSessions.some(session => session.id === state.activeSessionId)
            ? state.activeSessionId
            : (remainingSessions[0]?.id ?? null);

        return {
          sessions: remainingSessions,
          activeSessionId: nextActiveSessionId,
        };
      });
      setNotice(`Đã lưu trữ ${result.archived_count} phiên test.`);
    } catch (err) {
      console.error('Failed to cleanup smoke tests', err);
      setError('Không dọn được phiên test. Hãy thử lại.');
    }
  };

  return (
    <>
      <div className="panel-header">
        <h3>Phiên</h3>
        <div className="session-header-actions">
          <button className="btn-secondary icon-button" onClick={handleCleanupSmokeTests} title="Dọn phiên test">
            <Trash2 size={15} />
          </button>
          <button
            className="btn-secondary icon-button"
            onClick={() => setIsCreating(current => !current)}
            title="Tạo phiên mới"
          >
            <Plus size={16} />
          </button>
        </div>
      </div>

      <div className="panel-content">
        {sessions.length > 0 && (
          <label className="session-search">
            <Search size={14} />
            <input
              type="search"
              placeholder="Tìm phiên hoặc workspace..."
              value={query}
              onChange={event => setQuery(event.target.value)}
            />
          </label>
        )}

        {sessions.length === 0 && !isCreating && (
          <div className="empty-state">
            <div className="empty-state-title">Bắt đầu với không gian làm việc cục bộ</div>
            <div className="empty-state-text">Tạo phiên, chọn thư mục dự án, rồi gửi yêu cầu đầu tiên.</div>
            <button className="btn-primary" onClick={startDemoSession}>
              <PlayCircle size={14} /> Dùng không gian mẫu
            </button>
          </div>
        )}

        {isCreating && (
          <form onSubmit={handleCreate} className="session-form">
            <input
              type="text"
              placeholder="Tên phiên"
              value={title}
              onChange={event => setTitle(event.target.value)}
              autoFocus
            />
            <input
              type="text"
              placeholder="Bỏ trống để tự tạo thư mục output"
              value={workspace}
              onChange={event => setWorkspace(event.target.value)}
            />
            <div className="form-hint">Bỏ trống để backend tự tạo workspace trong thư mục workspace_outputs.</div>
            <button type="submit" className="btn-primary">
              Tạo
            </button>
          </form>
        )}

        {error && <div className="inline-error session-feedback">{error}</div>}
        {notice && <div className="inline-success session-feedback">{notice}</div>}

        {sessions.length > 0 && filteredSessions.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">Không tìm thấy phiên</div>
            <div className="empty-state-text">Thử tìm bằng tên phiên hoặc đường dẫn workspace khác.</div>
          </div>
        )}

        <div className="session-list">
          {filteredSessions.map(session => {
            const latestTask = latestTaskBySession[session.id];
            const latestTaskLabel = taskStatusLabel(latestTask?.status);

            return (
              <div
                key={session.id}
                className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                onClick={() => setActiveSession(session.id)}
              >
                <MessageSquare
                  size={16}
                  style={{ color: session.id === activeSessionId ? 'var(--accent-primary)' : 'var(--text-secondary)' }}
                />
                <div className="session-main">
                  {editingId === session.id ? (
                    <div className="session-rename" onClick={event => event.stopPropagation()}>
                      <input
                        type="text"
                        aria-label="Tên phiên mới"
                        value={editingTitle}
                        onChange={event => setEditingTitle(event.target.value)}
                      />
                      <button title="Lưu tên phiên" onClick={() => void saveRename(session.id)}>
                        <Check size={14} />
                      </button>
                      <button
                        title="Hủy đổi tên"
                        onClick={() => {
                          setEditingId(null);
                          setEditingTitle('');
                        }}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="session-title-row">
                        <div className="session-title">{session.title}</div>
                        {latestTaskLabel && (
                          <span className={`session-task-badge ${latestTask?.status === 'failed' ? 'failed' : ''}`}>
                            {latestTaskLabel}
                          </span>
                        )}
                      </div>
                      <div className="session-path">{session.workspace_path}</div>
                      {isCodeWorkspacePath(session.workspace_path) && (
                        <div className="runtime-guidance session-workspace-warning">
                          Không nên lưu output vào thư mục code. Hãy tạo phiên mới và bỏ trống workspace để tự tạo thư mục đầu ra.
                        </div>
                      )}
                    </>
                  )}
                </div>
                {editingId !== session.id && (
                  <div className="session-actions" onClick={event => event.stopPropagation()}>
                    <button title="Đổi tên phiên" onClick={() => startRename(session.id, session.title)}>
                      <Pencil size={14} />
                    </button>
                    <button title="Lưu trữ phiên" onClick={() => void handleArchive(session.id)}>
                      <Archive size={14} />
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
};
