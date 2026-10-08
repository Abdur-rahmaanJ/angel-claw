"""Configuration schema for every .env variable.

Source of truth: docs/configuration.md
Each field: key (.env name), label, hint, default, type, secret, required.
"""

SECTIONS = [
    {
        "name": "llm",
        "title": "LLM Settings",
        "fields": [
            {
                "key": "MODEL",
                "label": "Model",
                "hint": "The model name (e.g. openai/gpt-4o).",
                "default": "openai/gpt-4o-mini",
                "type": "text",
                "required": True,
            },
            {
                "key": "MODEL_KEY",
                "label": "Model API Key",
                "hint": "Your LLM provider API key.",
                "default": "",
                "type": "password",
                "secret": True,
                "required": True,
            },
            {
                "key": "MODEL_BASE_URL",
                "label": "Model Base URL",
                "hint": "Optional: custom endpoint for OpenAI-compatible APIs.",
                "default": "",
                "type": "text",
            },
        ],
    },
    {
        "name": "gateway",
        "title": "Gateway Settings",
        "fields": [
            {
                "key": "HOST",
                "label": "Host",
                "hint": "Host address to bind the server.",
                "default": "0.0.0.0",
                "type": "text",
            },
            {
                "key": "PORT",
                "label": "Port",
                "hint": "Port to run the Gateway.",
                "default": "8000",
                "type": "number",
            },
            {
                "key": "DEBUG",
                "label": "Debug",
                "hint": "Enable debug logging and features.",
                "default": "True",
                "type": "checkbox",
            },
            {
                "key": "WEBHOOK_KEY",
                "label": "Webhook Key",
                "hint": "Secret key required in the X-Webhook-Key header.",
                "default": "",
                "type": "password",
                "secret": True,
            },
        ],
    },
    {
        "name": "security",
        "title": "Security & Sandboxing",
        "fields": [
            {
                "key": "ANGEL_CLAW_VAULT_SALT",
                "label": "Vault Salt",
                "hint": "Secret salt used for user vault encryption. Change this in production!",
                "default": "default-salt-change-me",
                "type": "password",
                "secret": True,
            },
            {
                "key": "DOCKER_SANDBOXING_ENABLED",
                "label": "Docker Sandboxing",
                "hint": "Enable containerized skill execution.",
                "default": "False",
                "type": "checkbox",
            },
            {
                "key": "DOCKER_RUNTIME",
                "label": "Docker Runtime",
                "hint": "Container runtime (runsc for gVisor).",
                "default": "runc",
                "type": "select",
                "options": ["runc", "runsc"],
            },
            {
                "key": "DOCKER_IMAGE",
                "label": "Docker Image",
                "hint": "Base image for the skill sandbox.",
                "default": "python:3.11-slim",
                "type": "text",
            },
            {
                "key": "DOCKER_TIMEOUT",
                "label": "Docker Timeout",
                "hint": "Hard timeout (seconds) for skill execution.",
                "default": "30",
                "type": "number",
            },
            {
                "key": "CLI_API_KEY",
                "label": "CLI API Key",
                "hint": "The API key used by the CLI to authenticate.",
                "default": "",
                "type": "password",
                "secret": True,
                "required": True,
            },
        ],
    },
    {
        "name": "scalability",
        "title": "Scalability (Redis & Database)",
        "fields": [
            {
                "key": "REDIS_ENABLED",
                "label": "Redis",
                "hint": "Use Redis for task queuing.",
                "default": "False",
                "type": "checkbox",
            },
            {
                "key": "REDIS_URL",
                "label": "Redis URL",
                "hint": "Connection string for your Redis instance.",
                "default": "redis://localhost:6379/0",
                "type": "text",
            },
            {
                "key": "REDIS_QUEUE_NAME",
                "label": "Redis Queue Name",
                "hint": "Name of the Redis key used for the queue.",
                "default": "angel_claw_lane_queue",
                "type": "text",
            },
            {
                "key": "HISTORY_DATABASE_URI",
                "label": "History Database URI",
                "hint": "SQLAlchemy connection string for centralized history (e.g. PostgreSQL). Empty = per-user SQLite.",
                "default": "",
                "type": "text",
            },
        ],
    },
    {
        "name": "performance",
        "title": "Performance (Caching)",
        "fields": [
            {
                "key": "CACHE_ENABLED",
                "label": "Cache",
                "hint": "Enable Redis-based LLM response caching.",
                "default": "False",
                "type": "checkbox",
            },
            {
                "key": "CACHE_TTL",
                "label": "Cache TTL",
                "hint": "Time-to-live (seconds) for cached responses.",
                "default": "3600",
                "type": "number",
            },
        ],
    },
    {
        "name": "bridge",
        "title": "Bridge Settings",
        "fields": [
            {
                "key": "TELEGRAM_TOKEN",
                "label": "Telegram Token",
                "hint": "Your Telegram Bot API token.",
                "default": "",
                "type": "password",
                "secret": True,
            },
            {
                "key": "WHATSAPP_ENABLED",
                "label": "WhatsApp Bridge",
                "hint": "Enable the WhatsApp bridge.",
                "default": "False",
                "type": "checkbox",
            },
            {
                "key": "BRAVE_API_KEY",
                "label": "Brave API Key",
                "hint": "API key for the browser and search skills.",
                "default": "",
                "type": "password",
                "secret": True,
            },
        ],
    },
    {
        "name": "mcp",
        "title": "MCP Settings",
        "fields": [
            {
                "key": "MCP_SERVERS",
                "label": "MCP Servers",
                "hint": "JSON string defining the MCP servers to connect to.",
                "default": "",
                "type": "textarea",
                "json": True,
            },
            {
                "key": "MCP_AUTH",
                "label": "MCP Auth",
                "hint": "JSON string providing credentials for remote MCP servers.",
                "default": "",
                "type": "textarea",
                "json": True,
            },
        ],
    },
    {
        "name": "email",
        "title": "Email Settings (SMTP)",
        "fields": [
            {
                "key": "SMTP_HOST",
                "label": "SMTP Host",
                "hint": "The SMTP server host.",
                "default": "",
                "type": "text",
            },
            {
                "key": "SMTP_PORT",
                "label": "SMTP Port",
                "hint": "The SMTP server port.",
                "default": "587",
                "type": "number",
            },
            {
                "key": "SMTP_USER",
                "label": "SMTP User",
                "hint": "SMTP username.",
                "default": "",
                "type": "text",
            },
            {
                "key": "SMTP_PASSWORD",
                "label": "SMTP Password",
                "hint": "SMTP password.",
                "default": "",
                "type": "password",
                "secret": True,
            },
            {
                "key": "SMTP_USE_TLS",
                "label": "SMTP TLS",
                "hint": "Use TLS for SMTP connection.",
                "default": "True",
                "type": "checkbox",
            },
        ],
    },
    {
        "name": "google_calendar",
        "title": "Google Calendar",
        "fields": [
            {
                "key": "GOOGLE_CLIENT_ID",
                "label": "Google Client ID",
                "hint": "Either the path to a service account JSON file or the JSON content itself.",
                "default": "",
                "type": "textarea",
            },
        ],
    },
]

FIELDS = [field for section in SECTIONS for field in section["fields"]]
FIELD_BY_KEY = {field["key"]: field for field in FIELDS}

JSON_KEYS = [field["key"] for field in FIELDS if field.get("json")]
SECRET_KEYS = [field["key"] for field in FIELDS if field.get("secret")]
NUMBER_KEYS = [field["key"] for field in FIELDS if field["type"] == "number"]
CHECKBOX_KEYS = [field["key"] for field in FIELDS if field["type"] == "checkbox"]

LLM_KEYS = ["MODEL", "MODEL_KEY", "MODEL_BASE_URL"]


def defaults() -> dict:
    """All keys with their default values (for creating a fresh .env)."""
    return {field["key"]: field.get("default", "") for field in FIELDS}
