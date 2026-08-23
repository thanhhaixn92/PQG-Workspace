import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useHermesStore } from '../store/store';
import { fetchGlobalMemory, fetchSessionMemory, createMemory, deleteMemory } from '../api/memory';
import type { MemoryKind } from '../api/memory';

const memoryKindLabel: Record<MemoryKind, string> = {
  preference: 'Sở thích',
  project_fact: 'Thông tin dự án',
  workflow_rule: 'Quy tắc quy trình',
  style_rule: 'Quy tắc phong cách',
  temporary_note: 'Ghi chú tạm',
};

export const MemoryPanel: React.FC = () => {
  const memory = useHermesStore(state => state.memory);
  const setMemory = useHermesStore(state => state.setMemory);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');
  const [newKind, setNewKind] = useState<MemoryKind>('project_fact');
  const [viewMode, setViewMode] = useState<'global' | 'session'>('global');
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const requestVersion = useRef(0);

  const filteredMemory = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return memory;
    return memory.filter(item =>
      [item.key, item.value, item.kind, memoryKindLabel[item.kind]]
        .some(value => value.toLowerCase().includes(keyword)),
    );
  }, [memory, search]);

  const loadMemory = useCallback(async () => {
    const version = ++requestVersion.current;
    const sessionId = activeSessionId;
    try {
      setError(null);
      setLoading(true);
      const data = viewMode === 'global'
        ? await fetchGlobalMemory()
        : (sessionId ? await fetchSessionMemory(sessionId) : []);
      if (version === requestVersion.current && (viewMode === 'global' || useHermesStore.getState().activeSessionId === sessionId)) setMemory(data);
    } catch {
      if (version === requestVersion.current) setError('Không tải được bộ nhớ.');
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [activeSessionId, setMemory, viewMode]);

  useEffect(() => {
    requestVersion.current += 1;
    setMemory([]);
    void loadMemory();
  }, [loadMemory, setMemory]);

  const handleCreate = async () => {
    if (!newKey.trim() || !newValue.trim()) return;
    if (viewMode === 'session' && !activeSessionId) return;
    setLoading(true);
    try {
      setError(null);
      await createMemory({
        key: newKey,
        value: newValue,
        kind: newKind,
        session_id: viewMode === 'session' ? activeSessionId ?? undefined : undefined,
      });
      await loadMemory();
      setNewKey('');
      setNewValue('');
    } catch {
      setError('Không tạo được mục bộ nhớ.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string, label: string) => {
    if (deletingId || !window.confirm('Xóa mục bộ nhớ “' + label + '”? Không thể hoàn tác.')) return;
    setDeletingId(id);
    try {
      setError(null);
      await deleteMemory(id);
      await loadMemory();
    } catch {
      setError('Không xóa được mục bộ nhớ.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="memory-panel" style={{ padding: '12px', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <h3 style={{ margin: 0 }}>Bộ nhớ</h3>
        <select value={viewMode} onChange={e => setViewMode(e.target.value as 'global' | 'session')} className="hermes-input" style={{ width: 'auto', padding: '2px 4px' }}>
          <option value="global">Toàn cục</option>
          <option value="session" disabled={!activeSessionId}>Theo Công việc</option>
        </select>
      </div>

      <input
        placeholder="Tìm bộ nhớ..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="hermes-input"
        style={{ marginBottom: '10px' }}
      />
      {error && <div className="form-error">{error}</div>}

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filteredMemory.map(item => (
          <div key={item.id} style={{ border: '1px solid var(--border-subtle)', padding: '8px', marginBottom: '8px', borderRadius: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px' }}>
              <div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  {memoryKindLabel[item.kind]}
                </div>
                <strong>{item.key}</strong>
              </div>
              <button onClick={() => void handleDelete(item.id, item.key)} disabled={deletingId !== null} style={{ color: 'var(--error)' }}>
                {deletingId === item.id ? 'Đang xóa...' : 'Xóa'}
              </button>
            </div>
            <div style={{ fontSize: '12px', marginTop: '4px' }}>{item.value}</div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
              <span>Điểm: {item.importance_score.toFixed(1)}</span>
              <span>{item.last_accessed_at ? `Đã dùng: ${new Date(item.last_accessed_at * 1000).toLocaleDateString('vi-VN')}` : 'Chưa dùng'}</span>
            </div>
          </div>
        ))}
        {memory.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">Chưa có mục bộ nhớ</div>
            <div className="empty-state-text">Lưu sở thích, thông tin dự án hoặc quy tắc làm việc để dùng làm ngữ cảnh.</div>
          </div>
        )}
        {memory.length > 0 && filteredMemory.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-title">Không có kết quả phù hợp</div>
            <div className="empty-state-text">Thử từ khóa khác hoặc tạo mục bộ nhớ mới.</div>
          </div>
        )}
      </div>

      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <select value={newKind} onChange={e => setNewKind(e.target.value as MemoryKind)} className="hermes-input">
          <option value="project_fact">Thông tin dự án</option>
          <option value="preference">Sở thích</option>
          <option value="workflow_rule">Quy tắc quy trình</option>
          <option value="style_rule">Quy tắc phong cách</option>
          <option value="temporary_note">Ghi chú tạm</option>
        </select>
        <input
          placeholder="Khóa"
          value={newKey}
          onChange={e => setNewKey(e.target.value)}
          className="hermes-input"
        />
        <textarea
          placeholder="Giá trị"
          value={newValue}
          onChange={e => setNewValue(e.target.value)}
          className="hermes-input"
          style={{ minHeight: '40px' }}
        />
        <button onClick={() => void handleCreate()} disabled={loading} className="hermes-button">
          Thêm bộ nhớ
        </button>
      </div>
    </div>
  );
};
