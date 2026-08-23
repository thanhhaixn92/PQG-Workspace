import { beforeEach, describe, expect, it } from 'vitest';
import { useHermesStore } from './store';
import type { HermesEvent } from './store';

describe('useHermesStore', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/');
    const store = useHermesStore.getState();
    store.setSessions([]);
    store.setActiveSession(null);
    store.setPendingApproval(null);
    store.setAppError(null);
    useHermesStore.setState({
      events: {},
      sessionStatusById: {},
      sessionErrorById: {},
      sessionStartedAtById: {},
    });
  });

  it('khởi tạo state mặc định đúng', () => {
    const state = useHermesStore.getState();
    expect(state.sessions).toEqual([]);
    expect(state.activeSessionId).toBeNull();
    expect(state.pendingApproval).toBeNull();
    expect(state.appError).toBeNull();
    expect(state.sessionStatusById).toEqual({});
    expect(state.sessionErrorById).toEqual({});
    expect(state.sessionStartedAtById).toEqual({});
  });

  it('đặt phiên đang chọn', () => {
    useHermesStore.getState().setActiveSession('session-1');
    expect(useHermesStore.getState().activeSessionId).toBe('session-1');
  });

  it('điều hướng tab đang mở qua URL', () => {
    useHermesStore.getState().setSidebarTab('sessions');

    expect(useHermesStore.getState().sidebarTab).toBe('sessions');
    expect(window.location.pathname).toBe('/work');
  });

  it('lưu phê duyệt đang chờ', () => {
    const approval = {
      approval_id: 'app-1',
      session_id: 'session-1',
      action: 'read',
      target: 'file.txt',
      risk_level: 'read' as const,
      description: 'Read file',
    };
    useHermesStore.getState().setPendingApproval(approval);
    expect(useHermesStore.getState().pendingApproval).toEqual(approval);
  });

  it('thêm event vào đúng phiên', () => {
    const event: HermesEvent = { id: 'evt-1', type: 'token', text: 'hello' };
    useHermesStore.getState().addEvent('session-1', event);
    expect(useHermesStore.getState().events['session-1']).toHaveLength(1);
    expect(useHermesStore.getState().events['session-1'][0]).toEqual(event);
  });

  it('gộp các token liên tiếp trong cùng phiên', () => {
    const sessionId = 'session-1';

    useHermesStore.getState().addEvent(sessionId, { id: 'evt-1', type: 'token', text: '```mermaid\n' });
    useHermesStore.getState().addEvent(sessionId, { id: 'evt-2', type: 'token', text: 'graph TD;\n' });
    useHermesStore.getState().addEvent(sessionId, { id: 'evt-3', type: 'token', text: '  A-->B;\n```' });

    const events = useHermesStore.getState().events[sessionId];
    expect(events).toHaveLength(1);
    expect(events[0].type).toBe('token');
    expect(events[0].text).toBe('```mermaid\ngraph TD;\n  A-->B;\n```');
  });

  it('không gộp event khác loại', () => {
    const sessionId = 'session-1';

    useHermesStore.getState().addEvent(sessionId, { id: 'evt-1', type: 'status', status: 'running' });
    useHermesStore.getState().addEvent(sessionId, { id: 'evt-2', type: 'token', text: 'hello' });
    useHermesStore.getState().addEvent(sessionId, { id: 'evt-3', type: 'status', status: 'idle' });

    const events = useHermesStore.getState().events[sessionId];
    expect(events).toHaveLength(3);
    expect(events[0].type).toBe('status');
    expect(events[1].type).toBe('token');
    expect(events[1].text).toBe('hello');
    expect(events[2].type).toBe('status');
  });

  it('lưu trạng thái, lỗi và timer theo từng phiên', () => {
    const store = useHermesStore.getState();
    store.setSessionStatus('session-a', 'running');
    store.setSessionStatus('session-b', 'idle');
    store.setSessionError('session-a', 'timeout');
    store.setSessionStartedAt('session-a', 12345);

    const state = useHermesStore.getState();
    expect(state.sessionStatusById['session-a']).toBe('running');
    expect(state.sessionStatusById['session-b']).toBe('idle');
    expect(state.sessionErrorById['session-a']).toBe('timeout');
    expect(state.sessionErrorById['session-b']).toBeUndefined();
    expect(state.sessionStartedAtById['session-a']).toBe(12345);
  });

  it('xóa timer của đúng phiên khi truyền null', () => {
    const store = useHermesStore.getState();
    store.setSessionStartedAt('session-a', 12345);
    store.setSessionStartedAt('session-b', 67890);
    store.setSessionStartedAt('session-a', null);

    const state = useHermesStore.getState();
    expect(state.sessionStartedAtById['session-a']).toBeUndefined();
    expect(state.sessionStartedAtById['session-b']).toBe(67890);
  });

  it('lưu latestTaskBySession và hỗ trợ trạng thái succeeded', () => {
    const store = useHermesStore.getState();
    const task = {
      id: 'task-123',
      session_id: 'session-1',
      status: 'succeeded' as const,
      started_at: 1000,
      retry_count: 0,
    };
    store.setLatestTask('session-1', task);
    expect(useHermesStore.getState().latestTaskBySession['session-1']).toEqual(task);
  });
});
