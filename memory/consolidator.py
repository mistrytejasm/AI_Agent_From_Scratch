import json
import math
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from database.connection import db_client
from llm.groq_provider import GroqProvider
from llm.embeddings import EmbeddingClient
from database.models import MemoryModel

# Timezone-aware minimum datetime for safe comparison with MongoDB datetimes
EPOCH_START = datetime(1970, 1, 1, tzinfo=timezone.utc)

def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Calculates cosine similarity between two vectors."""
    dot_product = sum(x * y for x, y in zip(v1, v2))
    mag1 = sum(x * x for x in v1) ** 0.5
    mag2 = sum(x * x for x in v2) ** 0.5
    if not mag1 or not mag2:
        return 0.0
    return dot_product / (mag1 * mag2)

class MemoryConsolidator:
    """
    Consolidates the long-term memory store. Cleans duplicates, prunes stale
    records, resolves contradictions, and compresses bloated categories.
    """
    def __init__(
        self,
        db_conn=None,
        embedding_client: Optional[EmbeddingClient] = None,
        llm_provider: Optional[GroqProvider] = None
    ):
        self.db = db_conn.db if db_conn else db_client.db
        self.collection = self.db["memories"]
        self.embedding_client = embedding_client or EmbeddingClient()
        self.llm = llm_provider or GroqProvider()

    async def consolidate(self, user_id: str) -> Dict[str, int]:
        """
        Runs the full consolidation pipeline for a user.
        
        Returns:
            Dict containing the cleanup statistics.
        """
        stale_deleted = await self._find_stale(user_id)
        duplicates_merged = await self._find_duplicates(user_id)
        conflicts_resolved = await self._find_conflicts(user_id)
        categories_summarized = await self._compress_bloated_categories(user_id)

        return {
            "stale_deleted": stale_deleted,
            "duplicates_merged": duplicates_merged,
            "conflicts_resolved": conflicts_resolved,
            "categories_summarized": categories_summarized
        }

    async def _find_stale(self, user_id: str, threshold_days: int = 30) -> int:
        """Deletes active memories that have 0 access count and are older than threshold_days."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=threshold_days)
        
        query = {
            "user_id": user_id,
            "is_current": True,
            "access_count": 0,
            "created_at": {"$lt": cutoff_date}
        }
        
        result = await self.collection.delete_many(query)
        return result.deleted_count

    async def _find_duplicates(self, user_id: str) -> int:
        """
        Identifies exact duplicates (similarity > 0.95). Merges them in-place
        by keeping the newer one, combining access counts, and deleting the old one.
        """
        memories = await self.collection.find({"user_id": user_id, "is_current": True}).to_list(length=None)
        if len(memories) < 2:
            return 0

        merged_count = 0
        deleted_ids = set()

        for i in range(len(memories)):
            m1 = memories[i]
            if m1["_id"] in deleted_ids:
                continue

            for j in range(i + 1, len(memories)):
                m2 = memories[j]
                if m2["_id"] in deleted_ids:
                    continue

                sim = _cosine_similarity(m1["embedding"], m2["embedding"])
                if sim > 0.95:
                    # Duplicate found! Determine which is newer
                    t1 = m1.get("created_at", EPOCH_START)
                    t2 = m2.get("created_at", EPOCH_START)
                    newer, older = (m2, m1) if t2 > t1 else (m1, m2)

                    # Combine metrics
                    combined_access = newer.get("access_count", 0) + older.get("access_count", 0) + 1
                    
                    # Update newer memory
                    await self.collection.update_one(
                        {"_id": newer["_id"]},
                        {
                            "$set": {
                                "access_count": combined_access,
                                "last_accessed": datetime.now(timezone.utc)
                            }
                        }
                    )
                    # Delete older memory
                    await self.collection.delete_one({"_id": older["_id"]})
                    deleted_ids.add(older["_id"])
                    merged_count += 1
                    
                    if older == m1:
                        break
                        
        return merged_count

    async def _find_conflicts(self, user_id: str) -> int:
        """
        Identifies contradictions (similarity 0.85-0.95). Uses the LLM to verify,
        and deletes the older fact if a conflict is confirmed.
        """
        memories = await self.collection.find({"user_id": user_id, "is_current": True}).to_list(length=None)
        if len(memories) < 2:
            return 0

        resolved_count = 0
        deleted_ids = set()

        for i in range(len(memories)):
            m1 = memories[i]
            if m1["_id"] in deleted_ids:
                continue

            for j in range(i + 1, len(memories)):
                m2 = memories[j]
                if m2["_id"] in deleted_ids:
                    continue

                sim = _cosine_similarity(m1["embedding"], m2["embedding"])
                if 0.85 <= sim <= 0.95:
                    # Potential contradiction! Ask the LLM to verify
                    contradicts = await self._verify_contradiction(m1["fact"], m2["fact"])
                    if contradicts:
                        # Keep the newer, delete the older
                        t1 = m1.get("created_at", EPOCH_START)
                        t2 = m2.get("created_at", EPOCH_START)
                        newer, older = (m2, m1) if t2 > t1 else (m1, m2)

                        await self.collection.delete_one({"_id": older["_id"]})
                        deleted_ids.add(older["_id"])
                        resolved_count += 1

                        if older == m1:
                            break

        return resolved_count

    async def _verify_contradiction(self, fact1: str, fact2: str) -> bool:
        """Calls the LLM to verify if two facts contain contradictory logic."""
        prompt = (
            "You are a logical consistency validator. Check if the following two facts about a user "
            "directly contradict each other (e.g. they live in two different places, prefer mutually exclusive options, "
            "or have different roles). If they are compatible or just different details about the same user, "
            "they do NOT contradict.\n\n"
            f"Fact 1: '{fact1}'\n"
            f"Fact 2: '{fact2}'\n\n"
            "Respond in strict JSON format:\n"
            "{\n"
            "  \"contradict\": true or false\n"
            "}"
        )
        try:
            response = await self.llm.generate(
                [{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = response.get("content", "").strip()
            data = json.loads(content)
            return bool(data.get("contradict", False))
        except Exception as e:
            print(f"Error checking memory contradiction: {e}")
            return False

    async def _compress_bloated_categories(self, user_id: str, threshold: int = 15) -> int:
        """
        Compresses categories with more than 'threshold' active memories
        by summarizing them into 3-5 comprehensive facts.
        """
        memories = await self.collection.find({"user_id": user_id, "is_current": True}).to_list(length=None)
        
        # Group memories by category
        from collections import defaultdict
        grouped = defaultdict(list)
        for m in memories:
            grouped[m["category"]].append(m)
            
        summarized_count = 0
        
        for category, cat_memories in grouped.items():
            # Skip summarizing history summaries
            if category == "episode":
                continue
                
            if len(cat_memories) > threshold:
                facts_text = "\n".join(f"- {m['fact']}" for m in cat_memories)
                
                prompt = (
                    f"You are a data compression assistant. Below is a list of facts about a user in the category '{category}'. "
                    "Some of these facts might be redundant, overlapping, or minor details. "
                    "Consolidate and summarize these facts into a smaller, clean list of 3-5 comprehensive facts. "
                    "Each resulting fact must still be self-contained and atomic. "
                    "Do not lose any unique user preferences or project details, but merge overlapping details.\n\n"
                    f"RAW FACTS:\n{facts_text}\n\n"
                    "Output a JSON object in this format:\n"
                    "{\n"
                    "  \"facts\": [\n"
                    "    \"Consolidated fact 1\",\n"
                    "    \"Consolidated fact 2\"\n"
                    "  ]\n"
                    "}"
                )
                
                try:
                    response = await self.llm.generate(
                        [{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    content = response.get("content", "").strip()
                    data = json.loads(content)
                    new_facts = data.get("facts", [])
                    
                    if new_facts:
                        # 1. Delete all old memories in this category
                        old_ids = [m["_id"] for m in cat_memories]
                        await self.collection.delete_many({"_id": {"$in": old_ids}})
                        
                        # 2. Batch embed and insert new consolidated facts
                        new_embeddings = await self.embedding_client.embed_batch(new_facts)
                        
                        for fact_text, embedding in zip(new_facts, new_embeddings):
                            new_memory = MemoryModel(
                                user_id=user_id,
                                fact=fact_text,
                                embedding=embedding,
                                category=category,
                                confidence=1.0,
                                access_count=1,
                                is_current=True
                            )
                            await self.collection.insert_one(new_memory.to_mongo_dict())
                            
                        summarized_count += len(old_ids)
                except Exception as e:
                    print(f"Failed to compress bloated category '{category}': {e}")
                    
        return summarized_count