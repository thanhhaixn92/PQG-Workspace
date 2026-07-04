"""Event bus for SSE streaming.

Manages single-subscriber event queues per session to route ACP events
from the HermesClient to the frontend SSE endpoints.
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from fastapi import HTTPException, status

from app.api.schemas import SseEventPayload

logger = logging.getLogger(__name__)


class SessionEventBus:
    """Manages the event queues for active sessions.
    
    Enforces a single active subscriber per session as per Phase 1 requirements.
    """

    def __init__(self) -> None:
        # Maps session_id -> bounded queue of events
        self._queues: dict[str, asyncio.Queue[SseEventPayload]] = {}
        # Tracks whether a session currently has an active subscriber
        self._subscribers: set[str] = set()

    def has_subscriber(self, session_id: str) -> bool:
        """Check if a session already has an active subscriber."""
        return session_id in self._subscribers

    def get_queue(self, session_id: str) -> asyncio.Queue[SseEventPayload]:
        """Get or create the queue for a session.
        
        The queue is bounded to 100 items to prevent memory leaks if events
        are produced faster than consumed, or if the consumer drops.
        """
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue(maxsize=100)
        return self._queues[session_id]

    async def publish(self, session_id: str, event: SseEventPayload) -> None:
        """Publish an event to the session's queue, if it exists.
        
        If the queue is full, we log a warning and drop the event (or wait).
        For now, we use `put_nowait` and handle the Full exception to avoid
        blocking the publisher (HermesClient).
        """
        queue = self.get_queue(session_id)
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Event bus queue for session %s is full. Dropping event: %s",
                session_id,
                event.type,
            )

    async def subscribe(self, session_id: str) -> AsyncGenerator[SseEventPayload, None]:
        """Subscribe to a session's event stream.
        
        Raises HTTPException(409) if the session already has an active subscriber.
        Ensures the subscriber lock and queue are cleaned up when the generator exits.
        """
        if session_id in self._subscribers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Session {session_id} already has an active subscriber.",
            )

        self._subscribers.add(session_id)
        queue = self.get_queue(session_id)
        
        try:
            while True:
                # Wait for the next event
                event = await queue.get()
                yield event
                queue.task_done()
                
                # Close the stream if we hit terminal states
                if event.type in ("done", "error"):
                    break
        finally:
            # Cleanup on disconnect
            self._subscribers.discard(session_id)
            if session_id in self._queues:
                del self._queues[session_id]
            logger.info("Subscriber disconnected for session %s. Cleaned up queue.", session_id)


# Global event bus singleton for the app.
# In a larger app, this might be attached to app.state.
event_bus = SessionEventBus()
