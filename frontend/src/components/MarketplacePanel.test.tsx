import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as marketplaceApi from '../api/marketplace';
import { MarketplacePanel } from './MarketplacePanel';

vi.mock('../api/marketplace', () => ({
  getInstalledPlugins: vi.fn(), getMarketplaceCatalog: vi.fn(), installMarketplacePlugin: vi.fn(),
  rollbackMarketplacePlugin: vi.fn(), uninstallMarketplacePlugin: vi.fn(),
}));

describe('MarketplacePanel', () => {
  beforeEach(() => {
    vi.mocked(marketplaceApi.getMarketplaceCatalog).mockResolvedValue([{ package_id: 'pkg', version: '2', catalog_name: 'local', publisher: 'DIRAP', manifest: { name: 'Bộ công cụ', permissions: ['read_work'], network_domains: ['localhost'] }, package_hash: 'abc123', signature_valid: true }]);
    vi.mocked(marketplaceApi.getInstalledPlugins).mockResolvedValue([{ package_id: 'pkg', version: '1', catalog_name: 'local', manifest: { name: 'Bộ công cụ' }, install_state: 'cannot_run_safely', installed_at: 1, updated_at: 1 }]);
  });

  it('shows verified update and safe plugin details', async () => {
    render(<MarketplacePanel />);
    expect(await screen.findByText('Bộ công cụ')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Chi tiết' }));
    expect(screen.getByText('abc123')).toBeDefined();
    expect(screen.getByText('read_work')).toBeDefined();
    expect(screen.getByText('localhost')).toBeDefined();
    fireEvent.click(screen.getByRole('button', { name: 'Cập nhật (1)' }));
    expect(screen.getByText('v1 → v2')).toBeDefined();
  });
});
