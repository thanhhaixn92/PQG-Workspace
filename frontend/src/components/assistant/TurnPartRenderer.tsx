import React from 'react';
import { FileText, ShieldCheck, Sparkles, Wrench, AlertCircle, Bot } from 'lucide-react';
import type { AssistantPart, AssistantTurn } from '../../api/assistant';
import { MarkdownRenderer } from '../MarkdownRenderer';
import { ASSISTANT_NAME } from '../../branding';

const dateText = (timestamp?: number | null) => timestamp
  ? new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' }).format(timestamp * 1000)
  : '';

const partLabel: Record<AssistantPart['part_type'], string> = {
  text: '', source: 'Nguồn', tool_result: 'Kết quả công cụ', artifact: 'Đầu ra mới',
  action_proposal: 'Đề xuất thay đổi', approval: 'Cần bạn quyết định', error: 'Không thể hoàn tất',
};

const textFrom = (content: Record<string, unknown>, keys: string[], fallback = ''): string => {
  for (const key of keys) {
    const value = content[key];
    if (typeof value === 'string' && value.trim()) return value;
  }
  return fallback;
};

export function ActionProposalCard({ part, onOpenReview, onCreateProposal, busy, created }: {
  part: AssistantPart;
  onOpenReview?: () => void;
  onCreateProposal?: (part: AssistantPart) => void;
  busy?: boolean;
  created?: boolean;
}) {
  const content = { ...part.content } as Record<string, unknown>;
  const isApproval = part.part_type === 'approval';
  return (
    <section className={`gyo-part gyo-part-${part.part_type.replace('_', '-')}`} data-part-type={part.part_type}>
      <ShieldCheck size={15} aria-hidden="true" />
      <div className="gyo-part-body">
        <strong>{textFrom(content, ['title'], isApproval ? 'Cần bạn quyết định' : 'Đề xuất thay đổi')}</strong>
        <p>{textFrom(content, ['description', 'summary', 'message'], isApproval ? 'Xem nội dung trước khi quyết định.' : `${ASSISTANT_NAME} đã chuẩn bị thay đổi để bạn xem trước.`)}</p>
        <dl className="gyo-proposal-details">
          <div><dt>Tác động</dt><dd>{textFrom(content, ['impact', 'after'], 'Chỉ áp dụng trong Công việc đã chọn.')}</dd></div>
          <div><dt>Hoàn tác</dt><dd>{textFrom(content, ['undo'], 'Có thể tạo một đề xuất mới để điều chỉnh lại.')}</dd></div>
          {typeof content.risk === 'string' && <div><dt>Mức cần chú ý</dt><dd>{content.risk}</dd></div>}
        </dl>
        {part.part_type === 'action_proposal' && onCreateProposal && (
          <button
            type="button"
            className="btn-primary compact-button"
            onClick={() => onCreateProposal(part)}
            disabled={busy || created}
          >
            {created ? 'Đã tạo gói đề xuất' : busy ? 'Đang tạo…' : 'Tạo gói đề xuất'}
          </button>
        )}
        {(part.part_type === 'action_proposal' && !onCreateProposal || isApproval) && onOpenReview && (
          <button type="button" className="btn-secondary compact-button" onClick={onOpenReview}>
            {isApproval ? 'Mở mục cần duyệt' : 'Xem đề xuất'}
          </button>
        )}
      </div>
    </section>
  );
}

