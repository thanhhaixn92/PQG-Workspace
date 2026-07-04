import React, { useEffect, useState } from 'react';
import { Database, Download, RefreshCw } from 'lucide-react';
import { createLocalDataBackup, getLocalDataSummary } from '../api/localData';
import type { LocalDataBackup, LocalDataSummary } from '../api/localData';

const formatBytes = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const formatTime = (value: number) =>
  new Date(value * 1000).toLocaleString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });

export const LocalDataPanel: React.FC = () => {
  const [summary, setSummary] = useState<LocalDataSummary | null>(null);
  const [backup, setBackup] = useState<LocalDataBackup | null>(null);
  const [loading, setLoading] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = async () => {
    setLoading(true);
    try {
      setError(null);
      setSummary(await getLocalDataSummary());
    } catch {
      setError('Không tải được thông tin dữ liệu cục bộ.');
    } finally {
      setLoading(false);
    }
  };

  const runBackup = async () => {
    setBackupLoading(true);
    try {
      setError(null);
      const result = await createLocalDataBackup();
      setBackup(result);
      await loadSummary();
    } catch {
      setError('Không tạo được backup DB.');
    } finally {
      setBackupLoading(false);
    }
  };

  useEffect(() => {
    void loadSummary();
  }, []);

  return (
    <div className="list-panel">
      <div className="section-header">
        <div>
          <h3>
            <Database size={18} />
            Dữ liệu cục bộ
          </h3>
          <p>Quản lý thống kê và backup DB local. Không xóa dữ liệu thật.</p>
        </div>
        <button className="icon-button" title="Làm mới" onClick={loadSummary} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}

      {summary ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div className="runtime-status-list">
            <div className="runtime-row">
              <span>Phiên</span>
              <span className="runtime-pill ok">{summary.active_sessions_count}/{summary.sessions_count}</span>
            </div>
            <div className="runtime-row">
              <span>Tin nhắn</span>
              <span className="runtime-pill ok">{summary.messages_count}</span>
            </div>
            <div className="runtime-row">
              <span>Task run</span>
              <span className="runtime-pill ok">{summary.task_runs_count}</span>
            </div>
            <div className="runtime-row">
              <span>Audit event</span>
              <span className="runtime-pill ok">{summary.audit_events_count}</span>
            </div>
            <div className="runtime-row">
              <span>Dung lượng DB</span>
              <span className="runtime-pill ok">{formatBytes(summary.db_size_bytes)}</span>
            </div>
          </div>

          <div className="runtime-guidance">
            DB:
            <br />
            {summary.db_path}
          </div>

          <button className="primary-button" onClick={runBackup} disabled={backupLoading}>
            {backupLoading ? <RefreshCw size={16} className="spin" /> : <Download size={16} />}
            Tạo backup DB
          </button>

          {backup && (
            <div className="runtime-guidance" role="status">
              Đã tạo backup lúc {formatTime(backup.created_at)}
              <br />
              {backup.backup_path}
            </div>
          )}
        </div>
      ) : (
        !error && <div className="empty-state">Đang tải dữ liệu cục bộ...</div>
      )}
    </div>
  );
};
