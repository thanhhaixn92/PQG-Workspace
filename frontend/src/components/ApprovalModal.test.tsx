import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApprovalModal } from './ApprovalModal';
import { useHermesStore } from '../store/store';
import * as approvalsApi from '../api/approvals';

vi.mock('../api/approvals', () => ({
  submitApprovalDecision: vi.fn(),
}));

describe('ApprovalModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(approvalsApi.submitApprovalDecision).mockResolvedValue({
      status: 'recorded',
      approval_id: 'test-123',
      session_id: 'session-1',
      decision: 'deny',
      audit_action: 'approval.denied',
    });
    useHermesStore.setState({
      activeSessionId: 'session-1',
      pendingApproval: null,
      sessionStatusById: {},
      events: {},
      auditRefreshVersion: 0,
    });
  });

  it('không render khi không có phê duyệt đang chờ', () => {
    const { container } = render(<ApprovalModal />);
    expect(container.firstChild).toBeNull();
  });

  it('hiển thị chi tiết tiếng Việt và nút đầy đủ cho ghi trong workspace', () => {
    useHermesStore.setState({
      pendingApproval: {
        approval_id: 'test-1',
        action: 'write_workspace_file',
        target: 'notes.md',
        risk_level: 'write_internal',
        description: 'Hermes muốn ghi file ghi chú.',
      },
    });

    render(<ApprovalModal />);
    expect(screen.getByText('Cần phê duyệt')).toBeDefined();
    expect(screen.getByText('Ghi hoặc sửa tệp')).toBeDefined();
    expect(screen.getByText('notes.md')).toBeDefined();
    expect(screen.getByText('Ghi trong workspace')).toBeDefined();
    expect(screen.getByText('Chỉ cho phép nếu đúng workspace hoặc tệp mong muốn.')).toBeDefined();
    expect(screen.getByText('Cho phép một lần')).toBeDefined();
    expect(screen.getByText('Cho phép trong phiên')).toBeDefined();
    expect(screen.getByText('Từ chối')).toBeDefined();
  });

  it('hiển thị đánh giá nhanh rủi ro thấp cho thao tác đọc', () => {
    useHermesStore.setState({
      pendingApproval: {
        approval_id: 'test-read',
        action: 'read_file',
        target: 'README.md',
        risk_level: 'read',
      },
    });

    render(<ApprovalModal />);
    expect(screen.getByText('Rủi ro thấp, thường có thể cho phép.')).toBeDefined();
  });

  it('ẩn phê duyệt theo phiên cho hành động rủi ro cao', () => {
    useHermesStore.setState({
      pendingApproval: {
        approval_id: 'test-1',
        action: 'run_safe_task',
        target: 'pytest',
        risk_level: 'external_or_destructive',
      },
    });

    render(<ApprovalModal />);
    expect(screen.queryByText('Cho phép trong phiên')).toBeNull();
    expect(screen.getByText('Cho phép một lần')).toBeDefined();
    expect(screen.getByText(/chỉ cho phép nếu bạn hiểu lệnh/)).toBeDefined();
    expect(screen.getByText(/duyệt từng lần/)).toBeDefined();
  });

  it('ẩn phê duyệt theo phiên cho script execution dù backend gửi write_internal', () => {
    useHermesStore.setState({
      pendingApproval: {
        approval_id: 'test-script',
        action: 'hermes.permission',
        target: 'script execution via -e/-c flag: python -c "import docx"',
        risk_level: 'write_internal',
        description: 'Hermes yêu cầu quyền thực hiện script execution via -e/-c flag.',
      },
    });

    render(<ApprovalModal />);
    expect(screen.getByText('Lệnh cục bộ hoặc script, cần duyệt từng lần')).toBeDefined();
    expect(screen.queryByText('Cho phép trong phiên')).toBeNull();
    expect(screen.getByText('Cho phép một lần')).toBeDefined();
  });

  it('ẩn phê duyệt theo phiên cho workflow n8n', () => {
    useHermesStore.setState({
      pendingApproval: {
        approval_id: 'test-n8n',
        action: 'call_n8n_webhook',
        target: 'echo',
        risk_level: 'write_internal',
      },
    });

    render(<ApprovalModal />);
    expect(screen.getByText('Gọi workflow n8n')).toBeDefined();
    expect(screen.queryByText('Cho phép trong phiên')).toBeNull();
  });

  it('gửi quyết định, thêm activity và yêu cầu refresh audit', async () => {
    useHermesStore.setState({
      pendingApproval: {
        approval_id: 'test-123',
        action: 'write_workspace_file',
        target: 'file.txt',
        risk_level: 'write_internal',
      },
    });

    render(<ApprovalModal />);
    fireEvent.click(screen.getByText('Từ chối'));

    await waitFor(() => {
      expect(approvalsApi.submitApprovalDecision).toHaveBeenCalledWith('test-123', 'deny');
    });

    const state = useHermesStore.getState();
    expect(state.pendingApproval).toBeNull();
    expect(state.auditRefreshVersion).toBe(1);
    expect(state.events['session-1'][0].type).toBe('approval_decision');
    expect(state.events['session-1'][0].message).toContain('Đã từ chối');
  });
});
