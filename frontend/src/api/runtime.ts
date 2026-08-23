import { apiFetch } from './client';

export interface RuntimeStatus {
  backend: 'ok';
  db: {
    status: 'ok' | 'error';
  };
  hermes: {
    status: 'ready' | 'mock' | 'missing' | 'not_configured' | 'auth_unknown' | 'auth_expired';
    guidance: string;
  };
  timestamp: number;
}

export type RuntimeSmokeStatus = 'ready' | 'needs_config' | 'error' | 'skipped';

export interface RuntimeSmokeCheck {
  key: string;
  label: string;
  status: RuntimeSmokeStatus;
  detail: string;
}

export interface RuntimeSmokeResponse {
  checks: RuntimeSmokeCheck[];
  timestamp: number;
}

/** Opaque local scope for client-only draft namespacing; never an actor identifier. */
export interface RuntimeIdentityScope {
  identity_scope: string;
  workspace_scope: string;
}

export async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  return apiFetch<RuntimeStatus>('/api/runtime/status');
}

export async function runRuntimeSmoke(sessionId?: string | null): Promise<RuntimeSmokeResponse> {
  return apiFetch<RuntimeSmokeResponse>('/api/runtime/smoke', {
    method: 'POST',
    body: JSON.stringify(sessionId ? { session_id: sessionId } : {}),
  });
}

export const getRuntimeIdentityScope = () => apiFetch<RuntimeIdentityScope>('/api/runtime/identity-scope');
