import { apiFetch } from './client';

export type MemoryHubKind = 'preference' | 'project_context' | 'task_continuity' | 'workflow_rule' | 'technical_decision' | 'lesson';
export type MemoryHubLifecycle = 'proposed' | 'verified' | 'active' | 'superseded' | 'rejected';

export interface MemoryHubRecord {
  id: string;
  kind: MemoryHubKind;
  memory_key: string;
  content: string;
  project_id: string | null;
  task_id: string | null;
  lifecycle: MemoryHubLifecycle;
  sensitivity: 'normal';
  created_at: number;
}

export interface MemoryHubProposal {
  kind: MemoryHubKind;
  memory_key: string;
  content: string;
  project_id?: string;
  task_id?: string;
}

export interface LegacyPreview {
  legacy_memory_id: string;
  memory_key: string;
  content: string;
  kind: string;
}

function params(values: Record<string, string | boolean | undefined>): string {
  const query = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') query.set(key, String(value));
  });
  const serialized = query.toString();
  return serialized ? `?${serialized}` : '';
}

export async function searchMemoryHub(scope: { project_id?: string; task_id?: string; include_global_preferences?: boolean }, q?: string): Promise<MemoryHubRecord[]> {
  return apiFetch(`/api/memory-hub/operator/records${params({ ...scope, q })}`);
}

export async function createMemoryHubProposal(proposal: MemoryHubProposal): Promise<MemoryHubRecord> {
  return apiFetch('/api/memory-hub/operator/proposals', { method: 'POST', body: JSON.stringify(proposal) });
}

export async function transitionMemoryHubRecord(recordId: string, action: 'verify' | 'activate' | 'reject'): Promise<MemoryHubRecord> {
  return apiFetch(`/api/memory-hub/operator/records/${recordId}/${action}`, { method: 'POST', body: '{}' });
}

export async function previewLegacyMemory(memoryIds: string[]): Promise<LegacyPreview[]> {
  return apiFetch('/api/memory-hub/operator/legacy-import/preview', { method: 'POST', body: JSON.stringify({ memory_ids: memoryIds }) });
}

export async function importLegacyMemory(memoryIds: string[], scope: { project_id?: string; task_id?: string }): Promise<MemoryHubRecord[]> {
  return apiFetch('/api/memory-hub/operator/legacy-import', { method: 'POST', body: JSON.stringify({ memory_ids: memoryIds, ...scope }) });
}
