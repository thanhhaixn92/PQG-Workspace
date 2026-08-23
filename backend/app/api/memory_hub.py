"""Authenticated REST boundary for the Personal Memory Hub."""
from __future__ import annotations

import hmac
from typing import Literal
from urllib.parse import urlsplit

import keyring
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from aiosqlite import Connection

from app.dependencies import get_db, get_settings
from app.settings import Settings
from app.services import memory_hub

router = APIRouter()

class EvidenceIn(BaseModel):
    evidence_type: str = Field(min_length=1, max_length=80)
    reference: str = Field(min_length=1, max_length=1000)
    sha256: str | None = Field(default=None, max_length=64)

class ProposalIn(BaseModel):
    kind: str
    memory_key: str = Field(min_length=1, max_length=240)
    content: str
    project_id: str | None = Field(default=None, max_length=240)
    task_id: str | None = Field(default=None, max_length=240)
    session_id: str | None = Field(default=None, max_length=240)
    producer_model: str | None = Field(default=None, max_length=240)
    producer_session: str | None = Field(default=None, max_length=240)
    source_type: str = Field(default="agent_proposal", max_length=80)
    source_ref: str | None = Field(default=None, max_length=1000)
    source_artifact_sha256: str | None = Field(default=None, max_length=64)
    confidence: float = Field(default=0.5, ge=0, le=1)
    sensitivity: Literal["normal", "sensitive", "restricted"] = "normal"
    evidence: list[EvidenceIn] = Field(default_factory=list, max_length=20)

class TransitionIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)

class ContextPackIn(BaseModel):
    project_id: str | None = Field(default=None, max_length=240)
    task_id: str | None = Field(default=None, max_length=240)

class LegacyImportIn(BaseModel):
    memory_ids: list[str] = Field(min_length=1, max_length=100)
    project_id: str | None = Field(default=None, max_length=240)
    task_id: str | None = Field(default=None, max_length=240)


class OperatorProposalIn(BaseModel):
    kind: Literal["preference", "project_context", "task_continuity", "workflow_rule", "technical_decision", "lesson"]
    memory_key: str = Field(min_length=1, max_length=240)
    content: str
    project_id: str | None = Field(default=None, max_length=240)
    task_id: str | None = Field(default=None, max_length=240)


async def require_local_operator(request: Request, settings: Settings = Depends(get_settings)) -> None:
    client_host = request.client.host if request.client else ""
    if client_host not in {"127.0.0.1", "::1", "localhost"}:
        raise HTTPException(status_code=403, detail="Memory Hub operator access is restricted to localhost")
    origin = request.headers.get("origin")
    if origin is None:
        # Same-origin browser GETs routed through the local Vite proxy normally
        # omit Origin but retain Referer.  Accept only its exact loopback origin;
        # requests with neither header remain fail-closed.
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            if parsed.scheme and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in settings.cors_origins:
        raise HTTPException(status_code=403, detail="Memory Hub operator origin is not allowed")

