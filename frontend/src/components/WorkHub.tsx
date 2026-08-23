import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronUp, Circle, FileText, FolderOpen, ListChecks, MessageSquarePlus, Pencil, Plus, Send, Sparkles } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { confirmWorkCompletion, createConversation, createPlanPhase, createPlanStep, getConversationMessages, getWorkDashboard, listConversations, readWorkDraft, reopenWork, updateConversation, updatePlanPhase, updatePlanStep, updateWork, writeWorkDraft, type Conversation, type WorkDashboard, type WorkMessage, type WorkPlanPhase, type WorkPlanStep } from '../api/works';
import { FileExplorer } from './FileExplorer';
import { EditorPanel } from './EditorPanel';
import { ReportsPanel } from './ReportsPanel';
import { KnowledgePanel } from './KnowledgePanel';
import { ActionPackagesPanel } from './ActionPackagesPanel';
import { fetchSkills, type Skill } from '../api/skills';
import { cancelAssistantTurn, createAssistantRun, getAssistantTurns, listAssistantThreads, resolveWorkConversationAssistantThread, retryAssistantTurn, type AssistantPart, type AssistantTurn } from '../api/assistant';
import { subscribeThreadStream } from '../assistant/threadStreamRegistry';
import { createActionPackage, type ActionPackageProposal } from '../api/actionPackages';
import { TurnPartRenderer } from './assistant/TurnPartRenderer';
import { PhaseCard } from './PhaseCard';
import { ASSISTANT_NAME } from '../branding';
import { ApiError } from '../api/client';
import { filterAvailableSkills, OPEN_WORK_CONVERSATIONS_EVENT } from './workHubUtils';

type WorkTab = 'overview' | 'plan' | 'conversations' | 'documents' | 'outputs' | 'knowledge' | 'capabilities';
const tabLabels: Array<[WorkTab, string]> = [
  ['overview', 'Tổng quan'], ['plan', 'Kế hoạch'], ['conversations', 'Trao đổi'],
  ['documents', 'Tài liệu'], ['outputs', 'Đầu ra & Báo cáo'], ['knowledge', 'Tri thức & Bộ nhớ'], ['capabilities', 'Năng lực'],
];

const dateText = (value?: number | null) => value ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(value * 1000) : 'Chưa có cập nhật';
const workStatus = (value: string) => ({ not_started: 'Chưa bắt đầu', in_progress: 'Đang thực hiện', paused: 'Tạm dừng', waiting_confirmation: 'Chờ bạn xác nhận', completed: 'Hoàn tất' }[value] ?? value);
const stepStatus = (value: string) => ({ not_started: 'Chưa bắt đầu', in_progress: 'Đang làm', blocked: 'Cần xử lý', completed: 'Đã xong' }[value] ?? value);
function PlanStepItem({ step, onUpdate, onMoveUp, onMoveDown, canMoveUp, canMoveDown }: { step: WorkPlanStep; onUpdate: (updates: Partial<Pick<WorkPlanStep, 'title' | 'description' | 'result' | 'status' | 'sort_order'>>) => Promise<void>; onMoveUp: () => void; onMoveDown: () => void; canMoveUp: boolean; canMoveDown: boolean }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(step.title);
  const [description, setDescription] = useState(step.description || '');
  const [result, setResult] = useState(step.result || '');
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => { setTitle(step.title); setDescription(step.description || ''); setResult(step.result || ''); }, [step]);
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!title.trim() || saving) return;
    setSaving(true);
    try { await onUpdate({ title: title.trim(), description: description.trim() || undefined, result: result.trim() || undefined }); setValidationError(null); setEditing(false); }
    finally { setSaving(false); }
  };

  return <div className="plan-step">
    <button className="plan-step-toggle" onClick={() => void onUpdate({ status: step.status === 'completed' ? 'in_progress' : 'completed' })} title={step.status === 'completed' ? 'Đánh dấu đang làm' : 'Đánh dấu đã xong'}>{step.status === 'completed' ? <CheckCircle2 size={19} /> : <Circle size={19} />}</button>
    <div className="plan-step-content">
      {!editing ? <>
        <div className="plan-step-title-row"><strong>{step.title}</strong><button className="icon-button" type="button" aria-label={`Đưa bước ${step.title} lên`} disabled={!canMoveUp} onClick={onMoveUp}><ChevronUp size={15} /></button><button className="icon-button" type="button" aria-label={`Đưa bước ${step.title} xuống`} disabled={!canMoveDown} onClick={onMoveDown}><ChevronDown size={15} /></button><button className="icon-button" type="button" aria-label={`Chỉnh sửa bước ${step.title}`} onClick={() => setEditing(true)}><Pencil size={15} /></button></div>
        {step.description && <p>{step.description}</p>}
        {step.status === 'blocked' && <p className="plan-step-blocked">Cần xử lý: {step.result || step.description || 'Bổ sung lý do bị chặn và hành động tiếp theo.'}</p>}
        {step.status !== 'blocked' && step.result && <p className="plan-step-result">Kết quả: {step.result}</p>}
        <select aria-label={`Trạng thái ${step.title}`} value={step.status} onChange={event => { const status = event.target.value as WorkPlanStep['status']; if (status === 'blocked' && !(step.description || step.result)) { setValidationError('Hãy bổ sung lý do hoặc hành động tiếp theo trước khi đánh dấu Cần xử lý.'); setEditing(true); return; } void onUpdate({ status }); }}><option value="not_started">Chưa bắt đầu</option><option value="in_progress">Đang làm</option><option value="blocked">Cần xử lý</option><option value="completed">Đã xong</option></select>
      </> : <form className="plan-step-edit" onSubmit={save}>
        {validationError && <div className="inline-error" role="status">{validationError}</div>}
        <label>Tên bước<input value={title} onChange={event => setTitle(event.target.value)} /></label>
        <label>Mô tả hoặc lý do cần xử lý<textarea value={description} onChange={event => setDescription(event.target.value)} rows={2} /></label>
        <label>Kết quả hoặc hành động tiếp theo<textarea value={result} onChange={event => setResult(event.target.value)} rows={2} /></label>
        <div><button className="btn-primary compact-button" disabled={!title.trim() || saving}>{saving ? 'Đang lưu…' : 'Lưu bước'}</button><button className="btn-secondary compact-button" type="button" onClick={() => setEditing(false)}>Hủy</button></div>
      </form>}
    </div>
  </div>;
}

