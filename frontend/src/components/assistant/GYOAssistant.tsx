import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertCircle, CheckCircle, Clock, ExternalLink, Hash, List, Loader2,
  Lock, LogIn, Pause, RefreshCw, Send, Settings, WifiOff, X,
} from 'lucide-react';
import type {
  AssistantPart, AssistantThread, AssistantTurn,
  AssistantContextManifest,
} from '../../api/assistant';
import {
  getActionPackage, getActionPackagePreflight, getActionPackagePreflightDecisionBinding,
  type ActionPackage, type ActionPackagePreflight,
} from '../../api/actionPackages';
import type { Artifact } from '../../api/artifacts';
import type { GyoModel, GyoProvider, ModelConfig } from '../../api/marketplace';
import { ASSISTANT_NAME } from '../../branding';
import { ApiError } from '../../api/client';

import { AssistantTurnCard } from './TurnPartRenderer';
import { ContextPanel } from './ContextPanel';
import { HistoryPanel } from './HistoryPanel';

/**
 * Canonical GYO assistant surface — shared by drawer and focus mode.
 * Renders only canonical backend state. Does not fake approval/progress/completion/rollback.
 */

export type GYOMode = 'drawer' | 'focus';
const EMPTY_ATTACHMENT_IDS: string[] = [];

export interface GYOAssistantProps {
  /** Work session id from URL. */
  workId: string | null;
  /** Conversation id from URL query param (optional at surface level). */
  conversationId: string | null;
  /** Thread id from URL query param (optional; resolved from conversation if absent). */
  threadId: string | null;
  /** Surface mode. */
  mode: GYOMode;
  /** Whether the surface is visible. */
  visible: boolean;
  /** All assistant threads for the work. */
  threads: AssistantThread[];
  /** Turns for the active thread. */
  turns: AssistantTurn[];
  /** Streamed text keyed by turn id. */
  streamedText: Record<string, string>;
  /** Context manifest. */
  manifest: AssistantContextManifest | null;
  /** Available artifacts for attachment. */
  artifacts: Artifact[];
  /** Model config (providers, models, defaults). */
  modelConfig: ModelConfig | null;
  /** Work archived flag. */
  workArchived: boolean;
  /** Restored only from the server-scoped session draft namespace. */
  restoredDraft?: string;
  restoredModelChoice?: string;
  restoredAttachmentIds?: string[];
  /** Error state. */
  error: { category: string; message: string; actionable: boolean } | null;
  /** Loading state. */
  loading: boolean;
  /**
   * Exact draft scope that must be discarded after a stale request settles.
   * The signal is intentionally scoped: a stale request for conversation A
   * must never clear the draft/model/attachments currently shown for B.
   */
  discardDraftSignal?: { workId: string; conversationId: string; token: number } | null;

  /** Actions */
  onNavigateToFocus: (workId?: string | null, conversationId?: string | null, threadId?: string | null) => void;
  onSubmitPrompt: (
    prompt: string,
    modelChoice?: string,
    attachmentIds?: string[],
  ) => Promise<void>;
  onCancelTurn: (turnId: string) => Promise<void>;
  onRetryTurn: (turnId: string, mode?: 'same_model' | 'auto') => Promise<void>;
  onCreateProposal: (part: AssistantPart) => Promise<void>;
  onApproveConfirmation: (
    packageId: string,
    expectedRevision?: number | null,
    expectedPayloadHash?: string | null,
  ) => Promise<void>;
  onDenyConfirmation: (packageId: string, expectedRevision: number, expectedPayloadHash: string) => Promise<void>;
  onDraftChanged: (prompt: string, modelChoice: string, attachmentIds: string[]) => void;
}

interface ComposerProps {
  prompt: string;
  onPromptChange: (value: string) => void;
  modelChoice: string;
  onModelChoice: (value: string) => void;
  availableModels: GyoModel[];
  providers: GyoProvider[];
  attachments: Artifact[];
  availableArtifacts: Artifact[];
  onAddAttachment: (id: string) => void;
  onRemoveAttachment: (id: string) => void;
  onSubmit: () => Promise<void>;
  sending: boolean;
  canSubmit: boolean;
  workArchived: boolean;
  disabled: boolean;
}

