import React, { useEffect, useState } from 'react';
import { AlertTriangle, Check, Clipboard, ShieldAlert, X } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { type ApprovalDecision, submitApprovalDecision } from '../api/approvals';

function actionLabel(action: string): string {
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
      return action;
  }
}

function targetLabel(target: string): string {
  return target === 'memory_entries' ? 'Kho bộ nhớ' : target;
}

function isLocalScriptApproval(action: string, target: string, description?: string): boolean {
  const text = `${action} ${target} ${description || ''}`.toLowerCase();
  return (
    text.includes('script execution') ||
    text.includes('terminal') ||
    text.includes('shell') ||
    text.includes('python -c') ||
    text.includes('powershell') ||
    text.includes('cmd.exe') ||
    text.includes('execution via')
  );
}

function riskLabel(risk: string, elevated: boolean): string {
  if (elevated) {
    return 'Lệnh cục bộ hoặc script, cần duyệt từng lần';
  }

  switch (risk) {
    case 'read':
      return 'Chỉ đọc';
    case 'write_internal':
      return 'Ghi trong workspace';
    case 'external_or_destructive':
      return 'Tác động bên ngoài hoặc rủi ro cao';
    default:
      return risk;
  }
}

function quickReviewLabel(risk: string, elevated: boolean): string {
  if (elevated || risk === 'external_or_destructive') {
    return 'Rủi ro cao, chỉ cho phép nếu bạn hiểu lệnh và đúng mục tiêu.';
  }

  if (risk === 'write_internal') {
    return 'Chỉ cho phép nếu đúng workspace hoặc tệp mong muốn.';
  }

  if (risk === 'read') {
    return 'Rủi ro thấp, thường có thể cho phép.';
  }

  return 'Hãy kiểm tra kỹ hành động trước khi cho phép.';
}

function isSessionScopedApprovalAllowed(action: string, risk: string, elevated: boolean): boolean {
  if (elevated || risk === 'external_or_destructive') {
    return false;
  }

  return !['run_safe_task', 'call_n8n_webhook'].includes(action);
}

function decisionLabel(decision: ApprovalDecision): string {
  switch (decision) {
    case 'allow_once':
      return 'Đã cho phép một lần';
    case 'allow_for_session':
      return 'Đã cho phép trong phiên';
    case 'deny':
      return 'Đã từ chối';
  }
}

function approvalErrorMessage(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('409') || message.includes('expired') || message.includes('no longer active')) {
    return 'Yêu cầu phê duyệt đã hết hạn hoặc không còn hiệu lực. Hãy gửi lại yêu cầu nếu cần.';
  }
  if (message.includes('400') || message.includes('allow_for_session')) {
    return 'Hành động này chỉ được duyệt từng lần, không được cho phép trong cả phiên.';
  }
  return 'Không gửi được quyết định phê duyệt. Hãy kiểm tra backend rồi thử lại.';
}

