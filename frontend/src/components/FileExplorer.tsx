import React, { useEffect, useState } from 'react';
import { ChevronDown, ChevronRight, FileText, FileWarning, Folder, FolderOpen, RefreshCw } from 'lucide-react';
import { useHermesStore } from '../store/store';
import { fetchFileContent, fetchFileTree } from '../api/files';
import type { FileNode } from '../api/files';

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
      const file = await fetchFileContent(activeSessionId, node.path);
      openFile(node.path, file.content, { mtime: file.mtime, size: file.size });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'lỗi không xác định';
      onError(`Không đọc được tệp ${node.name}: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  const isActive = activeFile === node.path;

  return (
    <div>
      <div
        onClick={() => void handleClick()}
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
      </div>
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

export const FileExplorer: React.FC = () => {
  const { activeSessionId, fileTree, setFileTree } = useHermesStore();
  const [loading, setLoading] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTree = async () => {
    if (!activeSessionId) {
      return;
    }

    try {
      setError(null);
      setLoading(true);
      const res = await fetchFileTree(activeSessionId);
      setFileTree(res.tree);
      setTruncated(res.truncated);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'lỗi không xác định';
      setError(`Không tải được cây tệp: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTree();
  }, [activeSessionId]);

  if (!activeSessionId) {
    return (
      <div className="empty-state">
        <div className="empty-state-title">Chưa chọn không gian làm việc</div>
        <div className="empty-state-text">Tạo hoặc chọn một phiên trước khi duyệt tệp.</div>
      </div>
    );
  }

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
        <button
          onClick={() => void loadTree()}
          disabled={loading}
          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
        >
          <RefreshCw size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem 0' }}>
        {error && <div className="inline-error" style={{ margin: '0.5rem 1rem' }}>{error}</div>}

        {fileTree.length === 0 && !loading ? (
          <div className="empty-state">
            <div className="empty-state-title">Không gian làm việc đang trống</div>
            <div className="empty-state-text">Thêm tệp vào không gian làm việc rồi làm mới cây tệp.</div>
          </div>
        ) : (
          fileTree.map(node => <FileTreeNode key={node.path} node={node} depth={0} onError={setError} />)
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
