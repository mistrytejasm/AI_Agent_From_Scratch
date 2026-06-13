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