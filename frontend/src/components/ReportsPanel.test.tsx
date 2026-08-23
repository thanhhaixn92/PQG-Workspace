import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ReportsPanel } from './ReportsPanel';
import { useHermesStore } from '../store/store';
import * as artifactsApi from '../api/artifacts';
import * as worksApi from '../api/works';

vi.mock('../api/artifacts', () => ({
  listArtifacts: vi.fn().mockResolvedValue([]),
  createMarkdownReport: vi.fn(),
}));
vi.mock('../api/works', () => ({ getWorkDashboard: vi.fn() }));

describe('ReportsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ activeSessionId: 'session-1' });
  });

  it('creates and displays a managed Markdown report', async () => {
    vi.mocked(artifactsApi.createMarkdownReport).mockResolvedValue({
      id: 'artifact-1', session_id: 'session-1', relative_path: 'outputs/reports/weekly.md',
      kind: 'report_markdown', sha256: 'hash', size_bytes: 12, created_at: 1, duplicate: false,
    });
    render(<ReportsPanel />);
    await waitFor(() => expect(artifactsApi.listArtifacts).toHaveBeenCalledWith('session-1'));
    fireEvent.change(screen.getByLabelText('Tiêu đề báo cáo'), { target: { value: 'Weekly' } });
    fireEvent.change(screen.getByLabelText('Nội dung báo cáo'), { target: { value: 'Done' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo báo cáo Markdown' }));
    await waitFor(() => {
      expect(artifactsApi.createMarkdownReport).toHaveBeenCalled();
      expect(screen.getByText('weekly.md')).toBeDefined();
    });
  });

  it('does not show a report response from the previously selected work', async () => {
    let resolveReport!: (value: artifactsApi.ReportResult) => void;
    vi.mocked(artifactsApi.createMarkdownReport).mockReturnValue(new Promise(resolve => {
      resolveReport = resolve;
    }));
    render(<ReportsPanel />);
    fireEvent.change(screen.getByLabelText('Tiêu đề báo cáo'), { target: { value: 'Old work' } });
    fireEvent.change(screen.getByLabelText('Nội dung báo cáo'), { target: { value: 'Old content' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo báo cáo Markdown' }));
    await waitFor(() => expect(artifactsApi.createMarkdownReport).toHaveBeenCalled());

    act(() => useHermesStore.getState().setActiveSession('session-2'));
    resolveReport({
      id: 'artifact-old', session_id: 'session-1', relative_path: 'outputs/reports/old.md',
      kind: 'report_markdown', sha256: 'hash', size_bytes: 3, created_at: 1, duplicate: false,
    });

    await Promise.resolve();
    expect(screen.queryByText('old.md')).toBeNull();
    expect((screen.getByLabelText('Tiêu đề báo cáo') as HTMLInputElement).value).toBe('');
  });

  it('creates an HTML report for browser printing', async () => {
    vi.mocked(artifactsApi.createMarkdownReport).mockResolvedValue({
      id: 'artifact-html', session_id: 'session-1', relative_path: 'outputs/reports/review.html',
      kind: 'report_html', sha256: 'hash', size_bytes: 20, created_at: 1, duplicate: false,
    });
    render(<ReportsPanel />);
    fireEvent.change(screen.getByLabelText('Tiêu đề báo cáo'), { target: { value: 'Review' } });
    fireEvent.change(screen.getByLabelText('Nội dung báo cáo'), { target: { value: 'Ready' } });
    fireEvent.change(screen.getByLabelText('Định dạng báo cáo'), { target: { value: 'html' } });
    fireEvent.click(screen.getByRole('button', { name: 'Tạo báo cáo HTML' }));
    await waitFor(() => expect(artifactsApi.createMarkdownReport).toHaveBeenCalledWith(
      'session-1', 'Review', 'Ready', expect.any(String), 'html',
    ));
    expect(await screen.findByText('review.html')).toBeDefined();
  });

  it('creates an editable report draft from the selected Work only', async () => {
    vi.mocked(worksApi.getWorkDashboard).mockResolvedValue({
      work: { id: 'session-1', title: 'Kế hoạch tuần', goal: 'Chốt ưu tiên', workspace_path: 'hidden', created_at: 1, updated_at: 2, archived: 0, work_status: 'in_progress', progress_percent: 45 },
      next_step: { id: 'step-1', phase_id: 'phase-1', session_id: 'session-1', title: 'Xác nhận phạm vi', sort_order: 0, status: 'in_progress', source: 'user', created_at: 1, updated_at: 1 },
      conversations: [], phases: [], pending_approval_count: 2, artifacts: [{ id: 'artifact-1', session_id: 'session-1', relative_path: 'outputs/summary.md', kind: 'report_markdown', sha256: 'hash', size_bytes: 12, created_at: 1 }], context_summary: null, capabilities_used: [],
    });
    render(<ReportsPanel />);
    fireEvent.click(await screen.findByRole('button', { name: 'Tạo nháp từ Công việc' }));
    await waitFor(() => expect(worksApi.getWorkDashboard).toHaveBeenCalledWith('session-1'));
    expect((screen.getByLabelText('Tiêu đề báo cáo') as HTMLInputElement).value).toContain('Kế hoạch tuần');
    expect((screen.getByLabelText('Nội dung báo cáo') as HTMLTextAreaElement).value).toContain('Xác nhận phạm vi');
    expect((screen.getByLabelText('Nội dung báo cáo') as HTMLTextAreaElement).value).toContain('outputs/summary.md');
  });

  it('builds a selected-source draft with provenance and a preview', async () => {
    vi.mocked(worksApi.getWorkDashboard).mockResolvedValue({
      work: { id: 'session-1', title: 'Bàn giao tuần', goal: 'Giữ đúng phạm vi', workspace_path: 'hidden', created_at: 1, updated_at: 2, archived: 0, work_status: 'in_progress', progress_percent: 60 },
      next_step: null, conversations: [{ id: 'conversation-1', session_id: 'session-1', title: 'Phạm vi', status: 'active', message_count: 0, created_at: 1, updated_at: 1 }], phases: [], pending_approval_count: 1, artifacts: [], context_summary: null, capabilities_used: [], progress_source: 'plan_steps',
    });
    render(<ReportsPanel />);
    fireEvent.change(screen.getByLabelText('Mẫu báo cáo'), { target: { value: 'handoff' } });
    fireEvent.click(screen.getByLabelText('Đầu ra'));
    fireEvent.click(await screen.findByRole('button', { name: 'Tạo nháp từ Công việc' }));
    await waitFor(() => expect(worksApi.getWorkDashboard).toHaveBeenCalledWith('session-1'));
    const draft = (screen.getByLabelText('Nội dung báo cáo') as HTMLTextAreaElement).value;
    expect(draft).toContain('Trạng thái bàn giao');
    expect(draft).toContain('Nguồn và phạm vi');
    expect(draft).toContain('danh sách phiên trao đổi');
    expect(draft).not.toContain('đầu ra đã quản lý');
    fireEvent.click(screen.getByRole('button', { name: 'Xem trước báo cáo' }));
    expect(screen.getByRole('region', { name: 'Xem trước báo cáo' })).toBeDefined();
  });
});
