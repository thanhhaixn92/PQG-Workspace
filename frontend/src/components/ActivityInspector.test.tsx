import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getSessionAuditEvents } from '../api/audit';
import { useHermesStore } from '../store/store';
import { ActivityInspector } from './ActivityInspector';

vi.mock('../api/audit', () => ({
  getSessionAuditEvents: vi.fn(),
}));

describe('ActivityInspector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({
      activeSessionId: 's1',
      events: {},
      sessionStatusById: {},
    });
  });

  it('hiển thị audit event đã lưu bằng timeline tóm tắt', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([
      {
        id: 'a1',
        session_id: 's1',
        actor: 'user',
        action: 'prompt.submitted',
        target: null,
        payload_json: JSON.stringify({ task_id: 'task-1', prompt_length: 12 }),
        created_at: 1_800_000_000,
      },
    ]);

    render(<ActivityInspector />);

    await waitFor(() => {
      expect(getSessionAuditEvents).toHaveBeenCalledWith('s1');
      expect(screen.getByText('Nhận yêu cầu')).toBeDefined();
    });
    expect(screen.getByText('Mở tab Kỹ thuật để xem payload, actor và command đầy đủ.')).toBeDefined();
    expect(screen.queryByText('Actor: user')).toBeNull();
    expect(screen.queryByText(/prompt_length/)).toBeNull();
  });

  it('gom audit event theo task_id khi payload có task_id', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([
      {
        id: 'a1',
        session_id: 's1',
        actor: 'user',
        action: 'prompt.submitted',
        target: null,
        payload_json: JSON.stringify({ task_id: 'task-abcdef123' }),
        created_at: 1_800_000_000,
      },
      {
        id: 'a2',
        session_id: 's1',
        actor: 'system',
        action: 'task_run.completed',
        target: null,
        payload_json: JSON.stringify({ task_id: 'task-abcdef123' }),
        created_at: 1_800_000_001,
      },
    ]);

    render(<ActivityInspector />);

    expect(await screen.findByText('Task task-abc')).toBeDefined();
    expect(screen.getByText('Nhận yêu cầu')).toBeDefined();
    expect(screen.getAllByText('Hoàn tất').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('0 công cụ')).toBeDefined();
    expect(screen.getByText('0 phê duyệt')).toBeDefined();
  });

  it('ẩn terminal output mặc định và mở được chi tiết kỹ thuật', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([]);
    useHermesStore.setState({
      activeSessionId: 's1',
      events: {
        s1: [{ id: 'e1', type: 'terminal', output: 'Terminal command blocked by policy' }],
      },
    });

    render(<ActivityInspector />);

    expect(screen.getByText('Terminal')).toBeDefined();
    expect(screen.getByText('Đã nhận output terminal.')).toBeDefined();
    expect(screen.queryByText('Terminal command blocked by policy')).toBeNull();

    fireEvent.click(screen.getByText('Kỹ thuật'));
    expect(screen.getByText('Chi tiết terminal')).toBeDefined();
    expect(screen.getByText('Terminal command blocked by policy')).toBeDefined();
  });

  it('hiển thị tool arguments trong tab kỹ thuật', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([]);
    useHermesStore.setState({
      activeSessionId: 's1',
      events: {
        s1: [{ id: 'tool-1', type: 'tool_call', tool_name: 'read', arguments: { path: 'README.md' } }],
      },
    });

    render(<ActivityInspector />);

    expect(screen.getByText('Công cụ: read')).toBeDefined();
    expect(screen.queryByText(/README.md/)).toBeNull();

    fireEvent.click(screen.getByText('Kỹ thuật'));
    expect(screen.getByText('Tham số công cụ')).toBeDefined();
    expect(screen.getByText(/README.md/)).toBeDefined();
  });

  it('giải thích khi Hermes đang xử lý nhưng chưa có live event', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([]);
    useHermesStore.setState({
      activeSessionId: 's1',
      events: {},
      sessionStatusById: { s1: 'running' },
    });

    render(<ActivityInspector />);

    expect(screen.getByText(/model\/provider đang phản hồi chậm/)).toBeDefined();
  });

  it('hiển thị action phê duyệt bằng tiếng Việt và chỉ lộ raw khi xem kỹ thuật', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([]);
    useHermesStore.setState({
      activeSessionId: 's1',
      events: {
        s1: [
          {
            id: 'approval-1',
            type: 'approval_required',
            approval_id: 'appr-1',
            action: 'hermes.permission',
            target: 'python -c "import docx"',
            risk_level: 'write_internal',
          },
        ],
      },
    });

    render(<ActivityInspector />);

    expect(screen.getByText('Hành động: Cấp quyền cho Hermes')).toBeDefined();
    expect(screen.queryByText('Mã hành động: hermes.permission')).toBeNull();

    fireEvent.click(screen.getByText('Kỹ thuật'));
    expect(screen.getByText('Mã hành động: hermes.permission')).toBeDefined();
    expect(screen.getByText('Mục tiêu: python -c "import docx"')).toBeDefined();
  });

  it('chỉ hiển thị một hint kỹ thuật chung', async () => {
    vi.mocked(getSessionAuditEvents).mockResolvedValue([
      {
        id: 'a1',
        session_id: 's1',
        actor: 'user',
        action: 'prompt.submitted',
        target: null,
        payload_json: JSON.stringify({ task_id: 'task-1' }),
        created_at: 1_800_000_000,
      },
      {
        id: 'a2',
        session_id: 's1',
        actor: 'system',
        action: 'task_run.completed',
        target: null,
        payload_json: JSON.stringify({ task_id: 'task-1' }),
        created_at: 1_800_000_001,
      },
    ]);

    render(<ActivityInspector />);

    await screen.findByText('Nhận yêu cầu');
    expect(screen.getAllByText('Mở tab Kỹ thuật để xem payload, actor và command đầy đủ.')).toHaveLength(1);
  });
});
