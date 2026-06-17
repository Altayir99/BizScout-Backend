from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://bizscout:bizscout@bizscout-db:5432/bizscout_db"

    # Claude API (Anthropic)
    claude_api_key: str = "sk-ant-PLACEHOLDER"
    claude_model: str = "claude-sonnet-4-5"
    claude_max_tokens: int = 2048

    # Perplexity API
    perplexity_api_key: str = "pplx-PLACEHOLDER"
    perplexity_model: str = "llama-3.1-sonar-large-128k-online"

    # App
    cors_origins: list[str] = ["*"]
    memory_window: int = 20  # last N messages passed to Claude as context

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # ignore DB_USER/DB_PASSWORD/DB_NAME (docker-compose only)


@lru_cache
def get_settings() -> Settings:
    return Settings()
