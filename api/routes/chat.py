from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
import json

from memory.mongo_history import MongoDBChatHistory
from memory.short_term import ShortTermMemory
from llm.groq_provider import GroqProvider
from agent.simple_agent import SimpleAgent
from config.settings import settings
from config.logging_config import logger

router = APIRouter()

# Initialize shared agent dependencies
db_history = MongoDBChatHistory()
short_memory = ShortTermMemory(storage=db_history, max_messages=settings.max_messages)
groq_llm = GroqProvider()

# Setup primary LLM provider
# if settings.use_local_llm:
#     from llm.local_openai import LocalOpenAIProvider
#     from llm.fallback_provider import FallbackLLMProvider
#     local_llm = LocalOpenAIProvider()
#     llm = FallbackLLMProvider(primary=local_llm, fallback=groq_llm)
# else:
#     llm = groq_llm
llm = groq_llm

agent = SimpleAgent(llm=llm, memory=short_memory)

# --- Pydantic Request/Response Models ---

class ChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: Optional[str] = "default_user"

class ChatResponse(BaseModel):
    session_id: str
    response: str

# --- Route Implementations ---

@router.post("/", response_model=ChatResponse)
async def chat_sync(request: ChatRequest):
    """
    Standard synchronous chat execution.
    Runs the full ReAct loop and returns the complete text response.
    """
    logger.info(f"Chat Sync API request received (session_id: '{request.session_id}', user_id: '{request.user_id}')")
    try:
        # Check if session exists in history first
        logger.info(f"Validating session existence for ID: '{request.session_id}'")
        sessions = await db_history.get_all_sessions()
        session_exists = any(s["_id"] == request.session_id for s in sessions)
        if not session_exists:
            logger.warning(f"Session with ID '{request.session_id}' not found during chat_sync")
            raise HTTPException(status_code=404, detail=f"Session with ID '{request.session_id}' not found.")
            
        logger.info(f"Executing synchronous Agent loop for session '{request.session_id}' with input: '{request.message}'")
        response_text = await agent.run(request.session_id, request.message, user_id=request.user_id)
        logger.info(f"Chat Sync API completed successfully (response length: {len(response_text)} chars)")
        return ChatResponse(
            session_id=request.session_id,
            response=response_text
        )
    except Exception as e:
        logger.error(f"Chat Sync API failed for session '{request.session_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Agent loop failure: {str(e)}")

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Real-time streaming chat execution using Server-Sent Events (SSE).
    Yields JSON events for tool invocations and typewriter text content tokens.
    """
    logger.info(f"Chat Stream API request received (session_id: '{request.session_id}', user_id: '{request.user_id}')")
    # Verify session exists
    logger.info(f"Validating session existence for ID: '{request.session_id}'")
    sessions = await db_history.get_all_sessions()
    session_exists = any(s["_id"] == request.session_id for s in sessions)
    if not session_exists:
        logger.warning(f"Session with ID '{request.session_id}' not found during chat_stream")
        raise HTTPException(status_code=404, detail=f"Session with ID '{request.session_id}' not found.")

    logger.info(f"Initiating SSE streaming chat for session '{request.session_id}' with input: '{request.message}'")

    async def sse_event_generator() -> AsyncGenerator[str, None]:
        try:
            # Run the agent stream and capture yielded tokens
            async for token in agent.run_stream(request.session_id, request.message, user_id=request.user_id):
                if token.startswith("__TOOL_CALL__"):
                    # Format: __TOOL_CALL__:tool_name:arguments_json
                    parts = token.split(":", 2)
                    tool_name = parts[1]
                    args_str = parts[2] if len(parts) > 2 else "{}"
                    
                    logger.info(f"SSE Yielding tool call alert: '{tool_name}' with arguments: {args_str}")
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'arguments': args_str})}\n\n"
                else:
                    # Standard word/char chunk token
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            
            # Send completion token
            logger.info(f"SSE streaming stream complete for session '{request.session_id}'")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            logger.error(f"SSE streaming failed during token generation: {e}")
            # Yield error details to the frontend
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
            
    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
