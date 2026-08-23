import { apiFetch } from './client';

export interface ContextPreviewItem {
  id: string;
  label: string;
  selected: boolean;
  bytes: number;
  reason: string;
}

export interface ContextPreviewGroup {
  item_limit: number;
  byte_limit: number;
  selected_bytes: number;
  items: ContextPreviewItem[];
}

export interface ContextPreview {
  session_id: string;
  skills: ContextPreviewGroup;
  memories: ContextPreviewGroup;
  memory_hub_injected: boolean;
}

export const getContextPreview = (sessionId: string): Promise<ContextPreview> =>
  apiFetch(`/api/context-preview?session_id=${encodeURIComponent(sessionId)}`);
