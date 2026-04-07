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

<img width="1869" height="922" alt="image" src="https://github.com/user-attachments/assets/571d3650-4153-4a8f-b61f-52e4e75dfa6a" />

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
$ angel-claw setup     # Initialize database and create admin account
$ angel-claw serve     # Starts the Agent OS Gateway + Web Dashboard
$ angel-claw chat      # Authenticated CLI mode
```

---

## 🚀 Quick Setup

To get started with a fresh installation:

1. **Initialize the Environment**:
   ```bash
   angel-claw setup
   ```
   This will create your database at `~/.angelclaw/angelclaw.db`, run initial migrations, and prompt you to create your primary administrator account.

2. **Start the Services**:
   ```bash
   angel-claw serve
   ```
   The web dashboard will be available at `http://127.0.0.1:5000`.

3. **Configure LLMs**:
   Login to the dashboard with your admin credentials and navigate to the **Settings** or **Vault** to add your `MODEL_KEY` (OpenAI, Anthropic, etc.).

---

## 🛠️ CLI Reference

Angel Claw provides a powerful command-line interface for managing the OS, users, and bridges.

### Core Commands
*   `angel-claw setup`: Interactive wizard to initialize the database and create the primary admin account.
*   `angel-claw serve`: Starts the Flask Web Gateway and the background Bridge Worker in a single process.
*   `angel-claw chat`: Launches an authenticated interactive chat session in your terminal.
*   `angel-claw bridges`: Starts only the background bridge workers (Telegram, WhatsApp, Cron). Recommended for production.
*   `angel-claw tutorial`: Runs the interactive "Guided Tour" of Angel Claw's features.

### User Management
*   `angel-claw list-users`: Displays all registered users, their confirmation status, and admin privileges.
*   `angel-claw create-admin <email> <password>`: Directly creates a new administrator account.
*   `angel-claw update-password <email> <new_password>`: Updates the password for an existing user.
*   `angel-claw promote-user <email>`: Grants administrative privileges to an existing user.
*   `angel-claw confirm-user <email>`: Manually marks a user's email as confirmed.

### Utilities & Diagnostics
*   `angel-claw mcp list`: Lists all tools discovered from connected MCP servers.
*   `angel-claw mcp test`: Runs a diagnostic suite on your LLM and MCP connections.
*   `angel-claw login-whatsapp`: Generates a QR code for linking your WhatsApp account.
*   `angel-claw locate-static`: Prints the absolute path to the web static files (useful for Nginx configuration).

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
2. For WhatsApp: Run `angel-claw login-whatsapp` and scan the QR code.
3. Message your bot: `/pair <your-token>`.
4. The bridge routes messages to your specific **UserRuntime**.

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

## 🛠️ Deployment

Angel Claw is designed for high-density, production-grade deployments. For a professional setup, we recommend separating the **Web Gateway** and the **Bridge Worker**.

### 1. Data Architecture
In production, all persistent user data is isolated from the application code:
- **Database**: `~/.angelclaw/angelclaw.db`
- **User Vaults**: `~/.angelclaw/vaults/`
- **Bridge Data**: `~/.angelclaw/bridges/`

### 2. Systemd Service Setup
Create two services to ensure the Web UI and background bridges run independently and reliably.

**Web Gateway (`/etc/systemd/system/angel-claw-web.service`):**
```ini
[Service]
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "angel_claw.app.app:create_app('production')"
Environment="USER_DATA_ROOT=/home/user/.angelclaw"
Restart=always
```

**Bridge Worker (`/etc/systemd/system/angel-claw-bridge.service`):**
```ini
[Service]
ExecStart=/path/to/venv/bin/angel-claw bridges
Environment="USER_DATA_ROOT=/home/user/.angelclaw"
Restart=always
```

### 3. Production Hardening
For public-facing instances, always:
- **Use Nginx** as a reverse proxy with SSL (Certbot/Let's Encrypt).
- **Enable Docker Sandboxing**: Set `DOCKER_SANDBOXING_ENABLED=True` in your `.env` to execute custom skills in gVisor-hardened containers.
- **Dedicated User**: Run services under a low-privilege `angelclaw` user.

---

## 🧪 Testing & Reliability


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
