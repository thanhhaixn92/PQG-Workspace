import { useHermesStore } from '../store/store';
import type { HermesEvent, TaskRun } from '../store/store';
import { BASE_URL, VITE_USE_TASK_API } from './client';
import { getLatestSessionTaskRun } from './sessions';
import { getTask } from './tasks';

let currentEventSource: EventSource | null = null;
let currentSessionId: string | null = null;
let reconnectAttemptedBySession: Record<string, boolean> = {};
let reconnectTimer: number | null = null;

function toVietnameseRuntimeError(message?: string): string {
  if (!message) {
    return 'Đã xảy ra lỗi.';
  }

  if (message.includes('Timed out waiting for Hermes process to start')) {
    return 'Hermes chưa khởi động được. Hãy kiểm tra HERMES_EXECUTABLE_PATH trong backend/.env hoặc cài Hermes trước khi gửi yêu cầu.';
  }

  if (message.includes('No such file') || message.includes('does-not-exist')) {
    return 'Không tìm thấy chương trình Hermes. Hãy kiểm tra đường dẫn Hermes trong backend/.env.';
  }

  if (message.includes('503') || message.includes('capacity limits') || message.includes('temporarily unavailable')) {
    return 'Model Hermes hoặc Nous đang quá tải hoặc tạm thời chưa sẵn sàng. Hãy thử lại sau hoặc đổi sang model nhanh hơn.';
  }

  return message;
}

function updateLatestTaskStatus(sessionId: string, status: 'running' | 'completed' | 'failed') {
  const store = useHermesStore.getState();
  const task = store.latestTaskBySession[sessionId];
  if (!task) {
    return;
  }

  store.setLatestTask(sessionId, {
    ...task,
    status,
    finished_at: status === 'running' ? task.finished_at : Math.floor(Date.now() / 1000),
  });
}

function ensureSessionTimer(sessionId: string) {
  const store = useHermesStore.getState();
  if (!store.sessionStartedAtById[sessionId]) {
    store.setSessionStartedAt(sessionId, Date.now());
  }
}

function applyLatestTaskStatus(sessionId: string, task: TaskRun | null): boolean {
  const store = useHermesStore.getState();
  store.setLatestTask(sessionId, task);

  if (task?.status === 'completed') {
    store.setSessionStatus(sessionId, 'idle');
    store.setSessionError(sessionId, null);
    store.setSessionStartedAt(sessionId, null);
    return true;
  }

  if (task?.status === 'failed' || task?.status === 'cancelled') {
    store.setSessionStatus(sessionId, 'error');
    store.setSessionStartedAt(sessionId, null);
    store.setSessionError(sessionId, task.error || 'Luồng phản hồi bị mất và task đã kết thúc lỗi.');
    return true;
  }

  if (task?.status === 'running' || task?.status === 'queued' || task?.status === 'waiting_approval') {
    store.setSessionStatus(sessionId, task.status === 'waiting_approval' ? 'waiting_approval' : 'running');
    ensureSessionTimer(sessionId);
    return true;
  }

  return false;
}

async function refreshLatestTaskAfterStreamLoss(sessionId: string) {
  const store = useHermesStore.getState();
  try {
    const task = await getLatestSessionTaskRun(sessionId);
    if (applyLatestTaskStatus(sessionId, task)) {
      if (!task || task.status === 'running' || task.status === 'queued' || task.status === 'waiting_approval') {
        store.setSessionError(
          sessionId,
          'Mất kết nối luồng phản hồi. Task vẫn đang chạy; hãy chờ hoặc kiểm tra Nhật ký hoạt động.',
        );
      }
      return;
    }
  } catch {
    // Keep the user-facing SSE error below; this refresh is best-effort.
  }

  const message = 'Mất kết nối luồng phản hồi. Hãy kiểm tra backend còn chạy, sau đó thử gửi lại nếu task không tiếp tục.';
  store.setSessionStatus(sessionId, 'error');
  store.setSessionError(sessionId, message);
  store.setSessionStartedAt(sessionId, null);
  store.addEvent(sessionId, {
    id: `sse-error-${Date.now()}`,
    type: 'error',
    message,
  });
}

