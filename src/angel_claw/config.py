from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    # Gateway Settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # LLM Settings
    model: str = Field("gpt-4o-mini", validation_alias="MODEL")
    api_key: Optional[str] = Field(None, validation_alias="MODEL_KEY")
    
    # Memory Settings (Angel Recall)
    memory_persist_dir: str = "./vaults"

    # Proactive Messaging Settings
    proactive_webhook_url: Optional[str] = Field(None, validation_alias="PROACTIVE_WEBHOOK_URL")

    # Search Settings
    brave_api_key: Optional[str] = Field(None, validation_alias="BRAVE_API_KEY")
    
settings = Settings()
