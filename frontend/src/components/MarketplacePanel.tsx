import React, { useEffect, useState } from 'react';
import { Download, PackageCheck, ShieldAlert } from 'lucide-react';
import { getInstalledPlugins, getMarketplaceCatalog, installMarketplacePlugin, rollbackMarketplacePlugin, uninstallMarketplacePlugin, type InstalledPlugin, type MarketplacePackage } from '../api/marketplace';

type MarketplaceSection = 'discover' | 'installed' | 'updates';
type Selection = { packageId: string; version: string } | null;

function manifestList(manifest: Record<string, unknown>, key: 'permissions' | 'domains'): string[] {
  const value = key === 'domains' ? (manifest.domains ?? manifest.network_domains) : manifest.permissions;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

export const MarketplacePanel: React.FC = () => {
  const [catalog, setCatalog] = useState<MarketplacePackage[]>([]);
  const [installed, setInstalled] = useState<InstalledPlugin[]>([]);
  const [section, setSection] = useState<MarketplaceSection>('discover');
  const [selection, setSelection] = useState<Selection>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const [packages, plugins] = await Promise.all([getMarketplaceCatalog(), getInstalledPlugins()]);
      setCatalog(packages); setInstalled(plugins); setError(null);
    } catch { setError('Chưa tải được Marketplace an toàn.'); }
  };
  useEffect(() => { void load(); }, []);

  const install = async (item: MarketplacePackage) => {
    setBusy(item.package_id);
    try { await installMarketplacePlugin(item.package_id, item.version); await load(); }
    catch { setError('Không cài được gói đã xác minh.'); }
    finally { setBusy(null); }
  };
  const rollback = async (item: InstalledPlugin) => {
    setBusy(item.package_id);
    try { await rollbackMarketplacePlugin(item.package_id); await load(); }
    catch { setError('Chưa thể quay lại phiên bản đã được xác minh.'); }
    finally { setBusy(null); }
  };
  const uninstall = async (item: InstalledPlugin) => {
    if (!window.confirm(`Gỡ “${String(item.manifest.name || item.package_id)}” khỏi Marketplace?`)) return;
    setBusy(item.package_id);
    try { await uninstallMarketplacePlugin(item.package_id); await load(); }
    catch { setError('Không gỡ được plugin này.'); }
    finally { setBusy(null); }
  };

  const latestByPackage = new Map<string, MarketplacePackage>();
  catalog.forEach(item => { if (!latestByPackage.has(item.package_id)) latestByPackage.set(item.package_id, item); });
  const updates = installed.flatMap(plugin => {
    const next = latestByPackage.get(plugin.package_id);
    if (next?.version === plugin.version) return [];
    return next ? [{ plugin, next }] : [];
  });
  const selectedCatalog = selection ? catalog.find(item => item.package_id === selection.packageId && item.version === selection.version) : undefined;
  const selectedInstalled = selection ? installed.find(item => item.package_id === selection.packageId) : undefined;
  const selectedManifest = selectedCatalog?.manifest ?? selectedInstalled?.manifest;
  const permissions = selectedManifest ? manifestList(selectedManifest, 'permissions') : [];
  const domains = selectedManifest ? manifestList(selectedManifest, 'domains') : [];

  return <section className="marketplace-panel">
    <header><div><h2>Marketplace năng lực</h2><p>Chỉ hiển thị package đã qua kiểm chứng. Plugin cài xong vẫn tắt cho đến khi có môi trường chạy cô lập an toàn.</p></div><ShieldAlert size={25} /></header>
    <nav className="grouped-panel-tabs" aria-label="Marketplace">
      <button className={section === 'discover' ? 'active' : ''} onClick={() => setSection('discover')}>Khám phá</button>
      <button className={section === 'installed' ? 'active' : ''} onClick={() => setSection('installed')}>Đã cài ({installed.length})</button>
      <button className={section === 'updates' ? 'active' : ''} onClick={() => setSection('updates')}>Cập nhật ({updates.length})</button>
    </nav>
    {error && <div className="inline-error" role="status">{error}</div>}
    {section === 'discover' && <div className="marketplace-list">{catalog.length === 0 ? <div className="empty-state"><div className="empty-state-title">Chưa có catalog đã xác minh</div><div className="empty-state-text">Marketplace không cài URL hoặc Git tùy ý. Cần catalog Hermes/DIRAP đã ký trước khi package xuất hiện ở đây.</div></div> : catalog.map(item => <article key={`${item.package_id}-${item.version}`}><div><strong>{String(item.manifest.name || item.package_id)}</strong><p>{String(item.manifest.description || 'Package đã xác minh')}</p><small>{item.publisher} · v{item.version} · Chữ ký hợp lệ</small></div><div className="marketplace-actions"><button className="btn-secondary compact-button" onClick={() => setSelection({ packageId: item.package_id, version: item.version })}>Chi tiết</button><button className="btn-primary compact-button" disabled={busy === item.package_id} onClick={() => void install(item)}><Download size={15} />Cài</button></div></article>)}</div>}
    {section === 'installed' && <div className="marketplace-list">{installed.length === 0 ? <div className="empty-state">Chưa có plugin nào được cài.</div> : installed.map(item => <article key={item.package_id}><div><strong>{String(item.manifest.name || item.package_id)}</strong><p>v{item.version} · {item.install_state === 'cannot_run_safely' ? 'Đang cách ly — không thể chạy an toàn' : item.install_state}</p><small>Không có secret, đường dẫn máy hoặc quyền ngầm được cấp cho plugin.</small></div><div className="marketplace-actions"><button className="btn-secondary compact-button" onClick={() => setSelection({ packageId: item.package_id, version: item.version })}>Chi tiết</button>{item.previous_version && <button className="btn-secondary compact-button" disabled={busy === item.package_id} onClick={() => void rollback(item)}>Quay lại v{item.previous_version}</button>}<button className="btn-secondary compact-button" disabled={busy === item.package_id} onClick={() => void uninstall(item)}><PackageCheck size={15} />Gỡ</button></div></article>)}</div>}
    {section === 'updates' && <div className="marketplace-list">{updates.length === 0 ? <div className="empty-state">Các plugin đã cài đều đang ở phiên bản mới nhất trong catalog đã xác minh.</div> : updates.map(({ plugin, next }) => <article key={plugin.package_id}><div><strong>{String(plugin.manifest.name || plugin.package_id)}</strong><p>v{plugin.version} → v{next.version}</p><small>Bản cập nhật đã có chữ ký hợp lệ; cài xong vẫn ở trạng thái tắt/cách ly.</small></div><button className="btn-primary compact-button" disabled={busy === plugin.package_id} onClick={() => void install(next)}>Cập nhật</button></article>)}</div>}
    {selection && selectedManifest && <aside className="runtime-guidance" role="region" aria-label="Chi tiết plugin">
      <div className="review-source-row"><strong>{String(selectedManifest.name || selection.packageId)}</strong><button className="btn-secondary compact-button" onClick={() => setSelection(null)}>Đóng</button></div>
      <dl>
        <div><dt>Publisher</dt><dd>{selectedCatalog?.publisher || 'Không có trong bản cài cục bộ'}</dd></div>
        <div><dt>Phiên bản</dt><dd>{selection.version}</dd></div>
        <div><dt>Package hash</dt><dd>{selectedCatalog?.package_hash || 'Không có trong bản cài cục bộ'}</dd></div>
        <div><dt>Chữ ký</dt><dd>{selectedCatalog ? (selectedCatalog.signature_valid ? 'Hợp lệ' : 'Không hợp lệ') : 'Không xác định từ bản cài'}</dd></div>
        <div><dt>Quyền yêu cầu</dt><dd>{permissions.length ? permissions.join(', ') : 'Không khai báo'}</dd></div>
        <div><dt>Domain được khai báo</dt><dd>{domains.length ? domains.join(', ') : 'Không khai báo'}</dd></div>
        <div><dt>Cách ly</dt><dd>{selectedInstalled?.install_state === 'cannot_run_safely' ? 'Đang cách ly, không được thực thi' : selectedInstalled ? selectedInstalled.install_state : 'Chưa cài'}</dd></div>
      </dl>
    </aside>}
  </section>;
};
