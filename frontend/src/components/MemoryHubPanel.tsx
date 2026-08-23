import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  createMemoryHubProposal,
  importLegacyMemory,
  previewLegacyMemory,
  searchMemoryHub,
  transitionMemoryHubRecord,
  type MemoryHubKind,
  type MemoryHubRecord,
} from '../api/memoryHub';
import { ApiError } from '../api/client';

type ScopeMode = 'global' | 'project' | 'task';

const kindLabels: Record<MemoryHubKind, string> = {
  preference: 'Sở thích',
  project_context: 'Bối cảnh dự án',
  task_continuity: 'Tiếp nối tác vụ',
  workflow_rule: 'Quy tắc quy trình',
  technical_decision: 'Quyết định kỹ thuật',
  lesson: 'Bài học',
};

function backendDetail(error: unknown): string | null {
  const message = error instanceof Error ? error.message.trim() : '';
  if (!message || message.length > 180) return null;
  try {
    const detail = JSON.parse(message).detail;
    return typeof detail === 'string' && detail.trim() && detail.length <= 160 ? detail.trim() : null;
  } catch {
    return message.includes('\n') ? null : message;
  }
}

function memoryHubError(error: unknown, fallback: string): string {
  const action = error instanceof ApiError
    ? error.status === 401 ? 'Hãy kiểm tra lại phiên đăng nhập local.'
      : error.status === 403 ? 'Bạn không có quyền thực hiện thao tác này.'
        : error.status === 409 ? 'Bản ghi đã thay đổi hoặc chưa ở trạng thái phù hợp. Hãy tải lại danh sách.'
          : error.status >= 500 ? 'Dịch vụ local đang gặp sự cố. Hãy thử lại sau.'
            : 'Hãy kiểm tra lại dữ liệu đã nhập.'
    : 'Hãy kiểm tra kết nối backend local rồi thử lại.';
  const detail = backendDetail(error);
  return `${fallback} ${action}${detail ? ` (${detail})` : ''}`;
}

