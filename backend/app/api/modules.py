"""Foundation Module projection and user-only administration routes."""
from __future__ import annotations

from typing import Any

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_db, require_interactive_local_user_admin
from app.services.module_instances import (
    ModuleAdminError,
    list_module_instances,
    rename_module,
    reorder_attached_modules,
    set_module_attached,
)

router = APIRouter(tags=["modules"])


class ModuleInstanceResponse(BaseModel):
    id: str
    module_id: str
    source_kind: str
    package_id: str | None = None
    display_name: str
    attached: bool
    sort_order: int
    config: dict[str, Any]
    config_version: int
    health_state: str
    revision: int
    created_at: int
    updated_at: int


class ModuleRevisionRequest(BaseModel):
    expected_revision: int = Field(ge=1)


class ModuleRenameRequest(ModuleRevisionRequest):
    display_name: str = Field(min_length=1, max_length=80)


class ModuleReorderRequest(BaseModel):
    module_ids: list[str] = Field(min_length=1)
    expected_revisions: dict[str, int]


def _raise_admin_error(exc: ModuleAdminError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    ) from exc


@router.get("/api/modules", response_model=list[ModuleInstanceResponse])
async def get_module_projection(
    conn: aiosqlite.Connection = Depends(get_db),
) -> list[ModuleInstanceResponse]:
    """Return non-secret Module presentation state.

    This read projection is intentionally separate from user-only admin
    mutations so GYO/Foundation may understand which Modules are attached
    without receiving any administrative capability.
    """
    try:
        return [ModuleInstanceResponse(**item) for item in await list_module_instances(conn)]
    except ModuleAdminError as exc:
        _raise_admin_error(exc)


@router.post("/api/admin/modules/{module_id}/attach", response_model=ModuleInstanceResponse)
async def attach_module(
    module_id: str,
    request: ModuleRevisionRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    actor: str = Depends(require_interactive_local_user_admin),
) -> ModuleInstanceResponse:
    try:
        item = await set_module_attached(
            conn,
            module_id=module_id,
            attached=True,
            expected_revision=request.expected_revision,
            actor=actor,
        )
    except ModuleAdminError as exc:
        _raise_admin_error(exc)
    return ModuleInstanceResponse(**item)


@router.post("/api/admin/modules/{module_id}/detach", response_model=ModuleInstanceResponse)
async def detach_module(
    module_id: str,
    request: ModuleRevisionRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    actor: str = Depends(require_interactive_local_user_admin),
) -> ModuleInstanceResponse:
    try:
        item = await set_module_attached(
            conn,
            module_id=module_id,
            attached=False,
            expected_revision=request.expected_revision,
            actor=actor,
        )
    except ModuleAdminError as exc:
        _raise_admin_error(exc)
    return ModuleInstanceResponse(**item)


@router.patch("/api/admin/modules/{module_id}", response_model=ModuleInstanceResponse)
async def rename_module_instance(
    module_id: str,
    request: ModuleRenameRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    actor: str = Depends(require_interactive_local_user_admin),
) -> ModuleInstanceResponse:
    try:
        item = await rename_module(
            conn,
            module_id=module_id,
            display_name=request.display_name,
            expected_revision=request.expected_revision,
            actor=actor,
        )
    except ModuleAdminError as exc:
        _raise_admin_error(exc)
    return ModuleInstanceResponse(**item)


@router.post("/api/admin/modules/reorder", response_model=list[ModuleInstanceResponse])
async def reorder_modules(
    request: ModuleReorderRequest,
    conn: aiosqlite.Connection = Depends(get_db),
    actor: str = Depends(require_interactive_local_user_admin),
) -> list[ModuleInstanceResponse]:
    try:
        items = await reorder_attached_modules(
            conn,
            module_ids=request.module_ids,
            expected_revisions=request.expected_revisions,
            actor=actor,
        )
    except ModuleAdminError as exc:
        _raise_admin_error(exc)
    return [ModuleInstanceResponse(**item) for item in items]
