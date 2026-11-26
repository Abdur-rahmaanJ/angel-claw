# Developer API Reference

Angel Claw exposes two HTTP APIs:

| API | Start it with | Base URL | Authentication |
| --- | --- | --- | --- |
| Dashboard / companion API | `angel-claw serve` | `http://127.0.0.1:5000/api` | `Authorization: Bearer ac_v1_...` |
| Gateway API | `angel-claw gateway` | `http://127.0.0.1:8000` | Bearer key for `/chat`; optional webhook key for `/webhook` |

Ports can be changed in `.env`. The dashboard API is the one used by the web UI and
mobile app. The gateway is a lightweight FastAPI service for chat and webhooks.

---

## Authentication

Create a key in **Dashboard → Settings → API Keys** and copy it when it is shown;
the key cannot be displayed again.

```http
Authorization: Bearer ac_v1_your_key_here
```

Keys are scoped to the user who created them. Resources returned by the API (tasks,
chat history, messages, skills) are limited to that user.

The following endpoints do not require a key:

- `POST /api/mobile/login`
- `POST /api/mobile/pair`
- `GET /api/version`

The gateway's `GET /health` and, when `WEBHOOK_KEY` is unset, `POST /webhook` are also
unauthenticated.

### Error format

The dashboard API returns:

```json
{"status": "error", "message": "prompt is required"}
```

The gateway uses FastAPI's format:

```json
{"detail": "Invalid or inactive API key"}
```

---

## Scheduled Tasks API

A task runs one agent prompt at a chosen time. The task record stores the result, so a
client polls the API instead of listening for a message. Task jobs use reserved names;
the `schedule_task` agent tool cannot create or replace them.

All task endpoints require a bearer key.

### Create a task

```http
POST /api/tasks
Content-Type: application/json
```

```json
{
  "title": "Check availability",
  "prompt": "Search and report availability for the requested date.",
  "run_at": "2027-01-06T18:00:00+01:00"
}
```

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `prompt` | string | yes | Prompt the agent runs when the task fires. |
| `title` | string | no | Display title. Defaults to the first 60 characters of `prompt`; truncated to 200. |
| `run_at` | string or number | no | ISO-8601 date-time, epoch seconds, or omitted to run in about two seconds. |
| `session_id` | string | no | Conversation to run in. Defaults to a unique `task-...` session. Pass an existing thread id to give the prompt that thread's history. |

`run_at` rules:

- An offset such as `+01:00` or `Z` is converted to the server's local time.
- A value without an offset is treated as server-local time.
- A time more than one minute in the past returns `400`.
- A time within the last minute is moved to about two seconds from now.

Response `201`:

```json
{
  "status": "success",
  "task": {
    "id": 12,
    "title": "Check availability",
    "prompt": "Search and report availability for the requested date.",
    "status": "scheduled",
    "run_at": "2027-01-06T18:00:00+01:00",
    "result": null,
    "error": null,
    "attempts": 0,
    "session_id": "task-8c1f0e2a91",
    "created_at": "2026-11-26T10:15:00+01:00",
    "updated_at": "2026-11-26T10:15:00+01:00",
    "started_at": null,
    "finished_at": null
  }
}
```

### List tasks

```http
GET /api/tasks?status=scheduled&limit=50&offset=0
```

| Query | Default | Description |
| --- | --- | --- |
| `status` | all | One of `scheduled`, `running`, `succeeded`, `failed`, `cancelled`. |
| `limit` | `50` | `1`–`100`. |
| `offset` | `0` | Number of matching tasks to skip. |

Tasks are ordered by creation time, newest first.

```json
{
  "status": "success",
  "total": 1,
  "tasks": [
    {
      "id": 12,
      "title": "Check availability",
      "prompt": "Search and report availability for the requested date.",
      "status": "scheduled",
      "run_at": "2027-01-06T18:00:00+01:00",
      "result": null,
      "error": null,
      "attempts": 0,
      "session_id": "task-8c1f0e2a91",
      "created_at": "2026-11-26T10:15:00+01:00",
      "updated_at": "2026-11-26T10:15:00+01:00",
      "started_at": null,
      "finished_at": null
    }
  ]
}
```

