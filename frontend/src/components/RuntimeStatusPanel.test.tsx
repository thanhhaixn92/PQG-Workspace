import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StrictMode } from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { RuntimeStatusPanel } from './RuntimeStatusPanel';
import * as runtimeApi from '../api/runtime';
import * as n8nApi from '../api/n8n';
import { useHermesStore } from '../store/store';

vi.mock('../api/runtime', () => ({
  fetchRuntimeStatus: vi.fn(),
  runRuntimeSmoke: vi.fn(),
}));

vi.mock('../api/n8n', () => ({
  fetchN8nStatus: vi.fn(),
  testN8nEcho: vi.fn(),
}));

vi.mock('../api/events', () => ({
  subscribeToSessionEvents: vi.fn(),
}));

const baseStatus = {
  backend: 'ok' as const,
  db: { status: 'ok' as const },
  timestamp: 1_800_000_000,
};

describe('RuntimeStatusPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ activeSessionId: 's1' });
    vi.mocked(n8nApi.fetchN8nStatus).mockResolvedValue({
      configured: false,
      webhook_base_url: 'http://localhost:5678/webhook/',
      allowed_workflows: ['echo'],
      guidance: 'n8n chưa cấu hình secret; bỏ qua nếu chưa dùng tự động hóa.',
    });
  });

  it('hiển thị hướng dẫn khi Hermes chưa cấu hình', async () => {
    vi.mocked(runtimeApi.fetchRuntimeStatus).mockResolvedValue({
      ...baseStatus,
      hermes: {
        status: 'not_configured',
        guidance: 'Chưa cấu hình HERMES_EXECUTABLE_PATH trong backend/.env.',
      },
    });

    render(<RuntimeStatusPanel />);

    expect(await screen.findByText('Kiểm tra hệ thống')).toBeDefined();
    expect(screen.getByText(/HERMES_EXECUTABLE_PATH/)).toBeDefined();
    expect(screen.getByText('Cần cấu hình')).toBeDefined();
    expect(screen.getByText('Bỏ qua')).toBeDefined();
    expect(screen.getByText(/Workflow cho phép: echo/)).toBeDefined();
    expect(screen.getByText(/Lần cuối:/)).toBeDefined();
  });

  it('hiển thị mock dev mode khi bật HERMES_DEV_MOCK', async () => {
    vi.mocked(runtimeApi.fetchRuntimeStatus).mockResolvedValue({
      ...baseStatus,
      hermes: {
        status: 'mock',
        guidance: 'Đang dùng Hermes dev mock để kiểm tra chat end-to-end.',
      },
    });

    render(<RuntimeStatusPanel />);

    expect(await screen.findByText('Đang dùng mock')).toBeDefined();
    expect(screen.getAllByText('Sẵn sàng').length).toBeGreaterThan(1);
    expect(screen.getByText(/tắt HERMES_DEV_MOCK/)).toBeDefined();
    expect(screen.queryByText(/hermes-acp\.exe/)).toBeNull();
    expect(screen.getByText('Chẩn đoán kỹ thuật')).toBeDefined();
  });

  it('cảnh báo nguyên nhân thường gặp khi Hermes thật phản hồi chậm', async () => {
    vi.mocked(runtimeApi.fetchRuntimeStatus).mockResolvedValue({
      ...baseStatus,
      hermes: {
        status: 'ready',
        guidance: 'Hermes executable đã sẵn sàng.',
      },
    });

    render(<RuntimeStatusPanel />);

    expect(await screen.findByText(/model\/provider chậm/)).toBeDefined();
    expect(screen.getByText(/Runtime tương thích đã sẵn sàng/)).toBeDefined();
  });

  it('chạy kiểm tra nhanh và hiển thị từng trạng thái', async () => {
    vi.mocked(runtimeApi.fetchRuntimeStatus).mockResolvedValue({
      ...baseStatus,
      hermes: {
        status: 'ready',
        guidance: 'Hermes executable đã sẵn sàng.',
      },
    });
    vi.mocked(runtimeApi.runRuntimeSmoke).mockResolvedValue({
      timestamp: 1_800_000_001,
      checks: [
        { key: 'backend', label: 'Backend', status: 'ready', detail: 'FastAPI đang phản hồi.' },
        { key: 'n8n', label: 'n8n optional', status: 'skipped', detail: 'Chưa cấu hình n8n secret.' },
      ],
    });

    render(<RuntimeStatusPanel />);

    fireEvent.click(await screen.findByText('Chạy kiểm tra nhanh'));

    await waitFor(() => {
      expect(runtimeApi.runRuntimeSmoke).toHaveBeenCalledWith('s1');
      expect(screen.getByText('n8n optional')).toBeDefined();
      expect(screen.getAllByText('Bỏ qua').length).toBeGreaterThan(0);
      expect(screen.getByText('FastAPI đang phản hồi.')).toBeDefined();
    });
  });

  it('test workflow echo n8n khi đã cấu hình và có allowlist', async () => {
    vi.mocked(runtimeApi.fetchRuntimeStatus).mockResolvedValue({
      ...baseStatus,
      hermes: {
        status: 'ready',
        guidance: 'Hermes executable đã sẵn sàng.',
      },
    });
    vi.mocked(n8nApi.fetchN8nStatus).mockResolvedValue({
      configured: true,
      webhook_base_url: 'http://localhost:5678/webhook/',
      allowed_workflows: ['echo'],
      guidance: 'n8n đã cấu hình.',
    });
    vi.mocked(n8nApi.testN8nEcho).mockResolvedValue({
      status: 'sent',
      workflow_name: 'echo',
      message: 'Đã gọi workflow n8n echo.',
      response_status: 200,
    });

    render(<RuntimeStatusPanel />);

    fireEvent.click(await screen.findByText('Test echo n8n'));

    await waitFor(() => {
      expect(n8nApi.testN8nEcho).toHaveBeenCalledWith('s1');
      expect(screen.getByText('Đã gọi workflow n8n echo.')).toBeDefined();
    });
  });

  it('hiển thị lỗi tải trạng thái hệ thống', async () => {
    vi.mocked(runtimeApi.fetchRuntimeStatus).mockRejectedValue(new Error('offline'));

    render(<RuntimeStatusPanel />);

    await waitFor(() => {
      expect(screen.getByText('Không tải được tình trạng hệ thống.')).toBeDefined();
    });
  });

  it('bỏ qua lỗi của request cũ sau khi request mới tải thành công', async () => {
    let rejectFirst: (error: Error) => void = () => {};
    const first = new Promise<runtimeApi.RuntimeStatus>((_resolve, reject) => { rejectFirst = reject; });
    vi.mocked(runtimeApi.fetchRuntimeStatus)
      .mockReturnValueOnce(first)
      .mockResolvedValueOnce({
        ...baseStatus,
        hermes: { status: 'mock', guidance: 'mock' },
      });

    render(<StrictMode><RuntimeStatusPanel /></StrictMode>);
    await screen.findByText('Đang dùng mock');
    rejectFirst(new Error('late failure'));

    await waitFor(() => {
      expect(screen.queryByText('Không tải được tình trạng hệ thống.')).toBeNull();
    });
  });
});
