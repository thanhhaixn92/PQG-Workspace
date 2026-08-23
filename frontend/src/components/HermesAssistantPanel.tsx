import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Archive, ArchiveRestore, Bot, ChevronDown, FileText, ListChecks, MessageSquare, Paperclip, Pencil, Plus, Send, ShieldCheck, Sparkles, TriangleAlert, X } from 'lucide-react';
import {
  assistantThreadStreamUrl, cancelAssistantTurn, createAssistantRun, getAssistantContextManifest, getAssistantTurns, listAssistantThreads, resolveWorkConversationAssistantThread, retryAssistantTurn,
  updateAssistantThread, type AssistantContextManifest, type AssistantPart, type AssistantThread, type AssistantTurn,
} from '../api/assistant';
import { getOverview, type Overview } from '../api/overview';
import { approveActionPackage, createActionPackage, createActionPackageIdempotencyKey, denyActionPackage, getActionPackageDecisionBinding, getWorkActionPackages, type ActionPackage, type ActionPackageProposal } from '../api/actionPackages';
import { useHermesStore } from '../store/store';
import { isTestWork } from './workTestVisibility';
import { ASSISTANT_LABEL, ASSISTANT_NAME } from '../branding';
import { listArtifacts, type Artifact } from '../api/artifacts';
import { useReviewTarget } from '../hooks/useReviewTarget';
import { AssistantTurn as AssistantTurnCard } from './assistant/AssistantTurn';
import { PageHeader } from './ui/PageHeader';
import { MetricCard } from './ui/MetricCard';
import { ContextDrawer } from './ui/ContextDrawer';
import { getModelConfig, type GyoModel, type GyoProvider } from '../api/marketplace';
import { createConversation, getPlan, getWorkMemoryContext, listConversations, updateWorkMemoryContext, type Conversation, type MemoryContextMode, type WorkMemoryContext, type WorkPlanPhase } from '../api/works';
import { ApiError } from '../api/client';
export { TurnPartRenderer } from './assistant/TurnPartRenderer';

const dateText = (timestamp?: number | null) => timestamp
  ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(timestamp * 1000)
  : '';

const actionStatusLabel: Record<string, string> = {
  awaiting_approval: 'Chờ bạn duyệt', approved: 'Đã duyệt, đang chuẩn bị', executing: 'Đang thực hiện',
  succeeded: 'Đã hoàn tất', partially_failed: 'Hoàn tất một phần', failed: 'Không hoàn tất', cancelled: 'Đã từ chối hoặc hủy',
};

const actionImpact = (item: ActionPackage) => item.steps.some(step => step.risk_level === 'external_or_destructive')
  ? 'Có bước có thể tác động bên ngoài hoặc khó hoàn tác.'
  : 'Chỉ cập nhật nội dung hoặc trạng thái của Công việc đã chọn.';

const MOBILE_VIEWPORT = '(max-width: 768px)';

function useMobileViewport() {
  const [isMobile, setIsMobile] = useState(() => (
    typeof window !== 'undefined' && typeof window.matchMedia === 'function'
      ? window.matchMedia(MOBILE_VIEWPORT).matches
      : false
  ));

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const mediaQuery = window.matchMedia(MOBILE_VIEWPORT);
    const update = () => setIsMobile(mediaQuery.matches);
    update();
    mediaQuery.addEventListener('change', update);
    return () => mediaQuery.removeEventListener('change', update);
  }, []);

  return isMobile;
}

