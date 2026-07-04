from __future__ import annotations

from typing import Optional


class TransitionError(ValueError):
    pass


class TaskStateMachine:
    TRANSITIONS: dict[str, set[str]] = {
        "queued": {"running", "cancelled"},
        "running": {"succeeded", "failed", "cancelled", "waiting_approval"},
        "waiting_approval": {"running", "failed", "cancelled"},
    }

    TERMINAL: set[str] = {"succeeded", "failed", "cancelled"}

    @classmethod
    def validate(cls, from_status: str, to_status: str) -> None:
        if from_status in cls.TERMINAL:
            raise TransitionError(f"Cannot transition from terminal state: {from_status}")
        allowed = cls.TRANSITIONS.get(from_status)
        if allowed is None:
            raise TransitionError(f"Unknown state: {from_status}")
        if to_status not in allowed:
            raise TransitionError(f"Invalid transition: {from_status} -> {to_status}")

    @classmethod
    def is_terminal(cls, status: str) -> bool:
        return status in cls.TERMINAL
