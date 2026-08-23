"""Persistence and credential helpers for GYO provider/model profiles."""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

import aiosqlite
import keyring
from keyring.errors import KeyringError

from app.db.connection import get_db_connection
from app.settings import Settings

ProviderType = Literal["openai_responses", "openai_compatible"]
ModelTier = Literal["fast", "balanced", "deep", "vision"]


@dataclass(frozen=True)
class GyoProviderProfile:
    id: str
    display_name: str
    provider_type: ProviderType
    base_url: str | None
    credential_ref: str
    enabled: bool
    retired_at: int | None
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class GyoModelProfile:
    id: str
    provider_profile_id: str
    display_name: str
    model_identifier: str
    tier: ModelTier
    capabilities: list[str]
    priority: int
    enabled: bool
    is_default: bool
    cost_class: Literal["free", "unknown", "may_charge"]
    retired_at: int | None
    created_at: int
    updated_at: int


def validate_base_url(provider_type: ProviderType, base_url: str | None) -> str | None:
    if provider_type == "openai_responses" and not base_url:
        return None
    if not base_url:
        raise ValueError("OpenAI-compatible provider requires a base URL")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Provider base URL must be an absolute HTTP(S) URL without credentials")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Non-loopback provider base URL must use HTTPS")
    return base_url.rstrip("/")