An unknown `status` or non-numeric pagination value returns `400`.

### Get one task

```http
GET /api/tasks/12
```

Returns the same `task` object. A task belonging to another user returns `404`.

### Cancel a task

```http
POST /api/tasks/12/cancel
```

Removes the scheduled job and sets `status` to `cancelled` with `finished_at`.
Returns the task. Cancelling a running task marks the record cancelled; it cannot abort
work already executing, and a late result is not written to the record.

Returns `409` if the task is already `succeeded`, `failed` or `cancelled`, and `404` if
it does not exist.

### Run a task now

```http
POST /api/tasks/12/run
```

Re-schedules the task about two seconds from now, clears the previous result/error and
timestamps, sets `status` to `scheduled`, and returns `202` with the task. Any non-running
task can be re-run, including one that already finished or was cancelled.

Returns `409` while the task is `running`.

### Polling pattern

```bash
# Create
curl -sS -X POST "$BASE/api/tasks" \
  -H "Authorization: Bearer $ANGEL_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Check the example page and summarise it.","run_at":"2027-01-06T18:00:00+01:00"}'

# Poll until the status is terminal
curl -sS "$BASE/api/tasks/12" -H "Authorization: Bearer $ANGEL_KEY"
```

Statuses:

| Status | Meaning |
| --- | --- |
| `scheduled` | Waiting for `run_at`, or re-scheduled with `/run`. |
| `running` | The agent is executing the prompt. |
| `succeeded` | Finished; `result` contains the agent's answer. |
| `failed` | Finished with an error; `error` describes it. |
| `cancelled` | Cancelled before a current attempt completed. |

`attempts` increments when an attempt starts. `started_at` and `finished_at` are set for
the current attempt.

---

## Chat and session API

These endpoints use the same bearer key and live under `/api`.

### Send a message

```http
POST /api/mobile/chat
```

```json
{
  "message": "What is on my calendar today?",
  "session_id": "Thread 1",
  "ephemeral": false
}
```

| Field | Required | Description |
| --- | --- | --- |
| `message` | yes | User message. |
| `session_id` | no | Existing thread id. If omitted, the next `Thread N` is created. |
| `ephemeral` | no | If `true`, the thread is discarded after the response. Useful for integration traffic that should not appear in the user's thread list. |

Response:

```json
{
  "status": "success",
  "response": "You have a planning meeting at 14:00.",
  "session_id": "Thread 1"
}
```

### Stream a message

```http
POST /api/mobile/chat/stream
Accept: text/event-stream
```

Same request body as `/api/mobile/chat`. The response is `text/event-stream` with JSON
events:

```text
data: {"chunk": "You have a "}

data: {"chunk": "planning meeting at 14:00."}

data: {"done": true}
```

An execution error produces `data: {"error": "..."}`.

### List threads

```http
GET /api/chat/sessions
```

```json
{
  "status": "success",
  "sessions": [
    {"id": "Thread 2", "preview": "What is on my calendar today?"},
    {"id": "Thread 1", "preview": "Plan my week"}
  ]
}
```

`preview` is the first user message in the thread.

### Read a thread

```http
GET /api/chat/history/Thread%201
```

```json
{
  "status": "success",
  "history": [
    {"role": "user", "content": "Plan my week", "name": null, "tool_calls": null, "tool_call_id": null},
    {"role": "assistant", "content": "Here is a plan...", "name": null, "tool_calls": null, "tool_call_id": null}
  ]
}
```

---

## Mobile companion API

### Log in and obtain a key

```http
POST /api/mobile/login
```

```json
{"email": "you@example.com", "pass": "your-password", "device_name": "Pixel"}
```

Returns `{"status":"success","api_key":"ac_v1_..."}`. The key is permanent until
revoked. Failed attempts are rate-limited per IP.

### Pair with a token

```http
POST /api/mobile/pair
```

```json
{"token": "pairing-token", "device_name": "Pixel"}
```

Exchanges a time-limited pairing token for a permanent key. Passing an existing
`ac_v1_...` key as `token` validates and returns it. Invalid or expired tokens return
`401`.

### List inbox messages

