import React, { useMemo, useState } from 'react';
import { Archive, Check, MessageSquare, Pencil, PlayCircle, Plus, Search, Trash2, X } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { archiveSession, cleanupSmokeTestSessions, createSession, previewSmokeTestCleanup, updateSession } from '../api/sessions';
import { isTestWork } from './workTestVisibility';

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

export const SessionList: React.FC = () => {
  const sessions = useHermesStore(state => state.sessions);
  const latestTaskBySession = useHermesStore(state => state.latestTaskBySession);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const updateSessionInStore = useHermesStore(state => state.updateSession);

  const [isCreating, setIsCreating] = useState(false);
  const [title, setTitle] = useState('');
  const [goal, setGoal] = useState('');
  const [dataScope, setDataScope] = useState<'work_only' | 'approved_library'>('work_only');
  const [workspace, setWorkspace] = useState('');
  const [showAdvancedCreate, setShowAdvancedCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [query, setQuery] = useState('');
  const [showTestWork, setShowTestWork] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const filteredSessions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return sessions.filter(session => {
      if (!showTestWork && isTestWork(session)) return false;
      return !normalized ||
        session.title.toLowerCase().includes(normalized) ||
        (session.goal || '').toLowerCase().includes(normalized);
    });
  }, [query, sessions, showTestWork]);

  const smokeSessionCount = sessions.filter(session => session.title.startsWith('Smoke Test')).length;
  const testWorkCount = sessions.filter(isTestWork).length;

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    const nextTitle = title.trim();
    if (!nextTitle) {
      setError('Tên Công việc không được để trống.');
      return;
    }

    const resolvedWorkspace = resolveWorkspacePath(workspace);

    try {
      setError(null);
      setNotice(null);
      const newSession = await createSession(nextTitle, resolvedWorkspace.path, goal, dataScope);
      useHermesStore.setState(state => ({
        sessions: [newSession, ...state.sessions.filter(session => session.id !== newSession.id)],
        activeSessionId: newSession.id,
      }));
      setIsCreating(false);
      setTitle('');
      setGoal('');
      setDataScope('work_only');
      setWorkspace('');
      setShowAdvancedCreate(false);
      setQuery('');
      if (resolvedWorkspace.usedDefault) {
        setNotice('Đã tự tạo nơi lưu trữ riêng cho Công việc này.');
      }
    } catch (err) {
      console.error('Failed to create session', err);
      setError('Không tạo được Công việc. Hãy kiểm tra ứng dụng đang sẵn sàng rồi thử lại.');
    }
  };

  const startDemoSession = () => {
    setIsCreating(true);
    setError(null);
    setNotice(null);
    setTitle('Công việc dùng thử GYO');
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
      setError('Tên Công việc không được để trống.');
      return;
    }

    try {
      setError(null);
      setNotice(null);
      const updated = await updateSession(sessionId, { title: nextTitle });
      updateSessionInStore(sessionId, updated);
      setEditingId(null);
      setEditingTitle('');
      setNotice('Đã đổi tên Công việc.');
    } catch (err) {
      console.error('Failed to rename session', err);
      setError('Không đổi tên được Công việc. Hãy thử lại.');
    }
  };

  const handleArchive = async (sessionId: string) => {
    const confirmed = window.confirm('Lưu trữ Công việc này? Lịch sử vẫn được giữ và không bị xóa vĩnh viễn.');
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
      setNotice('Đã lưu trữ Công việc.');
    } catch (err) {
      console.error('Failed to archive session', err);
      setError('Không lưu trữ được Công việc. Hãy thử lại.');
    }
  };

  const handleCleanupSmokeTests = async () => {
    if (smokeSessionCount === 0) {
      setNotice('Không có Công việc thử nghiệm cần dọn.');
      return;
    }

    try {
      setError(null);
      setNotice(null);
      const preview = await previewSmokeTestCleanup();
      if (preview.items.length === 0) {
        setNotice('Không có Công việc thử nghiệm cần dọn.');
        return;
      }
      const names = preview.items.slice(0, 5).map(item => `• ${item.title}`).join('\n');
      const remainder = preview.items.length > 5 ? `\n• và ${preview.items.length - 5} Công việc khác` : '';
      const confirmed = window.confirm(
        `Lưu trữ đúng ${preview.items.length} Công việc thử nghiệm sau?\n\n${names}${remainder}\n\nDữ liệu sẽ không bị xóa vĩnh viễn.`,
      );
      if (!confirmed) return;
      const result = await cleanupSmokeTestSessions(preview.confirmation_token);
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
      setNotice(`Đã lưu trữ ${result.archived_count} Công việc thử nghiệm.`);
    } catch (err) {
      console.error('Failed to cleanup smoke tests', err);
      setError('Không dọn được dữ liệu thử nghiệm. Hãy thử lại.');
    }
  };

  return (
    <>
      <div className="panel-header">
        <h3>Công việc</h3>
        <div className="session-header-actions">
          {showTestWork && smokeSessionCount > 0 && <button className="btn-secondary icon-button" onClick={handleCleanupSmokeTests} title="Lưu trữ dữ liệu thử nghiệm">
            <Trash2 size={15} />
          </button>}
          <button
            className="btn-secondary icon-button"
            onClick={() => setIsCreating(current => !current)}
            title="Tạo Công việc mới"
          >
            <Plus size={16} />
          </button>
        </div>
      </div>

      <div className="panel-content">
        {sessions.length > 0 && (
          <>
          <label className="session-search">
            <Search size={14} />
            <input
              type="search"
              placeholder="Tìm Công việc..."
              value={query}
              onChange={event => setQuery(event.target.value)}
            />
          </label>
          {testWorkCount > 0 && (
            <button
              type="button"
              className="btn-secondary compact-button test-data-toggle"
              aria-pressed={showTestWork}
              onClick={() => setShowTestWork(current => !current)}
            >
              {showTestWork ? 'Ẩn dữ liệu kiểm thử' : `Hiện dữ liệu kiểm thử (${testWorkCount})`}
            </button>
          )}
          </>
        )}

        {sessions.length === 0 && !isCreating && (
          <div className="empty-state">
            <div className="empty-state-title">Bắt đầu Công việc đầu tiên</div>
            <div className="empty-state-text">Đặt tên, ghi mục tiêu rồi gửi yêu cầu đầu tiên cho Trợ lý GYO.</div>
            <button className="btn-primary" onClick={startDemoSession}>
              <PlayCircle size={14} /> Dùng Công việc mẫu
            </button>
          </div>
        )}

        {isCreating && (
          <form onSubmit={handleCreate} className="session-form">
            <input
              type="text"
              placeholder="Tên Công việc"
              value={title}
              onChange={event => setTitle(event.target.value)}
              autoFocus
            />
            <textarea
              className="session-goal"
              placeholder="Mục tiêu công việc (không bắt buộc)"
              value={goal}
              onChange={event => setGoal(event.target.value)}
              rows={2}
            />
            <label className="session-data-scope">
              <span>Phạm vi dữ liệu dùng cho Trợ lý GYO</span>
              <select aria-label="Phạm vi dữ liệu dùng cho Trợ lý GYO" value={dataScope} onChange={event => setDataScope(event.target.value as 'work_only' | 'approved_library')}>
                <option value="work_only">Chỉ tài liệu và trao đổi của Công việc này</option>
                <option value="approved_library">Công việc này và tri thức đã duyệt</option>
              </select>
              <small>Bạn có thể thay đổi sau. Memory Hub và nhật ký kỹ thuật không tự được đưa vào chat.</small>
            </label>
            <button
              type="button"
              className="btn-secondary compact-button"
              aria-expanded={showAdvancedCreate}
              onClick={() => setShowAdvancedCreate(current => !current)}
            >
              {showAdvancedCreate ? 'Ẩn tùy chọn nâng cao' : 'Tùy chọn nâng cao'}
            </button>
            {showAdvancedCreate && <>
              <input
                type="text"
                placeholder="Vị trí lưu trữ tùy chọn"
                value={workspace}
                onChange={event => setWorkspace(event.target.value)}
              />
              <div className="form-hint">Chỉ thay đổi khi bạn cần dùng một thư mục có sẵn. Nếu bỏ trống, ứng dụng tự tạo nơi lưu trữ an toàn.</div>
            </>}
            <button type="submit" className="btn-primary">
              Tạo
            </button>
          </form>
        )}

        {error && <div className="inline-error session-feedback">{error}</div>}
        {notice && <div className="inline-success session-feedback">{notice}</div>}

        {sessions.length > 0 && filteredSessions.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">Không tìm thấy Công việc</div>
            <div className="empty-state-text">Thử tìm bằng tên hoặc mục tiêu của Công việc.</div>
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
                role="button"
                tabIndex={0}
                onClick={() => setActiveSession(session.id)}
                onKeyDown={event => {
                  if (event.target !== event.currentTarget) return;
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    setActiveSession(session.id);
                  }
                }}
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
                        aria-label="Tên Công việc mới"
                        value={editingTitle}
                        onChange={event => setEditingTitle(event.target.value)}
                      />
                      <button title="Lưu tên Công việc" onClick={() => void saveRename(session.id)}>
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
                      <div className="session-path">{session.goal || 'Sẵn sàng để tiếp tục'}</div>
                    </>
                  )}
                </div>
                {editingId !== session.id && (
                  <div className="session-actions" onClick={event => event.stopPropagation()}>
                    <button title="Đổi tên Công việc" onClick={() => startRename(session.id, session.title)}>
                      <Pencil size={14} />
                    </button>
                    <button title="Lưu trữ Công việc" onClick={() => void handleArchive(session.id)}>
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
