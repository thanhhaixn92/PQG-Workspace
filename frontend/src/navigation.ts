import type { SidebarTab } from './store/store';
import { PATH_BY_SIDEBAR_TAB, SIDEBAR_TAB_BY_PATH } from './foundation/modules/registry';

export type WorkspaceRouteTab = 'today' | 'upcoming' | 'ai' | 'history';

const workspaceTabs: WorkspaceRouteTab[] = ['today', 'upcoming', 'ai', 'history'];

const publishLocationChange = () => {
  // history.pushState/replaceState do not emit popstate. The app shell owns
  // route rendering, so programmatic navigation must notify that subscriber.
  window.dispatchEvent(new PopStateEvent('popstate'));
};

const normalisePath = (pathname: string) => {
  const trimmed = pathname.replace(/\/+$/, '');
  return trimmed || '/';
};

export const getSidebarTabFromLocation = (location: Pick<Location, 'pathname'> = window.location): SidebarTab =>
  isGyoAssistantRoute(location.pathname) ? 'sessions' : SIDEBAR_TAB_BY_PATH[normalisePath(location.pathname)] ?? 'overview';

export const getWorkspaceTabFromLocation = (location: Pick<Location, 'search'> = window.location): WorkspaceRouteTab => {
  const tab = new URLSearchParams(location.search).get('tab');
  return workspaceTabs.includes(tab as WorkspaceRouteTab) ? tab as WorkspaceRouteTab : 'today';
};

export const navigateToSidebarTab = (tab: SidebarTab) => {
  const target = PATH_BY_SIDEBAR_TAB[tab];
  if (typeof window === 'undefined' || `${window.location.pathname}${window.location.search}` === target) return;
  window.history.pushState(null, '', target);
  publishLocationChange();
};

export const navigateToWorkspaceTab = (tab: WorkspaceRouteTab) => {
  if (typeof window === 'undefined') return;
  const search = new URLSearchParams();
  search.set('tab', tab);
  const target = `/work?${search.toString()}`;
  if (`${window.location.pathname}${window.location.search}` === target) return;
  window.history.pushState(null, '', target);
  publishLocationChange();
};

/**
 * GYO Assistant canonical URL helpers.
 * Canonical URL format: /work/:workId/assistant?conversation=:id&thread=:id
 * All IDs are opaque — never embed titles or paths.
 */

export interface GYOAssistantLocation {
  workId: string | null;
  conversationId: string | null;
  threadId: string | null;
  isAssistantRoute: boolean;
}

const ASSISTANT_PATH_REGEX = /^\/work\/([^/]+)\/assistant$/;

export function parseGyoAssistantLocation(location: Pick<Location, 'pathname' | 'search'> = window.location): GYOAssistantLocation {
  const match = normalisePath(location.pathname).match(ASSISTANT_PATH_REGEX);
  if (!match) return { workId: null, conversationId: null, threadId: null, isAssistantRoute: false };

  const workId = decodeURIComponent(match[1]);
  const searchParams = new URLSearchParams(location.search);
  const conversationId = searchParams.get('conversation');
  const threadId = searchParams.get('thread');

  return {
    workId,
    conversationId: conversationId && conversationId.trim() ? decodeURIComponent(conversationId) : null,
    threadId: threadId && threadId.trim() ? decodeURIComponent(threadId) : null,
    isAssistantRoute: true,
  };
}

export function buildGyoAssistantUrl(workId: string, conversationId?: string | null, threadId?: string | null): string {
  const params = new URLSearchParams();
  if (conversationId) params.set('conversation', encodeURIComponent(conversationId));
  if (threadId) params.set('thread', encodeURIComponent(threadId));
  return `/work/${encodeURIComponent(workId)}/assistant${params.toString() ? `?${params.toString()}` : ''}`;
}

export function navigateToGyoAssistant(workId: string, conversationId?: string | null, threadId?: string | null, replace = false) {
  const url = buildGyoAssistantUrl(workId, conversationId, threadId);
  if (typeof window === 'undefined') return;
  if (replace) {
    window.history.replaceState(null, '', url);
  } else {
    window.history.pushState(null, '', url);
  }
  publishLocationChange();
}

/**
 * Check if we're on the assistant route within a work context.
 * Accepts a full path+search string or pathname only.
 */
export function isGyoAssistantRoute(pathname: string = window.location.pathname): boolean {
  const cleanPath = pathname.split('?')[0];
  return ASSISTANT_PATH_REGEX.test(normalisePath(cleanPath));
}

/**
 * Check if we're on the global assistant route (top-level /assistant).
 * Accepts a full path+search string or pathname only.
 */
export function isGlobalAssistantRoute(pathname: string = window.location.pathname): boolean {
  const cleanPath = pathname.split('?')[0];
  return normalisePath(cleanPath) === '/assistant';
}
