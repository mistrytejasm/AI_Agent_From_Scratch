from ast import alias
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Groq LLM API Configuration
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")
    groq_default_model: str = Field("llama3-8b-8192", alias="GROQ_DEFAULT_MODEL")

    # MongoDB Atlas Database Configuration
    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_db_name: str = Field("chatbot_db", alias="MONGODB_DB_NAME")

    # Configuration to load from the .env file in the project root
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore" # Ignore other environment variables not specified here
    )

# Singleton instance of settings to import across modules
settings = Settings()
