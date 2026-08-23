import { Square } from 'lucide-react';
import type { AssistantPart, AssistantTurn as AssistantTurnModel } from '../../api/assistant';
import { ASSISTANT_NAME } from '../../branding';
import { TurnPartRenderer } from './TurnPartRenderer';

const dateText = (timestamp?: number | null) => timestamp
  ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(timestamp * 1000)
  : '';

export function AssistantTurn({ turn, streamedText, sending, onOpenReview, onCreateProposal, proposalBusy, proposalCreated, onCancel, onRetrySame, onRetryAuto }: {
  turn: AssistantTurnModel;
  streamedText?: string;
  sending?: boolean;
  onOpenReview?: () => void;
  onCreateProposal?: (part: AssistantPart) => void;
  proposalBusy?: string | null;
  proposalCreated?: Record<string, string>;
  onCancel?: (turnId: string) => void;
  onRetrySame?: (turnId: string) => void;
  onRetryAuto?: (turnId: string) => void;
}) {
  const cancelRequested = turn.role === 'assistant' && turn.status === 'running' && turn.run_status === 'cancel_requested';

  return <article className={`assistant-turn ${turn.role}`}>
    <div className="assistant-turn-label"><span>{turn.role === 'user' ? 'Bạn' : turn.model_id === 'local-summary' ? 'Tóm tắt local' : ASSISTANT_NAME}</span><time>{dateText(turn.created_at)}</time></div>
    {turn.parts.map(part => <TurnPartRenderer key={part.id} part={part} onOpenReview={onOpenReview} onCreateProposal={onCreateProposal} proposalBusy={proposalBusy === part.id} proposalCreated={Boolean(proposalCreated?.[part.id])} />)}
    {turn.role === 'assistant' && turn.status === 'running' && <div className="assistant-live-response" aria-live="polite">
      <p>{cancelRequested ? 'Đang hủy phản hồi…' : streamedText || `${ASSISTANT_NAME} đang trả lời…`}</p>
      {!cancelRequested && onCancel && <button className="btn-secondary compact-button" type="button" onClick={() => onCancel(turn.id)} disabled={sending}><Square size={14} /> Hủy phản hồi</button>}
    </div>}
    {turn.role === 'assistant' && turn.status === 'failed' && <div className="assistant-retry-actions">
      {onRetrySame && <button className="btn-secondary compact-button" type="button" onClick={() => onRetrySame(turn.id)} disabled={sending}>Thử lại</button>}
      {onRetryAuto && <button className="btn-secondary compact-button" type="button" onClick={() => onRetryAuto(turn.id)} disabled={sending}>Thử lại tự động</button>}
    </div>}
  </article>;
}
