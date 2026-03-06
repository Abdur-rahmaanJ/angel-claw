<h1 align="center">🪽 Angel Claw</h1>

<p align="center">
  <strong>The Multi-Tenant Agent Operating System with isolated runtimes, tiered skills, and encrypted vaults.</strong>
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

**Angel Claw** is a high-density, multi-tenant AI agent platform. Unlike traditional frameworks, it operates as an **Agent Operating System**, where every user runs within a fully isolated **UserRuntime**.

- 🛡️ **Total Isolation**: Each user has their own encrypted vault, private SQLite history, and dedicated vector memory.
- 🏗️ **UserRuntimes**: On-demand agent instances with LRU-based resource management.
- 🛠️ **Tiered Skills**: Platform-wide "Base Skills" combined with user-uploaded "Custom Skills" in isolated workspaces.
- 🔒 **Execution Sandboxing**: User-defined skills run in protected environments with strict resource timeouts.
- 🧠 **Personalized Souls**: Support for per-user `SOUL.md` to define unique agent personalities and goals.
- 📱 **Omni-Channel**: Seamless experience across Web, CLI, Telegram, and WhatsApp.

```bash
$ pip install angel-claw
$ angel-claw serve    # Starts the Agent OS Gateway + Web Dashboard
$ angel-claw chat     # Interactive CLI mode
```

---

## 🏗️ Core Architecture: Multi-Tenant Isolation

Angel Claw implements a "Security-First" architecture for multi-user environments:

| Layer | Isolation Strategy |
| :--- | :--- |
| **Runtime** | **UserRuntime** instances with LRU (Least Recently Used) eviction. |
| **Secrets** | **Encrypted Vaults** (Fernet) per user for API keys and credentials. |
| **Skills** | **Tiered Registry**: Global skills + User-specific skills in `~/users/{id}/skills/`. |
| **History** | **Private SQLite**: Dedicated `history.db` per user for persistent chat logs. |
| **Memory** | **Isolated Vector DB**: Unique memory namespaces per user/session. |
| **Execution** | **Sandboxed**: Thread-pool isolation with 30s timeouts for custom code. |
| **Scheduling** | **Fair-Share**: Per-user task lanes to prevent resource starvation. |

---

## 🏁 Quick Start

### 📦 Installation

```bash
pip install angel-claw
```

### ⚙️ Setup

Initialize your environment and configure global LLM settings:

```bash
angel-claw chat
```

### 🌐 Run the Gateway

Start the full multi-tenant Agent OS:

```bash
angel-claw serve
```
Access at `http://localhost:5000`. Default admin: `admin@admin.com` / `admin`.

---

## 🛠️ Advanced Features

### 🔑 User Vault (BYO Keys)
Users can provide their own API keys (OpenAI, Anthropic, Brave) via their encrypted vault. The engine dynamically injects these into skills, allowing for "Bring Your Own Key" (BYOK) deployments.

### 🎭 Custom Souls
Define unique personalities by placing a `SOUL.md` in the user's root directory (`~/.angelclaw/users/{user_id}/SOUL.md`). The Agent OS will prioritize this over the global system prompt.

### 📦 Custom User Skills
Users can extend their agent by dropping Python files into their personal `skills/` folder. These are automatically loaded into their `UserRuntime` and executed in a sandboxed environment.

---

## 📱 Multi-Channel Bridges

Angel Claw supports secure pairing across different messaging platforms.

### Telegram & WhatsApp
1. Generate a pairing token on the Web Dashboard.
2. Message your bot: `/pair <your-token>`.
3. The bridge routes messages to the correct **UserRuntime** based on the paired identity.

---

# 🧪 Testing & Verification

Angel Claw includes a comprehensive suite for verifying multi-tenant integrity:

```bash
# Run multi-tenant isolation and LRU tests
uv run python tests/test_multi_tenancy.py

# Run standard suite
pytest tests/
```

---

# 📜 License

Apache 2.0 License.

---

## 🪽 Angel Claw

**The high-density, secure Agent Operating System.**