function ModelCapabilitySelector({
  modelChoice,
  onModelChoice,
  availableModels,
  providers,
}: {
  modelChoice: string;
  onModelChoice: (value: string) => void;
  availableModels: GyoModel[];
  providers: GyoProvider[];
}) {
  const validModels = availableModels.filter(m => m.enabled && m.capabilities.includes('chat'));

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onModelChoice(e.target.value);
  };

  if (!validModels.length) {
    return (
      <span className="gyo-model-selector gyo-model-selector--empty" title="Chưa có model nào khả dụng">
        <Settings size={14} /> Tự động
      </span>
    );
  }

  const isAuto = modelChoice === 'auto' || modelChoice === '';

  return (
    <div className="gyo-model-selector-container">
      <label htmlFor="gyo-model-choice" className="gyo-model-selector-label">
        <Settings size={14} aria-hidden="true" /> Cách {ASSISTANT_NAME} xử lý
      </label>
      <select
        id="gyo-model-choice"
        className="gyo-model-select"
        value={modelChoice || 'auto'}
        onChange={handleChange}
        aria-label="Chọn model xử lý"
        title={isAuto ? 'GYO sẽ chọn model tự động' : `Đang dùng: ${validModels.find(m => m.id === modelChoice)?.display_name || modelChoice}`}
      >
        <option value="auto">Tự động (GYO chọn model phù hợp)</option>
        {providers.map(p => (
          <optgroup key={p.id} label={p.display_name}>
            {validModels.filter(m => m.provider_profile_id === p.id).map(m => (
              <option key={m.id} value={m.id}>
                {m.display_name} {m.is_default ? '(mặc định)' : ''} {m.cost_class === 'free' ? '— miễn phí' : ''}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
  );
}

function Composer({
  prompt,
  onPromptChange,
  modelChoice,
  onModelChoice,
  availableModels,
  providers,
  attachments,
  availableArtifacts,
  onAddAttachment,
  onRemoveAttachment,
  onSubmit,
  sending,
  canSubmit,
  workArchived,
  disabled,
}: ComposerProps) {
  const [attachmentTrayOpen, setAttachmentTrayOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = async () => {
    if (!canSubmit || sending) return;
    await onSubmit();
    textareaRef.current?.focus();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submit();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Match common chat behaviour: Enter sends, while Shift+Enter preserves a
    // deliberate line break. IME composition must never submit prematurely.
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void submit();
  };

  const visibleAttachments = attachments.slice(0, 3);
  const remainingCount = Math.max(0, attachments.length - 3);
  const selectableArtifacts = availableArtifacts.filter(artifact => !attachments.some(selected => selected.id === artifact.id));

  return (
    <form className={`gyo-composer ${workArchived ? 'is-archived' : ''}`} onSubmit={handleSubmit} aria-label="Soạn tin nhắn cho GYO">
      <textarea
        ref={textareaRef}
        className="gyo-composer-input"
        value={prompt}
        onChange={e => onPromptChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={workArchived ? 'Công việc đã lưu trữ — chỉ đọc' : 'Giao yêu cầu cho GYO...'}
        rows={3}
        disabled={disabled || sending || workArchived}
        aria-label={workArchived ? 'Đã lưu trữ — không thể gửi' : 'Gửi yêu cầu cho GYO'}
        aria-disabled={disabled || sending || workArchived}
      />
      <div className="gyo-composer-controls">
        <div className="gyo-composer-left">
          <ModelCapabilitySelector
            modelChoice={modelChoice}
            onModelChoice={onModelChoice}
            availableModels={availableModels}
            providers={providers}
          />
          <button
            type="button"
            className="gyo-attachment-toggle btn-secondary compact-button"
            onClick={() => setAttachmentTrayOpen(!attachmentTrayOpen)}
            aria-expanded={attachmentTrayOpen}
            aria-label={attachmentTrayOpen ? 'Đóng thùng tệp ngữ cảnh GYO' : 'Mở thùng tệp ngữ cảnh GYO'}
            disabled={disabled || workArchived}
          >
            <Hash size={14} /> Ngữ cảnh tệp
          </button>
        </div>
        <button
          type="submit"
          className="btn-primary gyo-submit"
          disabled={!canSubmit || sending || disabled || workArchived}
          aria-busy={sending}
        >
          <Send size={14} /> {sending ? 'Đang gửi…' : `Gửi ${ASSISTANT_NAME}`}
        </button>
      </div>

      {attachmentTrayOpen && !workArchived && (
        <div className="gyo-attachment-tray" aria-label="Tệp ngữ cảnh GYO">
          <div className="gyo-attachment-tray-header">
            <span>Tệp GYO sẽ dùng làm ngữ cảnh ({attachments.length})</span>
            <button
              type="button"
              className="icon-button"
              aria-label="Đóng danh sách tệp ngữ cảnh GYO"
              onClick={() => setAttachmentTrayOpen(false)}
            >
              <X size={14} />
            </button>
          </div>
          {visibleAttachments.map(artifact => (
            <div key={artifact.id} className="gyo-attachment-item">
              <FileText size={13} aria-hidden="true" />
              <span className="gyo-attachment-name">{artifact.relative_path}</span>
              <span className="gyo-attachment-size">{(artifact.size_bytes / 1024).toFixed(1)} KB</span>
              <button
                type="button"
                className="icon-button"
                aria-label={`Xóa ${artifact.relative_path}`}
                onClick={() => onRemoveAttachment(artifact.id)}
              >
                <X size={12} />
              </button>
            </div>
          ))}
          {remainingCount > 0 && (
            <div className="gyo-attachment-overflow">+{remainingCount} tệp khác</div>
          )}
          {attachments.length === 0 && (
            <p className="gyo-attachment-empty">Chưa có tệp văn bản đã kiểm tra cấu trúc. GYO hiện dùng TXT, Markdown hoặc CSV làm ngữ cảnh.</p>
          )}
          {selectableArtifacts.length > 0 && (
            <div className="gyo-attachment-available" aria-label="Tệp có thể dùng làm ngữ cảnh">
              <span>Tệp có thể dùng làm ngữ cảnh</span>
              {selectableArtifacts.slice(0, 8).map(artifact => (
                <button
                  key={artifact.id}
                  type="button"
                  className="btn-secondary compact-button"
                  onClick={() => onAddAttachment(artifact.id)}
                >
                  Dùng {artifact.relative_path}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </form>
  );
}

function FileText({ size }: { size: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="16" y2="17" /></svg>;
}

function ErrorAction({ error, onRetry, inline }: { error: NonNullable<GYOAssistantProps['error']>; onRetry?: () => void; inline?: boolean }) {
  const errorIcons: Record<string, React.ReactNode> = {
    conflict: <AlertCircle size={16} />,
    expired: <Clock size={16} />,
    missing_artifact: <FileText size={16} />,
    permission: <Lock size={16} />,
    disconnected: <WifiOff size={16} />,
    model_unavailable: <Settings size={16} />,
    budget: <AlertCircle size={16} />,
    interrupted: <Pause size={16} />,
  };

  const icon = errorIcons[error.category] || <AlertCircle size={16} />;

  return (
    <div className={`gyo-error gyo-error--${error.category} ${inline ? 'gyo-error--inline' : ''}`} role="alert" aria-label={`Lỗi: ${error.category}`}>
      {icon}
      <div className="gyo-error-body">
        <strong>{errorCategoryToLabel(error.category)}</strong>
        <p>{error.message}</p>
        {error.actionable && onRetry && (
          <button className="btn-secondary compact-button" onClick={onRetry}>
            <RefreshCw size={14} /> Thử lại
          </button>
        )}
      </div>
    </div>
  );
}

function errorCategoryToLabel(category: string): string {
  const labels: Record<string, string> = {
    conflict: 'Xung đột',
    expired: 'Đã hết hạn',
    missing_artifact: 'Thiếu tệp',
    permission: 'Không có quyền',
    disconnected: 'Mất kết nối',
    model_unavailable: 'Model không khả dụng',
    budget: 'Vượt ngân sách',
    interrupted: 'Đã gián đoạn',
  };
  return labels[category] || 'Lỗi';
}

interface WelcomeScreenProps {
  workArchived: boolean;
  onOpenHistory: () => void;
}

function WelcomeScreen({ workArchived, onOpenHistory }: WelcomeScreenProps) {
  return (
    <div className="gyo-welcome" aria-label={`Chào mừng đến với ${ASSISTANT_NAME}`}>
      <div className="gyo-welcome-icon">
        <LogIn size={32} />
      </div>
      <h2>{ASSISTANT_NAME} đã sẵn sàng</h2>
      <p>Gửi yêu cầu để bắt đầu trao đổi. {ASSISTANT_NAME} sẽ hỗ trợ bạn trong Công việc này.</p>
      <div className="gyo-welcome-tips">
        <h3>Gợi ý câu lệnh:</h3>
        <ul>
          <li>“Đánh giá tài liệu hiện tại và đưa ra ý kiến.”</li>
          <li>“Tóm tắt các bước tiếp theo trong kế hoạch.”</li>
          <li>“Tạo báo cáo từ những gì chúng ta đã thảo luận.”</li>
        </ul>
      </div>
      <button type="button" className="btn-secondary compact-button" onClick={onOpenHistory}>
        <Clock size={14} /> Xem lịch sử
      </button>
      {workArchived && (
        <div className="gyo-welcome-archived" role="status">
          <Lock size={14} /> Công việc đã lưu trữ — {ASSISTANT_NAME} ở chế độ chỉ đọc.
        </div>
      )}
    </div>
  );
}

interface ConfirmationFooterProps {
  confirmations: Array<{
    id: string;
    type: string;
    title: string;
    description?: string;
    package: ActionPackage;
    preflight: ActionPackagePreflight | null;
    expectedRevision?: number | null;
    expectedPayloadHash?: string | null;
  }>;
  onApprove: (id: string, expectedRevision?: number | null, expectedPayloadHash?: string | null) => void;
  onDeny: (id: string, expectedRevision: number, expectedPayloadHash: string) => void;
  busy: string | null;
  disabled: boolean;
}

function ConfirmationFooter({ confirmations, onApprove, onDeny, busy, disabled }: ConfirmationFooterProps) {
  if (!confirmations.length) return null;

  return (
    <div className="gyo-confirmation-footer" role="status" aria-label="Xác nhận cho GYO thực thi">
      {confirmations.map(c => {
        const preflightBinding = c.preflight ? getActionPackagePreflightDecisionBinding(c.preflight) : null;
        const canApprove = c.preflight?.package_id === c.id
          && preflightBinding?.expectedRevision === c.expectedRevision
          && preflightBinding?.expectedPayloadHash === c.expectedPayloadHash
          && c.expectedRevision != null && typeof c.expectedRevision === 'number' && !!c.expectedPayloadHash;
        const isBusy = busy === c.id;
        return (
          <div key={c.id} className="gyo-confirmation-item">
            <div className="gyo-confirmation-summary">
              <CheckCircle size={15} aria-hidden="true" />
              <strong>{c.title}</strong>
              {c.description && <p>{c.description}</p>}
              {!canApprove && (
                <p className="gyo-confirmation-warning" aria-label="Dữ liệu xác nhận chưa đầy đủ">
                  Chưa thể xác nhận an toàn; kế hoạch đã thay đổi hoặc cần đánh giá lại.
                </p>
              )}
            </div>
            <div className="gyo-confirmation-actions">
              <button
                type="button"
                className="btn-primary compact-button"
                onClick={() => onApprove(c.id, c.expectedRevision ?? null, c.expectedPayloadHash ?? null)}
                disabled={isBusy || disabled || !canApprove}
                aria-label="Xác nhận cho GYO thực thi"
                title={canApprove ? undefined : 'Thiếu binding xác nhận canonical — không thể xác nhận an toàn'}
              >
                {isBusy ? 'Đang xử lý…' : 'Xác nhận cho GYO thực thi'}
              </button>
              <button
                type="button"
                className="btn-secondary compact-button"
                onClick={() => {
                  if (canApprove) onDeny(c.id, c.expectedRevision!, c.expectedPayloadHash!);
                }}
                disabled={isBusy || disabled || !canApprove}
              >
                Không thực thi
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export const GYOAssistant: React.FC<GYOAssistantProps> = ({
  workId,
  conversationId,
  threadId: controlledThreadId,
  mode,
  visible,
  threads,
  turns,
  streamedText,
  manifest,
  artifacts,
  modelConfig,
  workArchived,
  restoredDraft = '',
  restoredModelChoice = 'auto',
  restoredAttachmentIds = EMPTY_ATTACHMENT_IDS,
  error: errorProp,
  loading,
  discardDraftSignal,
  onNavigateToFocus,
  onSubmitPrompt,
  onCancelTurn,
  onRetryTurn,
  onCreateProposal,
  onApproveConfirmation,
  onDenyConfirmation,
  onDraftChanged,
}) => {
  const [draft, setDraft] = useState('');
  const [modelChoice, setModelChoice] = useState('auto');
  const [attachmentIds, setAttachmentIds] = useState<string[]>([]);
  const [sendingScope, setSendingScope] = useState<string | null>(null);
  const [localError, setLocalError] = useState<GYOAssistantProps['error']>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const [canonicalPackages, setCanonicalPackages] = useState<Record<string, { package: ActionPackage | null; preflight: ActionPackagePreflight | null }>>({});
  const [confirmationBusy, setConfirmationBusy] = useState<string | null>(null);
  const confirmationInFlightRef = useRef<Set<string>>(new Set());
  const composerScopeKey = `${workId ?? ''}:${conversationId ?? ''}`;
  const composerScopeRef = useRef(composerScopeKey);

  useEffect(() => {
    composerScopeRef.current = composerScopeKey;
  }, [composerScopeKey]);

  const sending = sendingScope === composerScopeKey;

  // Restore only the parent-provided, server-scoped session draft.
  useEffect(() => {
    if (conversationId) {
      setDraft(restoredDraft);
      setModelChoice(restoredModelChoice || 'auto');
      setAttachmentIds(restoredAttachmentIds);
    }
  }, [conversationId, restoredAttachmentIds, restoredDraft, restoredModelChoice]);

  // Discard only a matching stale scope. A signal for another conversation is
  // intentionally ignored so the current composer stays intact.
  const handledDiscardTokenRef = useRef<number | null>(null);
  useEffect(() => {
    if (!discardDraftSignal) return;
    if (discardDraftSignal.workId !== workId || discardDraftSignal.conversationId !== conversationId) return;
    if (handledDiscardTokenRef.current === discardDraftSignal.token) return;

    setDraft('');
    setModelChoice('auto');
    setAttachmentIds([]);
    handledDiscardTokenRef.current = discardDraftSignal.token;
  }, [conversationId, discardDraftSignal, workId]);

  // Derive state
  const activeThread = controlledThreadId
    ? threads.find(t => t.id === controlledThreadId)
    : null;

  const hasTurns = turns.length > 0;
  const hasRunningTurn = turns.some(t => t.status === 'running');
  const hasFailedTurn = turns.some(t => t.status === 'failed');
  const hasActionProposal = turns.some(t =>
    t.parts.some(p => p.part_type === 'action_proposal' || p.part_type === 'approval')
  );

  // Determine surface activity status
  const activityStatus: string = useMemo(() => {
    if (errorProp || localError) return 'error';
    if (loading) return 'loading';
    if (hasRunningTurn) return 'streaming';
    if (showHistory) return 'history';
    if (hasActionProposal) return 'confirmation';
    if (!workId) return 'welcome';
    if (!conversationId) return 'welcome';
    if (!activeThread) return 'compose';
    if (!hasTurns) return 'compose';
    if (hasFailedTurn) return 'failed';
    return 'conversation';
  }, [errorProp, localError, loading, hasRunningTurn, showHistory, hasActionProposal, workId, conversationId, activeThread, hasTurns, hasFailedTurn]);

  // Handle draft persistence
  const handleDraftChange = useCallback((value: string) => {
    setDraft(value);
    onDraftChanged(value, modelChoice, attachmentIds);
  }, [attachmentIds, modelChoice, onDraftChanged]);

  const handleModelChange = useCallback((value: string) => {
    setModelChoice(value);
    onDraftChanged(draft, value, attachmentIds);
  }, [attachmentIds, draft, onDraftChanged]);

  // Extract confirmations from turns
  const proposalPackageIds = useMemo(() => {
    const ids = new Set<string>();
    for (const turn of turns) for (const part of turn.parts) {
      const value = part.content as Record<string, unknown> | undefined;
      if (part.part_type === 'action_proposal' && typeof value?.package_id === 'string') ids.add(value.package_id);
    }
    return [...ids];
  }, [turns]);

  const refreshCanonicalPackage = useCallback(async (id: string) => {
    let item: ActionPackage | null = null;
    let preflight: ActionPackagePreflight | null = null;
    try { item = await getActionPackage(id); } catch { item = null; }
    try { preflight = await getActionPackagePreflight(id); } catch { preflight = null; }
    setCanonicalPackages(current => ({ ...current, [id]: { package: item, preflight } }));
  }, []);

  // The message only carries a package reference. The confirmation card is
  // always hydrated from the canonical Action Package before exposing a CTA.
  useEffect(() => {
    let cancelled = false;
    if (!proposalPackageIds.length) {
      setCanonicalPackages({});
      return () => { cancelled = true; };
    }
    void Promise.all(proposalPackageIds.map(async id => {
      try {
        const [item, preflight] = await Promise.all([getActionPackage(id), getActionPackagePreflight(id)]);
        return [id, { package: item, preflight }] as const;
      } catch { return [id, { package: null, preflight: null }] as const; }
    })).then(entries => {
      if (!cancelled) setCanonicalPackages(Object.fromEntries(entries));
    });
    return () => { cancelled = true; };
  }, [proposalPackageIds]);

  const confirmations = useMemo(() => {
    const confs: ConfirmationFooterProps['confirmations'] = [];
    for (const turn of turns) {
      for (const part of turn.parts) {
        if (part.part_type === 'action_proposal' && part.content) {
          const content = part.content as Record<string, unknown>;
          const packageId = typeof content.package_id === 'string' ? content.package_id : null;
          const canonical = packageId ? canonicalPackages[packageId] : null;
          const canonicalPackage = canonical?.package ?? null;
          confs.push({
            id: packageId ?? part.id,
            type: 'action_proposal',
            title: typeof content.title === 'string' ? content.title : 'Đề xuất thay đổi',
            description: typeof content.description === 'string' ? content.description : undefined,
            package: canonicalPackage ?? ({ id: packageId ?? part.id } as ActionPackage),
            preflight: canonical?.preflight ?? null,
            expectedRevision: canonicalPackage?.revision ?? null,
            expectedPayloadHash: canonicalPackage?.payload_hash ?? null,
          });
        }
      }
    }
    return confs;
  }, [canonicalPackages, turns]);

  const handleRemoveAttachment = (id: string) => {
    const next = attachmentIds.filter(attachmentId => attachmentId !== id);
    setAttachmentIds(next);
    onDraftChanged(draft, modelChoice, next);
  };

  const handleAddAttachment = (id: string) => {
    if (attachmentIds.includes(id)) return;
    const next = [...attachmentIds, id];
    setAttachmentIds(next);
    onDraftChanged(draft, modelChoice, next);
  };

  const handleSubmit = async () => {
    const submittedScope = composerScopeRef.current;
    setLocalError(null);
    setSendingScope(submittedScope);
    try {
      await onSubmitPrompt(draft, modelChoice, attachmentIds);
      // A stale request must not clear the draft that is now shown for another scope.
      if (composerScopeRef.current === submittedScope) {
        setDraft('');
        setAttachmentIds([]);
        onDraftChanged('', modelChoice, []);
      }
    } catch (e: unknown) {
      const err = e as Error;
      if (composerScopeRef.current !== submittedScope) return;
      if (e instanceof ApiError && e.status === 409) {
        // DON'T clear draft on conflict — preserve user input for retry
        setLocalError({ category: 'conflict', message: 'Xung đột trạng thái — bản nháp vẫn được giữ.', actionable: true });
      } else if (e instanceof ApiError && e.status === 401) {
        setLocalError({ category: 'permission', message: 'Bạn cần đăng nhập lại.', actionable: true });
      } else if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
        setLocalError({ category: 'expired', message: 'Phiên đã hết hạn. Hãy làm mới trang.', actionable: true });
      } else if (err?.message?.includes('network') || err?.message?.includes('fetch')) {
        setLocalError({ category: 'disconnected', message: err.message, actionable: true });
      } else {
        setLocalError({ category: 'generic', message: err?.message || 'Không gửi được yêu cầu.', actionable: true });
      }
      // Keep draft on error so user can retry
    } finally {
      setSendingScope(current => current === submittedScope ? null : current);
    }
  };

  const handleConfirmationDecision = async (
    id: string,
    expectedRevision: number | null | undefined,
    expectedPayloadHash: string | null | undefined,
    decision: 'approve' | 'deny',
  ) => {
    if (confirmationInFlightRef.current.has(id)) return;
    if (expectedRevision == null || typeof expectedRevision !== 'number' || !expectedPayloadHash) {
      setLocalError({
        category: 'permission',
        message: 'Chưa thể xác nhận an toàn; dữ liệu xác nhận chưa đầy đủ.',
        actionable: false,
      });
      return;
    }

    confirmationInFlightRef.current.add(id);
    setConfirmationBusy(id);
    setLocalError(null);
    let decisionStarted = false;
    try {
      // Re-preflight on the exact click. A canonical binding that differs from
      // the package the user reviewed is stale; never silently approve/deny the
      // newer package under the old confirmation UI.
      const preflight = await getActionPackagePreflight(id);
      const currentBinding = getActionPackagePreflightDecisionBinding(preflight);
      if (
        preflight.package_id !== id
        || !currentBinding
        || currentBinding.expectedRevision !== expectedRevision
        || currentBinding.expectedPayloadHash !== expectedPayloadHash
      ) {
        throw new ApiError(409, 'Kế hoạch đã thay đổi hoặc không còn hợp lệ.');
      }

      decisionStarted = true;
      if (decision === 'approve') {
        await onApproveConfirmation(id, currentBinding.expectedRevision, currentBinding.expectedPayloadHash);
      } else {
        await onDenyConfirmation(id, currentBinding.expectedRevision, currentBinding.expectedPayloadHash);
      }
      await refreshCanonicalPackage(id);
    } catch (e: unknown) {
      // Refresh authoritative package/preflight state even when the click-time
      // preflight itself fails; no decision callback is reached in that case.
      await refreshCanonicalPackage(id);
      const err = e as Error;
      if (!decisionStarted && e instanceof ApiError && e.status === 409) {
        setLocalError({ category: 'conflict', message: 'Mục đã thay đổi, hết hạn hoặc được xử lý ở nơi khác. Trạng thái đã được làm mới.', actionable: true });
      } else if (!decisionStarted) {
        setLocalError({ category: 'generic', message: 'Chưa thể xác minh gói thay đổi. Không có quyết định nào được gửi.', actionable: true });
      } else if (decision === 'deny') {
        setLocalError({ category: 'generic', message: 'Không thể từ chối.', actionable: true });
      } else {
        setLocalError({ category: 'generic', message: err?.message || 'Không thể xác nhận.', actionable: true });
      }
    } finally {
      confirmationInFlightRef.current.delete(id);
      setConfirmationBusy(current => current === id ? null : current);
    }
  };

  const handleApprove = async (id: string, expectedRevision?: number | null, expectedPayloadHash?: string | null) => {
    await handleConfirmationDecision(id, expectedRevision, expectedPayloadHash, 'approve');
  };

  const handleDeny = async (id: string, expectedRevision: number, expectedPayloadHash: string) => {
    await handleConfirmationDecision(id, expectedRevision, expectedPayloadHash, 'deny');
  };

  const canSubmit = draft.trim().length > 0 && !sending && !workArchived;

  if (!visible) return null;

  const renderSurface = () => {
    const err = errorProp || localError;

    // Welcome state — no work/conversation selected
    if (!workId || !conversationId) {
      return <WelcomeScreen workArchived={workArchived} onOpenHistory={() => setShowHistory(true)} />;
    }

    // Loading
    if (loading && !hasTurns) {
      return (
        <div className="gyo-loading" role="status" aria-label="Đang tải">
          <Loader2 size={24} className="gyo-spin" aria-hidden="true" />
          <span>Đang kết nối với {ASSISTANT_NAME}…</span>
        </div>
      );
    }

    // Error state — shown inline, does not hide persisted turns
    const errorBanner = err ? (
      <ErrorAction error={err} onRetry={() => { setLocalError(null); }} inline />
    ) : null;

    // History view
    if (showHistory) {
      return (
        <HistoryPanel workId={workId} workArchived={workArchived} />
      );
    }

    // If no thread resolved yet, show compose state (error may still appear inline)
    // The Composer is ALWAYS rendered at the bottom so the user can always type.
    if (!activeThread) {
      return (
        <div className="gyo-compose-surface">
          {errorBanner}
          <div className="gyo-main">
            <WelcomeScreen workArchived={workArchived} onOpenHistory={() => setShowHistory(true)} />
          </div>
          <ConfirmationFooter
            confirmations={confirmations}
            onApprove={handleApprove}
            onDeny={handleDeny}
            busy={confirmationBusy}
            disabled={workArchived}
          />
          {/* Composer always at bottom */}
          <Composer
            prompt={draft}
            onPromptChange={handleDraftChange}
            modelChoice={modelChoice}
            onModelChoice={handleModelChange}
            availableModels={modelConfig?.models ?? []}
            providers={modelConfig?.providers ?? []}
            attachments={attachmentIds.map(id => artifacts.find(a => a.id === id)).filter(Boolean) as Artifact[]}
            availableArtifacts={artifacts}
            onAddAttachment={handleAddAttachment}
            onRemoveAttachment={handleRemoveAttachment}
            onSubmit={handleSubmit}
            sending={sending}
            canSubmit={canSubmit}
            workArchived={workArchived}
            disabled={false}
          />
        </div>
      );
    }

    // Conversation / streaming state
    return (
      <div className="gyo-conversation-surface">
        {errorBanner}
        <div className="gyo-turns-list" role="log" aria-label={`Trao đổi ${activeThread.title}`}>
          {turns.map(turn => (
            <AssistantTurnCard
              key={turn.id}
              turn={turn}
              streamedText={streamedText[turn.id]}
              sending={sending}
              onCreateProposal={(part: AssistantPart) => void onCreateProposal(part)}
              onCancel={(turnId: string) => void onCancelTurn(turnId)}
              onRetrySame={(turnId: string) => onRetryTurn(turnId, 'same_model')}
              onRetryAuto={(turnId: string) => onRetryTurn(turnId, 'auto')}
            />
          ))}
          {hasRunningTurn && (
            <div className="gyo-streaming-indicator" aria-live="polite" aria-atomic="true">
              <span className="gyo-streaming-dots">
                <span className="gyo-dot" />
                <span className="gyo-dot" />
                <span className="gyo-dot" />
              </span>
              <span>{ASSISTANT_NAME} đang trả lời…</span>
            </div>
          )}
        </div>

        <ConfirmationFooter
          confirmations={confirmations}
          onApprove={handleApprove}
          onDeny={handleDeny}
          busy={confirmationBusy}
          disabled={workArchived}
        />

        {/* Composer always at bottom */}
        <Composer
          prompt={draft}
          onPromptChange={handleDraftChange}
          modelChoice={modelChoice}
          onModelChoice={handleModelChange}
          availableModels={modelConfig?.models ?? []}
          providers={modelConfig?.providers ?? []}
          attachments={attachmentIds.map(id => artifacts.find(a => a.id === id)).filter(Boolean) as Artifact[]}
          availableArtifacts={artifacts}
          onAddAttachment={handleAddAttachment}
          onRemoveAttachment={handleRemoveAttachment}
          onSubmit={handleSubmit}
          sending={sending}
          canSubmit={canSubmit}
          workArchived={workArchived}
          disabled={!activeThread}
        />
      </div>
    );
  };

  return (
    <div
      className={`gyo-assistant-surface gyo-surface--${mode} ${workArchived ? 'is-archived' : ''}`}
      data-gyo-mode={mode}
      data-gyo-work-id={workId || 'none'}
      data-gyo-conversation-id={conversationId || 'none'}
      data-gyo-thread-id={controlledThreadId || 'none'}
      data-gyo-status={activityStatus}
      aria-label="Trợ lý GYO"
      role="region"
    >
      <header className={`gyo-header gyo-header--${mode}`}>
        <div className="gyo-header-title">
          <span className="gyo-header-icon" aria-hidden="true">
            <LogIn size={mode === 'focus' ? 20 : 16} />
          </span>
          <strong>{ASSISTANT_NAME}</strong>
          <span className="gyo-header-mode-label">
            {mode === 'drawer' ? 'Trong thanh bên' : 'Chế độ tập trung'}
          </span>
        </div>
        {mode === 'drawer' && (
          <button
            type="button"
            className="gyo-header-focus-btn btn-secondary compact-button"
            onClick={() => onNavigateToFocus(workId, conversationId, controlledThreadId)}
            title="Mở trong chế độ tập trung"
            aria-label="Mở GYO trong chế độ tập trung"
          >
            <ExternalLink size={13} />
          </button>
        )}
        <button
          type="button"
          className="icon-button"
          onClick={() => setShowContext(!showContext)}
          aria-label="Ngữ cảnh làm việc"
          aria-expanded={showContext}
        >
          <List size={14} />
        </button>
      </header>

      <div className={`gyo-surface-body ${showContext ? 'has-context' : ''}`}>
        <main className="gyo-main" aria-live="polite" aria-atomic="false">
          {renderSurface()}
        </main>
        {showContext && (
          <aside className="gyo-context-aside" aria-label="Ngữ cảnh">
            <ContextPanel manifest={manifest} artifacts={artifacts} loading={loading} />
          </aside>
        )}
      </div>
    </div>
  );
};
