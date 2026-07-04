import React, { useEffect, useMemo, useState } from 'react';
import { Moon, RefreshCw, SearchCheck, Sun, Workflow } from 'lucide-react';
import { fetchRuntimeStatus, runRuntimeSmoke } from '../api/runtime';
import type { RuntimeSmokeCheck, RuntimeStatus } from '../api/runtime';
import { fetchN8nStatus, testN8nEcho, type N8nStatus, type N8nTestEchoResponse } from '../api/n8n';
import { useHermesStore } from '../store/store';
import { subscribeToSessionEvents } from '../api/events';

function hermesLabel(status: RuntimeStatus['hermes']['status']): string {
  switch (status) {
    case 'ready':
      return 'Sẵn sàng';
    case 'mock':
      return 'Đang dùng mock';
    case 'missing':
      return 'Thiếu executable';
    case 'not_configured':
      return 'Cần cấu hình';
    case 'auth_unknown':
      return 'Cần đăng nhập Hermes';
    case 'auth_expired':
      return 'Cần đăng nhập lại Hermes';
  }
}

function smokeLabel(status: RuntimeSmokeCheck['status']): string {
  switch (status) {
    case 'ready':
      return 'Sẵn sàng';
    case 'needs_config':
      return 'Cần cấu hình';
    case 'error':
      return 'Lỗi';
    case 'skipped':
      return 'Bỏ qua';
  }
}

function statusClass(kind: 'ok' | 'warn' | 'error' | 'skip'): string {
  return `runtime-pill ${kind}`;
}

function smokeClass(status: RuntimeSmokeCheck['status']): string {
  if (status === 'ready') return statusClass('ok');
  if (status === 'needs_config') return statusClass('warn');
  if (status === 'error') return statusClass('error');
  return statusClass('skip');
}

