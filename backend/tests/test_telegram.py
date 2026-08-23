from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.connection import open_db
from app.main import create_app
from app.settings import Settings
from app.dependencies import get_db, get_settings


def _hmac_sign(secret: str, body: bytes) -> str:
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={expected}"


TELEGRAM_SECRET = "cp7-test-secret"


@pytest_asyncio.fixture()
async def tg_app(migrated_db_path):
    test_settings = Settings(
        db_path=str(migrated_db_path),
        cors_origins=["http://localhost:5173"],
        telegram_webhook_secret=TELEGRAM_SECRET,
        telegram_allowlist="12345,67890",
        telegram_callback_token_ttl_seconds=3600,
        log_level="WARNING",
    )
    application = create_app(settings_override=test_settings)
    application.dependency_overrides[get_settings] = lambda: test_settings

    from app.db.connection import get_db_connection

    async def _override_db():
        async with get_db_connection(migrated_db_path) as conn:
            yield conn

    application.dependency_overrides[get_db] = _override_db
    return application


@pytest_asyncio.fixture()
async def tg_client(tg_app):
    async with AsyncClient(
        transport=ASGITransport(app=tg_app, client=("127.0.0.1", 12345)),
        base_url="http://testserver",
    ) as ac:
        yield ac


async def _insert_expired_token(migrated_db_path, token: str, task_id: str):
    conn = await open_db(migrated_db_path)
    try:
        now = int(time.time())
        await conn.execute(
            """INSERT INTO telegram_callback_tokens (token, task_id, action_type, status, expires_at, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?)""",
            (token, task_id, "approval", now - 1, now - 3600),
        )
        await conn.commit()
    finally:
        await conn.close()


# =========================================================================
# CP7 Acceptance Criteria
# =========================================================================


async def _post_webhook(client, body: dict, secret: str | None = TELEGRAM_SECRET):
    payload = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-HMAC-Signature"] = _hmac_sign(secret, payload)
    return await client.post("/api/telegram/webhook", content=payload, headers=headers)


