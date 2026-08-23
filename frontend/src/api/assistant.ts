import { apiFetch, BASE_URL } from './client';

export interface AssistantPart { id: string; part_type: 'text' | 'source' | 'tool_result' | 'artifact' | 'action_proposal' | 'approval' | 'error'; content: Record<string, unknown>; sort_order: number }
export interface AssistantRoutingAttempt { provider_profile_id?: string | null; model_profile_id?: string | null; provider_display_name?: string | null; model_display_name?: string | null; outcome: 'succeeded' | 'rate_limited' | 'provider_unavailable' | 'connection_error' | 'failed' }
export interface AssistantRouting { provider_display_name?: string | null; model_display_name?: string | null; route_mode: 'auto' | 'manual'; selection_reason: string; attempts: AssistantRoutingAttempt[] }
export type AssistantRunStatus = 'created' | 'queued' | 'running' | 'waiting_input' | 'waiting_approval' | 'waiting_external' | 'retry_scheduled' | 'cancel_requested' | 'completed' | 'failed' | 'cancelled';
export interface AssistantTurn { id: string; thread_id: string; work_id?: string | null; conversation_id?: string | null; role: 'user' | 'assistant'; status: string; model_id?: string | null; error?: string | null; created_at: number; completed_at?: number | null; parts: AssistantPart[]; routing?: AssistantRouting | null; run_id?: string | null; run_status?: AssistantRunStatus | null; remote_compute_stop_proven?: boolean }
export interface AssistantRun { id: string; assistant_turn_id: string; user_turn_id?: string | null; thread_id: string; work_id?: string | null; conversation_id?: string | null; status: AssistantRunStatus; route_mode: 'auto' | 'manual'; attempt_count: number; created_at: number; updated_at: number; started_at?: number | null; completed_at?: number | null; cancel_requested_at?: number | null; retry_at?: number | null; error_code?: string | null }
export interface AssistantThread { id: string; title: string; work_id?: string | null; conversation_id?: string | null; status: 'active' | 'archived'; created_at: number; updated_at: number }
export interface AssistantHistoryItem extends Omit<AssistantThread, 'status'> { status: 'active' | 'completed' | 'failed' | 'archived'; pinned_at?: number | null; message_count?: number }
export interface AssistantHistoryPage { items: AssistantHistoryItem[]; next_cursor: string | null; has_more: boolean }
export interface AssistantContextManifest {
  work_id?: string | null; conversation_id?: string | null; plan_step_id?: string | null; turn_id?: string | null; package_id?: string | null;
  memory_context_mode?: 'off' | 'suggest_only' | 'active_work_memory'; auto_learning_enabled?: boolean;
  /** Legacy compatibility only. UI must not infer provenance from this group. */ included: Array<Record<string, unknown>>;
  accessible?: Array<Record<string, unknown>>; retrieved?: Array<Record<string, unknown>>; used?: Array<Record<string, unknown>>; targeted?: Array<Record<string, unknown>>;
  excluded: Array<Record<string, unknown>>; byte_limit: number; byte_count: number; version?: string | null; generated_at?: number | null; from_message_id?: string | null; through_message_id?: string | null; memory_hub_auto_injected: boolean;
}

export const listAssistantThreads = (includeArchived = false) => apiFetch<AssistantThread[]>(
  `/api/assistant/threads${includeArchived ? '?include_archived=true' : ''}`,
);
/** Creates only a global Assistant thread. Work threads must use the resolver below. */
export const createAssistantThread = (title: string) => apiFetch<AssistantThread>('/api/assistant/threads', { method: 'POST', body: JSON.stringify({ title }) });
export const resolveWorkConversationAssistantThread = (workId: string, conversationId: string) => apiFetch<AssistantThread>(
  `/api/assistant/works/${encodeURIComponent(workId)}/conversations/${encodeURIComponent(conversationId)}/assistant-thread`,
  { method: 'POST' },
);
export const updateAssistantThread = (threadId: string, changes: { title?: string; archived?: boolean }) =>
  apiFetch<AssistantThread>(`/api/assistant/threads/${threadId}`, { method: 'PATCH', body: JSON.stringify(changes) });
