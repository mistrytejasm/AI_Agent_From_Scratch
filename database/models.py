from datetime import datetime, timezone
from typing import Annotated, Any, Dict, Optional, List
from bson import ObjectId
from pydantic import BaseModel, BeforeValidator, Field

# Custom type validator to convert MongoDB ObjectIds to strings
def validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)

    if isinstance(v, str) and ObjectId.is_valid(v):
        return v
    raise ValueError("Invalid ObjectId format") 

PyObjectId = Annotated[str, BeforeValidator(validate_object_id)]

class MessageModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    session_id: PyObjectId = Field(...)
    role: str = Field(...)  # 'system', 'user', 'assistant', or 'tool'
    content: Optional[str] = Field(default=None)  # Optional since tool calls contain no text
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None)  # Holds requested tool information
    tool_call_id: Optional[str] = Field(default=None)  # Ties tool response to the specific tool request ID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_count: Optional[int] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,  # Allows serializing _id to id
        "arbitrary_types_allowed": True,
    }

class SessionModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    title: str = Field(default="New Session")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


# ──────────────────────────────────────────────────────────────────────
# Phase 4: Long-Term Memory Models
# ──────────────────────────────────────────────────────────────────────

class MemoryModel(BaseModel):
    """
    Schema for a single long-term memory document stored in MongoDB Atlas.

    Each memory represents one atomic fact about the user, stored as an
    embedded vector for semantic search retrieval.

    Fields reserved for future phases:
      - entities:      Phase 6 — Knowledge Graph entity extraction
      - relationships: Phase 6 — Knowledge Graph relationship mapping
      - metadata:      Phase 7 — Multi-agent support (agent_id, tags)
    """
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    # ── Core Identity ──
    user_id: str = Field(..., description="Owner of this memory — enables multi-user isolation")

    # ── Memory Content ──
    fact: str = Field(..., description="The atomic fact text, e.g. 'User prefers Python for backend'")
    embedding: List[float] = Field(..., description="384-dimensional vector from all-MiniLM-L6-v2 embedding model")
    category: str = Field(
        default="general",
        description="Memory category: user_preference | project_detail | personal_info | goal | decision | technical_context | episode"
    )

    # ── Provenance (Where did this memory come from?) ──
    source_session_id: Optional[PyObjectId] = Field(default=None, description="Session ID where this fact was extracted")
    source_message: Optional[str] = Field(default=None, description="Original user message that contained this fact")

    # ── Quality & Lifecycle ──
    confidence: float = Field(default=1.0, description="LLM extraction confidence score (0.0 to 1.0)")
    access_count: int = Field(default=0, description="Times this memory was reinforced or retrieved — used for ranking")
    is_current: bool = Field(default=True, description="False = archived/superseded by a newer contradicting fact")

    # ── Future: Knowledge Graph (Phase 6) ──
    entities: Optional[List[str]] = Field(default=None, description="Phase 6: Extracted entities like ['Python', 'backend']")
    relationships: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Phase 6: Entity relationships like [{'subject': 'User', 'predicate': 'uses', 'object': 'Python'}]"
    )

    # ── Timestamps ──
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Extensible ──
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Flexible field for future extensions (agent_id, tags, etc.)")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

    def to_mongo_dict(self) -> Dict[str, Any]:
        """
        Converts the Pydantic model to a MongoDB-ready dictionary.
        Excludes the 'id' field (MongoDB auto-generates _id on insert),
        and removes None values to keep documents clean.
        """
        data = self.model_dump(by_alias=True, exclude={"id"})
        # Remove keys with None values — keeps MongoDB documents lean
        return {k: v for k, v in data.items() if v is not None}