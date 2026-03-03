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
- 💬 **Peer-to-Peer Messaging**: Users can send internal notes and messages to each other via the AI agent.

```bash
$ pip install angel-claw
$ angel-claw serve    # Start the Web Dashboard
$ angel-claw bridges  # Start background bridges (Production)
$ angel-claw chat     # Interactive CLI Chat
```

---

## 🚀 Key Features

| Feature                        | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| 👥 **Multi-User Support**      | Full identity management with Shopyo integration.           |
| 🧠 **Isolated Memory**         | User data stored securely in `~/.angelclaw/users/{user_id}`. |
| ⚡ **Multi-Model**             | OpenAI, Anthropic, Ollama & more via `litellm`.             |
| 🔁 **Proactive Tasks**         | Autonomous execution of scheduled jobs.                     |
| ✅ **Todo Management**         | Native task tracking with priorities and due dates.        |
| 📅 **Calendar Sync**           | Manage events and sync with Google Calendar.                |
| 🌐 **Web Dashboard**           | Modern UI with 🪽 branding and connection indicators.       |
| ✉️  **Internal Notes**         | Send peer-to-peer messages: "Send a note to alice@dev.com telling check fridge". |
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

# 🏗️ Production Architecture

Angel Claw is designed for robust production deployment by separating the Web UI from background tasks.

### Dedicated Bridge Worker
To prevent Telegram/WhatsApp session conflicts when using multiple web workers (Gunicorn), run the bridges in their own process:
```bash
angel-claw bridges
```

### 📦 Package-First Persistence
All data is stored outside the package directory for safe updates:
*   **DB**: `~/.angelclaw/angelclaw.db`
*   **Bridges**: `~/.angelclaw/bridges/`
*   **Vaults**: `~/.angelclaw/vaults/`

See [DEPLOY.md](./DEPLOY.md) for full Nginx, Gunicorn, and Systemd templates.

---

# 💬 Internal Messaging

Angel Claw supports secure, internal communication between users. The agent handles delivery and notification.

**Commands:**
*   "Send an internal note to bob@example.com telling him the meeting is at 5"
*   "Do I have any unread messages?"
*   "Tell alice@dev.com that I finished the report"

---

# 🛠️ Built-in Skills

Angel Claw comes with high-quality native skills that integrate deeply with its memory.

### ✅ Todo Management
Keep track of your life without leaving the chat.
*   "Add a high priority todo: Buy milk by Friday"
*   "Show my pending todos"
*   "Mark todo 1 as complete"

### 📅 Calendar Integration
Manage your schedule and sync with external providers.
*   "Schedule a meeting with Sarah tomorrow at 2pm"
*   "What's on my calendar for next week?"
*   "Sync my events with Google Calendar"

---

# 📱 Multi-Channel Bridges
...

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