def _provider_from_row(row: aiosqlite.Row) -> GyoProviderProfile:
    return GyoProviderProfile(
        id=row["id"], display_name=row["display_name"], provider_type=row["provider_type"],
        base_url=row["base_url"], credential_ref=row["credential_ref"], enabled=bool(row["enabled"]),
        retired_at=row["retired_at"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _model_from_row(row: aiosqlite.Row) -> GyoModelProfile:
    parsed = json.loads(row["capabilities_json"])
    capabilities = [value for value in parsed if value in {"chat", "vision", "tools"}] if isinstance(parsed, list) else ["chat"]
    if "chat" not in capabilities:
        capabilities.insert(0, "chat")
    return GyoModelProfile(
        id=row["id"], provider_profile_id=row["provider_profile_id"], display_name=row["display_name"],
        model_identifier=row["model_identifier"], tier=row["tier"], capabilities=capabilities,
        priority=row["priority"], enabled=bool(row["enabled"]), is_default=bool(row["is_default"]),
        cost_class=row["cost_class"] if "cost_class" in row.keys() else "unknown",
        retired_at=row["retired_at"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


class GyoProviderRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_credential(self, credential_ref: str) -> str | None:
        try:
            return keyring.get_password(self.settings.gyo_keyring_service, credential_ref)
        except KeyringError:
            return None

    def set_credential(self, credential_ref: str, secret: str) -> None:
        try:
            keyring.set_password(self.settings.gyo_keyring_service, credential_ref, secret)
        except KeyringError as exc:
            raise RuntimeError("Windows Credential Manager is unavailable") from exc

    async def get_provider(self, provider_id: str, *, include_retired: bool = False) -> GyoProviderProfile | None:
        query = "SELECT * FROM ai_provider_profiles WHERE id = ?"
        if not include_retired:
            query += " AND retired_at IS NULL"
        async with get_db_connection(self.settings.db_path_resolved) as conn:
            async with conn.execute(query, (provider_id,)) as cur:
                row = await cur.fetchone()
        return _provider_from_row(row) if row else None

    async def select_model(
        self,
        *,
        model_profile_id: str | None,
        route_mode: Literal["auto", "manual"],
        prompt: str,
        attachment_count: int,
    ) -> tuple[GyoProviderProfile, GyoModelProfile, str]:
        candidates = await self.select_model_candidates(
            model_profile_id=model_profile_id, route_mode=route_mode, prompt=prompt, attachment_count=attachment_count,
        )
        return candidates[0]

    async def select_model_candidates(
        self,
        *,
        model_profile_id: str | None,
        route_mode: Literal["auto", "manual"],
        prompt: str,
        attachment_count: int,
    ) -> list[tuple[GyoProviderProfile, GyoModelProfile, str]]:
        """Return a deterministic candidate list without silently invoking fallbacks.

        The orchestrator decides whether the locally opted-in fallback policy
        may advance beyond the primary.  Every candidate is enabled, credential
        ready, and supports the required capability before it is returned.
        """
        async with get_db_connection(self.settings.db_path_resolved) as conn:
            if route_mode == "manual":
                if not model_profile_id:
                    raise ValueError("Chế độ chọn tay cần một model hợp lệ.")
                async with conn.execute(
                    """SELECT m.*, p.display_name AS provider_display_name, p.provider_type, p.base_url,
                              p.credential_ref, p.enabled AS provider_enabled, p.retired_at AS provider_retired_at,
                              p.created_at AS provider_created_at, p.updated_at AS provider_updated_at
                       FROM ai_model_profiles m JOIN ai_provider_profiles p ON p.id = m.provider_profile_id
                       WHERE m.id = ?""", (model_profile_id,)
                ) as cur:
                    row = await cur.fetchone()
                if row is None or row["retired_at"] is not None or row["provider_retired_at"] is not None or not row["enabled"] or not row["provider_enabled"]:
                    raise ValueError("Model đã chọn không còn sẵn sàng.")
                primary = (*self._joined_profiles(row), "manual_selection")
                required_tier = primary[1].tier
                async with conn.execute(self._eligible_models_query(required_tier), (required_tier,)) as cur:
                    rows = await cur.fetchall()
            else:
                required_tier = self._required_tier(prompt, attachment_count)
                async with conn.execute(self._eligible_models_query(required_tier), (required_tier,)) as cur:
                    rows = await cur.fetchall()
                primary = None
        if not rows:
            raise ValueError("Chưa có model GYO nào được bật. Hãy thêm model trong Cài đặt.")
        candidates: list[tuple[GyoProviderProfile, GyoModelProfile, str]] = []
        if primary is not None:
            provider, model, reason = primary
            if not self.get_credential(provider.credential_ref):
                raise ValueError("Model đã chọn chưa có khóa hợp lệ trong Windows Credential Manager.")
            if required_tier == "vision" and "vision" not in model.capabilities:
                raise ValueError("Model đã chọn không hỗ trợ tệp đính kèm.")
            candidates.append(primary)
        for row in rows:
            provider, model = self._joined_profiles(row)
            if not self.get_credential(provider.credential_ref):
                continue
            if required_tier != "vision" or "vision" in model.capabilities:
                if any(existing[1].id == model.id for existing in candidates):
                    continue
                candidates.append((provider, model, f"auto_{required_tier}"))
        if candidates:
            return candidates
        raise ValueError("Không có model GYO đã bật và sẵn sàng cho yêu cầu này.")

    @staticmethod
    def _eligible_models_query(required_tier: ModelTier) -> str:
        # The order deliberately starts with the requested tier, then default,
        # then numeric priority. It is reused after a manual primary so the
        # fallback set remains predictable and explains itself in provenance.
        return """SELECT m.*, p.display_name AS provider_display_name, p.provider_type, p.base_url,
                         p.credential_ref, p.enabled AS provider_enabled, p.retired_at AS provider_retired_at,
                         p.created_at AS provider_created_at, p.updated_at AS provider_updated_at
                  FROM ai_model_profiles m JOIN ai_provider_profiles p ON p.id = m.provider_profile_id
                  WHERE m.enabled = 1 AND m.retired_at IS NULL AND p.enabled = 1 AND p.retired_at IS NULL
                  ORDER BY CASE WHEN m.tier = ? THEN 0 WHEN m.is_default = 1 THEN 1 ELSE 2 END,
                           m.priority ASC, m.created_at ASC, m.id ASC"""

    async def auto_fallback_enabled(self) -> bool:
        async with get_db_connection(self.settings.db_path_resolved) as conn:
            async with conn.execute("SELECT auto_fallback_enabled FROM gyo_routing_policy WHERE id = 1") as cur:
                row = await cur.fetchone()
        return bool(row["auto_fallback_enabled"]) if row else False

    @staticmethod
    def _required_tier(prompt: str, attachment_count: int) -> ModelTier:
        if attachment_count:
            return "vision"
        normalized = prompt.casefold()
        if len(prompt) > 2_000 or any(term in normalized for term in ("kế hoạch", "phân tích", "mã", "code", "đề xuất")):
            return "deep"
        if len(prompt) <= 350:
            return "fast"
        return "balanced"

    @staticmethod
    def _joined_profiles(row: aiosqlite.Row) -> tuple[GyoProviderProfile, GyoModelProfile]:
        provider = GyoProviderProfile(
            id=row["provider_profile_id"], display_name=row["provider_display_name"], provider_type=row["provider_type"],
            base_url=row["base_url"], credential_ref=row["credential_ref"], enabled=bool(row["provider_enabled"]),
            retired_at=row["provider_retired_at"], created_at=row["provider_created_at"], updated_at=row["provider_updated_at"],
        )
        return provider, _model_from_row(row)
