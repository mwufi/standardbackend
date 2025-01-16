from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str = "conversations.db"
    cors_origins: List[str] = ["http://localhost:3000"]
    system_prompt: str = "You are a helpful AI assistant focused on providing clear and accurate information."
    personality: str = "friendly and professional"
    has_memory: bool = True
    enabled_tools: List[str] = ["search", "code"]
    llm_model: str = "claude-3-sonnet-20240229"
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings() 