export const getWorkAssistantHistory = (workId: string, options: { cursor?: string | null; limit?: number; q?: string; status?: string; includeArchived?: boolean } = {}) => {
  const query = new URLSearchParams();
  if (options.cursor) query.set('cursor', options.cursor);
  if (options.limit) query.set('limit', String(options.limit));
  if (options.q?.trim()) query.set('q', options.q.trim());
  if (options.status && options.status !== 'all') query.set('status', options.status);
  if (options.includeArchived) query.set('include_archived', 'true');
  const suffix = query.toString();
  return apiFetch<AssistantHistoryPage>(`/api/assistant/works/${encodeURIComponent(workId)}/history${suffix ? `?${suffix}` : ''}`);
};
export const updateWorkAssistantHistory = (workId: string, threadId: string, changes: { pinned?: boolean; archived?: boolean }) =>
  apiFetch<AssistantHistoryItem>(`/api/assistant/works/${encodeURIComponent(workId)}/history/${encodeURIComponent(threadId)}`, { method: 'PATCH', body: JSON.stringify(changes) });
export const getAssistantTurns = (threadId: string) => apiFetch<AssistantTurn[]>(`/api/assistant/threads/${threadId}/turns`);
export const getAssistantRun = (runId: string) => apiFetch<AssistantRun>(`/api/assistant/runs/${encodeURIComponent(runId)}`);
export interface AssistantRouteChoice { routeMode?: 'auto' | 'manual'; modelProfileId?: string | null; planStepId?: string | null }
export const createAssistantTurn = (threadId: string, prompt: string, workId?: string | null, conversationId?: string | null, attachmentArtifactIds: string[] = [], route: AssistantRouteChoice = {}) => apiFetch<AssistantTurn[]>(`/api/assistant/threads/${threadId}/turns`, { method: 'POST', body: JSON.stringify({ prompt, work_id: workId, conversation_id: conversationId, plan_step_id: route.planStepId ?? null, attachment_artifact_ids: attachmentArtifactIds, route_mode: route.routeMode ?? 'auto', model_profile_id: route.modelProfileId ?? null }) });
export const createAssistantRun = (threadId: string, prompt: string, workId?: string | null, conversationId?: string | null, attachmentArtifactIds: string[] = [], route: AssistantRouteChoice = {}) => apiFetch<AssistantTurn[]>(`/api/assistant/threads/${threadId}/runs`, { method: 'POST', body: JSON.stringify({ prompt, work_id: workId, conversation_id: conversationId, plan_step_id: route.planStepId ?? null, attachment_artifact_ids: attachmentArtifactIds, route_mode: route.routeMode ?? 'auto', model_profile_id: route.modelProfileId ?? null }) });
export const retryAssistantTurn = (turnId: string, mode: 'same_model' | 'auto' = 'same_model') => apiFetch<AssistantTurn>(`/api/assistant/turns/${turnId}/retry`, { method: 'POST', body: JSON.stringify({ mode }) });
export const cancelAssistantTurn = (turnId: string) => apiFetch<AssistantTurn>(`/api/assistant/turns/${turnId}/cancel`, { method: 'POST' });
export const getAssistantContextManifest = (workId?: string | null, conversationId?: string | null, planStepId?: string | null, signal?: AbortSignal, turnId?: string | null, packageId?: string | null) => apiFetch<AssistantContextManifest>(`/api/assistant/context-manifest?${new URLSearchParams({ ...(workId ? { work_id: workId } : {}), ...(conversationId ? { conversation_id: conversationId } : {}), ...(planStepId ? { plan_step_id: planStepId } : {}), ...(turnId ? { turn_id: turnId } : {}), ...(packageId ? { package_id: packageId } : {}) }).toString()}`, { signal });
export const assistantThreadStreamUrl = (threadId: string) => `${BASE_URL}/api/assistant/threads/${threadId}/stream`;
