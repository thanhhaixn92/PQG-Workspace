import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Archive, CheckCircle, Clock, MoreHorizontal, Pin, PinOff, RefreshCw, Search, Lock } from 'lucide-react';
import { ApiError } from '../../api/client';
import { getWorkAssistantHistory, updateWorkAssistantHistory, type AssistantHistoryItem } from '../../api/assistant';
import { ASSISTANT_NAME } from '../../branding';

export type HistoryStatusFilter = 'all' | 'active' | 'completed' | 'failed' | 'archived';

interface HistoryPanelProps {
  workId: string;
  workArchived: boolean;
  onOpenThread?: (threadId: string, conversationId?: string | null) => void;
}

const statusIcon: Record<AssistantHistoryItem['status'], ReactNode> = {
  active: <Clock size={12} />, completed: <CheckCircle size={12} />, failed: <Clock size={12} />, archived: <Archive size={12} />,
};
const statusLabel: Record<AssistantHistoryItem['status'], string> = {
  active: 'Đang hoạt động', completed: 'Hoàn tất', failed: 'Thất bại', archived: 'Đã lưu trữ',
};
const dateText = (timestamp: number) => new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(timestamp * 1000);

/** Server-backed, Work-scoped history. It has no client-side data fallback. */
export function HistoryPanel({ workId, workArchived, onOpenThread }: HistoryPanelProps) {
  const [items, setItems] = useState<AssistantHistoryItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<HistoryStatusFilter>('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async (append = false, cursor: string | null = null) => {
    const id = ++requestId.current;
    setLoading(true); setError(null);
    try {
      const page = await getWorkAssistantHistory(workId, { cursor, limit: 25, q: query, status: filter, includeArchived: true });
      if (id !== requestId.current) return;
      setItems(current => append ? [...current, ...page.items.filter(item => !current.some(existing => existing.id === item.id))] : page.items);
      setNextCursor(page.next_cursor); setHasMore(page.has_more);
    } catch (cause) {
      if (id !== requestId.current) return;
      const apiError = cause instanceof ApiError ? cause : null;
      setError(apiError?.status === 409 ? 'Công việc đã lưu trữ; lịch sử chỉ đọc.' : 'Không tải được lịch sử GYO. Hãy thử lại.');
    } finally { if (id === requestId.current) setLoading(false); }
  }, [filter, query, workId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [load, query]);

  const updateItem = async (threadId: string, changes: { pinned?: boolean; archived?: boolean }) => {
    if (workArchived) return;
    setLoading(true); setError(null);
    try {
      const changed = await updateWorkAssistantHistory(workId, threadId, changes);
      setItems(current => current.map(item => item.id === changed.id ? changed : item));
    } catch { setError('Không thể cập nhật lịch sử. Hãy làm mới rồi thử lại.'); }
    finally { setLoading(false); }
  };

  return <section className="gyo-history-panel" aria-label={`Lịch sử ${ASSISTANT_NAME} — ${workId}`} data-history-work={workId} data-history-readonly={workArchived}>
    <div className="gyo-history-header">
      <h3>Lịch sử {ASSISTANT_NAME}</h3>
      <div className="gyo-history-controls">
        <label className="gyo-history-search"><Search size={14} aria-hidden="true" /><input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Tìm trong lịch sử…" aria-label="Tìm trong lịch sử" /></label>
        <select className="gyo-history-filter" value={filter} onChange={event => setFilter(event.target.value as HistoryStatusFilter)} aria-label="Lọc trạng thái lịch sử">
          <option value="all">Tất cả trạng thái</option><option value="active">Đang hoạt động</option><option value="completed">Hoàn tất</option><option value="failed">Thất bại</option><option value="archived">Đã lưu trữ</option>
        </select>
      </div>
      {workArchived && <div className="gyo-history-readonly-badge" role="status"><Lock size={12} /> Chỉ đọc</div>}
    </div>
    {error && <div role="alert" className="gyo-history-error">{error}</div>}
    {loading && items.length === 0 && <div className="gyo-history-loading">Đang tải lịch sử…</div>}
    {!loading && !error && items.length === 0 && <div className="gyo-history-empty"><Clock size={24} /><p>Chưa có lịch sử trao đổi nào.</p></div>}
    <ul className="gyo-history-list" role="list">
      {items.map(item => <li key={item.id} className="gyo-history-row" data-history-id={item.id}>
        <button type="button" className="gyo-history-item-main" onClick={() => onOpenThread?.(item.id, item.conversation_id)}>
          <span className={`gyo-history-status gyo-history-status--${item.status}`} aria-hidden="true">{statusIcon[item.status]}</span>
          <span className="gyo-history-info"><strong className="gyo-history-title">{item.title}</strong><span className="gyo-history-meta"><span>{dateText(item.created_at)}</span><span>{item.message_count ?? 0} trao đổi</span><span>{statusLabel[item.status]}</span></span></span>
        </button>
        {!workArchived && <div className="gyo-history-actions">
          <button type="button" className="icon-button" aria-label={item.pinned_at ? 'Bỏ ghim' : 'Ghim'} onClick={() => void updateItem(item.id, { pinned: !item.pinned_at })}>{item.pinned_at ? <PinOff size={15} /> : <Pin size={15} />}</button>
          {item.status === 'archived' ? <button type="button" className="icon-button" aria-label="Khôi phục" onClick={() => void updateItem(item.id, { archived: false })}><RefreshCw size={15} /></button> : <button type="button" className="icon-button" aria-label="Lưu trữ" onClick={() => void updateItem(item.id, { archived: true })}><MoreHorizontal size={15} /></button>}
        </div>}
      </li>)}
    </ul>
    {hasMore && nextCursor && <button type="button" className="gyo-history-load-more btn-secondary" onClick={() => void load(true, nextCursor)} disabled={loading}><RefreshCw size={14} /> {loading ? 'Đang tải…' : 'Tải thêm'}</button>}
  </section>;
}