export function ConversationWorkspace({ workId, conversation, onRename, onArchive }: { workId: string; conversation: Conversation; onRename: (title: string) => Promise<void>; onArchive: () => Promise<void> }) {
  const [messages, setMessages] = useState<WorkMessage[]>([]);
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [streamedText, setStreamedText] = useState<Record<string, string>>({});
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [proposalBusy, setProposalBusy] = useState<string | null>(null);
  const [createdProposals, setCreatedProposals] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [nextTitle, setNextTitle] = useState(conversation.title);
  const loadGeneration = useRef(0);
  const turnsRef = useRef<AssistantTurn[]>([]);
  useEffect(() => { turnsRef.current = turns; }, [turns]);

  const load = useCallback(async () => {
    const generation = ++loadGeneration.current;
    setLoading(true);
    try {
      const page = await getConversationMessages(workId, conversation.id);
      if (generation !== loadGeneration.current) return;
      setMessages(page.messages); setHasMoreMessages(page.has_more); setError(null);
      const threads = await listAssistantThreads();
      if (generation !== loadGeneration.current) return;
      const matchingThread = threads.find(thread => thread.status === 'active' && thread.work_id === workId && thread.conversation_id === conversation.id);
      if (!matchingThread) { setThreadId(null); setTurns([]); return; }
      const existingTurns = await getAssistantTurns(matchingThread.id);
      if (generation !== loadGeneration.current) return;
      setThreadId(matchingThread.id); setTurns(existingTurns);
    } catch {
      if (generation !== loadGeneration.current) return;
      setError('Chưa tải được lịch sử của phiên trao đổi này.');
    } finally { if (generation === loadGeneration.current) setLoading(false); }
  }, [conversation.id, workId]);

  useEffect(() => {
    setNextTitle(conversation.title); setRenaming(false); setThreadId(null); setTurns([]); setStreamedText({});
    setPrompt(readWorkDraft(window.localStorage, workId, conversation.id));
    void load();
    return () => { loadGeneration.current += 1; };
  }, [conversation.id, conversation.title, load, workId]);
  useEffect(() => { writeWorkDraft(window.localStorage, workId, conversation.id, prompt); }, [conversation.id, prompt, workId]);

  const refreshTurns = useCallback(async (selectedThreadId: string, generation: number) => {
    try {
      const latestTurns = await getAssistantTurns(selectedThreadId);
      if (generation !== loadGeneration.current || selectedThreadId !== threadId) return;
      setTurns(latestTurns); setError(null);
    } catch {
      if (generation === loadGeneration.current && selectedThreadId === threadId) setError('Chưa đồng bộ được phản hồi của GYO. Bạn có thể làm mới phiên trao đổi này.');
    }
  }, [threadId]);

  useEffect(() => {
    if (!threadId || !turns.some(turn => turn.status === 'running')) return;
    const selected = threadId;
    const generation = loadGeneration.current;
    let refreshQueued = false;
    const onEvent = (event: { type: string; data: string }) => {
      if (event.type === 'token') {
        try {
          const payload = JSON.parse(event.data) as { text?: unknown; assistant_turn_id?: unknown; thread_id?: unknown };
          if (payload.thread_id !== selected || typeof payload.text !== 'string' || typeof payload.assistant_turn_id !== 'string') return;
          const active = turnsRef.current.find(turn => turn.id === payload.assistant_turn_id && turn.status === 'running');
          if (active) setStreamedText(current => ({ ...current, [active.id]: `${current[active.id] ?? ''}${payload.text}` }));
        } catch { /* Saved turns remain authoritative. */ }
      } else if ((event.type === 'done' || event.type === 'error')) {
        if (!refreshQueued && generation === loadGeneration.current && selected === threadId) {
          refreshQueued = true;
          setStreamedText({});
          void refreshTurns(selected, generation);
        }
      }
    };
    const unsubscribe = subscribeThreadStream(threadId, onEvent);
    return unsubscribe;
  }, [refreshTurns, threadId, turns]);

  const loadOlder = async () => {
    const oldestId = messages[0]?.id;
    if (!oldestId || loadingOlder || !hasMoreMessages) return;
    const generation = loadGeneration.current; setLoadingOlder(true);
    try {
      const page = await getConversationMessages(workId, conversation.id, 100, oldestId);
      if (generation !== loadGeneration.current) return;
      setMessages(current => [...page.messages, ...current]); setHasMoreMessages(page.has_more); setError(null);
    } catch { setError('Chưa tải được các trao đổi cũ hơn. Bạn có thể thử lại.'); }
    finally { setLoadingOlder(false); }
  };

  const ensureThread = async () => {
    if (threadId) return threadId;
    const created = await resolveWorkConversationAssistantThread(workId, conversation.id);
    const existingTurns = await getAssistantTurns(created.id);
    setThreadId(created.id);
    setTurns(existingTurns);
    return created.id;
  };
  const submitPrompt = async () => {
    if (!prompt.trim() || sending) return;
    const message = prompt.trim(); setSending(true); setError(null);
    try {
      const targetThread = await ensureThread();
      const created = await createAssistantRun(targetThread, message, workId, conversation.id);
      setTurns(current => [...current, ...created]); setPrompt('');
    } catch (caught) { setError(caught instanceof ApiError && caught.status === 409 ? 'Không thể bắt đầu hoặc gửi lại phản hồi vì phạm vi hoặc trạng thái chạy đã thay đổi. Bản nháp vẫn được giữ.' : 'Không gửi được yêu cầu. Bản nháp vẫn được giữ để bạn thử lại.'); }
    finally { setSending(false); }
  };
  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void submitPrompt();
  };
  const handleComposerKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void submitPrompt();
  };
  const retryTurn = async (turnId: string) => {
    setSending(true);
    try { const retried = await retryAssistantTurn(turnId); setTurns(current => [...current, retried]); setError(null); }
    catch (caught) { setError(caught instanceof ApiError && caught.status === 409 ? 'Không thể gửi lại phản hồi vì phạm vi hoặc trạng thái chạy đã thay đổi.' : 'Không thể gửi lại phản hồi; yêu cầu gốc không bị nhân đôi.'); }
    finally { setSending(false); }
  };
  const cancelTurn = async (turnId: string) => {
    setSending(true);
    try { const cancelled = await cancelAssistantTurn(turnId); setTurns(current => current.map(turn => turn.id === turnId ? cancelled : turn)); setError(null); }
    catch { setError('Chưa thể hủy phản hồi này.'); }
    finally { setSending(false); }
  };
  const createProposal = async (part: AssistantPart) => {
    const title = typeof part.content.title === 'string' ? part.content.title : '';
    const steps = Array.isArray(part.content.steps) ? part.content.steps : [];
    if (!title || !steps.length || proposalBusy) { setError('Đề xuất không đúng định dạng an toàn.'); return; }
    setProposalBusy(part.id);
    try {
      const proposal: ActionPackageProposal = { title, description: typeof part.content.description === 'string' ? part.content.description : undefined, conversation_id: conversation.id, steps: steps as ActionPackageProposal['steps'] };
      const created = await createActionPackage(workId, proposal, `work-conversation-proposal-${part.id}`);
      setCreatedProposals(current => ({ ...current, [part.id]: created.id })); setError(null);
    } catch { setError('Chưa tạo được gói đề xuất; chưa có thay đổi nào được thực hiện.'); }
    finally { setProposalBusy(null); }
  };

  return <section className="conversation-workspace" aria-label={`Trao đổi: ${conversation.title}`}>
    <header className="conversation-header"><div><h3>{conversation.title}</h3><p>{conversation.purpose || `Trao đổi với ${ASSISTANT_NAME} cho nội dung này.`}</p></div><div className="conversation-actions"><button className="btn-secondary compact-button" onClick={() => setRenaming(current => !current)}>Đổi tên</button><button className="btn-secondary compact-button" onClick={() => { if (window.confirm(`Lưu trữ phiên “${conversation.title}”? Bạn vẫn có thể xem lại trong lịch sử quản lý.`)) void onArchive(); }}>Lưu trữ</button><button className="btn-secondary compact-button" onClick={() => void load()}>Làm mới</button></div></header>
    {renaming && <form className="inline-create conversation-rename" onSubmit={event => { event.preventDefault(); if (nextTitle.trim()) void onRename(nextTitle.trim()); }}><input autoFocus value={nextTitle} onChange={event => setNextTitle(event.target.value)} aria-label="Tên phiên trao đổi" /><button className="btn-primary compact-button" disabled={!nextTitle.trim()}>Lưu tên</button></form>}
    <div className="conversation-messages">
      {loading && <div className="loading-indicator">Đang tải trao đổi…</div>}
      {!loading && hasMoreMessages && <button className="btn-secondary compact-button conversation-load-older" type="button" onClick={() => void loadOlder()} disabled={loadingOlder}>{loadingOlder ? 'Đang tải…' : 'Tải trao đổi cũ hơn'}</button>}
      {!loading && messages.length === 0 && turns.length === 0 && <div className="empty-state"><div className="empty-state-title">Bắt đầu một trao đổi</div><div className="empty-state-text">Nêu việc bạn muốn {ASSISTANT_NAME} thực hiện trong Công việc này.</div></div>}
      {messages.map(message => <article className={`conversation-message ${message.role}`} key={message.id}><strong>{message.role === 'user' ? 'Bạn' : ASSISTANT_NAME}</strong><p>{message.content}</p><time>{dateText(message.created_at)}</time></article>)}
      {turns.map(turn => <article className={`conversation-message ${turn.role}`} key={turn.id}><strong>{turn.role === 'user' ? 'Bạn' : ASSISTANT_NAME}</strong>{turn.parts.map(part => <TurnPartRenderer key={part.id} part={part} onCreateProposal={item => void createProposal(item)} proposalBusy={proposalBusy === part.id} proposalCreated={Boolean(createdProposals[part.id])} />)}{turn.role === 'assistant' && turn.status === 'running' && <div className="assistant-live-response"><p>{streamedText[turn.id] || `${ASSISTANT_NAME} đang trả lời…`}</p><button className="btn-secondary compact-button" type="button" onClick={() => void cancelTurn(turn.id)}>Hủy phản hồi</button></div>}{turn.role === 'assistant' && turn.status === 'failed' && <button className="btn-secondary compact-button" type="button" onClick={() => void retryTurn(turn.id)}>Gửi lại phản hồi</button>}<time>{dateText(turn.created_at)}</time></article>)}
    </div>
    {error && <div className="inline-error">{error}</div>}
    <ActionPackagesPanel workId={workId} />
    <form className="conversation-composer" onSubmit={submit}><textarea value={prompt} onChange={event => setPrompt(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder={`Giao yêu cầu cho ${ASSISTANT_NAME} trong phiên trao đổi này…`} rows={3} /><button className="btn-primary" disabled={sending || !prompt.trim()}><Send size={16} /> {sending ? 'Đang gửi…' : `Gửi ${ASSISTANT_NAME}`}</button></form>
  </section>;
}

export const WorkHub: React.FC = () => {
  const workId = useHermesStore(state => state.activeSessionId);
  const activeFile = useHermesStore(state => state.activeFile);
  const openFiles = useHermesStore(state => state.openFiles);
  const [dashboard, setDashboard] = useState<WorkDashboard | null>(null);
  const [tab, setTab] = useState<WorkTab>('overview');
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [archivedConversations, setArchivedConversations] = useState<Conversation[]>([]);
  const [archivedLoading, setArchivedLoading] = useState(false);
  const [archivedError, setArchivedError] = useState<string | null>(null);
  const [newConversation, setNewConversation] = useState(false);
  const [conversationTitle, setConversationTitle] = useState('');
  const [newPhase, setNewPhase] = useState('');
  const [newSteps, setNewSteps] = useState<Record<string, string>>({});
  const [editingWork, setEditingWork] = useState(false);
  const [workTitle, setWorkTitle] = useState('');
  const [workGoal, setWorkGoal] = useState('');
  const [workDataScope, setWorkDataScope] = useState<'work_only' | 'approved_library'>('work_only');
  const [workState, setWorkState] = useState<'not_started' | 'in_progress' | 'paused'>('not_started');
  const [availableSkills, setAvailableSkills] = useState<Skill[]>([]);
  const [skillsError, setSkillsError] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(workId));
  const dashboardGeneration = useRef(0);
  const load = useCallback(async () => {
    const generation = ++dashboardGeneration.current;
    if (!workId) { setDashboard(null); setLoading(false); return; }
    setLoading(true);
    try {
      const next = await getWorkDashboard(workId);
      if (generation !== dashboardGeneration.current) return;
      setDashboard(next); setError(null);
      setWorkTitle(next.work.title); setWorkGoal(next.work.goal || '');
      setWorkDataScope(next.work.data_scope || 'work_only');
      if (next.work.work_status !== 'waiting_confirmation' && next.work.work_status !== 'completed') setWorkState(next.work.work_status);
      setConversationId(current => current && next.conversations.some(item => item.id === current) ? current : (next.conversations[0]?.id ?? null));
    } catch { if (generation === dashboardGeneration.current) setError('Chưa tải được Công việc này. Hãy thử lại.'); }
    finally { if (generation === dashboardGeneration.current) setLoading(false); }
  }, [workId]);
  useEffect(() => {
    setTab('overview');
    setDashboard(null);
    setConversationId(null);
    setArchivedConversations([]);
    setArchivedError(null);
    void load();
  }, [load]);
  useEffect(() => {
    const openConversations = () => setTab('conversations');
    window.addEventListener(OPEN_WORK_CONVERSATIONS_EVENT, openConversations);
    return () => window.removeEventListener(OPEN_WORK_CONVERSATIONS_EVENT, openConversations);
  }, []);
  useEffect(() => {
    if (tab !== 'capabilities') return;
    let active = true;
    void fetchSkills().then(items => {
      if (!active) return;
      setAvailableSkills(filterAvailableSkills(items));
      setSkillsError(false);
    }).catch(() => { if (active) setSkillsError(true); });
    return () => { active = false; };
  }, [tab]);
  const loadArchivedConversations = useCallback(async () => {
    if (!workId) return;
    setArchivedLoading(true);
    try {
      const items = await listConversations(workId);
      setArchivedConversations(items.filter(item => item.status === 'archived'));
      setArchivedError(null);
    } catch { setArchivedError('Chưa tải được lịch sử đã lưu trữ.'); }
    finally { setArchivedLoading(false); }
  }, [workId]);
  useEffect(() => { if (tab === 'conversations') void loadArchivedConversations(); }, [loadArchivedConversations, tab]);
  if (!workId) return <div className="work-hub empty-state centered-empty-state"><div className="empty-state-title">Chọn hoặc tạo một Công việc</div><div className="empty-state-text">Mỗi Công việc là một dự án riêng, gồm kế hoạch, nhiều phiên trao đổi, tài liệu và đầu ra.</div></div>;
  const createConversationForWork = async (event: React.FormEvent) => { event.preventDefault(); if (!conversationTitle.trim()) return; try { const item = await createConversation(workId, conversationTitle.trim()); setConversationTitle(''); setNewConversation(false); setConversationId(item.id); setTab('conversations'); await load(); } catch { setError('Không tạo được Phiên trao đổi. Tên này có thể đã tồn tại.'); } };
  const addPhase = async (event: React.FormEvent) => { event.preventDefault(); if (!newPhase.trim()) return; try { await createPlanPhase(workId, newPhase.trim()); setNewPhase(''); await load(); } catch { setError('Không thêm được giai đoạn kế hoạch.'); } };
  const addStep = async (phaseId: string) => { const title = newSteps[phaseId]?.trim(); if (!title) return; try { await createPlanStep(workId, phaseId, title); setNewSteps(current => ({ ...current, [phaseId]: '' })); await load(); } catch { setError('Không thêm được bước công việc.'); } };
  const changeStep = async (stepId: string, updates: Partial<Pick<WorkPlanStep, 'title' | 'description' | 'result' | 'status' | 'sort_order'>>) => { try { await updatePlanStep(workId, stepId, updates); await load(); } catch { setError('Không cập nhật được bước này. Nếu bước bị chặn, hãy bổ sung lý do hoặc hành động tiếp theo.'); } };
  const changePhase = async (phaseId: string, updates: Partial<Pick<WorkPlanPhase, 'title' | 'status' | 'sort_order'>>) => { try { await updatePlanPhase(workId, phaseId, updates); await load(); } catch { setError('Không cập nhật được giai đoạn này.'); } };
  const swapPhases = async (first: WorkPlanPhase, second: WorkPlanPhase) => { try { await updatePlanPhase(workId, first.id, { sort_order: second.sort_order }); await updatePlanPhase(workId, second.id, { sort_order: first.sort_order }); await load(); } catch { setError('Không sắp xếp được các giai đoạn.'); } };
  const swapSteps = async (first: WorkPlanStep, second: WorkPlanStep) => { try { await updatePlanStep(workId, first.id, { sort_order: second.sort_order }); await updatePlanStep(workId, second.id, { sort_order: first.sort_order }); await load(); } catch { setError('Không sắp xếp được các bước.'); } };
  const confirmCompletion = async () => { try { await confirmWorkCompletion(workId); await load(); } catch { setError('Chưa thể xác nhận hoàn tất Công việc này.'); } };
  const reopen = async () => { try { await reopenWork(workId); await load(); } catch { setError('Chưa thể mở lại Công việc này.'); } };
  const saveWork = async (event: React.FormEvent) => { event.preventDefault(); if (!workTitle.trim()) return; try { await updateWork(workId, { title: workTitle.trim(), goal: workGoal.trim() || undefined, data_scope: workDataScope, work_status: workState }); setEditingWork(false); await load(); } catch { setError('Chưa cập nhật được thông tin Công việc.'); } };
  const renameConversation = async (id: string, title: string) => { try { await updateConversation(workId, id, { title }); await load(); } catch { setError('Chưa đổi được tên Phiên trao đổi.'); } };
  const archiveConversation = async (id: string) => { try { await updateConversation(workId, id, { archived: true }); setConversationId(null); await load(); await loadArchivedConversations(); } catch { setError('Chưa lưu trữ được Phiên trao đổi.'); } };
  const restoreConversation = async (id: string) => { try { await updateConversation(workId, id, { archived: false }); setConversationId(id); await load(); await loadArchivedConversations(); } catch { setArchivedError('Chưa khôi phục được Phiên trao đổi.'); } };
  const selectedConversation = dashboard?.conversations.find(item => item.id === conversationId) ?? null;
  return <div className="work-hub">
    {loading && <div className="loading-indicator">Đang mở Công việc…</div>}
    {error && <div className="inline-error" role="status">{error} <button className="btn-secondary compact-button" onClick={() => void load()}>Thử lại</button></div>}
    {dashboard && <>
      <header className="work-hub-header"><div><p className="work-breadcrumb">Công việc</p><h1>{dashboard.work.title}</h1><p className="work-goal">{dashboard.work.goal || 'Chưa đặt mục tiêu — bạn có thể bổ sung khi cần.'}</p></div><div className="work-header-status"><strong>{workStatus(dashboard.work.work_status)}</strong><span>Cập nhật {dateText(dashboard.work.updated_at)}</span>{dashboard.work.work_status !== 'completed' && <button className="btn-secondary compact-button" onClick={() => setEditingWork(current => !current)}>Chỉnh sửa</button>}{dashboard.work.work_status === 'waiting_confirmation' && <button className="btn-primary compact-button" onClick={() => void confirmCompletion}>Xác nhận hoàn tất</button>}{dashboard.work.work_status === 'completed' && <button className="btn-secondary compact-button" onClick={() => void reopen}>Mở lại Công việc</button>}</div></header>
      {editingWork && <form className="work-edit-form" onSubmit={saveWork}><label>Tên Công việc<input value={workTitle} onChange={event => setWorkTitle(event.target.value)} /></label><label>Mục tiêu<textarea value={workGoal} onChange={event => setWorkGoal(event.target.value)} rows={2} placeholder="Bạn muốn hoàn thành điều gì?" /></label><label>Phạm vi dữ liệu GYO được dùng<select value={workDataScope} onChange={event => setWorkDataScope(event.target.value as 'work_only' | 'approved_library')}><option value="work_only">Chỉ tài liệu và trao đổi của Công việc này</option><option value="approved_library">Công việc này và tri thức đã duyệt</option></select><small>Memory Hub và nhật ký kỹ thuật không tự được đưa vào chat.</small></label><label>Trạng thái<select value={workState} onChange={event => setWorkState(event.target.value as 'not_started' | 'in_progress' | 'paused')}><option value="not_started">Chưa bắt đầu</option><option value="in_progress">Đang thực hiện</option><option value="paused">Tạm dừng</option></select></label><div><button className="btn-primary compact-button" disabled={!workTitle.trim()}>Lưu thay đổi</button><button type="button" className="btn-secondary compact-button" onClick={() => setEditingWork(false)}>Hủy</button></div></form>}
      <section className="work-progress"><div><span>Tiến độ {dashboard.progress_source === 'plan_steps' ? 'tính từ kế hoạch' : 'được cập nhật thủ công'}</span><strong>{dashboard.work.progress_percent}%</strong></div><div className="progress-track" aria-label={`Tiến độ ${dashboard.work.progress_percent}%`}><span style={{ width: `${dashboard.work.progress_percent}%` }} /></div>{dashboard.next_step ? <p><Sparkles size={16} /> Tiếp theo: {dashboard.next_step.title}</p> : <p><Sparkles size={16} /> Chưa có bước nào. Hãy tạo kế hoạch để theo dõi tiến độ.</p>}</section>
      <nav className="work-tabs" aria-label="Nội dung Công việc">{tabLabels.map(([id, label]) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>{label}</button>)}</nav>
      {tab === 'overview' && <section className="work-overview-grid"><div className="work-overview-primary"><h2>Tình hình hiện tại</h2><div className="work-next-step"><ListChecks size={22} /><div><strong>{dashboard.next_step?.title || 'Chưa có bước tiếp theo'}</strong><p>{dashboard.next_step ? `${stepStatus(dashboard.next_step.status)} · ${dashboard.next_step.description || dashboard.next_step.result || 'Không có mô tả thêm.'}` : 'Tạo một giai đoạn và các bước để GYO cùng bạn theo dõi Công việc.'}</p></div></div><button className="btn-primary" onClick={() => setTab('conversations')}><MessageSquarePlus size={16} /> Mở Trao đổi</button></div><div className="work-summary-list"><div><span>Phiên trao đổi</span><strong>{dashboard.conversations.length}</strong></div><div><span>Bước cần xử lý</span><strong>{dashboard.work.blocked_step_count ?? 0}</strong></div><div><span>Đang chờ bạn duyệt</span><strong>{dashboard.pending_approval_count}</strong></div><div><span>Đầu ra đã quản lý</span><strong>{dashboard.artifacts.length}</strong></div></div><div className="work-overview-section"><h2>Đầu ra mới nhất</h2>{dashboard.artifacts.length ? dashboard.artifacts.slice(0, 3).map(item => <div className="compact-artifact" key={item.id}><FileText size={17} /><span>{item.relative_path.replace(/^outputs\//, '')}</span><time>{dateText(item.created_at)}</time></div>) : <p className="muted-copy">Chưa có đầu ra được quản lý cho Công việc này.</p>}</div></section>}
      {tab === 'plan' && <section className="work-plan"><header><div><h2>Kế hoạch Công việc</h2><p>GYO có thể đề xuất; bạn luôn có thể sửa, sắp xếp hoặc cập nhật từng bước.</p></div></header><form className="inline-create" onSubmit={addPhase}><input value={newPhase} onChange={event => setNewPhase(event.target.value)} placeholder="Tên giai đoạn, ví dụ: Thu thập thông tin" /><button className="btn-secondary" disabled={!newPhase.trim()}><Plus size={16} /> Thêm giai đoạn</button></form>{dashboard.phases.length === 0 && <div className="empty-state"><div className="empty-state-title">Chưa có kế hoạch</div><div className="empty-state-text">Thêm giai đoạn đầu tiên để tổ chức Công việc thành các bước rõ ràng.</div></div>}{dashboard.phases.map((phase, phaseIndex) => <PhaseCard key={phase.id} phase={phase} index={phaseIndex} count={dashboard.phases.length} onChange={updates => void changePhase(phase.id, updates)} onMoveUp={() => void swapPhases(phase, dashboard.phases[phaseIndex - 1])} onMoveDown={() => void swapPhases(phase, dashboard.phases[phaseIndex + 1])}>{phase.steps.map((step, stepIndex) => <PlanStepItem key={step.id} step={step} onUpdate={updates => changeStep(step.id, updates)} canMoveUp={stepIndex > 0} canMoveDown={stepIndex < phase.steps.length - 1} onMoveUp={() => void swapSteps(step, phase.steps[stepIndex - 1])} onMoveDown={() => void swapSteps(step, phase.steps[stepIndex + 1])} />)}<div className="inline-create step-create"><input value={newSteps[phase.id] || ''} onChange={event => setNewSteps(current => ({ ...current, [phase.id]: event.target.value }))} placeholder="Thêm bước công việc" /><button className="btn-secondary" type="button" onClick={() => void addStep(phase.id)} disabled={!newSteps[phase.id]?.trim()}><Plus size={15} /> Thêm bước</button></div></PhaseCard>)}</section>}
      {tab === 'conversations' && <section className="work-conversations"><aside className="conversation-list"><div className="conversation-list-header"><h2>Phiên trao đổi</h2><button className="btn-secondary compact-button" onClick={() => setNewConversation(current => !current)}><Plus size={15} /> Tạo</button></div>{newConversation && <form onSubmit={createConversationForWork} className="conversation-create"><input autoFocus value={conversationTitle} onChange={event => setConversationTitle(event.target.value)} placeholder="Tên phiên trao đổi" /><button className="btn-primary" disabled={!conversationTitle.trim()}>Tạo phiên</button></form>}{dashboard.conversations.map(item => <button key={item.id} className={`conversation-list-item ${item.id === conversationId ? 'active' : ''}`} onClick={() => setConversationId(item.id)}><strong>{item.title}</strong><span>{item.purpose || `${item.message_count} tin nhắn`}</span><time>{dateText(item.updated_at)}</time></button>)}<div className="conversation-list-header"><h3>Đã lưu trữ</h3><button className="btn-secondary compact-button" type="button" onClick={() => void loadArchivedConversations()}>Làm mới</button></div>{archivedLoading && <div className="loading-indicator">Đang tải lịch sử…</div>}{archivedError && <div className="inline-error" role="status">{archivedError}</div>}{!archivedLoading && !archivedError && archivedConversations.length === 0 && <p className="muted-copy">Chưa có phiên đã lưu trữ.</p>}{archivedConversations.map(item => <div className="conversation-list-item" key={item.id}><strong>{item.title}</strong><span>{item.message_count} tin nhắn</span><button className="btn-secondary compact-button" type="button" onClick={() => void restoreConversation(item.id)}>Khôi phục</button></div>)}</aside>{selectedConversation ? <ConversationWorkspace key={selectedConversation.id} workId={workId} conversation={selectedConversation} onRename={title => renameConversation(selectedConversation.id, title)} onArchive={() => archiveConversation(selectedConversation.id)} /> : <div className="empty-state">Tạo hoặc khôi phục một Phiên trao đổi để giao việc cho GYO.</div>}</section>}
      {tab === 'documents' && <section className="work-documents"><aside className="documents-rail"><div className="managed-documents-heading"><FolderOpen size={18} /><div><strong>Tài liệu của Công việc</strong><span>Chỉ hiển thị tài liệu thuộc Công việc hiện tại.</span></div></div><FileExplorer grouped /></aside><div className="document-editor-surface">{activeFile && openFiles.length ? <EditorPanel /> : <div className="empty-state centered-empty-state"><div className="empty-state-title">Tài liệu đầu vào, làm việc và đầu ra</div><div className="empty-state-text">Chọn một tệp ở bên trái để xem hoặc chỉnh sửa. Đầu ra nên được lưu trong thư mục outputs.</div></div>}</div></section>}
      {tab === 'outputs' && <section className="work-embedded-panel"><ReportsPanel /></section>}
      {tab === 'knowledge' && <section className="work-embedded-panel"><KnowledgePanel /></section>}
      {tab === 'capabilities' && <section className="work-capabilities"><h2>Năng lực GYO trong Công việc này</h2><p>Nội dung được tách rõ: phần đầu là những gì đã thực sự chạy trong Công việc; phần sau chỉ là các kỹ năng có thể dùng, chưa được ghi nhận là đã chạy.</p><h3>Đã dùng trong Công việc này</h3>{dashboard.capabilities_used.length ? <div className="capability-list">{dashboard.capabilities_used.map((item, index) => <div key={`${item.kind}-${item.name}-${index}`}><strong>{item.name}</strong><span>{item.kind}</span><time>{dateText(item.used_at)}</time></div>)}</div> : <div className="empty-state"><div className="empty-state-title">Chưa dùng năng lực bổ sung</div><div className="empty-state-text">Khi GYO áp dụng Skill, MCP, plugin hoặc công cụ trong Công việc này, kết quả sẽ được hiển thị tại đây.</div></div>}<h3 className="available-capabilities-heading">Có thể dùng</h3>{skillsError ? <div className="inline-error">Chưa tải được danh sách kỹ năng có thể dùng.</div> : availableSkills.length ? <div className="capability-list available-capability-list">{availableSkills.map(skill => <div key={skill.id}><strong>{skill.name}</strong><span>{skill.description || 'Kỹ năng đã duyệt và đang bật'}</span><time>Chưa dùng</time></div>)}</div> : <p className="muted-copy">Chưa có kỹ năng nào đã duyệt và bật. Bạn có thể quản lý chúng trong Thư viện tri thức.</p>}</section>}
      {tab === 'overview' && <ActionPackagesPanel workId={workId} />}
    </>}
  </div>;
};
