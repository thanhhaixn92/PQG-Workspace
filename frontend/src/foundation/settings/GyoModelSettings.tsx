import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  checkGyoProvider,
  createGyoModel,
  createGyoProvider,
  discoverGyoProviderModels,
  getModelConfig,
  importZenFreeModels,
  installZenFreePreset,
  retireGyoModel,
  retireGyoProvider,
  setGyoProviderCredential,
  updateGyoModel,
  updateGyoRoutingPolicy,
  type GyoCostClass,
  type GyoModelTier,
  type GyoProviderCatalog,
  type GyoProviderType,
  type ModelConfig,
} from '../../api/marketplace';

type ProviderForm = { display_name: string; provider_type: GyoProviderType; base_url: string; api_key: string };
type ModelForm = { provider_profile_id: string; display_name: string; model_identifier: string; tier: GyoModelTier };

const initialProvider: ProviderForm = { display_name: '', provider_type: 'openai_responses', base_url: '', api_key: '' };
const costLabel: Record<GyoCostClass, string> = { free: 'Miễn phí', unknown: 'Chi phí chưa rõ', may_charge: 'Có thể tính phí' };

/** Existing provider/model behaviour extracted from the legacy SettingsPanel. */
export function GyoModelSettings() {
  const [model, setModel] = useState<ModelConfig | null>(null);
  const [providerForm, setProviderForm] = useState<ProviderForm>(initialProvider);
  const [modelForm, setModelForm] = useState<ModelForm>({ provider_profile_id: '', display_name: '', model_identifier: '', tier: 'balanced' });
  const [credentialInputs, setCredentialInputs] = useState<Record<string, string>>({});
  const [catalogs, setCatalogs] = useState<Record<string, GyoProviderCatalog>>({});
  const [catalogSelections, setCatalogSelections] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const reload = useCallback(async () => {
    const config = await getModelConfig();
    setModel(config);
    return config;
  }, []);

  useEffect(() => {
    void reload().catch(() => setMessage('Chưa tải được cấu hình GYO. Bạn có thể thử lại.'));
  }, [reload]);

  const activeProviders = useMemo(
    () => (model?.providers ?? []).filter(item => item.enabled && !item.retired_at),
    [model?.providers],
  );

  const perform = async (key: string, action: () => Promise<unknown>, success: string) => {
    setBusy(key);
    setMessage(null);
    try {
      await action();
      await reload();
      setMessage(success);
    } catch {
      setMessage('Không thể lưu cấu hình. Không có thay đổi nào được xác nhận; hãy kiểm tra lại và thử lại.');
    } finally {
      setBusy(null);
    }
  };

  const addProvider = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!providerForm.display_name.trim()) return;
    await perform('add-provider', () => createGyoProvider({
      display_name: providerForm.display_name.trim(),
      provider_type: providerForm.provider_type,
      ...(providerForm.base_url.trim() ? { base_url: providerForm.base_url.trim() } : {}),
      ...(providerForm.api_key ? { api_key: providerForm.api_key } : {}),
    }), 'Đã thêm provider GYO. Khóa chỉ được chuyển một lần để lưu cục bộ.');
    setProviderForm(initialProvider);
  };

  const addModel = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!modelForm.provider_profile_id || !modelForm.display_name.trim() || !modelForm.model_identifier.trim()) return;
    await perform('add-model', () => createGyoModel({
      provider_profile_id: modelForm.provider_profile_id,
      display_name: modelForm.display_name.trim(),
      model_identifier: modelForm.model_identifier.trim(),
      tier: modelForm.tier,
      capabilities: modelForm.tier === 'vision' ? ['chat', 'vision'] : ['chat'],
      priority: 100,
      make_default: !(model?.models ?? []).some(item => item.is_default && item.enabled && !item.retired_at),
    }), 'Đã thêm model. Bạn có thể dùng Tự động hoặc chọn tay khi trao đổi.');
    setModelForm(current => ({ ...current, display_name: '', model_identifier: '' }));
  };

  const loadCatalog = async (providerId: string) => {
    setBusy(`catalog-${providerId}`);
    setMessage(null);
    try {
      const catalog = await discoverGyoProviderModels(providerId);
      setCatalogs(current => ({ ...current, [providerId]: catalog }));
      setCatalogSelections(current => ({ ...current, [providerId]: [] }));
      setMessage(`Đã tải ${catalog.models.length} model miễn phí và tương thích. Model chỉ được thêm khi bạn chọn.`);
    } catch {
      setMessage('Không tải được catalog. Kiểm tra khóa OpenCode Zen, base URL và kết nối rồi thử lại.');
    } finally {
      setBusy(null);
    }
  };

  const toggleCatalogModel = (providerId: string, modelId: string) => setCatalogSelections(current => {
    const selected = current[providerId] ?? [];
    return { ...current, [providerId]: selected.includes(modelId) ? selected.filter(item => item !== modelId) : [...selected, modelId] };
  });

  const importCatalogModels = async (providerId: string) => {
    const catalog = catalogs[providerId];
    const selected = new Set(catalogSelections[providerId] ?? []);
    const choices = (catalog?.models ?? []).filter(item => selected.has(item.model_identifier));
    if (!choices.length) return;
    setBusy(`import-${providerId}`);
    setMessage(null);
    try {
      await importZenFreeModels(providerId, choices.map(item => item.model_identifier));
      await reload();
      setCatalogSelections(current => ({ ...current, [providerId]: [] }));
      setMessage(`Đã thêm ${choices.length} model miễn phí. Dùng Bật/Tắt để quyết định model xuất hiện trong lựa chọn GYO.`);
    } catch {
      setMessage('Không thể thêm các model Zen Free đã chọn. Không có thay đổi một phần được xác nhận; hãy tải lại và thử lại.');
      await reload();
    } finally {
      setBusy(null);
    }
  };

  const applyZenFreePreset = async (providerId: string) => {
    await perform(`preset-${providerId}`, () => installZenFreePreset(providerId), 'Đã bật bộ Zen Free gợi ý: nhanh, cân bằng và chuyên sâu.');
  };

  return (
    <section className="model-settings-panel" aria-labelledby="gyo-model-title">
      <header>
        <h2 id="gyo-model-title">Bộ não của Trợ lý GYO</h2>
        <p>GYO chỉ dùng provider và model bạn bật. Tự động chọn theo độ dài, tệp đính kèm và loại tác vụ; mỗi lượt vẫn lưu model đã dùng.</p>
      </header>

      {message && <div className="inline-note" role="status">{message}<button className="btn-secondary compact-button" onClick={() => void reload()}>Làm mới</button></div>}
      <dl>
        <div><dt>Provider sẵn sàng</dt><dd>{activeProviders.filter(item => item.health_status === 'ready').length}</dd></div>
        <div><dt>Model đang bật</dt><dd>{(model?.models ?? []).filter(item => item.enabled && !item.retired_at).length}</dd></div>
        <div><dt>Model mặc định</dt><dd>{model?.model || 'Chưa chọn'}</dd></div>
      </dl>
      <p className="muted-copy">Khóa API không được trả về, lưu trong ứng dụng hay hiển thị lại. Ngừng dùng model/provider không làm mất provenance của lịch sử cũ.</p>

      <section className="gyo-routing-policy" aria-label="Fallback model">
        <div>
          <strong>Fallback khi lỗi tạm thời</strong>
          <small>Khi bật, GYO chỉ thử tối đa 2 model dự phòng trước token đầu tiên. Có thể dùng mọi model đang bật: {model?.routing_policy?.enabled_model_counts.free ?? 0} miễn phí, {model?.routing_policy?.enabled_model_counts.unknown ?? 0} chưa rõ chi phí, {model?.routing_policy?.enabled_model_counts.may_charge ?? 0} có thể tính phí.</small>
        </div>
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={model?.routing_policy?.auto_fallback_enabled ?? false}
            disabled={!model || busy === 'routing-policy'}
            onChange={event => void perform('routing-policy', () => updateGyoRoutingPolicy(event.target.checked), event.target.checked ? 'Đã bật fallback tối đa hai model dự phòng.' : 'Đã tắt fallback tự động.')}
          /> Bật fallback
        </label>
      </section>

      <details className="gyo-settings-advanced">
        <summary>Nâng cao: thêm provider hoặc Model ID thủ công</summary>
        <div className="gyo-settings-grid">
          <form className="gyo-settings-card" onSubmit={event => void addProvider(event)}>
            <h3>Thêm provider</h3>
            <label>Tên hiển thị<input value={providerForm.display_name} onChange={event => setProviderForm(current => ({ ...current, display_name: event.target.value }))} required maxLength={100} /></label>
            <label>Loại kết nối<select value={providerForm.provider_type} onChange={event => setProviderForm(current => ({ ...current, provider_type: event.target.value as GyoProviderType }))}><option value="openai_responses">OpenAI Responses</option><option value="openai_compatible">OpenAI-compatible</option></select></label>
            <label>Base URL {providerForm.provider_type === 'openai_compatible' ? '(bắt buộc)' : '(tuỳ chọn)'}<input value={providerForm.base_url} onChange={event => setProviderForm(current => ({ ...current, base_url: event.target.value }))} required={providerForm.provider_type === 'openai_compatible'} placeholder={providerForm.provider_type === 'openai_compatible' ? 'https://…/v1' : 'https://api.openai.com/v1'} /></label>
            <label>Khóa API (chỉ gửi một lần)<input type="password" autoComplete="new-password" value={providerForm.api_key} onChange={event => setProviderForm(current => ({ ...current, api_key: event.target.value }))} /></label>
            <button className="btn-primary" disabled={busy === 'add-provider'}>{busy === 'add-provider' ? 'Đang thêm…' : 'Thêm provider'}</button>
          </form>

          <form className="gyo-settings-card" onSubmit={event => void addModel(event)}>
            <h3>Thêm model</h3>
            <label>Provider<select value={modelForm.provider_profile_id} onChange={event => setModelForm(current => ({ ...current, provider_profile_id: event.target.value }))} required><option value="">Chọn provider</option>{activeProviders.map(item => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
            <label>Tên hiển thị<input value={modelForm.display_name} onChange={event => setModelForm(current => ({ ...current, display_name: event.target.value }))} required maxLength={100} /></label>
            <label>Model ID<input value={modelForm.model_identifier} onChange={event => setModelForm(current => ({ ...current, model_identifier: event.target.value }))} required maxLength={200} placeholder="model-name" /></label>
            <label>Nhóm năng lực<select value={modelForm.tier} onChange={event => setModelForm(current => ({ ...current, tier: event.target.value as GyoModelTier }))}><option value="fast">Nhanh</option><option value="balanced">Cân bằng</option><option value="deep">Chuyên sâu</option><option value="vision">Đọc ảnh</option></select></label>
            <button className="btn-primary" disabled={busy === 'add-model' || !activeProviders.length}>{busy === 'add-model' ? 'Đang thêm…' : 'Thêm model'}</button>
          </form>
        </div>
      </details>

      <div className="gyo-profile-list" aria-label="Provider và model GYO">
        {(model?.providers ?? []).filter(provider => !provider.retired_at).map(provider => <article key={provider.id}>
          <header>
            <div><strong>{provider.display_name}</strong><small>{provider.provider_type} · {provider.health_message || provider.health_status}</small></div>
            <span className={`status-badge ${provider.health_status}`}>{provider.health_status === 'ready' ? 'Sẵn sàng' : provider.health_status === 'needs_credential' ? 'Cần khóa' : 'Cần kiểm tra'}</span>
          </header>
          <div className="gyo-profile-actions">
            <input type="password" aria-label={`Khóa API cho ${provider.display_name}`} autoComplete="new-password" value={credentialInputs[provider.id] ?? ''} onChange={event => setCredentialInputs(current => ({ ...current, [provider.id]: event.target.value }))} placeholder={provider.credential_configured ? 'Thay khóa API' : 'Nhập khóa API'} />
            <button className="btn-secondary compact-button" disabled={!credentialInputs[provider.id] || busy === `credential-${provider.id}`} onClick={() => void perform(`credential-${provider.id}`, async () => { await setGyoProviderCredential(provider.id, credentialInputs[provider.id]); setCredentialInputs(current => ({ ...current, [provider.id]: '' })); }, 'Đã cập nhật khóa cục bộ.')}>Lưu khóa</button>
            <button className="btn-secondary compact-button" disabled={busy === `health-${provider.id}`} onClick={() => void perform(`health-${provider.id}`, () => checkGyoProvider(provider.id), 'Đã kiểm tra cấu hình provider.')}>Kiểm tra</button>
            {(provider.base_url || '').replace(/\/$/, '') === 'https://opencode.ai/zen/v1' && <button className="btn-secondary compact-button" disabled={!provider.credential_configured || busy === `catalog-${provider.id}`} onClick={() => void loadCatalog(provider.id)}>{busy === `catalog-${provider.id}` ? 'Đang tải…' : 'Cập nhật danh mục miễn phí'}</button>}
            <button className="btn-secondary compact-button" disabled={busy === `retire-provider-${provider.id}`} onClick={() => { if (window.confirm(`Ngừng dùng provider “${provider.display_name}”? Lịch sử cũ vẫn được giữ.`)) void perform(`retire-provider-${provider.id}`, () => retireGyoProvider(provider.id), 'Provider đã được ngừng dùng.'); }}>Ngừng dùng</button>
          </div>

          {(provider.base_url || '').replace(/\/$/, '') === 'https://opencode.ai/zen/v1' && <section className="gyo-zen-mode"><div><strong>Zen Free Mode</strong><small>Chỉ thêm model Free đã được PQG xác nhận và hiện còn trong catalog Zen.</small></div><button className="btn-primary compact-button" disabled={!provider.credential_configured || busy === `preset-${provider.id}`} onClick={() => void applyZenFreePreset(provider.id)}>{busy === `preset-${provider.id}` ? 'Đang bật…' : 'Dùng bộ model miễn phí gợi ý'}</button></section>}

          {catalogs[provider.id] && <section className="gyo-catalog-list" aria-label={`Model OpenCode Zen cho ${provider.display_name}`}>
            <div><strong>Thêm lựa chọn miễn phí</strong><small>Danh sách này chỉ dùng catalog live để kiểm tra model Free đã khóa vẫn còn khả dụng. Model chưa thêm sẽ không xuất hiện trong GYO.</small></div>
            {catalogs[provider.id].models.map(item => {
              const imported = (model?.models ?? []).some(profile => profile.provider_profile_id === provider.id && profile.model_identifier === item.model_identifier && !profile.retired_at);
              return <label key={item.model_identifier}><input type="checkbox" checked={imported || (catalogSelections[provider.id] ?? []).includes(item.model_identifier)} disabled={imported || busy === `import-${provider.id}`} onChange={() => toggleCatalogModel(provider.id, item.model_identifier)} /><span><strong>{item.display_name}</strong><small>{item.model_identifier} · {item.tier} · miễn phí{imported ? ' · đã thêm' : ''}</small></span></label>;
            })}
            {catalogs[provider.id].models.length === 0 && <p className="muted-copy">Hiện không có model Zen Free trong danh sách khả dụng. PQG Workspace không tự thêm model không xác định.</p>}
            <button className="btn-primary compact-button" disabled={busy === `import-${provider.id}` || !(catalogSelections[provider.id] ?? []).length} onClick={() => void importCatalogModels(provider.id)}>{busy === `import-${provider.id}` ? 'Đang thêm…' : 'Thêm lựa chọn miễn phí'}</button>
          </section>}

          <div className="gyo-model-list">
            {(model?.models ?? []).filter(item => item.provider_profile_id === provider.id && !item.retired_at).map(item => <div key={item.id}>
              <span><strong>{item.display_name}</strong><small>{item.model_identifier} · {item.tier} · {costLabel[item.cost_class]}{item.is_default ? ' · mặc định' : ''}</small></span>
              <span className="gyo-model-actions">
                <button className="btn-secondary compact-button" onClick={() => void perform(`toggle-${item.id}`, () => updateGyoModel(item.id, { enabled: !item.enabled }), item.enabled ? 'Đã tắt model.' : 'Đã bật model.')}>{item.enabled ? 'Tắt' : 'Bật'}</button>
                <button className="btn-secondary compact-button" disabled={item.is_default || !item.enabled} onClick={() => void perform(`default-${item.id}`, () => updateGyoModel(item.id, { make_default: true }), 'Đã đặt model mặc định.')}>Đặt mặc định</button>
                <button className="btn-secondary compact-button" onClick={() => { if (window.confirm(`Ngừng dùng model “${item.display_name}”?`)) void perform(`retire-model-${item.id}`, () => retireGyoModel(item.id), 'Model đã được ngừng dùng.'); }}>Ngừng dùng</button>
              </span>
            </div>)}
          </div>
        </article>)}

        {model && model.providers.length === 0 && <div className="empty-state"><div className="empty-state-title">Chưa có provider GYO</div><div className="empty-state-text">Thêm một provider và model để bắt đầu trao đổi với GYO.</div></div>}
      </div>
    </section>
  );
}