async function handleRuntimeError(sessionId: string, message?: string) {
  const store = useHermesStore.getState();
  const userMessage = toVietnameseRuntimeError(message);
  store.setSessionError(sessionId, userMessage);

  try {
    const task = await getLatestSessionTaskRun(sessionId);
    if (task?.status === 'failed' || task?.status === 'cancelled') {
      applyLatestTaskStatus(sessionId, task);
      store.setSessionError(sessionId, userMessage);
      return;
    }
    if (task?.status === 'running' || task?.status === 'queued' || task?.status === 'waiting_approval') {
      applyLatestTaskStatus(sessionId, task);
      return;
    }
  } catch {
    // Fall back to the explicit backend error event below.
  }

  store.setSessionStatus(sessionId, 'error');
  store.setSessionStartedAt(sessionId, null);
  updateLatestTaskStatus(sessionId, 'failed');
}

export const subscribeToSessionEvents = (sessionId: string) => {
  if (currentSessionId === sessionId && currentEventSource) {
    return;
  }

  unsubscribeFromSessionEvents(false);

  currentSessionId = sessionId;
  currentEventSource = new EventSource(`${BASE_URL}/api/sessions/${sessionId}/events`);

  const handleEvent = (event: MessageEvent) => {
    if (!event.data) {
      return;
    }

    const store = useHermesStore.getState();

    try {
      const data = JSON.parse(event.data);
      const hermesEvent = {
        id: typeof data.id === 'string' ? data.id : `${event.type}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        ...data,
        type: event.type,
      } as HermesEvent;
      if (hermesEvent.type === 'error') {
        hermesEvent.message = toVietnameseRuntimeError(hermesEvent.message);
      }

      store.addEvent(sessionId, hermesEvent);
      reconnectAttemptedBySession[sessionId] = false;

      if (hermesEvent.type === 'token' || hermesEvent.type === 'tool_call' || hermesEvent.type === 'terminal') {
        ensureSessionTimer(sessionId);
        store.setSessionStatus(sessionId, 'running');
        store.setSessionError(sessionId, null);
        updateLatestTaskStatus(sessionId, 'running');
      }

      if (hermesEvent.type === 'approval_required') {
        ensureSessionTimer(sessionId);
        store.setPendingApproval({
          approval_id: hermesEvent.approval_id || '',
          action: hermesEvent.action || 'approval',
          target: hermesEvent.target || '',
          risk_level: hermesEvent.risk_level || 'write_internal',
          description: hermesEvent.description,
        });
        store.setSessionStatus(sessionId, 'waiting_approval');
        updateLatestTaskStatus(sessionId, 'running');
      } else if (hermesEvent.type === 'error') {
        void handleRuntimeError(sessionId, hermesEvent.message);
      } else if (hermesEvent.type === 'done') {
        store.setSessionStatus(sessionId, 'idle');
        store.setSessionError(sessionId, null);
        store.setSessionStartedAt(sessionId, null);
        updateLatestTaskStatus(sessionId, 'completed');
        reconnectAttemptedBySession[sessionId] = false;
        unsubscribeFromSessionEvents();
      }
    } catch (err) {
      console.error('Failed to parse SSE event', err);
    }
  };

  const eventTypes = ['token', 'tool_call', 'terminal', 'file_diff', 'approval_required', 'plan_update', 'error', 'done'];

  eventTypes.forEach(type => {
    currentEventSource!.addEventListener(type, handleEvent);
  });

  currentEventSource.onerror = () => {
    if (!currentEventSource || currentEventSource.readyState === EventSource.CLOSED) {
      return;
    }

    currentEventSource.close();
    currentEventSource = null;

    const store = useHermesStore.getState();
    store.setSessionError(sessionId, 'Mất kết nối luồng phản hồi, đang thử kết nối lại...');

    if (!reconnectAttemptedBySession[sessionId] && currentSessionId === sessionId) {
      reconnectAttemptedBySession[sessionId] = true;
      reconnectTimer = window.setTimeout(() => {
        if (currentSessionId === sessionId) {
          subscribeToSessionEvents(sessionId);
        }
      }, 500);
      return;
    }

    void refreshLatestTaskAfterStreamLoss(sessionId);
  };
};

export const unsubscribeFromSessionEvents = (clearReconnectState = true) => {
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (currentEventSource) {
    currentEventSource.close();
    currentEventSource = null;
  }
  if (clearReconnectState && currentSessionId) {
    reconnectAttemptedBySession[currentSessionId] = false;
  }
  currentSessionId = null;
};

export const subscribeToTaskEvents = (sessionId: string, taskId: string) => {
  if (currentSessionId === taskId && currentEventSource) {
    return;
  }

  unsubscribeFromSessionEvents(false);

  currentSessionId = taskId;
  currentEventSource = new EventSource(`${BASE_URL}/api/tasks/${taskId}/events/stream`);

  const handleEvent = (event: MessageEvent) => {
    if (!event.data) {
      return;
    }

    const store = useHermesStore.getState();

    try {
      const data = JSON.parse(event.data);
      const msgData = data.data_json ? JSON.parse(data.data_json) : {};

      const hermesEvent = {
        id: data.id || `${event.type}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
        type: (event.type === 'status_change' ? 'status' : event.type) as any,
        text: msgData.msg || msgData.error || `Trạng thái: ${data.status}`,
        message: msgData.msg || msgData.error || `Trạng thái: ${data.status}`,
        created_at: data.created_at,
        status: data.status,
        task_id: taskId,
      };

      store.addEvent(sessionId, hermesEvent);

      if (event.type === 'done' || data.status === 'succeeded' || data.status === 'failed' || data.status === 'cancelled') {
        store.setSessionStatus(sessionId, 'idle');
        store.setSessionError(sessionId, data.status === 'failed' ? (msgData.error || 'Task bị lỗi') : null);
        store.setSessionStartedAt(sessionId, null);

        const latestTask = store.latestTaskBySession[sessionId];
        if (latestTask && latestTask.id === taskId) {
          store.setLatestTask(sessionId, {
            ...latestTask,
            status: data.status === 'succeeded' ? 'succeeded' : data.status,
            finished_at: Math.floor(Date.now() / 1000),
            error: data.status === 'failed' ? (msgData.error || 'Task bị lỗi') : null,
          });
        }
        unsubscribeFromSessionEvents();
      } else {
        store.setSessionStatus(sessionId, data.status === 'waiting_approval' ? 'waiting_approval' : 'running');
        const latestTask = store.latestTaskBySession[sessionId];
        if (latestTask && latestTask.id === taskId) {
          store.setLatestTask(sessionId, {
            ...latestTask,
            status: data.status,
          });
        }
      }
    } catch (err) {
      console.error('Failed to parse task event', err);
    }
  };

  const eventTypes = ['status_change', 'done', 'error'];

  eventTypes.forEach(type => {
    currentEventSource!.addEventListener(type, handleEvent);
  });

  currentEventSource.onerror = () => {
    if (!currentEventSource || currentEventSource.readyState === EventSource.CLOSED) {
      return;
    }
    currentEventSource.close();
    currentEventSource = null;

    if (VITE_USE_TASK_API) {
      getTask(taskId)
        .then(actualTask => {
          const store = useHermesStore.getState();
          store.setSessionStatus(sessionId, 'idle');
          store.setSessionStartedAt(sessionId, null);

          const latestTask = store.latestTaskBySession[sessionId];
          if (latestTask && latestTask.id === taskId) {
            store.setLatestTask(sessionId, {
              ...latestTask,
              status: actualTask.status,
              finished_at: ['succeeded', 'failed', 'cancelled'].includes(actualTask.status)
                ? Math.floor(Date.now() / 1000)
                : latestTask.finished_at,
            });
          }
        })
        .catch(err => {
          console.error('Failed to refresh task status on stream end', err);
          const store = useHermesStore.getState();
          store.setSessionStatus(sessionId, 'idle');
          store.setSessionStartedAt(sessionId, null);
        });
    }
  };
};
