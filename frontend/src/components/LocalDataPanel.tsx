import React, { useEffect, useState } from 'react';
import { Database, Download, RefreshCw } from 'lucide-react';
import { createLocalDataBackup, getLocalDataBackups, getLocalDataSummary, getRestoreReadiness } from '../api/localData';
import type { LocalDataBackup, LocalDataBackupInfo, LocalDataSummary, RestoreReadiness } from '../api/localData';

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
  const [backups, setBackups] = useState<LocalDataBackupInfo[]>([]);
  const [readiness, setReadiness] = useState<RestoreReadiness | null>(null);
  const [loading, setLoading] = useState(false);
  const [backupLoading, setBackupLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = async () => {
    setLoading(true);
    try {
      setError(null);
      setSummary(await getLocalDataSummary());
      setBackups(await getLocalDataBackups());
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

  const inspectBackup = async (name: string) => {
    try {
      setError(null);
      setReadiness(await getRestoreReadiness(name));
    } catch {
      setError('Không kiểm tra được khả năng khôi phục của backup này.');
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
              <span>Công việc</span>
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

          <div className="runtime-guidance">Dữ liệu được lưu trên máy này. Vị trí kỹ thuật không hiển thị trong giao diện thường dùng.</div>

          <button className="primary-button" onClick={runBackup} disabled={backupLoading}>
            {backupLoading ? <RefreshCw size={16} className="spin" /> : <Download size={16} />}
            Tạo backup DB
          </button>

          {backup && (
            <div className="runtime-guidance" role="status">
              Đã tạo bản sao lưu lúc {formatTime(backup.created_at)}. Bản sao chỉ gồm dữ liệu ứng dụng, không bao gồm credential hoặc thư mục ngoài vùng quản lý.
            </div>
          )}

          <div className="backup-list">
            <strong>Backup gần đây</strong>
            {backups.length === 0 && <div className="runtime-guidance">Chưa có backup nào.</div>}
            {backups.map(item => (
              <div className="runtime-row" key={item.name}>
                <span>{formatTime(item.created_at)} · {formatBytes(item.size_bytes)}</span>
                <button className="btn-secondary compact-button" onClick={() => void inspectBackup(item.name)} disabled={item.integrity_status !== 'ok' || item.manifest_status !== 'ok'}>
                  {item.integrity_status === 'ok' && item.manifest_status === 'ok' ? 'Kiểm tra sẵn sàng' : 'Thiếu xác minh'}
                </button>
              </div>
            ))}
          </div>
          {readiness && <div className="runtime-guidance" role="status">Backup DB hợp lệ, có {readiness.schema_versions} phiên bản schema. Chưa bao gồm workspace ngoài vùng quản lý hay credential; khôi phục chỉ thực hiện bằng công cụ maintenance offline.</div>}
        </div>
      ) : (
        !error && <div className="empty-state">Đang tải dữ liệu cục bộ...</div>
      )}
    </div>
  );
};
