import asyncio
import os
import sys

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from llm.embeddings import EmbeddingClient
from memory.consolidator import _cosine_similarity

async def main():
    client = EmbeddingClient()
    await client.initialize()
    
    pairs = [
        ("User works at Microsoft.", "User works at Google."),
        ("User lives in Seattle.", "User lives in Boston."),
        ("User prefers coding in Python.", "User prefers coding in Rust."),
        ("User prefers light mode.", "User prefers dark mode."),
        ("User lives in Munich.", "User lives in Berlin."),
        ("User works as a software engineer at Microsoft.", "User works as a product manager at Microsoft."),
        ("User works as a software engineer at Microsoft.", "User works as a software engineer at Google."),
        ("User prefers light theme.", "User prefers dark theme.")
    ]
    
    for p1, p2 in pairs:
        v1 = await client.embed(p1)
        v2 = await client.embed(p2)
        sim = _cosine_similarity(v1, v2)
        print(f"Similarity: {sim:.4f} | '{p1}' vs '{p2}'")

if __name__ == "__main__":
    asyncio.run(main())
