import React, { useCallback, useEffect, useRef, useState } from 'react';
import { getContextPreview, type ContextPreview } from '../api/contextPreview';
import { useHermesStore } from '../store/store';

const formatBytes = (value: number) => value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KB`;

export const ContextPreviewPanel: React.FC = () => {
  const sessionId = useHermesStore(state => state.activeSessionId);
  const [preview, setPreview] = useState<ContextPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);

  const load = useCallback(async () => {
    if (!sessionId) return;
    const targetSession = sessionId;
    const version = ++requestVersion.current;
    setLoading(true);
    try {
      const result = await getContextPreview(targetSession);
      if (version === requestVersion.current && useHermesStore.getState().activeSessionId === targetSession) {
        setPreview(result);
        setError(null);
      }
    } catch {
      if (version === requestVersion.current) setError('Không tải được bản xem trước ngữ cảnh chat.');
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    requestVersion.current += 1;
    setPreview(null);
    setError(null);
    void load();
  }, [load]);

  if (!sessionId) return <div className="empty-state">Chọn một Công việc để xem ngữ cảnh sẽ được dùng.</div>;
  return <div className="list-panel context-preview-panel">
    <div className="section-header"><div><h3>Ngữ cảnh chat tiếp theo</h3><p>Chỉ đọc: xem mục nào sẽ được dùng hoặc bị loại, không cập nhật lần truy cập.</p></div><button className="btn-secondary compact-button" onClick={() => void load()} disabled={loading}>Làm mới</button></div>
    <div className="panel-content">
      {loading && <div className="loading-indicator">Đang tính ngữ cảnh…</div>}
      {error && <div className="inline-error">{error}</div>}
      {preview && <>
        <div className="context-boundary-note">Memory Hub chưa tự động được đưa vào chat trong giai đoạn này.</div>
        {([['Kỹ năng', preview.skills], ['Bộ nhớ dùng trong chat', preview.memories]] as const).map(([label, group]) => <section className="context-preview-group" key={label}>
          <h4>{label}</h4>
          <p>{formatBytes(group.selected_bytes)} / {formatBytes(group.byte_limit)} · tối đa {group.item_limit} mục</p>
          {group.items.length === 0 && <div className="empty-state-text">Chưa có mục nào.</div>}
          {group.items.map(item => <div className="context-preview-item" key={item.id}>
            <span className={`runtime-pill ${item.selected ? 'ok' : 'warning'}`}>{item.selected ? 'Sẽ dùng' : 'Không dùng'}</span>
            <div><strong>{item.label}</strong><small>{item.reason} · {formatBytes(item.bytes)}</small></div>
          </div>)}
        </section>)}
      </>}
    </div>
  </div>;
};
