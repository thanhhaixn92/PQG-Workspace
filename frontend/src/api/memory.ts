import { apiFetch } from './client';

export type MemoryKind = 'preference' | 'project_fact' | 'workflow_rule' | 'style_rule' | 'temporary_note';

export interface MemoryEntry {
  id: string;
  session_id: string | null;
  key: string;
  value: string;
  kind: MemoryKind;
  importance_score: number;
  last_accessed_at: number | null;
  created_at: number;
}

export async function fetchGlobalMemory(): Promise<MemoryEntry[]> {
  return await apiFetch('/api/memory');
}

export async function fetchSessionMemory(sessionId: string): Promise<MemoryEntry[]> {
  return await apiFetch(`/api/sessions/${sessionId}/memory`);
}

export async function createMemory(entry: { session_id?: string; key: string; value: string; kind: MemoryKind; importance_score?: number }): Promise<MemoryEntry> {
  return await apiFetch('/api/memory', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
}

export async function updateMemory(id: string, entry: Partial<MemoryEntry>): Promise<MemoryEntry> {
  return await apiFetch(`/api/memory/${id}`, {
    method: 'PUT',
    body: JSON.stringify(entry),
  });
}

export async function deleteMemory(id: string): Promise<void> {
  await apiFetch(`/api/memory/${id}`, {
    method: 'DELETE',
  });
}
