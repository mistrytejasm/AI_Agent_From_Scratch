import sys
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

# Add the project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import decorators/registry so tools register themselves at startup
import tools

from database.connection import db_client
from llm.embeddings import EmbeddingClient
from api.routes.chat import router as chat_router
from api.routes.sessions import router as sessions_router
from api.routes.memories import router as memories_router

# Ensure Windows emoji printing support if logs are redirected
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from config.logging_config import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Starting server lifespan...")
    db_client.connect()
    
    # Pre-load local embedding model weights into memory
    logger.info("Pre-loading local embedding model weights...")
    emb_client = EmbeddingClient()
    await emb_client.initialize()
    logger.info("Embedding model initialized successfully.")
    
    yield
    
    # Shutdown actions
    logger.info("Closing database connections...")
    db_client.disconnect()
    logger.info("Lifespan shutdown complete.")

app = FastAPI(
    title="Scalable Python Chatbot API",
    description="REST & Streaming API wrapping the ReAct agent, Short-Term Chat History, and Long-Term Vector Search memories.",
    version="2.3.0",
    lifespan=lifespan
)

# Enable CORS for browser integration (crucial for frontend connections)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to target domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(memories_router, prefix="/api/memories", tags=["Memories"])

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    """Redirects the root URL to Swagger API documentation."""
    return RedirectResponse(url="/docs")
