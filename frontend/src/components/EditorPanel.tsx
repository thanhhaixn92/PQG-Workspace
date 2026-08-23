import React, { useCallback, useEffect, useRef, useState } from 'react';
import Editor from '@monaco-editor/react';
import { FileCode, RotateCcw, Save, X } from 'lucide-react';
import { ApiError } from '../api/client';
import { fetchFileContent, fetchFileTree, saveFileContent } from '../api/files';
import { useHermesStore } from '../store/store';

type SaveState = 'saved' | 'dirty' | 'saving' | 'error';

export const EditorPanel: React.FC = () => {
  const setSidebarTab = useHermesStore(state => state.setSidebarTab);
  const {
    activeSessionId,
    openFiles,
    activeFile,
    fileContents,
    fileMetadata,
    dirtyFiles,
    setFileTree,
    setActiveFile,
    closeFile,
    setFileContent,
    setFileMetadata,
    markFileClean,
    requestAuditRefresh,
    theme,
  } = useHermesStore();

  const [error, setError] = useState<string | null>(null);
  const [conflictPath, setConflictPath] = useState<string | null>(null);
  const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});
  const [savedSnapshots, setSavedSnapshots] = useState<Record<string, string>>({});
  const unmounted = useRef(false);

  useEffect(() => {
    unmounted.current = false;
    return () => {
      unmounted.current = true;
    };
  }, []);

  useEffect(() => {
    setSavedSnapshots(current => {
      const next = { ...current };
      openFiles.forEach(path => {
        if (!(path in next)) {
          next[path] = fileContents[path] || '';
        }
      });
      Object.keys(next).forEach(path => {
        if (!openFiles.includes(path)) {
          delete next[path];
        }
      });
      return next;
    });
  }, [fileContents, openFiles]);

  const activeSaveState: SaveState = activeFile
    ? saveStates[activeFile] || (dirtyFiles.has(activeFile) ? 'dirty' : 'saved')
    : 'saved';

  const refreshFileTree = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    try {
      const tree = await fetchFileTree(activeSessionId);
      setFileTree(tree.tree);
    } catch {
      // Best-effort refresh only.
    }
  }, [activeSessionId, setFileTree]);

  const saveFile = useCallback(async (path: string, force = false) => {
    if (!activeSessionId) {
      return;
    }

    const sessionId = activeSessionId;
    const contentToSave = fileContents[path] || '';
    const expectedHash = fileMetadata[path]?.hash;
    setSaveStates(state => ({ ...state, [path]: 'saving' }));

    try {
      const result = expectedHash
        ? await saveFileContent(sessionId, path, contentToSave, fileMetadata[path]?.mtime, force, expectedHash)
        : await saveFileContent(sessionId, path, contentToSave, fileMetadata[path]?.mtime, force);
      const currentState = useHermesStore.getState();
      if (!unmounted.current && currentState.activeSessionId === sessionId && currentState.fileContents[path] === contentToSave) {
        markFileClean(path);
        setFileMetadata(path, { mtime: result.mtime, size: result.size, hash: result.hash });
        setSavedSnapshots(state => ({ ...state, [path]: contentToSave }));
        setSaveStates(state => ({ ...state, [path]: 'saved' }));
        setConflictPath(null);
        setError(null);
        requestAuditRefresh();
        void refreshFileTree();
      }
    } catch (err: unknown) {
      if (!unmounted.current) {
        setSaveStates(state => ({ ...state, [path]: 'error' }));
        if (err instanceof ApiError && err.status === 409) {
          setConflictPath(path);
          setError(`File ${path} có thể đã thay đổi bên ngoài app. Hãy chọn tải lại hoặc lưu đè.`);
        } else {
          const message = err instanceof Error ? err.message : 'lỗi không xác định';
          setError(`Không lưu được ${path}: ${message}`);
        }
      }
    }
  }, [
    activeSessionId,
    fileContents,
    fileMetadata,
    markFileClean,
    refreshFileTree,
    requestAuditRefresh,
    setFileMetadata,
  ]);

  const reloadConflictFile = async () => {
    if (!activeSessionId || !conflictPath) {
      return;
    }

    try {
      const file = await fetchFileContent(activeSessionId, conflictPath);
      if (useHermesStore.getState().activeSessionId !== activeSessionId) return;
      setFileContent(conflictPath, file.content);
      markFileClean(conflictPath);
      setFileMetadata(conflictPath, { mtime: file.mtime, size: file.size, hash: file.hash });
      setSavedSnapshots(state => ({ ...state, [conflictPath]: file.content }));
      setSaveStates(state => ({ ...state, [conflictPath]: 'saved' }));
      setConflictPath(null);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'lỗi không xác định';
      setError(`Không thể tải lại ${conflictPath}: ${message}`);
    }
  };

  const handleEditorChange = useCallback((value: string | undefined) => {
    if (value === undefined || !activeSessionId || !activeFile) {
      return;
    }
    setFileContent(activeFile, value);
    setSaveStates(state => ({ ...state, [activeFile]: 'dirty' }));
  }, [activeSessionId, activeFile, setFileContent]);

  const restoreActiveFile = () => {
    if (!activeFile) {
      return;
    }
    const snapshot = savedSnapshots[activeFile];
    if (snapshot === undefined) {
      return;
    }
    const confirmed = window.confirm('Khôi phục nội dung về bản đã lưu gần nhất? Thay đổi chưa lưu sẽ bị bỏ.');
    if (!confirmed) {
      return;
    }
    setFileContent(activeFile, snapshot);
    markFileClean(activeFile);
    setSaveStates(state => ({ ...state, [activeFile]: 'saved' }));
    setError(null);
  };

  const handleClose = useCallback((path: string) => {
    if (dirtyFiles.has(path)) {
      const confirmed = window.confirm('Tệp này còn thay đổi chưa lưu. Đóng tệp và bỏ thay đổi?');
      if (!confirmed) {
        return;
      }
    }
    closeFile(path);
  }, [closeFile, dirtyFiles]);

  useEffect(() => {
    if (!activeSessionId || !activeFile || !dirtyFiles.has(activeFile)) {
      return;
    }

    const fileToSave = activeFile;
    const timer = setTimeout(() => {
      void saveFile(fileToSave);
    }, 1500);

    return () => clearTimeout(timer);
  }, [activeFile, activeSessionId, dirtyFiles, fileContents, saveFile]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (activeFile) void saveFile(activeFile);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'w') {
        e.preventDefault();
        if (activeFile) handleClose(activeFile);
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'E') {
        e.preventDefault();
        setSidebarTab('files');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [activeFile, handleClose, saveFile, setSidebarTab]);

  if (openFiles.length === 0 || !activeFile) {
    return (
      <div className="editor-empty-state">
        <FileCode size={42} style={{ opacity: 0.25, marginBottom: '0.75rem' }} />
        <p>Chưa mở tệp</p>
      </div>
    );
  }

  const currentContent = fileContents[activeFile] || '';
  const saveLabel = {
    saved: 'Đã lưu',
    dirty: 'Chưa lưu',
    saving: 'Đang lưu...',
    error: 'Lỗi lưu',
  }[activeSaveState];

  return (
    <div className="editor-panel">
      <div className="editor-tabs">
        {openFiles.map(path => (
          <div
            key={path}
            className={`editor-tab ${path === activeFile ? 'active' : ''}`}
          >
            <button
              type="button"
              className="editor-tab-select"
              role="tab"
              aria-selected={path === activeFile}
              onClick={() => setActiveFile(path)}
            >
              <span title={path}>{path.split('/').pop()}</span>
              {dirtyFiles.has(path) && <span style={{ color: 'var(--accent-primary)' }}>*</span>}
            </button>
            <button
              type="button"
              onClick={() => {
                handleClose(path);
              }}
              title="Đóng tệp"
            >
              <X size={14} />
            </button>
          </div>
        ))}
        <div className={`editor-save-state ${activeSaveState}`}>
          <span>{saveLabel}</span>
          <button
            onClick={restoreActiveFile}
            disabled={activeSaveState === 'saving' || !dirtyFiles.has(activeFile)}
            title="Khôi phục bản đã lưu"
          >
            <RotateCcw size={14} />
          </button>
          <button onClick={() => void saveFile(activeFile)} disabled={activeSaveState === 'saving'} title="Lưu tệp">
            <Save size={14} />
          </button>
        </div>
      </div>

      {error && (
        <div className="editor-error">
          <span>{error}</span>
          {conflictPath && (
            <>
              <button onClick={() => void reloadConflictFile()} title="Tải lại từ disk">
                Tải lại
              </button>
              <button
                onClick={() => {
                  const confirmed = window.confirm('File đã đổi bên ngoài app. Bạn chắc chắn muốn lưu đè?');
                  if (confirmed) {
                    void saveFile(conflictPath, true);
                  }
                }}
                title="Lưu đè"
              >
                Lưu đè
              </button>
            </>
          )}
          <button onClick={() => setError(null)} title="Đóng thông báo lỗi">
            <X size={14} />
          </button>
        </div>
      )}

      <div className="editor-container">
        <Editor
          height="100%"
          language={getLanguageFromPath(activeFile)}
          theme={theme === 'light' ? 'vs' : 'vs-dark'}
          value={currentContent}
          onChange={handleEditorChange}
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            padding: { top: 16 },
          }}
          loading={<div style={{ padding: '1rem', color: 'var(--text-secondary)' }}>Đang tải trình soạn thảo...</div>}
        />
      </div>
    </div>
  );
};

function getLanguageFromPath(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'ts':
    case 'tsx':
      return 'typescript';
    case 'js':
    case 'jsx':
      return 'javascript';
    case 'json':
      return 'json';
    case 'html':
      return 'html';
    case 'css':
      return 'css';
    case 'md':
      return 'markdown';
    case 'py':
      return 'python';
    case 'sql':
      return 'sql';
    default:
      return 'plaintext';
  }
}
