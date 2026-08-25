import { cleanup, render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../MarkdownRenderer', () => ({
  MarkdownRenderer: ({ content }: { content: string }) => <div data-testid="markdown">{content}</div>,
}));
vi.mock('./TurnPartRenderer', () => ({
  TurnPartRenderer: () => null,
  AssistantTurnCard: ({ streamedText }: { turn: { id: string; status: string }; streamedText?: string }) => {
    if (!streamedText) return null;
    return <div data-testid="streaming-text">{streamedText}</div>;
  },
}));
vi.mock('./ContextPanel', () => ({
  ContextPanel: () => <div data-testid="context-panel">Context</div>,
}));
vi.mock('./HistoryPanel', () => ({
  HistoryPanel: () => <div data-testid="history-panel">History</div>,
}));
vi.mock('../../api/actionPackages', () => ({
  getActionPackage: vi.fn(),
  getActionPackagePreflight: vi.fn(),
  getActionPackagePreflightDecisionBinding: vi.fn((preflight: { valid: boolean; revision?: number; payload_hash?: string }) => (
    preflight.valid === true
      && typeof preflight.revision === 'number'
      && Number.isInteger(preflight.revision)
      && preflight.revision >= 1
      && preflight.payload_hash
      ? { expectedRevision: preflight.revision, expectedPayloadHash: preflight.payload_hash }
      : null
  )),
}));

import { GYOAssistant } from './GYOAssistant';
import * as actionPackagesApi from '../../api/actionPackages';
import type { AssistantThread, AssistantTurn } from '../../api/assistant';
import type { Artifact } from '../../api/artifacts';
import type { WorkDashboard } from '../../api/works';

const WORK_DASHBOARD: WorkDashboard = {
  work: { id: 'work-a', title: 'Work A', workspace_path: '/a', created_at: 1, updated_at: 1, work_status: 'in_progress', progress_percent: 10 },
  next_step: null,
  conversations: [],
  phases: [],
  pending_approval_count: 0,
  artifacts: [],
  capabilities_used: [],
};

const noop = () => {};
const noopAsync = async () => {};
const CANONICAL_PACKAGE = {
  id: 'pkg-1', session_id: 'work-a', title: 'Cap nhat', package_hash: 'legacy-hash', payload_hash: 'hash-1',
  revision: 1, status: 'awaiting_approval', created_at: 1, updated_at: 1, steps: [],
};
const CANONICAL_PREFLIGHT = {
  package_id: 'pkg-1', valid: true, revision: 1, payload_hash: 'hash-1',
};
const THREAD: AssistantThread = {
  id: 't-1', title: 'Test', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1,
};
const ACTION_TURN: AssistantTurn = {
  id: 'turn-1', thread_id: 't-1', work_id: 'work-a', conversation_id: 'conv-a1',
  role: 'assistant', status: 'completed', created_at: 1,
  parts: [{
    id: 'part-1', part_type: 'action_proposal', sort_order: 0,
    content: {
      title: 'Cap nhat',
      description: 'Mo ta',
      package_id: 'pkg-1',
      expected_revision: 1,
      expected_payload_hash: 'hash-1',
    },
  }],
};

const baseProps = {
  workId: 'work-a',
  conversationId: 'conv-a1',
  threadId: null,
  mode: 'drawer' as const,
  visible: true,
  dashboard: WORK_DASHBOARD,
  conversations: [],
  threads: [],
  turns: [],
  streamedText: {},
  manifest: null,
  artifacts: [],
  modelConfig: { default_model_id: 'gpt', models: [], providers: [] },
  workArchived: false,
  error: null,
  loading: false,
  onSelectConversation: noop,
  onSelectThread: noop,
  onNavigateToFocus: noop,
  onSubmitPrompt: noopAsync,
  onCancelTurn: noopAsync,
  onRetryTurn: noopAsync,
  onCreateProposal: noopAsync,
  onApproveConfirmation: noopAsync,
  onDenyConfirmation: noopAsync,
  onSearchHistory: noop,
  onLoadHistory: noop,
  onDraftChanged: noop,
};

