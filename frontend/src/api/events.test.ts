import { beforeEach, describe, expect, it, vi } from 'vitest';
import { subscribeToSessionEvents, unsubscribeFromSessionEvents } from './events';
import { useHermesStore } from '../store/store';
import { getLatestSessionTaskRun } from './sessions';

vi.mock('./sessions', () => ({
  getLatestSessionTaskRun: vi.fn().mockResolvedValue(null),
}));

class MockEventSource {
  static instances: MockEventSource[] = [];
  static CLOSED = 2;

  url: string;
  onmessage: ((ev: MessageEvent) => unknown) | null = null;
  onerror: ((ev: Event) => unknown) | null = null;
  listeners: Record<string, Array<(event: MessageEvent) => void>> = {};
  readyState = 1;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(listener);
  }

  removeEventListener(type: string, listener: (event: MessageEvent) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter(item => item !== listener);
    }
  }

  close = vi.fn(() => {
    this.readyState = 2;
  });
}

global.EventSource = MockEventSource as never;

function lastEventSource(): MockEventSource {
  const instance = MockEventSource.instances.at(-1);
  expect(instance).toBeDefined();
  return instance as MockEventSource;
}

async function flushPromises() {
  await new Promise(resolve => window.setTimeout(resolve, 0));
}

describe('events.ts', () => {
  beforeEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
    vi.mocked(getLatestSessionTaskRun).mockResolvedValue(null);
    MockEventSource.instances = [];
    useHermesStore.setState({
      sessions: [],
      activeSessionId: null,
      events: {},
      sessionStatusById: {},
      sessionErrorById: {},
      sessionStartedAtById: {},
      pendingApproval: null,
      latestTaskBySession: {},
    });
    unsubscribeFromSessionEvents();
  });

  it('nhận token event, cập nhật store và bắt đầu timer theo phiên', () => {
    subscribeToSessionEvents('session-1');

    lastEventSource().listeners.token.forEach(listener => listener({
      type: 'token',
      data: JSON.stringify({ text: 'hello' }),
    } as MessageEvent));

    const state = useHermesStore.getState();
    const events = state.events['session-1'];
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('token');
    expect(events[0].text).toBe('hello');
    expect(state.sessionStatusById['session-1']).toBe('running');
    expect(state.sessionStartedAtById['session-1']).toBeGreaterThan(0);
  });

  it('đóng stream khi nhận done, xóa timer và cho phép đăng ký lại', () => {
    useHermesStore.getState().setSessionStartedAt('session-1', Date.now());
    subscribeToSessionEvents('session-1');

    const firstEventSource = lastEventSource();
    firstEventSource.listeners.done.forEach(listener => listener({
      type: 'done',
      data: JSON.stringify({}),
    } as MessageEvent));

    const state = useHermesStore.getState();
    expect(state.sessionStatusById['session-1']).toBe('idle');
    expect(state.sessionErrorById['session-1']).toBeNull();
    expect(state.sessionStartedAtById['session-1']).toBeUndefined();
    expect(firstEventSource.close).toHaveBeenCalled();

    subscribeToSessionEvents('session-1');
    expect(MockEventSource.instances).toHaveLength(2);
  });

  it('dịch lỗi khởi động Hermes, xóa timer và không nâng thành lỗi toàn app', async () => {
    vi.mocked(getLatestSessionTaskRun).mockResolvedValue({
      id: 'task-1',
      session_id: 'session-1',
      status: 'failed',
      started_at: 100,
      finished_at: 120,
      error: 'Timed out waiting for Hermes process to start.',
      retry_count: 0,
    });
    useHermesStore.getState().setSessionStartedAt('session-1', Date.now());
    subscribeToSessionEvents('session-1');

    lastEventSource().listeners.error.forEach(listener => listener({
      type: 'error',
      data: JSON.stringify({ message: 'Timed out waiting for Hermes process to start.' }),
    } as MessageEvent));

    await flushPromises();

    const stateAfterEvent = useHermesStore.getState();
    expect(stateAfterEvent.sessionErrorById['session-1']).toContain('Hermes chưa khởi động được');
    expect(stateAfterEvent.sessionStartedAtById['session-1']).toBeUndefined();
    expect(stateAfterEvent.appError).toBeNull();
  });

  it('server error không đánh dấu failed nếu backend xác nhận task vẫn đang chạy', async () => {
    vi.mocked(getLatestSessionTaskRun).mockResolvedValue({
      id: 'task-1',
      session_id: 'session-1',
      status: 'running',
      started_at: 100,
      retry_count: 0,
    });
    useHermesStore.setState({
      latestTaskBySession: {
        'session-1': {
          id: 'task-1',
          session_id: 'session-1',
          status: 'running',
          started_at: 100,
          retry_count: 0,
        },
      },
    });

    subscribeToSessionEvents('session-1');
    lastEventSource().listeners.error.forEach(listener => listener({
      type: 'error',
      data: JSON.stringify({ message: 'temporary stream issue' }),
    } as MessageEvent));

    await flushPromises();

    const state = useHermesStore.getState();
    expect(state.sessionStatusById['session-1']).toBe('running');
    expect(state.latestTaskBySession['session-1']?.status).toBe('running');
    expect(state.sessionErrorById['session-1']).toBe('temporary stream issue');
  });

  it('lỗi EventSource lần đầu chỉ thử kết nối lại, chưa đánh dấu task failed ngay', () => {
    vi.useFakeTimers();
    useHermesStore.setState({
      latestTaskBySession: {
        'session-1': {
          id: 'task-1',
          session_id: 'session-1',
          status: 'running',
          started_at: 100,
          retry_count: 0,
        },
      },
    });

    subscribeToSessionEvents('session-1');
    const firstEventSource = lastEventSource();
    firstEventSource.onerror?.({} as Event);

    let state = useHermesStore.getState();
    expect(state.sessionErrorById['session-1']).toBe('Mất kết nối luồng phản hồi, đang thử kết nối lại...');
    expect(state.latestTaskBySession['session-1']?.status).toBe('running');
    expect(firstEventSource.close).toHaveBeenCalled();

    vi.advanceTimersByTime(500);
    expect(MockEventSource.instances).toHaveLength(2);

    state = useHermesStore.getState();
    expect(state.latestTaskBySession['session-1']?.status).toBe('running');
    vi.useRealTimers();
  });
});
