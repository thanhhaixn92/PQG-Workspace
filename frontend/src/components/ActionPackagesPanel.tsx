import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Check, ShieldAlert, X } from 'lucide-react';
import {
  approveActionPackage, createActionPackageIdempotencyKey, denyActionPackage,
  getActionPackageDecisionBinding, getActionPackagePreflight, getActionPackagePreflightDecisionBinding,
  getWorkActionPackages, type ActionPackage,
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
  const decisionInFlightRef = useRef<Set<string>>(new Set());

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
    if (decisionInFlightRef.current.has(item.id)) return;
    const displayedBinding = getActionPackageDecisionBinding(item);
    if (!displayedBinding) {
      setError('Gói thay đổi chưa có dữ liệu xác nhận chuẩn. Hãy làm mới trước khi quyết định.');
      return;
    }

    decisionInFlightRef.current.add(item.id);
    setBusy(item.id);
    setError(null);
    try {
      // The package may have changed while the user was reading it. The
      // click-time canonical preflight is authoritative, but a binding that no
      // longer matches the rendered package is stale and must not be silently
      // accepted as a different decision.
      const preflight = await getActionPackagePreflight(item.id);
      const currentBinding = getActionPackagePreflightDecisionBinding(preflight);
      const packageMatches = preflight.package_id === item.id;
      const bindingMatches = currentBinding?.expectedRevision === displayedBinding.expectedRevision
        && currentBinding?.expectedPayloadHash === displayedBinding.expectedPayloadHash;
      if (!packageMatches || !currentBinding || !bindingMatches) {
        throw new ApiError(409, 'Gói thay đổi đã thay đổi hoặc không còn hợp lệ.');
      }

      // Allocate the idempotency key only after the current preflight has
      // succeeded. No stale/expired/error path reaches the decision request.
      const idempotencyKey = createActionPackageIdempotencyKey(`action-package-${decision}`);
      if (decision === 'approve') await approveActionPackage(item.id, currentBinding, idempotencyKey);
      else await denyActionPackage(item.id, currentBinding, idempotencyKey);
      await load();
    } catch (caught) {
      // Fail closed: remove the stale CTA immediately, then reload the server's
      // authoritative package state. This path is shared by 409/expiry,
      // invalid preflight, binding mismatch and network failures.
      setItems([]);
      await load();
      setError(caught instanceof ApiError && caught.status === 409
        ? 'Gói thay đổi đã thay đổi, hết hạn hoặc được xử lý ở nơi khác. Trạng thái đã được làm mới.'
        : 'Chưa thể xác minh gói thay đổi. Không có quyết định nào được gửi; trạng thái đã được làm mới.');
    } finally {
      decisionInFlightRef.current.delete(item.id);
      setBusy(current => current === item.id ? null : current);
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
