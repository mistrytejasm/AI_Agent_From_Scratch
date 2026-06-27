import asyncio
import os
import sys

# Add the project root to sys.path so we can import database and llm modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database.connection import db_client
from llm.groq_provider import GroqProvider

async def test():
    print("1. Testing MongoDB connection...")
    try:
        db_client.connect()
        # Run a simple server command to ping the DB
        await db_client.db.command("ping")
        print("   -> MongoDB Atlas Connection: [bold green]OK[/bold green]")
    except Exception as e:
        print(f"   -> MongoDB Connection Failed: {e}")
        return
    
    print("\n2. Testing Groq LLM API connectivity...")
    try:
        provider = GroqProvider()
        response = await provider.generate([{"role": "user", "content": "Say: 'API Connection Successful!'"}] )
        print(f"   -> Groq API Response: '{response['content'].strip()}'")
    except Exception as e:
        print(f"   -> Groq API Connection Failed: {e}")
        
    db_client.disconnect()
    print("\nAll connection checks complete.")

if __name__ == "__main__":
    asyncio.run(test())