import React, { Suspense, lazy, useState } from 'react';
import { GyoModelSettings } from '../foundation/settings/GyoModelSettings';
import { ModulesSettings } from '../foundation/settings/ModulesSettings';
import { useHermesStore } from '../store/store';

const LazyLocalDataPanel = lazy(() => import('./LocalDataPanel').then(module => ({ default: module.LocalDataPanel })));
const LazyMarketplacePanel = lazy(() => import('./MarketplacePanel').then(module => ({ default: module.MarketplacePanel })));
const LazyMemoryHubPanel = lazy(() => import('./MemoryHubPanel').then(module => ({ default: module.MemoryHubPanel })));
const LazyRuntimeStatusPanel = lazy(() => import('./RuntimeStatusPanel').then(module => ({ default: module.RuntimeStatusPanel })));

type Section = 'appearance' | 'modules' | 'model' | 'privacy' | 'memory-data' | 'backup' | 'advanced';

const sections: readonly { id: Section; label: string }[] = [
  { id: 'appearance', label: 'Giao diện & bố cục' },
  { id: 'modules', label: 'Modules' },
  { id: 'model', label: 'GYO & Models' },
  { id: 'privacy', label: 'Quyền Agent & Riêng tư' },
  { id: 'memory-data', label: 'Memory & Dữ liệu' },
  { id: 'backup', label: 'Backup & Lưu trữ' },
  { id: 'advanced', label: 'Nâng cao' },
] as const;

const settingsFallback = <div className="runtime-guidance" role="status">Đang tải khu vực cài đặt...</div>;

/** Foundation Settings control plane. */
export const SettingsPanel: React.FC = () => {
  const [section, setSection] = useState<Section>('model');
  const theme = useHermesStore(state => state.theme);
  const toggleTheme = useHermesStore(state => state.toggleTheme);

  return (
    <div className="grouped-panel" data-foundation-settings="true">
      <div className="grouped-panel-tabs" aria-label="Cài đặt ứng dụng">
        {sections.map(item => (
          <button
            key={item.id}
            className={section === item.id ? 'active' : ''}
            onClick={() => setSection(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="grouped-panel-body">
        {section === 'appearance' && (
          <section className="model-settings-panel" aria-labelledby="appearance-settings-title">
            <header>
              <h2 id="appearance-settings-title">Giao diện & bố cục</h2>
              <p>Foundation giữ bảng màu và bố cục ổn định; thay đổi ở đây chỉ dùng state giao diện đã tồn tại.</p>
            </header>
            <div className="gyo-settings-card">
              <strong>Chủ đề hiện tại</strong>
              <p className="muted-copy">{theme === 'dark' ? 'Tối' : 'Sáng'} · lựa chọn được lưu cục bộ như trước.</p>
              <button className="btn-secondary" type="button" onClick={toggleTheme}>
                Chuyển sang giao diện {theme === 'dark' ? 'sáng' : 'tối'}
              </button>
            </div>
          </section>
        )}

        {section === 'modules' && (
          <>
            <ModulesSettings />
            <div className="runtime-guidance">Marketplace vẫn giữ cơ chế fail-closed hiện hành. Cài package không đồng nghĩa package được phép chạy hoặc Module được gắn vào điều hướng.</div>
            <Suspense fallback={settingsFallback}><LazyMarketplacePanel /></Suspense>
          </>
        )}

        {section === 'model' && <GyoModelSettings />}

        {section === 'privacy' && (
          <section className="model-settings-panel" aria-labelledby="privacy-settings-title">
            <header>
              <h2 id="privacy-settings-title">Quyền Agent & Riêng tư</h2>
              <p>Các chính sách gửi dữ liệu ra dịch vụ ngoài sẽ chỉ xuất hiện khi backend thực sự hỗ trợ. Ứng dụng không tạo toggle giả hoặc ngầm nới quyền hiện hành.</p>
            </header>
            <div className="runtime-guidance">
              <strong>Boundary hiện hành</strong>
              <p>GYO không có quyền quản trị Foundation/Module. Work mutation vẫn phải qua Action Package, phê duyệt rõ ràng và executor idempotent.</p>
            </div>
          </section>
        )}

        {section === 'memory-data' && (
          <section className="model-settings-panel" aria-labelledby="memory-data-settings-title">
            <header>
              <h2 id="memory-data-settings-title">Memory & Dữ liệu người dùng</h2>
              <p>Memory GYO có lifecycle riêng và không được coi là source-of-truth của dữ liệu người dùng.</p>
            </header>
            <Suspense fallback={settingsFallback}><LazyMemoryHubPanel /></Suspense>
          </section>
        )}

        {section === 'backup' && (
          <section className="model-settings-panel" aria-labelledby="backup-settings-title">
            <header>
              <h2 id="backup-settings-title">Backup & Lưu trữ</h2>
              <p>Giữ nguyên capability backup hiện hành. Không mô tả DB-only backup là full workspace backup.</p>
            </header>
            <Suspense fallback={settingsFallback}><LazyLocalDataPanel /></Suspense>
          </section>
        )}

        {section === 'advanced' && (
          <>
            <div className="runtime-guidance">Khu vực này dành cho chẩn đoán runtime và kiểm tra kỹ thuật. Trạng thái “chưa xác định” không đồng nghĩa với “sẵn sàng”.</div>
            <Suspense fallback={settingsFallback}><LazyRuntimeStatusPanel /></Suspense>
          </>
        )}
      </div>
    </div>
  );
};