function checkedAt(timestamp?: number): string {
  if (!timestamp) return '';
  return new Date(timestamp * 1000).toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function hermesFix(status: RuntimeStatus): string {
  if (status.hermes.status === 'ready') {
    return 'Có thể gửi prompt thật cho Hermes. Nếu phản hồi lâu hơn 30 giây, thường là do model/provider chậm, phiên dài hoặc Hermes đang chờ phê duyệt quyền.';
  }
  if (status.hermes.status === 'mock') {
    return 'Đang chạy mock để thử UI. Khi muốn dùng Hermes thật, tắt HERMES_DEV_MOCK và đặt HERMES_EXECUTABLE_PATH.';
  }
  if (status.hermes.status === 'missing') {
    return 'Kiểm tra lại đường dẫn HERMES_EXECUTABLE_PATH trong backend/.env hoặc chạy lại hermes setup.';
  }
  if (status.hermes.status === 'auth_unknown') {
    return 'Chạy hermes auth hoặc hermes doctor trong PowerShell. Nếu Hermes đã đăng nhập nhưng app vẫn chưa nhận ra, đặt HERMES_AUTH_READY=1 trong backend/.env.';
  }
  if (status.hermes.status === 'auth_expired') {
    return 'Token Hermes không còn hợp lệ. Chạy hermes auth trong PowerShell để đăng nhập lại.';
  }
  return 'Tạo backend/.env từ .env.example, sau đó cấu hình HERMES_EXECUTABLE_PATH hoặc bật HERMES_DEV_MOCK=1 để thử trước.';
}

export const RuntimeStatusPanel: React.FC = () => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const theme = useHermesStore(state => state.theme);
  const toggleTheme = useHermesStore(state => state.toggleTheme);
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [smokeChecks, setSmokeChecks] = useState<RuntimeSmokeCheck[]>([]);
  const [n8nStatus, setN8nStatus] = useState<N8nStatus | null>(null);
  const [n8nResult, setN8nResult] = useState<N8nTestEchoResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [smokeError, setSmokeError] = useState<string | null>(null);
  const [n8nError, setN8nError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [smokeLoading, setSmokeLoading] = useState(false);
  const [n8nLoading, setN8nLoading] = useState(false);
  const [smokeTimestamp, setSmokeTimestamp] = useState<number | null>(null);

  const loadStatus = async () => {
    setLoading(true);
    try {
      setError(null);
      const [runtime, n8n] = await Promise.all([
        fetchRuntimeStatus(),
        fetchN8nStatus().catch(() => null),
      ]);
      setStatus(runtime);
      setN8nStatus(n8n);
    } catch {
      setError('Không tải được tình trạng hệ thống.');
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const runSmoke = async () => {
    setSmokeLoading(true);
    try {
      setSmokeError(null);
      const result = await runRuntimeSmoke(activeSessionId);
      setSmokeChecks(result.checks);
      setSmokeTimestamp(result.timestamp);
    } catch {
      setSmokeChecks([]);
      setSmokeError('Không chạy được kiểm tra nhanh.');
    } finally {
      setSmokeLoading(false);
    }
  };

  const runN8nEcho = async () => {
    setN8nLoading(true);
    try {
      setN8nError(null);
      if (activeSessionId) {
        subscribeToSessionEvents(activeSessionId);
      }
      setN8nResult(await testN8nEcho(activeSessionId));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Không gọi được workflow n8n echo.';
      setN8nResult(null);
      setN8nError(message);
    } finally {
      setN8nLoading(false);
    }
  };

  useEffect(() => {
    void loadStatus();
  }, []);

  const hermesKind = useMemo(() => {
    if (status?.hermes.status === 'ready' || status?.hermes.status === 'mock') return 'ok';
    if (status?.hermes.status === 'missing') return 'error';
    return 'warn';
  }, [status?.hermes.status]);

  const canTestN8nEcho = Boolean(n8nStatus?.configured && n8nStatus.allowed_workflows.includes('echo'));

  return (
    <div className="runtime-status-panel">
      <div className="runtime-status-header">
        <div>
          <strong>Kiểm tra hệ thống</strong>
          {status && <small> Lần cuối: {checkedAt(status.timestamp)}</small>}
        </div>
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <button title={theme === 'dark' ? 'Chuyển sang giao diện sáng' : 'Chuyển sang giao diện tối'} onClick={toggleTheme}>
            {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
          </button>
          <button title="Làm mới tình trạng hệ thống" onClick={loadStatus} disabled={loading}>
            <RefreshCw size={13} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {error && <div className="runtime-guidance">{error}</div>}

      {status && (
        <div className="runtime-status-list">
          <div className="runtime-row">
            <span>Backend</span>
            <span className={statusClass('ok')}>Sẵn sàng</span>
          </div>
          <div className="runtime-guidance">API đang phản hồi tại backend local.</div>

          <div className="runtime-row">
            <span>Cơ sở dữ liệu</span>
            <span className={statusClass(status.db.status === 'ok' ? 'ok' : 'error')}>
              {status.db.status === 'ok' ? 'Sẵn sàng' : 'Lỗi'}
            </span>
          </div>
          <div className="runtime-guidance">DB: {status.db.path}</div>

          <div className="runtime-row">
            <span>File .env</span>
            <span className={statusClass(status.environment.env_file_exists ? 'ok' : 'warn')}>
              {status.environment.env_file_exists ? 'Đã có' : 'Cần tạo'}
            </span>
          </div>
          {!status.environment.env_file_exists && (
            <div className="runtime-guidance">Tạo bằng cách copy backend/.env.example thành backend/.env.</div>
          )}

          <div className="runtime-row">
            <span>Hermes</span>
            <span className={statusClass(hermesKind)}>{hermesLabel(status.hermes.status)}</span>
          </div>
          <div className="runtime-guidance">
            {status.hermes.guidance}
            <br />
            {hermesFix(status)}
            <br />
            Lệnh: {status.hermes.executable_path || '(chưa cấu hình)'} {status.hermes.args.join(' ')}
          </div>

          <div className="runtime-row">
            <span>SSE stream</span>
            <span className={statusClass('ok')}>Sẵn sàng</span>
          </div>

          <div className="runtime-row">
            <span>File workspace</span>
            <span className={statusClass('ok')}>Sẵn sàng</span>
          </div>

          <div className="runtime-row">
            <span>Memory/Approval</span>
            <span className={statusClass('ok')}>Sẵn sàng</span>
          </div>

          <div className="runtime-row">
            <span>n8n</span>
            <span className={statusClass(status.n8n.configured ? 'ok' : 'skip')}>
              {status.n8n.configured ? 'Sẵn sàng' : 'Bỏ qua'}
            </span>
          </div>
          <div className="runtime-guidance">{status.n8n.guidance}</div>
          {n8nStatus && n8nStatus.allowed_workflows.length > 0 && (
            <div className="runtime-guidance">
              Workflow cho phép: {n8nStatus.allowed_workflows.join(', ')}
            </div>
          )}
          {canTestN8nEcho && (
            <div className="runtime-actions">
              <button className="secondary-button" onClick={runN8nEcho} disabled={n8nLoading || !activeSessionId}>
                {n8nLoading ? <RefreshCw size={14} className="spin" /> : <Workflow size={14} />}
                Test echo n8n
              </button>
              {!activeSessionId && <div className="runtime-guidance">Chọn một phiên trước khi test n8n để có thể phê duyệt.</div>}
            </div>
          )}
          {n8nResult && <div className="runtime-guidance">{n8nResult.message}</div>}
          {n8nError && <div className="runtime-guidance">{n8nError}</div>}
        </div>
      )}

      <div style={{ marginTop: '0.75rem' }}>
        <button className="secondary-button" onClick={runSmoke} disabled={smokeLoading}>
          {smokeLoading ? <RefreshCw size={14} className="spin" /> : <SearchCheck size={14} />}
          Chạy kiểm tra nhanh
        </button>
      </div>

      {smokeError && <div className="runtime-guidance">{smokeError}</div>}
      {smokeTimestamp && (
        <div className="runtime-guidance">Kết quả kiểm tra: {checkedAt(smokeTimestamp)}</div>
      )}
      {smokeChecks.length > 0 && (
        <div className="runtime-status-list" style={{ marginTop: '0.5rem' }}>
          {smokeChecks.map(check => (
            <React.Fragment key={check.key}>
              <div className="runtime-row">
                <span>{check.label}</span>
                <span className={smokeClass(check.status)}>{smokeLabel(check.status)}</span>
              </div>
              <div className="runtime-guidance">{check.detail}</div>
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
};
