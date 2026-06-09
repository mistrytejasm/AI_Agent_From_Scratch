from email.policy import default
from bson import timestamp
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, Optional 
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
    role: str = Field(...) # 'system', 'user', or 'assistant'
    content: str = Field(...)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    token_count: Optional[int] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populated_by_name": True,
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
