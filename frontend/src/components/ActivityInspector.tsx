import React, { useEffect, useMemo, useState } from 'react';
import { Activity, ChevronDown, RefreshCw } from 'lucide-react';
import { getSessionAuditEvents, type AuditEvent } from '../api/audit';
import { useHermesStore } from '../store/store';

const MAX_LIVE_EVENTS = 80;
const MAX_AUDIT_EVENTS_PER_GROUP = 80;

const liveEventLabel = (type: string) => {
  switch (type) {
    case 'tool_call':
      return 'Gọi công cụ';
    case 'terminal':
      return 'Terminal';
    case 'error':
      return 'Lỗi';
    case 'approval_required':
      return 'Cần phê duyệt';
    case 'approval_decision':
      return 'Kết quả phê duyệt';
    case 'done':
      return 'Hoàn tất';
    case 'plan_update':
      return 'Cập nhật kế hoạch';
    case 'file_diff':
      return 'Thay đổi tệp';
    default:
      return type;
  }
};

const approvalActionLabel = (action?: string) => {
  switch (action) {
    case 'update_memory':
    case 'mcp.update_memory':
    case 'curator.update_memory':
      return 'Ghi thêm bộ nhớ';
    case 'run_safe_task':
      return 'Chạy lệnh cục bộ';
    case 'call_n8n_webhook':
      return 'Gọi workflow n8n';
    case 'write_workspace_file':
      return 'Ghi hoặc sửa tệp';
    case 'hermes.permission':
      return 'Cấp quyền cho Hermes';
    default:
      return action || 'Không rõ';
  }
};

const auditLabel = (action: string) => {
  switch (action) {
    case 'session.created':
      return 'Tạo phiên';
    case 'session.renamed':
      return 'Đổi tên phiên';
    case 'session.archived':
      return 'Lưu trữ phiên';
    case 'prompt.submitted':
      return 'Nhận yêu cầu';
    case 'task_run.started':
      return 'Bắt đầu xử lý';
    case 'task_run.completed':
      return 'Hoàn tất';
    case 'task_run.failed':
      return 'Lỗi xử lý';
    case 'approval.requested':
      return 'Cần phê duyệt';
    case 'approval.allowed_once':
      return 'Đã cho phép một lần';
    case 'approval.allowed_for_session':
      return 'Đã cho phép trong phiên';
    case 'approval.denied':
      return 'Đã từ chối';
    case 'file.read':
      return 'Đọc tệp';
    case 'file.write':
      return 'Ghi tệp';
    case 'memory.injected':
      return 'Nạp bộ nhớ';
    case 'shell.error':
      return 'Lỗi lệnh cục bộ';
    case 'n8n.webhook.called':
      return 'Gọi workflow n8n';
    case 'content.quality_check':
      return 'Kiểm tra chất lượng nội dung';
    default:
      return action;
  }
};

const formatTime = (value?: number) => {
  if (!value) {
    return '';
  }
  return new Date(value * 1000).toLocaleTimeString('vi-VN');
};

