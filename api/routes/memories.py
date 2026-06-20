from fastapi import APIRouter, HTTPException, Path, Query, Body
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from memory.long_term import LongTermMemory
from memory.consolidator import MemoryConsolidator
from llm.groq_provider import GroqProvider
from config.logging_config import logger

router = APIRouter()
ltm = LongTermMemory()
# MemoryConsolidator needs LLM provider for contradictions & category compression
llm_provider = GroqProvider()
consolidator = MemoryConsolidator(llm_provider=llm_provider)

# --- Pydantic Schemas ---

class MemoryResponse(BaseModel):
    id: str
    fact: str
    category: str
    confidence: float
    access_count: int
    created_at: datetime
    last_accessed: datetime
    metadata: Dict[str, Any]

class ForgetRequest(BaseModel):
    topic: str
    user_id: Optional[str] = "default_user"

class ForgetResponse(BaseModel):
    status: str
    topic: str
    deleted_count: int

class DeleteMemoryResponse(BaseModel):
    status: str
    message: str

class ConsolidationResponse(BaseModel):
    status: str
    stale_deleted: int
    duplicates_merged: int
    conflicts_resolved: int
    categories_summarized: int

# --- Route Implementations ---

@router.get("/", response_model=List[MemoryResponse])
async def list_memories(
    user_id: str = Query("default_user", description="The ID of the user whose memories to retrieve")
):
    """Retrieves all active memories for a specific user, sorted by last accessed."""
    logger.info(f"List Memories API request received for user: '{user_id}'")
    try:
        memories = await ltm.list_all(user_id)
        result = []
        for m in memories:
            result.append(MemoryResponse(
                id=str(m["_id"]),
                fact=m.get("fact", ""),
                category=m.get("category", "general"),
                confidence=m.get("confidence", 1.0),
                access_count=m.get("access_count", 0),
                created_at=m.get("created_at", datetime.now(timezone.utc)),
                last_accessed=m.get("last_accessed", datetime.now(timezone.utc)),
                metadata=m.get("metadata", {})
            ))
        logger.info(f"List Memories API completed successfully: found {len(result)} memories for user '{user_id}'")
        return result
    except Exception as e:
        logger.error(f"List Memories API failed for user '{user_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {e}")

@router.delete("/{memory_id}", response_model=DeleteMemoryResponse)
async def delete_memory(
    memory_id: str = Path(..., description="The Hexadecimal ObjectId string of the memory document to delete")
):
    """Deletes a specific memory document permanently by its ID."""
    logger.info(f"Delete Memory API request received for memory ID: '{memory_id}'")
    try:
        success = await ltm.delete(memory_id)
        if not success:
            logger.warning(f"Memory with ID '{memory_id}' not found or could not be deleted")
            raise HTTPException(status_code=404, detail=f"Memory with ID '{memory_id}' not found or could not be deleted.")
        logger.info(f"Memory ID '{memory_id}' deleted successfully")
        return DeleteMemoryResponse(
            status="success",
            message=f"Memory fact '{memory_id}' permanently deleted."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Memory API failed for memory ID '{memory_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {e}")

@router.post("/forget", response_model=ForgetResponse)
async def forget_memories_by_topic(request: ForgetRequest):
    """
    Deletes memories matching a topic. Uses regex keyword and semantic vector search.
    Set topic to '--all' to delete all memories for the user.
    """
    logger.info(f"Forget Memories API request received for user: '{request.user_id}', topic: '{request.topic}'")
    try:
        deleted_count = await ltm.delete_by_topic(user_id=request.user_id, topic=request.topic)
        logger.info(f"Forget Memories API completed successfully: deleted {deleted_count} memories matching topic '{request.topic}'")
        return ForgetResponse(
            status="success",
            topic=request.topic,
            deleted_count=deleted_count
        )
    except Exception as e:
        logger.error(f"Forget Memories API failed for topic '{request.topic}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to forget topic '{request.topic}': {e}")

@router.post("/consolidate", response_model=ConsolidationResponse)
async def trigger_consolidation(
    user_id: str = Body("default_user", embed=True, description="The user whose database memory to consolidate")
):
    """
    Manually runs the memory consolidation pipeline (prunes stale records,
    merges duplicate entries, resolves contradictions, and compresses bloated categories).
    """
    logger.info(f"Memory Consolidation API request received for user: '{user_id}'")
    try:
        report = await consolidator.consolidate(user_id)
        logger.info(f"Memory Consolidation completed for user '{user_id}': {report}")
        return ConsolidationResponse(
            status="success",
            stale_deleted=report["stale_deleted"],
            duplicates_merged=report["duplicates_merged"],
            conflicts_resolved=report["conflicts_resolved"],
            categories_summarized=report["categories_summarized"]
        )
    except Exception as e:
        logger.error(f"Memory Consolidation failed for user '{user_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Failed to consolidate memories: {e}")
