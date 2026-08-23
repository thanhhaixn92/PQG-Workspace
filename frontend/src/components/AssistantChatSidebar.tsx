import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, MessageCircle, Plus, RefreshCw, WifiOff } from 'lucide-react';
import { useHermesStore } from '../store/store';
import {
  resolveWorkConversationAssistantThread,
  createAssistantRun,
  getAssistantTurns,
  listAssistantThreads,
  cancelAssistantTurn,
  retryAssistantTurn,
  getAssistantContextManifest,
  type AssistantThread,
  type AssistantTurn,
  type AssistantPart,
  type AssistantContextManifest,
} from '../api/assistant';
import { getModelConfig as fetchModelConfig } from '../api/marketplace';
import type { ModelConfig } from '../api/marketplace';
import { createConversation, listConversations, type Conversation } from '../api/works';
import { getActionPackage, getWorkActionPackages, createActionPackage, approveActionPackage, denyActionPackage, type ActionPackage, type ActionPackageProposal } from '../api/actionPackages';
import { listArtifacts, type Artifact } from '../api/artifacts';
import { getWorkDashboard, type WorkDashboard } from '../api/works';
import { subscribeThreadStream } from '../assistant/threadStreamRegistry';
import { createApprovalIdempotencyRegistry } from '../assistant/approvalIdempotency';
import { ApiError } from '../api/client';
import { isTestWork } from './workTestVisibility';
import { parseGyoAssistantLocation, navigateToGyoAssistant, buildGyoAssistantUrl } from '../navigation';
import { readGyoDraft, writeGyoDraft, clearAllGyoDrafts, clearGyoDraftsByWork, removeGyoDraft, type GYODraftScope } from '../assistant/draftStorage';
import { getRuntimeIdentityScope, type RuntimeIdentityScope } from '../api/runtime';
import { GYOAssistant } from './assistant/GYOAssistant';

export interface AssistantChatSidebarProps {
  surfaceMode?: 'drawer' | 'focus';
}

const GYO_CONTEXT_SUFFIXES = ['.txt', '.md', '.csv'] as const;

const isGyoContextArtifact = (artifact: Artifact): boolean =>
  artifact.validation_status === 'structurally_validated'
  && GYO_CONTEXT_SUFFIXES.some(suffix => artifact.relative_path.toLowerCase().endsWith(suffix));

