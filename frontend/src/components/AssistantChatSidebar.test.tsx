import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssistantChatSidebar } from './AssistantChatSidebar';
import { useHermesStore } from '../store/store';
import * as assistantApi from '../api/assistant';
import * as worksApi from '../api/works';
import * as actionPackagesApi from '../api/actionPackages';
import * as marketplaceApi from '../api/marketplace';
import { ApiError } from '../api/client';

// Local enabled check that does not depend on @testing-library/jest-dom matchers.
const waitForEnabled = (el: HTMLElement) =>
  waitFor(() => expect((el as any).disabled).toBe(false));

vi.mock('../api/assistant', () => ({
  resolveWorkConversationAssistantThread: vi.fn(),
  createAssistantRun: vi.fn(),
  getAssistantTurns: vi.fn().mockResolvedValue([]),
  listAssistantThreads: vi.fn().mockResolvedValue([]),
  cancelAssistantTurn: vi.fn(),
  retryAssistantTurn: vi.fn(),
  getAssistantContextManifest: vi.fn().mockResolvedValue(null),
}));

vi.mock('../api/works', () => ({
  createConversation: vi.fn(),
  listConversations: vi.fn().mockResolvedValue([]),
  getWorkMemoryContext: vi.fn().mockResolvedValue(null),
}));

vi.mock('../api/marketplace', () => ({
  getModelConfig: vi.fn().mockResolvedValue({ models: [], providers: [] }),
}));

vi.mock('../api/actionPackages', () => ({
  createActionPackage: vi.fn(),
  getWorkActionPackages: vi.fn().mockResolvedValue([]),
  getActionPackage: vi.fn(),
  approveActionPackage: vi.fn(),
  denyActionPackage: vi.fn(),
}));

vi.mock('../api/runtime', () => ({
  getRuntimeIdentityScope: vi.fn().mockResolvedValue({ identity_scope: 'identity-test', workspace_scope: 'local' }),
}));

vi.mock('./assistant/TurnPartRenderer', () => ({
  TurnPartRenderer: ({ part }: { part: assistantApi.AssistantPart }) => <span>{String(part.content.text ?? '')}</span>,
  AssistantTurnCard: ({ turn, streamedText }: { turn: { id: string; parts: assistantApi.AssistantPart[] }; streamedText?: string }) => {
    const text = turn.parts?.find(p => p.content?.text)?.content?.text;
    return <div data-testid="turn-card"><span>{String(text ?? '')}</span><span data-testid="streamed">{streamedText ?? ''}</span></div>;
  },
}));

const WORK_A = { id: 'work-a', title: 'Work A', workspace_path: 'C:/a', created_at: 1, updated_at: 1 };
const WORK_B = { id: 'work-b', title: 'Work B', workspace_path: 'C:/b', created_at: 2, updated_at: 2 };
const CONV_A1 = { id: 'conv-a1', session_id: 'work-a', title: 'A1', status: 'active' as const, created_at: 1, updated_at: 2, message_count: 0 };
const CONV_A2 = { id: 'conv-a2', session_id: 'work-a', title: 'A2', status: 'active' as const, created_at: 2, updated_at: 1, message_count: 0 };
const CONV_B1 = { id: 'conv-b1', session_id: 'work-b', title: 'B1', status: 'active' as const, created_at: 3, updated_at: 3, message_count: 0 };

const promptValue = { target: { value: 'test prompt' } };

// Renders the sidebar with given Work/Conversations/Threads and waits for conversation to auto-select.
async function setupSidebarAsync(params: {
  work?: typeof WORK_A;
  conversations?: any[];
  threads?: assistantApi.AssistantThread[];
} = {}) {
  const { work = WORK_A, conversations = [CONV_A1], threads = [] } = params;
  useHermesStore.setState({
    sessions: work ? [work] : [],
    activeSessionId: work ? work.id : null,
    assistantSidebarMode: 'expanded',
    assistantSidebarWidth: 380,
  });
  vi.mocked(worksApi.listConversations).mockResolvedValue(conversations);
  vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue(threads);
  render(<AssistantChatSidebar />);
  await waitFor(() => expect(worksApi.listConversations).toHaveBeenCalled(), { timeout: 1500 });
  const conversationSelect = await screen.findByRole('combobox', { name: 'Cuộc trao đổi' });
  const expectedConversationId = conversations[0]?.id ?? '';
  await waitFor(() => expect((conversationSelect as HTMLSelectElement).value).toBe(expectedConversationId));
  const textarea = await screen.findByPlaceholderText('Giao yêu cầu cho GYO...');
  await waitFor(() => expect((textarea as HTMLTextAreaElement).disabled).toBe(false));
  return { textarea, conversationSelect: conversationSelect as HTMLSelectElement };
}

