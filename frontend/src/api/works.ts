import { apiFetch } from './client';
import type { Session, TaskRun } from '../store/store';
import type { Artifact } from './artifacts';

export type WorkStatus = 'not_started' | 'in_progress' | 'paused' | 'waiting_confirmation' | 'completed';
export type PlanStepStatus = 'not_started' | 'in_progress' | 'blocked' | 'completed';

export interface Work extends Session {
  work_status: WorkStatus;
  progress_percent: number;
  completion_proposed_at?: number | null;
  completed_at?: number | null;
  progress_source?: 'stored' | 'plan_steps';
  next_step?: WorkPlanStep | null;
  blocked_step_count?: number;
  pending_approval_count?: number;
}

export interface Conversation {
  id: string;
  session_id: string;
  title: string;
  purpose?: string | null;
  status: 'active' | 'archived';
  created_at: number;
  updated_at: number;
  last_opened_at?: number | null;
  message_count: number;
  latest_task_status?: string | null;
}

export interface WorkPlanStep {
  id: string; phase_id: string; session_id: string; title: string;
  description?: string | null; result?: string | null; sort_order: number;
  status: PlanStepStatus; source: 'user' | 'hermes'; created_at: number; updated_at: number;
}
export interface WorkPlanPhase {
  id: string; session_id: string; title: string; sort_order: number;
  status: PlanStepStatus; source: 'user' | 'hermes'; created_at: number; updated_at: number;
  steps: WorkPlanStep[];
}
export interface ContextSummary {
  id: string; session_id: string; conversation_id?: string | null; content: string;
  from_message_id?: string | null; through_message_id?: string | null; version: number; created_at: number;
}
export interface WorkDashboard {
  work: Work; next_step?: WorkPlanStep | null; conversations: Conversation[];
  phases: WorkPlanPhase[]; pending_approval_count: number; artifacts: Artifact[];
  context_summary?: ContextSummary | null;
  capabilities_used: Array<{ kind: string; name: string; used_at: number }>;
  progress_source?: 'stored' | 'plan_steps';
}
export type MemoryContextMode = 'off' | 'suggest_only' | 'active_work_memory';
export interface WorkMemoryContext {
  work_id: string; plan_step_id: string; scope_id?: string | null;
  context_mode: MemoryContextMode; auto_learning_enabled: boolean;
  active_memory_count: number; excluded: Array<Record<string, unknown>>;
}
export interface WorkMessage { id: string; session_id: string; task_id?: string | null; role: 'user' | 'assistant'; content: string; created_at: number; conversation_id?: string | null }
export interface WorkMessagePage { messages: WorkMessage[]; has_more: boolean }

export const WORK_DRAFT_VERSION = 1;
export const workDraftKey = (workId: string, conversationId: string) => `dirap:work-draft:v${WORK_DRAFT_VERSION}:${workId}:${conversationId}`;
export const readWorkDraft = (storage: Pick<Storage, 'getItem'>, workId: string, conversationId: string) => {
  try {
    const raw = storage.getItem(workDraftKey(workId, conversationId));
    if (!raw) return '';
    const value = JSON.parse(raw) as { version?: number; prompt?: unknown };
    return value.version === WORK_DRAFT_VERSION && typeof value.prompt === 'string' ? value.prompt : '';
  } catch { return ''; }
};
export const writeWorkDraft = (storage: Pick<Storage, 'setItem' | 'removeItem'>, workId: string, conversationId: string, prompt: string) => {
  const key = workDraftKey(workId, conversationId);
  if (!prompt) storage.removeItem(key);
  else storage.setItem(key, JSON.stringify({ version: WORK_DRAFT_VERSION, prompt }));
};

export const getWorkDashboard = (workId: string) => apiFetch<WorkDashboard>(`/api/works/${workId}/dashboard`);
export const listConversations = (workId: string) => apiFetch<Conversation[]>(`/api/works/${workId}/conversations`);
export const createConversation = (workId: string, title: string, purpose?: string) => apiFetch<Conversation>(`/api/works/${workId}/conversations`, { method: 'POST', body: JSON.stringify({ title, purpose }) });
export const updateConversation = (workId: string, conversationId: string, updates: { title?: string; purpose?: string; archived?: boolean }) => apiFetch<Conversation>(`/api/works/${workId}/conversations/${conversationId}`, { method: 'PATCH', body: JSON.stringify(updates) });
export const getConversationMessages = (workId: string, conversationId: string, limit = 100, beforeId?: string) => apiFetch<WorkMessagePage>(`/api/works/${workId}/conversations/${conversationId}/messages?limit=${limit}${beforeId ? `&before_id=${encodeURIComponent(beforeId)}` : ''}`);
export const submitConversationPrompt = (workId: string, conversationId: string, prompt: string) => apiFetch<TaskRun>(`/api/works/${workId}/conversations/${conversationId}/prompt`, { method: 'POST', body: JSON.stringify({ prompt }) });
export const createPlanPhase = (workId: string, title: string) => apiFetch<WorkPlanPhase>(`/api/works/${workId}/plan/phases`, { method: 'POST', body: JSON.stringify({ title }) });
export const updatePlanPhase = (workId: string, phaseId: string, updates: Partial<Pick<WorkPlanPhase, 'title' | 'status' | 'sort_order'>>) => apiFetch<WorkPlanPhase>(`/api/works/${workId}/plan/phases/${phaseId}`, { method: 'PATCH', body: JSON.stringify(updates) });
export const createPlanStep = (workId: string, phaseId: string, title: string, description?: string) => apiFetch<WorkPlanStep>(`/api/works/${workId}/plan/steps`, { method: 'POST', body: JSON.stringify({ phase_id: phaseId, title, description }) });
export const updatePlanStep = (workId: string, stepId: string, updates: Partial<Pick<WorkPlanStep, 'title' | 'description' | 'result' | 'status' | 'sort_order'>>) => apiFetch<WorkPlanStep>(`/api/works/${workId}/plan/steps/${stepId}`, { method: 'PATCH', body: JSON.stringify(updates) });
export const getPlan = (workId: string) => apiFetch<WorkPlanPhase[]>(`/api/works/${workId}/plan`);
export const getWorkMemoryContext = (workId: string, stepId: string) => apiFetch<WorkMemoryContext>(`/api/works/${workId}/plan/steps/${stepId}/memory-context`);
export const updateWorkMemoryContext = (workId: string, stepId: string, updates: Pick<WorkMemoryContext, 'context_mode' | 'auto_learning_enabled'>) => apiFetch<WorkMemoryContext>(`/api/works/${workId}/plan/steps/${stepId}/memory-context`, { method: 'PUT', body: JSON.stringify(updates) });
export const updateWork = (workId: string, updates: Partial<Pick<Work, 'title' | 'goal' | 'data_scope' | 'work_status' | 'progress_percent'>>) => apiFetch<Work>(`/api/works/${workId}`, { method: 'PATCH', body: JSON.stringify(updates) });
export const confirmWorkCompletion = (workId: string) => apiFetch<{ work: Work }>(`/api/works/${workId}/confirm-completion`, { method: 'POST' });
export const reopenWork = (workId: string) => apiFetch<{ work: Work }>(`/api/works/${workId}/reopen`, { method: 'POST' });
