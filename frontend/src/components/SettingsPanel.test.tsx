import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as marketplaceApi from '../api/marketplace';
import { SettingsPanel } from './SettingsPanel';

vi.mock('../api/marketplace', () => ({
  getModelConfig: vi.fn(), createGyoProvider: vi.fn(), createGyoModel: vi.fn(),
  retireGyoModel: vi.fn(), retireGyoProvider: vi.fn(), setGyoProviderCredential: vi.fn(),
  updateGyoModel: vi.fn(), checkGyoProvider: vi.fn(), discoverGyoProviderModels: vi.fn(),
  importZenFreeModels: vi.fn(), installZenFreePreset: vi.fn(), updateGyoRoutingPolicy: vi.fn(),
}));

describe('SettingsPanel GYO provider controls', () => {
  beforeEach(() => {
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
});
