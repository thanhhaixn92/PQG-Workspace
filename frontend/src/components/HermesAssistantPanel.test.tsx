import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as assistantApi from '../api/assistant';
import * as overviewApi from '../api/overview';
import * as actionPackagesApi from '../api/actionPackages';
import * as artifactsApi from '../api/artifacts';
import * as worksApi from '../api/works';
import * as marketplaceApi from '../api/marketplace';
import { ApiError } from '../api/client';
import { useHermesStore } from '../store/store';
import { HermesAssistantPanel, TurnPartRenderer } from './HermesAssistantPanel';

vi.mock('../api/assistant', () => ({
  assistantThreadStreamUrl: vi.fn(() => '/api/assistant/threads/thread-1/stream'), cancelAssistantTurn: vi.fn(), createAssistantRun: vi.fn(), createAssistantThread: vi.fn(), resolveWorkConversationAssistantThread: vi.fn(), getAssistantContextManifest: vi.fn(),
  getAssistantTurns: vi.fn(), listAssistantThreads: vi.fn(), retryAssistantTurn: vi.fn(), updateAssistantThread: vi.fn(),
}));
vi.mock('../api/overview', () => ({ getOverview: vi.fn() }));
vi.mock('../api/actionPackages', () => ({
  approveActionPackage: vi.fn(), denyActionPackage: vi.fn(), getWorkActionPackages: vi.fn(),
  getActionPackageDecisionBinding: vi.fn(() => ({ expectedRevision: 1, expectedPayloadHash: 'payload-hash' })),
  createActionPackageIdempotencyKey: vi.fn(() => 'test-decision-key'),
}));
vi.mock('../api/artifacts', () => ({ listArtifacts: vi.fn() }));
vi.mock('../api/works', () => ({ createConversation: vi.fn(), getPlan: vi.fn(), getWorkMemoryContext: vi.fn(), listConversations: vi.fn(), updateWorkMemoryContext: vi.fn() }));
vi.mock('../api/marketplace', () => ({ getModelConfig: vi.fn() }));

