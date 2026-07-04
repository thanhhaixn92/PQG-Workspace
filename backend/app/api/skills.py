import time
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from aiosqlite import Connection

from app.dependencies import get_db
from app.api.schemas import Skill, SkillCreate, SkillUpdate
from app.services.audit import log_audit_event

router = APIRouter()

@router.get("", response_model=List[Skill])
async def list_skills(db: Connection = Depends(get_db)):
    """List all skills."""
    skills = []
    async with db.execute(
        "SELECT id, name, description, content, enabled, updated_at FROM skills ORDER BY name ASC"
    ) as cursor:
        async for row in cursor:
            skills.append(
                Skill(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    content=row[3],
                    enabled=bool(row[4]),
                    updated_at=row[5]
                )
            )
    return skills

@router.post("", response_model=Skill)
async def create_skill(skill_in: SkillCreate, db: Connection = Depends(get_db)):
    """Create a new skill."""
    # Check if name exists
    async with db.execute("SELECT id FROM skills WHERE name = ?", (skill_in.name,)) as cur:
        if await cur.fetchone():
            raise HTTPException(status_code=400, detail="Skill with this name already exists")
            
    skill_id = f"skill-{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    
    await db.execute(
        "INSERT INTO skills (id, name, description, content, enabled, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (skill_id, skill_in.name, skill_in.description, skill_in.content, int(skill_in.enabled), now)
    )
    
    # Write audit log
    await log_audit_event(db, None, "system", "skill.created", skill_id, skill_in.model_dump())
    
    await db.commit()
    
    return Skill(
        id=skill_id,
        name=skill_in.name,
        description=skill_in.description,
        content=skill_in.content,
        enabled=skill_in.enabled,
        updated_at=now
    )

@router.put("/{skill_id}", response_model=Skill)
async def update_skill(skill_id: str, skill_in: SkillUpdate, db: Connection = Depends(get_db)):
    """Update a skill."""
    async with db.execute("SELECT name, description, content, enabled FROM skills WHERE id = ?", (skill_id,)) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Skill not found")
            
    name = skill_in.name if skill_in.name is not None else row[0]
    description = skill_in.description if skill_in.description is not None else row[1]
    content = skill_in.content if skill_in.content is not None else row[2]
    enabled = skill_in.enabled if skill_in.enabled is not None else bool(row[3])
    
    now = int(time.time())
    
    # If name changed, check uniqueness
    if name != row[0]:
        async with db.execute("SELECT id FROM skills WHERE name = ? AND id != ?", (name, skill_id)) as cur:
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="Skill with this name already exists")
    
    await db.execute(
        "UPDATE skills SET name = ?, description = ?, content = ?, enabled = ?, updated_at = ? WHERE id = ?",
        (name, description, content, int(enabled), now, skill_id)
    )
    
    # Audit log logic
    action = "skill.updated"
    if skill_in.enabled is not None and skill_in.enabled != bool(row[3]):
        action = "skill.enabled" if skill_in.enabled else "skill.disabled"
        
    await log_audit_event(db, None, "system", action, skill_id, skill_in.model_dump(exclude_unset=True))
    await db.commit()
    
    return Skill(
        id=skill_id,
        name=name,
        description=description,
        content=content,
        enabled=enabled,
        updated_at=now
    )

@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, db: Connection = Depends(get_db)):
    """Delete a skill."""
    async with db.execute("SELECT id FROM skills WHERE id = ?", (skill_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Skill not found")
            
    await db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
    
    await log_audit_event(db, None, "system", "skill.deleted", skill_id, {})
    await db.commit()
