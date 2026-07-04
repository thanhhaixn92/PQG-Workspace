import { apiFetch } from './client';

export interface RuntimeStatus {
  backend: 'ok';
  db: {
    status: 'ok' | 'error';
    path: string;
  };
  hermes: {
    status: 'ready' | 'mock' | 'missing' | 'not_configured' | 'auth_unknown' | 'auth_expired';
    executable_path: string;
    configured: boolean;
    executable_found: boolean;
    auth_status: 'ready' | 'unknown' | 'not_required' | 'auth_expired';
    dev_mock: boolean;
    args: string[];
    guidance: string;
  };
  n8n: {
    configured: boolean;
    webhook_base_url: string;
    guidance: string;
  };
  environment: {
    env_file_exists: boolean;
    cwd: string;
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

export async function fetchRuntimeStatus(): Promise<RuntimeStatus> {
  return apiFetch<RuntimeStatus>('/api/runtime/status');
}

export async function runRuntimeSmoke(sessionId?: string | null): Promise<RuntimeSmokeResponse> {
  return apiFetch<RuntimeSmokeResponse>('/api/runtime/smoke', {
    method: 'POST',
    body: JSON.stringify(sessionId ? { session_id: sessionId } : {}),
  });
}
