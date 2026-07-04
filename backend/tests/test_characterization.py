"""Characterization tests — lock CURRENT behavior before refactoring.

These tests capture the existing contract of every API endpoint and key service.
They MUST pass on the current codebase without modification.
Any refactored code MUST produce the same observable behavior.

Baseline recorded: 2026-07-04
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from app.api.approvals import pending_approvals, register_pending_approval, wait_for_approval
from app.api.runtime import check_hermes_preflight
from app.api.sessions import _compose_hermes_prompt, _is_publishing_prompt
from app.db.connection import get_db_connection
from app.dependencies import get_db, get_settings
from app.main import create_app
from app.mcp.server import mcp_session_id_var
from app.services.audit import log_audit_event
from app.services.content_quality import check_output_file_quality, enrich_desktop_file_blocks
from app.services.context import CONTEXT_VERSION_CACHE, build_context, get_context_version
from app.services.n8n_webhook import validate_n8n_workflow
from app.services.sandbox import MAX_FILE_SIZE, get_workspace_path, resolve_and_validate_path
from app.settings import Settings


# =========================================================================
# Sync TestClient fixtures (matching existing test patterns)
# =========================================================================


@pytest.fixture
def sync_client(tmp_path) -> TestClient:
    db_path = tmp_path / "test_char.db"
    settings = Settings(
        db_path=str(db_path),
        hermes_dev_mock=True,
        log_level="WARNING",
    )
    app = create_app(settings_override=settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sync_client_real_path(tmp_path) -> TestClient:
    db_path = tmp_path / "test_char.db"
    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(
        db_path=str(db_path),
        default_workspace_root=str(tmp_path / "auto"),
        hermes_executable_path=sys.executable,
        hermes_args=[str(Path("tests/mock_hermes.py").absolute())],
        hermes_dev_mock=True,
    )
    app = create_app(settings_override=settings)
    app.state.test_workspace = str(ws)
    client = TestClient(app)
    client.__enter__()
    yield client
    # Small delay so aiosqlite worker threads can deliver pending
    # callbacks before the event loop is closed. The race is between
    # the thread's call_soon_threadsafe and loop.close() during
    # TestClient.__exit__ -- benign but noisy.
    import time
    time.sleep(0.05)
    client.__exit__(None, None, None)


@pytest.fixture
def sync_client_use_task_api_real_path(tmp_path) -> TestClient:
    db_path = tmp_path / "test_task_api.db"
    ws = tmp_path / "ws"
    ws.mkdir()
    settings = Settings(
        db_path=str(db_path),
        default_workspace_root=str(tmp_path / "auto"),
        hermes_executable_path=sys.executable,
        hermes_args=[str(Path("tests/mock_hermes.py").absolute())],
        hermes_dev_mock=True,
        use_task_api=True,
    )
    app = create_app(settings_override=settings)
    app.state.test_workspace = str(ws)
    client = TestClient(app)
    client.__enter__()
    yield client
    import time
    time.sleep(0.05)
    client.__exit__(None, None, None)


# =========================================================================
# Session Lifecycle
# =========================================================================


class TestSessionLifecycle:

    def test_create_session_returns_201_with_id(self, sync_client: TestClient) -> None:
        resp = sync_client.post("/api/sessions", json={"title": "Test", "workspace_path": "/tmp"})
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["title"] == "Test"
        assert data["archived"] == 0

    def test_create_session_auto_creates_workspace(self, sync_client: TestClient) -> None:
        resp = sync_client.post("/api/sessions", json={"title": "Auto WS"})
        assert resp.status_code == 201
        data = resp.json()
        ws = Path(data["workspace_path"])
        assert ws.exists()
        assert (ws / "outputs").exists()

    def test_list_sessions_returns_only_non_archived(self, sync_client: TestClient) -> None:
        s1 = sync_client.post("/api/sessions", json={"title": "S1", "workspace_path": "/tmp"}).json()
        s2 = sync_client.post("/api/sessions", json={"title": "S2", "workspace_path": "/tmp"}).json()
        sync_client.delete(f"/api/sessions/{s2['id']}")
        sessions = sync_client.get("/api/sessions").json()
        ids = {s["id"] for s in sessions}
        assert s1["id"] in ids
        assert s2["id"] not in ids

    def test_update_session_title(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Old", "workspace_path": "/tmp"}).json()
        resp = sync_client.patch(f"/api/sessions/{s['id']}", json={"title": "New"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "New"

    def test_update_session_empty_title_rejected(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Test", "workspace_path": "/tmp"}).json()
        resp = sync_client.patch(f"/api/sessions/{s['id']}", json={"title": ""})
        assert resp.status_code == 400

    def test_archive_session_soft_delete(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Del", "workspace_path": "/tmp"}).json()
        resp = sync_client.delete(f"/api/sessions/{s['id']}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

        async def _check():
            async with aiosqlite.connect(
                sync_client.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute("SELECT archived FROM sessions WHERE id=?", (s["id"],)) as cur:
                    row = await cur.fetchone()
                    assert row[0] == 1
        asyncio.run(_check())

    def test_cleanup_smoke_tests(self, sync_client: TestClient) -> None:
        s1 = sync_client.post("/api/sessions", json={"title": "Smoke Test 1", "workspace_path": "/tmp"}).json()
        s2 = sync_client.post("/api/sessions", json={"title": "Real Work", "workspace_path": "/tmp"}).json()
        resp = sync_client.post("/api/sessions/cleanup-smoke-tests")
        assert resp.status_code == 200
        assert resp.json()["archived_count"] == 1
        sessions = sync_client.get("/api/sessions").json()
        ids = {s["id"] for s in sessions}
        assert s1["id"] not in ids
        assert s2["id"] in ids

    def test_get_session_messages(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Msg", "workspace_path": "/tmp"}).json()
        resp = sync_client.get(f"/api/sessions/{s['id']}/messages")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_session_messages_not_found(self, sync_client: TestClient) -> None:
        resp = sync_client.get("/api/sessions/nonexistent/messages")
        assert resp.status_code == 404

    def test_get_session_memory(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Mem", "workspace_path": "/tmp"}).json()
        resp = sync_client.get(f"/api/sessions/{s['id']}/memory")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# =========================================================================
# Prompt Submission & SSE
# =========================================================================


class TestPromptSubmission:

    def test_submit_prompt_returns_202_with_queued_task(self, sync_client_real_path: TestClient) -> None:
        s = sync_client_real_path.post("/api/sessions", json={"title": "P", "workspace_path": "/tmp"}).json()
        resp = sync_client_real_path.post(f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"})
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"
        assert data["session_id"] == s["id"]
        assert "id" in data

    def test_submit_prompt_completes_and_streams_events(self, sync_client_real_path: TestClient) -> None:
        s = sync_client_real_path.post("/api/sessions", json={"title": "P2", "workspace_path": "/tmp"}).json()
        resp = sync_client_real_path.post(f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"})
        task_id = resp.json()["id"]
        events = []
        with sync_client_real_path.stream("GET", f"/api/sessions/{s['id']}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[5:].strip())
                if line.startswith("event: done"):
                    break
        assert len(events) >= 1

        async def _check():
            await asyncio.sleep(0.1)
            async with aiosqlite.connect(
                sync_client_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute("SELECT status FROM task_runs WHERE id=?", (task_id,)) as cur:
                    row = await cur.fetchone()
                    assert row[0] == "completed"
        asyncio.run(_check())

    def test_submit_prompt_invalid_session_returns_404(self, sync_client_real_path: TestClient) -> None:
        resp = sync_client_real_path.post("/api/sessions/bad-id/prompt", json={"prompt": "Hi"})
        assert resp.status_code == 404

    def test_sse_single_subscriber_enforced(self, sync_client_real_path: TestClient) -> None:
        s = sync_client_real_path.post("/api/sessions", json={"title": "SSE", "workspace_path": "/tmp"}).json()
        from app.services.event_bus import event_bus
        event_bus._subscribers.add(s["id"])
        resp = sync_client_real_path.get(f"/api/sessions/{s['id']}/events")
        assert resp.status_code == 409
        event_bus._subscribers.discard(s["id"])

    def test_task_run_detail_is_session_scoped(self, sync_client_real_path: TestClient) -> None:
        s1 = sync_client_real_path.post("/api/sessions", json={"title": "T1", "workspace_path": "/tmp"}).json()
        s2 = sync_client_real_path.post("/api/sessions", json={"title": "T2", "workspace_path": "/tmp"}).json()

        async def _seed():
            async with aiosqlite.connect(
                sync_client_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                await db.execute(
                    "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?,?,?, unixepoch())",
                    ("task-scoped", s1["id"], "completed"),
                )
                await db.commit()
        asyncio.run(_seed())
        own = sync_client_real_path.get(f"/api/sessions/{s1['id']}/task-runs/task-scoped")
        assert own.status_code == 200
        wrong = sync_client_real_path.get(f"/api/sessions/{s2['id']}/task-runs/task-scoped")
        assert wrong.status_code == 404


# =========================================================================
# Hermes Failure Handling
# =========================================================================


class TestHermesFailure:

    def test_preflight_blocks_missing_executable(self, tmp_path: Path) -> None:
        settings = Settings(
            db_path=str(tmp_path / "test.db"),
            hermes_executable_path="does-not-exist",
            hermes_dev_mock=False,
        )
        app = create_app(settings_override=settings)
        with TestClient(app) as c:
            s = c.post("/api/sessions", json={"title": "X", "workspace_path": "/tmp"}).json()
            r = c.post(f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hi"})
            assert r.status_code == 503
            assert "Không tìm thấy" in r.json()["detail"]

    def test_submit_prompt_hermes_spawn_failure_produces_error_event(
        self, sync_client_real_path: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setenv("HERMES_AUTH_READY", "1")
        from app.api.runtime import _run_hermes_doctor_sync
        monkeypatch.setattr("app.api.runtime._run_hermes_doctor_sync", lambda _: True)
        sync_client_real_path.app.state.hermes_client.settings.hermes_dev_mock = False
        s = sync_client_real_path.post("/api/sessions", json={"title": "F", "workspace_path": "/tmp"}).json()
        resp = sync_client_real_path.post(f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"})
        assert resp.status_code == 202
        has_error = False
        with sync_client_real_path.stream("GET", f"/api/sessions/{s['id']}/events") as stream:
            for line in stream.iter_lines():
                if line.startswith("event: error"):
                    has_error = True
                if line.startswith("event: done") or line.startswith("event: error"):
                    break
        assert has_error

        async def _check():
            await asyncio.sleep(0.1)
            async with aiosqlite.connect(
                sync_client_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute("SELECT action FROM audit_events WHERE session_id=?", (s["id"],)) as cur:
                    actions = [r[0] for r in await cur.fetchall()]
                    assert "task_run.failed" in actions
                    assert "hermes.error" in actions
        asyncio.run(_check())


# =========================================================================
# Approval Flow
# =========================================================================


class TestApprovalFlow:

    @pytest.mark.parametrize(
        "decision,expected_action",
        [
            ("allow_once", "approval.allowed_once"),
            ("allow_for_session", "approval.allowed_for_session"),
            ("deny", "approval.denied"),
        ],
    )
    def test_approval_decision_types(self, sync_client: TestClient, decision: str, expected_action: str) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Appr", "workspace_path": "/tmp"}).json()
        appr_id = f"appr-{uuid.uuid4().hex[:8]}"
        s_override = sync_client.app.dependency_overrides[get_settings]()
        asyncio.run(register_pending_approval(
            approval_id=appr_id, session_id=s["id"],
            action="execute", target="test", settings=s_override,
        ))
        resp = sync_client.post(f"/api/approvals/{appr_id}", json={"decision": decision})
        assert resp.status_code == 200
        assert resp.json()["decision"] == decision
        assert resp.json()["audit_action"] == expected_action

    def test_approval_unknown_id_returns_404(self, sync_client: TestClient) -> None:
        resp = sync_client.post("/api/approvals/nonexistent", json={"decision": "allow_once"})
        assert resp.status_code == 404

    def test_high_risk_rejects_allow_for_session(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "Risky", "workspace_path": "/tmp"}).json()
        appr_id = "appr-risky"
        s_override = sync_client.app.dependency_overrides[get_settings]()
        asyncio.run(register_pending_approval(
            approval_id=appr_id, session_id=s["id"],
            action="hermes.permission", target="script",
            risk_level="external_or_destructive", settings=s_override,
        ))
        resp = sync_client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_for_session"})
        assert resp.status_code == 400

    def test_approval_missing_waiter_returns_409(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "W", "workspace_path": "/tmp"}).json()
        appr_id = "appr-waiter"
        s_override = sync_client.app.dependency_overrides[get_settings]()
        asyncio.run(register_pending_approval(
            approval_id=appr_id, session_id=s["id"],
            action="write", target="test", settings=s_override,
        ))
        pending_approvals.clear()
        resp = sync_client.post(f"/api/approvals/{appr_id}", json={"decision": "allow_once"})
        assert resp.status_code == 409

    def test_approval_timeout_marks_expired(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "T", "workspace_path": "/tmp"}).json()
        appr_id = "appr-timeout"
        s_override = sync_client.app.dependency_overrides[get_settings]()
        asyncio.run(register_pending_approval(
            approval_id=appr_id, session_id=s["id"],
            action="write", target="test", settings=s_override, timeout_seconds=1,
        ))
        decision = asyncio.run(wait_for_approval(appr_id, timeout_seconds=0.01))
        assert decision == "deny"


# =========================================================================
# Workspace Sandbox
# =========================================================================


class TestWorkspaceSandbox:

    def test_resolve_and_validate_path_in_workspace(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "file.txt").write_text("ok")
        resolved = resolve_and_validate_path(ws, "file.txt")
        assert resolved == (ws / "file.txt").resolve()

    def test_traversal_relative_rejected(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        (tmp_path / "secret.txt").write_text("secret")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            resolve_and_validate_path(ws, "../secret.txt")
        assert "Path traversal" in exc.value.detail

    def test_absolute_path_outside_rejected(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            resolve_and_validate_path(ws, str(tmp_path / "secret.txt"))
        assert "Path traversal" in exc.value.detail

    def test_binary_file_rejected(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        f = ws / "data.bin"
        f.write_bytes(b"\x00\x01\x02\x03")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            resolve_and_validate_path(ws, "data.bin", check_binary=True)
        assert "Binary" in exc.value.detail

    def test_file_size_limit_enforced(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        big = ws / "big.txt"
        with open(big, "wb") as f:
            f.seek(MAX_FILE_SIZE + 100)
            f.write(b"x")
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            resolve_and_validate_path(ws, "big.txt")
        assert "1 MB" in exc.value.detail


# =========================================================================
# n8n Webhook
# =========================================================================


class TestN8nWebhook:

    def test_validate_allowed_workflow(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("N8N_WEBHOOK_SECRET", "test-secret")
        settings = Settings(db_path=str(tmp_path / "n8n.db"))
        url = validate_n8n_workflow(settings, "echo")
        assert "hermes-echo" in url

    def test_validate_disallowed_workflow(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("N8N_WEBHOOK_SECRET", "test-secret")
        settings = Settings(db_path=str(tmp_path / "n8n.db"))
        with pytest.raises(ValueError, match="not in the allowlist"):
            validate_n8n_workflow(settings, "malicious")

    def test_docker_compose_validation(self) -> None:
        import yaml
        compose_path = Path(__file__).parent.parent.parent / "infra" / "n8n" / "docker-compose.yml"
        assert compose_path.exists()
        with open(compose_path, encoding="utf-8") as f:
            compose = yaml.safe_load(f)
        svc = compose["services"]["n8n"]
        assert svc["image"] == "n8nio/n8n:1.70.0"
        ports = svc.get("ports", [])
        assert any(p.startswith("127.0.0.1:") for p in ports)
        env = svc.get("environment", [])
        assert any("N8N_ENCRYPTION_KEY" in e for e in env)
        assert any("HERMES_N8N_WEBHOOK_SECRET" in e for e in env)


# =========================================================================
# Content Quality Gate
# =========================================================================


class TestContentQuality:

    def test_html_chua_dat_labeled(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        f = ws / "a.html"
        f.write_text(
            "<!doctype html><html><body><p>Nội dung mẫu đủ dài để vượt qua kiểm tra độ dài tối thiểu.</p></body></html>",
            encoding="utf-8",
        )
        result = check_output_file_quality(f, ws, tmp_path)
        assert result.status == "needs_review"
        assert result.label == "HTML chưa đạt"

    def test_html_missing_utf8_sources_and_suspicious_phrase(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        f = ws / "outputs" / "article.html"
        f.parent.mkdir()
        f.write_text(
            "<!doctype html><html><head></head><body>"
            "<p>kênh thông lương</p><p>Xi măng ASEAN</p>"
            "<p>Đây là nội dung mẫu đủ dài để vượt qua kiểm tra độ dài tối thiểu cho bài viết.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        result = check_output_file_quality(f, ws, tmp_path)
        assert result.status == "needs_review"
        assert result.label == "HTML chưa đạt"
        assert any("thông thương" in i for i in result.issues)

    def test_suspicious_phrases_detected_in_any_file(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        f = ws / "outputs" / "note.txt"
        f.parent.mkdir()
        f.write_text("Ghi chú về thông lương.", encoding="utf-8")
        result = check_output_file_quality(f, ws, tmp_path)
        assert result.status == "needs_review"
        assert any("thông thương" in i for i in result.issues)

    def test_strong_claims_without_sources_flagged(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        f = ws / "c.html"
        f.write_text(
            '<!doctype html><html><head><meta charset="utf-8"></head>'
            "<body><h1>Tin</h1><p>Chắc chắn sự thật là không thể phủ nhận. Rõ ràng chứng minh rằng đúng.</p></body></html>",
            encoding="utf-8",
        )
        result = check_output_file_quality(f, ws, tmp_path)
        assert any("nhận định mạnh" in i for i in result.issues)

    def test_enrich_desktop_file_block_adds_quality_metadata(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        fp = ws / "article.html"
        fp.write_text("<article>Không có nguồn</article>", encoding="utf-8")
        response = (
            "File:\n```desktop-local-file\n"
            f'{{"localPath":"{str(fp).replace(chr(92), chr(92) * 2)}","fileName":"article.html"}}\n'
            "```"
        )
        enriched, results = enrich_desktop_file_blocks(response, ws, tmp_path)
        assert len(results) == 1
        assert '"contentQuality"' in enriched


# =========================================================================
# Context Injection
# =========================================================================


class TestContextInjection:

    def test_compose_includes_guidance(self) -> None:
        prompt = _compose_hermes_prompt("Hello")
        assert "=== HERMES LOCAL STACK RESPONSE GUIDE ===" in prompt
        assert "Kết quả" in prompt
        assert "File đầu ra" in prompt
        assert "Cần kiểm tra" in prompt
        assert "Bước tiếp theo" in prompt
        assert prompt.endswith("=== USER PROMPT ===\nHello")

    def test_compose_includes_context(self) -> None:
        prompt = _compose_hermes_prompt("Hi", context_str="MEMORY: use Vietnamese")
        assert "MEMORY: use Vietnamese" in prompt

    def test_compose_includes_version(self) -> None:
        prompt = _compose_hermes_prompt("Hi", context_version=5)
        assert "=== CONTEXT VERSION: 5 ===" in prompt

    def test_publishing_keywords_detected(self) -> None:
        assert _is_publishing_prompt("viết bài báo mới")
        assert _is_publishing_prompt("đăng website bài mới")
        assert _is_publishing_prompt("soạn thảo bản tin")
        assert _is_publishing_prompt("tạo file word báo cáo")
        assert not _is_publishing_prompt("chào bạn, khỏe không")

    def test_publishing_prompt_adds_extra_guidance(self) -> None:
        prompt = _compose_hermes_prompt("viết bài báo về AI")
        assert "Tựa đề" in prompt
        assert "Lead" in prompt
        assert "Nguồn tham khảo" in prompt

    def test_context_version_cache(self, tmp_path: Path) -> None:
        db_path = tmp_path / "ctx.db"

        async def _test():
            from app.db.migrations import run_migrations
            await run_migrations(db_path)
            async with get_db_connection(db_path) as db:
                version = await get_context_version(db)
                assert isinstance(version, int)
        asyncio.run(_test())


# =========================================================================
# Audit Trail Completeness
# =========================================================================


class TestAuditTrail:

    AUDIT_ACTIONS = {
        "session.created", "session.renamed", "session.archived", "session.cleanup_smoke_tests",
        "prompt.submitted", "task_run.started", "task_run.completed", "task_run.failed",
        "runtime.preflight_blocked", "hermes.error",
        "approval.requested", "approval.allowed_once", "approval.allowed_for_session",
        "approval.denied", "approval.expired",
        "skill.created", "skill.updated", "skill.deleted", "skill.enabled", "skill.disabled",
        "memory.created", "memory.updated", "memory.deleted",
        "file.write", "context.version_changed",
        "n8n.webhook.sent", "n8n.webhook.error",
        "shell.run", "shell.error",
        "curator.proposed", "curator.no_proposal", "curator.accepted", "curator.denied",
        "memory.injected",
        "content.quality_check",
        "task_service_adapter.error",
    }

    def test_all_audit_actions_defined(self) -> None:
        assert len(self.AUDIT_ACTIONS) >= 25

    def test_session_created_audit(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "A", "workspace_path": "/tmp"}).json()

        async def _check():
            async with aiosqlite.connect(
                sync_client.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT action FROM audit_events WHERE session_id=? AND action='session.created'",
                    (s["id"],),
                ) as cur:
                    assert await cur.fetchone() is not None
        asyncio.run(_check())

    def test_skill_actions_produce_audit(self, sync_client: TestClient) -> None:
        r = sync_client.post("/api/skills", json={"name": "AuditSkill", "content": "test", "enabled": True})
        sid = r.json()["id"]
        sync_client.put(f"/api/skills/{sid}", json={"name": "AuditSkill", "content": "updated", "enabled": False})
        sync_client.delete(f"/api/skills/{sid}")

        async def _check():
            async with aiosqlite.connect(
                sync_client.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute("SELECT action FROM audit_events") as cur:
                    actions = [r[0] for r in await cur.fetchall()]
                    assert "skill.created" in actions
                    assert "skill.disabled" in actions
                    assert "skill.deleted" in actions
        asyncio.run(_check())

    def test_audit_event_has_required_fields(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "AF", "workspace_path": "/tmp"}).json()

        async def _check():
            async with aiosqlite.connect(
                sync_client.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT id, session_id, actor, action, created_at FROM audit_events WHERE session_id=? LIMIT 1",
                    (s["id"],),
                ) as cur:
                    row = await cur.fetchone()
                    assert row is not None
                    assert row[0]  # id
                    assert row[1] == s["id"]  # session_id
                    assert row[2]  # actor
                    assert row[3]  # action
                    assert row[4]  # created_at
        asyncio.run(_check())


# =========================================================================
# Runtime Status
# =========================================================================


class TestRuntimeStatus:

    def test_runtime_status_returns_all_sections(self, sync_client: TestClient) -> None:
        resp = sync_client.get("/api/runtime/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "backend" in data
        assert "db" in data
        assert "hermes" in data
        assert "environment" in data

    def test_runtime_status_mock_mode(self, tmp_path: Path) -> None:
        settings = Settings(db_path=str(tmp_path / "m.db"), hermes_dev_mock=True)
        app = create_app(settings_override=settings)
        with TestClient(app) as c:
            resp = c.get("/api/runtime/status")
        data = resp.json()
        assert data["hermes"]["status"] == "mock"
        assert data["hermes"]["dev_mock"] is True

    def test_runtime_smoke_runs_all_checks(self, tmp_path: Path) -> None:
        settings = Settings(db_path=str(tmp_path / "s.db"), hermes_dev_mock=True)
        app = create_app(settings_override=settings)
        with TestClient(app) as c:
            resp = c.post("/api/runtime/smoke", json={})
        assert resp.status_code == 200
        checks = {item["key"]: item for item in resp.json()["checks"]}
        assert "backend" in checks
        assert "db" in checks
        assert "hermes" in checks

    def test_runtime_smoke_with_session_workspace(self, tmp_path: Path) -> None:
        settings = Settings(db_path=str(tmp_path / "sw.db"), hermes_dev_mock=True)
        app = create_app(settings_override=settings)
        with TestClient(app) as c:
            s = c.post("/api/sessions", json={"title": "SW", "workspace_path": str(tmp_path)}).json()
            resp = c.post("/api/runtime/smoke", json={"session_id": s["id"]})
        assert resp.status_code == 200
        checks = {item["key"]: item for item in resp.json()["checks"]}
        assert checks["workspace"]["status"] == "ready"


# =========================================================================
# Skills CRUD
# =========================================================================


class TestSkillsCRUD:

    def test_create_skill(self, sync_client: TestClient) -> None:
        resp = sync_client.post("/api/skills", json={"name": "TestSkill", "content": "Do something", "enabled": True})
        assert resp.status_code == 200
        assert resp.json()["name"] == "TestSkill"

    def test_create_skill_duplicate_name(self, sync_client: TestClient) -> None:
        sync_client.post("/api/skills", json={"name": "Dup", "content": "A", "enabled": True})
        resp = sync_client.post("/api/skills", json={"name": "Dup", "content": "B", "enabled": True})
        assert resp.status_code == 400

    def test_list_skills(self, sync_client: TestClient) -> None:
        sync_client.post("/api/skills", json={"name": "S1", "content": "X", "enabled": True})
        sync_client.post("/api/skills", json={"name": "S2", "content": "Y", "enabled": False})
        resp = sync_client.get("/api/skills")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "S1" in names
        assert "S2" in names

    def test_update_skill(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/skills", json={"name": "Upd", "content": "Old", "enabled": True}).json()
        resp = sync_client.put(f"/api/skills/{s['id']}", json={"name": "Upd", "content": "New", "enabled": False})
        assert resp.status_code == 200
        assert resp.json()["content"] == "New"
        assert resp.json()["enabled"] is False

    def test_delete_skill(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/skills", json={"name": "Del", "content": "X", "enabled": True}).json()
        resp = sync_client.delete(f"/api/skills/{s['id']}")
        assert resp.status_code == 204
        all_skills = sync_client.get("/api/skills").json()
        assert not any(sk["id"] == s["id"] for sk in all_skills)


# =========================================================================
# Memory CRUD
# =========================================================================


class TestMemoryCRUD:

    def test_create_memory(self, sync_client: TestClient) -> None:
        resp = sync_client.post("/api/memory", json={
            "key": "pref_lang", "value": "Vietnamese", "kind": "preference", "importance_score": 7.0,
        })
        assert resp.status_code == 200
        assert resp.json()["key"] == "pref_lang"

    def test_memory_create_accepts_session_id(self, sync_client: TestClient) -> None:
        s = sync_client.post("/api/sessions", json={"title": "MS", "workspace_path": "/tmp"}).json()
        resp = sync_client.post("/api/memory", json={
            "key": "session_key", "value": "val", "kind": "preference",
            "importance_score": 5.0, "session_id": s["id"],
        })
        assert resp.status_code == 200
        assert resp.json()["key"] == "session_key"

    def test_memory_ordered_by_importance(self, sync_client: TestClient) -> None:
        for i in range(5):
            sync_client.post("/api/memory", json={
                "key": f"imp_{i}", "value": str(i), "kind": "preference", "importance_score": float(i),
            })
        mems = sync_client.get("/api/memory").json()
        scores = [m["importance_score"] for m in mems if m["key"].startswith("imp_")]
        assert scores == sorted(scores, reverse=True)

    def test_update_memory(self, sync_client: TestClient) -> None:
        m = sync_client.post("/api/memory", json={
            "key": "update_key", "value": "old", "kind": "preference", "importance_score": 5.0,
        }).json()
        resp = sync_client.put(f"/api/memory/{m['id']}", json={
            "key": "update_key", "value": "new", "kind": "preference", "importance_score": 8.0,
        })
        assert resp.status_code == 200
        assert resp.json()["value"] == "new"

    def test_delete_memory(self, sync_client: TestClient) -> None:
        m = sync_client.post("/api/memory", json={
            "key": "del_key", "value": "x", "kind": "preference", "importance_score": 3.0,
        }).json()
        resp = sync_client.delete(f"/api/memory/{m['id']}")
        assert resp.status_code == 204
        all_mems = sync_client.get("/api/memory").json()
        assert not any(mem["id"] == m["id"] for mem in all_mems)


# =========================================================================
# Local Data & n8n Status
# =========================================================================


class TestLocalData:

    def test_local_data_summary(self, sync_client: TestClient) -> None:
        resp = sync_client.get("/api/local-data/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions_count" in data
        assert "task_runs_count" in data
        assert "db_size_bytes" in data
        assert "db_path" in data

    def test_local_data_backup(self, sync_client: TestClient) -> None:
        resp = sync_client.post("/api/local-data/backup")
        assert resp.status_code == 201
        data = resp.json()
        assert "backup_path" in data
        assert "created_at" in data


class TestN8nStatus:

    def test_n8n_status(self, sync_client: TestClient) -> None:
        resp = sync_client.get("/api/n8n/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "configured" in data
        assert "allowed_workflows" in data


# =========================================================================
# Health
# =========================================================================


class TestHealth:

    def test_health_returns_ok(self, sync_client: TestClient) -> None:
        resp = sync_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "db" in data
        assert "version" in data
        assert "timestamp" in data

    def test_health_with_bad_db(self, tmp_path: Path) -> None:
        settings = Settings(db_path=str(tmp_path / "nonexistent" / "db.db"), hermes_dev_mock=True)
        app = create_app(settings_override=settings)
        with TestClient(app) as c:
            resp = c.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "degraded")


# =========================================================================
# CP3: Legacy Task Adapter (USE_TASK_API flag)
# =========================================================================


class TestTaskApiAdapter:
    """CP3: Legacy adapter behind USE_TASK_API flag."""

    def test_flag_false_is_default(self) -> None:
        s = Settings()
        assert s.use_task_api is False

    def test_flag_off_no_task_artifacts(
        self, sync_client_real_path: TestClient
    ) -> None:
        from app.db.connection import get_db_connection

        s = sync_client_real_path.post(
            "/api/sessions", json={"title": "NoTask", "workspace_path": "/tmp"}
        ).json()
        resp = sync_client_real_path.post(
            f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"}
        )
        assert resp.status_code == 202
        task_run_id = resp.json()["id"]

        events = []
        with sync_client_real_path.stream(
            "GET", f"/api/sessions/{s['id']}/events"
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[5:].strip())
                if line.startswith("event: done"):
                    break
        assert len(events) >= 1

        async def _check():
            await asyncio.sleep(0.1)
            async with get_db_connection(
                sync_client_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT task_id FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["task_id"] is None

                async with db.execute(
                    "SELECT COUNT(*) AS cnt FROM tasks"
                ) as cur:
                    row = await cur.fetchone()
                    assert row["cnt"] == 0

                async with db.execute(
                    "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at ASC, rowid ASC",
                    (s["id"],),
                ) as cur:
                    rows = await cur.fetchall()
                    assert len(rows) >= 2
                    assert rows[0]["role"] == "user"
                    assert rows[1]["role"] == "assistant"

                async with db.execute(
                    "SELECT action FROM audit_events WHERE session_id=?", (s["id"],)
                ) as cur:
                    actions = [r["action"] for r in await cur.fetchall()]
                    assert "prompt.submitted" in actions
                    assert "task_run.completed" in actions
        asyncio.run(_check())

    def test_flag_true_submit_prompt_creates_task_link(
        self, sync_client_use_task_api_real_path: TestClient
    ) -> None:
        from app.db.connection import get_db_connection

        s = sync_client_use_task_api_real_path.post(
            "/api/sessions", json={"title": "TA", "workspace_path": "/tmp"}
        ).json()
        resp = sync_client_use_task_api_real_path.post(
            f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"}
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "queued"
        task_run_id = data["id"]

        async def _check():
            async with get_db_connection(
                sync_client_use_task_api_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT task_id FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row is not None
                    assert row["task_id"] is not None
                    assert row["task_id"].startswith("task-")
                    linked_task_id = row["task_id"]

                async with db.execute(
                    "SELECT * FROM tasks WHERE id=?", (linked_task_id,)
                ) as cur:
                    task = await cur.fetchone()
                    assert task is not None
                    assert task["status"] == "running"
                    assert task["session_id"] == s["id"]
        asyncio.run(_check())

    def test_flag_true_prompt_lifecycle_legacy_compatibility(
        self, sync_client_use_task_api_real_path: TestClient
    ) -> None:
        from app.db.connection import get_db_connection

        s = sync_client_use_task_api_real_path.post(
            "/api/sessions", json={"title": "TB", "workspace_path": "/tmp"}
        ).json()
        resp = sync_client_use_task_api_real_path.post(
            f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"}
        )
        assert resp.status_code == 202
        task_run_id = resp.json()["id"]

        events = []
        with sync_client_use_task_api_real_path.stream(
            "GET", f"/api/sessions/{s['id']}/events"
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[5:].strip())
                if line.startswith("event: done"):
                    break
        assert len(events) >= 1

        async def _check():
            await asyncio.sleep(0.1)
            async with get_db_connection(
                sync_client_use_task_api_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT status FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["status"] == "completed"

                async with db.execute(
                    "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at ASC, rowid ASC",
                    (s["id"],),
                ) as cur:
                    rows = await cur.fetchall()
                    assert rows[0]["role"] == "user"
                    assert rows[0]["content"] == "Hello"
                    assert rows[1]["role"] == "assistant"
                    assert rows[1]["content"]

                async with db.execute(
                    "SELECT action FROM audit_events WHERE session_id=?", (s["id"],)
                ) as cur:
                    actions = [r["action"] for r in await cur.fetchall()]
                    assert "prompt.submitted" in actions
                    assert "task_run.started" in actions
                    assert "task_run.completed" in actions

                async with db.execute(
                    "SELECT task_id FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["task_id"] is not None
                    linked_task_id = row["task_id"]

                async with db.execute(
                    "SELECT status FROM tasks WHERE id=?", (linked_task_id,)
                ) as cur:
                    task = await cur.fetchone()
                    assert task is not None
                    assert task["status"] == "succeeded"
        asyncio.run(_check())

    def test_flag_true_prompt_failure_tasks_failed(
        self, sync_client_use_task_api_real_path: TestClient, monkeypatch
    ) -> None:
        from app.db.connection import get_db_connection
        monkeypatch.setenv("HERMES_AUTH_READY", "1")
        from app.api.runtime import _run_hermes_doctor_sync
        monkeypatch.setattr("app.api.runtime._run_hermes_doctor_sync", lambda _: True)
        sync_client_use_task_api_real_path.app.state.hermes_client.settings.hermes_dev_mock = False

        s = sync_client_use_task_api_real_path.post(
            "/api/sessions", json={"title": "TC", "workspace_path": "/tmp"}
        ).json()
        resp = sync_client_use_task_api_real_path.post(
            f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"}
        )
        assert resp.status_code == 202
        task_run_id = resp.json()["id"]

        has_error = False
        with sync_client_use_task_api_real_path.stream(
            "GET", f"/api/sessions/{s['id']}/events"
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("event: error"):
                    has_error = True
                if line.startswith("event: done") or line.startswith("event: error"):
                    break
        assert has_error

        async def _check():
            await asyncio.sleep(0.1)
            async with get_db_connection(
                sync_client_use_task_api_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT task_id FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["task_id"] is not None
                    linked_task_id = row["task_id"]

                async with db.execute(
                    "SELECT status FROM tasks WHERE id=?", (linked_task_id,)
                ) as cur:
                    task = await cur.fetchone()
                    assert task is not None
                    assert task["status"] == "failed"

                async with db.execute(
                    "SELECT action FROM audit_events WHERE session_id=?", (s["id"],)
                ) as cur:
                    actions = [r["action"] for r in await cur.fetchall()]
                    assert "task_run.failed" in actions
                    assert "hermes.error" in actions
        asyncio.run(_check())

    def test_adapter_unit(self, tmp_path: Path) -> None:
        from app.db.migrations import run_migrations
        from app.db.connection import get_db_connection
        from app.services.legacy_task_adapter import LegacyTaskAdapter
        from app.services.task_service import TaskService

        db_path = tmp_path / "test_adapter.db"

        async def _test():
            await run_migrations(db_path)
            async with get_db_connection(db_path) as db:
                session_id = str(uuid.uuid4())
                task_run_id = str(uuid.uuid4())
                now = int(time.time())
                await db.execute(
                    "INSERT INTO sessions (id, title, workspace_path, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, "AdapterTest", "/tmp", now, now),
                )
                await db.execute(
                    "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
                    (task_run_id, session_id, "queued", now),
                )

                adapter = LegacyTaskAdapter(TaskService(db))
                task_id = await adapter.on_prompt_submit(
                    db, session_id, task_run_id, "Test prompt"
                )

                assert task_id.startswith("task-")
                async with db.execute(
                    "SELECT * FROM tasks WHERE id=?", (task_id,)
                ) as cur:
                    task = await cur.fetchone()
                    assert task is not None
                    assert task["status"] == "running"
                    assert task["session_id"] == session_id

                async with db.execute(
                    "SELECT task_id FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["task_id"] == task_id

                await adapter.update_from_task_run(db, task_run_id, "completed")
                async with db.execute(
                    "SELECT status FROM tasks WHERE id=?", (task_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["status"] == "succeeded"

                await adapter.update_from_task_run(db, "nonexistent", "completed")

                second_task_run_id = str(uuid.uuid4())
                await db.execute(
                    "INSERT INTO task_runs (id, session_id, status, started_at) VALUES (?, ?, ?, ?)",
                    (second_task_run_id, session_id, "queued", now),
                )
                second_task_id = await adapter.on_prompt_submit(
                    db, session_id, second_task_run_id, "Second prompt"
                )
                await adapter.update_from_task_run(db, second_task_run_id, "failed", error="test error")
                async with db.execute(
                    "SELECT status FROM tasks WHERE id=?", (second_task_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["status"] == "failed"

        asyncio.run(_test())

    def test_flag_true_sse_format_compatible(
        self, sync_client_use_task_api_real_path: TestClient
    ) -> None:
        s = sync_client_use_task_api_real_path.post(
            "/api/sessions", json={"title": "TD", "workspace_path": "/tmp"}
        ).json()
        sync_client_use_task_api_real_path.post(
            f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"}
        )

        events = []
        with sync_client_use_task_api_real_path.stream(
            "GET", f"/api/sessions/{s['id']}/events"
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("data:"):
                    events.append(line[5:].strip())
                if line.startswith("event:"):
                    pass
                if line.startswith("event: done"):
                    break

        assert len(events) >= 1
        import json
        for ev in events:
            parsed = json.loads(ev)
            assert "type" in parsed

    def test_flag_true_adapter_error_audit_json(
        self, sync_client_use_task_api_real_path: TestClient, monkeypatch
    ) -> None:
        from app.services.legacy_task_adapter import LegacyTaskAdapter
        import json

        async def _broken_update(self, db, task_run_id, status, error=None):
            raise ValueError("adapter failed")

        monkeypatch.setattr(
            LegacyTaskAdapter, "update_from_task_run", _broken_update
        )

        s = sync_client_use_task_api_real_path.post(
            "/api/sessions", json={"title": "TE", "workspace_path": "/tmp"}
        ).json()
        resp = sync_client_use_task_api_real_path.post(
            f"/api/sessions/{s['id']}/prompt", json={"prompt": "Hello"}
        )
        assert resp.status_code == 202
        task_run_id = resp.json()["id"]

        with sync_client_use_task_api_real_path.stream(
            "GET", f"/api/sessions/{s['id']}/events"
        ) as stream:
            for line in stream.iter_lines():
                if line.startswith("event: done"):
                    break

        from app.db.connection import get_db_connection

        async def _check():
            await asyncio.sleep(0.1)
            async with get_db_connection(
                sync_client_use_task_api_real_path.app.state.hermes_client.settings.db_path_resolved
            ) as db:
                async with db.execute(
                    "SELECT status FROM task_runs WHERE id=?", (task_run_id,)
                ) as cur:
                    row = await cur.fetchone()
                    assert row["status"] == "completed"

                async with db.execute(
                    "SELECT payload_json FROM audit_events WHERE action='task_service_adapter.error' AND session_id=?",
                    (s["id"],),
                ) as cur:
                    rows = await cur.fetchall()
                    assert len(rows) >= 1
                    for row in rows:
                        payload = json.loads(row["payload_json"])
                        assert "task_id" in payload
                        assert "error" in payload

        asyncio.run(_check())

# =========================================================================
# Content Quality Integration (Existing tests from test_content_quality)
# =========================================================================


class TestContentQualityExisting:

    def test_html_missing_utf8_sources(self, tmp_path: Path) -> None:
        ws = tmp_path / "ws"
        ws.mkdir()
        f = ws / "outputs" / "article.html"
        f.parent.mkdir()
        f.write_text(
            "<!doctype html><html><head></head><body>"
            "<p>kênh thông lương</p>"
            "<p>Đây là nội dung mẫu đủ dài để vượt qua kiểm tra độ dài tối thiểu.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        result = check_output_file_quality(f, ws, tmp_path)
        assert result.status == "needs_review"
        assert any("HTML thiếu meta charset UTF-8" in i for i in result.issues)

    def test_output_in_code_directory_is_flagged(self, tmp_path: Path) -> None:
        pr = tmp_path / "project"
        ws = pr
        f = pr / "backend" / "article.html"
        f.parent.mkdir(parents=True)
        f.write_text(
            '<!doctype html><html><head><meta charset="utf-8"></head>'
            '<body><a href="https://example.com">Nguồn</a></body></html>',
            encoding="utf-8",
        )
        result = check_output_file_quality(f, ws, pr)
        assert result.status == "needs_review"
        assert result.label == "Sai vị trí lưu file"
