"""Focused regression coverage for the native GYO provider core."""
from __future__ import annotations

import pytest

from app.api.model_config import _zen_is_free
from app.api.schemas import GyoDiscoveredModelResponse
from app.services.gyo_orchestrator import GyoEvent, GyoOrchestrator, GyoRunRequest
from app.services.gyo_registry import GyoProviderRegistry, validate_base_url


@pytest.mark.asyncio
async def test_provider_model_profiles_are_browser_safe_and_retirable(client, test_app, monkeypatch):
    """Credentials never appear in config and retire preserves model history."""
    secrets: dict[str, str] = {}
    monkeypatch.setattr("app.services.gyo_registry.keyring.set_password", lambda service, ref, value: secrets.__setitem__(ref, value))
    monkeypatch.setattr("app.services.gyo_registry.keyring.get_password", lambda service, ref: secrets.get(ref))
    response = await client.post("/api/model-config/providers", json={
        "display_name": "OpenAI local", "provider_type": "openai_responses", "api_key": "never-return-this",
    })
    assert response.status_code == 201
    provider = response.json()
    assert provider["credential_configured"] is True
    assert "never-return-this" not in response.text
    assert "credential_ref" not in provider

    model_response = await client.post("/api/model-config/models", json={
        "provider_profile_id": provider["id"], "display_name": "Balanced", "model_identifier": "gpt-test",
        "tier": "balanced", "capabilities": ["chat", "tools"], "make_default": True,
    })
    assert model_response.status_code == 201
    model = model_response.json()
    config = await client.get("/api/model-config")
    assert config.status_code == 200
    assert config.json()["provider"] == "OpenAI local"
    assert config.json()["model"] == "gpt-test"
    assert config.json()["auth_ready"] is True
    assert config.json()["models"][0]["id"] == model["id"]

    retired = await client.post(f"/api/model-config/models/{model['id']}/retire")
    assert retired.status_code == 200
    assert retired.json()["retired_at"] is not None
    historical = await client.get("/api/model-config?include_retired=true")
    assert any(item["id"] == model["id"] for item in historical.json()["models"])


@pytest.mark.asyncio
async def test_model_router_is_deterministic_and_never_uses_retired_profile(migrated_db_path, monkeypatch):
    from app.settings import Settings

    settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"])
    registry = GyoProviderRegistry(settings)
    monkeypatch.setattr("app.services.gyo_registry.keyring.get_password", lambda *_args: "test-key")
    from app.db.connection import get_db_connection
    async with get_db_connection(migrated_db_path) as conn:
        await conn.execute("INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES ('p-fast', 'Fast', 'openai_responses', NULL, 'provider:p-fast', 1, 1, 1)")
        await conn.execute("INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES ('p-deep', 'Deep', 'openai_responses', NULL, 'provider:p-deep', 1, 1, 1)")
        await conn.execute("INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES ('m-fast', 'p-fast', 'Fast', 'fast-model', 'fast', '[\"chat\"]', 1, 1, 0, 1, 1)")
        await conn.execute("INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES ('m-deep', 'p-deep', 'Deep', 'deep-model', 'deep', '[\"chat\", \"tools\"]', 1, 1, 1, 1, 1)")
        await conn.commit()
    profile, model, reason = await registry.select_model(model_profile_id=None, route_mode="auto", prompt="Lập kế hoạch cho Công việc", attachment_count=0)
    assert (profile.id, model.id, reason) == ("p-deep", "m-deep", "auto_deep")
    profile, model, reason = await registry.select_model(model_profile_id="m-fast", route_mode="manual", prompt="x", attachment_count=0)
    assert (profile.id, model.id, reason) == ("p-fast", "m-fast", "manual_selection")


def test_provider_url_boundary() -> None:
    assert validate_base_url("openai_responses", None) is None
    assert validate_base_url("openai_compatible", "http://127.0.0.1:11434/v1/") == "http://127.0.0.1:11434/v1"
    with pytest.raises(ValueError):
        validate_base_url("openai_compatible", "http://example.com/v1")
    with pytest.raises(ValueError):
        validate_base_url("openai_compatible", "https://user:password@example.com/v1")


def test_zen_free_filter_uses_locked_catalog_not_live_price_metadata() -> None:
    assert _zen_is_free({"id": "deepseek-v4-flash-free"}) is True
    assert _zen_is_free({"id": "muse-spark-1.2-contributor-free"}) is True
    assert _zen_is_free({"id": "free", "free": True}) is False
    assert _zen_is_free({"id": "unknown"}) is False
    assert _zen_is_free({"id": "paid", "pricing": {"input": 0, "output": 0}}) is False


@pytest.mark.asyncio
async def test_zen_catalog_is_explicit_and_never_persists_or_returns_credentials(client, monkeypatch):
    secrets: dict[str, str] = {}
    monkeypatch.setattr("app.services.gyo_registry.keyring.set_password", lambda _service, ref, value: secrets.__setitem__(ref, value))
    monkeypatch.setattr("app.services.gyo_registry.keyring.get_password", lambda _service, ref: secrets.get(ref))
    provider_response = await client.post("/api/model-config/providers", json={
        "display_name": "Zen free", "provider_type": "openai_compatible",
        "base_url": "https://opencode.ai/zen/v1", "api_key": "secret-zen-key",
    })
    assert provider_response.status_code == 201
    provider_id = provider_response.json()["id"]

    received: dict[str, str] = {}
    async def fake_catalog(credential: str, provider_type: str):
        received.update({"credential": credential, "provider_type": provider_type})
        return [GyoDiscoveredModelResponse(model_identifier="deepseek-v4-flash-free", display_name="DeepSeek V4 Flash Free", tier="fast", capabilities=["chat"])], 3
    monkeypatch.setattr("app.api.model_config.fetch_opencode_zen_catalog", fake_catalog)

    catalog = await client.post(f"/api/model-config/providers/{provider_id}/models/discover")
    assert catalog.status_code == 200
    assert catalog.json() == {
        "provider_id": provider_id, "source": "opencode_zen", "skipped_count": 3,
        "models": [{"model_identifier": "deepseek-v4-flash-free", "display_name": "DeepSeek V4 Flash Free", "tier": "fast", "capabilities": ["chat"], "is_free": True, "availability": "available"}],
    }
    assert received == {"credential": "secret-zen-key", "provider_type": "openai_compatible"}
    assert "secret-zen-key" not in catalog.text
    assert (await client.get("/api/model-config")).json()["models"] == []