describe('HermesAssistantPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    useHermesStore.setState({ sessions: [], activeSessionId: null, sidebarTab: 'hermes' });
    vi.mocked(overviewApi.getOverview).mockResolvedValue({
      recent_work: [], active_work_count: 0, pending_approval_count: 0, output_count: 0, latest_backup_at: null,
      blocked_step_count: 0, waiting_confirmation_count: 0, attention_items: [], recent_artifacts: [], latest_work_updates: [],
    });
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([{ id: 'historic-home', title: 'Trao đổi với Hermes', work_id: null, status: 'active', created_at: 1, updated_at: 1 }]);
    vi.mocked(assistantApi.getAssistantContextManifest).mockResolvedValue({
      included: [], excluded: [{ kind: 'memory_hub', reason: 'Không tự động đưa vào chat' }], byte_limit: 0, byte_count: 0, memory_hub_auto_injected: false,
    });
    vi.mocked(actionPackagesApi.getWorkActionPackages).mockResolvedValue([]);
    vi.mocked(artifactsApi.listArtifacts).mockResolvedValue([]);
    vi.mocked(worksApi.getPlan).mockResolvedValue([]);
    vi.mocked(worksApi.listConversations).mockResolvedValue([{ id: 'conversation-1', session_id: 'work-1', title: 'Phiên A', status: 'active', created_at: 1, updated_at: 1, message_count: 0 }]);
    vi.mocked(worksApi.getWorkMemoryContext).mockResolvedValue({ work_id: 'work-1', plan_step_id: 'step-1', scope_id: 'scope-1', context_mode: 'suggest_only', auto_learning_enabled: false, active_memory_count: 0, excluded: [] });
    vi.mocked(marketplaceApi.getModelConfig).mockResolvedValue({
      provider: 'Zen', model: 'mimo-v2.5-free', auth_ready: true, mutable_from_browser: true, guidance: 'x', default_model_profile_id: 'model-1',
      providers: [{ id: 'provider-1', display_name: 'Zen', provider_type: 'openai_compatible', base_url: 'https://opencode.ai/zen/v1', enabled: true, credential_configured: true, health_status: 'ready', created_at: 1, updated_at: 1 }],
      models: [{ id: 'model-1', provider_profile_id: 'provider-1', display_name: 'MiMo V2.5 Free', model_identifier: 'mimo-v2.5-free', tier: 'balanced', capabilities: ['chat'], priority: 10, enabled: true, is_default: true, cost_class: 'free', created_at: 1, updated_at: 1 }],
      routing_policy: { auto_fallback_enabled: false, max_fallback_attempts: 2, fallback_scope: 'all_enabled_models', enabled_model_counts: { free: 1, unknown: 0, may_charge: 0 } },
    });
  });

  it('does not expose or create an unscoped conversation while no Work is selected', async () => {
    render(<HermesAssistantPanel />);
    expect(await screen.findByText('Tạo Công việc đầu tiên để bắt đầu trao đổi, quản lý tài liệu và theo dõi tiến độ.')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Phiên mới' }).hasAttribute('disabled')).toBe(true);
    expect(screen.getByRole('combobox', { name: 'Phiên trao đổi trợ lý' }).textContent).toContain('Chưa có phiên trao đổi');
    expect(assistantApi.getAssistantTurns).not.toHaveBeenCalled();
  });

  it('renders every structured response part without treating it as raw technical output', () => {
    const { rerender } = render(<TurnPartRenderer part={{ id: 'p1', part_type: 'tool_result', content: { tool_name: 'Kiểm tra tài liệu', summary: 'Đã đọc 2 tài liệu.' }, sort_order: 1 }} />);
    expect(screen.getByText('Kiểm tra tài liệu')).toBeDefined();
    expect(screen.getByText('Đã đọc 2 tài liệu.')).toBeDefined();
    rerender(<TurnPartRenderer part={{ id: 'p2', part_type: 'error', content: { title: 'Không thể tiếp tục', message: 'Hermes ACP chưa sẵn sàng.' }, sort_order: 2 }} />);
    expect(screen.getByText('Không thể tiếp tục')).toBeDefined();
    expect(screen.getByText('Hermes ACP chưa sẵn sàng.')).toBeDefined();
  });

  it('renders an action proposal as a reviewable, non-executing card', () => {
    const openReview = vi.fn();
    render(<TurnPartRenderer part={{
      id: 'proposal-1', part_type: 'action_proposal', sort_order: 1,
      content: { title: 'Cập nhật bước kiểm thử', description: 'Đánh dấu bước đã hoàn tất.', impact: 'Cập nhật một bước của Công việc này.', undo: 'Có thể đổi lại trạng thái.', risk: 'Cần bạn duyệt' },
    }} onOpenReview={openReview} />);
    expect(screen.getByText('Cập nhật bước kiểm thử')).toBeDefined();
    expect(screen.getByText('Cập nhật một bước của Công việc này.')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Xem đề xuất' }));
    expect(openReview).toHaveBeenCalledOnce();
  });

  it('keeps the overview usable if the thread list fails', async () => {
    vi.mocked(assistantApi.listAssistantThreads).mockRejectedValue(new Error('offline'));
    render(<HermesAssistantPanel />);
    await waitFor(() => expect(screen.getByText('Chưa tải được danh sách phiên trao đổi. Bạn có thể thử lại phần này.')).toBeDefined());
    expect(screen.getByText('Tổng quan các Công việc')).toBeDefined();
  });

  it('loads and persists Memory policy only after the user selects a visible plan step', async () => {
    vi.mocked(worksApi.getPlan).mockResolvedValue([{
      id: 'phase-1', session_id: 'work-1', title: 'Pha 1', sort_order: 0, status: 'not_started', source: 'user', created_at: 1, updated_at: 1,
      steps: [{ id: 'step-1', phase_id: 'phase-1', session_id: 'work-1', title: 'Bước có Memory', sort_order: 0, status: 'not_started', source: 'user', created_at: 1, updated_at: 1 }],
    }]);
    vi.mocked(worksApi.updateWorkMemoryContext).mockResolvedValue({ work_id: 'work-1', plan_step_id: 'step-1', scope_id: 'scope-1', context_mode: 'active_work_memory', auto_learning_enabled: false, active_memory_count: 0, excluded: [] });
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });
    render(<HermesAssistantPanel />);
    fireEvent.click(await screen.findByRole('button', { name: /Ngữ cảnh & nguồn/i }));
    const stepSelect = await screen.findByLabelText('Bước kế hoạch');
    fireEvent.change(stepSelect, { target: { value: 'step-1' } });
    await screen.findByText('Tự học có kiểm soát cho bước này');
    fireEvent.change(screen.getByLabelText('Chế độ Memory'), { target: { value: 'active_work_memory' } });
    await waitFor(() => expect(worksApi.updateWorkMemoryContext).toHaveBeenCalledWith('work-1', 'step-1', { context_mode: 'active_work_memory', auto_learning_enabled: false }));
  });

  it('uses one model picker with automatic and provider-grouped manual choices', async () => {
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([{ id: 'thread-1', title: 'Trao đổi', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 1 }]);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([]);
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });
    render(<HermesAssistantPanel />);
    const picker = await screen.findByRole('combobox', { name: 'Model GYO' });
    expect(picker.textContent).toContain('Tự động (khuyến nghị)');
    expect(picker.textContent).toContain('MiMo V2.5 Free');
    expect(screen.queryByRole('combobox', { name: 'Cách chọn model' })).toBeNull();
  });

  it('creates an explicit Work conversation then resolves its bound thread before sending scope', async () => {
    const conversation = { id: 'conversation-new', session_id: 'work-1', title: 'Trao đổi: Công việc A', status: 'active' as const, created_at: 2, updated_at: 2, message_count: 0 };
    vi.mocked(worksApi.createConversation).mockResolvedValue(conversation);
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread).mockResolvedValue({ id: 'thread-new', title: 'GYO Thread', work_id: 'work-1', conversation_id: 'conversation-new', status: 'active', created_at: 2, updated_at: 2 });
    vi.mocked(assistantApi.createAssistantRun).mockResolvedValue([]);
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });

    render(<HermesAssistantPanel />);
    fireEvent.click(await screen.findByRole('button', { name: 'Phiên mới' }));
    await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-1', 'conversation-new'));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Tóm tắt phạm vi' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gửi' }));
    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith('thread-new', 'Tóm tắt phạm vi', 'work-1', 'conversation-new', [], expect.any(Object)));
  });

  it('opens context as a focus-managed drawer on mobile and restores the trigger after Escape', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    render(<HermesAssistantPanel />);

    const trigger = await screen.findByRole('button', { name: /Ngữ cảnh & nguồn/i });
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByRole('dialog', { name: 'Ngữ cảnh & nguồn' })).toBeDefined();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Đóng' }));

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'Ngữ cảnh & nguồn' })).toBeNull();
      expect(document.activeElement).toBe(trigger);
    });
  });

  it('renames and archives only the selected Work-scoped assistant thread', async () => {
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([{
      id: 'thread-1', title: 'Phân tích ban đầu', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 1,
    }]);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([]);
    vi.mocked(assistantApi.updateAssistantThread).mockResolvedValue({
      id: 'thread-1', title: 'Kế hoạch đã chốt', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 2,
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    useHermesStore.setState({
      sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }],
      activeSessionId: 'work-1',
    });

    render(<HermesAssistantPanel />);
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Phiên trao đổi trợ lý' }).textContent).toContain('Phân tích ban đầu'));
    fireEvent.change(screen.getByRole('combobox', { name: 'Phiên trao đổi trợ lý' }), { target: { value: 'thread-1' } });
    await screen.findByRole('button', { name: 'Đổi tên' });
    fireEvent.click(screen.getByRole('button', { name: 'Đổi tên' }));
    fireEvent.change(screen.getByLabelText('Tên phiên trao đổi'), { target: { value: 'Kế hoạch đã chốt' } });
    fireEvent.click(screen.getByRole('button', { name: 'Lưu tên' }));
    await waitFor(() => expect(assistantApi.updateAssistantThread).toHaveBeenCalledWith('thread-1', { title: 'Kế hoạch đã chốt' }));

    fireEvent.click(screen.getByRole('button', { name: 'Lưu trữ' }));
    await waitFor(() => expect(assistantApi.updateAssistantThread).toHaveBeenLastCalledWith('thread-1', { archived: true }));
    expect(screen.getByRole('combobox', { name: 'Phiên trao đổi trợ lý' }).textContent).toContain('Chưa có phiên trao đổi');
  });

  it('shows archived history read-only and requires restore before another request', async () => {
    vi.mocked(assistantApi.listAssistantThreads).mockImplementation(async includeArchived => includeArchived ? [{
      id: 'thread-archive', title: 'Trao đổi đã lưu', work_id: 'work-1', conversation_id: 'conversation-1', status: 'archived', created_at: 1, updated_at: 2,
    }] : []);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([]);
    vi.mocked(assistantApi.updateAssistantThread).mockResolvedValue({
      id: 'thread-archive', title: 'Trao đổi đã lưu', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 3,
    });
    useHermesStore.setState({
      sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }],
      activeSessionId: 'work-1',
    });

    render(<HermesAssistantPanel />);
    fireEvent.click(await screen.findByRole('button', { name: 'Lịch sử' }));
    await waitFor(() => expect(assistantApi.listAssistantThreads).toHaveBeenLastCalledWith(true));
    fireEvent.change(screen.getByRole('combobox', { name: 'Phiên trao đổi trợ lý' }), { target: { value: 'thread-archive' } });
    expect(await screen.findByText('Đây là phiên đã lưu trữ. Bạn có thể xem lại lịch sử hoặc khôi phục để tiếp tục trao đổi.')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Gửi' }).hasAttribute('disabled')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Khôi phục' }));
    await waitFor(() => expect(assistantApi.updateAssistantThread).toHaveBeenCalledWith('thread-archive', { archived: false }));
  });

  it('shows Work action packages inline and confirms the exact proposed change before approval', async () => {
    vi.mocked(actionPackagesApi.getWorkActionPackages).mockResolvedValue([{
      id: 'package-1', session_id: 'work-1', title: 'Cập nhật tiến độ', description: 'Đặt tiến độ thành 40%.', package_hash: 'hash', status: 'awaiting_approval', created_at: 1, updated_at: 1,
      steps: [{ id: 'step-1', sort_order: 0, kind: 'work_status_update', risk_level: 'write', input: {}, status: 'pending' }],
    }]);
    vi.mocked(actionPackagesApi.approveActionPackage).mockResolvedValue({
      id: 'package-1', session_id: 'work-1', title: 'Cập nhật tiến độ', description: 'Đặt tiến độ thành 40%.', package_hash: 'hash', status: 'approved', created_at: 1, updated_at: 2,
      steps: [{ id: 'step-1', sort_order: 0, kind: 'work_status_update', risk_level: 'write', input: {}, status: 'pending' }],
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });

    render(<HermesAssistantPanel />);
    expect(await screen.findByText('Cập nhật tiến độ')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt thay đổi' }));
    await waitFor(() => expect(actionPackagesApi.approveActionPackage).toHaveBeenCalledWith(
      'package-1', { expectedRevision: 1, expectedPayloadHash: 'payload-hash' }, 'test-decision-key',
    ));
  });

  it('refreshes authoritative Work package state and removes stale CTA after a 409 decision conflict', async () => {
    const pending = {
      id: 'package-409', session_id: 'work-1', title: 'Gói cạnh tranh', description: null, package_hash: 'hash', status: 'awaiting_approval', created_at: 1, updated_at: 1,
      steps: [{ id: 'step-409', sort_order: 0, kind: 'work_status_update', risk_level: 'write', input: {}, status: 'pending' }],
    };
    vi.mocked(actionPackagesApi.getWorkActionPackages)
      .mockResolvedValueOnce([pending])
      .mockResolvedValueOnce([{ ...pending, status: 'approved', updated_at: 2 }]);
    vi.mocked(actionPackagesApi.approveActionPackage).mockRejectedValue(new ApiError(409, 'already decided'));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });

    render(<HermesAssistantPanel />);
    expect(await screen.findByText('Gói cạnh tranh')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Duyệt thay đổi' }));
    expect(await screen.findByText('Mục đã được xử lý ở nơi khác. Trạng thái đang được làm mới.')).toBeDefined();
    await waitFor(() => expect(actionPackagesApi.getWorkActionPackages).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('button', { name: 'Duyệt thay đổi' })).toBeNull();
  });

  it('renders a live token only inside the selected assistant thread', async () => {
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      listeners = new Map<string, (event: MessageEvent) => void>();
      constructor(_url: string) { FakeEventSource.instances.push(this); }
      addEventListener(type: string, listener: (event: MessageEvent) => void) { this.listeners.set(type, listener); }
      close() {}
      emit(type: string, data: unknown) { this.listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent); }
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([{
      id: 'thread-1', title: 'Trao đổi A', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 1,
    }]);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([{
      id: 'turn-running', thread_id: 'thread-1', work_id: 'work-1', role: 'assistant', status: 'running', model_id: 'hermes-read-only', created_at: 1, parts: [],
    }]);
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });

    render(<HermesAssistantPanel />);
    fireEvent.change(await screen.findByRole('combobox', { name: 'Phiên trao đổi trợ lý' }), { target: { value: 'thread-1' } });
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    await act(async () => {
      FakeEventSource.instances[0].emit('token', { text: 'Đang tổng hợp tiến độ.', assistant_turn_id: 'turn-running' });
    });
    expect(await screen.findByText('Đang tổng hợp tiến độ.')).toBeDefined();
    vi.unstubAllGlobals();
  });

  it('ignores a token for another turn and cancels only the running turn shown', async () => {
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      listeners = new Map<string, (event: MessageEvent) => void>();
      constructor(_url: string) { FakeEventSource.instances.push(this); }
      addEventListener(type: string, listener: (event: MessageEvent) => void) { this.listeners.set(type, listener); }
      close() {}
      emit(type: string, data: unknown) { this.listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent); }
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([{ id: 'thread-1', title: 'Trao đổi A', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 1 }]);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([{ id: 'turn-running', thread_id: 'thread-1', work_id: 'work-1', role: 'assistant', status: 'running', model_id: 'hermes-read-only', created_at: 1, parts: [] }]);
    vi.mocked(assistantApi.cancelAssistantTurn).mockResolvedValue({ id: 'turn-running', thread_id: 'thread-1', work_id: 'work-1', role: 'assistant', status: 'cancelled', model_id: 'hermes-read-only', created_at: 1, completed_at: 2, parts: [{ id: 'cancel-part', part_type: 'error', content: { title: 'Đã hủy', message: 'Bạn đã hủy phản hồi này.' }, sort_order: 0 }] });
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });

    render(<HermesAssistantPanel />);
    fireEvent.change(await screen.findByRole('combobox', { name: 'Phiên trao đổi trợ lý' }), { target: { value: 'thread-1' } });
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    await act(async () => {
      FakeEventSource.instances[0].emit('token', { text: 'Sai turn', assistant_turn_id: 'turn-other' });
    });
    expect(screen.queryByText('Sai turn')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Hủy phản hồi' }));
    await waitFor(() => expect(assistantApi.cancelAssistantTurn).toHaveBeenCalledWith('turn-running'));
    expect(await screen.findByText('Bạn đã hủy phản hồi này.')).toBeDefined();
    vi.unstubAllGlobals();
  });

  it('reopens the thread stream after a terminal event so the next prompt can stream', async () => {
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      listeners = new Map<string, (event: MessageEvent) => void>();
      constructor(_url: string) { FakeEventSource.instances.push(this); }
      addEventListener(type: string, listener: (event: MessageEvent) => void) { this.listeners.set(type, listener); }
      close() {}
      emit(type: string, data: unknown) { this.listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent); }
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([{ id: 'thread-1', title: 'Trao đổi A', work_id: 'work-1', conversation_id: 'conversation-1', status: 'active', created_at: 1, updated_at: 1 }]);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([]);
    useHermesStore.setState({ sessions: [{ id: 'work-1', title: 'Công việc A', workspace_path: 'managed', created_at: 1 }], activeSessionId: 'work-1' });

    render(<HermesAssistantPanel />);
    fireEvent.change(await screen.findByRole('combobox', { name: 'Phiên trao đổi trợ lý' }), { target: { value: 'thread-1' } });
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    await act(async () => {
      FakeEventSource.instances[0].emit('done', { assistant_turn_id: 'turn-1' });
    });
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    vi.unstubAllGlobals();
  });
});
