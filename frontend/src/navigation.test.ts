import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  parseGyoAssistantLocation,
  buildGyoAssistantUrl,
  navigateToGyoAssistant,
  isGyoAssistantRoute,
  isGlobalAssistantRoute,
  getSidebarTabFromLocation,
} from './navigation';

describe('GYO Assistant URL routing', () => {
  beforeEach(() => {
    vi.stubGlobal('addEventListener', window.addEventListener.bind(window));
    vi.stubGlobal('removeEventListener', window.removeEventListener.bind(window));
  });

  it('parses canonical assistant URL with conversation and thread', () => {
    window.history.replaceState(null, '', '/work/work-123/assistant?conversation=conv-abc&thread=thread-xyz');
    const result = parseGyoAssistantLocation();
    expect(result.isAssistantRoute).toBe(true);
    expect(result.workId).toBe('work-123');
    expect(result.conversationId).toBe('conv-abc');
    expect(result.threadId).toBe('thread-xyz');
  });

  it('parses assistant URL with only work id', () => {
    window.history.replaceState(null, '', '/work/work-456/assistant');
    const result = parseGyoAssistantLocation();
    expect(result.isAssistantRoute).toBe(true);
    expect(result.workId).toBe('work-456');
    expect(result.conversationId).toBeNull();
    expect(result.threadId).toBeNull();
  });

  it('returns isAssistantRoute=false for non-assistant paths', () => {
    window.history.replaceState(null, '', '/work/work-123');
    const result = parseGyoAssistantLocation();
    expect(result.isAssistantRoute).toBe(false);
    expect(result.workId).toBeNull();
  });

  it('handles URL-encoded IDs', () => {
    window.history.replaceState(null, '', '/work/work%20abc/assistant?conversation=conv%20xyz&thread=thr%401');
    const result = parseGyoAssistantLocation();
    expect(result.workId).toBe('work abc');
    expect(result.conversationId).toBe('conv xyz');
    expect(result.threadId).toBe('thr@1');
  });

  it('builds canonical URL with all params', () => {
    const url = buildGyoAssistantUrl('work-1', 'conv-1', 'thread-1');
    expect(url).toBe('/work/work-1/assistant?conversation=conv-1&thread=thread-1');
  });

  it('builds URL with only work id when no conversation', () => {
    const url = buildGyoAssistantUrl('work-2');
    expect(url).toBe('/work/work-2/assistant');
  });

  it('builds URL with work + conversation but no thread', () => {
    const url = buildGyoAssistantUrl('work-3', 'conv-3');
    expect(url).toBe('/work/work-3/assistant?conversation=conv-3');
  });

  it('navigates to canonical URL (push)', () => {
    const locationChanged = vi.fn();
    window.addEventListener('popstate', locationChanged);
    const startPath = window.location.pathname + window.location.search;
    navigateToGyoAssistant('work-x', 'conv-x', 'thread-x');
    expect(window.location.pathname).toBe('/work/work-x/assistant');
    expect(new URLSearchParams(window.location.search).get('conversation')).toBe('conv-x');
    expect(new URLSearchParams(window.location.search).get('thread')).toBe('thread-x');
    expect(locationChanged).toHaveBeenCalledOnce();
    window.removeEventListener('popstate', locationChanged);
    // Restore
    window.history.replaceState(null, '', startPath);
  });

  it('navigates to canonical URL (replace) without adding history entry', () => {
    window.history.replaceState(null, '', '/');
    const entriesBefore = window.history.length;
    navigateToGyoAssistant('work-y', 'conv-y', 'thread-y', true);
    expect(window.location.pathname).toBe('/work/work-y/assistant');
    expect(new URLSearchParams(window.location.search).get('conversation')).toBe('conv-y');
    // Replace should not increase history length
    expect(window.history.length).toBe(entriesBefore);
  });

  it('isGyoAssistantRoute returns true for assistant routes', () => {
    expect(isGyoAssistantRoute('/work/work-1/assistant')).toBe(true);
    expect(isGyoAssistantRoute('/work/work-1/assistant?conversation=c1')).toBe(true);
  });

  it('selects Công việc in the sidebar for an assistant deep link', () => {
    window.history.replaceState(null, '', '/work/work-1/assistant?conversation=conv-1');
    expect(getSidebarTabFromLocation()).toBe('sessions');
  });

  it('isGyoAssistantRoute returns false for non-assistant routes', () => {
    expect(isGyoAssistantRoute('/work/work-1')).toBe(false);
    expect(isGyoAssistantRoute('/')).toBe(false);
    expect(isGyoAssistantRoute('/assistant')).toBe(false);
  });

  it('isGlobalAssistantRoute returns true only for /assistant', () => {
    expect(isGlobalAssistantRoute('/assistant')).toBe(true);
    expect(isGlobalAssistantRoute('/assistant?tab=history')).toBe(true);
    expect(isGlobalAssistantRoute('/work/work-1/assistant')).toBe(false);
  });
});
