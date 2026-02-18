# Angel Claw

A personal AI agent framework based on OpenClaw, using `angel-recall` for memory and `litellm` for LLM interactions.

## Features

- **FastAPI Gateway**: HTTP interface for interacting with the agent.
- **Agent-Native Memory**: Powered by `angel-recall`, providing long-term, evolvable memory for each session.
- **Multi-Model Support**: Uses `litellm` to connect to various providers (OpenAI, Anthropic, Ollama, etc.).
- **Lane-Based Isolation**: Each session has its own memory vault.

## Setup

1. **Install dependencies**:
   ```bash
   pip install angel-claw
   ```

2. **Configure environment**:
   Copy `.env.example` to `.env` and fill in your API keys.
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
