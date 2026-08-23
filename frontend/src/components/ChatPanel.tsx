import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Loader2, RotateCcw, Send } from 'lucide-react';
import { useHermesStore, type TaskRun } from '../store/store';
import { getSessionMessagePage, submitPrompt } from '../api/sessions';
import { apiFetch, VITE_USE_TASK_API } from '../api/client';
import { MarkdownRenderer } from './MarkdownRenderer';
import { subscribeToSessionEvents, subscribeToTaskEvents } from '../api/events';
import { createTask, startTask, cancelTask } from '../api/tasks';

function formatTime(value?: number): string {
  if (!value) return '';
  return new Date(value * 1000).toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function taskStatusLabel(status?: string): string {
  switch (status) {
    case 'queued':
      return 'Đang xếp hàng';
    case 'running':
      return 'Đang chạy';
    case 'waiting_approval':
      return 'Chờ phê duyệt';
    case 'completed':
      return 'Hoàn tất';
    case 'failed':
      return 'Lỗi';
    case 'cancelled':
      return 'Đã hủy';
    default:
      return status || 'Chưa có';
  }
}

function taskStatusHint(status?: string): string {
  switch (status) {
    case 'queued':
      return 'Yêu cầu đã được ghi nhận và đang chờ Trợ lý GYO xử lý.';
    case 'running':
      return 'Trợ lý GYO đang xử lý. Nếu mất hơn 30 giây, Công việc có thể dài hoặc đang chờ bạn duyệt quyền.';
    case 'waiting_approval':
      return 'Trợ lý GYO đang chờ bạn phê duyệt một hành động trong hộp thoại hoặc nhật ký bên phải.';
    case 'completed':
      return 'Yêu cầu gần nhất đã xử lý xong.';
    case 'failed':
      return 'Yêu cầu gần nhất bị lỗi. Bạn có thể gửi lại prompt cuối.';
    default:
      return '';
  }
}

function runtimeStatusText(status: string, elapsedSeconds: number, isSubmitting: boolean): string | null {
  if (isSubmitting) return 'Đang gửi yêu cầu...';
  if (status === 'waiting_approval') {
    return 'Đang chờ phê duyệt. Hãy xử lý hộp phê duyệt để Trợ lý GYO tiếp tục.';
  }
  if (status === 'queued' || status === 'running') {
    if (elapsedSeconds >= 30) {
      return `Trợ lý GYO đang cần thêm thời gian (${elapsedSeconds}s). Công việc có thể dài hoặc đang chờ bạn duyệt quyền.`;
    }
    return `Trợ lý GYO đang xử lý... (${elapsedSeconds}s)`;
  }
  return null;
}

export const ChatPanel: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const events = useHermesStore(state => state.events);
  const latestTaskBySession = useHermesStore(state => state.latestTaskBySession);
  const sessionStatusById = useHermesStore(state => state.sessionStatusById);
  const sessionErrorById = useHermesStore(state => state.sessionErrorById);
  const sessionStartedAtById = useHermesStore(state => state.sessionStartedAtById);
  const setSessionStatus = useHermesStore(state => state.setSessionStatus);
  const setSessionError = useHermesStore(state => state.setSessionError);
  const setSessionStartedAt = useHermesStore(state => state.setSessionStartedAt);
  const addEvent = useHermesStore(state => state.addEvent);
  const removeEvent = useHermesStore(state => state.removeEvent);
  const setLatestTask = useHermesStore(state => state.setLatestTask);
  const setEvents = useHermesStore(state => state.setEvents);

  const [prompt, setPrompt] = useState('');
  const [lastFailedPrompt, setLastFailedPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [curatorMessage, setCuratorMessage] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [hasEarlier, setHasEarlier] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const latestTask = activeSessionId ? latestTaskBySession[activeSessionId] : null;
  const status = activeSessionId ? (sessionStatusById[activeSessionId] ?? 'idle') : 'idle';
  const startedAt = activeSessionId ? sessionStartedAtById[activeSessionId] : undefined;
  const elapsedSeconds = startedAt ? Math.max(0, Math.floor((now - startedAt) / 1000)) : 0;
  const sessionWorkflowError = activeSessionId ? (sessionErrorById[activeSessionId] ?? null) : null;
  const sessionEvents = activeSessionId ? (events[activeSessionId] || []) : [];
  const chatEvents = sessionEvents.filter(evt => evt.type === 'token' || evt.type === 'user_message');
  const lastUserPrompt = useMemo(() => {
    const userMessages = chatEvents.filter(evt => evt.type === 'user_message' && evt.text);
    return userMessages[userMessages.length - 1]?.text || '';
  }, [chatEvents]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [activeSessionId, sessionEvents.length]);

  useEffect(() => {
    setPrompt('');
    setLastFailedPrompt('');
    setPromptError(null);
    setCuratorMessage(null);
    setIsSubmitting(false);
    setLoadingEarlier(false);
    setHasEarlier(true);
  }, [activeSessionId]);

  const loadEarlierMessages = async () => {
    if (!activeSessionId || loadingEarlier || chatEvents.length === 0) return;
    const sessionId = activeSessionId;
    const oldestPersisted = chatEvents.find(event => !event.id.startsWith('local-'));
    if (!oldestPersisted) {
      setHasEarlier(false);
      return;
    }
    setLoadingEarlier(true);
    try {
      const page = await getSessionMessagePage(sessionId, 100, oldestPersisted.id);
      if (useHermesStore.getState().activeSessionId !== sessionId) return;
      const current = useHermesStore.getState().events[sessionId] ?? [];
      const known = new Set(current.map(event => event.id));
      const older = page.messages
        .filter(message => !known.has(message.id))
        .map(message => ({
          id: message.id,
          type: message.role === 'user' ? 'user_message' as const : 'token' as const,
          text: message.content,
          created_at: message.created_at,
        }));
      setEvents(sessionId, [...older, ...current]);
      setHasEarlier(page.has_more);
    } catch {
      if (useHermesStore.getState().activeSessionId === sessionId) setPromptError('Không tải được tin nhắn cũ hơn.');
    } finally {
      if (useHermesStore.getState().activeSessionId === sessionId) setLoadingEarlier(false);
    }
  };

  useEffect(() => {
    const isWaiting = status === 'queued' || status === 'running' || status === 'waiting_approval';
    if (!activeSessionId) return;
    if (!isWaiting) {
      setSessionStartedAt(activeSessionId, null);
      return;
    }
    if (!startedAt) {
      setSessionStartedAt(activeSessionId, Date.now());
    }
    const intervalId = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [activeSessionId, setSessionStartedAt, startedAt, status]);

  const sendCurrentPrompt = async (nextPrompt: string) => {
    if (!nextPrompt.trim() || !activeSessionId || status === 'queued' || status === 'running' || status === 'waiting_approval') {
      return;
    }

    const sessionId = activeSessionId;
    const optimisticEventId = `local-user-${Date.now()}`;
    setIsSubmitting(true);
    try {
      setPromptError(null);
      setCuratorMessage(null);
      setSessionError(sessionId, null);
      setSessionStatus(sessionId, 'queued');
      setSessionStartedAt(sessionId, Date.now());
      addEvent(sessionId, {
        id: optimisticEventId,
        type: 'user_message',
        text: nextPrompt,
        created_at: Math.floor(Date.now() / 1000),
      });

      if (VITE_USE_TASK_API) {
        const createdTask = await createTask({
          session_id: sessionId,
          title: nextPrompt.slice(0, 100),
          description: nextPrompt,
          task_type: 'prompt',
        });
        const task = await startTask(createdTask.id);
        const taskRun: TaskRun = {
          id: task.id,
          session_id: sessionId,
          status: task.status === 'succeeded' ? 'succeeded' : task.status,
          started_at: task.created_at || Math.floor(Date.now() / 1000),
          retry_count: 0,
        };
        setLatestTask(sessionId, taskRun);
        setSessionStatus(sessionId, task.status === 'waiting_approval' ? 'waiting_approval' : 'queued');
        subscribeToTaskEvents(sessionId, task.id);
      } else {
        const task = await submitPrompt(sessionId, nextPrompt);
        setLatestTask(sessionId, task);
        setSessionStatus(sessionId, task.status === 'waiting_approval' ? 'waiting_approval' : 'queued');
        subscribeToSessionEvents(sessionId);
      }
      setPrompt('');
      setLastFailedPrompt('');
    } catch (err) {
      console.error('Failed to submit prompt', err);
      removeEvent(sessionId, optimisticEventId);
      const message = 'Không gửi được yêu cầu. Hãy kiểm tra backend đang chạy và cấu hình model của Trợ lý GYO trong Cài đặt.';
      setPromptError(message);
      setSessionError(sessionId, message);
      setLastFailedPrompt(nextPrompt);
      setPrompt(nextPrompt);
      setSessionStatus(sessionId, 'error');
      setSessionStartedAt(sessionId, null);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    await sendCurrentPrompt(prompt);
  };

  const handleRetry = async () => {
    await sendCurrentPrompt(lastFailedPrompt || prompt || lastUserPrompt);
  };

  const handleCurate = async () => {
    if (!activeSessionId) return;
    try {
      const result = await apiFetch<{ status: string; message?: string }>(`/api/sessions/${activeSessionId}/curate`, { method: 'POST' });
      if (result.status === 'no_proposal') {
        setCuratorMessage(result.message || 'Chưa có thông tin đủ rõ để đề xuất bộ nhớ.');
      } else {
        setCuratorMessage('Đã tạo đề xuất bộ nhớ. Hãy xem hộp phê duyệt.');
      }
    } catch (err) {
      console.error('Failed to request memory proposal', err);
      setCuratorMessage('Không tạo được đề xuất bộ nhớ.');
    }
  };

  const handleCancel = async () => {
    if (!activeSessionId || !latestTask) return;
    try {
      await cancelTask(latestTask.id);
      setLatestTask(activeSessionId, {
        ...latestTask,
        status: 'cancelled',
        finished_at: Math.floor(Date.now() / 1000),
      });
      setSessionStatus(activeSessionId, 'idle');
      setSessionError(activeSessionId, null);
      setSessionStartedAt(activeSessionId, null);
      setCuratorMessage("Đã hủy task trên metadata. Lưu ý: việc hủy chỉ cập nhật metadata, không đảm bảo dừng ngay xử lý đang chạy ở provider.");
    } catch (err) {
      console.error('Failed to cancel task', err);
      setPromptError("Không thể hủy task: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit(event);
      return;
    }
    if (event.key === 'Escape') {
      setPrompt('');
    }
  };

  const isInputDisabled =
    !activeSessionId || isSubmitting || status === 'queued' || status === 'running' || status === 'waiting_approval';
  const latestTaskFailed = latestTask?.status === 'failed';
  const taskFailureMessage = latestTaskFailed
    ? latestTask?.error || 'Lần xử lý gần nhất bị lỗi. Bạn có thể gửi lại yêu cầu cuối.'
    : null;
  const taskHint = taskStatusHint(latestTask?.status);
  const chatError = promptError || sessionWorkflowError || taskFailureMessage;
  const activeRuntimeText = runtimeStatusText(status, elapsedSeconds, isSubmitting);

  return (
    <section className="chat-surface">
      <div className="chat-header">
        <div>
          <h2>Trò chuyện</h2>
          <p>
            {activeSessionId
              ? 'Gửi yêu cầu cho Trợ lý GYO và mở Hoạt động khi bạn cần xem tiến độ.'
              : 'Tạo hoặc chọn một Công việc để bắt đầu.'}
          </p>
        </div>

        <div className="chat-header-actions">
          {activeRuntimeText && (
            <div className={`loading-indicator ${status === 'waiting_approval' || elapsedSeconds >= 30 ? 'warning' : ''}`}>
              {(isSubmitting || status === 'queued' || status === 'running') && <Loader2 size={16} className="spin" />}
              <span>{activeRuntimeText}</span>
            </div>
          )}
          {VITE_USE_TASK_API && activeSessionId && (status === 'queued' || status === 'running' || status === 'waiting_approval') && (
            <button
              type="button"
              className="btn-danger compact-button"
              onClick={handleCancel}
              style={{ display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '4px', padding: '4px 8px', fontSize: '12px', fontWeight: '500' }}
              title="Yêu cầu dừng có thể cần một lúc để Trợ lý GYO hoàn tất bước hiện tại."
            >
              Hủy
            </button>
          )}
          {status === 'idle' && activeSessionId && (
            <button className="btn-secondary compact-button" onClick={handleCurate}>
              Đề xuất bộ nhớ
            </button>
          )}
        </div>
      </div>

      {latestTask && (
        <div className={`task-status-strip ${latestTask.status === 'failed' ? 'failed' : ''}`}>
          <span>Yêu cầu gần nhất: {taskStatusLabel(latestTask.status)}</span>
          {latestTask.finished_at && <span>Hoàn tất lúc {formatTime(latestTask.finished_at)}</span>}
          {taskHint && <span>{taskHint}</span>}
        </div>
      )}

      {VITE_USE_TASK_API && (
        <div className="task-api-warning-banner" style={{ background: '#f59e0b', color: '#000', padding: '8px 12px', fontSize: '13px', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid rgba(0,0,0,0.1)' }}>
          <AlertCircle size={16} />
          <span>Chế độ tương thích đang bật; trạng thái dừng có thể cập nhật chậm hơn phản hồi của Trợ lý GYO.</span>
        </div>
      )}

      {curatorMessage && <div className="runtime-guidance">{curatorMessage}</div>}

      <div className="chat-messages">
        {!activeSessionId ? (
          <div className="empty-state centered-empty-state">
            <div className="empty-state-title">Tạo Công việc để bắt đầu</div>
            <div className="empty-state-text">1. Mở mục Công việc. 2. Tạo hoặc chọn một Công việc. 3. Gửi yêu cầu đầu tiên.</div>
          </div>
        ) : chatEvents.length === 0 ? (
          <div className="empty-state centered-empty-state">
            <div className="empty-state-title">Sẵn sàng trò chuyện</div>
            <div className="empty-state-text">Thử nhập: "Tóm tắt dự án hiện tại trong 5 gạch đầu dòng".</div>
          </div>
        ) : (
          <div className="message-list">
            {hasEarlier && <button type="button" className="btn-secondary compact-button history-load-button" onClick={() => void loadEarlierMessages()} disabled={loadingEarlier}>{loadingEarlier ? 'Đang tải…' : 'Tải tin nhắn trước'}</button>}
            {chatEvents.map((event, index) => {
              const isUser = event.type === 'user_message';
              return (
                <article
                  key={event.id || index}
                  className={`message-bubble ${isUser ? 'message-user' : 'message-agent markdown-body'}`}
                >
                  <div className="message-meta">
                    <span>{isUser ? 'Bạn' : 'Trợ lý GYO'}</span>
                    {event.created_at && <time>{formatTime(event.created_at)}</time>}
                  </div>
                  <MarkdownRenderer content={event.text || ''} />
                </article>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {chatError && (
        <div className="inline-error chat-error">
          <AlertCircle size={16} />
          <span>{chatError}</span>
          <button
            className="btn-secondary compact-button"
            onClick={handleRetry}
            disabled={isSubmitting || !activeSessionId || !(lastFailedPrompt || lastUserPrompt)}
          >
            <RotateCcw size={14} /> Gửi lại
          </button>
        </div>
      )}

      <form className="chat-input-container" onSubmit={handleSubmit}>
        <textarea
          className="chat-input"
          placeholder="Nhập yêu cầu..."
          value={prompt}
          onChange={event => setPrompt(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isInputDisabled}
          rows={2}
        />
        <button
          type="submit"
          className="chat-submit-btn"
          disabled={isInputDisabled || !prompt.trim()}
          title="Gửi tin nhắn"
        >
          <Send size={20} />
        </button>
      </form>
    </section>
  );
};
