import { apiFetch } from './client';

export interface N8nStatus {
  configured: boolean;
  webhook_base_url: string;
  allowed_workflows: string[];
  guidance: string;
}

export interface N8nTestEchoResponse {
  status: 'skipped' | 'sent' | 'error';
  workflow_name: 'echo';
  message: string;
  response_status?: number | null;
}

export async function fetchN8nStatus(): Promise<N8nStatus> {
  return apiFetch<N8nStatus>('/api/n8n/status');
}

export async function testN8nEcho(sessionId?: string | null): Promise<N8nTestEchoResponse> {
  return apiFetch<N8nTestEchoResponse>('/api/n8n/test-echo', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId || null,
      payload: {
        source: 'hermes-ui-smoke',
        timestamp: Math.floor(Date.now() / 1000),
      },
    }),
  });
}
