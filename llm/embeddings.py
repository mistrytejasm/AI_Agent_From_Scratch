from tenacity import asyncio
import asyncio
from typing import List
from config.settings import settings
from sentence_transformers import SentenceTransformer
from config.logging_config import logger

class EmbeddingClient:
    """
    An asynchronous wrapper around sentence-transformers to generate text embeddings locally.
    Uses lazy loading to keep startup fast, and offloads heavy math to background threads
    using asyncio.to_thread to keep the event loop completely free.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model_name
        self._model = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Pre-loads the model weights into memory on application startup."""
        await self._get_model()

    def _load_model(self):
        """Synchronously imports and loads sentence-transformers weights."""
        # Local import to prevent slow imports during app startup
        return SentenceTransformer(self.model_name)

    async def _get_model(self):
        """Asynchronously returns the model instance, loading it thread-safely if needed."""
        if self._model is not None:
            return self._model

        async with self._lock:
            # Double-checked locking pattern to avoid race conditions during async initialization
            if self._model is None:
                logger.info(f"EmbeddingClient: Loading model weights for model: '{self.model_name}'...")
                # Load the model in a background thread to prevent blocking startup
                self._model = await asyncio.to_thread(self._load_model)
                logger.info(f"EmbeddingClient: Model '{self.model_name}' successfully loaded into memory")
            return self._model

    async def embed(self, text: str) -> List[float]:
        """
        Generates a 384-dimensional embedding vector for a single text chunk.
        Runs in a background thread to avoid blocking the event loop.
        """
        logger.info(f"EmbeddingClient: Generating embedding for text: '{text[:60]}...' (length: {len(text)} chars)")
        model = await self._get_model()
        # SentenceTransformer.encode is synchronous & CPU-bound; offload it to thread pool

        vector = await asyncio.to_thread(model.encode, text)
        return vector.tolist()

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embedding vectors for a list of text chunks in a single batched run.
        Runs in a background thread.
        """
        if not texts:
            return []

        logger.info(f"EmbeddingClient: Generating batch embeddings for {len(texts)} text chunks")
        model = await self._get_model()
        vector_batch = await asyncio.to_thread(model.encode, texts)
        return [vec.tolist() for vec in vector_batch]
        

