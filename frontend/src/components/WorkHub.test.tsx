import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ApiError } from '../api/client';

const assistant = vi.hoisted(() => ({
  assistantThreadStreamUrl: vi.fn(() => '/stream'), cancelAssistantTurn: vi.fn(),
  createAssistantRun: vi.fn(), getAssistantTurns: vi.fn(), listAssistantThreads: vi.fn(),
  resolveWorkConversationAssistantThread: vi.fn(), retryAssistantTurn: vi.fn(),
}));
const works = vi.hoisted(() => ({ getConversationMessages: vi.fn(), readWorkDraft: vi.fn(() => ''), writeWorkDraft: vi.fn() }));
vi.mock('../api/assistant', () => assistant);
vi.mock('../api/works', async () => ({ ...(await vi.importActual<object>('../api/works')), ...works }));
vi.mock('./FileExplorer', () => ({ FileExplorer: () => null }));
vi.mock('./EditorPanel', () => ({ EditorPanel: () => null }));
vi.mock('./ReportsPanel', () => ({ ReportsPanel: () => null }));
vi.mock('./KnowledgePanel', () => ({ KnowledgePanel: () => null }));
vi.mock('./ActionPackagesPanel', () => ({ ActionPackagesPanel: () => null }));
vi.mock('./HermesAssistantPanel', () => ({ TurnPartRenderer: ({ part }: { part: { content: Record<string, unknown> } }) => <p>{String(part.content.text ?? '')}</p> }));
vi.mock('./PhaseCard', () => ({ PhaseCard: () => null }));

import { ConversationWorkspace } from './WorkHub';

const conversation = { id: 'conversation-a', session_id: 'work-a', title: 'Phiên A', status: 'active' as const, created_at: 1, updated_at: 1, message_count: 0 };

describe('ConversationWorkspace canonical assistant scope', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    works.getConversationMessages.mockResolvedValue({ messages: [], has_more: false });
    assistant.listAssistantThreads.mockResolvedValue([]);
    assistant.getAssistantTurns.mockResolvedValue([]);
    assistant.resolveWorkConversationAssistantThread.mockResolvedValue({ id: 'thread-a', work_id: 'work-a', conversation_id: 'conversation-a', title: 'GYO', status: 'active', created_at: 1, updated_at: 1 });
    assistant.createAssistantRun.mockResolvedValue([]);
  });

  it('does not resolve while opening a Conversation, then resolves and sends its exact scope on submit', async () => {
    render(<ConversationWorkspace workId="work-a" conversation={conversation} onRename={vi.fn()} onArchive={vi.fn()} />);
    await waitFor(() => expect(works.getConversationMessages).toHaveBeenCalledWith('work-a', 'conversation-a'));
    expect(assistant.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Tóm tắt' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gửi GYO' }));
    await waitFor(() => expect(assistant.resolveWorkConversationAssistantThread).toHaveBeenCalledWith('work-a', 'conversation-a'));
    expect(assistant.createAssistantRun).toHaveBeenCalledWith('thread-a', 'Tóm tắt', 'work-a', 'conversation-a');
  });

  it('submits with Enter, but preserves Shift+Enter for a line break', async () => {
    render(<ConversationWorkspace workId="work-a" conversation={conversation} onRename={vi.fn()} onArchive={vi.fn()} />);
    const composer = await screen.findByRole('textbox');
    fireEvent.change(composer, { target: { value: 'Tóm tắt bằng Enter' } });
    fireEvent.keyDown(composer, { key: 'Enter', shiftKey: true });
    expect(assistant.createAssistantRun).not.toHaveBeenCalled();
    fireEvent.keyDown(composer, { key: 'Enter' });
    await waitFor(() => expect(assistant.createAssistantRun).toHaveBeenCalledWith(
      'thread-a', 'Tóm tắt bằng Enter', 'work-a', 'conversation-a',
    ));
  });

  it('loads persisted GYO turns for the selected scope without creating a thread', async () => {
    assistant.listAssistantThreads.mockResolvedValue([{ id: 'thread-a', work_id: 'work-a', conversation_id: 'conversation-a', title: 'GYO', status: 'active', created_at: 1, updated_at: 1 }]);
    assistant.getAssistantTurns.mockResolvedValue([{ id: 'assistant-turn', thread_id: 'thread-a', work_id: 'work-a', conversation_id: 'conversation-a', role: 'assistant', status: 'completed', created_at: 1, parts: [{ id: 'text-part', type: 'text', content: { text: 'Kết quả đã lưu' }, created_at: 1 }] }]);
    render(<ConversationWorkspace workId="work-a" conversation={conversation} onRename={vi.fn()} onArchive={vi.fn()} />);
    expect(await screen.findByText('Kết quả đã lưu')).toBeTruthy();
    expect(assistant.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
  });

  it('does not subscribe after a run already returns completed turns', async () => {
    assistant.createAssistantRun.mockResolvedValue([
      { id: 'user-turn', thread_id: 'thread-a', work_id: 'work-a', conversation_id: 'conversation-a', role: 'user', status: 'completed', created_at: 1, parts: [] },
      { id: 'assistant-turn', thread_id: 'thread-a', work_id: 'work-a', conversation_id: 'conversation-a', role: 'assistant', status: 'completed', created_at: 1, parts: [{ id: 'text-part', type: 'text', content: { text: 'Hoàn tất nhanh' }, created_at: 1 }] },
    ]);
    render(<ConversationWorkspace workId="work-a" conversation={conversation} onRename={vi.fn()} onArchive={vi.fn()} />);
    await waitFor(() => expect(works.getConversationMessages).toHaveBeenCalled());
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Tóm tắt' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gửi GYO' }));
    expect(await screen.findByText('Hoàn tất nhanh')).toBeTruthy();
    expect(assistant.assistantThreadStreamUrl).not.toHaveBeenCalled();
  });

  it('keeps the draft and reports a scope/run conflict without retrying after run 409', async () => {
    assistant.listAssistantThreads.mockResolvedValue([{ id: 'thread-a', work_id: 'work-a', conversation_id: 'conversation-a', title: 'GYO', status: 'active', created_at: 1, updated_at: 1 }]);
    assistant.createAssistantRun.mockRejectedValue(new ApiError(409, 'conversation is archived'));
    render(<ConversationWorkspace workId="work-a" conversation={conversation} onRename={vi.fn()} onArchive={vi.fn()} />);
    await waitFor(() => expect(assistant.getAssistantTurns).toHaveBeenCalledWith('thread-a'));
    const composer = screen.getByRole('textbox');
    fireEvent.change(composer, { target: { value: 'Tóm tắt' } });
    fireEvent.click(screen.getByRole('button', { name: 'Gửi GYO' }));

    expect(await screen.findByText(/phạm vi hoặc trạng thái chạy/i)).toBeTruthy();
    expect((composer as HTMLTextAreaElement).value).toBe('Tóm tắt');
    expect(assistant.createAssistantRun).toHaveBeenCalledTimes(1);
    expect(assistant.resolveWorkConversationAssistantThread).not.toHaveBeenCalled();
  });
});
