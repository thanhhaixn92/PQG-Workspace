import React, { Suspense, useMemo, useState } from 'react';
import { Clipboard, ExternalLink, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchFileContent } from '../api/files';
import { useHermesStore } from '../store/store';

const MermaidDiagram = React.lazy(() =>
  import('./MermaidDiagram').then(module => ({ default: module.MermaidDiagram })),
);

interface MarkdownRendererProps {
  content: string;
}

interface DesktopLocalFile {
  localPath: string;
  fileName?: string;
  contentQuality?: {
    status: string;
    label: string;
    issues?: string[];
    file_path?: string;
    checked_at?: number;
  };
}

interface CodeBlock {
  className?: string;
  language?: string;
  content: string;
}

function parseDesktopLocalFile(value: string): DesktopLocalFile | null {
  try {
    const parsed = JSON.parse(value.trim()) as Partial<DesktopLocalFile>;
    if (typeof parsed.localPath === 'string' && parsed.localPath.trim()) {
      return {
        localPath: parsed.localPath,
        fileName: typeof parsed.fileName === 'string' ? parsed.fileName : parsed.localPath.split(/[\\/]/).pop(),
        contentQuality: parsed.contentQuality && typeof parsed.contentQuality === 'object'
          ? parsed.contentQuality as DesktopLocalFile['contentQuality']
          : undefined,
      };
    }
  } catch {
    return null;
  }

  return null;
}

function extractCodeBlock(children: React.ReactNode): CodeBlock | null {
  const child = React.Children.toArray(children)[0];
  if (!React.isValidElement<{ className?: string; children?: React.ReactNode }>(child)) {
    return null;
  }

  const className = child.props.className || '';
  const language = /language-([^\s]+)/.exec(className)?.[1];
  const content = String(child.props.children ?? '').replace(/\n$/, '');

  return { className, language, content };
}

const normalizeLocalPath = (value: string) => value.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase();

const toWorkspaceRelativePath = (localPath: string, workspacePath?: string): string | null => {
  if (!workspacePath) {
    return null;
  }

  const normalizedFile = normalizeLocalPath(localPath);
  const normalizedWorkspace = normalizeLocalPath(workspacePath);
  if (normalizedFile === normalizedWorkspace || !normalizedFile.startsWith(`${normalizedWorkspace}/`)) {
    return null;
  }

  return localPath.slice(workspacePath.length).replace(/^[\\/]+/, '').replace(/\\/g, '/');
};

const binaryExtensions = new Set([
  '.doc',
  '.docx',
  '.pdf',
  '.xlsx',
  '.xls',
  '.pptx',
  '.ppt',
  '.png',
  '.jpg',
  '.jpeg',
  '.gif',
  '.webp',
  '.zip',
  '.7z',
]);

const isLikelyBinary = (fileName?: string) => {
  const lowerName = (fileName || '').toLowerCase();
  return [...binaryExtensions].some(extension => lowerName.endsWith(extension));
};

const DesktopFileCard: React.FC<{ file: DesktopLocalFile }> = ({ file }) => {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);
  const activeSessionId = useHermesStore(state => state.activeSessionId);
  const activeSession = useHermesStore(state => state.sessions.find(session => session.id === state.activeSessionId));
  const openFile = useHermesStore(state => state.openFile);
  const setSidebarTab = useHermesStore(state => state.setSidebarTab);
  const relativePath = useMemo(
    () => toWorkspaceRelativePath(file.localPath, activeSession?.workspace_path),
    [activeSession?.workspace_path, file.localPath],
  );
  const fileName = file.fileName || file.localPath.split(/[\\/]/).pop() || 'Tệp đầu ra';
  const canOpenInWorkspace = Boolean(activeSessionId && relativePath && !isLikelyBinary(fileName));
  const quality = file.contentQuality;

  const copyPath = async () => {
    try {
      await navigator.clipboard?.writeText(file.localPath);
      setCopied(true);
      setCopyError(false);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
      setCopyError(true);
    }
  };

  const openInWorkspace = async () => {
    if (!activeSessionId || !relativePath) {
      return;
    }

    try {
      setOpenError(null);
      const fileContent = await fetchFileContent(activeSessionId, relativePath);
      openFile(relativePath, fileContent.content, { mtime: fileContent.mtime, size: fileContent.size });
      setSidebarTab('files');
    } catch {
      setOpenError('Không mở được tệp trong tab Tệp. Hãy copy đường dẫn hoặc làm mới cây tệp rồi thử lại.');
    }
  };

  return (
    <div className="desktop-file-card">
      <div className="desktop-file-icon">
        <FileText size={18} />
      </div>
      <div className="desktop-file-body">
        <div className="desktop-file-title-row">
          <div className="desktop-file-title">{fileName}</div>
          <span className={`desktop-file-badge ${relativePath ? 'inside' : 'outside'}`}>
            {relativePath ? 'Trong workspace' : 'Ngoài workspace'}
          </span>
          {quality?.label && (
            <span className={`desktop-file-badge ${quality.status === 'usable' ? 'inside' : 'outside'}`}>
              {quality.label}
            </span>
          )}
        </div>
        <div className="desktop-file-path">{file.localPath}</div>
        <div className="desktop-file-hint">
          {isLikelyBinary(fileName)
            ? 'File này nên mở bằng Microsoft Word hoặc ứng dụng phù hợp. Webapp không mở file nhị phân trong editor text.'
            : relativePath
              ? 'Có thể mở bằng tab Tệp trong workspace hoặc copy đường dẫn để dùng bên ngoài.'
              : 'File nằm ngoài workspace hiện tại, chỉ nên copy đường dẫn và kiểm tra thủ công.'}
        </div>
        {copyError && (
          <div className="desktop-file-error">Không copy được, hãy bôi đen đường dẫn để copy thủ công.</div>
        )}
        {quality?.issues && quality.issues.length > 0 && (
          <>
            <div className="desktop-file-error">
              {quality.issues.slice(0, 3).join(' ')}
            </div>
            {quality.status !== 'usable' && (
              <div className="desktop-file-error">Nên rà soát trước khi đăng/xuất bản.</div>
            )}
          </>
        )}
        {openError && <div className="desktop-file-error">{openError}</div>}
      </div>
      <div className="desktop-file-actions">
        {canOpenInWorkspace && (
          <button type="button" className="btn-secondary compact-button" onClick={() => void openInWorkspace()}>
            <ExternalLink size={13} /> Mở trong tab Tệp
          </button>
        )}
        <button type="button" className="btn-secondary compact-button" onClick={copyPath}>
          <Clipboard size={13} /> {copied ? 'Đã copy' : 'Copy đường dẫn'}
        </button>
      </div>
    </div>
  );
};

const markdownComponents: Components = {
  pre({ children }) {
    const codeBlock = extractCodeBlock(children);
    if (!codeBlock) {
      return <pre className="markdown-pre">{children}</pre>;
    }

    if (codeBlock.language === 'desktop-local-file') {
      const desktopFile = parseDesktopLocalFile(codeBlock.content);
      if (desktopFile) {
        return <DesktopFileCard file={desktopFile} />;
      }
    }

    if (codeBlock.language === 'mermaid') {
      return (
        <Suspense fallback={<div className="runtime-guidance">Đang tải sơ đồ...</div>}>
          <MermaidDiagram content={codeBlock.content} />
        </Suspense>
      );
    }

    return (
      <pre className="markdown-pre">
        <code className={codeBlock.className}>{codeBlock.content}</code>
      </pre>
    );
  },
  code({ className, children, ...props }) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
};

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={markdownComponents}
    >
      {content}
    </ReactMarkdown>
  );
};
