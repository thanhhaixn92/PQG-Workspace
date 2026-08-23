import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clearAllGyoDrafts, clearGyoDraftsByWork, gyoDraftKey, readGyoDraft,
  removeGyoDraft, writeGyoDraft, type GYODraftScope,
} from './draftStorage';

describe('draftStorage', () => {
  let store: Record<string, string>;
  const scope = (overrides: Partial<GYODraftScope> = {}): GYODraftScope => ({
    identityScope: 'identity-opaque', workspaceScope: 'workspace-opaque', workId: 'work-1', conversationId: 'conv-1', ...overrides,
  });
  const mockStorage = () => ({
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
  });

  beforeEach(() => { store = {}; vi.clearAllMocks(); });

  it('does not read or write with an incomplete server-owned scope', () => {
    const incomplete = scope({ identityScope: '' });
    const storage = mockStorage();
    expect(gyoDraftKey(incomplete)).toBeNull();
    expect(readGyoDraft(storage, incomplete)).toBeNull();
    writeGyoDraft(storage, incomplete, { prompt: 'secret', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    expect(storage.setItem).not.toHaveBeenCalled();
  });

  it('persists and restores only the exact identity/workspace/work/conversation scope', () => {
    const exact = scope();
    const sibling = scope({ conversationId: 'conv-2' });
    const storage = mockStorage();
    writeGyoDraft(storage, exact, { prompt: 'hello', modelChoice: 'auto', attachmentIds: ['artifact-1'], createdAt: 1, updatedAt: 2 });
    expect(gyoDraftKey(exact)).toContain(':identity-opaque:workspace-opaque:work-1:conv-1');
    expect(readGyoDraft(storage, exact)?.prompt).toBe('hello');
    expect(readGyoDraft(storage, exact)?.attachmentIds).toEqual(['artifact-1']);
    expect(readGyoDraft(storage, sibling)).toBeNull();
  });

  it('reads a legacy v2 draft without attachment ids as an empty attachment list', () => {
    const storage = mockStorage();
    const key = gyoDraftKey(scope())!;
    store[key] = JSON.stringify({ version: 2, prompt: 'legacy', modelChoice: 'auto', createdAt: 1, updatedAt: 2 });
    expect(readGyoDraft(storage, scope())?.attachmentIds).toEqual([]);
  });

  it('removes a stale conversation draft without erasing a sibling draft', () => {
    const first = scope({ conversationId: 'conv-a' });
    const second = scope({ conversationId: 'conv-b' });
    const storage = mockStorage();
    writeGyoDraft(storage, first, { prompt: 'first', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    writeGyoDraft(storage, second, { prompt: 'second', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    removeGyoDraft(storage, first);
    expect(readGyoDraft(storage, first)).toBeNull();
    expect(readGyoDraft(storage, second)?.prompt).toBe('second');
  });

  it('clears only the active work scope on a workspace switch', () => {
    const first = scope();
    const otherWork = scope({ workId: 'work-2' });
    const storage = mockStorage();
    writeGyoDraft(storage, first, { prompt: 'first', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    writeGyoDraft(storage, otherWork, { prompt: 'other', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    expect(clearGyoDraftsByWork(storage, { identityScope: first.identityScope, workspaceScope: first.workspaceScope, workId: first.workId })).toBe(1);
    expect(readGyoDraft(storage, first)).toBeNull();
    expect(readGyoDraft(storage, otherWork)?.prompt).toBe('other');
  });

  it('clears all GYO drafts on logout', () => {
    const storage = mockStorage();
    writeGyoDraft(storage, scope(), { prompt: 'one', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    writeGyoDraft(storage, scope({ workId: 'work-2' }), { prompt: 'two', modelChoice: 'auto', attachmentIds: [], createdAt: 1, updatedAt: 1 });
    expect(clearAllGyoDrafts(storage)).toBe(2);
    expect(store).toEqual({});
  });
});
