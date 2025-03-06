from enum import Enum
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # Plivo
    auth_id: str
    auth_token: str
    # OpenAI
    openai_api_key: str
    # Deepgram
    deepgram_api_key: str
    # ElevenLabs
    elevenlabs_api_key: str
    # Github
    github_token: Optional[str] = None
    # MySQL Database
    DB_NAME: str
    DB_HOST: str
    DB_PASSWORD: str
    DB_USER: str
    DB_PORT: int
    
    class Config:
        env_file = ".env"
        case_sensitive = True

class ModelType(str, Enum):
    GPT4O = 'gpt-4o'
    GPT4O_MINI = 'gpt-4o-mini'
    GPT35 = 'gpt-3.5-turbo'

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
