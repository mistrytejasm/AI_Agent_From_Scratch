from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Groq LLM API Configuration
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_default_model: str = Field("llama3-8b-8192", alias="GROQ_DEFAULT_MODEL")

    # MongoDB Atlas Database Configuration
    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_db_name: str = Field("chatbot_db", alias="MONGODB_DB_NAME")

    # Tavily Search Configuration
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")

    # Memory Configuration
    max_messages: int = Field(5, alias="MAX_MESSAGES")

    # Local LLM Configuration
    local_llm_base_url: str = Field("http://localhost/v1", alias="LOCAL_LLM_BASE_URL")
    local_llm_api_key: str = Field("my-local-secret-key-2026", alias="LOCAL_LLM_API_KEY")
    local_llm_model: str = Field("qwen3.5-4b", alias="LOCAL_LLM_MODEL")
    use_local_llm: bool = Field(False, alias="USE_LOCAL_LLM")

    # Embedding Configuration
    embedding_model_name: str = Field("all-MiniLM-L6-v2", alias="EMBEDDING_MODEL_NAME")

    # Configuration to load from the .env file in the project root
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()