class TestTelegramWebhook:

    # --- Criterion 1: Invalid HMAC → 401 ---

    async def test_missing_hmac_returns_401(self, tg_client):
        resp = await _post_webhook(tg_client, {"update_id": 1}, secret=None)
        assert resp.status_code == 401
        assert "HMAC" in resp.json()["detail"]

    async def test_wrong_hmac_returns_401(self, tg_client):
        resp = await _post_webhook(tg_client, {"update_id": 1}, secret="wrong-secret")
        assert resp.status_code == 401
        assert "HMAC" in resp.json()["detail"]

    # --- Criterion 2: User outside allowlist → 403 ---

    async def test_user_not_in_allowlist_returns_403(self, tg_client):
        body = {
            "update_id": 10,
            "message_id": "100",
            "from_id": 99999,
            "text": "hello",
        }
        resp = await _post_webhook(tg_client, body)
        assert resp.status_code == 403
        assert "allowlist" in resp.json()["detail"].lower()

    async def test_user_in_allowlist_succeeds(self, tg_client):
        body = {
            "update_id": 20,
            "message_id": "200",
            "from_id": 12345,
            "text": "/start",
        }
        resp = await _post_webhook(tg_client, body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert not data["duplicate"]
        assert data["task_id"] is not None

    # --- Criterion 3: Retried update (duplicate message_id) → no duplicate task ---

    async def test_duplicate_update_returns_existing_task(self, tg_client):
        body = {
            "update_id": 30,
            "message_id": "300",
            "from_id": 12345,
            "text": "duplicate test",
        }
        resp1 = await _post_webhook(tg_client, body)
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["status"] == "ok"
        assert not data1["duplicate"]

        resp2 = await _post_webhook(tg_client, body)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "duplicate"
        assert data2["duplicate"]
        assert data2["task_id"] == data1["task_id"]

    async def test_same_message_id_from_different_updates_remains_distinct(self, tg_client):
        """Telegram message ids are chat-local; update_id is the durable identity."""
        first = await _post_webhook(tg_client, {
            "update_id": 31,
            "message_id": "shared-message-id",
            "from_id": 12345,
            "text": "first chat message",
        })
        second = await _post_webhook(tg_client, {
            "update_id": 32,
            "message_id": "shared-message-id",
            "from_id": 67890,
            "text": "second chat message",
        })
        assert first.status_code == second.status_code == 200
        assert not first.json()["duplicate"]
        assert not second.json()["duplicate"]
        assert first.json()["task_id"] != second.json()["task_id"]

    # --- Criterion 5: Callback token lifecycle ---

    async def test_callback_token_returned_when_requested(self, tg_client):
        body = {
            "update_id": 40,
            "message_id": "400",
            "from_id": 12345,
            "text": "needs callback",
            "await_callback": True,
        }
        resp = await _post_webhook(tg_client, body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["callback_token"] is not None
        assert data["callback_token"].startswith("cb-")


class TestTelegramCallback:

    async def _post_callback(self, client, body: dict, secret: str | None = TELEGRAM_SECRET):
        payload = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if secret is not None:
            headers["X-HMAC-Signature"] = _hmac_sign(secret, payload)
        return await client.post("/api/telegram/callback", content=payload, headers=headers)

    # --- Criterion 1: Invalid HMAC on callback ---

    async def test_callback_missing_hmac_returns_401(self, tg_client):
        resp = await self._post_callback(tg_client, {"token": "cb-xxx"}, secret=None)
        assert resp.status_code == 401

    async def test_callback_wrong_hmac_returns_401(self, tg_client):
        resp = await self._post_callback(tg_client, {"token": "cb-xxx"}, secret="wrong")
        assert resp.status_code == 401

    # --- Criterion 4: Reused callback token → 409 ---

    async def test_reused_callback_token_returns_409(self, tg_client, migrated_db_path):
        body = {
            "update_id": 50,
            "message_id": "500",
            "from_id": 12345,
            "text": "approval needed",
            "await_callback": True,
        }
        webhook_resp = await _post_webhook(tg_client, body)
        token = webhook_resp.json()["callback_token"]

        resp1 = await self._post_callback(tg_client, {"token": token})
        assert resp1.status_code == 200

        resp2 = await self._post_callback(tg_client, {"token": token})
        assert resp2.status_code == 409
        assert "reused" in resp2.json()["detail"].lower()

    async def test_concurrent_callback_has_exactly_one_winner(self, tg_client):
        webhook_resp = await _post_webhook(tg_client, {
            "update_id": 51,
            "message_id": "501",
            "from_id": 12345,
            "text": "race callback",
            "await_callback": True,
        })
        token = webhook_resp.json()["callback_token"]

        first, second = await asyncio.gather(
            self._post_callback(tg_client, {"token": token}),
            self._post_callback(tg_client, {"token": token}),
        )

        assert sorted((first.status_code, second.status_code)) == [200, 409]

    # --- Criterion 5: Expired callback token → 410 ---

    async def test_expired_callback_token_returns_410(self, tg_client, migrated_db_path):
        expired_token = "cb-expired-test-token"
        task_id = "task-expired-test"

        conn = await open_db(migrated_db_path)
        try:
            now = int(time.time())
            await conn.execute(
                "INSERT OR IGNORE INTO tasks (id, status, task_type, created_at, updated_at) VALUES (?, 'queued', 'telegram', ?, ?)",
                (task_id, now, now),
            )
            await conn.commit()
        finally:
            await conn.close()

        await _insert_expired_token(migrated_db_path, expired_token, task_id)

        resp = await self._post_callback(tg_client, {"token": expired_token})
        assert resp.status_code == 410
        assert "expired" in resp.json()["detail"].lower()

    async def test_nonexistent_callback_token_returns_404(self, tg_client):
        resp = await self._post_callback(tg_client, {"token": "cb-nonexistent"})
        assert resp.status_code == 404

    async def test_valid_callback_token_succeeds(self, tg_client):
        body = {
            "update_id": 60,
            "message_id": "600",
            "from_id": 12345,
            "text": "approve me",
            "await_callback": True,
        }
        webhook_resp = await _post_webhook(tg_client, body)
        token = webhook_resp.json()["callback_token"]

        resp = await self._post_callback(tg_client, {"token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["action"] == "approval"
        assert data["task_id"] is not None
