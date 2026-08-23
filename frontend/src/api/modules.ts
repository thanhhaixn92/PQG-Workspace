import { apiFetch } from './client';

export type ModuleSourceKind = 'builtin' | 'marketplace';
export type ModuleHealthState = 'ready' | 'degraded' | 'unavailable' | 'unknown';

export interface ModuleInstance {
  id: string;
  module_id: string;
  source_kind: ModuleSourceKind;
  package_id?: string | null;
  display_name: string;
  attached: boolean;
  sort_order: number;
  config: Record<string, unknown>;
  config_version: number;
  health_state: ModuleHealthState;
  revision: number;
  created_at: number;
  updated_at: number;
}

export const getModuleInstances = () => apiFetch<ModuleInstance[]>('/api/modules');

export const attachModule = (moduleId: string, expectedRevision: number) =>
  apiFetch<ModuleInstance>(`/api/admin/modules/${encodeURIComponent(moduleId)}/attach`, {
    method: 'POST',
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });

export const detachModule = (moduleId: string, expectedRevision: number) =>
  apiFetch<ModuleInstance>(`/api/admin/modules/${encodeURIComponent(moduleId)}/detach`, {
    method: 'POST',
    body: JSON.stringify({ expected_revision: expectedRevision }),
  });

export const renameModule = (moduleId: string, displayName: string, expectedRevision: number) =>
  apiFetch<ModuleInstance>(`/api/admin/modules/${encodeURIComponent(moduleId)}`, {
    method: 'PATCH',
    body: JSON.stringify({ display_name: displayName, expected_revision: expectedRevision }),
  });

export const reorderModules = (moduleIds: string[], expectedRevisions: Record<string, number>) =>
  apiFetch<ModuleInstance[]>('/api/admin/modules/reorder', {
    method: 'POST',
    body: JSON.stringify({ module_ids: moduleIds, expected_revisions: expectedRevisions }),
  });
