import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as marketplaceApi from '../api/marketplace';
import type { ModuleInstance } from '../api/modules';
import { useModuleProjectionStore } from '../foundation/modules/store';
import { useHermesStore } from '../store/store';
import { SettingsPanel } from './SettingsPanel';

vi.mock('../api/marketplace', () => ({
  getModelConfig: vi.fn(), createGyoProvider: vi.fn(), createGyoModel: vi.fn(),
  retireGyoModel: vi.fn(), retireGyoProvider: vi.fn(), setGyoProviderCredential: vi.fn(),
  updateGyoModel: vi.fn(), checkGyoProvider: vi.fn(), discoverGyoProviderModels: vi.fn(),
  importZenFreeModels: vi.fn(), installZenFreePreset: vi.fn(), updateGyoRoutingPolicy: vi.fn(),
}));

vi.mock('./MarketplacePanel', () => ({ MarketplacePanel: () => <div>Marketplace content</div> }));
vi.mock('./MemoryHubPanel', () => ({ MemoryHubPanel: () => <div>Memory Hub content</div> }));
vi.mock('./LocalDataPanel', () => ({ LocalDataPanel: () => <div>Local data content</div> }));
vi.mock('./RuntimeStatusPanel', () => ({ RuntimeStatusPanel: () => <div>Runtime diagnostics</div> }));

const moduleInstance = (moduleId: string, displayName: string, attached: boolean, sortOrder: number): ModuleInstance => ({
  id: `builtin:${moduleId}`,
  module_id: moduleId,
  source_kind: 'builtin',
  package_id: null,
  display_name: displayName,
  attached,
  sort_order: sortOrder,
  config: {},
  config_version: 1,
  health_state: 'ready',
  revision: 1,
  created_at: 1,
  updated_at: 1,
});

describe('SettingsPanel GYO provider controls', () => {
  beforeEach(() => {
    window.localStorage.clear();
    useHermesStore.setState({ theme: 'dark' });
    useModuleProjectionStore.setState({
      status: 'ready',
      error: null,
      instances: [
        moduleInstance('work', 'Công việc', true, 10),
        moduleInstance('documents', 'Tài liệu', false, 20),
        moduleInstance('knowledge', 'Thư viện', true, 30),
        moduleInstance('review', 'Hộp duyệt', true, 40),
        moduleInstance('reports', 'Báo cáo', true, 50),
      ],
    });
    vi.mocked(marketplaceApi.getModelConfig).mockResolvedValue({
      provider: null, model: null, auth_ready: false, mutable_from_browser: true,
      guidance: 'Chưa có model GYO mặc định.', providers: [], models: [], default_model_profile_id: null,
      routing_policy: { auto_fallback_enabled: false, max_fallback_attempts: 2, fallback_scope: 'all_enabled_models', enabled_model_counts: { free: 0, unknown: 0, may_charge: 0 } },
    });
  });

  it('manages GYO models without presenting a Hermes login or stored API key', async () => {
    render(<SettingsPanel />);
    expect(await screen.findByRole('heading', { name: 'Bộ não của Trợ lý GYO' })).toBeDefined();
    expect(screen.getByText('Chưa có provider GYO')).toBeDefined();
    expect((screen.getByLabelText('Khóa API (chỉ gửi một lần)') as HTMLInputElement).type).toBe('password');
    expect(screen.queryByText(/hermes auth/i)).toBeNull();
  });

  it('loads only explicit Zen free catalog entries and requires an opt-in import', async () => {
    vi.mocked(marketplaceApi.getModelConfig).mockResolvedValue({
      provider: null, model: null, auth_ready: false, mutable_from_browser: true, guidance: 'x', default_model_profile_id: null,
      models: [], providers: [{ id: 'zen', display_name: 'Zen', provider_type: 'openai_compatible', base_url: 'https://opencode.ai/zen/v1', enabled: true, retired_at: null, credential_configured: true, health_status: 'ready', health_message: 'ready', created_at: 1, updated_at: 1 }],
      routing_policy: { auto_fallback_enabled: false, max_fallback_attempts: 2, fallback_scope: 'all_enabled_models', enabled_model_counts: { free: 0, unknown: 0, may_charge: 0 } },
    });
    vi.mocked(marketplaceApi.discoverGyoProviderModels).mockResolvedValue({ provider_id: 'zen', source: 'opencode_zen', skipped_count: 2, models: [{ model_identifier: 'deepseek-v4-flash-free', display_name: 'DeepSeek V4 Flash Free', tier: 'fast', capabilities: ['chat'], is_free: true, availability: 'available' }] });
    render(<SettingsPanel />);
    expect(await screen.findByRole('button', { name: 'Dùng bộ model miễn phí gợi ý' })).toBeDefined();
    const loadButton = await screen.findByRole('button', { name: 'Cập nhật danh mục miễn phí' });
    fireEvent.click(loadButton);
    await screen.findByRole('button', { name: 'Thêm lựa chọn miễn phí' });
    expect(screen.getByText('DeepSeek V4 Flash Free')).toBeDefined();
    expect((screen.getByRole('button', { name: 'Thêm lựa chọn miễn phí' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('exposes the seven Foundation settings sections', () => {
    render(<SettingsPanel />);
    expect(screen.getByRole('button', { name: 'Giao diện & bố cục' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Modules' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'GYO & Models' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Quyền Agent & Riêng tư' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Memory & Dữ liệu' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Backup & Lưu trữ' })).toBeDefined();
    expect(screen.getByRole('button', { name: 'Nâng cao' })).toBeDefined();
  });

  it('exposes persistent Module controls only inside the user Settings control plane', async () => {
    render(<SettingsPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Modules' }));
    expect(screen.getByRole('heading', { name: 'Modules' })).toBeDefined();
    expect(screen.getByText('Công việc')).toBeDefined();
    expect(screen.getByText('Tài liệu')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Gắn vào điều hướng' })).toBeDefined();
    expect(screen.getAllByRole('button', { name: 'Tháo khỏi điều hướng' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /xóa|delete|uninstall/i })).toBeNull();
    expect(await screen.findByText('Marketplace content')).toBeDefined();
  });

  it('loads optional storage panels only after their settings sections are selected', async () => {
    render(<SettingsPanel />);
    expect(screen.queryByText('Memory Hub content')).toBeNull();
    expect(screen.queryByText('Local data content')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Memory & Dữ liệu' }));
    expect(await screen.findByText('Memory Hub content')).toBeDefined();

    fireEvent.click(screen.getByRole('button', { name: 'Backup & Lưu trữ' }));
    expect(await screen.findByText('Local data content')).toBeDefined();
  });

  it('keeps privacy read-only until the Data Egress gate is implemented', () => {
    render(<SettingsPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Quyền Agent & Riêng tư' }));
    expect(screen.getByText(/không tạo toggle giả/i)).toBeDefined();
    expect(screen.getByText(/GYO không có quyền quản trị Foundation\/Module/)).toBeDefined();
  });

  it('reuses the existing theme preference instead of creating a second settings store', () => {
    render(<SettingsPanel />);
    fireEvent.click(screen.getByRole('button', { name: 'Giao diện & bố cục' }));
    fireEvent.click(screen.getByRole('button', { name: 'Chuyển sang giao diện sáng' }));
    expect(useHermesStore.getState().theme).toBe('light');
    expect(window.localStorage.getItem('hermes.theme')).toBe('light');
  });
});
