import { apiFetch } from './client';

export interface KnowledgeSummary {
  work_id: string | null;
  counts_by_source: Record<string, number>;
  counts_by_lifecycle: Record<string, number>;
  context_included_count: number;
  context_excluded_count: number;
  pending_review_count: number;
  last_updated_at: number | null;
}

export function getKnowledgeSummary(workId?: string | null): Promise<KnowledgeSummary> {
  const query = workId ? `?work_id=${encodeURIComponent(workId)}` : '';
  return apiFetch<KnowledgeSummary>(`/api/knowledge/summary${query}`);
}