const parsePayload = (payloadJson?: string | null): Record<string, unknown> => {
  if (!payloadJson) {
    return {};
  }

  try {
    const parsed = JSON.parse(payloadJson);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
};

const prettyJson = (value: unknown) => JSON.stringify(value ?? {}, null, 2);

const payloadTaskId = (event: AuditEvent): string | null => {
  const payload = parsePayload(event.payload_json);
  return typeof payload.task_id === 'string' && payload.task_id.trim() ? payload.task_id : null;
};

const taskHeading = (taskId: string) => {
  if (taskId === 'general') {
    return 'Hoạt động chung';
  }
  return `Task ${taskId.slice(0, 8)}`;
};

const taskSummary = (items: AuditEvent[]) => {
  const toolCount = items.filter(event => event.action.includes('tool') || event.action.startsWith('file.') || event.action.startsWith('n8n.')).length;
  const approvalCount = items.filter(event => event.action.startsWith('approval.') || event.action.includes('accepted') || event.action.includes('denied')).length;
  const failed = items.find(event => event.action === 'task_run.failed');
  const completed = items.find(event => event.action === 'task_run.completed');
  const started = items.find(event => event.action === 'task_run.started') || items[items.length - 1];
  const finished = failed || completed || items[0];
  const duration = started?.created_at && finished?.created_at
    ? Math.max(0, finished.created_at - started.created_at)
    : null;

  return {
    status: failed ? 'Lỗi' : completed ? 'Hoàn tất' : 'Đang xử lý',
    duration,
    toolCount,
    approvalCount,
  };
};

const idleLiveText = (sessionStatus: string) => {
  if (sessionStatus === 'queued' || sessionStatus === 'running') {
    return 'Hermes đang chờ token. Nếu chưa có hoạt động mới, thường là model/provider đang phản hồi chậm, phiên dài hoặc đang chờ phê duyệt.';
  }

  if (sessionStatus === 'waiting_approval') {
    return 'Hermes đang chờ bạn phê duyệt để tiếp tục.';
  }

  return 'Chưa có hoạt động live từ backend.';
};

const targetSummary = (event: AuditEvent) => {
  if (event.action === 'content.quality_check') {
    const payload = parsePayload(event.payload_json);
    const label = typeof payload.label === 'string' ? payload.label : 'Đã kiểm tra nội dung';
    const issues = Array.isArray(payload.issues) ? payload.issues.filter(item => typeof item === 'string') : [];
    if (issues.length > 0) {
      return `${label}: ${issues.slice(0, 2).join(' ')}`;
    }
    return label;
  }

  if (!event.target) {
    return null;
  }

  const payload = parsePayload(event.payload_json);
  const action = typeof payload.action === 'string' ? approvalActionLabel(payload.action) : null;

  if (event.action === 'approval.requested' && action) {
    return action;
  }

  return event.target.length > 80 ? `${event.target.slice(0, 80)}...` : event.target;
};

export const ActivityInspector: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const events = useHermesStore(state => state.events);
  const sessionStatusById = useHermesStore(state => state.sessionStatusById);
  const auditRefreshVersion = useHermesStore(state => state.auditRefreshVersion);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'summary' | 'technical'>('summary');

  const sessionStatus = activeSessionId ? (sessionStatusById[activeSessionId] ?? 'idle') : 'idle';
  const sessionEvents = activeSessionId ? events[activeSessionId] || [] : [];
  const inspectorEvents = sessionEvents.filter(event => event.type !== 'token' && event.type !== 'user_message');
  const hiddenLiveEventCount = Math.max(0, inspectorEvents.length - MAX_LIVE_EVENTS);
  const visibleInspectorEvents = inspectorEvents.slice(-MAX_LIVE_EVENTS);

  const auditGroups = useMemo(() => {
    const groups = new Map<string, AuditEvent[]>();
    for (const event of auditEvents) {
      const key = payloadTaskId(event) || 'general';
      groups.set(key, [...(groups.get(key) || []), event]);
    }
    return Array.from(groups.entries()).map(([taskId, items]) => ({ taskId, items }));
  }, [auditEvents]);

  useEffect(() => {
    let cancelled = false;

    if (!activeSessionId) {
      setAuditEvents([]);
      setAuditError(null);
      return;
    }

    setLoadingAudit(true);
    setAuditError(null);
    getSessionAuditEvents(activeSessionId)
      .then(items => {
        if (!cancelled) {
          setAuditEvents(items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAuditEvents([]);
          setAuditError('Không tải được lịch sử hoạt động đã lưu.');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingAudit(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeSessionId, auditRefreshVersion]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 't' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;
        setViewMode(mode => mode === 'summary' ? 'technical' : 'summary');
      }
      if (e.key === 'r' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return;
        if (activeSessionId) {
          setAuditEvents([]);
          setAuditError(null);
          setLoadingAudit(true);
          getSessionAuditEvents(activeSessionId)
            .then(items => setAuditEvents(items))
            .catch(() => setAuditEvents([]))
            .finally(() => setLoadingAudit(false));
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeSessionId, auditRefreshVersion]);

  const showTechnicalHint = viewMode === 'summary' && (auditEvents.length > 0 || inspectorEvents.length > 0);

  return (
    <>
      <div className="panel-header">
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={18} />
          Nhật ký hoạt động
        </h3>
      </div>

      <div className="panel-content">
        {!activeSessionId ? (
          <div style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '2rem' }}>
            Chưa có phiên đang hoạt động
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div className="activity-view-toggle" role="tablist" aria-label="Chế độ xem nhật ký">
              <button
                type="button"
                className={viewMode === 'summary' ? 'active' : ''}
                onClick={() => setViewMode('summary')}
              >
                Tóm tắt
              </button>
              <button
                type="button"
                className={viewMode === 'technical' ? 'active' : ''}
                onClick={() => setViewMode('technical')}
              >
                Kỹ thuật
              </button>
            </div>

            {showTechnicalHint && (
              <div className="runtime-guidance">
                Mở tab Kỹ thuật để xem payload, actor và command đầy đủ.
              </div>
            )}

            <section>
              <h4 style={{ margin: '0 0 0.75rem', color: 'var(--text-secondary)' }}>Đang diễn ra</h4>
              {inspectorEvents.length === 0 ? (
                <div style={{ color: 'var(--text-secondary)' }}>{idleLiveText(sessionStatus)}</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {hiddenLiveEventCount > 0 && (
                    <div className="runtime-guidance">
                      Đang hiển thị {MAX_LIVE_EVENTS} hoạt động mới nhất, đã ẩn {hiddenLiveEventCount} hoạt động cũ để giữ UI mượt.
                    </div>
                  )}
                  {visibleInspectorEvents.map((event, index) => (
                    <div key={event.id || index} className="activity-item">
                      <div className="header">
                        <strong>{liveEventLabel(event.type)}</strong>
                        <span>{new Date().toLocaleTimeString('vi-VN')}</span>
                      </div>
                      <div className="content">
                        {event.type === 'tool_call' && (
                          <>
                            <div>Công cụ: {event.tool_name}</div>
                            {viewMode === 'technical' && (
                              <details className="activity-details" open>
                                <summary><ChevronDown size={13} /> Tham số công cụ</summary>
                                <pre>{prettyJson(event.arguments)}</pre>
                              </details>
                            )}
                          </>
                        )}
                        {event.type === 'terminal' && viewMode === 'summary' && (
                          <div>Đã nhận output terminal.</div>
                        )}
                        {event.type === 'terminal' && viewMode === 'technical' && (
                          <details className="activity-details" open>
                            <summary><ChevronDown size={13} /> Chi tiết terminal</summary>
                            <pre>{event.output}</pre>
                          </details>
                        )}
                        {event.type === 'error' && <div style={{ color: 'var(--danger-primary)' }}>{event.message}</div>}
                        {event.type === 'approval_required' && (
                          <>
                            <div>Hành động: {approvalActionLabel(event.action)}</div>
                            <div>Mức rủi ro: {event.risk_level}</div>
                            {viewMode === 'technical' && (
                              <details className="activity-details" open>
                                <summary><ChevronDown size={13} /> Chi tiết phê duyệt</summary>
                                <div>Mã hành động: {event.action}</div>
                                <div>Mục tiêu: {event.target}</div>
                                {event.description && <div>Mô tả: {event.description}</div>}
                              </details>
                            )}
                          </>
                        )}
                        {event.type === 'approval_decision' && <div>{event.message}</div>}
                        {viewMode === 'technical' && !['tool_call', 'terminal', 'error', 'approval_required', 'approval_decision'].includes(event.type) && (
                          <pre>{prettyJson(event)}</pre>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h4 style={{ margin: '0 0 0.75rem', color: 'var(--text-secondary)' }}>Đã lưu trong phiên</h4>
              {loadingAudit && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                  <RefreshCw size={14} className="spin" />
                  Đang tải lịch sử...
                </div>
              )}
              {auditError && <div style={{ color: 'var(--danger-primary)' }}>{auditError}</div>}
              {!loadingAudit && !auditError && auditEvents.length === 0 && (
                <div style={{ color: 'var(--text-secondary)' }}>Chưa có audit event đã lưu.</div>
              )}
              {!loadingAudit && auditGroups.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {auditGroups.map(group => (
                    <div key={group.taskId} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div className="activity-task-header">
                        <div>{taskHeading(group.taskId)}</div>
                        {group.taskId !== 'general' && (() => {
                          const summary = taskSummary(group.items);
                          return (
                            <div className="activity-task-meta">
                              <span>{summary.status}</span>
                              {summary.duration !== null && <span>{summary.duration}s</span>}
                              <span>{summary.toolCount} công cụ</span>
                              <span>{summary.approvalCount} phê duyệt</span>
                            </div>
                          );
                        })()}
                      </div>
                      {group.items.length > MAX_AUDIT_EVENTS_PER_GROUP && (
                        <div className="runtime-guidance">
                          Đang hiển thị {MAX_AUDIT_EVENTS_PER_GROUP} audit event mới nhất của task này.
                        </div>
                      )}
                      {group.items.slice(-MAX_AUDIT_EVENTS_PER_GROUP).map(event => {
                        const summary = targetSummary(event);
                        return (
                          <div key={event.id} className="activity-item">
                            <div className="header">
                              <strong>{auditLabel(event.action)}</strong>
                              <span>{formatTime(event.created_at)}</span>
                            </div>
                            <div className="content">
                              {summary && <div>{summary}</div>}
                              {viewMode === 'technical' && (
                                <details className="activity-details" open>
                                  <summary><ChevronDown size={13} /> Chi tiết</summary>
                                  <div>Actor: {event.actor}</div>
                                  {event.target && <div>Mục tiêu: {event.target}</div>}
                                  {event.payload_json && <pre>{event.payload_json}</pre>}
                                </details>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </>
  );
};
