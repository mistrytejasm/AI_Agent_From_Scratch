from typing import List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from database.connection import db_client
from database.models import MessageModel, SessionModel
from memory.base import BaseMemory
from config.logging_config import logger

class MongoDBChatHistory(BaseMemory):
    def __init__(self):
        self.sessions_col = db_client.db["sessions"]
        self.messages_col = db_client.db["messages"]

    async def create_session(self, title: str = "New Conversation") -> str:
        """Creates a new session in MongoDB and returns its hex string ID."""
        logger.info(f"MongoDB create_session called with title: '{title}'")
        session = SessionModel(title=title)
        session_dict = session.model_dump(by_alias=True, exclude_none=True)
        result = await self.sessions_col.insert_one(session_dict)
        session_id = str(result.inserted_id)
        logger.info(f"MongoDB session created successfully with ID: {session_id}")
        return session_id

    async def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Retrieves all chat sessions sorted by last updated time (descending)."""
        logger.info("MongoDB get_all_sessions called")
        cursor = self.sessions_col.find().sort("updated_at", -1)
        sessions = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            sessions.append(doc)
        logger.info(f"MongoDB get_all_sessions retrieved {len(sessions)} sessions")
        return sessions

    async def add_message(self, session_id: str, role: str, content: str, **kwargs) -> None:
        """Stores a new message (including tool calls and tool IDs if present) in MongoDB."""
        logger.info(f"MongoDB add_message called for session '{session_id}' (role: '{role}')")
        obj_session_id = ObjectId(session_id)

        message = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=kwargs.get("tool_calls"),
            tool_call_id=kwargs.get("tool_call_id"),
            timestamp=datetime.now(timezone.utc),
            token_count=kwargs.get("token_count"),
            metadata=kwargs.get("metadata", {})
        )

        message_dict = message.model_dump(by_alias=True, exclude_none=True)
        message_dict["session_id"] = obj_session_id

        # Save the message document
        await self.messages_col.insert_one(message_dict)
        
        # Update the parent session's update time
        await self.sessions_col.update_one(
            {"_id": obj_session_id},
            {"$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"MongoDB message saved successfully; updated parent session '{session_id}' timestamp")

    async def get_messages(self, session_id: str, **kwargs) -> List[Dict[str, Any]]:
        """Loads all messages for a session, retaining tool metadata fields for the LLM."""
        logger.info(f"MongoDB get_messages called for session '{session_id}'")
        obj_session_id = ObjectId(session_id)
        cursor = self.messages_col.find({"session_id": obj_session_id}).sort("timestamp", 1)

        messages = []
        async for doc in cursor:
            msg_dict = {
                "role": doc["role"],
                "content": doc.get("content")
            }
            # Forward tool metadata if present
            if "tool_calls" in doc:
                msg_dict["tool_calls"] = doc["tool_calls"]
            if "tool_call_id" in doc:
                msg_dict["tool_call_id"] = doc["tool_call_id"]
            messages.append(msg_dict)
        logger.info(f"MongoDB retrieved {len(messages)} messages for session '{session_id}'")
        return messages

    async def clear(self, session_id: str) -> None:
        """Deletes all messages associated with the specified session."""
        logger.info(f"MongoDB clear messages called for session '{session_id}'")
        obj_session_id = ObjectId(session_id)
        await self.messages_col.delete_many({"session_id": obj_session_id})
        
        await self.sessions_col.update_one(
            {"_id": obj_session_id},
            {"$set": {"updated_at": datetime.now(timezone.utc)}}
        )
        logger.info(f"MongoDB cleared messages for session '{session_id}'")

    async def delete_session(self, session_id: str) -> bool:
        """Deletes a session document and all its associated messages from the database."""
        logger.info(f"MongoDB delete_session called for ID: '{session_id}'")
        try:
            obj_session_id = ObjectId(session_id)
            # Delete messages first
            await self.messages_col.delete_many({"session_id": obj_session_id})
            # Delete session document
            result = await self.sessions_col.delete_one({"_id": obj_session_id})
            success = result.deleted_count > 0
            logger.info(f"MongoDB delete_session for '{session_id}' completed (success: {success})")
            return success
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    async def delete_all_sessions(self) -> int:
        """Deletes all session documents and all message documents from the database."""
        logger.info("MongoDB delete_all_sessions called")
        try:
            # Clear all messages
            await self.messages_col.delete_many({})
            # Clear all sessions
            result = await self.sessions_col.delete_many({})
            logger.info(f"MongoDB cleared all collections (deleted sessions count: {result.deleted_count})")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Failed to delete all sessions: {e}")
            return 0