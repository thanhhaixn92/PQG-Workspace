import { apiFetch } from './client';

export type ApprovalDecision = 'allow_once' | 'allow_for_session' | 'deny';

export interface ApprovalDecisionResponse {
  status: 'recorded';
  approval_id: string;
  session_id?: string | null;
  decision: ApprovalDecision;
  audit_action: string;
}

export const submitApprovalDecision = async (
  approvalId: string,
  decision: ApprovalDecision,
): Promise<ApprovalDecisionResponse> => {
  return apiFetch<ApprovalDecisionResponse>(`/api/approvals/${approvalId}`, {
    method: 'POST',
    body: JSON.stringify({ decision }),
  });
};
