from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from app.settings import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions – status-code-aware so the resilience layer can classify
# ---------------------------------------------------------------------------


class ModelError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ModelAuthError(ModelError):
    """401 / 403 — unrecoverable; must NOT retry or fallback."""


class ModelRateLimitError(ModelError):
    """429 — retriable with back-off."""


class ModelServerError(ModelError):
    """5xx — retriable."""


class ModelTimeoutError(ModelError):
    """Timeout — retriable."""


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

RETRIABLE = "retriable"
AUTH = "auth"
UNKNOWN = "unknown"


def classify_error(exc: Exception) -> str:
    if isinstance(exc, (ModelRateLimitError, ModelServerError, ModelTimeoutError)):
        return RETRIABLE
    if isinstance(exc, ModelAuthError):
        return AUTH
    if isinstance(exc, ModelError):
        return UNKNOWN
    return UNKNOWN


# ---------------------------------------------------------------------------
# Model callable – a named async function that sends a prompt
# ---------------------------------------------------------------------------


@dataclass
class ModelCallable:
    id: str
    fn: Callable[[str, str], Awaitable[str]]


# ---------------------------------------------------------------------------
# Attempt-chain record
# ---------------------------------------------------------------------------


@dataclass
class AttemptEntry:
    model_id: str
    status: str
    error: Optional[str] = None
    started_at: float = 0.0
    finished_at: float = 0.0


@dataclass
class ResilienceResult:
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    error_category: Optional[str] = None
    attempt_chain: list[AttemptEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core resilience service
# ---------------------------------------------------------------------------


class ModelResilienceService:

    def __init__(
        self,
        models: list[ModelCallable],
        max_retries_per_model: int = 2,
        base_backoff_seconds: float = 2.0,
        max_backoff_seconds: float = 30.0,
        cooldown_seconds: float = 5.0,
    ) -> None:
        self._models = models
        self._max_retries = max_retries_per_model
        self._base_backoff = base_backoff_seconds
        self._max_backoff = max_backoff_seconds
        self._cooldown = cooldown_seconds
        self._last_attempt_time: dict[str, float] = {}

    @classmethod
    def from_settings(
        cls,
        models: list[ModelCallable],
        settings: Settings,
    ) -> ModelResilienceService:
        return cls(
            models=models,
            max_retries_per_model=settings.model_fallback_max_retries,
            base_backoff_seconds=settings.model_fallback_base_backoff_seconds,
            max_backoff_seconds=settings.model_fallback_max_backoff_seconds,
            cooldown_seconds=settings.model_fallback_cooldown_seconds,
        )

    async def execute_with_resilience(
        self,
        prompt: str,
        session_id: str,
    ) -> ResilienceResult:
        chain: list[AttemptEntry] = []

        for model in self._models:
            for attempt in range(self._max_retries + 1):
                await self._respect_cooldown(model.id)

                entry = AttemptEntry(
                    model_id=model.id,
                    status="",
                    started_at=time.time(),
                )
                try:
                    response = await model.fn(prompt, session_id)
                    entry.status = "success"
                    entry.finished_at = time.time()
                    chain.append(entry)
                    self._record_attempt(model.id)
                    return ResilienceResult(
                        success=True,
                        response=response,
                        attempt_chain=chain,
                    )
                except Exception as exc:
                    entry.finished_at = time.time()
                    entry.error = str(exc)
                    cat = classify_error(exc)
                    entry.status = cat
                    chain.append(entry)
                    self._record_attempt(model.id)

                    if cat == AUTH:
                        return ResilienceResult(
                            success=False,
                            error=str(exc),
                            error_category=cat,
                            attempt_chain=chain,
                        )

                    if cat == RETRIABLE and attempt < self._max_retries:
                        backoff = min(
                            self._base_backoff * (2**attempt),
                            self._max_backoff,
                        )
                        logger.warning(
                            "Model %s attempt %d retriable error, "
                            "backing off %.1fs: %s",
                            model.id,
                            attempt + 1,
                            backoff,
                            exc,
                        )
                        await asyncio.sleep(backoff)
                    elif cat == RETRIABLE:
                        logger.warning(
                            "Model %s exhausted retries, falling back: %s",
                            model.id,
                            exc,
                        )
                        break
                    else:
                        if attempt < self._max_retries:
                            backoff = min(
                                self._base_backoff * (2**attempt),
                                self._max_backoff,
                            )
                            await asyncio.sleep(backoff)
                        else:
                            break

        return ResilienceResult(
            success=False,
            error=chain[-1].error if chain else "All models exhausted",
            error_category=chain[-1].status if chain else UNKNOWN,
            attempt_chain=chain,
        )

    async def _respect_cooldown(self, model_id: str) -> None:
        last = self._last_attempt_time.get(model_id)
        if last is not None:
            elapsed = time.time() - last
            if elapsed < self._cooldown:
                wait = self._cooldown - elapsed
                logger.debug("Cooldown for %s: waiting %.1fs", model_id, wait)
                await asyncio.sleep(wait)

    def _record_attempt(self, model_id: str) -> None:
        self._last_attempt_time[model_id] = time.time()
