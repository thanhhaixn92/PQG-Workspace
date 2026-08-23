import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createLocalDataBackup, getLocalDataSummary, getLocalDataBackups } from '../api/localData';
import { LocalDataPanel } from './LocalDataPanel';

vi.mock('../api/localData', () => ({
  getLocalDataSummary: vi.fn(),
  getLocalDataBackups: vi.fn(),
  getRestoreReadiness: vi.fn(),
  createLocalDataBackup: vi.fn(),
}));

describe('LocalDataPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getLocalDataSummary).mockResolvedValue({
      db_path: 'C:\\Users\\dtron\\Documents\\Hermes\\backend\\app.db',
      db_size_bytes: 2048,
      sessions_count: 4,
      active_sessions_count: 3,
      messages_count: 12,
      task_runs_count: 5,
      audit_events_count: 30,
    });
    vi.mocked(getLocalDataBackups).mockResolvedValue([]);
  });

  it('hiển thị thống kê dữ liệu cục bộ', async () => {
    render(<LocalDataPanel />);

    expect(await screen.findByText('Dữ liệu cục bộ')).toBeDefined();
    expect(screen.getByText('3/4')).toBeDefined();
    expect(screen.getByText('12')).toBeDefined();
    expect(screen.getByText('5')).toBeDefined();
    expect(screen.getByText('30')).toBeDefined();
    expect(screen.getByText('2.0 KB')).toBeDefined();
  });

  it('tạo backup mà không hiển thị đường dẫn kỹ thuật', async () => {
    vi.mocked(createLocalDataBackup).mockResolvedValue({
      backup_path: 'C:\\Users\\dtron\\Documents\\Hermes\\backend\\backups\\app-20260702-120000.db',
      created_at: 1_800_000_000,
      sha256: 'a'.repeat(64),
      manifest_name: 'app-20260702-120000.db.manifest.json',
    });
    render(<LocalDataPanel />);

    fireEvent.click(await screen.findByText('Tạo backup DB'));

    await waitFor(() => {
      expect(createLocalDataBackup).toHaveBeenCalled();
      expect(screen.getByText(/Đã tạo bản sao lưu lúc/)).toBeDefined();
      expect(screen.queryByText(/app-20260702-120000.db/)).toBeNull();
    });
  });
});
