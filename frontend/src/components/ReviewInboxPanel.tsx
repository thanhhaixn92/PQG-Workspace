import React, { useEffect, useRef, useState } from 'react';
import { approveActionPackage, createActionPackageIdempotencyKey, denyActionPackage, getActionPackageDecisionBinding, getWorkActionPackages } from '../api/actionPackages';
import { approveKnowledgeRecord, listKnowledgeRecords, listWorkItems, rejectKnowledgeRecord } from '../api/dirap';
import { searchMemoryHub, transitionMemoryHubRecord } from '../api/memoryHub';
import { changeSkillStatus, fetchSkills } from '../api/skills';
import { ApiError } from '../api/client';
import { ApprovalItem, type ReviewCategory, type ReviewProjection } from './ApprovalItem';
import { useHermesStore } from '../store/store';

const CATEGORY_LABELS: Record<ReviewCategory, string> = {
  pending: 'Chờ xử lý', revision: 'Cần chỉnh sửa', decided: 'Đã quyết định',
};

export const ReviewInboxPanel: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const approval = useHermesStore(state => state.pendingApproval);
  const setSidebarTab = useHermesStore(state => state.setSidebarTab);
  const [items, setItems] = useState<ReviewProjection[]>([]);
  const [category, setCategory] = useState<ReviewCategory>('pending');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionBusy, setDecisionBusy] = useState<string | null>(null);
  const [refreshRevision, setRefreshRevision] = useState(0);
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    setItems([]);
    setSelectedKey(null);
    setError(null);
    if (!activeSessionId) return;
    setLoading(true);
    Promise.allSettled([
      fetchSkills(),
      listWorkItems({ session_id: activeSessionId }).then(async works => {
        const records = await Promise.all(works.map(work => listKnowledgeRecords(work.task_id)));
        return records.flat();
      }),
      searchMemoryHub({ project_id: activeSessionId }),
      getWorkActionPackages(activeSessionId),
    ]).then(results => {
      if (version !== requestVersion.current || useHermesStore.getState().activeSessionId !== activeSessionId) return;
      const projected: ReviewProjection[] = [];
      if (results[0].status === 'fulfilled') results[0].value.forEach(skill => projected.push({
        id: skill.id, source: 'Kỹ năng', title: skill.name,
        status: skill.status === 'review_pending' ? 'Chờ duyệt' : skill.status === 'approved' ? 'Đã duyệt' : 'Bản nháp',
        category: skill.status === 'review_pending' ? 'pending' : skill.status === 'approved' ? 'decided' : 'revision',
        scope: 'Toàn ứng dụng', risk: 'Kỹ năng được duyệt và bật có thể đi vào ngữ cảnh trợ lý.',
        before: skill.status === 'draft' ? 'Bản nháp, không được dùng.' : 'Trạng thái hiện tại được giữ nguyên.',
        after: skill.status === 'review_pending' ? 'Nếu duyệt, kỹ năng vẫn cần được bật riêng.' : 'Không có thay đổi đang chờ.',
        rollback: 'Có thể trả về bản nháp hoặc tắt tại khu vực Kỹ năng.', destination: 'skills',
        lifecycle: skill.status,
      }));
      if (results[1].status === 'fulfilled') results[1].value.forEach(record => projected.push({
        id: record.id, source: 'Tri thức tài liệu', title: record.content.slice(0, 90),
        status: record.status === 'review_pending' ? 'Chờ duyệt' : record.status === 'active' ? 'Đang hoạt động' : record.status === 'rejected' ? 'Đã từ chối' : 'Bản nháp',
        category: record.status === 'review_pending' ? 'pending' : record.status === 'draft' ? 'revision' : 'decided',
        scope: 'Công việc hiện tại', risk: 'Chỉ bản ghi active có đủ bằng chứng mới được tìm kiếm để sử dụng.',
        before: `${record.status} · nguồn ${record.source_file_id || 'đã đăng ký'}`,
        after: record.status === 'review_pending' ? 'Duyệt thành active hoặc từ chối nhưng vẫn giữ lịch sử.' : 'Không có quyết định đang chờ.',
        rollback: 'Nguồn và bằng chứng được giữ; không xóa lịch sử quyết định.', destination: 'skills',
        taskId: record.task_id, sourceFileId: record.source_file_id, provenance: record.provenance, lifecycle: record.status,
      }));
      if (results[2].status === 'fulfilled') results[2].value.forEach(record => projected.push({
        id: record.id, source: 'Memory Hub', title: record.memory_key,
        status: record.lifecycle === 'verified' ? 'Đã xác minh, chờ kích hoạt' : record.lifecycle === 'proposed' ? 'Đề xuất' : record.lifecycle,
        category: record.lifecycle === 'proposed' || record.lifecycle === 'verified' ? 'pending' : record.lifecycle === 'active' || record.lifecycle === 'rejected' || record.lifecycle === 'superseded' ? 'decided' : 'revision',
        scope: 'Công việc hiện tại', risk: 'Memory Hub không bao giờ tự động được đưa vào chat.',
        before: `Vòng đời hiện tại: ${record.lifecycle}.`,
        after: record.lifecycle === 'verified' ? 'Chỉ người có quyền mới có thể kích hoạt.' : 'Mỗi chuyển trạng thái cần quyết định tại Memory Hub.',
        rollback: 'Phiên bản cũ được giữ bằng lifecycle; không sửa lịch sử tại Hộp duyệt.', destination: 'skills',
        lifecycle: record.lifecycle,
      }));
      if (results[3].status === 'fulfilled') results[3].value.forEach(item => projected.push({
        id: item.id, source: 'Trợ lý', title: item.title,
        status: item.status === 'awaiting_approval' ? 'Chờ bạn duyệt' : item.status,
        category: item.status === 'awaiting_approval' ? 'pending' : item.status === 'draft' || item.status === 'failed' || item.status === 'partially_failed' ? 'revision' : 'decided',
        scope: 'Công việc hiện tại',
        risk: item.steps.some(step => ['external', 'destructive', 'external_or_destructive'].includes(step.risk_level)) ? 'Có bước tác động bên ngoài hoặc khó hoàn tác.' : 'Cập nhật dữ liệu Công việc trên máy này.',
        before: 'Dữ liệu Công việc hiện tại chưa bị thay đổi bởi đề xuất.',
        after: `${item.steps.length} bước đã được đóng gói bất biến. Chỉ chạy sau khi package hash được duyệt.`,
        rollback: 'Xem khả năng hoàn tác của từng bước tại Công việc trước khi quyết định.', destination: 'hermes',
        actionPackageBinding: getActionPackageDecisionBinding(item),
      }));
      setItems(projected);
      if (results.some(result => result.status === 'rejected')) setError('Một số nguồn duyệt chưa tải được; các mục còn lại vẫn được hiển thị.');
    }).finally(() => { if (version === requestVersion.current) setLoading(false); });
  }, [activeSessionId, refreshRevision]);

  const decideItem = async (item: ReviewProjection, decision: 'approve' | 'deny') => {
    if (item.category !== 'pending' || decisionBusy) return;
    setDecisionBusy(item.id);
    try {
      if (item.source === 'Trợ lý') {
        if (!item.actionPackageBinding) throw new Error('Gói thay đổi chưa có dữ liệu xác nhận chuẩn.');
        const idempotencyKey = createActionPackageIdempotencyKey(`review-action-${decision}`);
        if (decision === 'approve') await approveActionPackage(item.id, item.actionPackageBinding, idempotencyKey);
        else await denyActionPackage(item.id, item.actionPackageBinding, idempotencyKey);
      } else if (item.source === 'Kỹ năng') {
        await changeSkillStatus(item.id, decision === 'approve' ? 'approved' : 'draft');
      } else if (item.source === 'Tri thức tài liệu' && item.taskId) {
        if (decision === 'approve') await approveKnowledgeRecord(item.taskId, item.id, {
          reviewer: 'local-user', source_evidence_reference: item.sourceFileId || 'managed-source',
          authority_status: 'derived', authority_reference: item.provenance || item.sourceFileId || 'managed-source',
          note: 'Quyết định từ Hộp duyệt projection.',
        }, `review-approve-${item.id}`);
        else await rejectKnowledgeRecord(item.taskId, item.id, {
          reviewer: 'local-user', reason: 'Trả lại để chỉnh sửa từ Hộp duyệt.',
        }, `review-reject-${item.id}`);
      } else if (item.source === 'Memory Hub') {
        const action = decision === 'deny' ? 'reject' : item.lifecycle === 'verified' ? 'activate' : 'verify';
        await transitionMemoryHubRecord(item.id, action);
      }
      setError(null);
      setRefreshRevision(value => value + 1);
    } catch (caught) {
      setError(caught instanceof ApiError && caught.status === 409
        ? 'Mục này đã được xử lý ở nơi khác. Danh sách đang được làm mới.'
        : 'Quyết định không được ghi nhận. Danh sách sẽ được tải lại để tránh ghi đè trạng thái mới.');
      setRefreshRevision(value => value + 1);
    } finally { setDecisionBusy(null); }
  };

  const openSource = (item: ReviewProjection) => {
    const source = item.source === 'Trợ lý' ? 'action_package' : item.source === 'Kỹ năng' ? 'skill' : item.source === 'Tri thức tài liệu' ? 'knowledge' : 'memory_hub';
    const target = `${source}:${item.id}`;
    window.sessionStorage.setItem('hermes:review-target', target);
    window.history.replaceState(null, '', `#review/${encodeURIComponent(target)}`);
    setSidebarTab(item.destination);
  };

  const approvalForActiveSession = approval?.session_id === activeSessionId ? approval : null;
  const visible = items.filter(item => item.category === category);
  const counts = items.reduce<Record<ReviewCategory, number>>((result, item) => {
    result[item.category] += 1;
    return result;
  }, { pending: approvalForActiveSession ? 1 : 0, revision: 0, decided: 0 });

  return <div className="list-panel review-inbox-panel">
    <div className="section-header"><div><h3>Hộp duyệt</h3><p>Một projection hợp nhất; quyết định vẫn được thực hiện tại đúng nguồn để giữ nguyên lifecycle.</p></div></div>
    <nav className="grouped-panel-tabs" aria-label="Trạng thái duyệt">{(Object.keys(CATEGORY_LABELS) as ReviewCategory[]).map(key => <button key={key} className={category === key ? 'active' : ''} onClick={() => setCategory(key)}>{CATEGORY_LABELS[key]} ({counts[key]})</button>)}</nav>
    <div className="panel-content">
      {!activeSessionId && <div className="empty-state">Chọn một Công việc để xem mục cần rà soát.</div>}
      {loading && <div className="loading-indicator">Đang tổng hợp các nguồn duyệt…</div>}
      {error && <div className="inline-error" role="status">{error}</div>}
      {activeSessionId && !loading && visible.length === 0 && !(category === 'pending' && approvalForActiveSession) && <div className="empty-state"><strong>Không có mục trong nhóm này</strong><div>Các nguồn vẫn giữ trạng thái và lịch sử riêng.</div></div>}
      {category === 'pending' && approvalForActiveSession && <article className="review-inbox-item"><strong>{approvalForActiveSession.description || approvalForActiveSession.action}</strong><div>Nguồn: Trợ lý · Phạm vi: Công việc hiện tại</div><div>Mức tác động: {approvalForActiveSession.risk_level === 'external_or_destructive' ? 'Bên ngoài hoặc khó hoàn tác' : 'Thay đổi dữ liệu local'}</div><div className="runtime-guidance">Hộp quyết định đang mở; kiểm tra đích tác động trước khi cho phép.</div></article>}
      {visible.map(item => { const key = `${item.source}-${item.id}`; return <ApprovalItem key={key} item={item} expanded={selectedKey === key} busy={decisionBusy === item.id} onToggle={() => setSelectedKey(selectedKey === key ? null : key)} onDecide={decision => void decideItem(item, decision)} onOpen={() => openSource(item)} />; })}
    </div>
  </div>;
};