@pytest.mark.asyncio
async def test_orchestrator_returns_safe_failure_without_enabled_model(migrated_db_path):
    from app.settings import Settings

    orchestrator = GyoOrchestrator(Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"]))
    result = await orchestrator.run(GyoRunRequest(work_id="work", prompt="hello", context="context", assistant_turn_id="turn"))
    assert result.status == "failed"
    assert result.selection_reason == "no_eligible_model"


@pytest.mark.asyncio
async def test_zen_free_preset_is_atomic_idempotent_and_marks_cost_class(client, monkeypatch):
    secrets: dict[str, str] = {}
    monkeypatch.setattr("app.services.gyo_registry.keyring.set_password", lambda _service, ref, value: secrets.__setitem__(ref, value))
    monkeypatch.setattr("app.services.gyo_registry.keyring.get_password", lambda _service, ref: secrets.get(ref))
    provider = await client.post("/api/model-config/providers", json={
        "display_name": "Zen", "provider_type": "openai_compatible", "base_url": "https://opencode.ai/zen/v1", "api_key": "key",
    })
    assert provider.status_code == 201

    async def fake_catalog(_credential: str, _provider_type: str):
        return [
            GyoDiscoveredModelResponse(model_identifier="deepseek-v4-flash-free", display_name="DeepSeek V4 Flash Free", tier="fast", capabilities=["chat"]),
            GyoDiscoveredModelResponse(model_identifier="mimo-v2.5-free", display_name="MiMo V2.5 Free", tier="balanced", capabilities=["chat"]),
            GyoDiscoveredModelResponse(model_identifier="nemotron-3-ultra-free", display_name="Nemotron 3 Ultra Free", tier="deep", capabilities=["chat"]),
        ], 0
    monkeypatch.setattr("app.api.model_config.fetch_opencode_zen_catalog", fake_catalog)

    first = await client.post(f"/api/model-config/providers/{provider.json()['id']}/models/zen-free-preset")
    assert first.status_code == 200
    assert len(first.json()["models"]) == 3
    assert {item["cost_class"] for item in first.json()["models"]} == {"free"}
    assert next(item for item in first.json()["models"] if item["model_identifier"] == "mimo-v2.5-free")["is_default"] is True
    second = await client.post(f"/api/model-config/providers/{provider.json()['id']}/models/zen-free-preset")
    assert second.status_code == 200
    config = await client.get("/api/model-config")
    assert len(config.json()["models"]) == 3
    assert config.json()["routing_policy"]["auto_fallback_enabled"] is False


class _FallbackAdapter:
    def __init__(self, *, partial_token: bool = False):
        self.partial_token = partial_token
        self.calls: list[str] = []

    async def health_check(self, *_args):  # pragma: no cover - routing test only
        raise AssertionError("not used")

    async def stream(self, _request, _profile, model, _credential, _cancel_event):
        self.calls.append(model.id)
        if len(self.calls) == 1:
            if self.partial_token:
                yield GyoEvent("token", {"text": "partial"})
            yield GyoEvent("error", {"message": "safe", "retryable": True, "outcome": "rate_limited"})
            return
        yield GyoEvent("token", {"text": "completed"})


@pytest.mark.asyncio
async def test_fallback_is_opt_in_bounded_and_never_after_token(migrated_db_path, monkeypatch):
    from app.db.connection import get_db_connection
    from app.settings import Settings

    settings = Settings(db_path=str(migrated_db_path), cors_origins=["http://localhost:5173"])
    monkeypatch.setattr("app.services.gyo_registry.keyring.get_password", lambda *_args: "key")
    async with get_db_connection(migrated_db_path) as conn:
        for provider_id in ("fallback-p1", "fallback-p2"):
            await conn.execute("INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES (?, ?, 'openai_responses', NULL, ?, 1, 1, 1)", (provider_id, provider_id, f"provider:{provider_id}"))
        for model_id, provider_id, priority in (("fallback-m1", "fallback-p1", 1), ("fallback-m2", "fallback-p2", 2)):
            await conn.execute("INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, created_at, updated_at) VALUES (?, ?, ?, ?, 'fast', '[\"chat\"]', ?, 1, 0, 1, 1)", (model_id, provider_id, model_id, model_id, priority))
        await conn.execute("UPDATE gyo_routing_policy SET auto_fallback_enabled = 1 WHERE id = 1")
        await conn.commit()
    adapter = _FallbackAdapter()
    result = await GyoOrchestrator(settings, providers={"openai_responses": adapter}).run(GyoRunRequest(work_id="w", prompt="short", context="x"))
    assert result.status == "completed"
    assert adapter.calls == ["fallback-m1", "fallback-m2"]
    assert [item["outcome"] for item in result.fallback_chain] == ["rate_limited", "succeeded"]

    after_token = _FallbackAdapter(partial_token=True)
    result = await GyoOrchestrator(settings, providers={"openai_responses": after_token}).run(GyoRunRequest(work_id="w", prompt="short", context="x"))
    assert result.status == "failed"
    assert after_token.calls == ["fallback-m1"]
