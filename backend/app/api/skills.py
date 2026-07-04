import time
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from aiosqlite import Connection

from app.dependencies import get_db
from app.api.schemas import Skill, SkillCreate, SkillUpdate, SkillVersion, SkillStatusChange
from app.services.audit import log_audit_event

router = APIRouter()

SKILL_FIELDS = "id, name, description, content, enabled, status, version, updated_at"


async def _snapshot_skill(db: Connection, skill_id: str) -> None:
    """Snapshot current skill state into skill_versions."""
    async with db.execute(
        f"SELECT {SKILL_FIELDS} FROM skills WHERE id = ?", (skill_id,)
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return
    vid = f"sv-{uuid.uuid4().hex[:12]}"
    await db.execute(
        "INSERT INTO skill_versions (id, skill_id, version_number, name, description, content, status, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (vid, row[0], row[6], row[1], row[2], row[3], row[5], int(time.time())),
    )


def _row_to_skill(row) -> Skill:
    return Skill(
        id=row[0],
        name=row[1],
        description=row[2],
        content=row[3],
        enabled=bool(row[4]),
        status=row[5],
        version=row[6],
        updated_at=row[7],
    )


@router.get("", response_model=List[Skill])
async def list_skills(db: Connection = Depends(get_db)):
    skills = []
    async with db.execute(
        f"SELECT {SKILL_FIELDS} FROM skills ORDER BY name ASC"
    ) as cursor:
        async for row in cursor:
            skills.append(_row_to_skill(row))
    return skills


@router.post("", response_model=Skill)
async def create_skill(skill_in: SkillCreate, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM skills WHERE name = ?", (skill_in.name,)) as cur:
        if await cur.fetchone():
            raise HTTPException(status_code=400, detail="Skill with this name already exists")

    skill_id = f"skill-{uuid.uuid4().hex[:12]}"
    now = int(time.time())

    await db.execute(
        "INSERT INTO skills (id, name, description, content, enabled, status, version, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
        (skill_id, skill_in.name, skill_in.description, skill_in.content,
         int(skill_in.enabled), skill_in.status, now),
    )

    # Snapshot initial version
    await _snapshot_skill(db, skill_id)

    await log_audit_event(db, None, "api", "skill.created", skill_id,
                          {"name": skill_in.name, "status": skill_in.status, "version": 1})
    await db.commit()

    async with db.execute(f"SELECT {SKILL_FIELDS} FROM skills WHERE id = ?", (skill_id,)) as cur:
        return _row_to_skill(await cur.fetchone())


@router.get("/{skill_id}", response_model=Skill)
async def get_skill(skill_id: str, db: Connection = Depends(get_db)):
    async with db.execute(f"SELECT {SKILL_FIELDS} FROM skills WHERE id = ?", (skill_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _row_to_skill(row)


@router.put("/{skill_id}", response_model=Skill)
async def update_skill(skill_id: str, skill_in: SkillUpdate, db: Connection = Depends(get_db)):
    async with db.execute(
        "SELECT name, description, content, enabled, status, version FROM skills WHERE id = ?",
        (skill_id,),
    ) as cur:
        old = await cur.fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Skill not found")

    name = skill_in.name if skill_in.name is not None else old[0]
    description = skill_in.description if skill_in.description is not None else old[1]
    content = skill_in.content if skill_in.content is not None else old[2]
    enabled = skill_in.enabled if skill_in.enabled is not None else bool(old[3])
    status = skill_in.status if skill_in.status is not None else old[4]
    new_version = old[5] + 1

    if name != old[0]:
        async with db.execute(
            "SELECT id FROM skills WHERE name = ? AND id != ?", (name, skill_id)
        ) as cur:
            if await cur.fetchone():
                raise HTTPException(status_code=400, detail="Skill with this name already exists")

    # Snapshot old state before mutation
    await _snapshot_skill(db, skill_id)

    now = int(time.time())
    await db.execute(
        "UPDATE skills SET name = ?, description = ?, content = ?, enabled = ?, status = ?, version = ?, updated_at = ? WHERE id = ?",
        (name, description, content, int(enabled), status, new_version, now, skill_id),
    )

    # Determine audit action
    if skill_in.status is not None and skill_in.status != old[4]:
        audit_action = f"skill.status_{skill_in.status}"
    elif skill_in.enabled is not None and skill_in.enabled != bool(old[3]):
        audit_action = "skill.enabled" if skill_in.enabled else "skill.disabled"
    else:
        audit_action = "skill.updated"

    await log_audit_event(db, None, "api", audit_action, skill_id,
                          skill_in.model_dump(exclude_unset=True))
    await db.commit()

    async with db.execute(f"SELECT {SKILL_FIELDS} FROM skills WHERE id = ?", (skill_id,)) as cur:
        return _row_to_skill(await cur.fetchone())


@router.post("/{skill_id}/status", response_model=Skill)
async def change_skill_status(skill_id: str, status_in: SkillStatusChange, db: Connection = Depends(get_db)):
    """Change skill status (draft <-> approved)."""
    async with db.execute("SELECT status, version FROM skills WHERE id = ?", (skill_id,)) as cur:
        old = await cur.fetchone()
    if not old:
        raise HTTPException(status_code=404, detail="Skill not found")

    new_status = status_in.status
    if new_status == old[0]:
        raise HTTPException(status_code=400, detail=f"Skill already has status '{new_status}'")

    await _snapshot_skill(db, skill_id)

    now = int(time.time())
    new_version = old[1] + 1
    await db.execute(
        "UPDATE skills SET status = ?, version = ?, updated_at = ? WHERE id = ?",
        (new_status, new_version, now, skill_id),
    )

    audit_action = f"skill.status_{new_status}"
    await log_audit_event(db, None, "api", audit_action, skill_id, {"status": new_status})
    await db.commit()

    async with db.execute(f"SELECT {SKILL_FIELDS} FROM skills WHERE id = ?", (skill_id,)) as cur:
        return _row_to_skill(await cur.fetchone())


@router.get("/{skill_id}/versions", response_model=List[SkillVersion])
async def list_skill_versions(skill_id: str, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM skills WHERE id = ?", (skill_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Skill not found")

    versions = []
    async with db.execute(
        "SELECT id, skill_id, version_number, name, description, content, status, updated_at "
        "FROM skill_versions WHERE skill_id = ? ORDER BY version_number ASC",
        (skill_id,),
    ) as cursor:
        async for row in cursor:
            versions.append(SkillVersion(
                id=row[0],
                skill_id=row[1],
                version_number=row[2],
                name=row[3],
                description=row[4],
                content=row[5],
                status=row[6],
                updated_at=row[7],
            ))
    return versions


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(skill_id: str, db: Connection = Depends(get_db)):
    async with db.execute("SELECT id FROM skills WHERE id = ?", (skill_id,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status_code=404, detail="Skill not found")

    await db.execute("DELETE FROM skill_versions WHERE skill_id = ?", (skill_id,))
    await db.execute("DELETE FROM skills WHERE id = ?", (skill_id,))

    await log_audit_event(db, None, "api", "skill.deleted", skill_id, {})
    await db.commit()
