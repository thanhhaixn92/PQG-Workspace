import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useHermesStore } from '../store/store';
import {
  listWorkItems,
  createWorkItem,
  getWorkItemDetail,
  attachSourceFile,
  extractSourceFile,
  listExtractions,
  getExtractionDetail,
  createKnowledgeRecord,
  listKnowledgeRecords,
  getKnowledgeRecordDetail,
  DIRAP_AUTHORITY_OPTIONS,
  submitKnowledgeRecord,
  approveKnowledgeRecord,
  rejectKnowledgeRecord,
  getKnowledgeUsability,
  DIRAP_USABILITY_QUERY_TYPES,
  searchKnowledgeRecords,
} from '../api/dirap';
import type {
  DirapWorkItem,
  DirapWorkItemDetail,
  DirapExtractionDetail,
  DirapKnowledgeRecord,
  DirapKnowledgeStatus,
  DirapKnowledgeAuthorityForApprove,
  DirapUsabilityQueryType,
  DirapUsabilityResult,
  DirapUsabilityState,
  DirapKnowledgeSearchResponse,
} from '../api/dirap';

type PanelView = 'list' | 'create' | 'detail';

// Nhãn vòng đời rà soát bản ghi tri thức (draft → review_pending → active|rejected)
const KR_STATUS_META: Record<DirapKnowledgeStatus, { label: string; bg: string; color: string; border: string }> = {
  draft: { label: 'BẢN NHÁP', bg: 'rgba(245, 158, 11, 0.14)', color: '#f59e0b', border: '#f59e0b33' },
  review_pending: { label: 'CHỜ DUYỆT', bg: 'rgba(59, 130, 246, 0.14)', color: '#3b82f6', border: '#3b82f633' },
  active: { label: 'ĐÃ DUYỆT', bg: 'rgba(34, 197, 94, 0.14)', color: '#22c55e', border: '#22c55e33' },
  rejected: { label: 'TỪ CHỐI', bg: 'rgba(239, 68, 68, 0.14)', color: '#ef4444', border: '#ef444433' },
};

function krStatusBadge(status: DirapKnowledgeStatus) {
  const meta = KR_STATUS_META[status];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.1rem 0.45rem',
        borderRadius: '999px',
        fontSize: '0.68rem',
        fontWeight: 700,
        background: meta.bg,
        color: meta.color,
        border: `1px solid ${meta.border}`,
        whiteSpace: 'nowrap',
      }}
    >
      {meta.label}
    </span>
  );
}

function krDimChip(label: string, value: string) {
  const ok = value !== 'unverified' && value !== 'pending' && value !== 'none';
  const color = ok ? '#22c55e' : 'var(--text-tertiary)';
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.05rem 0.4rem',
        borderRadius: '4px',
        fontSize: '0.66rem',
        border: `1px solid ${ok ? '#22c55e55' : 'var(--border-subtle)'}`,
        color,
        whiteSpace: 'nowrap',
      }}
    >
      {label}: {value}
    </span>
  );
}

// Kết quả chính sách khả dụng — chỉ đọc; usable ≠ "đã duyệt" của vòng đời.
const USABILITY_META: Record<DirapUsabilityState, { label: string; bg: string; color: string; border: string }> = {
  usable: { label: 'DÙNG ĐƯỢC', bg: 'rgba(34, 197, 94, 0.14)', color: '#22c55e', border: '#22c55e33' },
  partial_usable: { label: 'DÙNG MỘT PHẦN', bg: 'rgba(245, 158, 11, 0.14)', color: '#f59e0b', border: '#f59e0b33' },
  unusable: { label: 'KHÔNG DÙNG ĐƯỢC', bg: 'rgba(239, 68, 68, 0.14)', color: '#ef4444', border: '#ef444433' },
};

function usabilityBadge(state: DirapUsabilityState) {
  const meta = USABILITY_META[state];
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '0.1rem 0.45rem',
        borderRadius: '999px',
        fontSize: '0.68rem',
        fontWeight: 700,
        background: meta.bg,
        color: meta.color,
        border: `1px solid ${meta.border}`,
        whiteSpace: 'nowrap',
      }}
    >
      {meta.label}
    </span>
  );
}

// Nhãn tiếng Việt cho sáu mục đích sử dụng chuẩn (policy v1).
const QUERY_TYPE_LABELS: Record<DirapUsabilityQueryType, string> = {
  official_search: 'Tìm kiếm chính thức',
  exploratory_search: 'Tìm kiếm thăm dò',
  analysis_input: 'Đầu vào phân tích',
  legal_review: 'Rà soát pháp lý',
  context_packaging: 'Đóng gói ngữ cảnh',
  memory_query: 'Truy vấn ghi nhớ',
};

const REVIEW_INPUT_STYLE: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  fontSize: '0.72rem',
  padding: '0.2rem 0.4rem',
  borderRadius: '4px',
  border: '1px solid var(--border-subtle)',
  background: 'var(--bg-elevated)',
  color: 'var(--text-primary)',
};

