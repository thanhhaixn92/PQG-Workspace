"""Browser-safe management of native GYO provider and model profiles."""
from __future__ import annotations

import json
import time
import uuid

import aiosqlite
import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas import (
    GyoModelCreateRequest, GyoModelResponse, GyoModelUpdateRequest,
    GyoProviderCredentialRequest, GyoProviderCreateRequest, GyoProviderHealthResponse,
    GyoProviderResponse, GyoProviderUpdateRequest, GyoProviderCatalogResponse,
    GyoDiscoveredModelResponse, ModelConfigResponse, GyoRoutingPolicyResponse,
    GyoRoutingPolicyUpdateRequest, GyoZenFreeImportRequest, GyoZenFreeImportResponse,
)
from app.dependencies import get_db, get_gyo_orchestrator, get_settings
from app.services.audit import log_audit_event
from app.services.gyo_orchestrator import GyoOrchestrator
from app.services.gyo_registry import GyoProviderRegistry, validate_base_url
from app.settings import Settings

router = APIRouter(prefix="/api/model-config", tags=["model-config"])

_OPENCODE_ZEN_BASE_URL = "https://opencode.ai/zen/v1"
_ZEN_FREE_MODELS: dict[str, dict[str, object]] = {
    "big-pickle": {"display_name": "Big Pickle", "tier": "balanced"},
    "deepseek-v4-flash-free": {"display_name": "DeepSeek V4 Flash Free", "tier": "fast"},
    "mimo-v2.5-free": {"display_name": "MiMo V2.5 Free", "tier": "balanced"},
    "hy3-free": {"display_name": "HY3 Free", "tier": "balanced"},
    "laguna-s-2.1-free": {"display_name": "Laguna S 2.1 Free", "tier": "balanced"},
    "muse-spark-1.2-contributor-free": {"display_name": "Muse Spark 1.2 Contributor Free", "tier": "balanced"},
    "nemotron-3-ultra-free": {"display_name": "Nemotron 3 Ultra Free", "tier": "deep"},
    "nemotron-3.5-lightning-free": {"display_name": "Nemotron 3.5 Lightning Free", "tier": "fast"},
}
_ZEN_PRESET_IDS = ("deepseek-v4-flash-free", "mimo-v2.5-free", "nemotron-3-ultra-free")


def _is_zen_provider(provider: aiosqlite.Row) -> bool:
    return (
        provider["provider_type"] == "openai_compatible"
        and (provider["base_url"] or "").rstrip("/") == _OPENCODE_ZEN_BASE_URL
    )


def _zen_is_free(item: dict[object, object]) -> bool:
    """Return true only for the locked, published Zen Free identifiers.

    ``/v1/models`` is an availability feed, not a pricing source.  This avoids
    accidentally labelling a paid model as free when the live payload omits
    price metadata.
    """
    identifier = item.get("id")
    return isinstance(identifier, str) and identifier.strip() in _ZEN_FREE_MODELS


