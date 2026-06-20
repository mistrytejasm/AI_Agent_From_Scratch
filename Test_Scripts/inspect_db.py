import asyncio
import os
import sys

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_client

async def inspect():
    db_client.connect()
    db = db_client.db
    collection = db["memories"]
    
    # 1. Total counts
    total_count = await collection.count_documents({})
    current_count = await collection.count_documents({"is_current": True})
    print(f"Total memories in database: {total_count}")
    print(f"Active memories (is_current=True): {current_count}")
    
    # 2. Sample document
    if total_count > 0:
        sample = await collection.find_one({})
        print(f"\nSample memory keys: {list(sample.keys())}")
        print(f"Sample memory user_id: {sample.get('user_id')}")
        print(f"Sample memory fact: {sample.get('fact')}")
        print(f"Sample memory category: {sample.get('category')}")
        print(f"Sample memory is_current: {sample.get('is_current')}")
        print(f"Sample memory confidence: {sample.get('confidence')}")
    else:
        print("\nNo memories found in the collection.")
        
    # 3. List unique user_ids in memories
    users = await collection.distinct("user_id")
    print(f"\nDistinct users in memories: {users}")
    
    # 4. Try vector search on both index names using an existing user or a mock query
    from llm.embeddings import EmbeddingClient
    embedding_client = EmbeddingClient()
    await embedding_client.initialize()
    query_vector = await embedding_client.embed("Python programming")
    
    for idx_name in ["vector_index", "memory_vector_index"]:
        print(f"\nTesting vector search with index name: '{idx_name}'")
        pipeline = [
            {
                "$vectorSearch": {
                    "index": idx_name,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": 10,
                    "limit": 5,
                    # We try without filters first to see if index name works at all
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "fact": 1,
                    "user_id": 1,
                    "similarity_score": {"$meta": "vectorSearchScore"}
                }
            }
        ]
        try:
            cursor = collection.aggregate(pipeline)
            results = await cursor.to_list(length=5)
            print(f"  -> Success! Found {len(results)} results.")
            for r in results:
                print(f"     - [{r.get('user_id')}] '{r.get('fact')}' (score: {r.get('similarity_score')})")
        except Exception as e:
            print(f"  -> Failed: {e}")
            
    db_client.disconnect()

if __name__ == "__main__":
    asyncio.run(inspect())
