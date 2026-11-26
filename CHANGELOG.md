# Changelog

All notable changes to this project will be documented in this file.

## [0.17.1] - 2026-11-26

### Changed

- Running `angel-claw` with no arguments (or `python -m angel_claw`) now prints version, data directory, database/model status and the next commands, instead of silently starting the FastAPI gateway. Use `angel-claw gateway` for the API and `angel-claw serve` for the dashboard.
- `angel-claw --help` lists each command with a description; an unknown command shows the same status panel and exits non-zero.
- `angel-claw serve` no longer blocks on the setup wizard when it has no TTY (systemd/Docker); it prints the missing `MODEL_KEY` instruction and continues.
- `python -m angel_claw.main` and the repository `main.py` now delegate to the CLI.

## [0.17.0] - 2026-11-26

### Added

- Web building blocks: `web_search` (Exa, Brave, or Lightpanda's keyless search) and `web_read` (Lightpanda markdown, HTTP fallback). They let the agent research menus, deals and table availability without a site-specific booking skill.
- Lightpanda is bundled on Linux/macOS and now powers `web_read` and the `browser_*` tools; Chromium and Playwright are no longer needed for scraping.
- Progressive skill loading: only calendar, reminders, todos, memory, scheduling and web tools are in the prompt; `list_skill_modules` and `load_skill_tools` expose browser, files, email and the rest on demand. Tool schemas are refreshed between turns of the same request.
- Scheduled `prompt` tasks now store their result in the web Messages inbox, so a task set for a future date is not executed into the void.

### Changed

- Skills settings now list modules (one card per skill file) instead of individual tool functions; a toggle applies to the whole module.
- Email, OpenWeather, Google Calendar, internal messaging and mobile tools are disabled by default; they stay installed and can be enabled in Settings -> Skills.
- `browser_search` was replaced by `web_search`.
- The non-streaming system prompt now includes the current date and guidance for scheduling future actions and loading missing tools.

## [0.16.3] - 2026-11-26

### Fixed

- Skill settings no longer silently reset: if `skill_config.json` exists but cannot be read or parsed, the config endpoint returns an error and the dialog refuses to open instead of showing blank fields whose Save would wipe the stored credentials.
- Opening another skill's settings while a request is still in flight no longer leaves the dialog showing the earlier skill's fields under the later skill's name.
- `schedule_task` rejects names starting with `reminder_`, which were reserved for reminders and left the task hidden from both the Tasks and Reminders tabs.
- Reminder timestamps are serialized with the server's UTC offset, so a browser in a different timezone no longer skips the notification or displays a shifted due time.

## [0.16.2] - 2026-11-26

### Changed

- A reminder now appears only in the Reminders tab: its backing cron job is hidden from Scheduled Tasks, and firing it no longer writes a `🔔 REMINDER:` item into Messages. The dashboard polls reminders and shows a toast/browser notification instead.

### Fixed

- Calendar returned 500 whenever events existed (and the calendar tab showed none); per-session events are merged for the calendar tab and dashboard, and first-event creation no longer fails on a missing directory.
- Chat streaming dropped tokens that were split across network reads and ignored HTTP/session errors; partial replies are kept with the error, session expiry reloads to login, and leaving a thread cancels its stream.
- Reloading the dashboard always started a new chat thread instead of restoring the active one.
- Failed mutations for tasks, messages, reminders, API keys, memories, skill config and thread deletion were shown as successes.
- Unknown `/view/<name>` returned 500 instead of 404, and expired sessions injected the login page into the dashboard.
- To-do counts were padded to 1 when empty and only counted the current chat session; the dashboard counted events for the default session only and labelled a year of events as "7 days".
- Dashboard load failures displayed zeros without a retry path.
- Pairing tokens were minted on every dashboard load and usually expired before the dialog opened; the Telegram "Connect" button never opened the pairing dialog and integrations ignored bridge status.
- Login validation errors were hidden, clipboard failures were silent, and the browser notification for an unread message repeated on every 30s poll.
- Chat and password inputs were unreadable in light theme.

### Security

- Skill credentials are no longer serialized into the dashboard HTML; the config dialog fetches them on demand.
- The service worker no longer caches authenticated dashboard pages or arbitrary cross-origin responses, and only known CDN hosts are cached.

## [0.16.1] - 2026-11-26

### Fixed

- Chat memory is retrieved with the user's message instead of returning the newest cubes from a fixed namespace list; an empty query now injects no memory rather than unrelated facts.
- Memory skills use the authenticated account email, so `store_memory`/`search_memory` and the engine share one memory owner.
- Semantic relevance order is preserved and results are expanded one hop through related memories; archived memories and memories the user cannot read are excluded.
- New memories are linked to semantically related memories, and graph edges are persisted so relationships survive a restart.
- Embedding-less retrieval no longer falls back to substring or word matching: angel-recall asks the LLM to select relevant memories and returns nothing when no model is available.

### Changed

- Bumped `angel-recall` to 0.5.1.

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

## [0.15.3] - 2026-11-25

### Added

- Scheduling now runs on APScheduler (date, interval and cron triggers) instead of a hand-rolled poll loop.
- Installable PWA: service worker, install button and manifest served from the site root.

### Fixed

- One-shot reminders and repeating jobs now fire through the scheduler.

## [0.15.2] - 2026-10-20

### Fixed

- Restored the stale calendar skill tests and fixed core test failures around cron schedule clobbering, `/chat` JSON clients and test isolation.

## [0.15.1] - 2026-10-19

### Fixed

- `angel-claw --help` no longer hangs on heavy imports.

### Changed

- Credit usage now updates for integrated apps; added 0.15.0 release notes.

## [0.15.0] - 2026-10-13

### Added

- Streaming mobile chat over SSE under token auth.
- Ephemeral mobile chats so integrations do not appear in the chat UI.
- SSO `key`/`token`/`verify` endpoints and usage tracking for ask-moris.

## [0.14.0] - 2026-10-08

### Added

- Admin model configuration UI with an opt-in env writer (atomic replace, newline-injection guard, secret masking).
- Shared mobile bridge state across gunicorn workers via a file-backed store.
- Direct API-key pairing for the mobile app, plus device info context and command-result follow-ups.
- Live phone capability reporting, automatic thread creation for mobile chats, and a public `/api/version` probe.
- Web UI polish: skeleton loaders and retryable error states, toast/confirm modals, unread badge, hash routing, markdown copy support and Android support.

### Fixed

- Reminder delivery skipped because the runtime manager lacks `_app`.
- One-shot reminders never firing; reminder and chat loading regressions.
- Mobile chat history `TypeError` and mobile chat error logging (traceback added).
- Dead "Create Key" button, copy-to-clipboard null `querySelector`, send-button alignment, markdown display/scroll and delete-thread behaviour.

## [0.13.0] - 2026-04-10

### Added

- Skills: upload, per-skill configuration UI and skill listing.
- SOUL.md customization UI for per-user agent personas.
- Mail-style chat UI with thread selection, memory deletion and improved tabs.

### Fixed

- Chat history not shown after switching threads and generator context errors.
- Internal messaging, soul loading, tab selection and console errors.
- Memory visibility/sync, double-noted memories, global memory and preference bugs.
- Credit display and chat response rendering issues.

## [0.12.0] - 2026-04-06

### Added

- Chat threads with per-thread history and sidebar navigation.
- PWA support, persistent login and a custom login UI.
- Calendar view, internal-message deletion, dashboard counters and unread status.
- `create-admin` and `update-password` CLI commands and a setup wizard with flags.
- Optional Redis lane queue, Redis-backed LLM response cache and centralized SQLAlchemy history.
- Telegram image receiving and user-specific chat directories under `~/.angelclaw/users/{user_id}/chats`.

### Fixed

- Streaming chat, credits accounting and mobile responsiveness.
- DB initialization, Pydantic v2 compatibility, absolute DB path and gateway isolation.
- High CPU usage in the lane worker loop, internal messaging app-context errors and a `UserContext` `TypeError`.
- Missing auth migrations and gitignore handling for database files.

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