describe('GYOAssistant (shared surface)', () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(actionPackagesApi.getActionPackage).mockResolvedValue(CANONICAL_PACKAGE);
    vi.mocked(actionPackagesApi.getActionPackagePreflight).mockResolvedValue(CANONICAL_PREFLIGHT);
  });

  it('renders GYO label — not Hermes', () => {
    render(<GYOAssistant {...baseProps} />);
    expect(screen.getByText('GYO')).toBeDefined();
    expect(document.body.innerHTML).not.toContain('Phê duyệt nghiệp vụ');
    expect(document.body.innerHTML).not.toContain('Hermes Local');
  });

  it('shows WelcomeScreen when no work is selected', () => {
    render(<GYOAssistant {...baseProps} workId={null} conversationId={null} />);
    expect(screen.getByText('GYO đã sẵn sàng')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Xem lịch sử' })).toBeDefined();
  });

  it('shows loading indicator when loading=true and no turns', () => {
    render(<GYOAssistant {...baseProps} loading={true} />);
    expect(screen.getByText('Đang kết nối với GYO…')).toBeDefined();
  });

  it('submits a composed prompt with Enter and keeps Shift+Enter for a line break', async () => {
    const submitPrompt = vi.fn().mockResolvedValue(undefined);
    render(<GYOAssistant {...baseProps} onSubmitPrompt={submitPrompt} />);
    const composer = screen.getByRole('textbox', { name: 'Gửi yêu cầu cho GYO' });
    fireEvent.change(composer, { target: { value: 'Tóm tắt việc hôm nay' } });
    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: true });
    expect(submitPrompt).not.toHaveBeenCalled();
    fireEvent.keyDown(composer, { key: 'Enter' });
    await waitFor(() => expect(submitPrompt).toHaveBeenCalledWith('Tóm tắt việc hôm nay', 'auto', []));
  });

  it('shows streaming indicator when a turn is running', () => {
    const runningTurn: AssistantTurn = {
      id: 'turn-1', thread_id: 't-1', work_id: 'work-a', conversation_id: 'conv-a1',
      role: 'assistant', status: 'running', created_at: 1, parts: [],
    };
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[runningTurn]} />);
    expect(screen.getByText(/đang trả lời/i)).toBeDefined();
  });

  it('renders composer with model selector and attachment tray', () => {
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[{
      id: 'turn-1', thread_id: 't-1', work_id: 'work-a', conversation_id: 'conv-a1',
      role: 'assistant', status: 'completed', created_at: 1, parts: [],
    }]} />);
    expect(screen.getByLabelText(/Gửi yêu cầu cho GYO/i)).toBeDefined();
    expect(screen.getByText('Gửi GYO')).toBeDefined();
    expect(screen.getByText(/Tự động/i)).toBeDefined();
    expect(screen.getByLabelText('Mở thùng tệp ngữ cảnh GYO')).toBeDefined();
  });

  it('adds a structurally validated text artifact to the GYO context draft', () => {
    const artifact: Artifact = {
      id: 'artifact-text', session_id: 'work-a', relative_path: 'inputs/evidence.txt',
      kind: 'imported_file', sha256: 'abc', size_bytes: 12, created_at: 1,
      validation_status: 'structurally_validated',
    };
    const onDraftChanged = vi.fn();
    render(<GYOAssistant {...baseProps} artifacts={[artifact]} onDraftChanged={onDraftChanged} />);
    fireEvent.click(screen.getByLabelText('Mở thùng tệp ngữ cảnh GYO'));
    fireEvent.click(screen.getByRole('button', { name: 'Dùng inputs/evidence.txt' }));
    expect(onDraftChanged).toHaveBeenLastCalledWith('', 'auto', ['artifact-text']);
    expect(screen.getByText('inputs/evidence.txt')).toBeDefined();
  });

  it('renders ConfirmationFooter with correct wording', async () => {
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} />);
    const confirmBtn = screen.getByRole('button', { name: 'Xác nhận cho GYO thực thi' });
    expect(confirmBtn).toBeDefined();
    expect(screen.getByText('Xác nhận cho GYO thực thi')).toBeDefined();
    await waitFor(() => expect((confirmBtn as HTMLButtonElement).disabled).toBe(false));
  });

  it('shows error state with correct label for conflict', () => {
    render(<GYOAssistant {...baseProps} error={{ category: 'conflict', message: 'Test conflict', actionable: true }} />);
    expect(screen.getByText('Xung đột')).toBeDefined();
    expect(screen.getByText('Test conflict')).toBeDefined();
    expect(screen.getByRole('alert', { name: /Lỗi: conflict/i })).toBeDefined();
  });

  it('shows read-only message when work is archived', () => {
    render(<GYOAssistant {...baseProps} workArchived={true} />);
    expect(screen.getByText(/Công việc đã lưu trữ/i)).toBeDefined();
  });

  it('renders in focus mode with focus header class', () => {
    const { container } = render(<GYOAssistant {...baseProps} mode="focus" />);
    expect(container.querySelector('.gyo-surface--focus')).toBeDefined();
  });

  it('has aria-label on surface for accessibility', () => {
    render(<GYOAssistant {...baseProps} />);
    const surface = screen.getByLabelText('Trợ lý GYO');
    expect(surface).toBeDefined();
  });

  it('sets data-gyo-mode attribute for drawer and focus', () => {
    const { unmount } = render(<GYOAssistant {...baseProps} mode="drawer" />);
    expect(document.querySelector('[data-gyo-mode="drawer"]')).toBeDefined();
    unmount();
    render(<GYOAssistant {...baseProps} mode="focus" />);
    expect(document.querySelector('[data-gyo-mode="focus"]')).toBeDefined();
  });

  it('shows streaming cursor during active streaming', () => {
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" streamedText={{ 'turn-1': 'Hello' }} turns={[{
      id: 'turn-1', thread_id: 't-1', work_id: 'work-a', conversation_id: 'conv-a1',
      role: 'assistant', status: 'running', created_at: 1, parts: [],
    }]} />);
    expect(screen.getByTestId('streaming-text').textContent).toBe('Hello');
  });

  it('renders context panel toggle button', () => {
    render(<GYOAssistant {...baseProps} />);
    expect(screen.getByLabelText('Ngữ cảnh làm việc')).toBeDefined();
  });

  it('renders context panel when toggled', () => {
    render(<GYOAssistant {...baseProps} />);
    const toggle = screen.getByLabelText('Ngữ cảnh làm việc');
    fireEvent.click(toggle);
    expect(screen.getByTestId('context-panel')).toBeDefined();
  });

  it('re-preflights approval and passes the exact current binding to onApproveConfirmation', async () => {
    const approveSpy = vi.fn().mockResolvedValue(undefined);
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} onApproveConfirmation={approveSpy} />);
    const confirmBtn = screen.getByRole('button', { name: 'Xác nhận cho GYO thực thi' });
    await waitFor(() => expect((confirmBtn as HTMLButtonElement).disabled).toBe(false));

    fireEvent.click(confirmBtn);

    await waitFor(() => expect(approveSpy).toHaveBeenCalledWith('pkg-1', 1, 'hash-1'));
    expect(actionPackagesApi.getActionPackagePreflight).toHaveBeenCalledWith('pkg-1');
  });

  it('re-preflights deny and passes the exact current binding to onDenyConfirmation', async () => {
    const denySpy = vi.fn().mockResolvedValue(undefined);
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} onDenyConfirmation={denySpy} />);
    const denyBtn = await screen.findByRole('button', { name: 'Không thực thi' });
    await waitFor(() => expect((denyBtn as HTMLButtonElement).disabled).toBe(false));

    fireEvent.click(denyBtn);

    await waitFor(() => expect(denySpy).toHaveBeenCalledWith('pkg-1', 1, 'hash-1'));
    expect(actionPackagesApi.getActionPackagePreflight).toHaveBeenCalledWith('pkg-1');
  });

  it('disables approval CTA when the canonical package binding is missing (fail-closed)', () => {
    vi.mocked(actionPackagesApi.getActionPackage).mockRejectedValueOnce(new Error('not available'));
    const approveSpy = vi.fn().mockResolvedValue(undefined);
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} onApproveConfirmation={approveSpy} />);

    const confirmBtn = screen.getByRole('button', { name: 'Xác nhận cho GYO thực thi' });
    expect((confirmBtn as HTMLButtonElement).disabled).toBe(true);
    expect(approveSpy).not.toHaveBeenCalled();
  });

  it('rechecks canonical preflight at click time and rejects an invalid package without approval', async () => {
    const approveSpy = vi.fn().mockResolvedValue(undefined);
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} onApproveConfirmation={approveSpy} />);
    const confirm = await screen.findByRole('button', { name: 'Xác nhận cho GYO thực thi' });
    await waitFor(() => expect((confirm as HTMLButtonElement).disabled).toBe(false));
    vi.mocked(actionPackagesApi.getActionPackagePreflight).mockResolvedValueOnce({ package_id: 'pkg-1', valid: false, errors: ['artifact changed'] });

    fireEvent.click(confirm);

    await waitFor(() => expect(screen.getByText(/Mục đã thay đổi, hết hạn hoặc được xử lý ở nơi khác/i)).toBeDefined());
    expect(approveSpy).not.toHaveBeenCalled();
  });

  it('rejects a click-time binding mismatch and refreshes instead of approving a different revision', async () => {
    const approveSpy = vi.fn().mockResolvedValue(undefined);
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} onApproveConfirmation={approveSpy} />);
    const confirm = await screen.findByRole('button', { name: 'Xác nhận cho GYO thực thi' });
    await waitFor(() => expect((confirm as HTMLButtonElement).disabled).toBe(false));
    vi.mocked(actionPackagesApi.getActionPackagePreflight).mockResolvedValueOnce({
      package_id: 'pkg-1', valid: true, revision: 2, payload_hash: 'hash-2',
    });

    fireEvent.click(confirm);

    await waitFor(() => expect(screen.getByText(/Mục đã thay đổi, hết hạn hoặc được xử lý ở nơi khác/i)).toBeDefined());
    expect(approveSpy).not.toHaveBeenCalled();
  });

  it('prevents double-click from duplicating a GYO confirmation decision', async () => {
    const approveSpy = vi.fn().mockResolvedValue(undefined);
    let resolvePreflight!: (value: typeof CANONICAL_PREFLIGHT) => void;
    render(<GYOAssistant {...baseProps} threads={[THREAD]} threadId="t-1" turns={[ACTION_TURN]} onApproveConfirmation={approveSpy} />);
    const confirm = await screen.findByRole('button', { name: 'Xác nhận cho GYO thực thi' });
    await waitFor(() => expect((confirm as HTMLButtonElement).disabled).toBe(false));
    vi.mocked(actionPackagesApi.getActionPackagePreflight).mockReturnValueOnce(new Promise(resolve => { resolvePreflight = resolve; }));

    fireEvent.click(confirm);
    fireEvent.click(confirm);

    expect(approveSpy).not.toHaveBeenCalled();
    resolvePreflight(CANONICAL_PREFLIGHT);
    await waitFor(() => expect(approveSpy).toHaveBeenCalledTimes(1));
  });
});
