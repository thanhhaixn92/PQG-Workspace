from __future__ import annotations

import time

import pytest

from app.services.model_resilience import (
    AUTH,
    ModelAuthError,
    ModelCallable,
    ModelRateLimitError,
    ModelResilienceService,
    ModelServerError,
    ModelTimeoutError,
    RETRIABLE,
    UNKNOWN,
)


async def _ok(prompt: str, session_id: str) -> str:
    return f"response-{session_id}"


async def _429(prompt: str, session_id: str) -> str:
    raise ModelRateLimitError("Rate limited", status_code=429)


async def _500(prompt: str, session_id: str) -> str:
    raise ModelServerError("Internal server error", status_code=500)


async def _timeout(prompt: str, session_id: str) -> str:
    raise ModelTimeoutError("Request timed out")


async def _401(prompt: str, session_id: str) -> str:
    raise ModelAuthError("Invalid API key", status_code=401)


async def _403(prompt: str, session_id: str) -> str:
    raise ModelAuthError("Forbidden", status_code=403)


async def _fail_then_ok(_, __):
    """First call raises 429, subsequent calls succeed."""
    if not hasattr(_fail_then_ok, "_call_count"):
        _fail_then_ok._call_count = 0
    _fail_then_ok._call_count += 1
    if _fail_then_ok._call_count <= 1:
        raise ModelRateLimitError("Rate limited", status_code=429)
    return "retry-success"


def _reset_fail_then_ok():
    _fail_then_ok._call_count = 0


async def _always_fail_429(_, __):
    raise ModelRateLimitError("Always rate limited", status_code=429)


SERVICE_KWARGS = dict(
    max_retries_per_model=2,
    base_backoff_seconds=0.01,
    max_backoff_seconds=0.1,
    cooldown_seconds=0.01,
)


# =========================================================================
# CP8 Acceptance Criteria
# =========================================================================