export const AssistantChatSidebar: React.FC<AssistantChatSidebarProps> = ({ surfaceMode = 'drawer' }) => {
  const focusMode = surfaceMode === 'focus';
  const sessions = useHermesStore(state => state.sessions);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const setActiveSession = useHermesStore(state => state.setActiveSession);
  const assistantSidebarMode = useHermesStore(state => state.assistantSidebarMode);
  const setAssistantSidebarMode = useHermesStore(state => state.setAssistantSidebarMode);
  const toggleAssistantSidebar = useHermesStore(state => state.toggleAssistantSidebar);
  const assistantSidebarWidth = useHermesStore(state => state.assistantSidebarWidth);
  const setAssistantSidebarWidth = useHermesStore(state => state.setAssistantSidebarWidth);

  const [threads, setThreads] = useState<AssistantThread[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [turns, setTurns] = useState<AssistantTurn[]>([]);
  const [streamedText, setStreamedText] = useState<Record<string, string>>({});
  const [manifest, setManifest] = useState<AssistantContextManifest | null>(null);
  const [artifactList, setArtifactList] = useState<Artifact[]>([]);
  const [modelConfig, setModelConfig] = useState<ModelConfig | null>(null);
  const [dashboard, setDashboard] = useState<WorkDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [creatingThread, setCreatingThread] = useState(false);
  const [showArchivedThreads] = useState(false);
  const [submitError, setSubmitError] = useState<{ category: string; message: string; actionable: boolean } | null>(null);
  const [proposalBusy, setProposalBusy] = useState<string | null>(null);
  const [, setCreatedProposals] = useState<Record<string, string>>({});
  const [, setActionPackages] = useState<ActionPackage[]>([]);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [discardDraftSignal, setDiscardDraftSignal] = useState<{
    workId: string;
    conversationId: string;
    token: number;
  } | null>(null);
  const [sidebarKey, setSidebarKey] = useState(0);
  const [identityScope, setIdentityScope] = useState<RuntimeIdentityScope | null>(null);

  const requestGeneration = useRef(0);
  const bootstrapGenerationRef = useRef(0);
  const selectedThreadRef = useRef<string | null>(null);
  const turnsRef = useRef<AssistantTurn[]>([]);
  const actionsGeneration = useRef(0);
  const scopeKeyRef = useRef<string>('');
  const scopeGenerationRef = useRef(0);
  const inFlightResolverRef = useRef<{ scopeKey: string; promise: Promise<AssistantThread | null> } | null>(null);
  const submitInFlightRef = useRef(false);
  const approvalKeySequenceRef = useRef(0);
  const approvalIdempotencyRegistryRef = useRef(
    createApprovalIdempotencyRegistry(() => {
      const uuid = globalThis.crypto?.randomUUID?.();
      if (uuid) return `chat-approve-${uuid}`;
      approvalKeySequenceRef.current += 1;
      return `chat-approve-fallback-${approvalKeySequenceRef.current}`;
    }),
  );
  const resizeRef = useRef<HTMLDivElement | null>(null);
  const returnFocusRef = useRef<HTMLElement | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [isOverlay, setIsOverlay] = useState(() => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 1439px)').matches);

  useEffect(() => { selectedThreadRef.current = threadId; }, [threadId]);
  useEffect(() => { turnsRef.current = turns; }, [turns]);

  // The backend deliberately returns only opaque scopes. Until it succeeds we
  // neither restore nor persist a draft, avoiding cross-identity leakage.
  useEffect(() => {
    let cancelled = false;
    void getRuntimeIdentityScope()
      .then(scope => { if (!cancelled) setIdentityScope(scope); })
      .catch(() => { if (!cancelled) setIdentityScope(null); });
    return () => { cancelled = true; };
  }, [sidebarKey]);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const media = window.matchMedia('(max-width: 1439px)');
    const syncOverlay = () => setIsOverlay(media.matches);
    syncOverlay();
    media.addEventListener('change', syncOverlay);
    return () => media.removeEventListener('change', syncOverlay);
  }, []);

  useEffect(() => {
    if (assistantSidebarMode !== 'expanded') return;
    const activeElement = document.activeElement;
    if (activeElement instanceof HTMLElement && !resizeRef.current?.contains(activeElement)) returnFocusRef.current = activeElement;
    resizeRef.current?.querySelector<HTMLElement>('button:not(:disabled), select:not(:disabled), textarea:not(:disabled), input:not(:disabled)')?.focus();
  }, [assistantSidebarMode]);

  useEffect(() => {
    if (assistantSidebarMode === 'expanded') return;
    const focusTarget = returnFocusRef.current?.isConnected ? returnFocusRef.current : document.querySelector<HTMLElement>('.assistant-toggle');
    if (focusTarget) requestAnimationFrame(() => focusTarget.focus());
  }, [assistantSidebarMode]);

  useEffect(() => {
    if (assistantSidebarMode !== 'expanded') return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); setAssistantSidebarMode('collapsed'); return; }
      if (event.key !== 'Tab' || !isOverlay || !resizeRef.current) return;
      const focusable = [...resizeRef.current.querySelectorAll<HTMLElement>('button:not(:disabled), select:not(:disabled), textarea:not(:disabled), input:not(:disabled)')];
      if (!focusable.length) return;
      const first = focusable[0]; const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [assistantSidebarMode, isOverlay, setAssistantSidebarMode]);

  // --- Account/workspace change listeners for draft clearing ---
  useEffect(() => {
    const handleLogout = () => {
      clearAllGyoDrafts(window.sessionStorage);
    };
    const handleWorkspaceChange: EventListener = event => {
      const e = event as CustomEvent<{ workspaceId?: string; workId?: string }>;
      const newWs = e.detail?.workspaceId;
      const newWork = e.detail?.workId;
      if (newWs && newWork && identityScope) {
        clearGyoDraftsByWork(window.sessionStorage, {
          identityScope: identityScope.identity_scope,
          workspaceScope: newWs,
          workId: newWork,
        });
      }
    };

    window.addEventListener('hermes:logout', handleLogout);
    window.addEventListener('hermes:workspace-change', handleWorkspaceChange);

    return () => {
      window.removeEventListener('hermes:logout', handleLogout);
      window.removeEventListener('hermes:workspace-change', handleWorkspaceChange);
    };
  }, [identityScope]);

  // --- Parse URL for canonical routing ---
  const visibleWorks = useMemo(() => sessions.filter(work => work.id !== 'test' && !isTestWork(work)), [sessions]);
  const selectedWork = useMemo(() => visibleWorks.find(w => w.id === activeSessionId) ?? null, [activeSessionId, visibleWorks]);
  const selectedConversation = useMemo(() => conversations.find(c => c.id === conversationId && c.status === 'active') ?? null, [conversationId, conversations]);

  // Sync URL params to state when present (canonical URL restore)
  useEffect(() => {
    const loc = parseGyoAssistantLocation();
    if (loc.isAssistantRoute && loc.workId) {
      const workSession = sessions.find(w => w.id === loc.workId);
      if (workSession && loc.workId !== activeSessionId) {
        setActiveSession(loc.workId);
      }

      if (loc.conversationId && loc.conversationId !== conversationId) {
        setConversationId(loc.conversationId);
      }
      if (loc.threadId && loc.threadId !== threadId) {
        setThreadId(loc.threadId);
      }
    }
  }, [sessions, activeSessionId, conversationId, threadId, sidebarKey, setActiveSession]);

  const currentScopeKey = (selectedWork?.id ?? '') + ':' + (selectedConversation?.id ?? '');

  // Scope key + generation: incremented ONLY when Work/Conversation changes to reject stale results.
  useEffect(() => {
    if (scopeKeyRef.current === currentScopeKey) return;
    scopeKeyRef.current = currentScopeKey;
    scopeGenerationRef.current += 1;
    inFlightResolverRef.current = null;
  }, [currentScopeKey]);

  const loadThread = useCallback(async (id: string, expectedScope: string) => {
    if (!id) return;
    if (scopeKeyRef.current !== expectedScope) return;
    const gen = ++requestGeneration.current;
    const sgGen = scopeGenerationRef.current;
    setThreadId(id);
    try {
      const nextTurns = await getAssistantTurns(id);
      if (gen === requestGeneration.current && sgGen === scopeGenerationRef.current && scopeKeyRef.current === expectedScope) {
        setTurns(nextTurns);
      }
    } catch {
      if (gen === requestGeneration.current && sgGen === scopeGenerationRef.current && scopeKeyRef.current === expectedScope) {
        // Silent — backend state remains authoritative.
      }
    }
  }, []);

  const loadThreads = useCallback(async () => {
    const currentScope = scopeKeyRef.current;
    try {
      const nextThreads = await listAssistantThreads(showArchivedThreads);
      if (scopeKeyRef.current !== currentScope) return;
      setThreads(nextThreads);
      setBackendOnline(true);
      const current = nextThreads.find(t => t.id === selectedThreadRef.current);
      if (current) void loadThread(current.id, currentScope);
      else { setThreadId(null); setTurns([]); }
    } catch {
      if (scopeKeyRef.current === currentScope) setBackendOnline(false);
      // Silent — UI shows empty state.
    }
  }, [loadThread, showArchivedThreads]);

  const loadActionPackages = useCallback(async (workId?: string | null) => {
    const generation = ++actionsGeneration.current;
    if (!workId) { setActionPackages([]); return; }
    try {
      const next = await getWorkActionPackages(workId);
      if (generation !== actionsGeneration.current) return;
      setActionPackages(next);
    } catch {
      // Silent — empty list.
    }
  }, []);

  const loadDashboard = useCallback(async (workId: string) => {
    try {
      const dash = await getWorkDashboard(workId);
      setDashboard(dash);
    } catch {
      setDashboard(null);
    }
  }, []);

  const loadModelConfig = useCallback(async () => {
    try {
      const config = await fetchModelConfig();
      setModelConfig(config);
    } catch {
      setModelConfig(null);
    }
  }, []);

  const loadArtifacts = useCallback(async (workId: string) => {
    try {
      const artifacts = await listArtifacts(workId);
      setArtifactList(artifacts);
    } catch {
      setArtifactList([]);
    }
  }, []);

  const bootstrap = useCallback(async () => {
    const bootstrapGeneration = ++bootstrapGenerationRef.current;
    if (!selectedWork) {
      setThreads([]); setTurns([]); setConversationId(null); setThreadId(null);
      setConversations([]); setDashboard(null); setManifest(null);
      setArtifactList([]); setModelConfig(null); setLoading(false);
      return;
    }
    setLoading(true);
    setBackendOnline(null);
    await loadDashboard(selectedWork.id);
    void loadArtifacts(selectedWork.id);
    void loadModelConfig();
    await loadThreads();
    void loadActionPackages(selectedWork.id);
    if (bootstrapGeneration === bootstrapGenerationRef.current) setLoading(false);
  }, [selectedWork, loadThreads, loadArtifacts, loadModelConfig, loadDashboard, loadActionPackages]);

  // Load threads when sidebar becomes visible (even without a work selected)
  useEffect(() => {
    if (assistantSidebarMode === 'expanded' && !selectedWork) {
      void loadThreads();
    }
  }, [assistantSidebarMode, selectedWork, loadThreads]);

  useEffect(() => { void bootstrap(); }, [bootstrap]);

  // Load conversations for the selected work
  useEffect(() => {
    let cancelled = false;
    if (!activeSessionId) { setConversations([]); setConversationId(null); return; }
    setConversations([]);
    setConversationId(null);
    requestGeneration.current += 1;
    selectedThreadRef.current = null;
    setThreadId(null); setTurns([]); setStreamedText({}); setSubmitError(null); setManifest(null);

    void listConversations(activeSessionId).then(items => {
      if (!cancelled) {
        const activeItems = items.filter(i => i.status === 'active').sort((l, r) => r.updated_at - l.updated_at);
        setConversations(activeItems);
        setConversationId(current => activeItems.some(i => i.id === current) ? current : (activeItems[0]?.id ?? null));
      }
    }).catch(() => { setConversations([]); });

    return () => { cancelled = true; };
  }, [activeSessionId]);

  const draftScope = useMemo<GYODraftScope | null>(() => {
    if (!identityScope || !activeSessionId || !conversationId) return null;
    return {
      identityScope: identityScope.identity_scope,
      workspaceScope: identityScope.workspace_scope,
      workId: activeSessionId,
      conversationId,
    };
  }, [activeSessionId, conversationId, identityScope]);

  // Load draft from sessionStorage when its server-owned scope changes.
  useEffect(() => {
    if (!draftScope) { setDraft(''); setModelChoice('auto'); setAttachmentIds([]); return; }
    const saved = readGyoDraft(window.sessionStorage, draftScope) ?? undefined;
    if (saved) {
      setDraft(saved.prompt);
      setModelChoice(saved.modelChoice || 'auto');
      setAttachmentIds(saved.attachmentIds);
    } else {
      setDraft('');
      setModelChoice('auto');
      setAttachmentIds([]);
    }
  }, [draftScope]);

  // Save draft to sessionStorage on change
  const [draft, setDraft] = useState('');
  const [modelChoice, setModelChoice] = useState('auto');
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);

  useEffect(() => {
    if (!draftScope) return;
    writeGyoDraft(window.sessionStorage, draftScope, {
      prompt: draft, modelChoice, attachmentIds, createdAt: Date.now(), updatedAt: Date.now(),
    });
  }, [attachmentIds, draft, modelChoice, draftScope]);

  // Reset stale thread/turns/stream when Conversation changes within the same Work.
  useEffect(() => {
    if (!selectedWork) return;
    requestGeneration.current += 1;
    selectedThreadRef.current = null;
    setThreadId(null); setTurns([]); setStreamedText({}); setManifest(null);
  }, [selectedWork, conversationId]);

  // Reset conversationId when Work scope changes (prevents stale conversation from leaking)
  useEffect(() => {
    if (!selectedWork) {
      setConversationId(null);
    } else if (selectedConversation && selectedConversation.session_id !== selectedWork.id) {
      setConversationId(null);
    }
  }, [selectedWork, selectedConversation]);

  // Context manifest
  useEffect(() => {
    const controller = new AbortController();
    // Only use conversationId if it belongs to the currently selected work.
    const scopedConversationId = (conversations.length > 0 && activeSessionId && selectedConversation?.session_id === activeSessionId)
      ? selectedConversation?.id ?? null
      : null;
    void getAssistantContextManifest(activeSessionId, scopedConversationId, null, controller.signal)
      .then(setManifest)
      .catch(error => { if ((error as Error).name !== 'AbortError') setManifest(null); });
    return () => controller.abort();
  }, [activeSessionId, conversations.length, selectedConversation?.id, selectedConversation?.session_id]);

  // Action packages sync
  useEffect(() => { void loadActionPackages(activeSessionId); }, [activeSessionId, loadActionPackages]);

  // SSE stream for active turns
  useEffect(() => {
    if (!threadId || !turns.some(turn => turn.status === 'running')) return;
    const subscribedThreadId = threadId;
    const subscribedScopeKey = scopeKeyRef.current;
    const subscribedScopeGeneration = scopeGenerationRef.current;
    let refreshQueued = false;

    const onEvent = (event: { type: string; data: string }) => {
      if (scopeKeyRef.current !== subscribedScopeKey || scopeGenerationRef.current !== subscribedScopeGeneration) return;
      if (event.type === 'token') {
        try {
          const payload = JSON.parse(event.data) as { text?: unknown; assistant_turn_id?: unknown; thread_id?: unknown };
          if (payload.thread_id !== subscribedThreadId || typeof payload.text !== 'string' || !payload.text || typeof payload.assistant_turn_id !== 'string') return;
          setStreamedText(current => {
            const activeTurn = turnsRef.current.find(t => t.id === payload.assistant_turn_id && t.role === 'assistant' && t.status === 'running');
            return activeTurn ? { ...current, [activeTurn.id]: `${current[activeTurn.id] ?? ''}${payload.text}` } : current;
          });
        } catch { /* ignore — backend turns remain authoritative */ }
      } else if (event.type === 'done' || event.type === 'error') {
        if (!refreshQueued && selectedThreadRef.current === subscribedThreadId) {
          refreshQueued = true;
          setStreamedText({});
          void loadThread(subscribedThreadId, scopeKeyRef.current);
        }
      }
    };

    const unsubscribe = subscribeThreadStream(threadId, onEvent);
    return () => {
      unsubscribe();
    };
  }, [threadId, loadThread, turns]);

  // URL sync: update canonical URL when work/conversation/thread changes
  const syncUrl = useCallback(() => {
    if (!selectedWork?.id) return;
    const currentUrl = parseGyoAssistantLocation();
    if (currentUrl.isAssistantRoute && currentUrl.workId === selectedWork.id) {
      const needsUpdate =
        currentUrl.conversationId !== conversationId ||
        currentUrl.threadId !== threadId;
      if (!needsUpdate) return;
      navigateToGyoAssistant(selectedWork.id, conversationId, threadId, true);
    }
  }, [selectedWork?.id, conversationId, threadId]);

  useEffect(() => { syncUrl(); }, [syncUrl]);

  const createThread = async () => {
    if (creatingThread || !selectedWork) return;
    setCreatingThread(true);
    try {
      const createdConversation = await createConversation(selectedWork.id, `Trao đổi: ${selectedWork.title}`);
      const created = await resolveWorkConversationAssistantThread(selectedWork.id, createdConversation.id);
      setConversations(current => [createdConversation, ...current]);
      setConversationId(createdConversation.id);
      setThreads(current => [created, ...current]);
      setTurns([]);
      setThreadId(created.id);
      // Update URL to canonical with new conversation + thread
      navigateToGyoAssistant(selectedWork.id, createdConversation.id, created.id, true);
    } catch {
      setSubmitError({ category: 'generic', message: 'Không tạo được phiên trao đổi.', actionable: true });
    } finally {
      setCreatingThread(false);
    }
  };

  const selectedThread = useMemo(() => threads.find(t => t.id === threadId) ?? null, [threadId, threads]);

  // Auto-select an active thread for the current scope when scope changes.
  useEffect(() => {
    if (!selectedWork || !selectedConversation) return;
    const activeThread = threads.find(t => t.work_id === selectedWork.id && t.conversation_id === selectedConversation.id && t.status === 'active');
    if (activeThread && activeThread.id !== threadId) {
      void loadThread(activeThread.id, scopeKeyRef.current);
    }
  }, [selectedWork, selectedConversation, threads, loadThread, threadId]);

  // Submit handler
  const submit = async (promptText: string, routeModelChoice?: string, attachmentIds: string[] = []) => {
    if (!selectedWork || !selectedConversation || sending) return;
    const snapshotWorkId = selectedWork.id;
    const snapshotConvId = selectedConversation.id;
    const snapshotDraftScope = draftScope;
    const currentSubmitScopeKey = `${snapshotWorkId}:${snapshotConvId}`;

    if (scopeKeyRef.current !== currentSubmitScopeKey) {
      scopeKeyRef.current = currentSubmitScopeKey;
      scopeGenerationRef.current += 1;
      inFlightResolverRef.current = null;
    }
    const snapshotScopeKey = scopeKeyRef.current;
    const snapshotGeneration = scopeGenerationRef.current;
    if (submitInFlightRef.current) return;
    submitInFlightRef.current = true;

    const value = promptText.trim();
    setSubmitError(null);
    setSending(true);

    const scopeChanged = () => scopeKeyRef.current !== snapshotScopeKey || scopeGenerationRef.current !== snapshotGeneration;

    try {
      const thread = await (async () => {
        const existingActive = threads.find(t =>
          t.work_id === snapshotWorkId
          && t.conversation_id === snapshotConvId
          && t.status === 'active'
        );
        if (existingActive) return existingActive;

        const currentResolver = inFlightResolverRef.current;
        if (currentResolver?.scopeKey === snapshotScopeKey) {
          return currentResolver.promise.then(result => {
            if (scopeKeyRef.current !== snapshotScopeKey) return null;
            if (scopeGenerationRef.current !== snapshotGeneration) return null;
            return result;
          });
        }

        let resolverEntry: { scopeKey: string; promise: Promise<AssistantThread | null> } | null = null;
        const resolverPromise = (async () => {
          try {
            const resolved = await resolveWorkConversationAssistantThread(snapshotWorkId, snapshotConvId);
            if (scopeKeyRef.current !== snapshotScopeKey) return null;
            if (scopeGenerationRef.current !== snapshotGeneration) return null;
            if (resolved.status !== 'active') return null;
            if (resolved.work_id !== snapshotWorkId || resolved.conversation_id !== snapshotConvId) return null;

            setThreads(current => current.some(t => t.id === resolved.id) ? current : [resolved, ...current]);
            void loadThread(resolved.id, snapshotScopeKey);
            return resolved;
          } catch {
            if (scopeKeyRef.current !== snapshotScopeKey) return null;
            if (scopeGenerationRef.current !== snapshotGeneration) return null;
            return null;
          } finally {
            if (resolverEntry !== null && inFlightResolverRef.current === resolverEntry) {
              inFlightResolverRef.current = null;
            }
          }
        })();

        resolverEntry = { scopeKey: snapshotScopeKey, promise: resolverPromise };
        inFlightResolverRef.current = resolverEntry;
        return resolverPromise;
      })();

      if (scopeChanged()) throw new Error('Scope changed during resolution');
      if (!thread) throw new Error('Failed to resolve conversation thread');
      if (scopeChanged()) throw new Error('Scope changed');

      const routeChoice = {
        routeMode: 'auto' as const,
        planStepId: null,
        modelProfileId: routeModelChoice && routeModelChoice !== 'auto' ? routeModelChoice : null,
      };

      const created = await createAssistantRun(
        thread.id, value, snapshotWorkId, snapshotConvId,
        attachmentIds, routeChoice
      );
      if (scopeChanged()) return;
      setTurns(current => [...current, ...created]);
      setDraft('');
      setAttachmentIds([]);
    } catch (caught) {
      const isScopeConflict = caught instanceof ApiError && caught.status === 409;
      const isCurrentSubmitScope = !scopeChanged();

      if (isCurrentSubmitScope) {
        setSubmitError({
          category: isScopeConflict ? 'conflict' : 'generic',
          message: isScopeConflict
            ? 'Không thể bắt đầu hoặc gửi lại phản hồi vì phạm vi hoặc trạng thái chạy đã thay đổi. Bản nháp vẫn được giữ.'
            : (caught instanceof Error ? caught.message : 'Không gửi được yêu cầu. Bản nháp vẫn được giữ để bạn thử lại.'),
          actionable: true,
        });
      }
      // Only re-throw if the scope hasn't changed — when scope changed,
      // the rejection is stale and should be silently discarded.
      // GYOAssistant's handleSubmit uses the throw to decide whether to clear the draft.
      if (isCurrentSubmitScope) throw caught;
      // Stale rejection after scope change — remove only the current conversation's
      // draft from sessionStorage. Do NOT clear sibling conversation drafts.
      if (!isCurrentSubmitScope) {
        if (snapshotDraftScope) removeGyoDraft(window.sessionStorage, snapshotDraftScope);
        setDiscardDraftSignal(previous => ({
          workId: snapshotWorkId,
          conversationId: snapshotConvId,
          token: (previous?.token ?? 0) + 1,
        }));
      }
    } finally {
      setSending(false);
      submitInFlightRef.current = false;
    }
  };

  const retryTurn = async (turnId: string, mode: 'same_model' | 'auto' = 'same_model') => {
    if (sending) return;
    setSending(true);
    setSubmitError(null);
    try {
      const retried = await retryAssistantTurn(turnId, mode);
      setTurns(current => [...current, retried]);
    } catch (caught) {
      setSubmitError({
        category: caught instanceof ApiError && caught.status === 409 ? 'conflict' : 'generic',
        message: caught instanceof ApiError && caught.status === 409
          ? 'Không thể gửi lại phản hồi vì phạm vi hoặc trạng thái chạy đã thay đổi.'
          : 'Không thể gửi lại phản hồi này.',
        actionable: true,
      });
    } finally {
      setSending(false);
    }
  };

  const cancelTurn = async (turnId: string) => {
    if (sending) return;
    setSending(true);
    try {
      const cancelled = await cancelAssistantTurn(turnId);
      setTurns(current => current.map(t => t.id === turnId ? cancelled : t));
    } catch {
      // Silent — backend state remains authoritative.
    } finally {
      setSending(false);
    }
  };

  const createProposal = async (part: AssistantPart) => {
    const title = typeof part.content.title === 'string' ? part.content.title : '';
    const steps = Array.isArray(part.content.steps) ? part.content.steps : [];
    if (!title || !steps.length || proposalBusy) return;
    setProposalBusy(part.id);
    try {
      const proposal: ActionPackageProposal = {
        title,
        description: typeof part.content.description === 'string' ? part.content.description : undefined,
        conversation_id: selectedConversation?.id ?? '',
        steps,
      };
      const created = await createActionPackage(activeSessionId ?? '', proposal, `chat-proposal-${part.id}`);
      setCreatedProposals(current => ({ ...current, [part.id]: created.id }));
    } catch {
      // Silent — no action taken.
    } finally {
      setProposalBusy(null);
    }
  };

  const handleApproveConfirmation = async (
    packageId: string,
    expectedRevision?: number | null,
    expectedPayloadHash?: string | null,
  ) => {
    // Fail-closed: required canonical values must be present.
    // This is enforced in both the UI (disabled CTA) and the API client.
    if (expectedRevision == null || typeof expectedRevision !== 'number' || !expectedPayloadHash) {
      setSubmitError({
        category: 'permission',
        message: 'Chưa thể xác nhận an toàn; dữ liệu xác nhận chưa đầy đủ.',
        actionable: false,
      });
      return;
    }
    setSubmitError(null);
    try {
      const canonical = await getActionPackage(packageId);
      if (canonical.revision !== expectedRevision || canonical.payload_hash !== expectedPayloadHash) {
        throw new ApiError(409, 'Gói thay đổi đã thay đổi; cần tải lại trước khi xác nhận.');
      }
      const idempotencyKey = approvalIdempotencyRegistryRef.current.get({
        packageId,
        expectedRevision,
        expectedPayloadHash,
      });
      await approveActionPackage(packageId, { expectedRevision, expectedPayloadHash }, idempotencyKey);
      void loadActionPackages(activeSessionId ?? null);
    } catch (e: unknown) {
      const err = e as Error;
      setSubmitError({
        category: e instanceof ApiError && e.status === 409 ? 'conflict' : 'generic',
        message: e instanceof ApiError && e.status === 409
          ? 'Mục đã được xử lý ở nơi khác.'
          : (err?.message || 'Không thể xác nhận cho GYO thực thi.'),
        actionable: true,
      });
    }
  };

  const handleDenyConfirmation = async (packageId: string, expectedRevision: number, expectedPayloadHash: string) => {
    setSubmitError(null);
    try {
      const canonical = await getActionPackage(packageId);
      if (canonical.revision !== expectedRevision || canonical.payload_hash !== expectedPayloadHash) {
        throw new ApiError(409, 'Gói thay đổi đã thay đổi; cần tải lại trước khi từ chối.');
      }
      const idempotencyKey = approvalIdempotencyRegistryRef.current.get({ packageId, expectedRevision, expectedPayloadHash });
      await denyActionPackage(packageId, { expectedRevision, expectedPayloadHash }, idempotencyKey);
      void loadActionPackages(activeSessionId ?? null);
    } catch {
      setSubmitError({
        category: 'generic',
        message: 'Không thể từ chối yêu cầu này.',
        actionable: true,
      });
    }
  };

  const handleNavigateToFocus = (workId?: string | null, convId?: string | null, threadIdParam?: string | null) => {
    const targetWork = workId ?? selectedWork?.id ?? null;
    const targetConv = convId ?? conversationId ?? null;
    const targetThread = threadIdParam ?? threadId ?? null;

    if (targetWork) {
      const url = buildGyoAssistantUrl(targetWork, targetConv, targetThread);
      window.open(url, '_blank');
    }
  };

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault(); e.stopPropagation();
    setIsResizing(true);
    const startX = e.clientX;
    const startWidth = assistantSidebarWidth;
    const onMouseMove = (moveEvent: MouseEvent) => {
      const deltaX = startX - moveEvent.clientX;
      setAssistantSidebarWidth(startWidth + deltaX);
    };
    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      setIsResizing(false);
    };
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  const workArchived = Boolean(dashboard?.work?.archived);

  const handleDraftChanged = (value: string, model: string, nextAttachmentIds: string[] = attachmentIds) => {
    setDraft(value);
    setModelChoice(model);
    setAttachmentIds(nextAttachmentIds);
  };

  // Build the attachments that the user has selected (from artifact list by ids)
  const availableAttachments = useMemo(() => {
    return artifactList.filter(isGyoContextArtifact);
  }, [artifactList]);

  if (!focusMode && assistantSidebarMode === 'hidden') return null;

  // Render collapsed state
  if (!focusMode && assistantSidebarMode === 'collapsed') {
    return (
      <div className="assistant-sidebar-collapsed">
        <button
          className="collapse-toggle"
          onClick={toggleAssistantSidebar}
          aria-label="Mở rộng Trợ lý GYO"
        >
          <MessageCircle size={24} />
        </button>
        <div className="collapse-toggle-bottom">
          <button className="collapse-toggle" onClick={toggleAssistantSidebar} aria-label="Mở rộng">
            <ChevronRight size={20} />
          </button>
        </div>
      </div>
    );
  }

  const assistantSurface = (
    <GYOAssistant
      workId={selectedWork?.id ?? null}
      conversationId={conversationId}
      threadId={threadId}
      mode={focusMode ? 'focus' : 'drawer'}
      visible={true}
      discardDraftSignal={discardDraftSignal}
      threads={threads}
      turns={turns}
      streamedText={streamedText}
      manifest={manifest}
      artifacts={availableAttachments}
      modelConfig={modelConfig}
      workArchived={workArchived}
      restoredDraft={draft}
      restoredModelChoice={modelChoice}
      restoredAttachmentIds={attachmentIds}
      error={submitError}
      loading={loading && !selectedThread}
      onNavigateToFocus={handleNavigateToFocus}
      onSubmitPrompt={submit}
      onCancelTurn={cancelTurn}
      onRetryTurn={retryTurn}
      onCreateProposal={createProposal}
      onApproveConfirmation={handleApproveConfirmation}
      onDenyConfirmation={handleDenyConfirmation}
      onDraftChanged={handleDraftChanged}
    />
  );

  if (focusMode) return assistantSurface;

  return (
    <>
      <button className="assistant-scrim" aria-label="Đóng Trợ lý GYO" onClick={toggleAssistantSidebar} />
      <div
        className="assistant-sidebar"
        ref={resizeRef}
        role={isOverlay ? 'dialog' : 'complementary'}
        aria-modal={isOverlay || undefined}
        aria-label="Trợ lý GYO"
        style={{ '--assistant-panel-width': `${assistantSidebarWidth}px` } as React.CSSProperties}
      >
        {backendOnline === false && activeSessionId && (
          <div className="gyo-backend-status" role="status" aria-label="Trạng thái kết nối backend">
            <WifiOff size={14} aria-hidden="true" />
            <span>Mất kết nối đến backend. Dữ liệu có thể lỗi thời.</span>
            <button className="icon-button" onClick={() => { setSidebarKey(k => k + 1); }} aria-label="Làm mới">
              <RefreshCw size={14} />
            </button>
          </div>
        )}
        {backendOnline === false && (
          <div className="gyo-backend-warning" role="alert">
            <WifiOff size={12} /> Không thể kết nối backend local. GYO tạm thời không khả dụng.
          </div>
        )}

        {/* Header with collapse/hide controls for drawer mode */}
        <div className="assistant-sidebar-header">
          <h2 className="assistant-sidebar-title">Trợ lý GYO</h2>
          <div className="assistant-sidebar-header-actions">
            <button
              className="icon-button"
              onClick={toggleAssistantSidebar}
              aria-label="Thu gọn"
            >
              <ChevronLeft size={14} />
            </button>
          </div>
        </div>

        {assistantSurface}

        {/* Onboarding overlay when work is selected but no conversation */}
        {selectedWork && !conversationId && (
          <div className="gyo-onboarding-overlay" aria-hidden={!workArchived ? undefined : true}>
            <p className="gyo-onboarding-text">Chọn cuộc trao đổi</p>
            <small className="gyo-onboarding-hint">
              Tạo hoặc chọn một cuộc trao đổi để bắt đầu với GYO.
            </small>
          </div>
        )}

        {/* Work & Conversation Selector - kept for drawer mode */}
        <div className="gyo-drawer-selector">
          <div className="gyo-selector-group">
            <label>Công việc</label>
            <select
              value={activeSessionId ?? ''}
              onChange={e => {
                const val = e.target.value || null;
                setActiveSession(val);
                if (val) {
                  navigateToGyoAssistant(val);
                }
              }}
            >
              <option value="">Chọn Công việc</option>
              {visibleWorks.map(w => <option key={w.id} value={w.id}>{w.title}</option>)}
            </select>
          </div>

          {selectedWork && (
            <div className="gyo-selector-group">
              <label>Cuộc trao đổi</label>
              <div className="gyo-selector-row">
                <select
                  aria-label="Cuộc trao đổi"
                  value={conversationId ?? ''}
                  onChange={e => setConversationId(e.target.value || null)}
                  disabled={!selectedConversation}
                >
                  <option value="">Chọn hoặc tạo mới</option>
                  {conversations.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
                </select>
                <button
                  onClick={createThread}
                  disabled={creatingThread || !selectedWork || selectedThread?.status === 'archived'}
                  aria-label="Cuộc trao đổi mới"
                >
                  <Plus size={14} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Resize handle */}
        <div
          className={`resize-handle ${isResizing ? 'resizing' : ''}`}
          onMouseDown={handleResizeStart}
          aria-label="Thay đổi chiều rộng sidebar"
        />
      </div>
    </>
  );
};
