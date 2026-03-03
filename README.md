<h1 align="center">🪽 Angel Claw</h1>

<p align="center">
  <strong>The Multi-Tenant AI Agent Framework with memory, skills, and multi-channel superpowers.</strong>
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

**Angel Claw** is a powerful, extensible AI agent framework designed for both personal and multi-user environments. It provides a robust engine for building autonomous agents that learn, remember, and act across multiple platforms.

- 🧠 **Multi-Tenant Memory**: Isolated, long-term memory for every user.
- 🛠 **Extensible Skills**: Self-generating tools and community skills from ClawHub.
- 🔌 **MCP Host**: Standardized standardized external tool interoperability (Model Context Protocol).
- 📅 **Proactive Automation**: Built-in scheduling (cron, at, every) for autonomous actions.
- 📱 **Omni-Channel**: Consistent experience across Web, CLI, Telegram, and WhatsApp.
- 🔐 **Enterprise Ready**: Secure API keys, pairing tokens, and Shopyo-based user management.

```bash
$ pip install angel-claw
$ angel-claw serve  # Start the Web Dashboard
$ angel-claw chat   # Interactive CLI Chat
```

---

## 🚀 Key Features

| Feature                        | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| 👥 **Multi-User Support**      | Full identity management with Shopyo integration.           |
| 🧠 **Isolated Memory**         | User data stored securely in `~/.angelclaw/users/{user_id}`. |
| ⚡ **Multi-Model**             | OpenAI, Anthropic, Ollama & more via `litellm`.             |
| 🔁 **Proactive Tasks**         | Autonomous execution of scheduled jobs.                     |
| 🌐 **Web Dashboard**           | Modern UI for chat, pairing, and API key management.        |
| 🛠 **Dynamic Skills**          | Agent writes its own Python tools on the fly.               |
| 📱 **Secure Pairing**          | Link Telegram/WhatsApp using time-limited secure tokens.    |
| 🔑 **Developer APIs**          | Create and manage scoped API keys for external integration. |

---

## 🏁 Quick Start

### 📦 Installation

```bash
pip install angel-claw
```

### ⚙️ Setup

Run the setup wizard to configure your LLM and basic settings:

```bash
angel-claw chat
```

### 🌐 Run the Web Dashboard

Start the full multi-tenant environment:

```bash
angel-claw serve
```
Access at `http://localhost:5000`. Default admin: `admin@admin.com` / `admin`.

---

# 🧠 Core Architecture

### Identity & Context
Angel Claw uses a canonical `UserContext` to ensure every interaction is correctly attributed and isolated. Whether coming from a Web UI, a Telegram bot, or an API call, the engine knows exactly who the user is and what they should have access to.

### Storage Isolation
All user-specific data (memos, todos, calendar, chats) is stored under:
`~/.angelclaw/users/{user_id}/`

### Authentication Modes
- **Shopyo (Default)**: Full web-based user management, pairing, and API keys.
- **Internal**: Lightweight mode for single-user CLI/Local usage.

---

# 🔌 Model Context Protocol (MCP)

Angel Claw is a full **MCP Host**. Add your servers to `.env`:

```env
MCP_SERVERS='{"everything": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everything"]}}'
```

- `angel-claw mcp list`: View all discovered tools.
- `angel-claw mcp test`: Diagnose server connections.

---

# 📱 Multi-Channel Bridges

Control your AI from anywhere.

### Telegram
1. Add `TELEGRAM_TOKEN` to `.env`.
2. Generate a pairing token on the Web Dashboard.
3. Message your bot: `/pair <your-token>`.

### WhatsApp
1. Run `angel-claw login-whatsapp`.
2. Scan QR code.
3. Message the bot: `/pair <your-token>`.

---

# 💬 Developer API

Generate an API key in the Dashboard and use it to build your own integrations:

```bash
curl -X POST http://localhost:5000/agent/chat \
     -H "Authorization: Bearer ac_v1_..." \
     -H "Content-Type: application/json" \
     -d '{"message": "Remind me to call John tomorrow"}'
```

---

# 🧪 Testing

```bash
# Run engine and isolation tests
.venv/bin/pytest tests/test_basic.py tests/test_engine_todos.py

# Run Shopyo endpoint tests
PYTHONPATH=src/angel_claw/app .venv/bin/pytest tests/test_shopyo_endpoints.py
```

---

# 📜 License

Apache 2.0 License.

---

## 🪽 Angel Claw

**The multi-tenant, evolving AI agent framework.**
