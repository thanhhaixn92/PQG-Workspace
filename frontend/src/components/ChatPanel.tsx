import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Loader2, RotateCcw, Send } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { submitPrompt } from '../api/sessions';
import { apiFetch } from '../api/client';
import { MarkdownRenderer } from './MarkdownRenderer';
import { subscribeToSessionEvents } from '../api/events';

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
      return 'Yêu cầu đã được ghi nhận và đang chờ Hermes xử lý.';
    case 'running':
      return 'Hermes hoặc model đang xử lý. Nếu mất hơn 30 giây, thường do provider chậm, phiên dài hoặc đang chờ quyền.';
    case 'waiting_approval':
      return 'Hermes đang chờ bạn phê duyệt một hành động trong hộp thoại hoặc nhật ký bên phải.';
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
    return 'Đang chờ phê duyệt. Hãy xử lý hộp phê duyệt để Hermes tiếp tục.';
  }
  if (status === 'queued' || status === 'running') {
    if (elapsedSeconds >= 30) {
      return `Hermes phản hồi chậm (${elapsedSeconds}s). Thường do model/provider, phiên dài hoặc đang chờ phê duyệt.`;
    }
    return `Hermes đang xử lý... (${elapsedSeconds}s)`;
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
  const setLatestTask = useHermesStore(state => state.setLatestTask);

  const [prompt, setPrompt] = useState('');
  const [lastFailedPrompt, setLastFailedPrompt] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [promptError, setPromptError] = useState<string | null>(null);
  const [curatorMessage, setCuratorMessage] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
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

    setIsSubmitting(true);
    try {
      setPromptError(null);
      setCuratorMessage(null);
      setSessionError(activeSessionId, null);
      setSessionStatus(activeSessionId, 'queued');
      setSessionStartedAt(activeSessionId, Date.now());
      addEvent(activeSessionId, {
        id: `local-user-${Date.now()}`,
        type: 'user_message',
        text: nextPrompt,
        created_at: Math.floor(Date.now() / 1000),
      });

      const task = await submitPrompt(activeSessionId, nextPrompt);
      setLatestTask(activeSessionId, task);
      setSessionStatus(activeSessionId, task.status === 'waiting_approval' ? 'waiting_approval' : 'queued');
      subscribeToSessionEvents(activeSessionId);
      setPrompt('');
      setLastFailedPrompt('');
    } catch (err) {
      console.error('Failed to submit prompt', err);
      const message = 'Không gửi được yêu cầu. Hãy kiểm tra backend đang chạy và Hermes đã được cấu hình trong backend/.env.';
      setPromptError(message);
      setSessionError(activeSessionId, message);
      setLastFailedPrompt(nextPrompt);
      setPrompt(nextPrompt);
      setSessionStatus(activeSessionId, 'error');
      setSessionStartedAt(activeSessionId, null);
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
              ? 'Gửi yêu cầu cho Hermes và theo dõi kết quả tại nhật ký bên phải.'
              : 'Tạo hoặc chọn một phiên để bắt đầu.'}
          </p>
        </div>

        <div className="chat-header-actions">
          {activeRuntimeText && (
            <div className={`loading-indicator ${status === 'waiting_approval' || elapsedSeconds >= 30 ? 'warning' : ''}`}>
              {(isSubmitting || status === 'queued' || status === 'running') && <Loader2 size={16} className="spin" />}
              <span>{activeRuntimeText}</span>
            </div>
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
          <span>Task gần nhất: {taskStatusLabel(latestTask.status)}</span>
          {latestTask.finished_at && <span>Hoàn tất lúc {formatTime(latestTask.finished_at)}</span>}
          {taskHint && <span>{taskHint}</span>}
        </div>
      )}

      {curatorMessage && <div className="runtime-guidance">{curatorMessage}</div>}

      <div className="chat-messages">
        {!activeSessionId ? (
          <div className="empty-state centered-empty-state">
            <div className="empty-state-title">Tạo phiên để bắt đầu</div>
            <div className="empty-state-text">1. Mở tab Phiên. 2. Chọn không gian làm việc. 3. Gửi yêu cầu đầu tiên.</div>
          </div>
        ) : chatEvents.length === 0 ? (
          <div className="empty-state centered-empty-state">
            <div className="empty-state-title">Sẵn sàng trò chuyện</div>
            <div className="empty-state-text">Thử nhập: "Tóm tắt dự án hiện tại trong 5 gạch đầu dòng".</div>
          </div>
        ) : (
          <div className="message-list">
            {chatEvents.map((event, index) => {
              const isUser = event.type === 'user_message';
              return (
                <article
                  key={event.id || index}
                  className={`message-bubble ${isUser ? 'message-user' : 'message-agent markdown-body'}`}
                >
                  <div className="message-meta">
                    <span>{isUser ? 'Bạn' : 'Hermes'}</span>
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
            disabled={isSubmitting || !activeSessionId || !lastUserPrompt}
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
