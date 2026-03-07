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

| Variable | Description | Default |
| :--- | :--- | :--- |
| `ANGEL_CLAW_VAULT_SALT` | Secret salt used for user vault encryption. **Change this in production!** | `default-salt...` |
| `DOCKER_SANDBOXING_ENABLED` | Set to `True` to enable containerized skill execution. | `False` |
| `DOCKER_RUNTIME` | The container runtime (use `runsc` for gVisor). | `runc` |
| `DOCKER_IMAGE` | The base image for the skill sandbox. | `python:3.11-slim` |
| `DOCKER_TIMEOUT` | Hard timeout (seconds) for skill execution. | `30` |
| `CLI_API_KEY` | The API Key used by the CLI to authenticate. | (Required) |

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
