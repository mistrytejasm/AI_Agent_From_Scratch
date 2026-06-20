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
from memory.long_term import LongTermMemory

async def profile_latency():
    print("=== Long-Term Memory Latency Profiler ===")
    
    # 1. Cold Startup / Lazy Loading Profile
    print("\n1. Profiling cold model initialization...")
    ltm = LongTermMemory()
    
    t_init_start = time.perf_counter()
    await ltm.embedding_client.initialize()
    t_init_end = time.perf_counter()
    init_latency_ms = (t_init_end - t_init_start) * 1000.0
    print(f"   -> Embedding Model Initialization: {init_latency_ms:.2f} ms")
    
    # 2. Warm Embedding Generation Profile
    print("\n2. Profiling warm vector encoding...")
    text = "The user prefers working with Python and MongoDB."
    
    # Warm up first
    await ltm.embedding_client.embed(text)
    
    runs = 10
    total_embed_ms = 0.0
    for i in range(runs):
        t_start = time.perf_counter()
        await ltm.embedding_client.embed(text)
        t_end = time.perf_counter()
        total_embed_ms += (t_end - t_start) * 1000.0
        
    avg_embed_ms = total_embed_ms / runs
    print(f"   -> Average Vector Encoding (across {runs} runs): {avg_embed_ms:.2f} ms")
    
    # 3. MongoDB Vector Search & Re-ranking Profile
    print("\n3. Profiling MongoDB Atlas + Re-ranking retrieval...")
    db_client.connect()
    
    # Ensure there are some mock memories in the database for a user to search over
    test_user = "test_user_profile"
    await ltm.collection.delete_many({"user_id": test_user})
    
    # Insert 5 memories
    for i in range(5):
        await ltm.store(
            user_id=test_user,
            fact=f"User likes technical detail number {i} for their programming.",
            category="project_detail",
            confidence=0.9
        )
        
    # Wait for indexing
    print("   -> Waiting 8 seconds for vector search index to process...")
    await asyncio.sleep(8)
    
    query = "What programming details does the user like?"
    
    runs_retrieval = 10
    total_retrieval_ms = 0.0
    
    for i in range(runs_retrieval):
        t_start = time.perf_counter()
        results = await ltm.retrieve(user_id=test_user, query=query, limit=5)
        t_end = time.perf_counter()
        total_retrieval_ms += (t_end - t_start) * 1000.0
        
    avg_retrieval_ms = total_retrieval_ms / runs_retrieval
    print(f"   -> Average Retrieve call (Embedding + Atlas + Filtering + Re-ranking): {avg_retrieval_ms:.2f} ms")
    
    # Cleanup
    await ltm.collection.delete_many({"user_id": test_user})
    db_client.disconnect()
    
    print("\n=== Profiling Complete ===")
    print(f"Average Turn Retrieval Overhead: {avg_retrieval_ms:.2f} ms")
    if avg_retrieval_ms < 200.0:
        print("🟢 SUCCESS: Memory retrieval latency is well within the 200ms budget limit!")
    else:
        print("⚠️ WARNING: Memory retrieval latency exceeds the 200ms budget limit.")

if __name__ == "__main__":
    asyncio.run(profile_latency())
