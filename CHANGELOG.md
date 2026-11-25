# Changelog

All notable changes to this project will be documented in this file.

## [0.16.0] - 2026-11-26

### Added

- Cron worker now reloads the shared job directory every 15s, so reminders created by the web app or CLI are picked up without a restart; job files are written atomically.
- A runner lease (`.cron_worker.lock`) keeps a single cron owner per data directory, preventing double-fired jobs when `serve` and `bridges` both run.
- Scheduled tasks appear in the Tasks tab, with pause/resume and delete actions, plus user-wide to-dos with working complete/delete.
- Skipped stale one-shot jobs are reported to the user instead of silently disappearing.
- `clear_completed_todos` todo skill restored.

### Fixed

- Cron worker task was garbage-collected at startup, silently stopping the scheduler; background task handles are now retained (`cli.py`, `gateway.py`).
- Jobs persisted on disk were never scheduled after a restart; the worker now schedules all loaded jobs on startup.
- Tasks tab read the wrong JSON shape and only ever showed the current session's to-dos.
- Deleting a reminder now removes its delivered internal message.
- Duplicate-reminder detection checks both sides of the target time.

### Security

- Registration is opt-in (`ALLOW_REGISTRATION`); self-signup is hidden by default.
- Skill uploads use sanitized file names and cannot escape the user's skills directory.
- Markdown and tool-log output are sanitized before rendering (stored XSS), and `marked` is pinned with an SRI hash.
- Usage summary is scoped to the viewer unless admin; mobile commands can only target the caller's own account.
- Mobile API routes have a single owning module.
- `SECRET_KEY` is generated and persisted instead of a public default; no default admin password.
- Login, registration and pairing attempts are throttled; pairing tokens are 12 digits and expire in 5 minutes.
- Skill installs are restricted to `https://` repositories and write to the user's skills directory; file tools and the browser stay inside uploads/public URLs.
- Session ids are sanitized before being used as file names; secrets, history and job files are owner-only (`0600`/`0700`).
- Pairing tokens are no longer logged; cross-user internal messages are rate-limited.
- Production cookies are `Secure`/`HttpOnly`/`SameSite=Lax` with 30-day sessions; `/api/version` no longer leaks the commit hash; SSO failure tracking is pruned.
- Bare `except:` handlers replaced with `except Exception:`.

## [0.11.0] - 2026-03-06

### Added

- **Multi-Tenant Agent OS Architecture**:
  - **Isolated UserRuntimes**: Dynamic instantiation of agent environments per user, ensuring zero state leakage.
  - **Runtime Manager (LRU)**: Efficient resource management with automatic eviction of idle runtimes from memory (Default idle: 30 mins).
  - **Tiered Skill Registry**: Clean separation between platform-wide read-only skills and user-specific custom skills.
  - **Fair-Share Scheduling**: Per-user task lanes in the global queue to prevent resource starvation by single tenants.
- **Encrypted Persistence**:
  - **User Vaults**: Encrypted storage (AES-128 Fernet) for per-user API keys and secrets, enabling "Bring Your Own Key" (BYOK).
  - **Private History**: Dedicated SQLite `history.db` per user for high-performance, isolated chat logging.
  - **Database Integration**: New Shopyo models for `UserSetting` and `UserVaultSecret` to support per-user config.
- **Security Hardening (Audit Remediation)**:
  - **Reasoning Safeguards**: Hard caps on reasoning turns (`MAX_TURNS=10`) and tool calls (`MAX_TOOLS_PER_TURN=20`).
  - **Recursive Workflow Shield**: Deterministic tracking and termination of agent-to-agent communication loops (Recursion Depth limit: 3).
  - **Unified Sandboxing**: Consolidated all tool execution (Platform & MCP) into a sandboxed environment with strict 30s-45s timeouts.
  - **Prompt Injection Defense**: Explicit "Untrusted" labeling for RAG context and delimiter stripping to prevent escape attacks.
  - **Identity Enforcement**: Mandatory API Key authentication for both the Gateway and the CLI (`CLI_API_KEY`).

### Fixed

- Resolved `RuntimeError` during startup by deferring background task creation to an active event loop.
- Fixed Flask async view compatibility issues using `asgiref.sync.async_to_sync`.
- Improved resource cleanup in the `RuntimeManager` background loop.

### Changed

- **README Refinement**: Complete overhaul to reflect the new "Agent OS" vision and comprehensive feature set including Peer-to-Peer messaging and multi-channel login guides.
- **Dependency Update**: Added `cryptography` and `asgiref` to core requirements.

## [0.10.1] - 2026-03-05

### Added
- **Internal Messaging Notification**: Proactive notification via bridges when an internal message is received.

### Fixed
- Telegram polling stability and status updates.
- Reliability of scheduled reminders in the cron engine.
- General bug fixes for session persistence and bridge hiccups.

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