class TestCriterion1_429CanFallbackAndSucceed:

    async def test_429_fallback_succeeds(self):
        primary = ModelCallable(id="primary", fn=_always_fail_429)
        fallback = ModelCallable(id="fallback", fn=_ok)
        svc = ModelResilienceService(
            models=[primary, fallback],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("hello", "s1")
        assert result.success
        assert result.response == "response-s1"
        assert len(result.attempt_chain) >= 1

    async def test_429_chain_records_all_attempts(self):
        primary = ModelCallable(id="primary", fn=_always_fail_429)
        fallback = ModelCallable(id="fallback", fn=_ok)
        svc = ModelResilienceService(
            models=[primary, fallback],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("x", "s2")
        assert result.success

        # primary: 3 attempts (max_retries=2 -> 0,1,2 = 3), then fallback: 1
        model_ids = [e.model_id for e in result.attempt_chain]
        assert model_ids.count("primary") == 3
        assert model_ids.count("fallback") == 1

        for e in result.attempt_chain:
            if e.model_id == "primary":
                assert e.status == RETRIABLE
                assert e.error is not None
            else:
                assert e.status == "success"

    async def test_429_immediate_fallback_if_retries_exhausted(self):
        primary = ModelCallable(id="primary", fn=_always_fail_429)
        fallback = ModelCallable(id="fallback", fn=_ok)
        svc = ModelResilienceService(
            models=[primary, fallback],
            max_retries_per_model=0,
            base_backoff_seconds=0.01,
        )
        result = await svc.execute_with_resilience("x", "s3")
        assert result.success
        assert result.response == "response-s3"
        assert len(result.attempt_chain) == 2
        assert result.attempt_chain[0].model_id == "primary"
        assert result.attempt_chain[1].model_id == "fallback"


class TestCriterion2_Timeout5xxCanRetryAndSucceed:

    async def test_500_retry_then_succeed(self):
        _reset_fail_then_ok()
        model = ModelCallable(id="hermes", fn=_fail_then_ok)
        svc = ModelResilienceService(
            models=[model],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("x", "s4")
        assert result.success
        assert result.response == "retry-success"
        assert len(result.attempt_chain) == 2

    async def test_timeout_retry_then_succeed(self):
        call_count = 0

        async def _timeout_then_ok(p, s):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise ModelTimeoutError("Timed out")
            return "timeout-retry-success"

        model = ModelCallable(id="hermes", fn=_timeout_then_ok)
        svc = ModelResilienceService(
            models=[model],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("x", "s5")
        assert result.success
        assert result.response == "timeout-retry-success"
        assert len(result.attempt_chain) == 2

    async def test_all_retries_exhausted_returns_error(self):
        model = ModelCallable(id="hermes", fn=_always_fail_429)
        svc = ModelResilienceService(
            models=[model],
            max_retries_per_model=1,
            base_backoff_seconds=0.01,
        )
        result = await svc.execute_with_resilience("x", "s6")
        assert not result.success
        assert len(result.attempt_chain) == 2  # attempt 0 + attempt 1


class TestCriterion3_401_403_StopsWithoutFallback:

    async def test_401_stops_immediately_no_retry(self):
        model = ModelCallable(id="hermes", fn=_401)
        svc = ModelResilienceService(
            models=[model],
            max_retries_per_model=5,
            base_backoff_seconds=0.01,
        )
        result = await svc.execute_with_resilience("x", "s7")
        assert not result.success
        assert result.error_category == AUTH
        assert len(result.attempt_chain) == 1

    async def test_403_stops_immediately_no_fallback(self):
        primary = ModelCallable(id="primary", fn=_403)
        fallback = ModelCallable(id="fallback", fn=_ok)
        svc = ModelResilienceService(
            models=[primary, fallback],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("x", "s8")
        assert not result.success
        assert result.error_category == AUTH
        # Only the auth error attempt, no fallback tried
        assert len(result.attempt_chain) == 1
        assert result.attempt_chain[0].model_id == "primary"

    async def test_auth_error_chain_entry(self):
        model = ModelCallable(id="hermes", fn=_401)
        svc = ModelResilienceService(
            models=[model],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("x", "s9")
        entry = result.attempt_chain[0]
        assert entry.model_id == "hermes"
        assert entry.status == AUTH
        assert entry.error is not None
        assert entry.started_at > 0
        assert entry.finished_at >= entry.started_at


class TestCriterion4_CooldownIsRespected:

    async def test_cooldown_delays_between_attempts(self):
        call_times = []

        async def _record_time(p, s):
            call_times.append(time.time())
            raise ModelRateLimitError("rate", 429)

        model = ModelCallable(id="hermes", fn=_record_time)
        svc = ModelResilienceService(
            models=[model],
            max_retries_per_model=1,
            base_backoff_seconds=0.01,
            max_backoff_seconds=0.02,
            cooldown_seconds=0.1,
        )
        result = await svc.execute_with_resilience("x", "s10")
        assert not result.success
        assert len(call_times) == 2
        gap = call_times[1] - call_times[0]
        # The gap should be at least cooldown + backoff
        assert gap >= 0.1, f"Gap {gap:.3f}s < 0.1s cooldown"

    async def test_cooldown_respected_across_different_models(self):
        primary_calls = []
        fallback_calls = []

        async def _primary_fn(p, s):
            primary_calls.append(time.time())
            raise ModelRateLimitError("rate", 429)

        async def _fallback_fn(p, s):
            fallback_calls.append(time.time())
            return "ok"

        primary = ModelCallable(id="primary", fn=_primary_fn)
        fallback = ModelCallable(id="fallback", fn=_fallback_fn)
        svc = ModelResilienceService(
            models=[primary, fallback],
            max_retries_per_model=0,
            base_backoff_seconds=0.01,
            cooldown_seconds=0.0,  # No cooldown so fallback runs immediately
        )
        result = await svc.execute_with_resilience("x", "s11")
        assert result.success
        assert len(primary_calls) == 1
        assert len(fallback_calls) == 1


class TestCriterion5_AttemptChainIsRecorded:

    async def test_chain_contains_all_fields(self):
        model = ModelCallable(id="hermes", fn=_ok)
        svc = ModelResilienceService(
            models=[model],
            **SERVICE_KWARGS,
        )
        result = await svc.execute_with_resilience("x", "s12")
        assert result.success
        assert len(result.attempt_chain) == 1
        entry = result.attempt_chain[0]
        assert entry.model_id == "hermes"
        assert entry.status == "success"
        assert entry.error is None
        assert entry.started_at > 0
        assert entry.finished_at >= entry.started_at

    async def test_chain_includes_failed_attempts(self):
        async def _fail_then_ok_chain(p, s):
            if not hasattr(_fail_then_ok_chain, "_n"):
                _fail_then_ok_chain._n = 0
            _fail_then_ok_chain._n += 1
            if _fail_then_ok_chain._n <= 2:
                raise ModelServerError("Server error", status_code=502)
            return "final-success"

        _fail_then_ok_chain._n = 0
        model = ModelCallable(id="hermes", fn=_fail_then_ok_chain)
        svc = ModelResilienceService(
            models=[model],
            max_retries_per_model=2,
            base_backoff_seconds=0.01,
            cooldown_seconds=0.0,
        )
        result = await svc.execute_with_resilience("x", "s13")
        assert result.success
        assert len(result.attempt_chain) == 3
        assert result.attempt_chain[0].status == RETRIABLE
        assert result.attempt_chain[0].error is not None
        assert result.attempt_chain[1].status == RETRIABLE
        assert result.attempt_chain[1].error is not None
        assert result.attempt_chain[2].status == "success"
        assert result.attempt_chain[2].error is None

    async def test_all_models_exhausted_chain(self):
        primary = ModelCallable(id="primary", fn=_always_fail_429)
        fallback = ModelCallable(id="fallback", fn=_always_fail_429)
        svc = ModelResilienceService(
            models=[primary, fallback],
            max_retries_per_model=1,
            base_backoff_seconds=0.01,
            cooldown_seconds=0.0,
        )
        result = await svc.execute_with_resilience("x", "s14")
        assert not result.success
        # primary 2 attempts + fallback 2 attempts = 4
        assert len(result.attempt_chain) == 4
        for entry in result.attempt_chain:
            assert entry.status == RETRIABLE
            assert entry.error is not None

    async def test_chain_timing_fields(self):
        model = ModelCallable(id="hermes", fn=_ok)
        svc = ModelResilienceService(
            models=[model],
            **SERVICE_KWARGS,
        )
        t0 = time.time()
        result = await svc.execute_with_resilience("x", "s15")
        t1 = time.time()
        entry = result.attempt_chain[0]
        assert entry.started_at >= t0
        assert entry.finished_at <= t1
        assert entry.finished_at >= entry.started_at
