import { create } from 'zustand';
import type { FileNode } from '../api/files';
import type { Skill } from '../api/skills';
import type { MemoryEntry } from '../api/memory';

export interface Session {
  id: string;
  title: string;
  workspace_path: string;
  created_at: number;
  updated_at?: number;
  archived?: number;
}

export type HermesEventType =
  | 'user_message'
  | 'token'
  | 'tool_call'
  | 'terminal'
  | 'file_diff'
  | 'approval_required'
  | 'approval_decision'
  | 'plan_update'
  | 'status'
  | 'error'
  | 'done';

export interface HermesEvent {
  id: string;
  type: HermesEventType;
  text?: string;
  message?: string;
  created_at?: number;
  tool_name?: string;
  output?: string;
  approval_id?: string;
  action?: string;
  target?: string;
  risk_level?: 'read' | 'write_internal' | 'external_or_destructive';
  description?: string;
  decision?: string;
  arguments?: unknown;
  [key: string]: unknown;
}

export interface ApprovalRequest {
  approval_id: string;
  action: string;
  target: string;
  risk_level: 'read' | 'write_internal' | 'external_or_destructive';
  description?: string;
}

export interface TaskRun {
  id: string;
  session_id: string;
  status: 'queued' | 'running' | 'waiting_approval' | 'completed' | 'succeeded' | 'failed' | 'cancelled';
  started_at: number;
  finished_at?: number | null;
  error?: string | null;
  retry_count: number;
}

export interface FileMetadata {
  mtime: number;
  size: number;
}

export type SessionRuntimeStatus = 'idle' | 'queued' | 'running' | 'waiting_approval' | 'error';
export type SidebarTab = 'sessions' | 'files' | 'skills' | 'memory' | 'data';
export type ThemeMode = 'dark' | 'light';

interface HermesStore {
  // Session State
  sessions: Session[];
  activeSessionId: string | null;
  sidebarTab: SidebarTab;
  setSessions: (sessions: Session[]) => void;
  setActiveSession: (id: string | null) => void;
  setSidebarTab: (tab: SidebarTab) => void;
  addSession: (session: Session) => void;
  updateSession: (id: string, updates: Partial<Session>) => void;
  removeSession: (id: string) => void;
  
  // Chat / Event State
  events: Record<string, HermesEvent[]>; // mapped by session ID
  latestTaskBySession: Record<string, TaskRun | null>;
  auditRefreshVersion: number;
  addEvent: (sessionId: string, event: HermesEvent) => void;
  setEvents: (sessionId: string, events: HermesEvent[]) => void;
  setLatestTask: (sessionId: string, task: TaskRun | null) => void;
  requestAuditRefresh: () => void;
  
  // Approvals State
  pendingApproval: ApprovalRequest | null;
  setPendingApproval: (approval: ApprovalRequest | null) => void;
  
  // File Editor State
  fileTree: FileNode[];
  openFiles: string[];
  activeFile: string | null;
  fileContents: Record<string, string>;
  fileMetadata: Record<string, FileMetadata>;
  dirtyFiles: Set<string>;

  // Activity / Status State
  appError: string | null;
  sessionStatusById: Record<string, SessionRuntimeStatus>;
  sessionErrorById: Record<string, string | null>;
  sessionStartedAtById: Record<string, number>;
  setAppError: (error: string | null) => void;
  setSessionStatus: (sessionId: string, status: SessionRuntimeStatus) => void;
  setSessionError: (sessionId: string, error: string | null) => void;
  setSessionStartedAt: (sessionId: string, timestamp: number | null) => void;
  
  // File Actions
  setFileTree: (tree: FileNode[]) => void;
  openFile: (path: string, content: string, metadata?: FileMetadata) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string | null) => void;
  setFileContent: (path: string, content: string) => void;
  setFileMetadata: (path: string, metadata: FileMetadata) => void;
  markFileClean: (path: string) => void;
  resetFileState: () => void;

  // Theme State
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;

  // Skills State
  skills: Skill[];
  setSkills: (skills: Skill[]) => void;
  
  // Memory State
  memory: MemoryEntry[];
  setMemory: (memory: MemoryEntry[]) => void;
}

