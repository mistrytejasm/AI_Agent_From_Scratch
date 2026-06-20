from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from memory.mongo_history import MongoDBChatHistory
from config.logging_config import logger

router = APIRouter()
db_history = MongoDBChatHistory()

# --- Pydantic Schemas for Requests/Responses ---

class SessionCreateRequest(BaseModel):
    title: Optional[str] = "New Conversation"

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: datetime
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any]

class DeleteReportResponse(BaseModel):
    status: str
    message: str

# --- Route Implementations ---

@router.get("/", response_model=List[SessionResponse])
async def list_sessions():
    """Retrieves all chat sessions from MongoDB sorted by last active."""
    logger.info("List Sessions API request received")
    try:
        sessions = await db_history.get_all_sessions()
        result = []
        for s in sessions:
            result.append(SessionResponse(
                id=s["_id"],
                title=s.get("title", "Untitled"),
                created_at=s.get("created_at", datetime.now(timezone.utc)),
                updated_at=s.get("updated_at", datetime.now(timezone.utc)),
                metadata=s.get("metadata", {})
            ))
        logger.info(f"List Sessions API completed successfully: found {len(result)} sessions")
        return result
    except Exception as e:
        logger.error(f"List Sessions API failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {e}")

@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(request: SessionCreateRequest):
    """Creates a new conversation session."""
    logger.info(f"Create Session API request received with title: '{request.title}'")
    try:
        session_id = await db_history.create_session(title=request.title)
        # Fetch the newly created session to return its full details
        sessions = await db_history.get_all_sessions()
        new_session = next((s for s in sessions if s["_id"] == session_id), None)
        
        if not new_session:
            logger.warning(f"Newly created session {session_id} not immediately found in active list, using default fallback representation")
            # Fallback if not immediately queried
            return SessionResponse(
                id=session_id,
                title=request.title,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                metadata={}
            )
            
        logger.info(f"Create Session API completed successfully (session_id: {session_id})")
        return SessionResponse(
            id=new_session["_id"],
            title=new_session.get("title", "Untitled"),
            created_at=new_session.get("created_at", datetime.now(timezone.utc)),
            updated_at=new_session.get("updated_at", datetime.now(timezone.utc)),
            metadata=new_session.get("metadata", {})
        )
    except Exception as e:
        logger.error(f"Create Session API failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")

@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: str = Path(..., description="The Hexadecimal ObjectId string of the session")
):
    """Retrieves the chronological list of message documents for a specific session."""
    logger.info(f"Get Session Messages API request received for session ID: {session_id}")
    try:
        # Check if the session exists first by listing all sessions
        logger.info(f"Validating session existence for ID: {session_id}")
        sessions = await db_history.get_all_sessions()
        session_exists = any(s["_id"] == session_id for s in sessions)
        if not session_exists:
            logger.warning(f"Session with ID '{session_id}' not found during messages retrieval")
            raise HTTPException(status_code=404, detail=f"Session with ID '{session_id}' not found.")
            
        messages = await db_history.get_messages(session_id)
        result = []
        for msg in messages:
            # Skip internal system messages if they shouldn't show in standard FE loops (or keep them)
            result.append(MessageResponse(
                role=msg.get("role"),
                content=msg.get("content") or "",
                timestamp=msg.get("timestamp", datetime.now(timezone.utc)),
                tool_calls=msg.get("tool_calls"),
                tool_call_id=msg.get("tool_call_id"),
                metadata=msg.get("metadata", {})
            ))
        logger.info(f"Session messages retrieved successfully for session {session_id} (found {len(result)} messages)")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get Session Messages API failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch messages for session '{session_id}': {e}")

@router.delete("/{session_id}", response_model=DeleteReportResponse)
async def delete_session(
    session_id: str = Path(..., description="The Hexadecimal ObjectId string of the session to delete")
):
    """Deletes a single chat session and all its message history."""
    logger.info(f"Delete Session API request received for session ID: {session_id}")
    try:
        # Check if the session exists first
        logger.info(f"Validating session existence for ID: {session_id}")
        sessions = await db_history.get_all_sessions()
        session_exists = any(s["_id"] == session_id for s in sessions)
        if not session_exists:
            logger.warning(f"Session with ID '{session_id}' not found for deletion")
            raise HTTPException(status_code=404, detail=f"Session with ID '{session_id}' not found.")
            
        await db_history.delete_session(session_id)
        logger.info(f"Session {session_id} and all messages deleted successfully")
        return DeleteReportResponse(
            status="success",
            message=f"Session '{session_id}' and all message history successfully deleted."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete Session API failed for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {e}")

@router.delete("/", response_model=DeleteReportResponse)
async def delete_all_sessions():
    """Wipes all saved chat sessions and all message history."""
    logger.info("Delete All Sessions API request received")
    try:
        deleted_count = await db_history.delete_all_sessions()
        logger.info(f"Wiped all sessions and messages successfully (deleted count: {deleted_count})")
        return DeleteReportResponse(
            status="success",
            message=f"Successfully wiped all chat sessions and message histories (total deleted sessions: {deleted_count})."
        )
    except Exception as e:
        logger.error(f"Delete All Sessions API failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear sessions: {e}")