function textFrom(content: Record<string, unknown>, keys: string[], fallback: string): string {
  for (const key of keys) {
    const value = content[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return fallback;
}

function ContextItems({ items, empty }: { items?: Array<Record<string, unknown>>; empty: string }) {
  if (!items?.length) return <li>{empty}</li>;
  return <>{items.map((item, index) => <li key={index}><strong>{textFrom(item, ['title', 'kind'], 'Nguồn')}</strong><span>{textFrom(item, ['reason'], '')}</span></li>)}</>;
}

export const HermesAssistantPanel: React.FC = () => {
  const keepHermesReviewTarget = useCallback((_source: string) => undefined, []);
  useReviewTarget(keepHermesReviewTarget);
  const sessions = useHermesStore(state => state.sessions);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const setActiveTab = useHermesStore(state => state.setSidebarTab);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [threads, setThreads] = useState<AssistantThread[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [manifest, setManifest] = useState<AssistantContextManifest | null>(null);
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [creatingThread, setCreatingThread] = useState(false);
  const [editingThread, setEditingThread] = useState(false);
  const [threadTitle, setThreadTitle] = useState('');
  const [updatingThread, setUpdatingThread] = useState(false);
  const [showArchivedThreads, setShowArchivedThreads] = useState(false);
  const [contextOpen, setContextOpen] = useState(false);
  const [streamedText, setStreamedText] = useState<Record<string, string>>({});
  const [streamRevision, setStreamRevision] = useState(0);
  const [actionPackages, setActionPackages] = useState<ActionPackage[]>([]);
  const [actionsError, setActionsError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [proposalBusy, setProposalBusy] = useState<string | null>(null);
  const [createdProposals, setCreatedProposals] = useState<Record<string, string>>({});
  const [availableArtifacts, setAvailableArtifacts] = useState<Artifact[]>([]);
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);
  const [modelChoice, setModelChoice] = useState<string>('auto');
  const [availableModels, setAvailableModels] = useState<GyoModel[]>([]);
  const [modelProviders, setModelProviders] = useState<GyoProvider[]>([]);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [threadError, setThreadError] = useState<string | null>(null);
  const [planPhases, setPlanPhases] = useState<WorkPlanPhase[]>([]);
  const [planStepId, setPlanStepId] = useState<string>('');
  const [memoryContext, setMemoryContext] = useState<WorkMemoryContext | null>(null);
  const [memoryContextBusy, setMemoryContextBusy] = useState(false);
  const contextTriggerRef = useRef<HTMLButtonElement>(null);
  const isMobileViewport = useMobileViewport();
  const requestGeneration = useRef(0);
  const selectedThreadRef = useRef<string | null>(null);
  const turnsRef = useRef<AssistantTurn[]>([]);
  const actionsGeneration = useRef(0);
  const artifactsGeneration = useRef(0);

  useEffect(() => { selectedThreadRef.current = threadId; }, [threadId]);
  useEffect(() => { turnsRef.current = turns; }, [turns]);

  const visibleWorks = useMemo(() => sessions.filter(work => !isTestWork(work)), [sessions]);
  const selectedWork = useMemo(() => visibleWorks.find(work => work.id === activeSessionId) ?? null, [activeSessionId, visibleWorks]);
  const selectedConversation = useMemo(() => conversations.find(item => item.id === conversationId && item.status === 'active') ?? null, [conversationId, conversations]);
  const planSteps = useMemo(() => planPhases.flatMap(phase => phase.steps.map(step => ({ ...step, phaseTitle: phase.title }))), [planPhases]);
  const visibleThreads = useMemo(() => selectedWork
    && selectedConversation
    ? threads.filter(thread => thread.work_id === selectedWork.id && thread.conversation_id === selectedConversation.id && (showArchivedThreads || thread.status === 'active'))
    : [], [selectedConversation, selectedWork, showArchivedThreads, threads]);

  const loadThread = useCallback(async (id: string) => {
    if (!id) return;
    const generation = ++requestGeneration.current;
    setThreadId(id);
    setEditingThread(false);
    setThreadError(null);
    try {
      const nextTurns = await getAssistantTurns(id);
      if (generation === requestGeneration.current) setTurns(nextTurns);
    } catch {
      if (generation === requestGeneration.current) setThreadError('Chưa tải được lịch sử phiên trao đổi này. Bạn có thể chọn phiên khác hoặc thử lại.');
    }
  }, []);

  const loadOverview = useCallback(async () => {
    setOverviewError(null);
    try { setOverview(await getOverview()); }
    catch { setOverviewError('Chưa tải được bản tóm tắt chung. Các phần khác vẫn có thể tiếp tục.'); }
  }, []);

  const loadThreads = useCallback(async () => {
    setThreadError(null);
    try {
      const nextThreads = await listAssistantThreads(showArchivedThreads);
      setThreads(nextThreads);
      const current = nextThreads.find(thread => thread.id === selectedThreadRef.current);
      if (current) void loadThread(current.id);
      else { setThreadId(null); setTurns([]); }
    } catch { setThreadError('Chưa tải được danh sách phiên trao đổi. Bạn có thể thử lại phần này.'); }
  }, [loadThread, showArchivedThreads]);

  const bootstrap = useCallback(() => {
    setLoading(true);
    void loadOverview().finally(() => setLoading(false));
    void loadThreads();
  }, [loadOverview, loadThreads]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);
  useEffect(() => {
    let active = true;
    void getModelConfig().then(config => {
      if (!active) return;
      setAvailableModels(config.models.filter(item => item.enabled && !item.retired_at));
      setModelProviders(config.providers.filter(item => item.enabled && !item.retired_at));
    }).catch(() => { if (active) { setAvailableModels([]); setModelProviders([]); } });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    let active = true;
    setPlanStepId(''); setPlanPhases([]); setMemoryContext(null);
    if (!activeSessionId) return () => { active = false; };
    void getPlan(activeSessionId).then(items => { if (active) setPlanPhases(items); }).catch(() => { if (active) setPlanPhases([]); });
    return () => { active = false; };
  }, [activeSessionId]);
  useEffect(() => {
    let active = true;
    requestGeneration.current += 1;
    selectedThreadRef.current = null;
    setThreadId(null); setTurns([]); setStreamedText({}); setPrompt(''); setManifest(null); setAttachmentIds([]);
    if (!activeSessionId) { setConversations([]); setConversationId(null); return () => { active = false; }; }
    void listConversations(activeSessionId).then(items => {
      if (!active) return;
      const activeItems = items.filter(item => item.status === 'active').sort((left, right) => right.updated_at - left.updated_at);
      setConversations(activeItems);
      setConversationId(current => activeItems.some(item => item.id === current) ? current : (activeItems[0]?.id ?? null));
    }).catch(() => { if (active) { setConversations([]); setConversationId(null); } });
    return () => { active = false; };
  }, [activeSessionId]);

  useEffect(() => {
    let active = true;
    setMemoryContext(null);
    if (!activeSessionId || !planStepId) return () => { active = false; };
    void getWorkMemoryContext(activeSessionId, planStepId).then(item => { if (active) setMemoryContext(item); }).catch(() => { if (active) setMemoryContext(null); });
    return () => { active = false; };
  }, [activeSessionId, planStepId]);
  useEffect(() => {
    const controller = new AbortController();
    void getAssistantContextManifest(activeSessionId, selectedConversation?.id ?? null, planStepId || null, controller.signal)
      .then(setManifest)
      .catch(error => { if ((error as Error).name !== 'AbortError') setManifest(null); });
    return () => controller.abort();
  }, [activeSessionId, planStepId, selectedConversation?.id]);
  const loadActionPackages = useCallback(async (workId?: string | null) => {
    const generation = ++actionsGeneration.current;
    if (!workId) { setActionPackages([]); setActionsError(null); return; }
    try {
      const next = await getWorkActionPackages(workId);
      if (generation !== actionsGeneration.current) return;
      setActionPackages(next);
      setActionsError(null);
    } catch {
      if (generation === actionsGeneration.current) setActionsError('Chưa tải được các đề xuất thay đổi của Công việc này.');
    }
  }, []);
  useEffect(() => { void loadActionPackages(activeSessionId); }, [activeSessionId, loadActionPackages]);
  useEffect(() => {
    const generation = ++artifactsGeneration.current;
    setAttachmentIds([]);
    if (!activeSessionId) { setAvailableArtifacts([]); return; }
    void listArtifacts(activeSessionId)
      .then(items => { if (generation === artifactsGeneration.current) setAvailableArtifacts(items); })
      .catch(() => { if (generation === artifactsGeneration.current) setAvailableArtifacts([]); });
  }, [activeSessionId]);
  useEffect(() => {
    if (!threadId || typeof EventSource === 'undefined') return;
    const subscribedThreadId = threadId;
    const stream = new EventSource(assistantThreadStreamUrl(subscribedThreadId));
    const refreshCompletedRun = () => {
      stream.close();
      if (selectedThreadRef.current === subscribedThreadId) {
        setStreamedText({});
        void loadThread(subscribedThreadId);
        setStreamRevision(current => current + 1);
      }
    };
    stream.addEventListener('token', event => {
      if (selectedThreadRef.current !== subscribedThreadId) return;
      try {
        const payload = JSON.parse(event.data) as { text?: unknown; assistant_turn_id?: unknown };
        if (typeof payload.text !== 'string' || !payload.text || typeof payload.assistant_turn_id !== 'string') return;
        setStreamedText(current => {
          const activeTurn = turnsRef.current.find(turn => turn.id === payload.assistant_turn_id && turn.role === 'assistant' && turn.status === 'running');
          return activeTurn ? { ...current, [activeTurn.id]: `${current[activeTurn.id] ?? ''}${payload.text}` } : current;
        });
      } catch { /* Ignore malformed live updates; the saved turn remains authoritative. */ }
    });
    stream.addEventListener('done', refreshCompletedRun);
    stream.addEventListener('error', refreshCompletedRun);
    return () => stream.close();
  }, [threadId, loadThread, streamRevision]);

  const createThread = async () => {
    if (creatingThread) return;
    if (!selectedWork) { setThreadError(`Chọn một Công việc trước khi tạo phiên trao đổi với ${ASSISTANT_NAME}.`); return; }
    setCreatingThread(true);
    try {
      const createdConversation = await createConversation(selectedWork.id, `Trao đổi: ${selectedWork.title}`);
      const created = await resolveWorkConversationAssistantThread(selectedWork.id, createdConversation.id);
      setConversations(current => [createdConversation, ...current.filter(item => item.id !== createdConversation.id)]);
      setConversationId(createdConversation.id);
      setThreads(current => [created, ...current]);
      setTurns([]);
      setThreadId(created.id);
      setThreadTitle(created.title);
      setEditingThread(false);
      setThreadError(null);
    } catch {
      setThreadError('Chưa tạo được phiên trao đổi. Hãy thử lại sau.');
    } finally {
      setCreatingThread(false);
    }
  };

  const selectedThread = useMemo(
    () => visibleThreads.find(thread => thread.id === threadId) ?? null,
    [threadId, visibleThreads],
  );
  const selectedThreadArchived = selectedThread?.status === 'archived';

  const beginRenameThread = () => {
    if (!selectedThread) return;
    setThreadTitle(selectedThread.title);
    setEditingThread(true);
  };

  const saveThreadTitle = async () => {
    if (!selectedThread || !threadTitle.trim() || updatingThread) return;
    const targetId = selectedThread.id;
    setUpdatingThread(true);
    try {
      const updated = await updateAssistantThread(targetId, { title: threadTitle.trim() });
      if (selectedThreadRef.current !== targetId) return;
      setThreads(current => current.map(thread => thread.id === targetId ? updated : thread));
      setThreadTitle(updated.title);
      setEditingThread(false);
      setThreadError(null);
    } catch {
      if (selectedThreadRef.current === targetId) setThreadError('Chưa đổi được tên phiên trao đổi. Hãy thử lại.');
    } finally { setUpdatingThread(false); }
  };

  const archiveThread = async () => {
    if (!selectedThread || updatingThread) return;
    if (!window.confirm(`Lưu trữ phiên “${selectedThread.title}”? Lịch sử vẫn được giữ và có thể xem lại trong phần quản lý.`)) return;
    const targetId = selectedThread.id;
    setUpdatingThread(true);
    try {
      await updateAssistantThread(targetId, { archived: true });
      if (selectedThreadRef.current !== targetId) return;
      requestGeneration.current += 1;
      selectedThreadRef.current = null;
      setThreads(current => current.filter(thread => thread.id !== targetId));
      setThreadId(null);
      setTurns([]);
      setEditingThread(false);
      setThreadTitle('');
      setThreadError(null);
    } catch {
      if (selectedThreadRef.current === targetId) setThreadError('Chưa lưu trữ được phiên trao đổi. Hãy thử lại.');
    } finally { setUpdatingThread(false); }
  };

  const restoreThread = async () => {
    if (!selectedThread || !selectedThreadArchived || updatingThread) return;
    const targetId = selectedThread.id;
    setUpdatingThread(true);
    try {
      const updated = await updateAssistantThread(targetId, { archived: false });
      setThreads(current => current.map(thread => thread.id === targetId ? updated : thread));
      setThreadError(null);
    } catch {
      setThreadError('Chưa khôi phục được phiên trao đổi. Hãy thử lại sau.');
    } finally { setUpdatingThread(false); }
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!threadId || selectedThreadArchived || !prompt.trim() || sending) return;
    const value = prompt.trim();
    setPrompt('');
    setSending(true);
    setThreadError(null);
    try {
      const manualModelId = modelChoice.startsWith('model:') ? modelChoice.slice('model:'.length) : null;
      if (!selectedWork || !selectedConversation) throw new Error('Missing Work and Conversation scope');
      const created = await createAssistantRun(threadId, value, selectedWork.id, selectedConversation.id, attachmentIds, {
        routeMode: manualModelId ? 'manual' : 'auto', modelProfileId: manualModelId, planStepId: planStepId || null,
      });
      setTurns(current => [...current, ...created]);
      setAttachmentIds([]);
    } catch {
      setPrompt(value);
      setThreadError('Chưa gửi được yêu cầu. Nội dung của bạn vẫn được giữ lại để gửi lại.');
    } finally { setSending(false); }
  };

  const saveMemoryContext = async (updates: Pick<WorkMemoryContext, 'context_mode' | 'auto_learning_enabled'>) => {
    if (!selectedWork || !planStepId || memoryContextBusy) return;
    setMemoryContextBusy(true);
    try {
      const saved = await updateWorkMemoryContext(selectedWork.id, planStepId, updates);
      setMemoryContext(saved);
      const refreshed = await getAssistantContextManifest(selectedWork.id, selectedConversation?.id ?? null, planStepId);
      setManifest(refreshed);
    } catch {
      setThreadError('Chưa lưu được phạm vi Memory Hub. Không có thay đổi nào được xác nhận.');
    } finally { setMemoryContextBusy(false); }
  };

  const applyQuickPrompt = (value: string) => {
    setPrompt(value);
    window.requestAnimationFrame(() => document.querySelector<HTMLTextAreaElement>('.assistant-composer textarea')?.focus());
  };

  const retryTurn = async (turnId: string, mode: 'same_model' | 'auto') => {
    if (sending) return;
    setSending(true);
    setThreadError(null);
    try {
      const retried = await retryAssistantTurn(turnId, mode);
      setTurns(current => [...current, retried]);
    } catch {
      setThreadError('Chưa thể gửi lại phản hồi này. Nội dung gốc vẫn được giữ nguyên và không bị gửi trùng.');
    } finally { setSending(false); }
  };

  const cancelTurn = async (turnId: string) => {
    if (sending) return;
    setSending(true);
    setThreadError(null);
    try {
      const cancelled = await cancelAssistantTurn(turnId);
      setTurns(current => current.map(turn => turn.id === turnId ? cancelled : turn));
      setStreamedText(current => {
        const { [turnId]: _discarded, ...remaining } = current;
        return remaining;
      });
    } catch {
      setThreadError('Chưa thể hủy phản hồi này. Hãy làm mới để xem trạng thái mới nhất.');
    } finally { setSending(false); }
  };

  const decideActionPackage = async (item: ActionPackage, decision: 'approve' | 'deny') => {
    if (actionBusy) return;
    const binding = getActionPackageDecisionBinding(item);
    if (!binding) {
      setActionsError('Gói thay đổi chưa có dữ liệu xác nhận chuẩn. Hãy làm mới trước khi quyết định.');
      return;
    }
    const decisionLabel = decision === 'approve' ? 'duyệt' : 'từ chối';
    if (!window.confirm(`Bạn muốn ${decisionLabel} đề xuất “${item.title}”?\n\nTác động: ${actionImpact(item)}\nHoàn tác: Có thể tạo đề xuất mới để điều chỉnh lại.`)) return;
    setActionBusy(item.id);
    try {
      const idempotencyKey = createActionPackageIdempotencyKey(`hermes-action-${decision}`);
      if (decision === 'approve') await approveActionPackage(item.id, binding, idempotencyKey);
      else await denyActionPackage(item.id, binding, idempotencyKey);
      await loadActionPackages(selectedWork?.id);
    } catch (caught) {
      setActionPackages([]);
      await loadActionPackages(selectedWork?.id);
      setActionsError(caught instanceof ApiError && caught.status === 409
        ? 'Mục đã được xử lý ở nơi khác. Trạng thái đang được làm mới.'
        : 'Quyết định chưa được ghi nhận. Trạng thái đang được làm mới.');
    } finally { setActionBusy(null); }
  };

  const createProposalPackage = async (part: AssistantPart) => {
    if (!selectedWork || proposalBusy || createdProposals[part.id]) return;
    const title = typeof part.content.title === 'string' ? part.content.title.trim() : '';
    const steps = Array.isArray(part.content.steps) ? part.content.steps : [];
    if (!title || !steps.length) {
      setActionsError(`Đề xuất của ${ASSISTANT_NAME} không đúng định dạng an toàn và chưa được tạo thành gói hành động.`);
      return;
    }
    const proposal: ActionPackageProposal = {
      title,
      description: typeof part.content.description === 'string' ? part.content.description : undefined,
      conversation_id: typeof part.content.conversation_id === 'string' ? part.content.conversation_id : undefined,
      source_proposal_part_id: part.id,
      steps: steps as ActionPackageProposal['steps'],
    };
    setProposalBusy(part.id);
    try {
      const created = await createActionPackage(selectedWork.id, proposal, `assistant-proposal-${part.id}`);
      setCreatedProposals(current => ({ ...current, [part.id]: created.id }));
      await loadActionPackages(selectedWork.id);
      setActionsError(null);
    } catch {
      setActionsError(`Chưa tạo được gói đề xuất. ${ASSISTANT_NAME} không thực hiện thay đổi nào; hãy kiểm tra nội dung rồi thử lại.`);
    } finally {
      setProposalBusy(null);
    }
  };

  const nextAction = selectedWork
    ? 'Mở Công việc để xem bước tiếp theo và các đề xuất đang chờ.'
    : visibleWorks.length
      ? `Chọn một Công việc để ${ASSISTANT_NAME} có thể chuẩn bị đề xuất đúng phạm vi.`
      : 'Tạo Công việc đầu tiên để bắt đầu trao đổi, quản lý tài liệu và theo dõi tiến độ.';

  const contextContent = <>
    <p>{ASSISTANT_NAME} chỉ nhận các mục được liệt kê. Secret, nhật ký kỹ thuật và Memory Hub không tự động đi vào chat.</p>
    {selectedWork ? <div className="assistant-memory-controls">
      <label> Bước kế hoạch
        <select value={planStepId} onChange={event => setPlanStepId(event.target.value)} disabled={memoryContextBusy}>
          <option value="">Không gắn với bước cụ thể</option>
          {planSteps.map(step => <option key={step.id} value={step.id}>{step.title}</option>)}
        </select>
      </label>
      {planStepId ? <>
        <label> Chế độ Memory
          <select value={memoryContext?.context_mode ?? 'off'} onChange={event => void saveMemoryContext({ context_mode: event.target.value as MemoryContextMode, auto_learning_enabled: memoryContext?.auto_learning_enabled ?? false })} disabled={memoryContextBusy}>
            <option value="off">Tắt Memory cho bước này</option>
            <option value="suggest_only">Chỉ gợi ý, không tự đưa vào chat</option>
            <option value="active_work_memory">Dùng Memory đã kích hoạt của bước</option>
          </select>
        </label>
        <label className="assistant-memory-toggle"><input type="checkbox" checked={memoryContext?.auto_learning_enabled ?? false} onChange={event => void saveMemoryContext({ context_mode: memoryContext?.context_mode ?? 'off', auto_learning_enabled: event.target.checked })} disabled={memoryContextBusy} /> Tự học có kiểm soát cho bước này</label>
        <p className="runtime-guidance">{memoryContextBusy ? 'Đang cập nhật chính sách…' : `${memoryContext?.active_memory_count ?? 0} bản ghi Memory đang đủ điều kiện. ${(memoryContext?.excluded?.length ?? 0) > 0 ? `${memoryContext?.excluded.length} nhóm bị loại theo chính sách.` : 'Các bản ghi ngoài phạm vi, nhạy cảm hoặc chưa kích hoạt luôn bị loại.'}`}</p>
      </> : <p className="runtime-guidance">Chọn một bước kế hoạch để cấu hình Memory và học tự động. Không có bước nào được tự bật mặc định.</p>}
    </div> : <p className="runtime-guidance">Chọn Công việc và bước kế hoạch trước khi thay đổi ngữ cảnh Memory.</p>}
    {manifest?.version && <p className="runtime-guidance">Phiên bản {manifest.version} · {manifest.byte_count}/{manifest.byte_limit} byte{manifest.generated_at ? ` · tạo ${dateText(manifest.generated_at)}` : ''}{manifest.from_message_id && manifest.through_message_id ? ` · tin nhắn ${manifest.from_message_id.slice(0, 8)}… → ${manifest.through_message_id.slice(0, 8)}…` : ''}</p>}
    <h3>Đang dùng</h3><ul><ContextItems items={manifest?.included} empty="Chỉ dùng dữ liệu tổng quan." /></ul>
    <h3>Không tự dùng</h3><ul><ContextItems items={manifest?.excluded} empty="Không có mục nào khác." /></ul>
  </>;

  return <main className={`hermes-assistant${selectedWork ? ' has-selected-work' : ''}`} aria-labelledby="hermes-assistant-title">
    <PageHeader eyebrow="AI AGENT" id="hermes-assistant-title" icon={<Bot size={28} />} title={ASSISTANT_LABEL} description={`Hỏi để tổng hợp, làm rõ việc tiếp theo hoặc chuẩn bị đề xuất. ${ASSISTANT_NAME} chỉ thay đổi dữ liệu sau khi bạn chọn đúng Công việc và duyệt gói hành động.`} actions={<button ref={contextTriggerRef} className="btn-secondary compact-button" onClick={() => setContextOpen(current => !current)} aria-expanded={contextOpen} aria-haspopup={isMobileViewport ? 'dialog' : undefined}>Ngữ cảnh &amp; nguồn <ChevronDown size={15} /></button>} />
    <div className="gyo-workspace-grid">
      <div className="gyo-main-column">
    <section className="assistant-brief" aria-label="Tình hình cần chú ý">
      <div><span>{ASSISTANT_NAME} đang xem</span><strong>{selectedWork ? `Công việc: ${selectedWork.title}` : 'Tổng quan các Công việc'}</strong></div>
      <div><span>Việc tiếp theo</span><strong>{nextAction}</strong></div>
      <div><span>Cần bạn quyết định</span><strong>{overview?.pending_approval_count ? `${overview.pending_approval_count} mục đang chờ duyệt` : overview?.waiting_confirmation_count ? `${overview.waiting_confirmation_count} Công việc chờ xác nhận` : 'Hiện chưa có mục chờ duyệt'}</strong></div>
    </section>
    {overviewError && <div className="inline-error" role="status">{overviewError}<button className="btn-secondary compact-button" onClick={() => void bootstrap()}>Thử lại</button></div>}
    {loading ? <div className="loading-indicator">Đang chuẩn bị {ASSISTANT_NAME}…</div> : <>
      {(overview?.active_work_count ?? 0) > 0 || (overview?.pending_approval_count ?? 0) > 0 || (overview?.output_count ?? 0) > 0 ? <section className="assistant-summary" aria-label="Tình hình hiện tại">
        <MetricCard onClick={() => setActiveTab('sessions')} icon={<Sparkles size={19} />} value={selectedWork ? 1 : overview?.active_work_count ?? '—'} label={selectedWork ? 'Công việc đang xem' : 'việc đang xử lý'} />
        <MetricCard onClick={() => setActiveTab('review')} icon={<ShieldCheck size={19} />} value={overview?.pending_approval_count ?? '—'} label="mục chờ bạn duyệt" />
        <MetricCard onClick={() => setActiveTab('sessions')} icon={<FileText size={19} />} value={overview?.output_count ?? '—'} label="đầu ra đã quản lý" />
      </section> : null}
      {!!(overview?.attention_items ?? []).length && <section className="assistant-attention" aria-labelledby="assistant-attention-title">
        <div><TriangleAlert size={18} /><h2 id="assistant-attention-title">Cần chú ý</h2></div>
        <div className="assistant-attention-list">{(overview?.attention_items ?? []).map(item => <button key={`${item.kind}-${item.work_id}-${item.title}`} type="button" onClick={() => { setActiveSession(item.work_id); setActiveTab(item.kind === 'approval' ? 'review' : 'sessions'); }}>
          <strong>{item.title}</strong><span>{item.reason} • {item.work_title}</span>
        </button>)}</div>
      </section>}
      <section className="assistant-work-picker">
        <label htmlFor="assistant-work">Công việc đang trao đổi
          <select id="assistant-work" value={selectedWork?.id ?? ''} onChange={event => setActiveSession(event.target.value || null)}>
            <option value="">Chưa chọn — chỉ xem tổng quan</option>
            {visibleWorks.map(work => <option key={work.id} value={work.id}>{work.title}</option>)}
          </select>
        </label>
        {selectedWork && <button className="btn-secondary compact-button" onClick={() => setActiveTab('sessions')}>Mở Công việc</button>}
        {visibleWorks.length === 0 && <button className="btn-primary compact-button" onClick={() => setActiveTab('sessions')}>Tạo Công việc đầu tiên</button>}
      </section>
      {contextOpen && !isMobileViewport && <aside className="assistant-context-drawer" aria-label="Ngữ cảnh và nguồn đang áp dụng"><h2>Ngữ cảnh &amp; nguồn</h2>{contextContent}</aside>}
      {isMobileViewport && <ContextDrawer open={contextOpen} title="Ngữ cảnh & nguồn" onClose={() => setContextOpen(false)} returnFocusRef={contextTriggerRef}><div className="assistant-context-drawer assistant-context-drawer-modal">{contextContent}</div></ContextDrawer>}
      {selectedWork && (actionPackages.length > 0 || actionsError) && <section className="assistant-action-packages" aria-label="Đề xuất thay đổi của Công việc">
        <header><div><h2>Đề xuất cần quyết định</h2><p>Các thay đổi chỉ được thực hiện sau khi bạn duyệt đúng nội dung đã xem.</p></div><button className="btn-secondary compact-button" type="button" onClick={() => setActiveTab('review')}>Mở Hộp duyệt</button></header>
        {actionsError && <div className="inline-error" role="status">{actionsError}<button className="btn-secondary compact-button" onClick={() => void loadActionPackages(selectedWork.id)}>Thử lại</button></div>}
        {actionPackages.filter(item => ['awaiting_approval', 'approved', 'executing'].includes(item.status)).slice(0, 3).map(item => <article key={item.id} data-review-source="action_package" data-review-id={item.id} tabIndex={-1}>
          <div><strong>{item.title}</strong><p>{item.description || `${item.steps.length} bước thay đổi đã được chuẩn bị.`}</p><dl><div><dt>Tác động</dt><dd>{actionImpact(item)}</dd></div><div><dt>Hoàn tác</dt><dd>Có thể tạo đề xuất mới để điều chỉnh lại.</dd></div></dl><small>{actionStatusLabel[item.status] || item.status} · {item.steps.length} bước</small></div>
          {item.status === 'awaiting_approval' && <div className="assistant-action-buttons"><button className="btn-primary compact-button" disabled={actionBusy === item.id} onClick={() => void decideActionPackage(item, 'approve')}>{actionBusy === item.id ? 'Đang ghi nhận…' : 'Duyệt thay đổi'}</button><button className="btn-secondary compact-button" disabled={actionBusy === item.id} onClick={() => void decideActionPackage(item, 'deny')}>Từ chối</button></div>}
        </article>)}
      </section>}
      <section className={`assistant-chat${threadId ? "" : " assistant-chat-empty"}`} aria-label={`Trao đổi với ${ASSISTANT_NAME}`}>
        <div className="assistant-thread-bar"><MessageSquare size={18} />
          <select aria-label="Phiên Công việc" value={conversationId ?? ''} onChange={event => { requestGeneration.current += 1; selectedThreadRef.current = null; setThreadId(null); setTurns([]); setStreamedText({}); setPrompt(''); setManifest(null); setAttachmentIds([]); setConversationId(event.target.value || null); }} disabled={!selectedWork}>
            <option value="">{selectedWork ? 'Chưa có phiên Công việc' : 'Chọn Công việc trước'}</option>
            {conversations.map(conversation => <option key={conversation.id} value={conversation.id}>{conversation.title}</option>)}
          </select>
          <select aria-label="Phiên trao đổi trợ lý" value={threadId ?? ''} onChange={event => void loadThread(event.target.value)}><option value="">{visibleThreads.length ? 'Chọn phiên trao đổi' : 'Chưa có phiên trao đổi'}</option>{visibleThreads.map(thread => <option key={thread.id} value={thread.id}>{thread.status === 'archived' ? `[Đã lưu trữ] ${thread.title}` : thread.title}</option>)}</select>
          <button className="btn-secondary compact-button" onClick={() => void createThread()} disabled={!selectedWork || creatingThread}><Plus size={15} />{creatingThread ? 'Đang tạo…' : 'Phiên mới'}</button>
          <button className="btn-secondary compact-button" type="button" onClick={() => setShowArchivedThreads(current => !current)} aria-pressed={showArchivedThreads}>{showArchivedThreads ? 'Ẩn lịch sử' : 'Lịch sử'}</button>
          {selectedThread && !selectedThreadArchived && <button className="btn-secondary compact-button" type="button" onClick={beginRenameThread} disabled={updatingThread}><Pencil size={15} /> Đổi tên</button>}
          {selectedThread && !selectedThreadArchived && <button className="btn-secondary compact-button" type="button" onClick={() => void archiveThread()} disabled={updatingThread}><Archive size={15} /> Lưu trữ</button>}
          {selectedThread && selectedThreadArchived && <button className="btn-secondary compact-button" type="button" onClick={() => void restoreThread()} disabled={updatingThread}><ArchiveRestore size={15} /> Khôi phục</button>}
        </div>
        {editingThread && <form className="assistant-thread-rename" onSubmit={event => { event.preventDefault(); void saveThreadTitle(); }}><label htmlFor="assistant-thread-title">Tên phiên trao đổi</label><input id="assistant-thread-title" value={threadTitle} onChange={event => setThreadTitle(event.target.value)} maxLength={160} autoFocus /><button className="btn-primary compact-button" disabled={!threadTitle.trim() || updatingThread}>{updatingThread ? 'Đang lưu…' : 'Lưu tên'}</button><button className="btn-secondary compact-button" type="button" onClick={() => setEditingThread(false)} disabled={updatingThread}><X size={15} /> Hủy</button></form>}
        {threadError && <div className="inline-error assistant-thread-error" role="status">{threadError}<button className="btn-secondary compact-button" onClick={() => void bootstrap()}>Thử lại</button></div>}
        <div className="assistant-turns">
          {!threadId && <div className="empty-state"><div className="empty-state-title">Bắt đầu một phiên trao đổi</div><div className="empty-state-text">{selectedWork && !selectedConversation ? 'Công việc này chưa có Phiên trao đổi. Chọn “Phiên mới” để tạo rõ ràng trước khi gửi yêu cầu.' : `Tạo phiên mới để gửi yêu cầu cho ${ASSISTANT_NAME}. Trang này không tự tạo dữ liệu khi bạn chỉ đang xem.`}</div></div>}
          {threadId && turns.length === 0 && <div className="empty-state"><div className="empty-state-title">Bạn muốn làm gì hôm nay?</div><div className="empty-state-text">Ví dụ: “Tóm tắt việc cần tiếp tục” hoặc “Giúp tôi chuẩn bị kế hoạch cho Công việc đang chọn”.</div>{selectedWork && <div className="assistant-quick-actions"><button type="button" onClick={() => applyQuickPrompt('Tóm tắt tình hình Công việc và bước tiếp theo.')}>Tóm tắt Công việc</button><button type="button" onClick={() => applyQuickPrompt('Phân tích bước tiếp theo và các điểm đang bị chặn.')}>Phân tích tiến độ</button><button type="button" onClick={() => applyQuickPrompt('Chuẩn bị một đề xuất thay đổi an toàn, nếu cần.')}>Chuẩn bị đề xuất</button></div>}</div>}
          {turns.map(turn => <AssistantTurnCard key={turn.id} turn={turn} streamedText={streamedText[turn.id]} sending={sending} onOpenReview={() => setActiveTab('review')} onCreateProposal={item => void createProposalPackage(item)} proposalBusy={proposalBusy} proposalCreated={createdProposals} onCancel={id => void cancelTurn(id)} onRetrySame={id => void retryTurn(id, 'same_model')} onRetryAuto={id => void retryTurn(id, 'auto')} />)}
        </div>
        {selectedThreadArchived && <div className="assistant-archived-note" role="status">Đây là phiên đã lưu trữ. Bạn có thể xem lại lịch sử hoặc khôi phục để tiếp tục trao đổi.</div>}
        <form className="assistant-composer" onSubmit={submit}>
          {selectedWork && availableArtifacts.length > 0 && <div className="assistant-attachments">
            <label><Paperclip size={15} /> Đính kèm tài liệu managed
              <select aria-label="Chọn tệp đính kèm" value="" onChange={event => { const id = event.target.value; if (id) setAttachmentIds(current => current.includes(id) || current.length >= 10 ? current : [...current, id]); }} disabled={selectedThreadArchived || attachmentIds.length >= 10}>
                <option value="">Chọn tài liệu…</option>
                {availableArtifacts.filter(item => !attachmentIds.includes(item.id)).map(item => <option key={item.id} value={item.id}>{item.relative_path.split('/').at(-1)}</option>)}
              </select>
            </label>
            {attachmentIds.length > 0 && <div className="assistant-attachment-chips" aria-label="Tệp sẽ gửi">{attachmentIds.map(id => { const artifact = availableArtifacts.find(item => item.id === id); return <button type="button" key={id} onClick={() => setAttachmentIds(current => current.filter(item => item !== id))} aria-label={`Bỏ tệp ${artifact?.relative_path.split('/').at(-1) ?? id}`}><Paperclip size={13} /> {artifact?.relative_path.split('/').at(-1) ?? id}<X size={13} /></button>; })}</div>}
          </div>}
          <label className="assistant-model-choice">Model cho lượt này
            <select aria-label="Model GYO" value={modelChoice} onChange={event => setModelChoice(event.target.value)} disabled={selectedThreadArchived || !availableModels.length}>
              <option value="auto">Tự động (khuyến nghị)</option>
              {modelProviders.map(provider => {
                const models = availableModels.filter(item => item.provider_profile_id === provider.id);
                return models.length ? <optgroup key={provider.id} label={provider.display_name}>{models.map(item => <option key={item.id} value={`model:${item.id}`}>{item.display_name} · {item.tier}</option>)}</optgroup> : null;
              })}
            </select>
          </label>
          {!availableModels.length && <div className="assistant-model-empty" role="status">Chưa có model GYO đang bật. <button className="btn-secondary compact-button" type="button" onClick={() => setActiveTab('settings')}>Mở cài đặt model</button></div>}
          <textarea value={prompt} onChange={event => setPrompt(event.target.value)} rows={3} disabled={selectedThreadArchived || !availableModels.length || Boolean(selectedWork && !selectedConversation)} placeholder={selectedThreadArchived ? 'Khôi phục phiên này để tiếp tục trao đổi.' : selectedWork && !selectedConversation ? 'Tạo Phiên mới trước khi gửi yêu cầu…' : !availableModels.length ? 'Bật một model trong Cài đặt trước khi gửi…' : selectedWork ? `Hỏi ${ASSISTANT_NAME} về “${selectedWork.title}”…` : `Hỏi ${ASSISTANT_NAME} về tình hình công việc…`} /><button className="btn-primary" disabled={!prompt.trim() || sending || !threadId || selectedThreadArchived || !availableModels.length || Boolean(selectedWork && !selectedConversation)}><Send size={17} />{sending ? 'Đang gửi…' : 'Gửi'}</button>
        </form>
        <p className="assistant-safety-note">GYO chỉ dùng model đang bật. Lựa chọn model và lý do định tuyến được lưu cùng lượt trả lời; thay đổi Công việc chỉ có thể đi qua gói đề xuất đã duyệt.</p>
      </section>
      </>}
      </div>
      <aside className="gyo-right-rail" aria-label="Gợi ý và hoạt động của Workspace">
        <section className="gyo-rail-card">
          <header><div><Sparkles size={18} /><h2>Gợi ý cho bạn</h2></div></header>
          <button type="button" onClick={() => setActiveTab('sessions')}><ListChecks size={17} /><span><strong>{visibleWorks.length ? 'Mở hoặc tạo Công việc' : 'Tạo Công việc mới'}</strong><small>Quản lý kế hoạch, trao đổi và đầu ra theo cùng một phạm vi.</small></span><ChevronDown size={16} /></button>
          <button type="button" onClick={() => setActiveTab('review')}><ShieldCheck size={17} /><span><strong>Xem mục chờ duyệt</strong><small>{overview?.pending_approval_count ?? 0} mục đang chờ quyết định.</small></span><ChevronDown size={16} /></button>
          <button type="button" onClick={() => selectedWork ? applyQuickPrompt('Tóm tắt tiến độ và bước tiếp theo của Công việc này.') : setActiveTab('sessions')}><FileText size={17} /><span><strong>Tóm tắt tiến độ</strong><small>Chỉ điền yêu cầu; GYO không tự gửi tin nhắn.</small></span><ChevronDown size={16} /></button>
        </section>
        <section className="gyo-rail-card">
          <header><div><MessageSquare size={18} /><h2>Hoạt động gần đây</h2></div></header>
          {(overview?.latest_work_updates ?? []).length ? <ul className="gyo-activity-list">{(overview?.latest_work_updates ?? []).slice(0, 4).map(item => <li key={`${item.id}-${item.updated_at}`}><span>{item.title}</span><small>{dateText(item.updated_at)}</small></li>)}</ul> : <p className="gyo-rail-empty">Chưa có hoạt động đủ điều kiện để hiển thị.</p>}
        </section>
        <section className="gyo-learning-card">
          <span>HỌC CÓ KIỂM SOÁT</span><h2>Memory và Skill luôn cần được duyệt</h2><p>{memoryContext?.auto_learning_enabled ? 'GYO chỉ tạo candidate có cấu trúc cho bước đã chọn; không tự kích hoạt Memory hoặc Skill.' : 'Tự học đang tắt cho bước này. Bạn có thể bật trong Ngữ cảnh & nguồn.'}</p>
          <button className="btn-secondary compact-button" type="button" onClick={() => setContextOpen(true)}>Mở ngữ cảnh</button>
        </section>
      </aside>
    </div>
  </main>;
};
