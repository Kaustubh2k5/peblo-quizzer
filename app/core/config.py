from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    APP_ENV: Literal["development", "production", "test"] = "development"
    SECRET_KEY: str = "change-me-in-production"

    MONGODB_URL: str = "mongodb://mongo:27017"
    MONGODB_DB: str = "peblo"

    REDIS_URL: str = "redis://redis:6379/0"

    LLM_PROVIDER: Literal["nvidia", "openai", "anthropic", "gemini"] = "nvidia"

    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "meta/llama-3.1-70b-instruct"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    MAX_FILE_SIZE_MB: int = 5
    CHUNK_SIZE_CHARS: int = 500
    CHUNK_OVERLAP_CHARS: int = 100
    QUESTIONS_PER_CHUNK: int = 1

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
