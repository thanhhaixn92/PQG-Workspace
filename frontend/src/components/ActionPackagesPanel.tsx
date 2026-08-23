import React, { useCallback, useEffect, useState } from 'react';
import { Check, ShieldAlert, X } from 'lucide-react';
import {
  approveActionPackage, createActionPackageIdempotencyKey, denyActionPackage,
  getActionPackageDecisionBinding, getWorkActionPackages, type ActionPackage,
} from '../api/actionPackages';
import { ASSISTANT_NAME } from '../branding';
import { ApiError } from '../api/client';

const statusLabel: Record<string, string> = {
  awaiting_approval: 'Chờ bạn duyệt',
  approved: 'Đã duyệt, đang chuẩn bị',
  executing: 'Đang thực hiện',
  succeeded: 'Đã hoàn tất',
  partially_failed: 'Hoàn tất một phần',
  failed: 'Không hoàn tất',
  cancelled: 'Đã hủy',
};

const stepExplanation = (kind: string) => {
  if (kind === 'work_plan_step_update') {
    return {
      impact: 'Cập nhật một bước trong kế hoạch của Công việc này; không thay đổi tài liệu hay dữ liệu Công việc khác.',
      undo: 'Có thể hoàn tác bằng một đề xuất mới để đặt lại nội dung hoặc trạng thái của bước.',
    };
  }
  if (kind === 'work_status_update') {
    return {
      impact: 'Cập nhật trạng thái và phần trăm tiến độ của Công việc này.',
      undo: 'Có thể hoàn tác bằng một đề xuất mới để cập nhật lại trạng thái hoặc tiến độ.',
    };
  }
  return {
    impact: 'Thay đổi này chỉ được áp dụng trong Công việc hiện tại.',
    undo: 'Khả năng hoàn tác sẽ được nêu rõ trước khi bạn duyệt.',
  };
};

export const ActionPackagesPanel: React.FC<{ workId: string }> = ({ workId }) => {
  const [items, setItems] = useState<ActionPackage[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await getWorkActionPackages(workId));
      setError(null);
    } catch {
      setError('Chưa tải được các đề xuất thay đổi.');
    }
  }, [workId]);

  useEffect(() => { void load(); }, [load]);

  const decide = async (item: ActionPackage, decision: 'approve' | 'deny') => {
    const binding = getActionPackageDecisionBinding(item);
    if (!binding) {
      setError('Gói thay đổi chưa có dữ liệu xác nhận chuẩn. Hãy làm mới trước khi quyết định.');
      return;
    }
    setBusy(item.id);
    try {
      const idempotencyKey = createActionPackageIdempotencyKey(`action-package-${decision}`);
      if (decision === 'approve') await approveActionPackage(item.id, binding, idempotencyKey);
      else await denyActionPackage(item.id, binding, idempotencyKey);
      await load();
    } catch (caught) {
      setItems([]);
      await load();
      setError(caught instanceof ApiError && caught.status === 409
        ? 'Mục đã được xử lý ở nơi khác. Trạng thái đang được làm mới.'
        : 'Quyết định chưa được ghi nhận. Trạng thái đang được làm mới.');
    } finally {
      setBusy(null);
    }
  };

  const visible = items.slice(0, 3);
  return <section className="action-packages-panel" aria-label="Đề xuất thay đổi">
    <header>
      <div>
        <h2>Đề xuất thay đổi</h2>
        <p>{ASSISTANT_NAME} chỉ có thể thực hiện thay đổi sau khi bạn duyệt đúng gói đã xem.</p>
        <p className="action-package-guidance">Cách duyệt: yêu cầu {ASSISTANT_NAME} tạo đề xuất, kiểm tra tác động và hoàn tác của gói bên dưới, rồi bấm Duyệt. Bấm Từ chối nếu không muốn áp dụng; trò chuyện hoặc giao việc không tự thay đổi dữ liệu.</p>
      </div>
      <ShieldAlert size={20} />
    </header>
    {error ? <div className="inline-error">{error}</div> : null}
    {visible.length === 0 ? <p className="muted-copy">Hiện chưa có thay đổi nào chờ bạn duyệt. GYO vẫn chỉ trả lời hoặc chuẩn bị đề xuất cho đến khi có một gói hợp lệ.</p> : visible.map(item => <article key={item.id}>
      <div>
        <strong>{item.title}</strong>
        <p>{item.description || `${item.steps.length} bước thay đổi có thể hoàn tác.`}</p>
        <small>{statusLabel[item.status] || item.status} · {item.steps.length} bước</small>
        <div className="action-package-explanations">
          {item.steps.map(step => {
            const explanation = stepExplanation(step.kind);
            return <div key={step.id}>
              <strong>Tác động</strong><span>{explanation.impact}</span>
              <strong>Hoàn tác</strong><span>{explanation.undo}</span>
            </div>;
          })}
        </div>
      </div>
      {item.status === 'awaiting_approval' ? <div className="action-package-buttons">
        <button className="btn-primary compact-button" disabled={busy === item.id || !getActionPackageDecisionBinding(item)} onClick={() => void decide(item, 'approve')}><Check size={15} />Duyệt</button>
        <button className="btn-secondary compact-button" disabled={busy === item.id || !getActionPackageDecisionBinding(item)} onClick={() => void decide(item, 'deny')}><X size={15} />Từ chối</button>
      </div> : null}
    </article>)}
  </section>;
};
