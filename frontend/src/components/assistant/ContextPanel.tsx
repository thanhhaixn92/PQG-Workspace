import { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, FileText, Link, Search, X, ExternalLink, AlertCircle } from 'lucide-react';
import type { AssistantContextManifest } from '../../api/assistant';
import type { Artifact } from '../../api/artifacts';
import { ASSISTANT_NAME } from '../../branding';
import { openSafeUri, resolveSafeUri } from './contextUri';

export type ContextGroupKey = 'accessible' | 'retrieved' | 'used' | 'targeted' | 'excluded';

interface ContextItem {
  id: string;
  label: string;
  uri: string;
  kind?: string;
}

interface ContextPanelProps {
  manifest: AssistantContextManifest | null;
  artifacts: Artifact[];
  loading: boolean;
}

interface ContextGroupProps {
  label: string;
  key2: ContextGroupKey;
  items: ContextItem[];
  defaultOpen?: boolean;
  onOpen: (key: ContextGroupKey) => void;
  onClose: (key: ContextGroupKey) => void;
}

function ContextGroup({ label, key2, items, defaultOpen, onOpen, onClose }: ContextGroupProps) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  const handleToggle = () => {
    setOpen(o => !o);
    if (!open) onOpen(key2); else onClose(key2);
  };
  return (
    <div className="gyo-context-group">
      <button
        type="button"
        className="gyo-context-group-header"
        onClick={handleToggle}
        aria-expanded={open}
        aria-controls={`ctx-${key2}`}
      >
        <span>{label} <strong className="gyo-context-count">{items.length}</strong></span>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <ul id={`ctx-${key2}`} className="gyo-context-list">
          {items.length === 0 ? (
            <li className="gyo-context-empty">Không có mục nào trong nhóm này.</li>
          ) : items.map(item => {
            const resolved = resolveSafeUri(item.uri);
            const isExternal = resolved.safe && resolved.external;
            const isUnsafe = !resolved.safe;
            return (
              <li key={item.id} className="gyo-context-item">
                <FileText size={13} aria-hidden="true" />
                <span className="gyo-context-item-label" title={item.label}>{item.label || item.uri}</span>
                {item.kind && <span className="gyo-context-item-kind">{item.kind}</span>}
                {!isUnsafe && (
                  <button
                    type="button"
                    className="gyo-context-link"
                    onClick={() => openSafeUri(item.uri)}
                    aria-label={isExternal
                      ? `Mở bên ngoài: ${item.label || item.uri}`
                      : `Mở ${item.label || item.uri}`}
                  >
                    <Link size={12} />
                    {isExternal && <ExternalLink size={10} aria-hidden="true" />}
                  </button>
                )}
                {isUnsafe && (
                  <span className="gyo-context-item-kind" aria-label="Đường dẫn không an toàn" title="Đường dẫn không an toàn">
                    <AlertCircle size={12} />
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

const groupLabels: Record<ContextGroupKey, string> = {
  accessible: 'Có thể truy cập',
  retrieved: 'Đã truy xuất',
  used: 'Đã dùng',
  targeted: 'Mục tiêu',
  excluded: 'Đã loại trừ',
};

function parseManifestItems(manifest: AssistantContextManifest | null): Record<ContextGroupKey, ContextItem[]> {
  const result: Record<ContextGroupKey, ContextItem[]> = {
    accessible: [], retrieved: [], used: [], targeted: [], excluded: [],
  };
  if (!manifest) return result;

  // Provenance is server-owned. In particular, legacy `included` means only
  // a context-pack candidate and must never be presented as accessible,
  // retrieved, or used by GYO.
  const toItem = (entry: Record<string, unknown>, i: number): ContextItem => ({
    id: String(entry.id ?? entry.uri ?? entry.path ?? `${i}`),
    label: String(entry.title ?? entry.name ?? entry.label ?? entry.uri ?? entry.path ?? ''),
    uri: String(entry.uri ?? entry.path ?? ''),
    kind: typeof entry.kind === 'string' ? entry.kind : undefined,
  });

  result.excluded = Array.isArray(manifest.excluded)
    ? (manifest.excluded as Array<Record<string, unknown>>).map(toItem)
    : [];

  // Each server group is rendered only with its explicit semantic label.
  const raw = manifest as unknown as Record<string, unknown>;
  const accessibleCtx = raw.accessible;
  const retrievedCtx = raw.retrieved;
  const usedCtx = raw.used;
  const targetedCtx = raw.targeted;

  if (Array.isArray(retrievedCtx)) result.retrieved = (retrievedCtx as Array<Record<string, unknown>>).map(toItem);
  if (Array.isArray(usedCtx)) result.used = (usedCtx as Array<Record<string, unknown>>).map(toItem);
  if (Array.isArray(targetedCtx)) result.targeted = (targetedCtx as Array<Record<string, unknown>>).map(toItem);
  if (Array.isArray(accessibleCtx)) result.accessible = (accessibleCtx as Array<Record<string, unknown>>).map(toItem);

  return result;
}

export function ContextPanel({ manifest, artifacts, loading }: ContextPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [openGroups, setOpenGroups] = useState<Set<ContextGroupKey>>(
    new Set(['accessible', 'used', 'targeted', 'excluded'])
  );

  const groups = useMemo(() => parseManifestItems(manifest), [manifest]);

  const allItems = useMemo(() => {
    return (Object.keys(groups) as ContextGroupKey[]).flatMap(key =>
      groups[key].map(item => ({ ...item, key }))
    );
  }, [groups]);

  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return groups;
    const query = searchQuery.toLowerCase();
    const result: Record<ContextGroupKey, ContextItem[]> = {
      accessible: [], retrieved: [], used: [], targeted: [], excluded: [],
    };
    for (const groupKey of Object.keys(result) as ContextGroupKey[]) {
      result[groupKey] = groups[groupKey].filter(
        item => item.label.toLowerCase().includes(query) || item.uri.toLowerCase().includes(query)
      );
    }
    return result;
  }, [groups, searchQuery]);

  const openGroup = (key: ContextGroupKey) => setOpenGroups(s => new Set([...s, key]));
  const closeGroup = (key: ContextGroupKey) => setOpenGroups(s => { const n = new Set(s); n.delete(key); return n; });

  return (
    <section className="gyo-context-panel" aria-label="Ngữ cảnh làm việc">
      <div className="gyo-context-header">
        <h3>Ngữ cảnh cho {ASSISTANT_NAME}</h3>
        <div className="gyo-context-search">
          <Search size={14} aria-hidden="true" />
          <input
            type="search"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Tìm trong ngữ cảnh…"
            aria-label="Tìm trong ngữ cảnh"
          />
          {searchQuery && (
            <button type="button" onClick={() => setSearchQuery('')} aria-label="Xóa tìm kiếm">
              <X size={12} />
            </button>
          )}
        </div>
        <small className="gyo-context-meta">
          {artifacts.length} tệp · {allItems.length} mục ngữ cảnh
        </small>
      </div>
      {loading && <div className="gyo-context-loading">Đang tải ngữ cảnh…</div>}
      {!loading && (Object.values(filteredGroups).every(g => g.length === 0) && searchQuery && (
        <p className="gyo-context-empty">Không tìm thấy mục nào khớp với “{searchQuery}”.</p>
      ))}
      {!loading && (Object.keys(filteredGroups) as ContextGroupKey[]).map(key => {
        const items = filteredGroups[key];
        if (items.length === 0 && !searchQuery) return null;
        return (
          <ContextGroup
            key={key}
            key2={key}
            label={groupLabels[key]}
            items={items}
            defaultOpen={openGroups.has(key)}
            onOpen={openGroup}
            onClose={closeGroup}
          />
        );
      })}
    </section>
  );
}
