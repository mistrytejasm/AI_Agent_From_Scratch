import asyncio
import os
import sys

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_client
from memory.long_term import LongTermMemory

async def debug():
    db_client.connect()
    ltm = LongTermMemory()
    await ltm.embedding_client.initialize()
    
    test_user = "test_user_phase4c_debug"
    
    # 1. Clean up
    await ltm.collection.delete_many({"user_id": test_user})
    
    # 2. Store a memory
    print("Storing memory...")
    res = await ltm.store(
        user_id=test_user,
        fact="User loves coding in Python.",
        category="user_preference",
        confidence=1.0
    )
    print(f"Store result: {res}")
    
    # 3. Query using standard find()
    doc = await ltm.collection.find_one({"user_id": test_user})
    print(f"Found document via standard query: {doc is not None}")
    if doc:
        print(f"Document keys: {list(doc.keys())}")
        print(f"is_current: {doc.get('is_current')}")
        print(f"Embedding length: {len(doc.get('embedding', []))}")
    
    # 4. Check collection indexes
    print("\nListing collection indexes:")
    try:
        async for index in ltm.collection.list_indexes():
            print(f"  Index: {index}")
    except Exception as e:
        print(f"  Could not list indexes: {e}")
        
    # 5. Try vector search with different query parameters or check if vector search fails with error
    print("\nAttempting vector search aggregation pipeline...")
    query_vector = await ltm.embedding_client.embed("What language does the user like?")
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": 10,
                "limit": 1,
                "filter": {
                    "user_id": test_user,
                    "is_current": True
                }
            }
        }
    ]
    try:
        cursor = ltm.collection.aggregate(pipeline)
        results = await cursor.to_list(length=1)
        print(f"Vector search results count: {len(results)}")
        if results:
            print(f"Vector search result: {results[0]['fact']}")
    except Exception as e:
        print(f"Vector search failed: {e}")
        
    await ltm.collection.delete_many({"user_id": test_user})
    db_client.disconnect()

if __name__ == "__main__":
    asyncio.run(debug())