async def fetch_opencode_zen_catalog(credential: str, provider_type: str) -> tuple[list[GyoDiscoveredModelResponse], int]:
    """Fetch Zen only after an explicit user request; never persist remote output."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
            response = await client.get(
                f"{_OPENCODE_ZEN_BASE_URL}/models",
                headers={"Authorization": f"Bearer {credential}", "Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Không tải được danh sách model từ OpenCode Zen. Kiểm tra khóa, kết nối và thử lại.") from exc
    raw_models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(raw_models, list):
        raise RuntimeError("OpenCode Zen trả về catalog không đúng định dạng.")

    if provider_type != "openai_compatible":
        return [], len(raw_models)
    live_ids: set[str] = set()
    skipped = 0
    for item in raw_models:
        if not isinstance(item, dict):
            skipped += 1
            continue
        model_identifier = item.get("id")
        if not isinstance(model_identifier, str) or not model_identifier.strip() or len(model_identifier) > 200:
            skipped += 1
            continue
        model_identifier = model_identifier.strip()
        if model_identifier not in _ZEN_FREE_MODELS:
            skipped += 1
            continue
        live_ids.add(model_identifier)
    discovered: list[GyoDiscoveredModelResponse] = []
    for model_identifier, metadata in _ZEN_FREE_MODELS.items():
        if model_identifier not in live_ids:
            continue
        discovered.append(GyoDiscoveredModelResponse(
            model_identifier=model_identifier, display_name=str(metadata["display_name"]),
            tier=str(metadata["tier"]), capabilities=["chat"], is_free=True, availability="available",
        ))
    return discovered, skipped


def _model(row: aiosqlite.Row) -> GyoModelResponse:
    try:
        raw = json.loads(row["capabilities_json"])
    except (json.JSONDecodeError, TypeError):
        raw = ["chat"]
    capabilities = [v for v in raw if v in {"chat", "vision", "tools"}]
    if "chat" not in capabilities:
        capabilities.insert(0, "chat")
    return GyoModelResponse(
        id=row["id"], provider_profile_id=row["provider_profile_id"], display_name=row["display_name"],
        model_identifier=row["model_identifier"], tier=row["tier"], capabilities=capabilities,
        priority=row["priority"], enabled=bool(row["enabled"]), is_default=bool(row["is_default"]),
        cost_class=row["cost_class"] if "cost_class" in row.keys() else "unknown",
        retired_at=row["retired_at"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _provider(row: aiosqlite.Row, registry: GyoProviderRegistry) -> GyoProviderResponse:
    configured = bool(registry.get_credential(row["credential_ref"]))
    if row["retired_at"] is not None:
        health, detail = "unknown", "Provider đã nghỉ hưu và chỉ còn trong lịch sử."
    elif row["provider_type"] == "openai_compatible" and not row["base_url"]:
        health, detail = "misconfigured", "Provider cần base URL hợp lệ."
    elif not configured:
        health, detail = "needs_credential", "Chưa có khóa trong Windows Credential Manager."
    else:
        health, detail = "ready", "Đã có cấu hình cục bộ."
    return GyoProviderResponse(
        id=row["id"], display_name=row["display_name"], provider_type=row["provider_type"], base_url=row["base_url"],
        enabled=bool(row["enabled"]), retired_at=row["retired_at"], credential_configured=configured,
        health_status=health, health_message=detail, created_at=row["created_at"], updated_at=row["updated_at"],
    )


async def _provider_row(conn: aiosqlite.Connection, provider_id: str, *, active_only: bool = False) -> aiosqlite.Row:
    query = "SELECT * FROM ai_provider_profiles WHERE id = ?" + (" AND retired_at IS NULL" if active_only else "")
    async with conn.execute(query, (provider_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    return row


async def _model_row(conn: aiosqlite.Connection, model_id: str, *, active_only: bool = False) -> aiosqlite.Row:
    query = "SELECT * FROM ai_model_profiles WHERE id = ?" + (" AND retired_at IS NULL" if active_only else "")
    async with conn.execute(query, (model_id,)) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Model profile not found")
    return row


@router.get("", response_model=ModelConfigResponse)
async def get_model_config(
    include_retired: bool = False, conn: aiosqlite.Connection = Depends(get_db), settings: Settings = Depends(get_settings),
) -> ModelConfigResponse:
    registry = GyoProviderRegistry(settings)
    provider_query = "SELECT * FROM ai_provider_profiles" + ("" if include_retired else " WHERE retired_at IS NULL") + " ORDER BY created_at, id"
    model_query = "SELECT * FROM ai_model_profiles" + ("" if include_retired else " WHERE retired_at IS NULL") + " ORDER BY priority, created_at, id"
    async with conn.execute(provider_query) as cur:
        providers = [_provider(row, registry) async for row in cur]
    async with conn.execute(model_query) as cur:
        models = [_model(row) async for row in cur]
    default = next((m for m in models if m.is_default and m.enabled and m.retired_at is None), None)
    default_provider = next((p for p in providers if default and p.id == default.provider_profile_id), None)
    async with conn.execute("SELECT auto_fallback_enabled FROM gyo_routing_policy WHERE id = 1") as cur:
        policy_row = await cur.fetchone()
    counts = {"free": 0, "unknown": 0, "may_charge": 0}
    for item in models:
        if item.enabled and item.retired_at is None:
            counts[item.cost_class] += 1
    return ModelConfigResponse(
        provider=default_provider.display_name if default_provider else None,
        model=default.model_identifier if default else None,
        auth_ready=bool(default_provider and default_provider.enabled and default_provider.credential_configured),
        mutable_from_browser=True,
        guidance=("Chưa có model GYO mặc định. Thêm provider và model; khóa chỉ lưu trong Windows Credential Manager."
                  if default is None else "GYO dùng model mặc định hoặc model được chọn cho từng lần chạy. Trình duyệt không nhận lại khóa API."),
        providers=providers, models=models, default_model_profile_id=default.id if default else None,
        routing_policy=GyoRoutingPolicyResponse(
            auto_fallback_enabled=bool(policy_row["auto_fallback_enabled"]) if policy_row else False,
            enabled_model_counts=counts,
        ),
    )


@router.post("/providers", response_model=GyoProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(request: GyoProviderCreateRequest, conn: aiosqlite.Connection = Depends(get_db), settings: Settings = Depends(get_settings)) -> GyoProviderResponse:
    try:
        base_url = validate_base_url(request.provider_type, request.base_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    provider_id = f"provider-{uuid.uuid4().hex[:12]}"
    credential_ref = f"provider:{provider_id}"
    now = int(time.time())
    registry = GyoProviderRegistry(settings)
    try:
        await conn.execute("BEGIN IMMEDIATE")
        await conn.execute("INSERT INTO ai_provider_profiles (id, display_name, provider_type, base_url, credential_ref, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                           (provider_id, request.display_name, request.provider_type, base_url, credential_ref, now, now))
        if request.api_key is not None:
            registry.set_credential(credential_ref, request.api_key.get_secret_value())
        await log_audit_event(conn, None, "user", "gyo.provider_created", provider_id,
                              {"provider_type": request.provider_type, "credential_configured": request.api_key is not None}, commit=False)
        await conn.commit()
    except RuntimeError as exc:
        await conn.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _provider(await _provider_row(conn, provider_id), registry)


@router.patch("/providers/{provider_id}", response_model=GyoProviderResponse)
async def update_provider(provider_id: str, request: GyoProviderUpdateRequest, conn: aiosqlite.Connection = Depends(get_db), settings: Settings = Depends(get_settings)) -> GyoProviderResponse:
    current = await _provider_row(conn, provider_id, active_only=True)
    updates: list[str] = []
    values: list[object] = []
    if request.display_name is not None:
        updates.append("display_name = ?"); values.append(request.display_name)
    if request.base_url is not None:
        try:
            base_url = validate_base_url(current["provider_type"], request.base_url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        updates.append("base_url = ?"); values.append(base_url)
    if request.enabled is not None:
        updates.append("enabled = ?"); values.append(int(request.enabled))
    if not updates:
        return _provider(current, GyoProviderRegistry(settings))
    now = int(time.time())
    updates.append("updated_at = ?"); values.extend([now, provider_id])
    await conn.execute(f"UPDATE ai_provider_profiles SET {', '.join(updates)} WHERE id = ?", values)
    await log_audit_event(conn, None, "user", "gyo.provider_updated", provider_id, {"fields": updates[:-1]}, commit=False)
    await conn.commit()
    return _provider(await _provider_row(conn, provider_id), GyoProviderRegistry(settings))


@router.post("/providers/{provider_id}/credential", response_model=GyoProviderResponse)
async def set_provider_credential(provider_id: str, request: GyoProviderCredentialRequest, conn: aiosqlite.Connection = Depends(get_db), settings: Settings = Depends(get_settings)) -> GyoProviderResponse:
    current = await _provider_row(conn, provider_id, active_only=True)
    registry = GyoProviderRegistry(settings)
    try:
        registry.set_credential(current["credential_ref"], request.api_key.get_secret_value())
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await log_audit_event(conn, None, "user", "gyo.provider_credential_set", provider_id, {}, commit=False)
    await conn.commit()
    return _provider(current, registry)


@router.post("/providers/{provider_id}/health", response_model=GyoProviderHealthResponse)
async def provider_health(provider_id: str, conn: aiosqlite.Connection = Depends(get_db), orchestrator: GyoOrchestrator = Depends(get_gyo_orchestrator)) -> GyoProviderHealthResponse:
    await _provider_row(conn, provider_id, active_only=True)
    result = await orchestrator.health_check(provider_id)
    return GyoProviderHealthResponse(provider_id=provider_id, status=result.status, message=result.message)


@router.post("/providers/{provider_id}/models/discover", response_model=GyoProviderCatalogResponse)
async def discover_provider_models(
    provider_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GyoProviderCatalogResponse:
    """Load the supported subset of an OpenCode Zen catalog on explicit demand."""
    provider = await _provider_row(conn, provider_id, active_only=True)
    if not provider["enabled"]:
        raise HTTPException(status_code=409, detail="Provider is disabled")
    if not _is_zen_provider(provider):
        raise HTTPException(status_code=422, detail="Tải catalog hiện chỉ hỗ trợ provider OpenCode Zen với base URL https://opencode.ai/zen/v1")
    registry = GyoProviderRegistry(settings)
    credential = registry.get_credential(provider["credential_ref"])
    if not credential:
        raise HTTPException(status_code=409, detail="Cần lưu khóa OpenCode Zen trước khi tải catalog")
    try:
        models, skipped_count = await fetch_opencode_zen_catalog(credential, provider["provider_type"])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await log_audit_event(
        conn, None, "user", "gyo.provider_catalog_loaded", provider_id,
        {"source": "opencode_zen", "provider_type": provider["provider_type"], "model_count": len(models), "skipped_count": skipped_count},
        commit=False,
    )
    await conn.commit()
    return GyoProviderCatalogResponse(provider_id=provider_id, source="opencode_zen", models=models, skipped_count=skipped_count)


async def _import_zen_free_models(
    conn: aiosqlite.Connection,
    *,
    provider: aiosqlite.Row,
    settings: Settings,
    model_identifiers: list[str],
    preset: bool,
) -> GyoZenFreeImportResponse:
    """Atomically install only free Zen IDs which the live catalog exposes."""
    if not provider["enabled"]:
        raise HTTPException(status_code=409, detail="Provider is disabled")
    if not _is_zen_provider(provider):
        raise HTTPException(status_code=422, detail="Zen Free Mode cần provider OpenAI-compatible tại https://opencode.ai/zen/v1")
    registry = GyoProviderRegistry(settings)
    credential = registry.get_credential(provider["credential_ref"])
    if not credential:
        raise HTTPException(status_code=409, detail="Cần lưu khóa OpenCode Zen trước khi thêm model miễn phí")
    try:
        catalog, _ = await fetch_opencode_zen_catalog(credential, provider["provider_type"])
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    available = {item.model_identifier for item in catalog}
    requested = list(dict.fromkeys(model_identifiers))
    unavailable = [identifier for identifier in requested if identifier not in available]
    installable = [identifier for identifier in requested if identifier in available]
    if not installable:
        raise HTTPException(status_code=409, detail="Không có model Zen Free nào đang khả dụng để thêm")
    now = int(time.time())
    created_ids: list[str] = []
    try:
        await conn.execute("BEGIN IMMEDIATE")
        for identifier in installable:
            metadata = _ZEN_FREE_MODELS[identifier]
            async with conn.execute(
                "SELECT id FROM ai_model_profiles WHERE provider_profile_id = ? AND model_identifier = ?",
                (provider["id"], identifier),
            ) as cur:
                existing = await cur.fetchone()
            model_id = existing["id"] if existing else f"model-{uuid.uuid4().hex[:12]}"
            # The preset is an explicit user choice; its balanced MiMo model
            # becomes the deterministic default even when an older provider
            # previously owned the singleton default slot.
            make_default = int(identifier == "mimo-v2.5-free")
            if make_default:
                await conn.execute("UPDATE ai_model_profiles SET is_default = 0, updated_at = ? WHERE is_default = 1", (now,))
            if existing:
                await conn.execute(
                    "UPDATE ai_model_profiles SET display_name = ?, tier = ?, capabilities_json = ?, priority = 10, enabled = 1, "
                    "is_default = CASE WHEN ? = 1 THEN 1 ELSE is_default END, retired_at = NULL, cost_class = 'free', updated_at = ? WHERE id = ?",
                    (metadata["display_name"], metadata["tier"], json.dumps(["chat"]), make_default, now, model_id),
                )
            else:
                await conn.execute(
                    "INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, cost_class, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 10, 1, ?, 'free', ?, ?)",
                    (model_id, provider["id"], metadata["display_name"], identifier, metadata["tier"], json.dumps(["chat"]), make_default, now, now),
                )
            created_ids.append(model_id)
        await log_audit_event(
            conn, None, "user", "gyo.zen_free_models_added", provider["id"],
            {"preset": preset, "model_count": len(created_ids), "unavailable_count": len(unavailable)}, commit=False,
        )
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    models = [_model(await _model_row(conn, model_id)) for model_id in created_ids]
    return GyoZenFreeImportResponse(provider_id=provider["id"], models=models, unavailable_model_ids=unavailable)


@router.post("/providers/{provider_id}/models/zen-free-preset", response_model=GyoZenFreeImportResponse)
async def install_zen_free_preset(
    provider_id: str,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GyoZenFreeImportResponse:
    provider = await _provider_row(conn, provider_id, active_only=True)
    return await _import_zen_free_models(
        conn, provider=provider, settings=settings, model_identifiers=list(_ZEN_PRESET_IDS), preset=True,
    )


@router.post("/providers/{provider_id}/models/zen-free-import", response_model=GyoZenFreeImportResponse)
async def import_zen_free_models(
    provider_id: str,
    request: GyoZenFreeImportRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> GyoZenFreeImportResponse:
    provider = await _provider_row(conn, provider_id, active_only=True)
    if any(identifier not in _ZEN_FREE_MODELS for identifier in request.model_identifiers):
        raise HTTPException(status_code=422, detail="Chỉ model thuộc Zen Free catalog mới có thể được thêm từ danh sách này")
    return await _import_zen_free_models(
        conn, provider=provider, settings=settings, model_identifiers=request.model_identifiers, preset=False,
    )


@router.put("/routing-policy", response_model=GyoRoutingPolicyResponse)
async def update_routing_policy(
    request: GyoRoutingPolicyUpdateRequest,
    conn: aiosqlite.Connection = Depends(get_db),
) -> GyoRoutingPolicyResponse:
    now = int(time.time())
    await conn.execute(
        "INSERT INTO gyo_routing_policy (id, auto_fallback_enabled, updated_at) VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET auto_fallback_enabled = excluded.auto_fallback_enabled, updated_at = excluded.updated_at",
        (int(request.auto_fallback_enabled), now),
    )
    await log_audit_event(conn, None, "user", "gyo.routing_policy_updated", "routing-policy", {"auto_fallback_enabled": request.auto_fallback_enabled}, commit=False)
    await conn.commit()
    counts = {"free": 0, "unknown": 0, "may_charge": 0}
    async with conn.execute("SELECT cost_class, COUNT(*) AS count FROM ai_model_profiles WHERE enabled = 1 AND retired_at IS NULL GROUP BY cost_class") as cur:
        rows = await cur.fetchall()
    for row in rows:
        if row["cost_class"] in counts:
            counts[row["cost_class"]] = row["count"]
    return GyoRoutingPolicyResponse(auto_fallback_enabled=request.auto_fallback_enabled, enabled_model_counts=counts)


@router.post("/providers/{provider_id}/retire", response_model=GyoProviderResponse)
async def retire_provider(provider_id: str, conn: aiosqlite.Connection = Depends(get_db), settings: Settings = Depends(get_settings)) -> GyoProviderResponse:
    await _provider_row(conn, provider_id, active_only=True)
    now = int(time.time())
    await conn.execute("UPDATE ai_provider_profiles SET enabled = 0, retired_at = ?, updated_at = ? WHERE id = ?", (now, now, provider_id))
    await conn.execute("UPDATE ai_model_profiles SET is_default = 0, updated_at = ? WHERE provider_profile_id = ?", (now, provider_id))
    await log_audit_event(conn, None, "user", "gyo.provider_retired", provider_id, {}, commit=False)
    await conn.commit()
    return _provider(await _provider_row(conn, provider_id), GyoProviderRegistry(settings))


@router.post("/models", response_model=GyoModelResponse, status_code=status.HTTP_201_CREATED)
async def create_model(request: GyoModelCreateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> GyoModelResponse:
    provider = await _provider_row(conn, request.provider_profile_id, active_only=True)
    if not provider["enabled"]:
        raise HTTPException(status_code=409, detail="Provider is disabled")
    model_id = f"model-{uuid.uuid4().hex[:12]}"; now = int(time.time())
    try:
        await conn.execute("BEGIN IMMEDIATE")
        if request.make_default:
            await conn.execute("UPDATE ai_model_profiles SET is_default = 0, updated_at = ? WHERE is_default = 1", (now,))
        await conn.execute("INSERT INTO ai_model_profiles (id, provider_profile_id, display_name, model_identifier, tier, capabilities_json, priority, enabled, is_default, cost_class, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 'unknown', ?, ?)",
                           (model_id, request.provider_profile_id, request.display_name, request.model_identifier, request.tier, json.dumps(request.capabilities), request.priority, int(request.make_default), now, now))
        await log_audit_event(conn, None, "user", "gyo.model_created", model_id, {"provider_profile_id": request.provider_profile_id, "tier": request.tier, "capabilities": request.capabilities}, commit=False)
        await conn.commit()
    except aiosqlite.IntegrityError as exc:
        await conn.rollback()
        raise HTTPException(status_code=409, detail="A model with this identifier already exists for the provider") from exc
    return _model(await _model_row(conn, model_id))


@router.patch("/models/{model_id}", response_model=GyoModelResponse)
async def update_model(model_id: str, request: GyoModelUpdateRequest, conn: aiosqlite.Connection = Depends(get_db)) -> GyoModelResponse:
    current = await _model_row(conn, model_id, active_only=True)
    updates: list[str] = []; values: list[object] = []
    for field, value in (("display_name", request.display_name), ("tier", request.tier), ("priority", request.priority)):
        if value is not None:
            updates.append(f"{field} = ?"); values.append(value)
    if request.capabilities is not None:
        updates.append("capabilities_json = ?"); values.append(json.dumps(request.capabilities))
    if request.enabled is not None:
        updates.append("enabled = ?"); values.append(int(request.enabled))
        if not request.enabled:
            updates.append("is_default = 0")
    now = int(time.time())
    try:
        await conn.execute("BEGIN IMMEDIATE")
        if request.make_default is True:
            if request.enabled is False:
                raise HTTPException(status_code=422, detail="A disabled model cannot be default")
            await conn.execute("UPDATE ai_model_profiles SET is_default = 0, updated_at = ? WHERE is_default = 1", (now,))
            updates.append("is_default = 1")
        elif request.make_default is False:
            updates.append("is_default = 0")
        if not updates:
            await conn.rollback()
            return _model(current)
        updates.append("updated_at = ?"); values.extend([now, model_id])
        await conn.execute(f"UPDATE ai_model_profiles SET {', '.join(updates)} WHERE id = ?", values)
        await log_audit_event(conn, None, "user", "gyo.model_updated", model_id, {"fields": updates[:-1]}, commit=False)
        await conn.commit()
    except HTTPException:
        await conn.rollback(); raise
    return _model(await _model_row(conn, model_id))


@router.post("/models/{model_id}/retire", response_model=GyoModelResponse)
async def retire_model(model_id: str, conn: aiosqlite.Connection = Depends(get_db)) -> GyoModelResponse:
    await _model_row(conn, model_id, active_only=True)
    now = int(time.time())
    await conn.execute("UPDATE ai_model_profiles SET enabled = 0, is_default = 0, retired_at = ?, updated_at = ? WHERE id = ?", (now, now, model_id))
    await log_audit_event(conn, None, "user", "gyo.model_retired", model_id, {}, commit=False)
    await conn.commit()
    return _model(await _model_row(conn, model_id))