describe('AssistantChatSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    vi.mocked(worksApi.listConversations).mockResolvedValue([]);
    vi.mocked(assistantApi.listAssistantThreads).mockResolvedValue([]);
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([]);
    vi.mocked(assistantApi.createAssistantRun).mockResolvedValue([]);
    vi.mocked(assistantApi.getAssistantContextManifest).mockResolvedValue(null as any);
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread).mockResolvedValue(null as any);
    vi.mocked(worksApi.createConversation).mockResolvedValue(null as any);
    vi.mocked(worksApi.getWorkMemoryContext).mockResolvedValue(null as any);
    useHermesStore.setState({
      sessions: [],
      activeSessionId: null,
      assistantSidebarMode: 'collapsed',
      assistantSidebarWidth: 380,
    });
  });

  afterEach(() => {
    cleanup();
    window.sessionStorage.clear();
  });

  it('renders collapsed and expands without creating a Work-scoped thread', async () => {
    render(<AssistantChatSidebar />);

    const expandButton = screen.getByRole('button', { name: 'Mở rộng Trợ lý GYO' });
    fireEvent.click(expandButton);

    expect(await screen.findByRole('button', { name: 'Thu gọn' })).toBeDefined();
    expect(screen.queryByRole('button', { name: 'Ẩn Trợ lý' })).toBeNull();
    await waitFor(() => expect(assistantApi.listAssistantThreads).toHaveBeenCalled());
    expect(assistantApi.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    expect(assistantApi.createAssistantRun).not.toHaveBeenCalled();
  });

  it('renders the same assistant surface in focus mode without the drawer shell', async () => {
    render(<AssistantChatSidebar surfaceMode="focus" />);

    expect((await screen.findByRole('region', { name: 'Trợ lý GYO' })).getAttribute('data-gyo-mode')).toBe('focus');
    expect(document.querySelector('.assistant-sidebar')).toBeNull();
  });

  it('collapses the assistant when Escape is pressed', async () => {
    useHermesStore.setState({ assistantSidebarMode: 'expanded' });
    render(<AssistantChatSidebar />);
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(useHermesStore.getState().assistantSidebarMode).toBe('collapsed'));
    expect(screen.getByRole('button', { name: 'Mở rộng Trợ lý GYO' })).toBeDefined();
  });

  it('keeps onboarding in the chat area until a conversation is selected', async () => {
    useHermesStore.setState({
      sessions: [WORK_A],
      activeSessionId: WORK_A.id,
      assistantSidebarMode: 'expanded',
    });
    vi.mocked(worksApi.listConversations).mockResolvedValue([]);

    render(<AssistantChatSidebar />);

    expect(await screen.findByText('Chọn cuộc trao đổi', { exact: true })).toBeDefined();
    expect(screen.getByText('Tạo hoặc chọn một cuộc trao đổi để bắt đầu với GYO.')).toBeDefined();
    expect(screen.queryByText(/Trao đổi với GYO \(/)).toBeNull();
  });

  it('does not request a Conversation from the previous Work while switching scope', async () => {
    const conversationA = { id: 'conversation-a', session_id: 'work-a', title: 'A', status: 'active' as const, created_at: 1, updated_at: 1, message_count: 0 };
    const conversationB = { id: 'conversation-b', session_id: 'work-b', title: 'B', status: 'active' as const, created_at: 2, updated_at: 2, message_count: 0 };
    let resolveWorkB!: (value: typeof conversationB[]) => void;
    const workBConversations = new Promise<typeof conversationB[]>(resolve => { resolveWorkB = resolve; });
    vi.mocked(worksApi.listConversations)
      .mockResolvedValueOnce([conversationA])
      .mockReturnValueOnce(workBConversations);
    useHermesStore.setState({
      sessions: [
        { id: 'work-a', title: 'Work A', workspace_path: 'C:/a', created_at: 1 },
        { id: 'work-b', title: 'Work B', workspace_path: 'C:/b', created_at: 2 },
      ],
      activeSessionId: 'work-a',
      assistantSidebarMode: 'expanded',
    });

    render(<AssistantChatSidebar />);
    await waitFor(() => expect(assistantApi.getAssistantContextManifest).toHaveBeenCalledWith(
      'work-a', 'conversation-a', null, expect.any(AbortSignal),
    ));

    act(() => useHermesStore.getState().setActiveSession('work-b'));
    await waitFor(() => expect(assistantApi.getAssistantContextManifest).toHaveBeenCalledWith(
      'work-b', null, null, expect.any(AbortSignal),
    ));
    expect(vi.mocked(assistantApi.getAssistantContextManifest).mock.calls.some(
      ([workId, conversationId]) => workId === 'work-b' && conversationId === 'conversation-a',
    )).toBe(false);

    await act(async () => { resolveWorkB([conversationB]); });
    await waitFor(() => expect(assistantApi.getAssistantContextManifest).toHaveBeenCalledWith(
      'work-b', 'conversation-b', null, expect.any(AbortSignal),
    ));
  });

  it('reuses active thread for the correct scope without creating Conversation', async () => {
    const activeThread: assistantApi.AssistantThread = { id: 'thread-1', title: 'T1', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    const { textarea } = await setupSidebarAsync({ threads: [activeThread] });
    fireEvent.change(textarea, promptValue);
    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
    fireEvent.click(sendBtn);

    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith(
      'thread-1', 'test prompt', 'work-a', 'conv-a1', [],
      expect.objectContaining({ routeMode: 'auto' }),
    ));
    expect(assistantApi.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    expect(worksApi.createConversation).not.toHaveBeenCalled();
  });

  it('keeps the prompt and reports a scope/run conflict without creating another Conversation or retrying after run 409', async () => {
    const activeThread: assistantApi.AssistantThread = { id: 'thread-409', title: 'T1', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    vi.mocked(assistantApi.getAssistantTurns).mockResolvedValue([{ id: 'turn-persisted', thread_id: 'thread-409', work_id: 'work-a', conversation_id: 'conv-a1', role: 'assistant', status: 'completed', created_at: 1, parts: [{ id: 'part-persisted', part_type: 'text', content: { text: 'PERSISTED_TIMELINE' }, sort_order: 0 }] }]);
    const { textarea } = await setupSidebarAsync({ threads: [activeThread] });
    vi.mocked(assistantApi.createAssistantRun).mockRejectedValue(new ApiError(409, 'conversation is archived'));
    await waitFor(() => expect(assistantApi.getAssistantTurns).toHaveBeenCalledWith('thread-409'));
    expect(await screen.findByText('PERSISTED_TIMELINE')).toBeDefined();
    fireEvent.change(textarea, promptValue);
    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
    fireEvent.click(sendBtn);

    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith(
      'thread-409', 'test prompt', 'work-a', 'conv-a1', [], expect.any(Object),
    ));
    expect(await screen.findByText(/phạm vi hoặc trạng thái chạy/i)).toBeDefined();
    expect((textarea as HTMLTextAreaElement).value).toBe('test prompt');
    expect(screen.getByRole('alert').textContent).toMatch(/phạm vi hoặc trạng thái chạy/i);
    expect(await screen.findByText('PERSISTED_TIMELINE')).toBeDefined();
    expect(assistantApi.createAssistantRun).toHaveBeenCalledTimes(1);
    expect(assistantApi.listAssistantThreads).toHaveBeenCalledTimes(1);
    expect(assistantApi.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    expect(worksApi.createConversation).not.toHaveBeenCalled();
    expect(actionPackagesApi.createActionPackage).not.toHaveBeenCalled();
  });

  it('does not restore a stale 409 draft or notice after returning to the same scope', async () => {
    const activeThread: assistantApi.AssistantThread = { id: 'thread-stale-409', title: 'T1', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    let rejectRun!: (reason: unknown) => void;
    const pendingRun = new Promise<assistantApi.AssistantTurn[]>((_, reject) => { rejectRun = reject; });
    const { textarea, conversationSelect } = await setupSidebarAsync({ threads: [activeThread] });
    vi.mocked(assistantApi.createAssistantRun).mockReturnValue(pendingRun);
    vi.mocked(worksApi.listConversations).mockImplementation(async workId => workId === 'work-b' ? [CONV_B1] : [CONV_A1]);
    act(() => useHermesStore.setState({ sessions: [WORK_A, WORK_B] }));

    fireEvent.change(textarea, promptValue);
    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
    fireEvent.click(sendBtn);
    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledTimes(1));

    act(() => useHermesStore.getState().setActiveSession('work-b'));
    await waitFor(() => expect(conversationSelect.value).toBe('conv-b1'));
    act(() => useHermesStore.getState().setActiveSession('work-a'));
    await waitFor(() => expect(conversationSelect.value).toBe('conv-a1'));

    await act(async () => { rejectRun(new ApiError(409, 'conversation is archived')); });
    await waitFor(() => expect((screen.getByPlaceholderText('Giao yêu cầu cho GYO...') as HTMLTextAreaElement).value).toBe(''));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(assistantApi.createAssistantRun).toHaveBeenCalledTimes(1);
    expect(assistantApi.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    expect(worksApi.createConversation).not.toHaveBeenCalled();
    expect(actionPackagesApi.createActionPackage).not.toHaveBeenCalled();
  });

  it('removes only stale A persistence and preserves B draft, model, and attachment UI in the same Work', async () => {
    const activeThreadA: assistantApi.AssistantThread = {
      id: 'thread-a', title: 'A', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1,
    };
    const activeThreadB: assistantApi.AssistantThread = {
      id: 'thread-b', title: 'B', work_id: 'work-a', conversation_id: 'conv-a2', status: 'active', created_at: 2, updated_at: 2,
    };
    let rejectRun!: (reason: unknown) => void;
    const pendingRun = new Promise<assistantApi.AssistantTurn[]>((_, reject) => { rejectRun = reject; });
    vi.mocked(assistantApi.createAssistantRun).mockReturnValue(pendingRun);
    vi.mocked(marketplaceApi.getModelConfig).mockResolvedValue({
      providers: [{ id: 'provider-1', display_name: 'Nhà cung cấp', enabled: true }],
      models: [{ id: 'model-b', display_name: 'Model B', provider_profile_id: 'provider-1', enabled: true, capabilities: ['chat'], is_default: false, cost_class: 'free' }],
    } as any);

    const { textarea, conversationSelect } = await setupSidebarAsync({
      threads: [activeThreadA, activeThreadB],
      conversations: [CONV_A1, CONV_A2],
    });
    fireEvent.change(textarea, { target: { value: 'Nháp A đang gửi' } });
    await waitFor(() => expect(window.sessionStorage.getItem('gyo:draft:v2:identity-test:local:work-a:conv-a1')).toContain('Nháp A đang gửi'));

    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
    fireEvent.click(sendBtn);
    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledTimes(1));

    fireEvent.change(conversationSelect, { target: { value: 'conv-a2' } });
    await waitFor(() => expect(conversationSelect.value).toBe('conv-a2'));
    const textareaB = await screen.findByPlaceholderText('Giao yêu cầu cho GYO...');
    fireEvent.change(textareaB, { target: { value: 'Nháp B giữ nguyên' } });
    const modelSelect = await screen.findByRole('combobox', { name: 'Chọn model xử lý' });
    fireEvent.change(modelSelect, { target: { value: 'model-b' } });
    const attachmentToggle = screen.getByRole('button', { name: 'Mở thùng tệp ngữ cảnh GYO' });
    fireEvent.click(attachmentToggle);
    await waitFor(() => expect(window.sessionStorage.getItem('gyo:draft:v2:identity-test:local:work-a:conv-a2')).toContain('Nháp B giữ nguyên'));

    await act(async () => { rejectRun(new ApiError(409, 'conversation is archived')); });
    await waitFor(() => expect(window.sessionStorage.getItem('gyo:draft:v2:identity-test:local:work-a:conv-a1')).toBeNull());

    const draftB = window.sessionStorage.getItem('gyo:draft:v2:identity-test:local:work-a:conv-a2');
    expect(draftB).toContain('Nháp B giữ nguyên');
    expect(draftB).toContain('model-b');
    expect((screen.getByPlaceholderText('Giao yêu cầu cho GYO...') as HTMLTextAreaElement).value).toBe('Nháp B giữ nguyên');
    expect((modelSelect as HTMLSelectElement).value).toBe('model-b');
    expect(screen.getByRole('button', { name: 'Đóng thùng tệp ngữ cảnh GYO' })).toBeDefined();
    expect(screen.getByLabelText('Tệp ngữ cảnh GYO').textContent).toContain('Tệp GYO sẽ dùng làm ngữ cảnh (0)');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(assistantApi.createAssistantRun).toHaveBeenCalledTimes(1);
    expect(assistantApi.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    expect(actionPackagesApi.createActionPackage).not.toHaveBeenCalled();
  });

  it('resolves canonical thread on first submit when no thread exists yet', async () => {
    const resolvedThread: assistantApi.AssistantThread = { id: 'thread-resolved', title: 'T2', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread).mockResolvedValue(resolvedThread);
    const { textarea } = await setupSidebarAsync();
    fireEvent.change(textarea, promptValue);
    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
    fireEvent.click(sendBtn);

    await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conv-a1'));
    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith('thread-resolved', 'test prompt', 'work-a', 'conv-a1', [], expect.any(Object)));
    expect(worksApi.createConversation).not.toHaveBeenCalled();
  });

  it('single-flight: double-submit creates at most one resolver and one run call', async () => {
    const resolvedThread: assistantApi.AssistantThread = { id: 'thread-single', title: 'T', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    let resolveResolver!: (value: assistantApi.AssistantThread) => void;
    let resolverSettled = false;
    const resolverPromise = new Promise<assistantApi.AssistantThread>(resolve => { resolveResolver = resolve; });
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread).mockReturnValue(resolverPromise as any);

    try {
      const { textarea } = await setupSidebarAsync();
      fireEvent.change(textarea, promptValue);
      const sendBtn = screen.getByRole('button', { name: /Gửi/i });
      await waitForEnabled(sendBtn);

      fireEvent.click(sendBtn);
      fireEvent.click(sendBtn);

      await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledTimes(1));
      expect(assistantApi.createAssistantRun).not.toHaveBeenCalled();

      await act(async () => { resolveResolver(resolvedThread); resolverSettled = true; });
      await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledTimes(1));
      expect(worksApi.createConversation).not.toHaveBeenCalled();
    } finally {
      if (!resolverSettled) await act(async () => { resolveResolver(resolvedThread); });
    }
  });

  it('does not reuse archived threads; resolves a fresh active thread instead', async () => {
    const archivedThread: assistantApi.AssistantThread = { id: 'thread-archived', title: 'T', work_id: 'work-a', conversation_id: 'conv-a1', status: 'archived', created_at: 1, updated_at: 1 };
    const wrongScopeThread: assistantApi.AssistantThread = { id: 'thread-wrong-scope', title: 'Wrong', work_id: 'work-b', conversation_id: 'conv-b1', status: 'active', created_at: 1, updated_at: 1 };
    const resolvedThread: assistantApi.AssistantThread = { id: 'thread-new', title: 'T', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 2, updated_at: 2 };
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread).mockResolvedValue(resolvedThread);
    const { textarea } = await setupSidebarAsync({ threads: [archivedThread, wrongScopeThread] });
    fireEvent.change(textarea, promptValue);
    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
    fireEvent.click(sendBtn);

    await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith('thread-new', 'test prompt', 'work-a', 'conv-a1', [], expect.any(Object)));
    expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conv-a1');
  });

  it('discards stale resolver result when Work scope changes during pending resolution', async () => {
    const staleThread: assistantApi.AssistantThread = { id: 'thread-stale-a1', title: 'Stale A1 thread', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    const freshThreadB: assistantApi.AssistantThread = { id: 'thread-fresh-b1', title: 'Fresh B1 thread', work_id: 'work-b', conversation_id: 'conv-b1', status: 'active', created_at: 2, updated_at: 2 };
    let resolveStale!: (value: assistantApi.AssistantThread) => void;
    let staleSettled = false;
    const staleResolver = new Promise<assistantApi.AssistantThread>(resolve => { resolveStale = resolve; });
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread)
      .mockReturnValueOnce(staleResolver as any)
      .mockResolvedValueOnce(freshThreadB);
    vi.mocked(assistantApi.getAssistantTurns).mockImplementation(async thread => thread === staleThread.id ? [{
      id: 'turn-stale-a1', thread_id: staleThread.id, work_id: 'work-a', conversation_id: 'conv-a1', role: 'assistant', status: 'completed', created_at: 1,
      parts: [{ id: 'part-stale-a1', part_type: 'text', content: { text: 'STALE_A1_TURN' }, sort_order: 0 }],
    }] : []);

    try {
      const { textarea, conversationSelect } = await setupSidebarAsync({ work: WORK_A, conversations: [CONV_A1] });
      act(() => useHermesStore.setState({ sessions: [WORK_A, WORK_B] }));
      vi.mocked(worksApi.listConversations).mockImplementation(async workId => workId === 'work-b' ? [CONV_B1] : [CONV_A1]);

      fireEvent.change(textarea, { target: { value: 'A1 pending' } });
      const sendBtn = screen.getByRole('button', { name: /Gửi/i });
      await waitForEnabled(sendBtn);
      fireEvent.click(sendBtn);
      await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conv-a1'));

      act(() => useHermesStore.getState().setActiveSession('work-b'));
      await waitFor(() => expect(worksApi.listConversations).toHaveBeenCalledWith('work-b'));
      await waitFor(() => expect(conversationSelect.value).toBe('conv-b1'));

      await act(async () => { resolveStale(staleThread); staleSettled = true; });
      const textareaB = await screen.findByPlaceholderText('Giao yêu cầu cho GYO...');
      await waitFor(() => expect((textareaB as HTMLTextAreaElement).value).toBe(''));

      expect(assistantApi.createAssistantRun).not.toHaveBeenCalled();
      expect(assistantApi.getAssistantTurns).not.toHaveBeenCalledWith(staleThread.id);
      expect(screen.queryByText('Stale A1 thread')).toBeNull();
      expect(screen.queryByText('STALE_A1_TURN')).toBeNull();

      fireEvent.change(textareaB, { target: { value: 'B1 fresh' } });
      const sendBtnB = screen.getByRole('button', { name: /Gửi/i });
      await waitForEnabled(sendBtnB);
      fireEvent.click(sendBtnB);
      await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-b', 'conv-b1'));
      await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith('thread-fresh-b1', 'B1 fresh', 'work-b', 'conv-b1', [], expect.any(Object)));
      expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledTimes(2);
      expect(assistantApi.getAssistantTurns).not.toHaveBeenCalledWith(staleThread.id);
    } finally {
      if (!staleSettled) await act(async () => { resolveStale(staleThread); });
    }
  });

  it('discards stale result when Conversation scope changes during pending resolution', async () => {
    const staleThread: assistantApi.AssistantThread = { id: 'thread-stale-a1-conv', title: 'Stale conversation A1 thread', work_id: 'work-a', conversation_id: 'conv-a1', status: 'active', created_at: 1, updated_at: 1 };
    const freshThreadA2: assistantApi.AssistantThread = { id: 'thread-fresh-a2', title: 'Fresh A2 thread', work_id: 'work-a', conversation_id: 'conv-a2', status: 'active', created_at: 2, updated_at: 2 };
    let resolveStale!: (value: assistantApi.AssistantThread) => void;
    let staleSettled = false;
    const staleResolver = new Promise<assistantApi.AssistantThread>(resolve => { resolveStale = resolve; });
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread)
      .mockReturnValueOnce(staleResolver as any)
      .mockResolvedValueOnce(freshThreadA2);
    vi.mocked(assistantApi.getAssistantTurns).mockImplementation(async thread => thread === staleThread.id ? [{
      id: 'turn-stale-conv-a1', thread_id: staleThread.id, work_id: 'work-a', conversation_id: 'conv-a1', role: 'assistant', status: 'completed', created_at: 1,
      parts: [{ id: 'part-stale-conv-a1', part_type: 'text', content: { text: 'STALE_CONV_A1_TURN' }, sort_order: 0 }],
    }] : []);

    try {
      const { textarea, conversationSelect } = await setupSidebarAsync({ work: WORK_A, conversations: [CONV_A1, CONV_A2] });
      fireEvent.change(textarea, { target: { value: 'A1 pending' } });
      const sendBtn = screen.getByRole('button', { name: /Gửi/i });
      await waitForEnabled(sendBtn);
      fireEvent.click(sendBtn);
      await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conv-a1'));

      expect(conversationSelect.value).toBe('conv-a1');
      fireEvent.change(conversationSelect, { target: { value: 'conv-a2' } });
      await waitFor(() => expect(conversationSelect.value).toBe('conv-a2'));

      await act(async () => { resolveStale(staleThread); staleSettled = true; });
      const textareaA2 = await screen.findByPlaceholderText('Giao yêu cầu cho GYO...');
      await waitFor(() => expect((textareaA2 as HTMLTextAreaElement).value).toBe(''));

      expect(assistantApi.createAssistantRun).not.toHaveBeenCalled();
      expect(assistantApi.getAssistantTurns).not.toHaveBeenCalledWith(staleThread.id);
      expect(screen.queryByText('Stale conversation A1 thread')).toBeNull();
      expect(screen.queryByText('STALE_CONV_A1_TURN')).toBeNull();

      fireEvent.change(textareaA2, { target: { value: 'A2 fresh' } });
      const sendBtnA2 = screen.getByRole('button', { name: /Gửi/i });
      await waitForEnabled(sendBtnA2);
      fireEvent.click(sendBtnA2);
      await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conv-a2'));
      await waitFor(() => expect(assistantApi.createAssistantRun).toHaveBeenCalledWith('thread-fresh-a2', 'A2 fresh', 'work-a', 'conv-a2', [], expect.any(Object)));
      expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledTimes(2);
      expect(assistantApi.getAssistantTurns).not.toHaveBeenCalledWith(staleThread.id);
    } finally {
      if (!staleSettled) await act(async () => { resolveStale(staleThread); });
    }
  });

  it('composer enabled when Work + Conversation selected but no thread exists yet', async () => {
    const { textarea, conversationSelect } = await setupSidebarAsync();
    expect(conversationSelect.value).toBe('conv-a1');
    expect((textarea as HTMLTextAreaElement).disabled).toBe(false);
    fireEvent.change(textarea, { target: { value: 'ready to send' } });
    const sendBtn = screen.getByRole('button', { name: /Gửi/i });
    await waitForEnabled(sendBtn);
  });

  it('"Cuộc trao đổi mới" creates exactly one Conversation and one bound thread', async () => {
    const createdConv = { id: 'conv-new', session_id: 'work-a', title: 'Trao đổi: Work A', status: 'active' as const, created_at: 1, updated_at: 1, message_count: 0 };
    const createdThread: assistantApi.AssistantThread = { id: 'thread-new-conv', title: 'T', work_id: 'work-a', conversation_id: 'conv-new', status: 'active', created_at: 1, updated_at: 1 };
    vi.mocked(worksApi.createConversation).mockResolvedValue(createdConv);
    vi.mocked(assistantApi.resolveWorkConversationAssistantThread).mockResolvedValue(createdThread);
    await setupSidebarAsync();

    const newBtn = screen.getByRole('button', { name: /Cuộc trao đổi mới/i });
    await waitForEnabled(newBtn);
    fireEvent.click(newBtn);

    await waitFor(() => expect(worksApi.createConversation).toHaveBeenCalledTimes(1));
    expect(worksApi.createConversation).toHaveBeenCalledWith('work-a', expect.stringContaining('Trao đổi'));
    await waitFor(() => expect(assistantApi.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conv-new'));
    expect(assistantApi.createAssistantRun).not.toHaveBeenCalled();
  });

  it('opening sidebar and selecting Conversation does not create thread or run', async () => {
    const { conversationSelect } = await setupSidebarAsync();
    await waitFor(() => expect(assistantApi.listAssistantThreads).toHaveBeenCalled());
    // Re-selecting the same conversation should not trigger resolver/run
    expect(conversationSelect.value).toBe('conv-a1');
    fireEvent.change(conversationSelect, { target: { value: 'conv-a1' } });
    await waitFor(() => expect(assistantApi.listAssistantThreads).toHaveBeenCalled());
    expect(assistantApi.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    expect(assistantApi.createAssistantRun).not.toHaveBeenCalled();
  });
});