export const DirapPanel: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const sessions = useHermesStore(state => state.sessions);

  const [view, setView] = useState<PanelView>('list');
  const [items, setItems] = useState<DirapWorkItem[]>([]);
  const [detail, setDetail] = useState<DirapWorkItemDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create form
  const [title, setTitle] = useState('');
  const [goal, setGoal] = useState('');
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const detailRequestVersion = useRef(0);
  const listRequestVersion = useRef(0);

  // Attach file form
  const [filePath, setFilePath] = useState('');
  const [fileNote, setFileNote] = useState('');
  const [attachLoading, setAttachLoading] = useState(false);

  // Extraction
  const [extractionsByFile, setExtractionsByFile] = useState<Record<string, DirapExtractionDetail | null>>({});
  const [extractingFileId, setExtractingFileId] = useState<string | null>(null);
  const [expandedExtractionFileId, setExpandedExtractionFileId] = useState<string | null>(null);

  // Knowledge records
  const [knowledgeRecords, setKnowledgeRecords] = useState<DirapKnowledgeRecord[]>([]);
  // Tìm kiếm tri thức có kiểm soát — hoàn toàn chỉ đọc (không lưu kết quả)
  const [searchQ, setSearchQ] = useState('');
  const [searchQueryType, setSearchQueryType] = useState<DirapUsabilityQueryType>('official_search');
  const [searchResp, setSearchResp] = useState<DirapKnowledgeSearchResponse | null>(null);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  // Số thứ tự truy vấn: mọi phản hồi bất đồng bộ cũ (số nhỏ hơn) đều bị bỏ —
  // không bao giờ ghi đè kết quả của cụm từ/mục đích mới.
  const searchSeqRef = useRef(0);
  const [creatingKnowledgeFor, setCreatingKnowledgeFor] = useState<string | null>(null);
  const [expandedKnowledgeId, setExpandedKnowledgeId] = useState<string | null>(null);
  // Chi tiết (có evidence) tải riêng khi mở rộng thẻ
  const [expandedKnowledgeDetail, setExpandedKnowledgeDetail] = useState<Record<string, DirapKnowledgeRecord>>({});
  // Rà soát: bản ghi đang mở form duyệt/từ chối + dữ liệu form
  const [reviewPanelFor, setReviewPanelFor] = useState<string | null>(null);
  const [reviewBusy, setReviewBusy] = useState<string | null>(null);
  const [reviewDraft, setReviewDraft] = useState<Record<string, Record<string, string>>>({});

  // Khả dụng (chỉ đọc — policy v1): mục đích đang chọn + kết quả theo bản ghi
  const [usabilityQueryType, setUsabilityQueryType] = useState<DirapUsabilityQueryType>('official_search');
  const [usabilityByRecord, setUsabilityByRecord] = useState<Record<string, DirapUsabilityResult | null>>({});
  const [usabilityBusyId, setUsabilityBusyId] = useState<string | null>(null);

  // Set defaults when session changes
  useEffect(() => {
    detailRequestVersion.current += 1;
    listRequestVersion.current += 1;
    setSelectedSessionId(activeSessionId || '');
    setDetail(null);
    setKnowledgeRecords([]);
    setExtractionsByFile({});
    setExpandedExtractionFileId(null);
    setReviewPanelFor(null);
    setUsabilityByRecord({});
    setSearchResp(null);
    setSearchError(null);
    setSearchBusy(false);
    setView('list');
  }, [activeSessionId]);

  const loadItems = useCallback(async () => {
    const version = ++listRequestVersion.current;
    const sessionId = activeSessionId;
    try {
      setError(null);
      const data = await listWorkItems({ session_id: sessionId || undefined });
      if (version !== listRequestVersion.current || useHermesStore.getState().activeSessionId !== sessionId) return;
      setItems(data);
    } catch {
      if (version === listRequestVersion.current) setError('Không tải được danh sách quy trình duyệt.');
    }
  }, [activeSessionId]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const handleCreate = async () => {
    if (!title.trim() || !selectedSessionId) return;
    setLoading(true);
    try {
      setError(null);
      await createWorkItem({ session_id: selectedSessionId, title: title.trim(), goal: goal.trim() || null });
      setTitle('');
      setGoal('');
      await loadItems();
      setView('list');
    } catch {
      setError('Không tạo được quy trình duyệt.');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetail = async (taskId: string) => {
    const requestVersion = ++detailRequestVersion.current;
    try {
      setError(null);
      const data = await getWorkItemDetail(taskId);
      if (requestVersion !== detailRequestVersion.current || useHermesStore.getState().activeSessionId !== activeSessionId) return;
      setDetail(data);
      setView('detail');
      void loadKnowledge(taskId, requestVersion);
      void loadPersistedExtractions(data, requestVersion);
    } catch {
      setError('Không tải được chi tiết quy trình duyệt.');
    }
  };

  const loadKnowledge = async (taskId: string, requestVersion = detailRequestVersion.current) => {
    try {
      const records = await listKnowledgeRecords(taskId);
      if (requestVersion !== detailRequestVersion.current) return;
      setKnowledgeRecords(records);
    } catch {
      // Không làm gián đoạn view nếu lỗi tải danh sách bản ghi tri thức
    }
  };

  const loadPersistedExtractions = async (workItem: DirapWorkItemDetail, requestVersion: number) => {
    try {
      const entries = await Promise.all(workItem.work_item.source_files.map(async source => {
        const summaries = await listExtractions(workItem.work_item.task_id, source.id);
        const current = summaries.find(item => item.status === 'fresh') || summaries[0];
        if (!current) return [source.id, null] as const;
        const detail = await getExtractionDetail(workItem.work_item.task_id, source.id, current.id);
        return [source.id, detail] as const;
      }));
      if (requestVersion !== detailRequestVersion.current) return;
      setExtractionsByFile(Object.fromEntries(entries));
    } catch {
      if (requestVersion === detailRequestVersion.current) {
        setError('Không tải được trạng thái extraction đã lưu.');
      }
    }
  };

  const handleCreateKnowledge = async (extractionId: string, recordId: string) => {
    if (!detail) return;
    setCreatingKnowledgeFor(recordId);
    try {
      setError(null);
      // Idempotency-Key theo record id: bấm trùng không tạo bản trùng
      await createKnowledgeRecord(
        detail.work_item.task_id,
        { extraction_id: extractionId, extraction_record_id: recordId },
        `kr-${recordId}`,
      );
      await loadKnowledge(detail.work_item.task_id);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Không tạo được bản ghi tri thức.';
      setError(message);
    } finally {
      setCreatingKnowledgeFor(null);
    }
  };

  // --- Rà soát bản ghi tri thức (draft → review_pending → active|rejected) ---

  const setReviewField = (krId: string, field: string, value: string) => {
    setReviewDraft(prev => ({
      ...prev,
      [krId]: { ...(prev[krId] ?? {}), [field]: value },
    }));
  };

  const handleToggleKnowledgeDetail = (krId: string) => {
    const next = expandedKnowledgeId === krId ? null : krId;
    setExpandedKnowledgeId(next);
    if (next && !expandedKnowledgeDetail[krId] && detail) {
      getKnowledgeRecordDetail(detail.work_item.task_id, krId)
        .then(krDetail => setExpandedKnowledgeDetail(prev => ({ ...prev, [krId]: krDetail })))
        .catch(() => {
          // Không có evidence chi tiết thì thẻ mở rộng vẫn dùng dữ liệu từ danh sách
        });
    }
  };

  const handleSubmitForReview = async (krId: string) => {
    if (!detail) return;
    setReviewBusy(krId);
    try {
      setError(null);
      await submitKnowledgeRecord(
        detail.work_item.task_id,
        krId,
        {},
        `kr-sub-${krId}`,
      );
      setReviewPanelFor(null);
      await loadKnowledge(detail.work_item.task_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không gửi được bản ghi lên rà soát.');
    } finally {
      setReviewBusy(null);
    }
  };

  const handleApproveKnowledge = async (krId: string) => {
    if (!detail || !reviewDraft[krId]) return;
    const f = reviewDraft[krId];
    if (!f.reviewer?.trim() || !f.source?.trim() || !f.authorityStatus?.trim() || !f.authorityRef?.trim()) {
      setError('Duyệt yêu cầu đủ: người rà soát, bằng chứng nguồn, cơ quan ban hành và tham chiếu cơ quan.');
      return;
    }
    const authorityStatus = f.authorityStatus.trim() as DirapKnowledgeAuthorityForApprove;
    if (!DIRAP_AUTHORITY_OPTIONS.includes(authorityStatus)) {
      setError('Cơ quan ban hành phải thuộc tập đóng: regulatory, organizational, expert, derived.');
      return;
    }
    setReviewBusy(krId);
    try {
      setError(null);
      await approveKnowledgeRecord(
        detail.work_item.task_id,
        krId,
        {
          reviewer: f.reviewer.trim(),
          source_evidence_reference: f.source.trim(),
          authority_status: authorityStatus,
          authority_reference: f.authorityRef.trim(),
          calculation_evidence_reference: f.calcRef?.trim() || null,
        },
        `kr-appr-${krId}`,
      );
      setReviewPanelFor(null);
      await loadKnowledge(detail.work_item.task_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không duyệt được bản ghi.');
    } finally {
      setReviewBusy(null);
    }
  };

  const handleRejectKnowledge = async (krId: string) => {
    if (!detail || !reviewDraft[krId]) return;
    const f = reviewDraft[krId];
    if (!f.reviewer?.trim() || !f.reason?.trim()) {
      setError('Từ chối yêu cầu đủ: người rà soát và lý do.');
      return;
    }
    setReviewBusy(krId);
    try {
      setError(null);
      await rejectKnowledgeRecord(
        detail.work_item.task_id,
        krId,
        { reviewer: f.reviewer.trim(), reason: f.reason.trim() },
        `kr-rej-${krId}`,
      );
      setReviewPanelFor(null);
      await loadKnowledge(detail.work_item.task_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không từ chối được bản ghi.');
    } finally {
      setReviewBusy(null);
    }
  };

  const handleCheckUsability = async (krId: string) => {
    if (!detail) return;
    setUsabilityBusyId(krId);
    try {
      setError(null);
      const result = await getKnowledgeUsability(detail.work_item.task_id, krId, usabilityQueryType);
      setUsabilityByRecord(prev => ({ ...prev, [krId]: result }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Không tính được khả dụng cho bản ghi.');
    } finally {
      setUsabilityBusyId(null);
    }
  };

  const handleSearchKnowledge = async (loadMore: boolean) => {
    if (!detail) return;
    const q = searchQ.trim();
    if (!q) {
      setSearchError('Nhập cụm từ cần tìm (không rỗng).');
      return;
    }
    // Chụp nhanh truy vấn này; mọi truy vấn sau (đổi cụm từ/mục đích/tìm lại)
    // sẽ tăng searchSeqRef và làm mất hiệu lực phản hồi của lần này.
    const seq = ++searchSeqRef.current;
    const snapshotQ = q;
    const snapshotType = searchQueryType;
    setSearchBusy(true);
    setSearchError(null);
    try {
      const offset = loadMore && searchResp ? searchResp.offset + searchResp.limit : 0;
      const resp = await searchKnowledgeRecords(detail.work_item.task_id, {
        q,
        queryType: snapshotType,
        limit: 20,
        offset,
      });
      if (seq !== searchSeqRef.current) return; // phản hồi cũ — bỏ, không ghi đè
      if (searchQ.trim() !== snapshotQ || searchQueryType !== snapshotType) {
        return; // truy vấn đã đổi giữa chừng — bỏ phản hồi này
      }
      setSearchResp(prev => {
        // Chỉ ghép khi cả hai thuộc cùng truy vấn (prev đã bị reset khi đổi đầu vào)
        if (loadMore && prev) {
          return { ...resp, results: [...prev.results, ...resp.results] };
        }
        return resp;
      });
    } catch (err: unknown) {
      if (seq === searchSeqRef.current) {
        setSearchError(err instanceof Error ? err.message : 'Không tìm được tri thức.');
      }
    } finally {
      if (seq === searchSeqRef.current) {
        setSearchBusy(false);
      }
    }
  };

  // Đổi cụm từ hoặc mục đích: vô hiệu hóa truy vấn đang bay và xóa ngay kết quả cũ
  // (đảm bảo "Tải thêm" không bao giờ chạy trên kết quả của truy vấn khác).
  const handleSearchInputChange = (value: string) => {
    searchSeqRef.current += 1;
    setSearchQ(value);
    setSearchResp(null);
    setSearchError(null);
    setSearchBusy(false); // giải phóng nút Tìm: truy vấn cũ đã bị vô hiệu nên busy không còn chủ
  };

  const handleSearchTypeChange = (value: DirapUsabilityQueryType) => {
    searchSeqRef.current += 1;
    setSearchQueryType(value);
    setSearchResp(null);
    setSearchError(null);
    setSearchBusy(false); // giải phóng nút Tìm: truy vấn cũ đã bị vô hiệu nên busy không còn chủ
  };

  const handleAttachFile = async () => {
    if (!detail || !filePath.trim()) return;
    setAttachLoading(true);
    try {
      setError(null);
      await attachSourceFile(detail.work_item.task_id, {
        file_path: filePath.trim(),
        note: fileNote.trim() || null,
      });
      setFilePath('');
      setFileNote('');
      // Reload detail
      const data = await getWorkItemDetail(detail.work_item.task_id);
      setDetail(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Không gắn được tệp nguồn.';
      setError(message);
    } finally {
      setAttachLoading(false);
    }
  };

  const handleExtractFile = async (sourceFileId: string) => {
    if (!detail) return;
    setExtractingFileId(sourceFileId);
    try {
      setError(null);
      const data = await extractSourceFile(detail.work_item.task_id, sourceFileId);
      setExtractionsByFile(prev => ({ ...prev, [sourceFileId]: data }));
      setExpandedExtractionFileId(sourceFileId);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Không trích xuất được tệp.';
      setError(message);
    } finally {
      setExtractingFileId(null);
    }
  };

  const handleTogglePreview = async (sourceFileId: string) => {
    if (expandedExtractionFileId === sourceFileId) {
      setExpandedExtractionFileId(null);
      return;
    }
    const existing = extractionsByFile[sourceFileId];
    if (existing) {
      setExpandedExtractionFileId(sourceFileId);
    }
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts * 1000);
    return d.toLocaleString('vi-VN');
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, { bg: string; color: string }> = {
      queued: { bg: 'rgba(245, 158, 11, 0.14)', color: '#f59e0b' },
      running: { bg: 'rgba(59, 130, 246, 0.14)', color: '#3b82f6' },
      waiting_approval: { bg: 'rgba(245, 158, 11, 0.14)', color: '#f59e0b' },
      succeeded: { bg: 'rgba(16, 185, 129, 0.14)', color: '#10b981' },
      failed: { bg: 'rgba(239, 68, 68, 0.14)', color: '#ef4444' },
      cancelled: { bg: 'rgba(100, 116, 139, 0.14)', color: '#64748b' },
    };
    const s = colors[status] || { bg: 'rgba(100, 116, 139, 0.14)', color: '#64748b' };
    const labels: Record<string, string> = {
      queued: 'Đang chờ', running: 'Đang xử lý', waiting_approval: 'Chờ duyệt',
      succeeded: 'Hoàn tất', failed: 'Lỗi', cancelled: 'Đã hủy',
    };
    return (
      <span style={{
        display: 'inline-block',
        padding: '0.1rem 0.45rem',
        borderRadius: '999px',
        fontSize: '0.72rem',
        fontWeight: 700,
        background: s.bg,
        color: s.color,
        border: `1px solid ${s.color}33`,
      }}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="dirap-panel" style={{ padding: '12px', display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div><h3 style={{ margin: 0, fontSize: '0.95rem' }}>Quy trình duyệt tri thức</h3><div className="runtime-guidance">Biến tài liệu nguồn thành tri thức có bằng chứng và trạng thái rõ ràng.</div></div>
        <button
          className="btn-primary compact-button"
          onClick={() => {
            setView(view === 'create' ? 'list' : 'create');
            setError(null);
          }}
        >
          {view === 'create' ? '← Danh sách' : '+ Tạo quy trình'}
        </button>
      </div>

      {error && (
        <div className="form-error" style={{ color: 'var(--danger-primary)', fontSize: '0.82rem', marginBottom: '8px', padding: '6px 8px', background: 'rgba(239,68,68,0.08)', borderRadius: '4px' }}>
          {error}
        </div>
      )}

      {/* Create Form */}
      {view === 'create' && (
        <div style={{ border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px', marginBottom: '12px' }}>
          <h4 style={{ margin: '0 0 10px 0', fontSize: '0.85rem' }}>Bắt đầu quy trình mới</h4>
          <div className="session-form">
            <select
              value={selectedSessionId}
              onChange={e => setSelectedSessionId(e.target.value)}
              className="hermes-input"
              style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-subtle)', padding: '0.5rem 0.75rem', borderRadius: '8px' }}
            >
              <option value="">Chọn Công việc...</option>
              {sessions.filter(s => !s.archived).map(s => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
            <input
              placeholder="Tên nội dung cần duyệt"
              value={title}
              onChange={e => setTitle(e.target.value)}
              className="hermes-input"
            />
            <textarea
              placeholder="Mục tiêu (không bắt buộc)"
              value={goal}
              onChange={e => setGoal(e.target.value)}
              className="hermes-input"
              style={{ minHeight: '50px' }}
            />
            <button onClick={() => void handleCreate()} disabled={loading || !title.trim() || !selectedSessionId} className="btn-primary">
              {loading ? 'Đang tạo...' : 'Bắt đầu quy trình'}
            </button>
          </div>
        </div>
      )}

      {/* Detail View */}
      {view === 'detail' && detail && (
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <button
            className="btn-secondary compact-button"
            onClick={() => { setView('list'); setDetail(null); }}
            style={{ alignSelf: 'flex-start' }}
          >
            ← Quay lại danh sách
          </button>

          <ol className="dirap-steps" aria-label="Tiến độ duyệt tri thức">
            {[
              ['1', 'Mục tiêu', true],
              ['2', 'Nguồn', detail.work_item.source_files.length > 0],
              ['3', 'Trích xuất', Object.values(extractionsByFile).some(item => item?.extraction.status === 'fresh')],
              ['4', 'Tri thức', knowledgeRecords.length > 0],
              ['5', 'Duyệt', knowledgeRecords.some(item => item.status === 'active')],
              ['6', 'Tìm kiếm / báo cáo', knowledgeRecords.some(item => item.status === 'active')],
            ].map(([number, label, complete]) => <li className={complete ? 'complete' : ''} key={String(number)}><span>{number}</span>{label}</li>)}
          </ol>

          {/* Work Item Info */}
          <div style={{ border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h4 style={{ margin: 0, fontSize: '0.9rem' }}>{detail.work_item.title || 'Không tiêu đề'}</h4>
              {statusBadge(detail.work_item.status)}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div><strong>Công việc:</strong> {detail.work_item.session_title || 'Công việc hiện tại'}</div>
              {detail.work_item.goal && <div><strong>Mục tiêu:</strong> {detail.work_item.goal}</div>}
              <div><strong>Tạo lúc:</strong> {formatTime(detail.work_item.created_at)}</div>
              <div><strong>Cập nhật:</strong> {formatTime(detail.work_item.updated_at)}</div>
              <details className="technical-details"><summary>Chi tiết kỹ thuật</summary><div>ID: <code>{detail.work_item.task_id}</code></div>{detail.work_item.workspace_path && <div>Workspace: {detail.work_item.workspace_path}</div>}</details>
            </div>
          </div>

          {/* Source Files */}
          <div style={{ border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem' }}>Tệp nguồn ({detail.work_item.source_files.length})</h4>
            {detail.work_item.source_files.length === 0 && (
              <div className="empty-state" style={{ textAlign: 'center', padding: '12px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Chưa có tệp nguồn nào được gắn.
              </div>
            )}
            {detail.work_item.source_files.map(f => {
              const extraction = extractionsByFile[f.id];
              const isExpanded = expandedExtractionFileId === f.id;
              const extBadge = (status: string) =>
                status === 'fresh'
                  ? { bg: 'rgba(16, 185, 129, 0.14)', color: '#10b981' }
                  : { bg: 'rgba(245, 158, 11, 0.14)', color: '#f59e0b' };
              return (
                <div key={f.id} style={{ border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', marginBottom: '6px', fontSize: '0.8rem' }}>
                  <div style={{ fontWeight: 600 }}>{f.file_name}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>Đường dẫn: {f.file_path}</div>
                  {f.note && <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontStyle: 'italic' }}>{f.note}</div>}
                  <div style={{ color: 'var(--text-tertiary)', fontSize: '0.72rem' }}>Đã gắn: {formatTime(f.attached_at)}</div>

                  {/* Extraction controls */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
                    <button
                      onClick={() => void handleExtractFile(f.id)}
                      disabled={extractingFileId === f.id}
                      className="btn-primary compact-button"
                      style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem' }}
                    >
                      {extractingFileId === f.id ? 'Đang trích xuất...' : 'Trích xuất'}
                    </button>
                    {extraction && (
                      <>
                        <span style={{
                          display: 'inline-block',
                          padding: '0.1rem 0.45rem',
                          borderRadius: '999px',
                          fontSize: '0.68rem',
                          fontWeight: 700,
                          background: extBadge(extraction.extraction.status).bg,
                          color: extBadge(extraction.extraction.status).color,
                          border: `1px solid ${extBadge(extraction.extraction.status).color}33`,
                        }}>
                          {extraction.extraction.status === 'fresh' ? 'MỚI NHẤT' : 'NGUỒN ĐÃ THAY ĐỔI'}
                        </span>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.72rem' }}>
                          {extraction.total_records} bản ghi · {extraction.extraction.file_type}
                        </span>
                        <button
                          onClick={() => void handleTogglePreview(f.id)}
                          className="btn-secondary compact-button"
                          style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', marginLeft: 'auto' }}
                        >
                          {isExpanded ? 'Ẩn' : 'Xem trước'}
                        </button>
                      </>
                    )}
                  </div>

                  {extraction && (
                    <div style={{ marginTop: '6px', color: 'var(--text-tertiary)', fontSize: '0.7rem', wordBreak: 'break-all' }}>
                      Hash: <code style={{ fontSize: '0.66rem' }}>{extraction.extraction.source_sha256.slice(0, 16)}…</code>
                      {' '}· v{extraction.extraction.extractor_version} · {formatTime(extraction.extraction.extracted_at)}
                    </div>
                  )}

                  {extraction && isExpanded && (
                    <div style={{ marginTop: '8px', border: '1px solid var(--border-subtle)', borderRadius: '6px', maxHeight: '220px', overflowY: 'auto', background: 'var(--bg-primary)' }}>
                      {extraction.records.length === 0 && (
                        <div style={{ padding: '10px', color: 'var(--text-tertiary)', fontSize: '0.75rem', textAlign: 'center' }}>
                          Không có bản ghi nào được trích xuất.
                        </div>
                      )}
                      {extraction.records.slice(0, 30).map(rec => (
                        <div key={rec.id || rec.seq} style={{ padding: '6px 8px', borderBottom: '1px solid var(--border-subtle)', fontSize: '0.72rem', display: 'flex', gap: '8px', alignItems: 'center' }}>
                          <span style={{ color: 'var(--text-tertiary)', whiteSpace: 'nowrap', fontFamily: 'monospace' }}>#{rec.seq}</span>
                          <span style={{ color: 'var(--text-secondary)', whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: '0.66rem' }}>{rec.provenance}</span>
                          <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{rec.content}</span>
                          <button
                            onClick={() => void handleCreateKnowledge(extraction.extraction.id, rec.id)}
                            disabled={creatingKnowledgeFor === rec.id || extraction.extraction.status !== 'fresh'}
                            title={
                              extraction.extraction.status === 'fresh'
                                ? 'Tạo bản ghi tri thức (draft) từ bản ghi này'
                                : 'Nguồn đã thay đổi; hãy trích xuất lại trước khi tạo tri thức'
                            }
                            className="btn-primary compact-button"
                            style={{ fontSize: '0.62rem', padding: '0.1rem 0.45rem', whiteSpace: 'nowrap', flexShrink: 0 }}
                          >
                            {creatingKnowledgeFor === rec.id ? '…' : '→ Tri thức'}
                          </button>
                        </div>
                      ))}
                      {extraction.total_records > extraction.records.length && (
                        <div style={{ padding: '6px 8px', color: 'var(--text-tertiary)', fontSize: '0.7rem' }}>
                          … và {extraction.total_records - extraction.records.length} bản ghi nữa
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}

            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <h5 style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Gắn tệp nguồn mới</h5>
              <input
                placeholder="Đường dẫn tương đối (vd: inputs/doc.docx)"
                value={filePath}
                onChange={e => setFilePath(e.target.value)}
                className="hermes-input"
              />
              <input
                placeholder="Ghi chú (không bắt buộc)"
                value={fileNote}
                onChange={e => setFileNote(e.target.value)}
                className="hermes-input"
              />
              <button
                onClick={() => void handleAttachFile()}
                disabled={attachLoading || !filePath.trim()}
                className="btn-primary compact-button"
              >
                {attachLoading ? 'Đang gắn...' : 'Gắn tệp'}
              </button>
            </div>
          </div>

          {/* Tìm kiếm tri thức có kiểm soát — chỉ đọc, lọc theo chính sách v1 */}
          <div style={{ border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px', marginBottom: '10px' }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem' }}>Tìm kiếm tri thức (chỉ đọc)</h4>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
              <input
                value={searchQ}
                onChange={e => handleSearchInputChange(e.target.value)}
                onKeyDown={e => {
                  // Keep keyboard submission aligned with the disabled search button.
                  if (e.key === 'Enter' && !searchBusy) void handleSearchKnowledge(false);
                }}
                placeholder="Cụm từ (tìm trong nội dung và nguồn)"
                style={{ flex: '1 1 170px', minWidth: '140px', fontSize: '0.78rem', padding: '4px 6px' }}
              />
              <select
                value={searchQueryType}
                onChange={e => handleSearchTypeChange(e.target.value as DirapUsabilityQueryType)}
                style={{ fontSize: '0.75rem', padding: '4px 6px' }}
              >
                {DIRAP_USABILITY_QUERY_TYPES.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <button onClick={() => void handleSearchKnowledge(false)} disabled={searchBusy}>
                {searchBusy ? 'Đang tìm...' : 'Tìm'}
              </button>
            </div>
            {searchError && (
              <div style={{ color: '#ef4444', fontSize: '0.75rem', marginBottom: '6px' }}>{searchError}</div>
            )}
            {searchResp && (
              <>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  {searchResp.total} kết quả đủ điều kiện cho “{searchResp.query_type}” (đã lọc theo chính sách v1;
                  {searchResp.query_type === 'exploratory_search'
                    ? ' có thể gồm kết quả partial_usable — xem nhãn mức khả dụng.'
                    : ' chỉ gồm kết quả usable.'}{' '}
                  Bản ghi “active” không tự nghĩa là dùng được cho mọi mục đích.)
                </div>
                {searchResp.results.length === 0 && (
                  <div className="empty-state" style={{ textAlign: 'center', padding: '10px', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                    Không có kết quả khớp và đủ điều kiện chính sách.
                  </div>
                )}
                {searchResp.results.map(r => {
                  const meta = KR_STATUS_META[r.lifecycle_state];
                  const uColor = r.usability_state === 'usable' ? '#22c55e' : r.usability_state === 'partial_usable' ? '#f59e0b' : '#ef4444';
                  const fieldLabel = r.matched_field === 'both' ? 'nội dung + nguồn' : r.matched_field === 'content' ? 'nội dung' : 'nguồn';
                  return (
                    <div key={r.record_id} style={{ border: '1px solid var(--border-subtle)', padding: '6px 8px', borderRadius: '6px', marginBottom: '4px', fontSize: '0.75rem' }}>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '2px' }}>
                        <span style={{ background: `${uColor}22`, color: uColor, border: `1px solid ${uColor}44`, padding: '0 4px', borderRadius: '4px', fontWeight: 600 }}>
                          {r.usability_state}
                        </span>
                        <span style={{ background: meta.bg, color: meta.color, border: `1px solid ${meta.border}`, padding: '0 4px', borderRadius: '4px' }}>
                          {meta.label}
                        </span>
                        <span style={{ color: 'var(--text-secondary)' }}>Khớp: {fieldLabel}</span>
                      </div>
                      <div>{r.content_excerpt}</div>
                      {r.provenance && <div style={{ color: 'var(--text-secondary)' }}>Nguồn: {r.provenance}</div>}
                      <div style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                        4 chiều: sv={r.source_verification_state} · cv={r.calculation_verification_state} · oa={r.owner_acceptance_state} · au={r.authority_status}
                      </div>
                    </div>
                  );
                })}
                {searchResp.offset + searchResp.results.length < searchResp.total && (
                  <button onClick={() => void handleSearchKnowledge(true)} disabled={searchBusy} style={{ marginTop: '4px', fontSize: '0.75rem' }}>
                    Tải thêm ({searchResp.total - (searchResp.offset + searchResp.results.length)} còn lại)
                  </button>
                )}
              </>
            )}
          </div>

          {/* Knowledge Records */}
          <div style={{ border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem' }}>Bản ghi tri thức ({knowledgeRecords.length})</h4>
            {knowledgeRecords.length === 0 && (
              <div className="empty-state" style={{ textAlign: 'center', padding: '12px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Chưa có bản ghi tri thức. Trích xuất tệp nguồn rồi bấm "→ Tri thức" trên một bản ghi.
              </div>
            )}
            {knowledgeRecords.map(kr => {
              const isExpanded = expandedKnowledgeId === kr.id;
              const krDetail = expandedKnowledgeDetail[kr.id] ?? kr;
              const krEvidence = krDetail.evidence ?? [];
              const f = reviewDraft[kr.id] ?? {};
              return (
                <div key={kr.id} data-review-source="knowledge" data-review-id={kr.id} tabIndex={-1} style={{ border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', marginBottom: '6px', fontSize: '0.8rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 600, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {kr.content}
                    </span>
                    {krStatusBadge(kr.status)}
                    <button
                      onClick={() => handleToggleKnowledgeDetail(kr.id)}
                      className="btn-secondary compact-button"
                      style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem', whiteSpace: 'nowrap' }}
                    >
                      {isExpanded ? 'Ẩn' : 'Chi tiết'}
                    </button>
                  </div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem', marginTop: '2px' }}>
                    {kr.provenance} · v{kr.extractor_version} · {formatTime(kr.created_at)}
                  </div>
                  {/* 4 chiều xác minh độc lập */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '4px' }}>
                    {krDimChip('Nguồn', kr.source_verification_state)}
                    {krDimChip('Tính toán', kr.calculation_verification_state)}
                    {krDimChip('Chủ sở hữu', kr.owner_acceptance_state)}
                    <span style={{
                      display: 'inline-block',
                      padding: '0.05rem 0.4rem',
                      borderRadius: '4px',
                      fontSize: '0.66rem',
                      border: `1px solid ${kr.authority_status !== 'none' ? '#22c55e55' : 'var(--border-subtle)'}`,
                      color: kr.authority_status !== 'none' ? '#22c55e' : 'var(--text-tertiary)',
                      whiteSpace: 'nowrap',
                    }}>
                      Cơ quan: {kr.authority_status}
                    </span>
                  </div>
                  {kr.note && <div style={{ color: 'var(--text-secondary)', fontSize: '0.72rem', fontStyle: 'italic' }}>{kr.note}</div>}
                  {/* active không phải "dùng được" */}
                  {kr.status === 'active' && (
                    <div style={{ marginTop: '4px', fontSize: '0.68rem', color: '#22c55e', border: '1px dashed #22c55e55', borderRadius: '4px', padding: '3px 6px' }}>
                      Đã duyệt (active) — phản ánh kết quả rà soát; không ngụ ý “có thể sử dụng” theo chính sách.
                    </div>
                  )}
                  {/* draft → gửi rà soát */}
                  {kr.status === 'draft' && (
                    <div style={{ marginTop: '6px' }}>
                      <button
                        onClick={() => void handleSubmitForReview(kr.id)}
                        disabled={reviewBusy === kr.id}
                        className="btn-secondary compact-button"
                        style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem', borderColor: '#3b82f655', color: '#3b82f6' }}
                      >
                        {reviewBusy === kr.id ? '…' : 'Gửi rà soát'}
                      </button>
                    </div>
                  )}
                  {/* review_pending → duyệt / từ chối */}
                  {kr.status === 'review_pending' && (
                    reviewPanelFor !== kr.id ? (
                      <div style={{ marginTop: '6px', display: 'flex', gap: '6px' }}>
                        <button
                          onClick={() => setReviewPanelFor(kr.id)}
                          className="btn-secondary compact-button"
                          style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem', borderColor: '#22c55e55', color: '#22c55e' }}
                        >
                          Duyệt (active)
                        </button>
                        <button
                          onClick={() => setReviewPanelFor(kr.id)}
                          className="btn-secondary compact-button"
                          style={{ fontSize: '0.7rem', padding: '0.15rem 0.55rem', borderColor: '#ef444455', color: '#ef4444' }}
                        >
                          Từ chối
                        </button>
                      </div>
                    ) : (
                      <div style={{ marginTop: '6px', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                          Rà soát kiểm soát — mọi chiều xác minh chỉ được máy chủ tính từ bằng chứng
                        </div>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          Người rà soát *
                          <input
                            style={REVIEW_INPUT_STYLE}
                            value={f.reviewer ?? ''}
                            onChange={e => setReviewField(kr.id, 'reviewer', e.target.value)}
                            placeholder="vd: An.D — cá nhân phê duyệt"
                          />
                        </label>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          Bằng chứng nguồn (tham chiếu) * — bắt buộc khi duyệt
                          <input
                            style={REVIEW_INPUT_STYLE}
                            value={f.source ?? ''}
                            onChange={e => setReviewField(kr.id, 'source', e.target.value)}
                            placeholder="vd: inputs/doc.txt dòng 3"
                          />
                        </label>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          Cơ quan ban hành (tập đóng: regulatory|organizational|expert|derived) * — bắt buộc khi duyệt
                          <select
                            style={REVIEW_INPUT_STYLE}
                            value={f.authorityStatus ?? ''}
                            onChange={e => setReviewField(kr.id, 'authorityStatus', e.target.value)}
                          >
                            <option value="" disabled>Chọn quyền hạn nguồn *</option>
                            {DIRAP_AUTHORITY_OPTIONS.map(v => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                        </label>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          Tham chiếu cơ quan ban hành * — bắt buộc khi duyệt
                          <input
                            style={REVIEW_INPUT_STYLE}
                            value={f.authorityRef ?? ''}
                            onChange={e => setReviewField(kr.id, 'authorityRef', e.target.value)}
                            placeholder="vd: Kết luận 04/2026 mục 2.1"
                          />
                        </label>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          Tham chiếu bằng chứng tính toán (tùy chọn; nếu có → chiều “Tính toán” thành verified)
                          <input
                            style={REVIEW_INPUT_STYLE}
                            value={f.calcRef ?? ''}
                            onChange={e => setReviewField(kr.id, 'calcRef', e.target.value)}
                            placeholder="vd: calc.xlsx sheet2"
                          />
                        </label>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                          Lý do (bắt buộc khi từ chối)
                          <textarea
                            style={{ ...REVIEW_INPUT_STYLE, minHeight: '44px', resize: 'vertical' }}
                            value={f.reason ?? ''}
                            onChange={e => setReviewField(kr.id, 'reason', e.target.value)}
                            placeholder="vd: nguồn không khớp"
                          />
                        </label>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                          <button
                            onClick={() => void handleApproveKnowledge(kr.id)}
                            disabled={reviewBusy === kr.id}
                            className="btn-primary compact-button"
                            style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem' }}
                          >
                            {reviewBusy === kr.id ? '…' : 'Duyệt → active'}
                          </button>
                          <button
                            onClick={() => void handleRejectKnowledge(kr.id)}
                            disabled={reviewBusy === kr.id}
                            className="btn-secondary compact-button"
                            style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem', borderColor: '#ef444455', color: '#ef4444' }}
                          >
                            Từ chối
                          </button>
                          <button
                            onClick={() => setReviewPanelFor(null)}
                            className="btn-secondary compact-button"
                            style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem' }}
                          >
                            Đóng
                          </button>
                        </div>
                      </div>
                    )
                  )}
                  {/* Khả dụng theo chính sách v1 — chỉ đọc (không lưu, không đổi dữ liệu gốc) */}
                  <div style={{ marginTop: '6px', border: '1px dashed var(--border-subtle)', borderRadius: '6px', padding: '8px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                        Khả dụng theo chính sách (chỉ đọc) — policy v1
                      </span>
                      <select
                        style={{ ...REVIEW_INPUT_STYLE, width: 'auto', fontSize: '0.68rem' }}
                        value={usabilityQueryType}
                        onChange={e => setUsabilityQueryType(e.target.value as DirapUsabilityQueryType)}
                        title="Chọn mục đích sử dụng để tính khả dụng"
                      >
                        {DIRAP_USABILITY_QUERY_TYPES.map(qt => (
                          <option key={qt} value={qt}>{QUERY_TYPE_LABELS[qt]} ({qt})</option>
                        ))}
                      </select>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <button
                        onClick={() => void handleCheckUsability(kr.id)}
                        disabled={usabilityBusyId === kr.id}
                        className="btn-secondary compact-button"
                        style={{ fontSize: '0.68rem', padding: '0.15rem 0.5rem' }}
                      >
                        {usabilityBusyId === kr.id ? '…' : 'Tính khả dụng'}
                      </button>
                      {usabilityByRecord[kr.id] ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                          {usabilityBadge(usabilityByRecord[kr.id]!.overall_usability_state)}
                          <span style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)' }}>
                            v{usabilityByRecord[kr.id]!.policy_version}
                          </span>
                        </span>
                      ) : null}
                    </div>
                    {usabilityByRecord[kr.id] && usabilityByRecord[kr.id]!.exclusions.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div style={{ fontSize: '0.66rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Lý do loại trừ:</div>
                        {usabilityByRecord[kr.id]!.exclusions.map((exc, idx) => (
                          <div key={idx} style={{ fontSize: '0.66rem', color: 'var(--text-secondary)', borderLeft: '2px solid var(--border-subtle)', paddingLeft: '6px' }}>
                            <strong>{exc.dimension}</strong>: cần {exc.required_state}, đang {exc.actual_state} — {exc.reason}
                          </div>
                        ))}
                      </div>
                    )}
                    {usabilityByRecord[kr.id] && usabilityByRecord[kr.id]!.usable_for_query_types.length > 0 && (
                      <div style={{ fontSize: '0.66rem', color: '#22c55e' }}>
                        Dùng được cho: {usabilityByRecord[kr.id]!.usable_for_query_types.map(type => QUERY_TYPE_LABELS[type]).join(', ')}
                      </div>
                    )}
                    <div style={{ fontSize: '0.64rem', color: 'var(--text-tertiary)' }}>
                      Kết quả này chỉ được tính khi xem và không thay đổi dữ liệu hay trạng thái duyệt.
                    </div>
                  </div>
                  {isExpanded && (
                    <div style={{ marginTop: '6px', border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '8px', fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '4px', wordBreak: 'break-all' }}>
                      <div><strong>Nội dung:</strong> {kr.content}</div>
                      <details className="technical-details"><summary>Chi tiết kỹ thuật và truy xuất nguồn</summary>
                        <div>Extraction: <code>{kr.extraction_id}</code></div>
                        <div>Bản ghi nguồn: <code>{kr.extraction_record_id}</code></div>
                        <div>Tệp nguồn: <code>{kr.source_file_id}</code></div>
                        <div>Hash nguồn: <code>{kr.source_sha256}</code></div>
                        <div>Phiên bản bộ trích xuất: {kr.extractor_version}</div>
                        <div>Trạng thái nội bộ: {kr.status}</div>
                      </details>
                      {krEvidence.length > 0 && (
                        <div style={{ marginTop: '4px' }}>
                          <strong>Bằng chứng rà soát ({krEvidence.length}):</strong>
                          {krEvidence.map(ev => (
                            <div key={ev.id} style={{ padding: '2px 0', fontSize: '0.7rem' }}>
                              <span style={{ color: '#a78bfa' }}>[{ev.evidence_type}]</span> {ev.reference}
                              {ev.note ? ` — ${ev.note}` : ''}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Audit Trail */}
          <div style={{ border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
            <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem' }}>Audit Trail ({detail.audit_events.length})</h4>
            {detail.audit_events.length === 0 && (
              <div className="empty-state" style={{ textAlign: 'center', padding: '12px', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                Chưa có sự kiện kiểm toán.
              </div>
            )}
            {detail.audit_events.slice(0, 20).map(e => (
              <div key={e.id} style={{ borderBottom: '1px solid var(--border-subtle)', padding: '6px 0', fontSize: '0.75rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '8px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>{e.action}</span>
                  <span style={{ color: 'var(--text-tertiary)', whiteSpace: 'nowrap' }}>{formatTime(e.created_at)}</span>
                </div>
                <div style={{ color: 'var(--text-secondary)' }}>
                  {e.actor} → {e.target || '(global)'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* List View */}
      {view === 'list' && (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {items.length === 0 && (
            <div className="empty-state" style={{ textAlign: 'center', padding: '24px 12px' }}>
              <div className="empty-state-title" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>Chưa có quy trình duyệt</div>
              <div className="empty-state-text" style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                Chọn Công việc và tạo quy trình để bắt đầu từ tài liệu nguồn.
              </div>
            </div>
          )}
          {items.map(item => (
            <button
              type="button"
              key={item.task_id}
              onClick={() => void handleViewDetail(item.task_id)}
              aria-label={`Mở quy trình ${item.title || 'không tiêu đề'}`}
              style={{
                display: 'block',
                width: '100%',
                color: 'inherit',
                font: 'inherit',
                textAlign: 'left',
                border: '1px solid var(--border-subtle)',
                padding: '10px 12px',
                marginBottom: '8px',
                borderRadius: '6px',
                cursor: 'pointer',
                background: 'transparent',
                transition: 'background var(--transition-fast)',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-tertiary)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <strong style={{ fontSize: '0.85rem', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.title || 'Không tiêu đề'}
                </strong>
                {statusBadge(item.status)}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>{item.session_title || item.session_id.slice(0, 8)}</span>
                <span>{item.source_files.length} tệp</span>
              </div>
              {item.goal && (
                <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.goal}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
