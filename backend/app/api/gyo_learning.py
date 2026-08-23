"""Explicit, governed learning candidate endpoints for Trợ lý GYO.

These endpoints only create reviewable candidates.  They are never invoked by
streaming automatically and do not activate Memory Hub records, enable Skills,
or mutate Work state.
"""
from __future__ import annotations

import aiosqlite
from fastapi import APIRouter, Depends, status

from app.api.schemas import MemoryLearningCandidateCreate, Skill, SkillLearningCandidateCreate
from app.dependencies import get_db
from app.services.learning import create_memory_candidate, create_skill_candidate


router = APIRouter(prefix="/api/gyo/learning", tags=["gyo-learning"])


@router.post("/memory-candidates", status_code=status.HTTP_201_CREATED)
async def propose_memory_candidate(
    payload: MemoryLearningCandidateCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    """Create one task-scoped Memory Hub proposal from explicit evidence."""
    return await create_memory_candidate(db, payload)


@router.post("/skill-candidates", response_model=Skill, status_code=status.HTTP_201_CREATED)
async def propose_skill_candidate(
    payload: SkillLearningCandidateCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> Skill:
    """Create one disabled Skill draft from explicit evidence."""
    return await create_skill_candidate(db, payload)