export function TurnPartRenderer({ part, onOpenReview, onCreateProposal, proposalBusy, proposalCreated }: {
  part: AssistantPart;
  onOpenReview?: () => void;
  onCreateProposal?: (part: AssistantPart) => void;
  proposalBusy?: boolean;
  proposalCreated?: boolean;
}) {
  const content = { ...part.content } as Record<string, unknown>;

  if (part.part_type === 'text') {
    return (
      <div className="gyo-part gyo-part-text" data-part-type="text">
        <MarkdownRenderer content={textFrom(content, ['text'], '')} />
      </div>
    );
  }

  if (part.part_type === 'source') {
    return (
      <div className="gyo-part gyo-part-source" data-part-type="source">
        <span className="gyo-source-chip">
          <FileText size={13} />
          {textFrom(content, ['title', 'kind'], 'Nguồn')}
        </span>
        {textFrom(content, ['reason'], '') && <small className="gyo-muted">{textFrom(content, ['reason'], '')}</small>}
      </div>
    );
  }

  if (part.part_type === 'action_proposal' || part.part_type === 'approval') {
    return <ActionProposalCard part={part} onOpenReview={onOpenReview} onCreateProposal={onCreateProposal} busy={proposalBusy} created={proposalCreated} />;
  }

  const Icon: React.ElementType = part.part_type === 'tool_result' ? Wrench :
    part.part_type === 'artifact' ? FileText :
    part.part_type === 'error' ? AlertCircle : Sparkles;

  return (
    <section className={`gyo-part gyo-part-${part.part_type.replace('_', '-')}`} data-part-type={part.part_type}>
      <Icon size={15} aria-hidden="true" />
      <div className="gyo-part-body">
        <strong>{textFrom(content, ['title', 'name', 'tool_name'], content.attachment === true ? 'Tệp đính kèm' : partLabel[part.part_type])}</strong>
        <p>{textFrom(content, ['description', 'summary', 'message', 'text'], 'Không có thông tin bổ sung.')}</p>
      </div>
    </section>
  );
}

export function AssistantTurnCard({ turn, streamedText, sending, onOpenReview, onCreateProposal, proposalBusy, proposalCreated, onCancel, onRetrySame, onRetryAuto }: {
  turn: AssistantTurn;
  streamedText?: string;
  sending?: boolean;
  onOpenReview?: () => void;
  onCreateProposal?: (part: AssistantPart) => void;
  proposalBusy?: string | null;
  proposalCreated?: boolean;
  onCancel?: (turnId: string) => void;
  onRetrySame?: (turnId: string) => void;
  onRetryAuto?: (turnId: string) => void;
}) {
  const isGYO = turn.role === 'assistant';
  const isRunning = turn.status === 'running';
  const isFailed = turn.status === 'failed';

  return (
    <article
      className={`gyo-turn gyo-turn--${turn.role} ${isRunning ? 'is-running' : ''} ${isFailed ? 'is-failed' : ''}`}
      data-turn-id={turn.id}
      data-turn-status={turn.status}
    >
      <div className="gyo-turn-header">
        <span className="gyo-turn-label">
          {isGYO ? ASSISTANT_NAME : 'Bạn'}
          {!isGYO && <Bot size={16} />}
        </span>
        <time className="gyo-turn-time">{dateText(turn.created_at)}</time>
        {isRunning && (
          <span className="gyo-status-badge gyo-status-running" aria-label="Đang trả lời">
            <span className="gyo-status-dot" aria-hidden="true" /> Đang trả lời…
          </span>
        )}
        {isFailed && (
          <span className="gyo-status-badge gyo-status-failed" aria-label="Thất bại">
            <AlertCircle size={12} /> Thất bại
          </span>
        )}
      </div>
      <div className="gyo-turn-content">
        {turn.parts.map(part => (
          <TurnPartRenderer
            key={part.id}
            part={part}
            onOpenReview={onOpenReview && (isGYO ? onOpenReview : undefined)}
            onCreateProposal={onCreateProposal && (isGYO ? onCreateProposal : undefined)}
            proposalBusy={onCreateProposal ? proposalBusy === part.id : undefined}
            proposalCreated={proposalCreated}
          />
        ))}
        {isGYO && isRunning && streamedText && (
          <div className="gyo-streaming-text" aria-live="polite" aria-atomic="false">
            <MarkdownRenderer content={streamedText} />
            <span className="gyo-streaming-cursor" aria-hidden="true">▋</span>
          </div>
        )}
      </div>
      {isGYO && isRunning && onCancel && (
        <button
          className="btn-secondary compact-button"
          type="button"
          onClick={() => onCancel(turn.id)}
          disabled={!!sending}
        >
          <Wrench size={14} /> Hủy phản hồi
        </button>
      )}
      {isGYO && isFailed && (
        <div className="gyo-retry-actions">
          {onRetrySame && (
            <button className="btn-secondary compact-button" type="button" onClick={() => onRetrySame(turn.id)} disabled={!!sending}>
              Thử lại
            </button>
          )}
          {onRetryAuto && (
            <button className="btn-secondary compact-button" type="button" onClick={() => onRetryAuto(turn.id)} disabled={!!sending}>
              Thử lại tự động
            </button>
          )}
        </div>
      )}
    </article>
  );
}
