"""Tests for the SSE events stream."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.schemas import SseDoneEvent, SseTokenEvent
from app.main import create_app
from app.services.event_bus import event_bus
from app.settings import Settings


@pytest.fixture
def client(tmp_path) -> TestClient:
    db_path = tmp_path / "test_sse.db"
    settings = Settings(db_path=str(db_path))
    app = create_app(settings_override=settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_sse_endpoint(client: TestClient) -> None:
    # Create a session first to pass DB validation
    resp = client.post("/api/sessions", json={"title": "SSE test", "workspace_path": "/tmp"})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    # Push some events to the bus to simulate Hermes streaming
    await event_bus.publish(session_id, SseTokenEvent(text="Hello "))
    await event_bus.publish(session_id, SseTokenEvent(text="World"))
    await event_bus.publish(session_id, SseDoneEvent())

    # We use TestClient to read the stream
    with client.stream("GET", f"/api/sessions/{session_id}/events") as response:
        assert response.status_code == 200
        
        events_received = []
        for line in response.iter_lines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("event: "):
                event_type = line.split("event: ")[1]
            elif line.startswith("data: "):
                data_str = line.split("data: ")[1]
                events_received.append((event_type, json.loads(data_str)))
                
    assert len(events_received) == 3
    assert events_received[0][0] == "token"
    assert events_received[0][1]["text"] == "Hello "
    assert events_received[1][0] == "token"
    assert events_received[1][1]["text"] == "World"
    assert events_received[2][0] == "done"


@pytest.mark.asyncio
async def test_sse_multiple_subscribers_conflict(client: TestClient) -> None:
    # Create a session first
    resp = client.post("/api/sessions", json={"title": "SSE conflict test", "workspace_path": "/tmp"})
    assert resp.status_code == 201
    session_id = resp.json()["id"]

    # We will simulate a background task holding the stream open
    async def subscribe_and_hold():
        async for _ in event_bus.subscribe(session_id):
            pass
            
    task = asyncio.create_task(subscribe_and_hold())
    
    # Give it a tiny moment to register the subscriber
    await asyncio.sleep(0.1)
    
    # Now try to connect via the API
    response = client.get(f"/api/sessions/{session_id}/events")
    assert response.status_code == 409
    assert "already has an active subscriber" in response.text
    
    # Clean up
    task.cancel()
