from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from bson import ObjectId

from database.connection import db_client
from llm.embeddings import EmbeddingClient
from database.models import MemoryModel
from config.logging_config import logger

class LongTermMemory:
    """
    Manages long-term semantic memory storage, retrieval, and deduplication
    using MongoDB Atlas Vector Search and a local embedding model.
    Supports multi-signal re-ranking and confidence-based filtering.
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
        logger.info(f"MongoDB _find_most_similar called for user '{user_id}' using vector search")
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
            most_similar = results[0] if results else None
            logger.info(f"MongoDB _find_most_similar complete (found match: {most_similar is not None})")
            return most_similar
        except Exception as e:
            logger.error(f"Error during duplicate vector search: {e}")
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
        logger.info(f"LTM store called for user '{user_id}' with fact: '{fact}'")
        embedding = await self.embedding_client.embed(fact)
        logger.info("Fact embedded successfully")

        # 2. Check for the most similar existing memory
        most_similar = await self._find_most_similar(user_id, embedding)

        if most_similar:
            score = most_similar["similarity_score"]
            logger.info(f"Most semantically similar memory check: similarity score is {score:.4f}")

            # 🟢 ZONE A: Similarity > 0.95 -> Exact Duplicate (Reinforce)
            if score > 0.95:
                logger.info(f"Zone A Match (>0.95) for user '{user_id}': Reinforcing memory ID {most_similar['_id']}")
                await self.collection.update_one(
                    {"_id": most_similar["_id"]},
                    {
                        "$inc": {"access_count": 1},
                        "$set": {"last_accessed": datetime.now(timezone.utc)}
                    }
                )
                logger.info(f"LTM store complete (Reinforce success) for ID: {most_similar['_id']}")
                return {
                    "status": "reinforced",
                    "id": str(most_similar["_id"]),
                    "similarity_score": score
                }

            # 🟡 ZONE B: Similarity 0.90 - 0.95 -> Evolved Fact (Update in-place)
            elif score >= 0.90:
                logger.info(f"Zone B Match (0.90-0.95) for user '{user_id}': Updating memory ID {most_similar['_id']} in-place")
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
                logger.info(f"LTM store complete (Update success) for ID: {most_similar['_id']}")
                return {
                    "status": "updated",
                    "id": str(most_similar["_id"]),
                    "similarity_score": score
                }

        # 🔵 ZONE C: Similarity < 0.90 (or no similar memory) -> Brand New Knowledge
        logger.info(f"Zone C Match (<0.90) or no similar match for user '{user_id}': Inserting new memory record")
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
        logger.info(f"LTM store complete (Insert success) for new ID: {result.inserted_id}")
        return {
            "status": "inserted",
            "id": str(result.inserted_id),
            "similarity_score": most_similar["similarity_score"] if most_similar else 0.0
        }

    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves active semantically relevant memories for a user based on a text query.
        Over-fetches candidates, filters by confidence (>0.5), and applies multi-signal
        re-ranking (similarity, recency, frequency, category boost).
        """
        logger.info(f"LTM retrieve called for user '{user_id}', query: '{query}'")
        query_vector = await self.embedding_client.embed(query)

        # Over-fetch up to 20 candidates (HNSW searches 100 nodes for high retrieval accuracy)
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 100,
                    "limit": 20,
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
            candidates = await cursor.to_list(length=20)

            logger.info(f"MongoDB Vector Search returned {len(candidates)} candidates")
            if not candidates:
                return []

            # 1. Step 11: Confidence-based filtering (Only keep facts with confidence > 0.5)
            filtered_candidates = [c for c in candidates if c.get("confidence", 1.0) > 0.5]
            logger.info(f"Filtered candidates with confidence > 0.5: count is {len(filtered_candidates)}")
            if not filtered_candidates:
                return []

            # 2. Step 10: Multi-signal re-ranking
            # A. Infer the expected category from query for Category Boost
            expected_category = self._infer_expected_category(query)
            logger.info(f"Inferred expected category from query: '{expected_category}'")
            
            # B. Get maximum access count for Frequency Scaling
            max_access = max((c.get("access_count", 0) for c in filtered_candidates), default=0)
            
            now = datetime.now(timezone.utc)
            scored_candidates = []

            for c in filtered_candidates:
                # Signal 1: Semantic Similarity (50%)
                similarity = c.get("similarity_score", 0.0)

                # Signal 2: Recency Decay (25%)
                last_acc = c.get("last_accessed", now)
                if last_acc.tzinfo is None:
                    last_acc = last_acc.replace(tzinfo=timezone.utc)
                days_since = max(0.0, (now - last_acc).total_seconds() / 86400.0)
                recency = 1.0 / (1.0 + days_since)

                # Signal 3: Access Frequency (15%)
                frequency = c.get("access_count", 0) / max_access if max_access > 0 else 0.0

                # Signal 4: Category Boost (10%)
                category_boost = 1.0 if expected_category and c.get("category") == expected_category else 0.0

                # Calculate final weighted score
                final_score = (similarity * 0.50) + (recency * 0.25) + (frequency * 0.15) + (category_boost * 0.10)
                c["final_ranking_score"] = final_score
                scored_candidates.append(c)

            # Sort by final score descending
            scored_candidates.sort(key=lambda x: x["final_ranking_score"], reverse=True)
            
            # Slice to target limit
            top_memories = scored_candidates[:limit]
            logger.info(f"Selected top {len(top_memories)} memories after multi-signal ranking")

            # 3. Reinforce ONLY the final selected top memories in MongoDB
            if top_memories:
                memory_ids = [m["_id"] for m in top_memories]
                await self.collection.update_many(
                    {"_id": {"$in": memory_ids}},
                    {
                        "$inc": {"access_count": 1},
                        "$set": {"last_accessed": datetime.now(timezone.utc)}
                    }
                )
                logger.info("Reinforced access_count and last_accessed for top retrieved memories")

            return top_memories
        except Exception as e:
            logger.error(f"Error during candidate retrieval and re-ranking: {e}")
            return []

    def _infer_expected_category(self, query: str) -> Optional[str]:
        """Infers expected category from user query keywords for category boosting."""
        text = query.lower()
        if any(k in text for k in ["like", "prefer", "dislike", "love", "hate", "favorite", "choice", "want"]):
            return "user_preference"
        if any(k in text for k in ["project", "app", "code", "programming", "database", "stack", "rust", "python", "mongodb", "postgres", "framework"]):
            return "project_detail"
        if any(k in text for k in ["live", "reside", "location", "name", "work", "job", "career", "role", "age", "birthday"]):
            return "personal_info"
        if any(k in text for k in ["goal", "target", "plan", "achieve", "aim", "future", "objective"]):
            return "goal"
        if any(k in text for k in ["last time", "yesterday", "before", "history", "previous", "earlier", "session"]):
            return "episode"
        return None

    async def list_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all active memories for a specific user sorted by last accessed."""
        cursor = self.collection.find({"user_id": user_id, "is_current": True})
        cursor.sort("last_accessed", -1)
        return await cursor.to_list(length=None)

    async def delete(self, memory_id: str) -> bool:
        """Deletes a specific memory document permanently by its ID."""
        logger.info(f"LTM delete called for memory ID: '{memory_id}'")
        try:
            obj_id = ObjectId(memory_id) if isinstance(memory_id, str) else memory_id
            result = await self.collection.delete_one({"_id": obj_id})
            success = result.deleted_count > 0
            logger.info(f"LTM delete completed (success: {success})")
            return success
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False

    async def delete_by_topic(self, user_id: str, topic: str) -> int:
        """
        Deletes memories matching a topic. Uses a hybrid approach:
        1. Exact/fuzzy keyword match on fact string.
        2. Semantic similarity vector search matching on the topic.
        """
        logger.info(f"LTM delete_by_topic called for user '{user_id}', topic: '{topic}'")
        deleted_count = 0

        # Case 1: Complete wipe request
        if topic.strip().lower() == "--all":
            logger.info(f"LTM wipe all memories requested for user '{user_id}'")
            result = await self.collection.delete_many({"user_id": user_id})
            logger.info(f"LTM wipe complete: deleted {result.deleted_count} memories")
            return result.deleted_count

        # Case 2: Exact/fuzzy keyword regex match (highly reliable for specific keywords)
        logger.info(f"LTM running regex keyword deletion check for topic '{topic}'")
        regex_result = await self.collection.delete_many({
            "user_id": user_id,
            "fact": {"$regex": topic, "$options": "i"}
        })
        deleted_count += regex_result.deleted_count
        logger.info(f"LTM regex keyword deletion deleted {regex_result.deleted_count} memories")

        # Case 3: Semantic match (catch related words/synonyms)
        logger.info(f"LTM running semantic similarity vector search for topic '{topic}'")
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
            logger.info(f"Found {len(semantic_ids)} candidate memories with similarity score > 0.80")

            if semantic_ids:
                sem_result = await self.collection.delete_many({"_id": {"$in": semantic_ids}})
                deleted_count += sem_result.deleted_count
                logger.info(f"LTM semantic similarity search deleted {sem_result.deleted_count} memories")
        except Exception as e:
            logger.error(f"Semantic cleanup check failed: {e}")

        logger.info(f"LTM delete_by_topic complete: deleted {deleted_count} total memories")
        return deleted_count