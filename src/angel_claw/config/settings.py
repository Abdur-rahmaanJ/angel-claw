from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Gateway Settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    webhook_key: Optional[str] = Field(None, validation_alias="WEBHOOK_KEY")

    # LLM Settings
    model: str = Field("openai/gpt-4o-mini", validation_alias="MODEL")
    api_key: Optional[str] = Field(None, validation_alias="MODEL_KEY")
    api_base: Optional[str] = Field(None, validation_alias="MODEL_BASE_URL")

    # Auth Settings
    auth_mode: str = Field("shopyo", validation_alias="ANGEL_CLAW_AUTH_MODE")

    # Data & Persistence Settings
    user_data_root: str = Field("~/.angelclaw", validation_alias="USER_DATA_ROOT")
    
    @property
    def data_dir(self) -> Path:
        p = Path(self.user_data_root).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> str:
        return str(self.data_dir / "angelclaw.db")

    @property
    def memory_persist_dir(self) -> str:
        p = self.data_dir / "vaults"
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    @property
    def telegram_persist_dir(self) -> str:
        p = self.data_dir / "bridges" / "telegram"
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    @property
    def whatsapp_persist_dir(self) -> str:
        p = self.data_dir / "bridges" / "whatsapp"
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    # Proactive Messaging Settings
    proactive_webhook_url: Optional[str] = Field(
        None, validation_alias="PROACTIVE_WEBHOOK_URL"
    )

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

    # Lane Queue Settings
    lane_queue_global_max_tasks: int = Field(
        100, validation_alias="LANE_QUEUE_GLOBAL_MAX_TASKS"
    )
    lane_queue_default_concurrency: int = Field(
        2, validation_alias="LANE_QUEUE_DEFAULT_CONCURRENCY"
    )
    lane_queue_num_workers: int = Field(4, validation_alias="LANE_QUEUE_NUM_WORKERS")
    lane_queue_task_timeout_seconds: int = Field(
        300, validation_alias="LANE_QUEUE_TASK_TIMEOUT_SECONDS"
    )
    lane_queue_max_lane_depth: int = Field(
        100, validation_alias="LANE_QUEUE_MAX_LANE_DEPTH"
    )

    # Email Settings (IMAP/SMTP)
    smtp_host: Optional[str] = Field(None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(587, validation_alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(None, validation_alias="SMTP_USER")
    smtp_password: Optional[str] = Field(None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, validation_alias="SMTP_USE_TLS")

    # Google Calendar Settings (Service Account JSON)
    google_client_id: Optional[str] = Field(None, validation_alias="GOOGLE_CLIENT_ID")


settings = Settings()
