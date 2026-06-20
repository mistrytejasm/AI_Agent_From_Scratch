import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Reconfigure stdout/stderr to UTF-8 on Windows for emoji support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_client
from memory.mongo_history import MongoDBChatHistory
from memory.short_term import ShortTermMemory
from llm.groq_provider import GroqProvider
from agent.simple_agent import SimpleAgent
from memory.consolidator import MemoryConsolidator
from database.models import MemoryModel

async def test_edge_cases():
    print("Initializing components...")
    db_client.connect()
    
    db_history = MongoDBChatHistory()
    short_memory = ShortTermMemory(storage=db_history, max_messages=10)
    groq_llm = GroqProvider()
    agent = SimpleAgent(llm=groq_llm, memory=short_memory)
    consolidator = MemoryConsolidator(llm_provider=groq_llm)
    
    await consolidator.embedding_client.initialize()
    
    test_user = "test_user_edge"
    
    # Clean up old test data
    await consolidator.collection.delete_many({"user_id": test_user})
    print("Cleaned up old memories.")
    
    try:
        # ==========================================
        # 1. Test Duplicate Merging
        # ==========================================
        print("\n--- Edge Case 1: Duplicate Merging ---")
        fact_text = "User prefers light theme."
        emb = await consolidator.embedding_client.embed(fact_text)
        
        # Insert two identical facts at different times with different access counts
        time_old = datetime.now(timezone.utc) - timedelta(hours=2)
        time_new = datetime.now(timezone.utc)
        
        mem1 = MemoryModel(
            user_id=test_user,
            fact=fact_text,
            embedding=emb,
            category="user_preference",
            access_count=2,
            is_current=True,
            created_at=time_old,
            last_accessed=time_old
        )
        mem2 = MemoryModel(
            user_id=test_user,
            fact=fact_text,
            embedding=emb,
            category="user_preference",
            access_count=1,
            is_current=True,
            created_at=time_new,
            last_accessed=time_new
        )
        
        await consolidator.collection.insert_one(mem1.to_mongo_dict())
        await consolidator.collection.insert_one(mem2.to_mongo_dict())
        
        total_docs = await consolidator.collection.count_documents({"user_id": test_user})
        print(f"Inserted identical duplicates. Total docs in DB: {total_docs}")
        assert total_docs == 2
        
        print("Running duplicate consolidation...")
        duplicates_merged = await consolidator._find_duplicates(test_user)
        print(f"Duplicates merged report: {duplicates_merged}")
        assert duplicates_merged == 1, "Should have merged 1 duplicate."
        
        # Verify only one remains, and its access count is consolidated
        remaining = await consolidator.collection.find({"user_id": test_user}).to_list(length=None)
        assert len(remaining) == 1, "Only 1 document should remain."
        
        # Combined count should be older.access (2) + newer.access (1) + 1 = 4
        print(f"Remaining memory: '{remaining[0]['fact']}' | Access Count: {remaining[0]['access_count']}")
        assert remaining[0]["access_count"] == 4, f"Access count should be 4, but got {remaining[0]['access_count']}"
        print("🟢 Edge Case 1 Passed: Redundant identical memories successfully merged and access counts summed.")
        
        # Clean up
        await consolidator.collection.delete_many({"user_id": test_user})
        
        # ==========================================
        # 2. Test Contradiction Resolution
        # ==========================================
        print("\n--- Edge Case 2: Contradiction Resolution ---")
        
        # Insert two contradicting facts
        # Fact A (Older): User prefers light theme.
        # Fact B (Newer): User prefers dark theme.
        fact_old = "User prefers light theme."
        fact_new = "User prefers dark theme."
        
        emb_old = await consolidator.embedding_client.embed(fact_old)
        emb_new = await consolidator.embedding_client.embed(fact_new)
        
        mem_old = MemoryModel(
            user_id=test_user,
            fact=fact_old,
            embedding=emb_old,
            category="personal_info",
            access_count=0,
            is_current=True,
            created_at=datetime.now(timezone.utc) - timedelta(days=5)
        )
        mem_new = MemoryModel(
            user_id=test_user,
            fact=fact_new,
            embedding=emb_new,
            category="personal_info",
            access_count=0,
            is_current=True,
            created_at=datetime.now(timezone.utc)
        )
        
        await consolidator.collection.insert_one(mem_old.to_mongo_dict())
        await consolidator.collection.insert_one(mem_new.to_mongo_dict())
        
        print("Running contradiction consolidation...")
        conflicts_resolved = await consolidator._find_conflicts(test_user)
        print(f"Conflicts resolved report: {conflicts_resolved}")
        assert conflicts_resolved == 1, "Should have resolved 1 conflict."
        
        # Verify that only the newer one exists
        remaining_conflicts = await consolidator.collection.find({"user_id": test_user}).to_list(length=None)
        assert len(remaining_conflicts) == 1, "Only 1 document should remain after conflict resolution."
        print(f"Remaining memory after conflict: '{remaining_conflicts[0]['fact']}'")
        assert remaining_conflicts[0]["fact"] == fact_new, f"Should have kept newer fact '{fact_new}', but got '{remaining_conflicts[0]['fact']}'"
        print("🟢 Edge Case 2 Passed: Contradictions successfully resolved by retaining the newer fact.")
        
        # Clean up
        await consolidator.collection.delete_many({"user_id": test_user})
        
        # ==========================================
        # 3. Test Empty Session Summarization
        # ==========================================
        print("\n--- Edge Case 3: Empty Session Summarization ---")
        session_id = await db_history.create_session("Empty Session")
        
        # Summarize empty session
        summary = await agent.save_session_summary(session_id, user_id=test_user)
        print(f"Empty session summary result: {summary}")
        assert summary is None, "Empty session summary should return None."
        print("🟢 Edge Case 3 Passed: Empty session summary handled gracefully.")
        
        # Clean up
        await db_history.delete_session(session_id)
        
        # ==========================================
        # 4. Test Fact Extractor Noise Filtering
        # ==========================================
        print("\n--- Edge Case 4: Fact Extractor Noise Filtering ---")
        extractor = agent.fact_extractor
        
        # Verify filtering of greetings/commands/casual words
        assert not extractor._should_extract("Hi"), "Greeting 'Hi' should be filtered."
        assert not extractor._should_extract("/exit"), "Slash command '/exit' should be filtered."
        assert not extractor._should_extract("Ok thanks"), "Short casual phrase 'Ok thanks' should be filtered."
        assert not extractor._should_extract("Yes"), "Single word answer 'Yes' should be filtered."
        assert extractor._should_extract("I live in Berlin and code in Go"), "Factual sentence should NOT be filtered."
        print("🟢 Edge Case 4 Passed: Fact extractor successfully filters conversational noise.")
        
    finally:
        # Clean up all memories
        await consolidator.collection.delete_many({"user_id": test_user})
        print("\nCleaned up all test data.")
        db_client.disconnect()
        print("Disconnected from database.")

if __name__ == "__main__":
    asyncio.run(test_edge_cases())