export const ApprovalModal: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const pendingApproval = useHermesStore(state => state.pendingApproval);
  const setPendingApproval = useHermesStore(state => state.setPendingApproval);
  const setSessionStatus = useHermesStore(state => state.setSessionStatus);
  const addEvent = useHermesStore(state => state.addEvent);
  const requestAuditRefresh = useHermesStore(state => state.requestAuditRefresh);
  const [submittingDecision, setSubmittingDecision] = useState<ApprovalDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const elevatedLocalScript = pendingApproval
    ? isLocalScriptApproval(pendingApproval.action, pendingApproval.target, pendingApproval.description)
    : false;
  const isHighRisk = pendingApproval ? pendingApproval.risk_level === 'external_or_destructive' || elevatedLocalScript : false;
  const allowSessionDecision = pendingApproval
    ? isSessionScopedApprovalAllowed(pendingApproval.action, pendingApproval.risk_level, elevatedLocalScript)
    : false;
  const disableButtons = submittingDecision !== null;

  const copyText = async (field: string, value?: string) => {
    if (!value) return;
    try {
      await navigator.clipboard?.writeText(value);
      setCopiedField(field);
      window.setTimeout(() => setCopiedField(current => (current === field ? null : current)), 1500);
    } catch {
      setError('Không copy được nội dung. Bạn có thể bôi đen và copy thủ công.');
    }
  };

  const handleDecision = async (decision: ApprovalDecision) => {
    if (!pendingApproval) return;
    setSubmittingDecision(decision);
    setError(null);
    try {
      const response = await submitApprovalDecision(pendingApproval.approval_id, decision);
      const sessionId = response.session_id || activeSessionId;
      if (sessionId) {
        addEvent(sessionId, {
          id: `approval-${pendingApproval.approval_id}-${decision}`,
          type: 'approval_decision',
          decision,
          audit_action: response.audit_action,
          message: `${decisionLabel(decision)}: ${actionLabel(pendingApproval.action)}`,
        });
        setSessionStatus(sessionId, decision === 'deny' ? 'idle' : 'running');
      }
      requestAuditRefresh();
      setPendingApproval(null);
    } catch (err) {
      setError(approvalErrorMessage(err));
    } finally {
      setSubmittingDecision(null);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!pendingApproval) return;
      if (e.altKey && e.key === 'a') {
        e.preventDefault();
        if (!submittingDecision) void handleDecision('allow_once');
      }
      if (e.altKey && e.key === 'd') {
        e.preventDefault();
        if (!submittingDecision) void handleDecision('deny');
      }
      if (e.altKey && e.key === 's' && allowSessionDecision) {
        e.preventDefault();
        if (!submittingDecision) void handleDecision('allow_for_session');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (!pendingApproval) return null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="approval-title">
      <div className="modal-content approval-modal">
        <div className="approval-header">
          <ShieldAlert size={22} />
          <div>
            <h2 id="approval-title">Cần phê duyệt</h2>
            <p>Hermes đang yêu cầu quyền trước khi tiếp tục.</p>
          </div>
        </div>

        <div className={`approval-risk ${isHighRisk ? 'high' : ''}`}>
          <AlertTriangle size={16} />
          {riskLabel(pendingApproval.risk_level, elevatedLocalScript)}
        </div>

        <div className="approval-details">
          <div>
            <span>Hành động</span>
            <strong>{actionLabel(pendingApproval.action)}</strong>
          </div>
          <div>
            <span className="approval-detail-header">
              Đối tượng
              <button
                type="button"
                className="detail-copy-button"
                onClick={() => void copyText('target', pendingApproval.target)}
                title="Copy đối tượng"
              >
                <Clipboard size={13} />
                {copiedField === 'target' ? 'Đã copy' : 'Copy'}
              </button>
            </span>
            <strong>{targetLabel(pendingApproval.target)}</strong>
          </div>
          {pendingApproval.description && (
            <div>
              <span className="approval-detail-header">
                Mô tả
                <button
                  type="button"
                  className="detail-copy-button"
                  onClick={() => void copyText('description', pendingApproval.description)}
                  title="Copy mô tả"
                >
                  <Clipboard size={13} />
                  {copiedField === 'description' ? 'Đã copy' : 'Copy'}
                </button>
              </span>
              <strong>{pendingApproval.description}</strong>
            </div>
          )}
          <div>
            <span>Đánh giá nhanh</span>
            <strong>{quickReviewLabel(pendingApproval.risk_level, elevatedLocalScript)}</strong>
          </div>
        </div>

        {!allowSessionDecision && (
          <p className="approval-warning">
            Hành động này không được cấp quyền cho cả phiên. Bạn cần duyệt từng lần.
          </p>
        )}

        {error && <div className="inline-error">{error}</div>}

        <div className="modal-actions">
          <button className="btn-primary" onClick={() => void handleDecision('allow_once')} disabled={disableButtons}>
            <Check size={14} /> Cho phép một lần
          </button>
          {allowSessionDecision && (
            <button
              className="btn-secondary"
              onClick={() => void handleDecision('allow_for_session')}
              disabled={disableButtons}
            >
              Cho phép trong phiên
            </button>
          )}
          <button className="btn-danger" onClick={() => void handleDecision('deny')} disabled={disableButtons}>
            <X size={14} /> Từ chối
          </button>
        </div>
      </div>
    </div>
  );
};
