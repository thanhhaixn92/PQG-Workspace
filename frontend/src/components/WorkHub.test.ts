import { describe, expect, it } from 'vitest';
import { readWorkDraft, workDraftKey, writeWorkDraft } from '../api/works';
import { filterAvailableSkills, OPEN_WORK_CONVERSATIONS_EVENT } from './workHubUtils';

describe('filterAvailableSkills', () => {
  it('only exposes approved and enabled skills as available', () => {
    const available = filterAvailableSkills([
      { id: 'approved', name: 'Approved', description: null, content: '', enabled: true, status: 'approved', updated_at: 1 },
      { id: 'draft', name: 'Draft', description: null, content: '', enabled: true, status: 'draft', updated_at: 1 },
      { id: 'disabled', name: 'Disabled', description: null, content: '', enabled: false, status: 'approved', updated_at: 1 },
    ]);
    expect(available.map(skill => skill.id)).toEqual(['approved']);
  });

  it('uses a stable event name to open the current Work conversations', () => {
    expect(OPEN_WORK_CONVERSATIONS_EVENT).toBe('hermes:open-work-conversations');
  });

  it('keeps versioned drafts isolated by Work and conversation', () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
      removeItem: (key: string) => { values.delete(key); },
    };
    writeWorkDraft(storage, 'work-a', 'conversation-a', 'Bản nháp A');
    writeWorkDraft(storage, 'work-a', 'conversation-b', 'Bản nháp B');
    expect(readWorkDraft(storage, 'work-a', 'conversation-a')).toBe('Bản nháp A');
    expect(readWorkDraft(storage, 'work-a', 'conversation-b')).toBe('Bản nháp B');
    expect(readWorkDraft(storage, 'work-b', 'conversation-a')).toBe('');
    expect(workDraftKey('work-a', 'conversation-a')).toContain(':v1:work-a:conversation-a');
    writeWorkDraft(storage, 'work-a', 'conversation-a', '');
    expect(readWorkDraft(storage, 'work-a', 'conversation-a')).toBe('');
  });

  it('ignores malformed or future draft payloads', () => {
    const storage = { getItem: () => JSON.stringify({ version: 99, prompt: 'không dùng' }) };
    expect(readWorkDraft(storage, 'work', 'conversation')).toBe('');
    expect(readWorkDraft({ getItem: () => '{bad json' }, 'work', 'conversation')).toBe('');
  });
});
