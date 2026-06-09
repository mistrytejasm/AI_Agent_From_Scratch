from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings


class DatabaseConnection:
    def __init__(self):
        self._client: AsyncIOMotorClient | None = None
        self._db = None
    
    def connect(self) -> AsyncIOMotorClient:
        """Initializes the asynchronous connection pool if not already active."""
        if not self._client:
            # Motor client manages connection pooling automatically
            self._client = AsyncIOMotorClient(settings.mongodb_uri)
            self._db = self._client[settings.mongodb_db_name]
        return self._client

    def disconnect(self) -> AsyncIOMotorClient:
        """Safely closes all connections in the pool."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    @property
    def db(self):
        """Retrieves the active database instance."""
        if self._db is None:
            self.connect()
        return self._db

# Singleton instance used throughout the app
db_client = DatabaseConnection()