export const useHermesStore = create<HermesStore>((set) => ({
  sessions: [],
  activeSessionId: null,
  sidebarTab: 'sessions',
  setSessions: (sessions) => set({ sessions }),
  setActiveSession: (id) => set({ activeSessionId: id }),
  setSidebarTab: (tab) => set({ sidebarTab: tab }),
  addSession: (session) => set((state) => ({ sessions: [...state.sessions, session] })),
  updateSession: (id, updates) => set((state) => ({
    sessions: state.sessions.map(s => s.id === id ? { ...s, ...updates } : s)
  })),
  removeSession: (id) => set((state) => {
    const sessions = state.sessions.filter(s => s.id !== id);
    const activeSessionId = state.activeSessionId === id ? (sessions[0]?.id ?? null) : state.activeSessionId;
    return { sessions, activeSessionId };
  }),
  
  events: {},
  latestTaskBySession: {},
  auditRefreshVersion: 0,
  addEvent: (sessionId, event) => set((state) => {
    const sessionEvents = state.events[sessionId] || [];
    
    if (event.type === 'token' && sessionEvents.length > 0) {
      const lastEvent = sessionEvents[sessionEvents.length - 1];
      if (lastEvent.type === 'token') {
        const newEvents = [...sessionEvents];
        newEvents[newEvents.length - 1] = {
          ...lastEvent,
          text: (lastEvent.text || '') + (event.text || '')
        };
        return {
          events: { ...state.events, [sessionId]: newEvents }
        };
      }
    }
    
    return {
      events: {
        ...state.events,
        [sessionId]: [...sessionEvents, event]
      }
    };
  }),
  setEvents: (sessionId, events) => set((state) => ({
    events: {
      ...state.events,
      [sessionId]: events
    }
  })),
  setLatestTask: (sessionId, task) => set((state) => ({
    latestTaskBySession: {
      ...state.latestTaskBySession,
      [sessionId]: task
    }
  })),
  requestAuditRefresh: () => set((state) => ({ auditRefreshVersion: state.auditRefreshVersion + 1 })),
  
  pendingApproval: null,
  setPendingApproval: (approval) => set({ pendingApproval: approval }),
  
  fileTree: [],
  openFiles: [],
  activeFile: null,
  fileContents: {},
  fileMetadata: {},
  dirtyFiles: new Set(),

  appError: null,
  sessionStatusById: {},
  sessionErrorById: {},
  sessionStartedAtById: {},
  setAppError: (error) => set({ appError: error }),
  setSessionStatus: (sessionId, status) => set((state) => ({
    sessionStatusById: {
      ...state.sessionStatusById,
      [sessionId]: status,
    },
  })),
  setSessionError: (sessionId, error) => set((state) => ({
    sessionErrorById: {
      ...state.sessionErrorById,
      [sessionId]: error,
    },
  })),
  setSessionStartedAt: (sessionId, timestamp) => set((state) => {
    const sessionStartedAtById = { ...state.sessionStartedAtById };
    if (timestamp === null) {
      delete sessionStartedAtById[sessionId];
    } else {
      sessionStartedAtById[sessionId] = timestamp;
    }
    return { sessionStartedAtById };
  }),

  setFileTree: (tree) => set({ fileTree: tree }),
  openFile: (path, content, metadata) => set((state) => {
    const isNew = !state.openFiles.includes(path);
    return {
      openFiles: isNew ? [...state.openFiles, path] : state.openFiles,
      activeFile: path,
      fileContents: { ...state.fileContents, [path]: content },
      fileMetadata: metadata ? { ...state.fileMetadata, [path]: metadata } : state.fileMetadata,
      dirtyFiles: new Set([...state.dirtyFiles].filter(p => p !== path))
    };
  }),
  closeFile: (path) => set((state) => {
    const openFiles = state.openFiles.filter(p => p !== path);
    const dirtyFiles = new Set(state.dirtyFiles);
    dirtyFiles.delete(path);
    const fileContents = { ...state.fileContents };
    delete fileContents[path];
    const fileMetadata = { ...state.fileMetadata };
    delete fileMetadata[path];
    
    let activeFile = state.activeFile;
    if (activeFile === path) {
      activeFile = openFiles.length > 0 ? openFiles[openFiles.length - 1] : null;
    }
    
    return { openFiles, activeFile, fileContents, fileMetadata, dirtyFiles };
  }),
  setActiveFile: (path) => set({ activeFile: path }),
  setFileContent: (path, content) => set((state) => {
    const dirtyFiles = new Set(state.dirtyFiles);
    dirtyFiles.add(path);
    return {
      fileContents: { ...state.fileContents, [path]: content },
      dirtyFiles
    };
  }),
  setFileMetadata: (path, metadata) => set((state) => ({
    fileMetadata: { ...state.fileMetadata, [path]: metadata }
  })),
  markFileClean: (path) => set((state) => {
    const dirtyFiles = new Set(state.dirtyFiles);
    dirtyFiles.delete(path);
    return { dirtyFiles };
  }),
  resetFileState: () => set({
    fileTree: [],
    openFiles: [],
    activeFile: null,
    fileContents: {},
    fileMetadata: {},
    dirtyFiles: new Set()
  }),
  
  theme: (window.localStorage.getItem('hermes.theme') as ThemeMode) || 'dark',
  setTheme: (theme) => {
    window.localStorage.setItem('hermes.theme', theme);
    set({ theme });
  },
  toggleTheme: () => set((state) => {
    const next = state.theme === 'dark' ? 'light' : 'dark';
    window.localStorage.setItem('hermes.theme', next);
    return { theme: next };
  }),

  skills: [],
  setSkills: (skills) => set({ skills }),
  
  memory: [],
  setMemory: (memory) => set({ memory }),
}));
