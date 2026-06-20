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

async def test_e2e_recall():
    print("Initializing components...")
    db_client.connect()
    
    db_history = MongoDBChatHistory()
    short_memory = ShortTermMemory(storage=db_history, max_messages=10)
    groq_llm = GroqProvider()
    agent = SimpleAgent(llm=groq_llm, memory=short_memory)
    consolidator = MemoryConsolidator(llm_provider=groq_llm)
    
    await agent.long_term_memory.embedding_client.initialize()
    
    test_user = "test_user_e2e"
    
    # 1. Clean up old test data
    await agent.long_term_memory.collection.delete_many({"user_id": test_user})
    await db_client.db["sessions"].delete_many({"user_id": test_user}) # If user_id is in sessions, otherwise it's per session
    print("Cleaned up existing test data.")
    
    try:
        # ==========================================
        # Session 1: User teaches the agent a fact
        # ==========================================
        print("\n--- Starting Session 1 ---")
        session_id1 = await db_history.create_session("E2E Session 1")
        print(f"Created Session 1: {session_id1}")
        
        user_input1 = "I am building a web app in Rust. The project name is 'Aether'."
        print(f"User: '{user_input1}'")
        
        response1 = await agent.run(session_id1, user_input1, user_id=test_user)
        print(f"Agent: '{response1}'")
        
        # Await background extraction tasks
        print("Waiting for background fact extraction tasks to complete...")
        await agent.cleanup()
        print("Background tasks complete.")
        
        # Let's inspect stored memories before waiting
        initial_memories = await agent.long_term_memory.list_all(test_user)
        print(f"Stored facts in DB: {[m['fact'] for m in initial_memories]}")
        
        # We need to wait for Atlas Vector Search to update the index
        print("Waiting 8 seconds for Atlas Vector Search index to update...")
        await asyncio.sleep(8)
        
        # Exit session 1 (simulate CLI exit hook)
        print("\nExiting Session 1 - saving summary & running consolidation...")
        summary = await agent.save_session_summary(session_id1, user_id=test_user)
        if summary:
            print(f"✓ Saved session summary: {summary}")
        
        report = await consolidator.consolidate(test_user)
        print(f"✓ Consolidator ran: {report}")
        
        # ==========================================
        # Session 2: User asks about the fact in a brand new session
        # ==========================================
        print("\n--- Starting Session 2 (New Session, Empty Short-Term Memory) ---")
        session_id2 = await db_history.create_session("E2E Session 2")
        print(f"Created Session 2: {session_id2}")
        
        # Verify LTM is retrieved. Let's inspect retrieve results manually first
        query = "What was the name of the project I mentioned earlier, and what language is it in?"
        retrieved = await agent.long_term_memory.retrieve(user_id=test_user, query=query, limit=5)
        print(f"Retrieved {len(retrieved)} long-term memories for Session 2 query:")
        for idx, m in enumerate(retrieved, 1):
            print(f"  {idx}. Fact: '{m['fact']}' (Score: {m.get('final_ranking_score', 0.0):.4f})")
            
        print(f"User: '{query}'")
        response2 = await agent.run(session_id2, query, user_id=test_user)
        print(f"Agent: '{response2}'")
        
        # Assertions
        assert "aether" in response2.lower(), "Agent response should mention 'Aether'!"
        assert "rust" in response2.lower(), "Agent response should mention 'Rust'!"
        print("🟢 E2E Multi-Session Recall Test Passed!")
        
    finally:
        # Cleanup test data
        await agent.long_term_memory.collection.delete_many({"user_id": test_user})
        # Delete message histories for these sessions
        if 'session_id1' in locals():
            await db_history.delete_session(session_id1)
        if 'session_id2' in locals():
            await db_history.delete_session(session_id2)
        print("\nCleaned up all test data.")
        db_client.disconnect()
        print("Disconnected from database.")

if __name__ == "__main__":
    asyncio.run(test_e2e_recall())
