# Changelog

All notable changes to this project will be documented in this file.

## [0.10.1] - 2026-03-06

### Added

- **Multi-Tenant Agent OS Architecture**:
  - **Isolated UserRuntimes**: Dynamic instantiation of agent environments per user, ensuring zero state leakage.
  - **Runtime Manager (LRU)**: Efficient resource management with automatic eviction of idle runtimes from memory.
  - **Tiered Skill Registry**: Clean separation between platform-wide read-only skills and user-specific custom skills.
  - **Fair-Share Scheduling**: Per-user task lanes in the global queue to prevent resource starvation by single tenants.
- **Encrypted Persistence**:
  - **User Vaults**: Encrypted storage (AES-128 Fernet) for per-user API keys and secrets, enabling "Bring Your Own Key" (BYOK).
  - **Private History**: Dedicated SQLite `history.db` per user for high-performance, isolated chat logging.
  - **Database Integration**: New Shopyo models for `UserSetting` and `UserVaultSecret`.
- **Security Hardening (Audit Remediation)**:
  - **Reasoning Safeguards**: Hard caps on reasoning turns (`MAX_TURNS=10`) and tool calls (`MAX_TOOLS_PER_TURN=20`).
  - **Recursive Workflow Shield**: Deterministic tracking and termination of agent-to-agent communication loops.
  - **Unified Sandboxing**: Consolidated all tool execution (Platform & MCP) into a sandboxed environment with strict 30s-45s timeouts.
  - **Prompt Injection Defense**: Explicit "Untrusted" labeling for RAG context and delimiter stripping to prevent escape attacks.
  - **Identity Enforcement**: Mandatory API Key authentication for both the Gateway and the CLI.

### Fixed

- Resolved `RuntimeError` during startup by deferring background task creation to an active event loop.
- Fixed Flask async view compatibility issues using `asgiref.sync.async_to_sync`.
- Improved resource cleanup in the `RuntimeManager` background loop.

### Changed

- **README Refinement**: Complete overhaul to reflect the new "Agent OS" vision and comprehensive feature set.
- **Dependency Update**: Added `cryptography` and `asgiref` to core requirements.

## [0.9.0] - 2026-02-26

### Added

- **Chat History Logging**:
  - Chats are now automatically logged to `.angelclaw/chats/year/month/day.md`
  - New skills: `get_chat_history(date)` and `get_chat_history_range(start_date, end_date)`
  - Supports session filtering for multi-user scenarios
- **Todo Management Skill**:
  - Full CRUD for todos: `add_todo`, `list_todos`, `complete_todo`, `delete_todo`, `update_todo`
  - Priority levels (low/medium/high), due dates, session isolation
- **Calendar Skill**:
  - Local calendar events stored in `.angelclaw/calendar/`
  - Skills: `create_calendar_event`, `list_calendar_events`, `delete_calendar_event`, `update_calendar_event`, `check_availability`, `get_today_events`
- **Email Skill**:
  - SMTP-based email sending via `send_email` and `send_email_with_template`
  - Supports HTML emails, CC/BCC, templates
- **Google Calendar Integration**:
  - Service Account-based OAuth (no user interaction needed)
  - Skills: `gcal_create_event`, `gcal_list_events`, `gcal_delete_event`, `gcal_check_status`
- **File Handler Skill**:
  - Save/upload files to `.angelclaw/uploads/`
  - `extract_pdf_text` - Extract text from PDFs
  - `analyze_image` - AI vision analysis using LLM
  - `extract_text_from_image` - OCR using pytesseract

### Security

- **Webhook Authentication**: Added optional `WEBHOOK_KEY` for API authentication
- **MCP Auth Validation**: Prevent header injection in MCP tokens
- **API Key Validation**: Reject placeholder/empty API keys

### Fixed

- Memory leak in lane_queue - proper cleanup of results/events
- TTL-based cleanup for processed tasks (was clearing all)
- WhatsApp bridge close method - proper resource cleanup
- Telegram bridge graceful shutdown
- History bounds checking for empty history
- Duplicate code in mcp_manager and skills

### Refactored

- Extracted magic numbers to constants in lane_queue
- Simplified cron schedule parsing with dictionary mapping
- Extracted duplicate date parsing and session filtering to helpers

## [0.8.0] - 2026-02-24

### Added

- **Lane-based Task Management**:
  - Introduced a robust internal queuing system (`lane_queue`) for request processing.
  - Improved concurrency control and task isolation through "lanes".
  - Background workers now handle chat requests asynchronously for better responsiveness.
  - Configurable queue parameters (workers, timeouts, concurrency) via environment variables.
- **Custom API Base Support**:
  - Added support for `MODEL_BASE_URL` in `.env`.
  - Users can now connect to any OpenAI-compatible endpoint (e.g., NVIDIA NIM, LiteLLM proxy, local Ollama).
  - CLI commands now support `--model` and `--api-base` overrides.

### Changed

- **Clean CLI Experience**:
  - Refactored the CLI to utilize the new lane-based processing engine.
  - Optimized logging and output formatting for a more focused, noise-free interface.
- **Improved Project Structure**:
  - Relocated `.env.example` to the internal package directory for better distribution and consistency.

### Removed

- Top-level `.env.example` (merged into the package structure).

## [0.6.0] - 2026-02-21

### Added

- **Full Model Context Protocol (MCP) Support**: Angel Claw now acts as a robust MCP Host.
  - Support for both local `stdio` (command-based) and remote `sse` (HTTP-based) servers like Zapier.
  - **MCP Authentication**: Handles bearer tokens and custom headers via `MCP_AUTH`.
  - **Resilient Connections**: Automatic server restarts with exponential backoff (up to 3 attempts).
  - **Concurrency Control**: Per-server semaphores to prevent resource saturation.
  - **Security Guardrails**: Strict 30s timeouts and configurable output size limits (`MCP_MAX_OUTPUT_SIZE`) to prevent `RateLimitError`.
- **MCP Management CLI**:
  - `angel-claw mcp list`: Discovers and lists all tools from configured MCP servers.
  - `angel-claw mcp test`: Verifies connectivity to all configured MCP servers.
- **FastAPI Modernization**: Migrated `gateway.py` from deprecated `on_event` handlers to the modern `lifespan` context manager.
- **Python 3.10+ Support**: Lowered minimum Python version to 3.10 and added backward compatibility for `ExceptionGroup` handling.

### Fixed

- Improved JSON parsing for `.env` strings to handle literal single quotes.
- Fixed `RateLimitError` when tools (like Gmail) returned oversized results.

## [0.5.0] - 2026-02-20

### Added

- **Automatic .env Creation**: When running `angel-claw chat` or `login-whatsapp`, a `.env` file is automatically created from `.env.example` if it doesn't exist.
- **ClawHub Integration**: Users can now search for and install community-contributed skills from [ClawHub.ai](https://clawhub.ai).
- **Local Skills Management**: Skills created or installed are now stored in the local `./skills` directory for easier management and persistence.

## [0.4.0] - 2026-02-15

### Added

- **WhatsApp Bridge**: Initial support for linking WhatsApp via QR code (`login-whatsapp` command).
- **Telegram Improvements**: Better handling of reminders and UI cleanup in the Telegram bridge.
- **ClawHub Search**: Enhanced search capabilities for finding skills.

### Fixed

- WhatsApp bot reply errors and group message filtering.
- CLI "You:" prompt visibility issues.
- General session persistence bugs.

## [0.3.0] - 2026-01-20

### Added

- Core agent framework with Multi-Channel support.
- Initial FastAPI Gateway implementation.
- Support for `litellm` model switching.
