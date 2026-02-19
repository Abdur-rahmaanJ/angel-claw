# 🪽 Angel Claw

A personal AI agent framework inspired by OpenClaw, using `angel-recall` for memory and `litellm` for LLM interactions.

## Features

- **FastAPI Gateway**: HTTP interface for interacting with the agent.
- **Multi-Channel Bridge**: Connect and pair your agent with **Telegram** for mobile access.
- **Agent-Native Memory**: Powered by `angel-recall`, providing long-term, evolvable memory for each session.
- **Proactive Tasks**: Built-in background worker for `at`, `every`, and `cron` schedules.
- **Multi-Model Support**: Uses `litellm` to connect to various providers (OpenAI, Anthropic, Ollama, etc.).

## Setup

1. **Install dependencies**:
   ```bash
   pip install angel-claw
   ```

2. **Configure environment**:
   Copy `.env.example` to `.env` and fill in your API keys.
   - `MODEL_KEY`: Your LLM API key.
   - `TELEGRAM_TOKEN`: (Optional) Your bot token from @BotFather.
   ```bash
   cp .env.example .env
   ```

3. **Run the gateway**:
   ```bash
   angel-claw
   ```

## Usage

For detailed instructions on how to use Angel Claw and its skills system, see the [Documentation](docs/index.md).

## Out-of-the-Box Capabilities

Angel Claw comes pre-loaded with several powerful features. Here are some examples of what you can do:

### 1. Long-Term Memory
The agent automatically stores and retrieves facts about you.
- **Prompt:** "Remember that I'm allergic to peanuts."
- **Prompt (Later):** "What should I avoid at the Thai restaurant?"
- **Result:** Angel Claw will retrieve your allergy fact and advise you accordingly.

### 2. Proactive Messaging & Scheduling
Schedule tasks or reminders that the agent will trigger on its own.
- **Prompt:** "Remind me to check the oven in 20 minutes."
- **Prompt:** "Every day at 9 AM, check the weather in London and message me if it's raining."
- **Prompt:** "Schedule a task named 'daily-report' to run `0 18 * * *` that summarizes my day."

### 3. Web Search & Browser Automation
The agent can browse the web to find information or interact with sites.
- **Prompt:** "Search for the latest news about SpaceX and summarize it."
- **Prompt:** "Go to https://news.ycombinator.com and tell me the top story."

### 4. Custom Skill Generation
If Angel Claw doesn't have a tool, it can write one for itself.
- **Prompt:** "Create a skill called 'currency_converter' that uses an API to convert USD to EUR."

### Telegram Bridge

You can interact with Angel Claw from your phone using Telegram:
1.  **Get a Bot Token**: Create a bot using [@BotFather](https://t.me/botfather) and add `TELEGRAM_TOKEN` to your `.env`.
2.  **Start your bot** on Telegram and press "Start".
3.  **Pair your chat**: Use the `/pair` command with your session ID (e.g., `/pair cli-default`).
4.  Angel Claw will now respond to your Telegram messages using that session's memory and skills.

### WhatsApp Bridge

Angel Claw supports WhatsApp via a "Link Device" (QR code) method:
1.  **Enable WhatsApp**: Add `WHATSAPP_ENABLED=True` to your `.env`.
2.  **Link Your Device**: Run the dedicated login command:
    ```bash
    angel-claw login-whatsapp
    ```
3.  **Scan QR Code**: Scan the QR code that appears in your terminal using your phone (WhatsApp > Linked Devices).
4.  **Start Angel Claw**: Once linked, you can run `angel-claw chat` as normal.
5.  **Pair your chat**: On WhatsApp, send `/pair <session-id>` (e.g., `/pair cli-default`) to yourself or the bot's number.
6.  Angel Claw is now connected to your WhatsApp!

### Basic Chat
Send a POST request to `/chat`:

```bash
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user-123", "message": "Hi, I am Alex. Remember that I like Python.", "user_id": "alex"}'
```

## Testing

```bash
pytest
```
