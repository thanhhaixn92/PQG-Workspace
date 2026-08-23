import React, { useState } from 'react';
import { getPrimaryModuleDefinitions } from '../foundation/modules/registry';
import { GyoModelSettings } from '../foundation/settings/GyoModelSettings';
import { useHermesStore } from '../store/store';
import { LocalDataPanel } from './LocalDataPanel';
import { MarketplacePanel } from './MarketplacePanel';
import { MemoryHubPanel } from './MemoryHubPanel';
import { RuntimeStatusPanel } from './RuntimeStatusPanel';

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

/**
 * Foundation Settings control plane.
 *
 * Wave 1 reorganizes existing Settings surfaces without inventing persistence or
 * privacy controls that the backend does not yet implement. Protected Module
 * lifecycle and Data Egress settings remain later gates.
 */
export const SettingsPanel: React.FC = () => {
  const [section, setSection] = useState<Section>('model');
  const theme = useHermesStore(state => state.theme);
  const toggleTheme = useHermesStore(state => state.toggleTheme);
  const primaryModules = getPrimaryModuleDefinitions();

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
              <p>Foundation giữ bảng màu và bố cục hiện hành trong Wave 1; thay đổi ở đây chỉ dùng state giao diện đã tồn tại.</p>
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
          <section className="model-settings-panel" aria-labelledby="module-settings-title">
            <header>
              <h2 id="module-settings-title">Modules</h2>
              <p>Wave 1 chỉ chuẩn hóa registry và khu vực quản lý. Attach/detach/rename/reorder bền vững sẽ chỉ được mở ở gate persistence có phê duyệt.</p>
            </header>
            <div className="gyo-settings-grid" aria-label="Modules hiện có">
              {primaryModules.map(module => (
                <article className="gyo-settings-card" key={module.id}>
                  <strong>{module.defaultLabel}</strong>
                  <p className="muted-copy">ID: {module.id} · route {module.path}</p>
                  <span className="status-badge ready">Có sẵn</span>
                </article>
              ))}
            </div>
            <div className="runtime-guidance">Marketplace vẫn giữ cơ chế fail-closed hiện hành. Cài package không đồng nghĩa package được phép chạy hoặc Module được attach.</div>
            <MarketplacePanel />
          </section>
        )}

        {section === 'model' && <GyoModelSettings />}

        {section === 'privacy' && (
          <section className="model-settings-panel" aria-labelledby="privacy-settings-title">
            <header>
              <h2 id="privacy-settings-title">Quyền Agent & Riêng tư</h2>
              <p>Khu vực này là điểm neo cho Data Egress và permission control sau này. Wave 1 không tạo toggle giả hoặc thay đổi security policy hiện hành.</p>
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
            <MemoryHubPanel />
          </section>
        )}

        {section === 'backup' && (
          <section className="model-settings-panel" aria-labelledby="backup-settings-title">
            <header>
              <h2 id="backup-settings-title">Backup & Lưu trữ</h2>
              <p>Giữ nguyên capability backup hiện hành. Không mô tả DB-only backup là full workspace backup.</p>
            </header>
            <LocalDataPanel />
          </section>
        )}

        {section === 'advanced' && (
          <>
            <div className="runtime-guidance">Khu vực này dành cho chẩn đoán runtime và kiểm tra kỹ thuật. Trạng thái “chưa xác định” không đồng nghĩa với “sẵn sàng”.</div>
            <RuntimeStatusPanel />
          </>
        )}
      </div>
    </div>
  );
};
