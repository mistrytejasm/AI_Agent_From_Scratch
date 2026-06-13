import asyncio
from database.connection import db_client
from config.settings import settings

async def truncate_database():
    print("Connecting to MongoDB...")
    try:
        # Connect to MongoDB
        db_client.connect()
        
        # Ping to check connection
        await db_client.db.command("ping")
        print("MongoDB connection successful.")
        
        # Collections to truncate
        collections = ["sessions", "messages"]
        
        for coll_name in collections:
            coll = db_client.db[coll_name]
            result = await coll.delete_many({})
            print(f"Truncated collection '{coll_name}': Deleted {result.deleted_count} documents.")
            
        print("Database truncation complete.")
    except Exception as e:
        print(f"Failed to truncate database: {e}")
    finally:
        db_client.disconnect()

if __name__ == "__main__":
    asyncio.run(truncate_database())
