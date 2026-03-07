<h1 align="center">🪽 Angel Claw</h1>

<p align="center">
  <strong>The Multi-Tenant Agent Operating System.</strong><br>
  Isolated runtimes, tiered skills, and encrypted vaults for secure, high-density AI deployments.
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

## 🚀 The Agent OS Vision

**Angel Claw** is a high-density **Agent Operating System**. Built for both personal productivity and enterprise multi-tenancy, it provides a "Shared-Nothing" architecture where every user operates within a fully isolated, secure environment.

- 🧠 **Multi-Tenant Memory**: Isolated, long-term memory for every user.
- ✉️ **Peer-to-Peer Messaging**: Users can send internal notes and messages to each other via the AI agent.
- 🛠 **Tiered Skill Registry**: Global Platform Skills + User-Uploaded Custom Skills in isolated workspaces.
- 🔌 **MCP Host**: Full support for Model Context Protocol external tools.
- 📅 **Proactive Automation**: Built-in scheduling (cron, at, every) with isolated Fair-Share execution lanes.
- 🛡️ **Execution Sandboxing**: Skills run in isolated thread pools with strict 30s timeouts.
- 🔐 **Encrypted Vaults**: Per-user secrets (API keys) are encrypted at rest using AES-128 (Fernet).

```bash
$ pip install angel-claw
$ angel-claw serve    # Starts the Agent OS Gateway + Web Dashboard
$ angel-claw chat     # Authenticated CLI mode
```

---

## 🚀 Key Features

| Feature                        | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| 👥 **Multi-User Support**      | Full identity management with Shopyo integration.           |
| 🧠 **Isolated Memory**         | User data stored securely in `~/.angelclaw/users/{user_id}`. |
| ✉️  **Internal Notes**         | Send peer-to-peer messages: "Send a note to alice@dev.com". |
| ⚡ **Multi-Model**             | OpenAI, Anthropic, Ollama & more via `litellm`.             |
| 🔒 **Execution Sandbox**       | Safe execution of custom tools with resource timeouts.       |
| ✅ **Todo Management**         | Native task tracking with priorities and due dates.        |
| 📅 **Calendar Sync**           | Manage events and sync with Google Calendar.                |
| 🌐 **Web Dashboard**           | Modern UI with 🪽 branding and connection indicators.       |
| 📱 **Secure Pairing**          | Link Telegram/WhatsApp using time-limited secure tokens.    |
| 🔑 **Developer APIs**          | Create and manage scoped API keys for external integration. |

---

# 💬 Internal Messaging

Angel Claw supports secure, internal communication between users. The agent handles delivery and notification across all active bridges.

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

# 📖 User Guides

### 🔑 Using the User Vault
Stop putting keys in `.env`. Users can securely add their own `MODEL_KEY` or `BRAVE_API_KEY` through the dashboard. The Agent OS automatically injects these into sandboxed skills on-demand.

### 🎭 Customizing Your Agent's Soul
Define a unique personality by creating a `SOUL.md` in your user directory (`~/.angelclaw/users/{id}/SOUL.md`). The OS prioritizes local souls over system defaults.

### 📦 Custom User Skills
Users can extend their agent by dropping Python files into their personal `skills/` folder. They are loaded dynamically and executed behind the safety sandbox.

---

# 📱 Multi-Channel Bridges

Control your AI from anywhere with secure pairing.

### Telegram & WhatsApp
1. Generate a pairing token on the Web Dashboard.
2. Message your bot: `/pair <your-token>`.
3. The bridge routes messages to your specific **UserRuntime**.

---

# 💬 Developer API

Generate an API key in the Dashboard and use it to build your own integrations:

```bash
curl -X POST http://localhost:5000/chat \
     -H "Authorization: Bearer ac_v1_..." \
     -H "Content-Type: application/json" \
     -d '{"message": "Remind me to call John tomorrow"}'
```

---

# 🧪 Testing & Reliability

Angel Claw is hardened for "Diamond-Tier" reliability:
- **Loop Defense**: 10-turn reasoning limit per request.
- **Recursion Shield**: Detects and breaks agent-to-agent loops.
- **Isolation Verification**: `uv run python tests/test_multi_tenancy.py`

---

# 📜 License

Apache 2.0 License.

---

<p align="center">
  <strong>Built for the next generation of autonomous infrastructure.</strong>
</p>
