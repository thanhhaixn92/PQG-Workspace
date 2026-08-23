import { StatusBadge } from './ui/StatusBadge';
import { ASSISTANT_LABEL } from '../branding';

export type ReviewCategory = 'pending' | 'revision' | 'decided';

export interface ReviewProjection {
  id: string;
  source: 'Trợ lý' | 'Kỹ năng' | 'Tri thức tài liệu' | 'Memory Hub';
  title: string;
  status: string;
  category: ReviewCategory;
  scope: string;
  risk: string;
  before: string;
  after: string;
  rollback: string;
  destination: 'hermes' | 'skills';
  taskId?: string;
  sourceFileId?: string;
  provenance?: string | null;
  lifecycle?: string;
  actionPackageBinding?: { expectedRevision: number; expectedPayloadHash: string } | null;
}

export function ApprovalItem({ item, expanded, busy, onToggle, onDecide, onOpen }: {
  item: ReviewProjection;
  expanded: boolean;
  busy: boolean;
  onToggle: () => void;
  onDecide: (decision: 'approve' | 'deny') => void;
  onOpen: () => void;
}) {
  return <article className="review-inbox-item">
    <div className="review-source-row"><strong>{item.title}</strong><StatusBadge tone={item.category === 'decided' ? 'success' : 'warning'}>{item.status}</StatusBadge></div>
    <div>Nguồn: {item.source} · Phạm vi: {item.scope}</div><div>Mức tác động: {item.risk}</div><div className="runtime-guidance">{item.after}</div>
    <button className="btn-secondary compact-button" aria-expanded={expanded} onClick={onToggle}>{expanded ? 'Ẩn chi tiết' : 'Xem trước và sau'}</button>
    {expanded && <div className="runtime-guidance" role="region" aria-label={`Chi tiết ${item.title}`}><div><strong>Trước:</strong> {item.before}</div><div><strong>Sau:</strong> {item.after}</div><div><strong>Hoàn tác:</strong> {item.rollback}</div><div><strong>Hết hạn:</strong> Nguồn chưa công bố thời hạn tự động.</div></div>}
    {item.category === 'pending' && <div className="review-decision-actions"><button className="btn-primary compact-button" disabled={busy || (item.source === 'Trợ lý' && !item.actionPackageBinding)} onClick={() => onDecide('approve')}>{item.source === 'Trợ lý' ? 'Duyệt gói đề xuất' : item.source === 'Memory Hub' && item.lifecycle === 'verified' ? 'Kích hoạt' : 'Duyệt tại nguồn'}</button><button className="btn-secondary compact-button" disabled={busy || (item.source === 'Trợ lý' && !item.actionPackageBinding)} onClick={() => onDecide('deny')}>{item.source === 'Kỹ năng' ? 'Trả về bản nháp' : 'Từ chối tại nguồn'}</button></div>}
    <button className="btn-secondary compact-button" onClick={onOpen}>{item.destination === 'hermes' ? `Mở đề xuất trong ${ASSISTANT_LABEL}` : 'Mở khu vực Tri thức'}</button>
  </article>;
}
