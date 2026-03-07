# Configuration Reference (.env)

Angel Claw is configured primarily via environment variables. This document provides a complete reference of all available settings.

---

## 🧠 LLM Settings

| Variable | Description | Default |
| :--- | :--- | :--- |
| `MODEL` | The model name (e.g., `openai/gpt-4o`). | `openai/gpt-4o-mini` |
| `MODEL_KEY` | Your LLM provider API key. | (Required) |
| `MODEL_BASE_URL`| Optional: Custom endpoint for OpenAI-compatible APIs. | None |

## 🌐 Gateway Settings

| Variable | Description | Default |
| :--- | :--- | :--- |
| `HOST` | Host address to bind the server. | `0.0.0.0` |
| `PORT` | Port to run the Gateway. | `8000` |
| `DEBUG` | Enable/disable debug logging and features. | `True` |
| `WEBHOOK_KEY` | Secret key required in the `X-Webhook-Key` header. | None |

## 🛡️ Security & Sandboxing
...
| `CLI_API_KEY` | The API Key used by the CLI to authenticate. | (Required) |

## 🚀 Scalability (Redis & Database)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `REDIS_ENABLED` | Set to `True` to use Redis for task queuing. | `False` |
| `REDIS_URL` | The connection string for your Redis instance. | `redis://localhost:6379/0` |
| `REDIS_QUEUE_NAME`| The name of the Redis key used for the queue. | `angel_claw_lane_queue` |
| `HISTORY_DATABASE_URI` | SQLAlchemy connection string for centralized history management (e.g., PostgreSQL). | None |

## ⚡ Performance (Caching)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `CACHE_ENABLED` | Set to `True` to enable Redis-based LLM response caching. | `False` |
| `CACHE_TTL` | Time-to-live (seconds) for cached responses. | `3600` |

## 📱 Bridge Settings

| Variable | Description | Default |
| :--- | :--- | :--- |
| `TELEGRAM_TOKEN` | Your Telegram Bot API token. | None |
| `WHATSAPP_ENABLED` | Enable/disable the WhatsApp bridge. | `False` |
| `BRAVE_API_KEY` | API Key for the `browser` and `search` skills. | None |

## 🔌 MCP Settings

| Variable | Description |
| :--- | :--- |
| `MCP_SERVERS` | A JSON string defining the MCP servers to connect to. |
| `MCP_AUTH` | A JSON string providing credentials for remote MCP servers. |

## 📧 Email Settings (SMTP)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `SMTP_HOST` | The SMTP server host. | None |
| `SMTP_PORT` | The SMTP server port. | `587` |
| `SMTP_USER` | SMTP username. | None |
| `SMTP_PASSWORD` | SMTP password. | None |
| `SMTP_USE_TLS` | Use TLS for SMTP connection. | `True` |

## 📅 Google Calendar

| Variable | Description |
| :--- | :--- |
| `GOOGLE_CLIENT_ID` | Either the path to a service account JSON file or the JSON content itself. |
