import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, FilePlus2, FileText, FileWarning, Folder, FolderOpen, FolderPlus, RefreshCw, Upload, X } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { createManagedFolder, createManagedTextFile, fetchFileContent, fetchFileTree, importDocument } from '../api/files';
import type { FileNode } from '../api/files';
import { countTestDataNodes, filterTestDataNodes } from './fileTreeFilters';

const FileTreeNode: React.FC<{
  node: FileNode;
  depth: number;
  onError: (message: string | null) => void;
}> = ({ node, depth, onError }) => {
  const [expanded, setExpanded] = useState(false);
  const { activeSessionId, openFile, activeFile } = useHermesStore();
  const [loading, setLoading] = useState(false);

  const isDirectory = node.type === 'directory';

  const handleClick = async () => {
    if (isDirectory) {
      setExpanded(current => !current);
      return;
    }

    if (node.too_large) {
      onError(`Không thể mở ${node.name}: tệp quá lớn (> 1MB)`);
      return;
    }
    if (!activeSessionId) {
      return;
    }

    try {
      onError(null);
      setLoading(true);
      const sessionId = activeSessionId;
      const file = await fetchFileContent(sessionId, node.path);
      if (useHermesStore.getState().activeSessionId !== sessionId) return;
      openFile(node.path, file.content, { mtime: file.mtime, size: file.size, hash: file.hash });
    } catch (err: unknown) {
      if (useHermesStore.getState().activeSessionId !== activeSessionId) return;
      const message = err instanceof Error ? err.message : 'lỗi không xác định';
      onError(`Không đọc được tệp ${node.name}: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const isActive = activeFile === node.path;

  return (
    <div>
      <button
        type="button"
        onClick={() => void handleClick()}
        onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); void handleClick(); } }}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '0.25rem 0.5rem',
          paddingLeft: `${depth * 1 + 0.5}rem`,
          cursor: 'pointer',
          backgroundColor: isActive ? 'var(--bg-tertiary)' : 'transparent',
          color: isActive ? 'var(--accent-primary)' : 'var(--text-primary)',
          userSelect: 'none',
          fontSize: '0.9rem',
          opacity: loading ? 0.7 : 1,
        }}
        className="file-tree-node hover-bg"
      >
        <span style={{ width: '16px', display: 'flex', alignItems: 'center', marginRight: '4px' }}>
          {isDirectory ? (expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />) : null}
        </span>
        <span style={{ marginRight: '6px', color: 'var(--text-secondary)' }}>
          {isDirectory ? (
            expanded ? <FolderOpen size={14} /> : <Folder size={14} />
          ) : node.too_large ? (
            <FileWarning size={14} color="#ef4444" />
          ) : (
            <FileText size={14} />
          )}
        </span>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.name}</span>
      </button>
      {isDirectory && expanded && node.children && (
        <div>
          {node.children.map(child => (
            <FileTreeNode key={child.path} node={child} depth={depth + 1} onError={onError} />
          ))}
        </div>
      )}
    </div>
  );
};

export const FileExplorer: React.FC<{ grouped?: boolean }> = ({ grouped = false }) => {
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const fileTree = useHermesStore(state => state.fileTree);
  const setFileTree = useHermesStore(state => state.setFileTree);
  const [loading, setLoading] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const importInputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [createKind, setCreateKind] = useState<'file' | 'folder' | null>(null);
  const [newItemName, setNewItemName] = useState('');
  const [newFileContent, setNewFileContent] = useState('');
  const [creating, setCreating] = useState(false);
  const [showTestData, setShowTestData] = useState(false);

  const loadTree = useCallback(async () => {
    const sessionId = activeSessionId;
    const version = ++requestVersion.current;
    if (!sessionId) {
      setFileTree([]);
      return;
    }

    try {
      setError(null);
      setLoading(true);
      const res = await fetchFileTree(sessionId, grouped);
      if (version !== requestVersion.current || useHermesStore.getState().activeSessionId !== sessionId) return;
      setFileTree(res.tree);
      setTruncated(res.truncated);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'lỗi không xác định';
      if (version === requestVersion.current) setError(`Không tải được cây tệp: ${message}`);
    } finally {
      if (version === requestVersion.current) setLoading(false);
    }
  }, [activeSessionId, grouped, setFileTree]);

  useEffect(() => {
    requestVersion.current += 1;
    setFileTree([]);
    void loadTree();
  }, [loadTree, setFileTree]);

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    const sessionId = activeSessionId;
    event.target.value = '';
    if (!file || !sessionId) return;
    if (file.size > 10 * 1024 * 1024) {
      setError('Tệp vượt giới hạn nhập 10 MB.');
      return;
    }
    setImporting(true);
    setError(null);
    try {
      const key = globalThis.crypto?.randomUUID?.() ?? `import-${Date.now()}-${file.size}`;
      await importDocument(sessionId, file, key);
      if (useHermesStore.getState().activeSessionId === sessionId) await loadTree();
    } catch (err: unknown) {
      if (useHermesStore.getState().activeSessionId === sessionId) {
        setError(err instanceof Error ? `Không nhập được tệp: ${err.message}` : 'Không nhập được tệp.');
      }
    } finally {
      if (useHermesStore.getState().activeSessionId === sessionId) setImporting(false);
    }
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    const sessionId = activeSessionId;
    const name = newItemName.trim();
    if (!sessionId || !createKind || !name) return;
    setCreating(true);
    setError(null);
    try {
      const key = globalThis.crypto?.randomUUID?.() ?? `create-${Date.now()}-${name}`;
      if (createKind === 'folder') await createManagedFolder(sessionId, name, key);
      else await createManagedTextFile(sessionId, name, newFileContent, key);
      if (useHermesStore.getState().activeSessionId === sessionId) {
        setCreateKind(null);
        setNewItemName('');
        setNewFileContent('');
        await loadTree();
      }
    } catch (err: unknown) {
      if (useHermesStore.getState().activeSessionId === sessionId) {
        setError(err instanceof Error ? `Không tạo được tài liệu: ${err.message}` : 'Không tạo được tài liệu.');
      }
    } finally {
      if (useHermesStore.getState().activeSessionId === sessionId) setCreating(false);
    }
  };

  if (!activeSessionId) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">Chưa chọn Công việc</div>
        <div className="empty-state-text">Tạo hoặc chọn một Công việc trước khi quản lý tài liệu.</div>
      </div>
    );
  }

  const testDataCount = grouped ? countTestDataNodes(fileTree) : 0;
  const visibleTree = grouped && !showTestData ? filterTestDataNodes(fileTree) : fileTree;

  return (
    <div className="file-explorer" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          padding: '0.5rem 1rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontWeight: 'bold',
          fontSize: '0.9rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        <span>Không gian làm việc</span>
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {grouped && testDataCount > 0 && <button className="btn-secondary compact-button" type="button" onClick={() => setShowTestData(current => !current)}>{showTestData ? 'Ẩn dữ liệu kiểm thử' : `Hiện dữ liệu kiểm thử (${testDataCount})`}</button>}
          <input ref={importInputRef} type="file" hidden onChange={event => void handleImport(event)} />
          <button className="icon-button" type="button" onClick={() => importInputRef.current?.click()} disabled={importing} title="Nhập tệp vào Công việc">
            <Upload size={14} className={importing ? 'spin' : ''} />
          </button>
          <button className="icon-button" type="button" onClick={() => setCreateKind('file')} title="Tạo tệp văn bản"><FilePlus2 size={14} /></button>
          <button className="icon-button" type="button" onClick={() => setCreateKind('folder')} title="Tạo thư mục"><FolderPlus size={14} /></button>
          <button className="icon-button" type="button" onClick={() => void loadTree()} disabled={loading} title="Làm mới tài liệu">
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {createKind && (
        <form className="session-form" onSubmit={event => void handleCreate(event)} style={{ margin: '0.6rem' }}>
          <div className="section-header"><strong>{createKind === 'file' ? 'Tạo tệp văn bản' : 'Tạo thư mục'}</strong><button type="button" className="icon-button" title="Đóng" onClick={() => setCreateKind(null)}><X size={14} /></button></div>
          <input aria-label="Tên tài liệu mới" value={newItemName} onChange={event => setNewItemName(event.target.value)} placeholder={createKind === 'file' ? 'Ví dụ: ghi-chu.txt' : 'Ví dụ: Nguồn tham khảo'} />
          {createKind === 'file' && <textarea aria-label="Nội dung tệp mới" value={newFileContent} onChange={event => setNewFileContent(event.target.value)} rows={3} placeholder="Có thể để trống và sửa sau" />}
          <button className="btn-primary" disabled={creating || !newItemName.trim()}>{creating ? 'Đang tạo…' : 'Tạo'}</button>
        </form>
      )}

      <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem 0' }}>
        {error && <div className="inline-error" style={{ margin: '0.5rem 1rem' }}>{error}</div>}

        {visibleTree.length === 0 && !loading ? (
          <div className="empty-state">
            <div className="empty-state-title">Không gian làm việc đang trống</div>
            <div className="empty-state-text">Thêm tệp vào không gian làm việc rồi làm mới cây tệp.</div>
          </div>
        ) : (
          visibleTree.map(node => <FileTreeNode key={node.path} node={node} depth={0} onError={setError} />)
        )}

        {truncated && (
          <div style={{ padding: '0.5rem 1rem', color: '#f59e0b', fontSize: '0.8rem', fontStyle: 'italic' }}>
            Cây tệp đã được rút gọn do đạt giới hạn mục.
          </div>
        )}
      </div>
    </div>
  );
};