export const MemoryHubPanel: React.FC<{ currentWorkId?: string | null }> = ({ currentWorkId = null }) => {
  const [scopeMode, setScopeMode] = useState<ScopeMode>(currentWorkId ? 'project' : 'global');
  const [projectId, setProjectId] = useState(currentWorkId || '');
  const [taskId, setTaskId] = useState('');
  const [query, setQuery] = useState('');
  const [records, setRecords] = useState<MemoryHubRecord[]>([]);
  const [kind, setKind] = useState<MemoryHubKind>('preference');
  const [memoryKey, setMemoryKey] = useState('');
  const [content, setContent] = useState('');
  const [legacyIds, setLegacyIds] = useState('');
  const [legacyPreview, setLegacyPreview] = useState<Array<{ legacy_memory_id: string; memory_key: string; content: string }>>([]);
  const [selectedLegacyIds, setSelectedLegacyIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const queryRef = useRef(query);
  const legacyRequestVersion = useRef(0);
  const previewScopeSnapshot = useRef<string | null>(null);

  useEffect(() => {
    if (!currentWorkId) return;
    setProjectId(currentWorkId);
    setTaskId('');
    setScopeMode('project');
  }, [currentWorkId]);

  const scope = () => scopeMode === 'global'
    ? { include_global_preferences: true }
    : scopeMode === 'project'
      ? { project_id: projectId }
      : { project_id: projectId, task_id: taskId };

  const validScope = scopeMode === 'global' || (scopeMode === 'project' ? Boolean(projectId.trim()) : Boolean(projectId.trim() && taskId.trim()));

  queryRef.current = query;

  const load = useCallback(async () => {
    const version = ++requestVersion.current;
    const scopeSnapshot = scopeMode === 'global'
      ? { include_global_preferences: true }
      : scopeMode === 'project'
        ? { project_id: projectId }
        : { project_id: projectId, task_id: taskId };
    if (!validScope) {
      setRecords([]);
      return;
    }
    setLoading(true);
    try {
      setError(null);
      const result = await searchMemoryHub(scopeSnapshot, queryRef.current.trim() || undefined);
      if (version === requestVersion.current) setRecords(result);
    } catch (error) {
      if (version === requestVersion.current) setError(memoryHubError(error, 'Không thể tải Memory Hub.'));
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [projectId, scopeMode, taskId, validScope]);

  useEffect(() => {
    requestVersion.current += 1;
    legacyRequestVersion.current += 1;
    previewScopeSnapshot.current = null;
    setRecords([]);
    setLegacyPreview([]);
    setSelectedLegacyIds([]);
    void load();
  }, [load]);

  const submitProposal = async () => {
    if (!memoryKey.trim() || !content.trim() || !validScope) return;
    if (scopeMode === 'global' && kind !== 'preference') {
      setError('Phạm vi toàn cục chỉ dùng cho sở thích của người dùng.');
      return;
    }
    setLoading(true);
    try {
      setError(null);
      await createMemoryHubProposal({
        kind,
        memory_key: memoryKey.trim(),
        content: content.trim(),
        ...(scopeMode === 'global' ? {} : { project_id: projectId.trim() }),
        ...(scopeMode === 'task' ? { task_id: taskId.trim() } : {}),
      });
      setMemoryKey('');
      setContent('');
      await load();
    } catch (error) {
      setError(memoryHubError(error, 'Không thể tạo đề xuất.'));
    } finally {
      setLoading(false);
    }
  };

  const transition = async (record: MemoryHubRecord, action: 'verify' | 'activate' | 'reject') => {
    setLoading(true);
    try {
      setError(null);
      await transitionMemoryHubRecord(record.id, action);
      await load();
    } catch (error) {
      setError(memoryHubError(error, 'Không thể thay đổi trạng thái.'));
    } finally {
      setLoading(false);
    }
  };

  const previewLegacy = async () => {
    const ids = legacyIds.split(/[\s,]+/).filter(Boolean);
    if (!ids.length) return;
    const version = ++legacyRequestVersion.current;
    const scopeSnapshot = JSON.stringify(scope());
    setLoading(true);
    try {
      setError(null);
      const preview = await previewLegacyMemory(ids);
      if (version !== legacyRequestVersion.current || scopeSnapshot !== JSON.stringify(scope())) return;
      setLegacyPreview(preview);
      setSelectedLegacyIds([]);
      previewScopeSnapshot.current = scopeSnapshot;
    } catch (error) {
      if (version === legacyRequestVersion.current) setError(memoryHubError(error, 'Không thể xem trước dữ liệu legacy đã chọn.'));
    } finally {
      if (version === legacyRequestVersion.current) setLoading(false);
    }
  };

  const importSelectedLegacy = async () => {
    if (!selectedLegacyIds.length || scopeMode === 'global' || !validScope) return;
    const scopeSnapshot = JSON.stringify(scope());
    if (previewScopeSnapshot.current !== scopeSnapshot) {
      setError('Phạm vi đã thay đổi. Hãy xem trước lại dữ liệu trước khi nhập.');
      return;
    }
    const targetScope = scope();
    setLoading(true);
    try {
      setError(null);
      await importLegacyMemory(selectedLegacyIds, targetScope);
      setLegacyPreview([]);
      setSelectedLegacyIds([]);
      await load();
    } catch (error) {
      setError(memoryHubError(error, 'Không thể nhập các mục đã chọn. Dữ liệu legacy không bị thay đổi.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="memory-panel" style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 10, height: '100%', overflow: 'auto' }}>
      <h3 style={{ margin: 0 }}>Memory Hub</h3>
      <select aria-label="Phạm vi Memory Hub" className="hermes-input" value={scopeMode} onChange={event => setScopeMode(event.target.value as ScopeMode)}>
        <option value="global">Sở thích toàn cục</option>
        <option value="project">Dự án</option>
        <option value="task">Tác vụ</option>
      </select>
      {scopeMode !== 'global' && currentWorkId && <div className="runtime-guidance">Phạm vi: Công việc hiện tại</div>}
      {scopeMode !== 'global' && <input aria-label="Mã dự án" className="hermes-input" placeholder="Mã dự án" value={projectId} readOnly={Boolean(currentWorkId)} onChange={event => setProjectId(event.target.value)} />}
      {scopeMode === 'task' && <input aria-label="Mã tác vụ" className="hermes-input" placeholder="Mã tác vụ" value={taskId} onChange={event => setTaskId(event.target.value)} />}
      {!validScope && <div className="empty-state-text">Chọn phạm vi cụ thể để xem dữ liệu; không có chế độ xem tất cả.</div>}
      <div style={{ display: 'flex', gap: 6 }}>
        <input aria-label="Tìm Memory Hub" className="hermes-input" placeholder="Tìm trong phạm vi" value={query} onChange={event => setQuery(event.target.value)} />
        <button className="btn-secondary" onClick={() => void load()} disabled={loading || !validScope}>Tìm</button>
      </div>
      {error && <div className="form-error">{error}</div>}
      {loading && <div role="status">Đang xử lý…</div>}
      <div>
        {records.map(record => <div key={record.id} data-review-source="memory_hub" data-review-id={record.id} tabIndex={-1} style={{ border: '1px solid var(--border-subtle)', padding: 8, marginBottom: 8, borderRadius: 4 }}>
          <small>{kindLabels[record.kind]} · {record.lifecycle}</small>
          <strong style={{ display: 'block' }}>{record.memory_key}</strong>
          <div>{record.content}</div>
          {record.kind !== 'preference' && record.lifecycle === 'proposed' && <small>Đề xuất này cần Codex review; bạn không thể tự kích hoạt.</small>}
          {record.kind === 'preference' && record.lifecycle === 'proposed' && <button className="btn-secondary" onClick={() => void transition(record, 'verify')} disabled={loading}>Xác minh</button>}
          {record.kind === 'preference' && record.lifecycle === 'verified' && <button className="hermes-button" onClick={() => void transition(record, 'activate')} disabled={loading}>Xác nhận kích hoạt</button>}
          {record.lifecycle === 'proposed' && <button className="btn-secondary" onClick={() => void transition(record, 'reject')} disabled={loading}>Từ chối</button>}
        </div>)}
        {!loading && validScope && records.length === 0 && <div className="empty-state-text">Chưa có Memory Hub phù hợp trong phạm vi này.</div>}
      </div>
      <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, display: 'grid', gap: 8 }}>
        <strong>Tạo đề xuất</strong>
        <select aria-label="Loại Memory Hub" className="hermes-input" value={kind} onChange={event => setKind(event.target.value as MemoryHubKind)}>
          {Object.entries(kindLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <input aria-label="Khóa Memory Hub" className="hermes-input" placeholder="Khóa" value={memoryKey} onChange={event => setMemoryKey(event.target.value)} />
        <textarea aria-label="Nội dung Memory Hub" className="hermes-input" placeholder="Nội dung ngắn gọn" value={content} onChange={event => setContent(event.target.value)} />
        <button className="hermes-button" onClick={() => void submitProposal()} disabled={loading || !validScope}>Tạo đề xuất</button>
      </div>
      {scopeMode !== 'global' && <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, display: 'grid', gap: 8 }}>
        <strong>Nhập từ bộ nhớ legacy</strong>
        <input aria-label="ID legacy" className="hermes-input" placeholder="ID legacy, cách nhau bằng dấu phẩy" value={legacyIds} onChange={event => {
          setLegacyIds(event.target.value);
          legacyRequestVersion.current += 1;
          previewScopeSnapshot.current = null;
          setLegacyPreview([]);
          setSelectedLegacyIds([]);
        }} />
        <button className="btn-secondary" onClick={() => void previewLegacy()} disabled={loading}>Xem trước</button>
        {legacyPreview.map(item => <label key={item.legacy_memory_id}><input type="checkbox" checked={selectedLegacyIds.includes(item.legacy_memory_id)} onChange={() => setSelectedLegacyIds(current => current.includes(item.legacy_memory_id) ? current.filter(id => id !== item.legacy_memory_id) : [...current, item.legacy_memory_id])} /> {item.memory_key}: {item.content}</label>)}
        {legacyPreview.length > 0 && <button className="hermes-button" onClick={() => void importSelectedLegacy()} disabled={loading || !selectedLegacyIds.length}>Xác nhận nhập mục đã chọn</button>}
      </div>}
    </div>
  );
};
