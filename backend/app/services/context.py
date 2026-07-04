import logging
import time
from typing import List, Tuple
from aiosqlite import Connection

logger = logging.getLogger(__name__)

# Configurable limits based on Phase 4 rules
MAX_SKILLS = 10
MAX_SKILL_BYTES = 12_000
MAX_MEMORIES = 10
MAX_MEMORY_BYTES = 8_000

CONTEXT_VERSION_CACHE: dict[str, int] = {}


async def get_context_version(db: Connection) -> int:
    """Return the latest modification timestamp across skills and memories."""
    async with db.execute(
        "SELECT COALESCE(MAX(updated_at), 0) FROM skills WHERE enabled = 1 AND status = 'approved'"
    ) as cur:
        skills_ts = (await cur.fetchone())[0] or 0
    async with db.execute(
        "SELECT COALESCE(MAX(last_accessed_at), 0) FROM memory_entries"
    ) as cur:
        memory_ts = (await cur.fetchone())[0] or 0
    return max(skills_ts, memory_ts)


async def build_context(db: Connection, session_id: str) -> str:
    """
    Builds the context string containing injected skills and memory entries.
    Adheres strictly to the byte and item count caps.
    """
    skills_context = await _get_skills_context(db)
    memory_context = await _get_memory_context(db, session_id)
    
    parts = []
    if skills_context:
        parts.append(skills_context)
    if memory_context:
        parts.append(memory_context)
        
    return "\n\n".join(parts)

async def _get_skills_context(db: Connection) -> str:
    # Fetch enabled + approved skills only (CP9)
    cursor = await db.execute(
        "SELECT id, name, description, content FROM skills WHERE enabled = 1 AND status = 'approved' ORDER BY name ASC"
    )
    rows = await cursor.fetchall()
    
    injected_count = 0
    total_bytes = 0
    injected_skills = []
    
    for row in rows:
        skill_id, name, desc, content = row
        
        # Skill content is plain text.
        header = f"--- Skill: {name} ---"
        if desc:
            header += f"\nDescription: {desc}"
            
        block = f"{header}\n{content}\n"
        block_bytes = len(block.encode("utf-8"))
        
        if injected_count >= MAX_SKILLS:
            logger.debug(f"Skipping skill {name} - max skills reached")
            continue
            
        if total_bytes + block_bytes > MAX_SKILL_BYTES:
            logger.debug(f"Skipping skill {name} - max bytes reached")
            continue
            
        injected_skills.append(block)
        injected_count += 1
        total_bytes += block_bytes
        
    if not injected_skills:
        return ""
        
    return "=== ACTIVE SKILLS ===\n" + "\n".join(injected_skills)

async def _get_memory_context(db: Connection, session_id: str) -> str:
    # Fetch global and session memory entries
    cursor = await db.execute(
        "SELECT id, key, value, kind, importance_score FROM memory_entries "
        "WHERE session_id IS NULL OR session_id = ? "
        "ORDER BY importance_score DESC, last_accessed_at DESC",
        (session_id,)
    )
    rows = await cursor.fetchall()
    
    injected_count = 0
    total_bytes = 0
    injected_memories = []
    injected_ids = []
    
    for row in rows:
        mem_id, key, value, kind, score = row
        
        block = f"[{kind}] {key}: {value}"
        block_bytes = len(block.encode("utf-8"))
        
        if injected_count >= MAX_MEMORIES:
            break
            
        if total_bytes + block_bytes > MAX_MEMORY_BYTES:
            continue
            
        injected_memories.append(block)
        injected_ids.append(mem_id)
        injected_count += 1
        total_bytes += block_bytes
        
    if not injected_memories:
        return ""
        
    # Update last_accessed_at and log audit events ONLY for injected memories
    if injected_ids:
        now = int(time.time())
        # Bulk update
        placeholders = ",".join(["?"] * len(injected_ids))
        await db.execute(
            f"UPDATE memory_entries SET last_accessed_at = ? WHERE id IN ({placeholders})",
            [now] + injected_ids
        )
        # Log injection audit for each
        # We need a separate query for inserting multiple audit rows, but let's do it in a loop for simplicity
        from app.services.audit import log_audit_event
        for mem_id in injected_ids:
            await log_audit_event(db, session_id, "system", "memory.injected", mem_id, {})
            
        await db.commit()
        
    return "=== CONTEXT / MEMORY ===\n" + "\n".join(injected_memories)
