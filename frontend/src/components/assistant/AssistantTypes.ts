import type { AssistantTurn, AssistantThread, AssistantContextManifest } from '../../api/assistant';
import type { ActionPackage } from '../../api/actionPackages';
import type { Artifact } from '../../api/artifacts';
import type { GyoModel, GyoProvider } from '../../api/marketplace';
import type { Conversation } from '../../api/works';

/** Canonical UI modes for the GYO assistant surface. */
export type GYOSurfaceMode = 'drawer' | 'focus';

/**
 * Canonical assistant surface state.
 * Mirrors the backend turn thread: queued → running → completed|failed|cancelled.
 */
export type GYOActivityStatus =
  | 'idle'
  | 'welcome'
  | 'compose'
  | 'streaming'
  | 'running'
  | 'needs_info'
  | 'confirmation'
  | 'executing'
  | 'completed'
  | 'partial'
  | 'failed'
  | 'blocked'
  | 'interrupted'
  | 'history';

/** A pending confirmation item rendered from backend canonical state. */
export interface GYOConfirmationItem {
  type: 'action_package';
  package: ActionPackage;
  /** Optional concurrency guard from the backend (contract gap noted in receipt). */
  expectedRevision?: number | null;
  expectedPayloadHash?: string | null;
}

/** Attachment descriptor shown in the composer tray. */
export interface GYOAttachment {
  id: string;
  name: string;
  kind: string;
  sizeBytes: number;
  sha256: string;
}

/** A single turn as rendered in the message list. */
export interface GYOTurnView {
  turn: AssistantTurn;
  streamedText?: string;
}

/** Context panel groups: canonical categories from the manifest. */
export interface GYOContextGroup {
  label: 'accessible' | 'retrieved' | 'used' | 'targeted' | 'excluded';
  title: string;
  items: Array<Record<string, unknown>>;
}

export interface GYOAssistantState {
  /** Current high-level surface mode. */
  mode: GYOActivityStatus;
  /** Selected work session id (opaque). */
  workId: string | null;
  /** Selected conversation id (opaque). */
  conversationId: string | null;
  /** Selected thread id (opaque). */
  threadId: string | null;
  /** All threads for the current work/conversation scope. */
  threads: AssistantThread[];
  /** All conversations for the current work. */
  conversations: Conversation[];
  /** Turns for the selected thread. */
  turns: GYOTurnView[];
  /** Context manifest describing what GYO will use. */
  manifest: AssistantContextManifest | null;
  /** Available artifacts for attachment. */
  availableArtifacts: Artifact[];
  /** Currently attached artifact ids. */
  attachmentIds: string[];
  /** Available models for the capability selector. */
  availableModels: GyoModel[];
  /** Available providers, grouped. */
  modelProviders: GyoProvider[];
  /** Current selected model choice ('auto' or 'model:<id>'). */
  modelChoice: string;
  /** Composer draft text. */
  draft: string;
  /** Pending confirmation items. */
  confirmations: GYOConfirmationItem[];
  /** Execution view data (only populated when backend provides it). */
  execution: {
    steps: Array<{ id: string; title: string; status: 'pending' | 'running' | 'succeeded' | 'failed'; progress?: number | null }>;
    progressPercent: number | null;
    etaSeconds: number | null;
  } | null;
  /** History items (Work-scoped, keyset cursor). */
  history: {
    items: AssistantThread[];
    /** Cursor for keyset pagination. */
    nextCursor: string | null;
    /** Whether more items exist. */
    hasMore: boolean;
  };
  /** Errors, each categorized. */
  errors: Array<{ category: GYOErrorCategory; message: string; actionable: boolean }>;
}

export type GYOErrorCategory =
  | 'conflict'
  | 'expired'
  | 'missing_artifact'
  | 'permission'
  | 'disconnected'
  | 'model_unavailable'
  | 'budget'
  | 'interrupted'
  | 'generic';

export interface GYOAssistantConfig {
  /** Surface mode: drawer (sidebar) or focus (main content). */
  surface: GYOSurfaceMode;
  /** Whether the assistant surface is currently visible. */
  visible: boolean;
  /** Work session id parsed from URL. */
  workId: string | null;
  /** Conversation id parsed from URL query param. */
  conversationId: string | null;
  /** Thread id parsed from URL query param. */
  threadId: string | null;
}
