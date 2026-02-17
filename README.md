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
