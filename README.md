
<h1 align="center">🪽 Angel Claw</h1>

<p align="center">
  <strong>Your Personal AI Agent Framework  with memory, skills, and multi-channel superpowers.</strong>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/github/license/abdur-rahmaanj/angel-claw" /></a>
  <a href="#"><img src="https://img.shields.io/pypi/v/angel-claw" /></a>
  <a href="https://pepy.tech/projects/angel-claw">
     <img 
       src="https://static.pepy.tech/personalized-badge/angel-claw?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads" 
       alt="PyPI Downloads"
     />
  </a>
</p>

---

## What Is Angel Claw?


**Angel Claw** is a powerful, extensible AI agent framework inspired by OpenClaw designed to give you:

- 🧠 Long-term, evolvable memory  
- 🛠 Self-generating skills & load skills from clawhub
- 🔌 Model Context Protocol (MCP) Host: standardized external tool interoperability 
- 📅 Proactive scheduling & automation  
- 🌍 Web browsing & tool usage  
- 📱 Telegram & WhatsApp integration  

All powered by:

- `angel-recall` for agent-native memory  
- `litellm` for multi-model LLM support  
- `FastAPI` as the gateway layer

```
$ pip install angel-claw
$ angel-claw chat  # Interactive setup wizard runs automatically!
$ angel-claw tutorial  # Start the guided tour
```

---

## 🎬 Quick Demo

> The agent learns, remembers, schedules, and extends itself  in plain English.

```text
> remember that I'm allergic to peanuts
> what should I avoid at the Thai restaurant?
```

Angel Claw retrieves stored memory and responds intelligently.

```text
> remind me to check the oven in 20 minutes
```

It schedules the task and executes it proactively.

```text
> create skill to shut down pc
> shut down pc
```

It writes and installs a new capability.

```text
> search clawhub for frontend skills
> use x skill
```

---

# ⭐ Why Angel Claw?

### Designed for Developers Who Want More Than Chat

| Feature | What It Means |
|----------|--------------|
| 🧠 **Agent-Native Memory** | Persistent long-term memory per session using `angel-recall`. |
| ⚡ **Multi-Model Support** | Connect to OpenAI, Anthropic, Ollama & more via `litellm`. |
| 🔁 **Proactive Tasks** | Built-in `cron`, `every`, and `at` scheduling engine. |
| 🌐 **Web Search & Automation** | Browse, extract, and summarize websites. |
| 🛠 **Self-Generating Skills** | Agent writes tools for itself dynamically. |
| 📱 **Telegram & WhatsApp** | Control your AI from your phone. |

---

# 🏁 Get Started in 30 Seconds

### 📦 Installation

```bash
pip install angel-claw
```

### ⚙️ Interactive Configuration

Run the chat command to start the integrated setup wizard:

```bash
angel-claw chat
```

The wizard will help you:
- Select your LLM provider (OpenAI, Anthropic, Ollama, etc.)
- Validate your API key
- Set up optional channels (Telegram, WhatsApp)
- Configure MCP servers

### 🎓 Guided Tutorial

New to Angel Claw? Run the interactive tutorial to learn the basics:

```bash
angel-claw tutorial
```

---

## ▶ Run the Gateway

```bash
angel-claw
```

You're live.

---

# 💬 Minimal Example (HTTP API)

Send a message to your agent:

```bash
curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"session_id": "user-123", "message": "Hi, I am Alex. Remember that I like Python.", "user_id": "alex"}'
```

The agent:

- Stores the fact
- Associates it with the session
- Uses it in future conversations

---

# 🧠 Core Capabilities

## Long-Term Memory

```text
Remember that I'm allergic to peanuts.
```

Later:

```text
What should I avoid at the Thai restaurant?
```

✔ Retrieves stored memory  
✔ Applies contextual reasoning  

---

## Proactive Scheduling

```text
Remind me to check the oven in 20 minutes.
```

```text
Every day at 9 AM check the weather in London.
```

```text
Schedule task 'daily-report' with cron: 0 18 * * *
```

Angel Claw executes autonomously.

---

## Web Search & Automation

```text
Search for the latest news about SpaceX and summarize it.
```

```text
Go to https://news.ycombinator.com and tell me the top story.
```

---

## Custom Skill Generation

```text
Create a skill called currency_converter using an API.
```

The agent:
- Writes tool code  
- Registers it  
- Immediately uses it  

---

## ClawHub Community Skills

```text
Search ClawHub for frontend skills.
Install the 'slopwork-marketplace' skill.
```

⚠ **Security Warning**  
ClawHub skills are community-contributed and unvetted. Always review skill code before use.

---

# 🔌 Model Context Protocol (MCP)

Angel Claw acts as a robust **MCP Host**, allowing you to consume external tools from any MCP-compliant server (local or remote).

### Configuration

Add your servers to `.env`:

```env
# Example: Local Node server and Remote Zapier server
MCP_SERVERS='{"everything": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}, "zapier": {"url": "https://mcp.zapier.com/api/v1/connect"}}'

# Example: Bearer token for Zapier
MCP_AUTH='{"zapier": {"token": "your_zapier_key"}}'
```

### Management Commands

```bash
# List all discovered MCP tools
angel-claw mcp list

# Test connections to MCP servers
angel-claw mcp test
```

### Features

- **Standardized Interoperability**: Use any tool from the growing MCP ecosystem.
- **Resilient Process Management**: Automatic restarts (max 3) with exponential backoff.
- **Concurrency Control**: Per-server semaphores to prevent saturation.
- **Security Guardrails**: 1MB output size capping and 30s timeouts.

---

# 📱 Multi-Channel Bridges

---

## Telegram Bridge

1. Create bot via `@BotFather`
2. Add `TELEGRAM_TOKEN` to `.env`
3. Start Angel Claw
4. Pair session:

```
/pair cli-default
```

Now your AI lives in Telegram.

---

## WhatsApp Bridge

Enable:

```env
WHATSAPP_ENABLED=True
```

Login:

```bash
angel-claw login-whatsapp
```

Scan QR → Pair session:

```
/pair cli-default
```

Now Angel Claw is on WhatsApp.

# 🩺 Troubleshooting

### "Authentication Error" or "401"
Your LLM API key is likely missing or incorrect.
- **Fix:** Run `angel-claw chat --reconfigure` to re-enter your key.

### "Model Not Found"
The model specified in your `.env` (e.g., `gpt-4o-mini`) is not available to your account or is misspelled.
- **Fix:** Run `angel-claw chat --reconfigure` and select a different model.

### MCP Server Fails to Connect
The command for a local MCP server might not be installed (e.g., `npx` not found).
- **Fix:** Ensure Node.js is installed or run `angel-claw mcp test` to diagnose specific server failures.

---

# 🧪 Testing

```bash
pytest
```

---

# 🤝 Contributing

We welcome contributions.

1. Fork the repository  
2. Create feature branch  
3. Submit PR  

See `CONTRIBUTING.md` for full guidelines.

---

# 💬 Community & Support

- 🐛 Issues: GitHub Issues  
- 💡 Feature Requests: Open a Discussion  
- 🌍 Skills: Explore ClawHub  
- ⭐ If you find this useful, give it a star!

---

# 📜 License

Apache 2.0 License.

---

## 🪽 Angel Claw

**Not just a chatbot. A persistent, evolving AI agent.**
