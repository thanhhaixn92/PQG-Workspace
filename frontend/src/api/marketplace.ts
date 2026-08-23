import { apiFetch } from './client';

export interface MarketplacePackage { package_id: string; version: string; catalog_name: string; publisher: string; manifest: Record<string, unknown>; package_hash: string; signature_valid: boolean }
export interface InstalledPlugin { package_id: string; version: string; catalog_name: string; manifest: Record<string, unknown>; install_state: string; previous_version?: string | null; installed_at: number; updated_at: number }
export type GyoProviderType = 'openai_responses' | 'openai_compatible';
export type GyoModelTier = 'fast' | 'balanced' | 'deep' | 'vision';
export type GyoCapability = 'chat' | 'vision' | 'tools';
export type GyoCostClass = 'free' | 'unknown' | 'may_charge';
export interface GyoProvider {
  id: string; display_name: string; provider_type: GyoProviderType; base_url?: string | null;
  enabled: boolean; retired_at?: number | null; credential_configured: boolean;
  health_status: 'ready' | 'needs_credential' | 'misconfigured' | 'unreachable' | 'unknown';
  health_message?: string | null; created_at: number; updated_at: number;
}
export interface GyoModel {
  id: string; provider_profile_id: string; display_name: string; model_identifier: string;
  tier: GyoModelTier; capabilities: GyoCapability[]; priority: number; enabled: boolean;
  is_default: boolean; retired_at?: number | null; created_at: number; updated_at: number;
  cost_class: GyoCostClass;
}
export interface GyoDiscoveredModel {
  model_identifier: string; display_name: string; tier: GyoModelTier; capabilities: GyoCapability[];
  is_free: true; availability: 'available';
}
export interface GyoProviderCatalog { provider_id: string; source: 'opencode_zen'; models: GyoDiscoveredModel[]; skipped_count: number; }
export interface GyoZenFreeImport { provider_id: string; models: GyoModel[]; unavailable_model_ids: string[]; }
export interface GyoRoutingPolicy { auto_fallback_enabled: boolean; max_fallback_attempts: 2; fallback_scope: 'all_enabled_models'; enabled_model_counts: Record<GyoCostClass, number>; }
export interface ModelConfig {
  provider?: string | null; model?: string | null; auth_ready?: boolean; mutable_from_browser?: boolean;
  guidance?: string; providers: GyoProvider[]; models: GyoModel[]; default_model_profile_id?: string | null;
  routing_policy?: GyoRoutingPolicy;
}
export interface CreateGyoProvider {
  display_name: string; provider_type: GyoProviderType; base_url?: string; api_key?: string;
}
export interface CreateGyoModel {
  provider_profile_id: string; display_name: string; model_identifier: string; tier: GyoModelTier;
  capabilities: GyoCapability[]; priority: number; make_default?: boolean;
}
export const getMarketplaceCatalog = () => apiFetch<MarketplacePackage[]>('/api/marketplace/catalog');
export const getInstalledPlugins = () => apiFetch<InstalledPlugin[]>('/api/marketplace/installed');
export const installMarketplacePlugin = (packageId: string, version: string) => apiFetch<InstalledPlugin>(`/api/marketplace/${encodeURIComponent(packageId)}/${encodeURIComponent(version)}/install`, { method: 'POST' });
export const rollbackMarketplacePlugin = (packageId: string) => apiFetch<InstalledPlugin>(`/api/marketplace/${encodeURIComponent(packageId)}/rollback`, { method: 'POST' });
export const uninstallMarketplacePlugin = (packageId: string) => apiFetch<InstalledPlugin>(`/api/marketplace/${encodeURIComponent(packageId)}/uninstall`, { method: 'POST' });
export const getModelConfig = () => apiFetch<ModelConfig>('/api/model-config');
export const createGyoProvider = (value: CreateGyoProvider) => apiFetch<GyoProvider>('/api/model-config/providers', { method: 'POST', body: JSON.stringify(value) });
export const updateGyoProvider = (id: string, value: Partial<Pick<GyoProvider, 'display_name' | 'base_url' | 'enabled'>>) => apiFetch<GyoProvider>(`/api/model-config/providers/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(value) });
export const setGyoProviderCredential = (id: string, apiKey: string) => apiFetch<GyoProvider>(`/api/model-config/providers/${encodeURIComponent(id)}/credential`, { method: 'POST', body: JSON.stringify({ api_key: apiKey }) });
export const checkGyoProvider = (id: string) => apiFetch<{ provider_id: string; status: GyoProvider['health_status']; message: string }>(`/api/model-config/providers/${encodeURIComponent(id)}/health`, { method: 'POST' });
export const discoverGyoProviderModels = (id: string) => apiFetch<GyoProviderCatalog>(`/api/model-config/providers/${encodeURIComponent(id)}/models/discover`, { method: 'POST' });
export const installZenFreePreset = (id: string) => apiFetch<GyoZenFreeImport>(`/api/model-config/providers/${encodeURIComponent(id)}/models/zen-free-preset`, { method: 'POST' });
export const importZenFreeModels = (id: string, modelIdentifiers: string[]) => apiFetch<GyoZenFreeImport>(`/api/model-config/providers/${encodeURIComponent(id)}/models/zen-free-import`, { method: 'POST', body: JSON.stringify({ model_identifiers: modelIdentifiers }) });
export const updateGyoRoutingPolicy = (autoFallbackEnabled: boolean) => apiFetch<GyoRoutingPolicy>('/api/model-config/routing-policy', { method: 'PUT', body: JSON.stringify({ auto_fallback_enabled: autoFallbackEnabled }) });
export const retireGyoProvider = (id: string) => apiFetch<GyoProvider>(`/api/model-config/providers/${encodeURIComponent(id)}/retire`, { method: 'POST' });
export const createGyoModel = (value: CreateGyoModel) => apiFetch<GyoModel>('/api/model-config/models', { method: 'POST', body: JSON.stringify(value) });
export const updateGyoModel = (id: string, value: Partial<Pick<GyoModel, 'display_name' | 'tier' | 'capabilities' | 'priority' | 'enabled' | 'is_default'>> & { make_default?: boolean }) => apiFetch<GyoModel>(`/api/model-config/models/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(value) });
export const retireGyoModel = (id: string) => apiFetch<GyoModel>(`/api/model-config/models/${encodeURIComponent(id)}/retire`, { method: 'POST' });
