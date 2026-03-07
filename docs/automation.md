# Automation & Proactive Tasks

Angel Claw features a powerful built-in automation engine that allows your agent to act autonomously on a schedule. This document explains how the `CronManager` and proactive triggers work.

---

## 1. Task Types

The system supports three primary types of autonomous tasks:

- **Message**: Send a raw text message to the user at a specific time.
- **Prompt**: Send a specific instruction to the LLM at a scheduled time. The agent will process the prompt and proactively notify the user of the result.
- **Skill**: Execute a specific Python skill function automatically.

## 2. Scheduling Options

Angel Claw supports flexible scheduling using several formats:

- **At**: Execute once at a specific date and time (`YYYY-MM-DD HH:MM:SS`).
- **Every**: Execute repeatedly at a fixed interval (e.g., `10m`, `1h`, `1d`).
- **Cron**: Standard crontab expressions for complex recurring schedules (e.g., `0 9 * * 1-5` for every weekday at 9 AM).
- **In**: Execute once after a specific delay (e.g., `30m`).

## 3. How it Works

1.  **Job Persistence**: Jobs are stored as JSON files in `~/.angelclaw/memory/cron/`. 
2.  **Worker Loop**: A background thread (managed by `cron_manager`) wakes up every 10 seconds to check for due jobs.
3.  **Execution**: When a job is due, the manager instantiates the appropriate `UserRuntime` and executes the task.
4.  **Proactive Handlers**: Once a task completes, the result is sent to all active "proactive handlers" (Telegram, WhatsApp, Web Dashboard) to notify the user.

## 4. Example Commands

You can tell your agent to schedule tasks using natural language:

- "Remind me to buy milk in 2 hours."
- "Every morning at 8 AM, tell me the weather forecast for London."
- "On March 15th at 3 PM, check my calendar for the following day."
- "Stop the weather reminder job."

---

## 🛡️ Recursive Shield

To prevent accidental loops (e.g., a scheduled prompt that triggers another scheduled prompt), the automation engine respects the global **Recursion Depth Limit**. Any proactive trigger that attempts to nest beyond 3 levels will be automatically terminated.
