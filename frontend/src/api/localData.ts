import { apiFetch } from './client';

export interface LocalDataSummary {
  db_path: string;
  db_size_bytes: number;
  sessions_count: number;
  active_sessions_count: number;
  messages_count: number;
  task_runs_count: number;
  audit_events_count: number;
}

export interface LocalDataBackup {
  backup_path: string;
  created_at: number;
}

export async function getLocalDataSummary(): Promise<LocalDataSummary> {
  return apiFetch<LocalDataSummary>('/api/local-data/summary');
}

export async function createLocalDataBackup(): Promise<LocalDataBackup> {
  return apiFetch<LocalDataBackup>('/api/local-data/backup', {
    method: 'POST',
  });
}
