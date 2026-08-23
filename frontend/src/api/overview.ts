import type { Session } from '../store/store';
import { apiFetch } from './client';

export interface Overview {
  recent_work: Session[];
  active_work_count: number;
  pending_approval_count: number;
  output_count: number;
  latest_backup_at: number | null;
  blocked_step_count: number;
  waiting_confirmation_count: number;
  attention_items: OverviewAttentionItem[];
  recent_artifacts: OverviewArtifact[];
  latest_work_updates: Session[];
}

export interface OverviewAttentionItem {
  kind: 'blocked_step' | 'approval' | 'completion';
  work_id: string;
  work_title: string;
  title: string;
  reason: string;
  severity: 'warning' | 'attention';
  updated_at: number;
}

export interface OverviewArtifact {
  work_id: string;
  work_title: string;
  title: string;
  kind: string;
  size_bytes: number;
  created_at: number;
}

export const getOverview = (): Promise<Overview> => apiFetch<Overview>('/api/overview');
