/**
 * Session-scoped GYO drafts. The opaque scopes come from the server runtime
 * endpoint; no browser-supplied actor or account identifier participates in
 * the namespace.
 */
const DRAFT_VERSION = 2;

export interface GYODraftScope {
  identityScope: string;
  workspaceScope: string;
  workId: string;
  conversationId: string;
}

function isUsableScope(scope: GYODraftScope): boolean {
  return Boolean(
    scope.identityScope.trim()
    && scope.workspaceScope.trim()
    && scope.workId.trim()
    && scope.conversationId.trim(),
  );
}

function getNamespace(scope: GYODraftScope): string {
  return `gyo:draft:v${DRAFT_VERSION}:${scope.identityScope}:${scope.workspaceScope}:${scope.workId}:${scope.conversationId}`;
}

export interface GYODraftData {
  prompt: string;
  createdAt: number;
  updatedAt: number;
  modelChoice: string;
  /** Opaque artifact ids only; file names and content never enter browser draft storage. */
  attachmentIds: string[];
}

export function gyoDraftKey(scope: GYODraftScope): string | null {
  return isUsableScope(scope) ? getNamespace(scope) : null;
}

export function readGyoDraft(storage: Pick<Storage, 'getItem'>, scope: GYODraftScope): GYODraftData | null {
  const key = gyoDraftKey(scope);
  if (!key) return null;
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<GYODraftData> & { version?: number };
    if (parsed.version !== DRAFT_VERSION) return null;
    return {
      prompt: typeof parsed.prompt === 'string' ? parsed.prompt : '',
      createdAt: typeof parsed.createdAt === 'number' ? parsed.createdAt : 0,
      updatedAt: typeof parsed.updatedAt === 'number' ? parsed.updatedAt : 0,
      modelChoice: typeof parsed.modelChoice === 'string' ? parsed.modelChoice : '',
      attachmentIds: Array.isArray(parsed.attachmentIds)
        ? parsed.attachmentIds.filter((value): value is string => typeof value === 'string')
        : [],
    };
  } catch {
    return null;
  }
}

export function writeGyoDraft(
  storage: Pick<Storage, 'setItem' | 'removeItem'>,
  scope: GYODraftScope,
  data: GYODraftData,
): void {
  const key = gyoDraftKey(scope);
  if (!key) return;
  if (!data.prompt && (!data.attachmentIds?.length) && (!data.modelChoice || data.modelChoice === 'auto')) storage.removeItem(key);
  else storage.setItem(key, JSON.stringify({ version: DRAFT_VERSION, ...data }));
}

export function removeGyoDraft(storage: Pick<Storage, 'removeItem'>, scope: GYODraftScope): void {
  const key = gyoDraftKey(scope);
  if (key) storage.removeItem(key);
}

export function clearAllGyoDrafts(storage: Pick<Storage, 'length' | 'key' | 'removeItem'>): number {
  const prefix = 'gyo:draft:';
  let removed = 0;
  for (let i = storage.length - 1; i >= 0; i--) {
    const key = storage.key(i);
    if (key?.startsWith(prefix)) {
      storage.removeItem(key);
      removed++;
    }
  }
  return removed;
}

/** Clear the active identity/workspace/work only; sibling workspaces remain intact. */
export function clearGyoDraftsByWork(
  storage: Pick<Storage, 'length' | 'key' | 'removeItem'>,
  scope: Omit<GYODraftScope, 'conversationId'>,
): number {
  if (!scope.identityScope || !scope.workspaceScope || !scope.workId) return 0;
  const prefix = `gyo:draft:v${DRAFT_VERSION}:${scope.identityScope}:${scope.workspaceScope}:${scope.workId}:`;
  let removed = 0;
  for (let i = storage.length - 1; i >= 0; i--) {
    const key = storage.key(i);
    if (key?.startsWith(prefix)) {
      storage.removeItem(key);
      removed++;
    }
  }
  return removed;
}
