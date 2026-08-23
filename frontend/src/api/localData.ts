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
  sha256: string;
  manifest_name: string;
}

export interface LocalDataBackupInfo {
  name: string;
  created_at: number;
  size_bytes: number;
  integrity_status: 'ok' | 'invalid';
  sha256: string | null;
  manifest_status: 'ok' | 'missing' | 'invalid';
  coverage: 'database_only';
}

export interface RestoreReadiness extends LocalDataBackupInfo {
  schema_versions: number;
  managed_workspace_coverage: 'not_included';
}

export async function getLocalDataSummary(): Promise<LocalDataSummary> {
  return apiFetch<LocalDataSummary>('/api/local-data/summary');
}

export async function createLocalDataBackup(): Promise<LocalDataBackup> {
  return apiFetch<LocalDataBackup>('/api/local-data/backup', {
    method: 'POST',
  });
}

export const getLocalDataBackups = (): Promise<LocalDataBackupInfo[]> => apiFetch('/api/local-data/backups');

export const getRestoreReadiness = (name: string): Promise<RestoreReadiness> =>
  apiFetch(`/api/local-data/backups/${encodeURIComponent(name)}/restore-readiness`);
