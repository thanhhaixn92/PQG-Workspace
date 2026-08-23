import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { AssistantTurn as AssistantTurnModel } from '../../api/assistant';
import { AssistantTurn } from './AssistantTurn';

const runningTurn = (overrides: Partial<AssistantTurnModel> = {}): AssistantTurnModel => ({
  id: 'turn-1',
  thread_id: 'thread-1',
  work_id: 'work-1',
  conversation_id: 'conversation-1',
  role: 'assistant',
  status: 'running',
  model_id: 'gyo',
  created_at: 1,
  parts: [],
  ...overrides,
});

describe('AssistantTurn durable run state', () => {
  it('shows cancel-requested as pending and prevents duplicate cancel requests', () => {
    const onCancel = vi.fn();
    render(
      <AssistantTurn
        turn={runningTurn({
          run_id: 'turn-1',
          run_status: 'cancel_requested',
          remote_compute_stop_proven: false,
        })}
        streamedText="Late streamed text must not look authoritative"
        onCancel={onCancel}
      />,
    );

    expect(screen.getByText('Đang hủy phản hồi…')).toBeDefined();
    expect(screen.queryByText('Late streamed text must not look authoritative')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Hủy phản hồi' })).toBeNull();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it('keeps the cancel action available for a normal running response', () => {
    const onCancel = vi.fn();
    render(<AssistantTurn turn={runningTurn()} onCancel={onCancel} />);

    expect(screen.getByText(/đang trả lời/i)).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Hủy phản hồi' }));
    expect(onCancel).toHaveBeenCalledWith('turn-1');
  });
});
