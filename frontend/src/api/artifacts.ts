import { apiFetch } from './client';

export interface Artifact {
  id: string;
  session_id: string | null;
  relative_path: string;
  kind: string;
  sha256: string;
  size_bytes: number;
  created_at: number;
  validation_status?: 'pending' | 'structurally_validated' | 'rejected' | 'failed';
  media_type?: string | null;
}

export interface ReportResult extends Artifact {
  duplicate: boolean;
}

export const listArtifacts = (sessionId: string): Promise<Artifact[]> =>
  apiFetch<Artifact[]>(`/api/sessions/${sessionId}/artifacts`);

export const createMarkdownReport = (
  sessionId: string,
  title: string,
  content: string,
  idempotencyKey: string,
  outputFormat: 'markdown' | 'html' = 'markdown',
): Promise<ReportResult> => apiFetch<ReportResult>(`/api/sessions/${sessionId}/reports`, {
  method: 'POST',
  headers: { 'Idempotency-Key': idempotencyKey },
  body: JSON.stringify({ title, content, output_format: outputFormat }),
});
