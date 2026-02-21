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

    # Telegram Bridge Settings
    telegram_token: Optional[str] = Field(None, validation_alias="TELEGRAM_TOKEN")

    # WhatsApp Bridge Settings
    whatsapp_enabled: bool = Field(False, validation_alias="WHATSAPP_ENABLED")

    # Search Settings
    brave_api_key: Optional[str] = Field(None, validation_alias="BRAVE_API_KEY")

    # MCP Settings
    # Example format: '{"server1": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}, "server2": {"url": "http://localhost:3000/sse"}}'
    mcp_servers: Optional[str] = Field(None, validation_alias="MCP_SERVERS")
    # Example format: '{"server2": {"token": "my-secret-token"}}'
    mcp_auth: Optional[str] = Field(None, validation_alias="MCP_AUTH")
    mcp_timeout: int = Field(30, validation_alias="MCP_TIMEOUT")
    mcp_max_concurrency: int = Field(10, validation_alias="MCP_MAX_CONCURRENCY")
    mcp_max_output_size: int = Field(15000, validation_alias="MCP_MAX_OUTPUT_SIZE")
    
settings = Settings()
