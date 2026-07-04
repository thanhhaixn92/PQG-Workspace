import { apiFetch } from './client';

export interface AuditEvent {
  id: string;
  session_id?: string | null;
  actor: string;
  action: string;
  target?: string | null;
  payload_json?: string | null;
  created_at: number;
}

export const getSessionAuditEvents = async (
  sessionId: string,
  limit = 100,
): Promise<AuditEvent[]> => {
  return apiFetch<AuditEvent[]>(`/api/sessions/${sessionId}/audit-events?limit=${limit}`);
};