```http
GET /api/mobile/messages
```

Returns the 50 newest internal messages addressed to the authenticated user:

```json
{
  "status": "success",
  "messages": [
    {
      "id": 7,
      "sender_email": "alice@example.com",
      "content": "The report is ready.",
      "created_at": "2026-11-26T09:30:00",
      "is_read": false
    }
  ]
}
```

### Fetch queued device commands

```http
GET /api/mobile/commands
```

Drains and returns the commands queued for the device:

```json
{
  "status": "success",
  "commands": [
    {"id": "1f5c...", "type": "send_sms", "params": {"to": "+15550100", "body": "Running late"}}
  ]
}
```

The queue is consumed by this call; a command is not returned twice.

### Report a command result

```http
POST /api/mobile/commands/result
```

```json
{
  "command_id": "1f5c...",
  "status": "success",
  "result": {"contact": "Ada", "number": "+15550100"}
}
```

If `result` is present and the command came from a chat session, the agent gets a
follow-up turn in that session and the reply is returned as `followup`; otherwise
`followup` is `null`.

### Report live capabilities

```http
POST /api/mobile/capabilities
```

```json
{
  "capabilities": [
    {"id": "sms", "label": "Send SMS"},
    {"id": "alarms", "label": "Set alarms"}
  ],
  "device": {"model": "Pixel 9", "os": "Android 16"}
}
```

The capabilities and device info are stored for the user and used when deciding which
mobile commands are possible.

---

## Skills API

### List skill modules

```http
GET /api/skills
```

```json
{
  "status": "success",
  "skills": [
    {"name": "browser", "description": "Drive a real browser: open pages, click, type, screenshot", "enabled": true, "tools": 6},
    {"name": "email", "description": "Send mail through your SMTP account", "enabled": false, "tools": 2}
  ]
}
```

### Enable or disable a module

```http
POST /api/skills/toggle
```

```json
{"skill": "email", "enabled": true}
```

Enabling a module also clears legacy per-tool disable flags for that module's tools, so
a tool hidden by an old `skill_config.json` entry becomes available again. Saved
credentials and other fields are preserved. The change applies to later turns.

---

## Utility endpoints

### Version

```http
GET /api/version
```

No authentication. Returns the installed package version:

```json
{"status": "success", "version": "0.19.1"}
```

---

## Gateway API

Start the gateway with `angel-claw gateway`. It listens on `http://127.0.0.1:8000` by
default.

### Chat

```http
POST /chat
Authorization: Bearer ac_v1_...
Content-Type: application/json
```

```json
{
  "session_id": "monitoring",
  "message": "Summarise the latest alert.",
  "user_id": "42"
}
```

`user_id` is required by the request schema, but the authenticated key determines the
actual user and permissions. `session_id` groups related messages.

```json
{
  "response": "The latest alert is a latency spike on the API.",
  "session_id": "monitoring"
}
```

### Health check

```http
GET /health
```

```json
{"status": "healthy"}
```

No authentication. Useful for load balancers and readiness checks.

### Webhook trigger

```http
POST /webhook
Content-Type: application/json
X-Webhook-Key: optional-configured-key
```

```json
{
  "message": "Deployment failed on production",
  "user_id": "42",
  "session_id": "monitoring-alerts"
}
```

If `WEBHOOK_KEY` is set in `.env`, the `X-Webhook-Key` header must match it. If it is
unset, the endpoint is open; set a key on any internet-facing deployment.

The agent processes the message and sends its response through the user's configured
proactive channel (for example Telegram or WhatsApp):

```json
{
  "status": "success",
  "agent_response": "I see the failed deployment; the error is a missing migration."
}
```

---

## Status codes

| Code | Meaning |
| --- | --- |
| `200` | Success. |
| `201` | Task created. |
| `202` | Task accepted for immediate execution. |
| `400` | Invalid JSON, missing required field, bad status filter, or invalid `run_at`. |
| `401` | Missing, invalid or revoked API key / pairing token. |
| `404` | Resource not found or owned by another user. |
| `409` | Task is already finished or already running. |
| `429` | Too many login or pairing attempts. |
| `500` | Agent or scheduling failure. |