async def get_memory_hub_role(
    authorization: str | None = Header(default=None), settings: Settings = Depends(get_settings)
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Memory Hub bearer token")
    candidate = authorization.removeprefix("Bearer ")
    try:
        matches: list[str] = []
        for role in sorted(memory_hub.ALL_ROLES):
            token = keyring.get_password(settings.memory_hub_keyring_service, role)
            if token and hmac.compare_digest(candidate, token):
                matches.append(role)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise HTTPException(status_code=503, detail="Memory Hub credential roles are ambiguous")
    except keyring.errors.KeyringError as exc:
        raise HTTPException(status_code=503, detail="Memory Hub credential store is unavailable") from exc
    raise HTTPException(status_code=401, detail="Invalid Memory Hub bearer token")

@router.post("/proposals")
async def create_proposal(payload: ProposalIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.create_proposal(db, role, payload.model_dump())

@router.get("/records")
async def search_records(
    q: str | None = Query(default=None, max_length=240), project_id: str | None = None, task_id: str | None = None,
    lifecycle: str | None = "active", sensitivity: str | None = None, include_global_preferences: bool = False, limit: int = Query(default=20, ge=1, le=100),
    role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db),
) -> list[dict]:
    return await memory_hub.search(db, role, query=q, project_id=project_id, task_id=task_id, lifecycle=lifecycle, sensitivity=sensitivity, include_global_preferences=include_global_preferences, limit=limit)

@router.get("/records/{record_id}")
async def read_record(record_id: str, project_id: str | None = None, task_id: str | None = None, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.get_record(db, role, record_id, project_id=project_id, task_id=task_id)

@router.post("/records/{record_id}/verify")
async def verify_record(record_id: str, payload: TransitionIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.transition(db, role, record_id, "verify", payload.note)

@router.post("/records/{record_id}/activate")
async def activate_record(record_id: str, payload: TransitionIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.transition(db, role, record_id, "activate", payload.note)

@router.post("/records/{record_id}/reject")
async def reject_record(record_id: str, payload: TransitionIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.transition(db, role, record_id, "reject", payload.note)

@router.post("/context-pack")
async def create_context_pack(payload: ContextPackIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.context_pack(db, role, payload.project_id, payload.task_id)

@router.post("/legacy-import/preview")
async def legacy_preview(payload: LegacyImportIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> list[dict]:
    return await memory_hub.preview_legacy(db, role, payload.memory_ids)

@router.post("/legacy-import")
async def legacy_import(payload: LegacyImportIn, role: str = Depends(get_memory_hub_role), db: Connection = Depends(get_db)) -> list[dict]:
    return await memory_hub.import_legacy(db, role, payload.memory_ids, project_id=payload.project_id, task_id=payload.task_id)


@router.get("/operator/records")
async def operator_search_records(
    q: str | None = Query(default=None, max_length=240), project_id: str | None = None, task_id: str | None = None,
    lifecycle: str | None = None, include_global_preferences: bool = False, limit: int = Query(default=20, ge=1, le=100),
    _: None = Depends(require_local_operator), db: Connection = Depends(get_db),
) -> list[dict]:
    return await memory_hub.search(db, "user", query=q, project_id=project_id, task_id=task_id, lifecycle=lifecycle, sensitivity="normal", include_global_preferences=include_global_preferences, limit=limit)


@router.post("/operator/proposals")
async def operator_create_proposal(payload: OperatorProposalIn, _: None = Depends(require_local_operator), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.create_proposal(db, "user", {
        **payload.model_dump(), "source_type": "user_input", "sensitivity": "normal", "confidence": 1.0,
    })


@router.post("/operator/records/{record_id}/verify")
async def operator_verify_preference(record_id: str, payload: TransitionIn, _: None = Depends(require_local_operator), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.transition(db, "user", record_id, "verify", payload.note)


@router.post("/operator/records/{record_id}/activate")
async def operator_activate_preference(record_id: str, payload: TransitionIn, _: None = Depends(require_local_operator), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.transition(db, "user", record_id, "activate", payload.note)


@router.post("/operator/records/{record_id}/reject")
async def operator_reject_preference(record_id: str, payload: TransitionIn, _: None = Depends(require_local_operator), db: Connection = Depends(get_db)) -> dict:
    return await memory_hub.transition(db, "user", record_id, "reject", payload.note)


@router.post("/operator/legacy-import/preview")
async def operator_legacy_preview(payload: LegacyImportIn, _: None = Depends(require_local_operator), db: Connection = Depends(get_db)) -> list[dict]:
    return await memory_hub.preview_legacy(db, "user", payload.memory_ids)


@router.post("/operator/legacy-import")
async def operator_legacy_import(payload: LegacyImportIn, _: None = Depends(require_local_operator), db: Connection = Depends(get_db)) -> list[dict]:
    return await memory_hub.import_legacy(db, "user", payload.memory_ids, project_id=payload.project_id, task_id=payload.task_id)
