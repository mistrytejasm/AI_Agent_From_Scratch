import asyncio
import os
import sys
import time
from datetime import datetime, timezone

# Reconfigure stdout/stderr to UTF-8 on Windows for emoji support
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass # python < 3.7

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_client
from memory.long_term import LongTermMemory

async def poll_retrieve(ltm: LongTermMemory, user_id: str, query: str, expected_fact: str, timeout: int = 45) -> list:
    """Polls vector search until the expected fact is retrieved or timeout is reached."""
    start_time = time.time()
    print(f"Polling vector search for query: '{query}'...")
    while time.time() - start_time < timeout:
        retrieved = await ltm.retrieve(user_id=user_id, query=query, limit=5)
        facts = [m["fact"] for m in retrieved]
        if expected_fact in facts:
            print(f"  -> Fact found after {int(time.time() - start_time)} seconds!")
            return retrieved
        await asyncio.sleep(3)
    
    # One last try to print what we got
    retrieved = await ltm.retrieve(user_id=user_id, query=query, limit=5)
    print(f"  -> Timeout reached. Current retrieved facts: {[m['fact'] for m in retrieved]}")
    return retrieved

async def test_phase4c():
    print("Initializing components...")
    db_client.connect()
    
    # Initialize LongTermMemory
    ltm = LongTermMemory()
    
    # Ensure model is initialized
    print("Initializing embedding client...")
    await ltm.embedding_client.initialize()
    
    # We will use clean test user identifiers
    test_user_1 = "test_user_phase4c_1"
    test_user_2 = "test_user_phase4c_2"
    
    # Clean up any existing test memories first
    await ltm.collection.delete_many({"user_id": {"$in": [test_user_1, test_user_2]}})
    print("Cleaned up old test memories. Waiting 5 seconds for index stabilization...")
    await asyncio.sleep(5)
    
    try:
        # ==========================================
        # 1. Verify Confidence-Based Filtering
        # ==========================================
        print("\n--- Test 1: Confidence-Based Filtering ---")
        
        # Insert a high-confidence memory
        print("Inserting high-confidence memory (confidence=0.9)...")
        await ltm.store(
            user_id=test_user_1,
            fact="User prefers water over juice.",
            category="user_preference",
            confidence=0.9
        )
        
        # Insert a low-confidence memory
        print("Inserting low-confidence memory (confidence=0.3)...")
        await ltm.store(
            user_id=test_user_1,
            fact="User prefers tea over coffee.",
            category="user_preference",
            confidence=0.3
        )
        
        # Query memories using polling
        retrieved = await poll_retrieve(
            ltm=ltm,
            user_id=test_user_1,
            query="What does the user prefer to drink?",
            expected_fact="User prefers water over juice."
        )
        
        print(f"Retrieved {len(retrieved)} memories:")
        for idx, m in enumerate(retrieved, 1):
            print(f"  {idx}. Fact: '{m['fact']}' | Category: '{m['category']}' | Confidence: {m.get('confidence')} | Score: {m.get('final_ranking_score', 0.0):.4f}")
            
        facts_retrieved = [m["fact"] for m in retrieved]
        
        assert "User prefers water over juice." in facts_retrieved, "High confidence fact should be retrieved!"
        assert "User prefers tea over coffee." not in facts_retrieved, "Low confidence fact should be filtered out!"
        print("🟢 Test 1 Passed: Low confidence memories (< 0.5) are successfully filtered out.")
        
        # ==========================================
        # 2. Verify Category Boosting Check
        # ==========================================
        print("\n--- Test 2: Category Boosting ---")
        
        # Fact A: User preference
        fact_a = "User likes coding in Python."
        print(f"Storing Fact A (user_preference): '{fact_a}'")
        await ltm.store(
            user_id=test_user_2,
            fact=fact_a,
            category="user_preference",
            confidence=1.0
        )
        
        # Fact B: Project detail (highly semantically similar word Python)
        fact_b = "User's API backend is written in Python."
        print(f"Storing Fact B (project_detail): '{fact_b}'")
        await ltm.store(
            user_id=test_user_2,
            fact=fact_b,
            category="project_detail",
            confidence=1.0
        )
        
        # Query that should infer user_preference: "What language do I prefer?"
        query = "What language do I prefer?"
        inferred = ltm._infer_expected_category(query)
        print(f"Query: '{query}' -> Inferred category: '{inferred}'")
        assert inferred == "user_preference", "Should infer user_preference!"
        
        # Query memories using polling
        retrieved_boosted = await poll_retrieve(
            ltm=ltm,
            user_id=test_user_2,
            query=query,
            expected_fact=fact_a
        )
        
        print(f"Retrieved {len(retrieved_boosted)} memories:")
        for idx, m in enumerate(retrieved_boosted, 1):
            print(f"  {idx}. Fact: '{m['fact']}' | Category: '{m['category']}' | Similarity: {m.get('similarity_score', 0.0):.4f} | Final Score: {m.get('final_ranking_score', 0.0):.4f}")
            
        assert len(retrieved_boosted) >= 2, "Both memories should be retrieved (above threshold)"
        assert retrieved_boosted[0]["fact"] == fact_a, "Fact A (user_preference) should rank higher than Fact B because of category boost!"
        print("🟢 Test 2 Passed: Category boosting re-ranks targeted categories higher than similar-vector other categories.")
        
    finally:
        # Clean up everything we inserted
        await ltm.collection.delete_many({"user_id": {"$in": [test_user_1, test_user_2]}})
        print(f"\nCleaned up all test memories for {test_user_1} and {test_user_2}.")
        db_client.disconnect()
        print("Disconnected from database.")

if __name__ == "__main__":
    asyncio.run(test_phase4c())
