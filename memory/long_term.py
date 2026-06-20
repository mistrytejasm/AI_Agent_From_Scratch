from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bson import ObjectId

from database.connection import db_client
from llm.embeddings import EmbeddingClient
from database.models import MemoryModel

class LongTermMemory:
    """
    Manages long-term semantic memory storage, retrieval, and deduplication
    using MongoDB Atlas Vector Search and a local embedding model.
    """
    def __init__(self, db_conn=None, embedding_client=None):
        self.db = db_conn.db if db_conn else db_client.db
        self.collection = self.db["memories"]
        self.embedding_client = embedding_client or EmbeddingClient()

    async def _find_most_similar(self, user_id: str, embedding: List[float]) -> Optional[Dict[str, Any]]:
        """
        Finds the single most semantically similar active memory for a user.
        Returns the memory document with an injected 'similarity_score' field, or None.
        """
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": embedding,
                    "numCandidates": 50,  # HNSW search scope
                    "limit": 1,           # We only need the single closest match
                    "filter": {
                        "user_id": user_id,
                        "is_current": True
                    }
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "fact": 1,
                    "category": 1,
                    "confidence": 1,
                    "access_count": 1,
                    "is_current": 1,
                    "created_at": 1,
                    "last_accessed": 1,
                    "metadata": 1,
                    "similarity_score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        try:
            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=1)
            return results[0] if results else None
        except Exception as e:
            print(f"Error during duplicate vector search: {e}")
            return None

    async def store(
        self,
        user_id: str,
        fact: str,
        category: str = "general",
        source_session_id: Optional[str] = None,
        source_message: Optional[str] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Processes and stores a new fact. Runs semantic deduplication (Three-Zone Check)
        to insert, update, or reinforce the memory.
        
        Returns:
            Dict containing the outcome: {"status": "inserted"|"updated"|"reinforced", "id": str}
        """
        # 1. Embed the incoming fact
        embedding = await self.embedding_client.embed(fact)

        # 2. Check for the most similar existing memory
        most_similar = await self._find_most_similar(user_id, embedding)

        if most_similar:
            score = most_similar["similarity_score"]

            # ZONE A: Similarity > 0.95 -> Exact Duplicate (Reinforce)
            if score > 0.95:
                await self.collection.update_one(
                    {"_id": most_similar["_id"]},
                    {
                        "$inc": {"access_count": 1},
                        "$set": {"last_accessed": datetime.now(timezone.utc)}
                    }
                )
                return {
                    "status": "reinforced",
                    "id": str(most_similar["_id"]),
                    "similarity_score": score
                }

            # ZONE B: Similarity 0.90 - 0.95 -> Evolved Fact (Update in-place)
            elif score >= 0.90:
                await self.collection.update_one(
                    {"_id": most_similar["_id"]},
                    {
                        "$set": {
                            "fact": fact,
                            "embedding": embedding,
                            "last_accessed": datetime.now(timezone.utc),
                            "confidence": confidence,
                            "category": category
                        },
                        "$inc": {"access_count": 1}
                    }
                )
                return {
                    "status": "updated",
                    "id": str(most_similar["_id"]),
                    "similarity_score": score
                }

        # ZONE C: Similarity < 0.90 (or no similar memory) -> Brand New Knowledge
        new_memory = MemoryModel(
            user_id=user_id,
            fact=fact,
            embedding=embedding,
            category=category,
            source_session_id=source_session_id,
            source_message=source_message,
            confidence=confidence,
            access_count=0,
            is_current=True,
            metadata=metadata or {}
        )
        
        result = await self.collection.insert_one(new_memory.to_mongo_dict())
        return {
            "status": "inserted",
            "id": str(result.inserted_id),
            "similarity_score": most_similar["similarity_score"] if most_similar else 0.0
        }

    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves active semantically relevant memories for a user based on a text query.
        Updates the access stats for retrieved memories.
        """
        query_vector = await self.embedding_client.embed(query)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 50,
                    "limit": limit,
                    "filter": {
                        "user_id": user_id,
                        "is_current": True
                    }
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "fact": 1,
                    "category": 1,
                    "confidence": 1,
                    "access_count": 1,
                    "created_at": 1,
                    "last_accessed": 1,
                    "metadata": 1,
                    "similarity_score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        try:
            cursor = self.collection.aggregate(pipeline)
            memories = await cursor.to_list(length=limit)

            # Reinforce accessed memories asynchronously
            if memories:
                memory_ids = [m["_id"] for m in memories]
                await self.collection.update_many(
                    {"_id": {"$in": memory_ids}},
                    {
                        "$inc": {"access_count": 1},
                        "$set": {"last_accessed": datetime.now(timezone.utc)}
                    }
                )
            return memories
        except Exception as e:
            print(f"Error during memory retrieval vector search: {e}")
            return []

    async def list_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all active memories for a specific user sorted by last accessed."""
        cursor = self.collection.find({"user_id": user_id, "is_current": True})
        cursor.sort("last_accessed", -1)
        return await cursor.to_list(length=None)

    async def delete(self, memory_id: str) -> bool:
        """Deletes a specific memory document permanently by its ID."""
        try:
            obj_id = ObjectId(memory_id) if isinstance(memory_id, str) else memory_id
            result = await self.collection.delete_one({"_id": obj_id})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Failed to delete memory {memory_id}: {e}")
            return False

    async def delete_by_topic(self, user_id: str, topic: str) -> int:
        """
        Deletes memories matching a topic. Uses a hybrid approach:
        1. Exact/fuzzy keyword match on fact string.
        2. Semantic similarity vector search matching on the topic.
        """
        deleted_count = 0

        # Case 1: Complete wipe request
        if topic.strip().lower() == "--all":
            result = await self.collection.delete_many({"user_id": user_id})
            return result.deleted_count

        # Case 2: Exact/fuzzy keyword regex match (highly reliable for specific keywords)
        regex_result = await self.collection.delete_many({
            "user_id": user_id,
            "fact": {"$regex": topic, "$options": "i"}
        })
        deleted_count += regex_result.deleted_count

        # Case 3: Semantic match (catch related words/synonyms)
        topic_vector = await self.embedding_client.embed(topic)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": topic_vector,
                    "numCandidates": 50,
                    "limit": 10,
                    "filter": {
                        "user_id": user_id,
                        "is_current": True
                    }
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "similarity_score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        try:
            cursor = self.collection.aggregate(pipeline)
            candidates = await cursor.to_list(length=10)
            # Find candidate memory IDs that are close semantically (Similarity > 0.80)
            semantic_ids = [c["_id"] for c in candidates if c["similarity_score"] > 0.80]

            if semantic_ids:
                sem_result = await self.collection.delete_many({"_id": {"$in": semantic_ids}})
                deleted_count += sem_result.deleted_count
        except Exception as e:
            print(f"Semantic cleanup check failed: {e}")

        return deleted_count