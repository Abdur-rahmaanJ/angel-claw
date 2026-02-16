OpenClaw Architecture Document
Introduction
OpenClaw (formerly Clawdbot / Moltbot) is a self‑hosted, open‑source personal AI agent framework that connects large language models (LLMs) to messaging platforms and local tools. It enables autonomous, multi‑step workflows on the user’s own hardware, emphasizing reliability, security, and extensibility.

Originally implemented in TypeScript, the architecture has been refined to support multiple languages and runtimes. PicoClaw is an ultra‑lightweight evolution that achieves a sub‑10MB memory footprint and sub‑1s boot times by stripping heavy dependencies and embracing a minimalist core philosophy. This document describes the combined architecture, incorporating PicoClaw’s efficiency principles while remaining implementation‑agnostic. It also provides concrete guidance for a Python‑based implementation, leveraging Python’s rich AI ecosystem.

High‑Level Architecture
OpenClaw follows a hub‑and‑spoke model with a centralized Gateway as the control plane. The Gateway routes messages between multiple channels (messaging platforms, UI, CLI) and one or more Agent Runtimes, which execute the LLM loop and invoke tools.

text
┌─────────────────────────────────────────────────────────────┐
│                      INTERFACE LAYER                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Web UI   │  │   CLI    │  │ Telegram │  │ Discord  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                           │                                  │
│                    (WebSockets/HTTP)                         │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    GATEWAY DAEMON                            │
│  • Message routing                    • Session management  │
│  • Authentication                     • Request coordination│
│  • Lane classification                 • Health / observability
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│                    AGENT RUNTIME                             │
│  • Reasoning loop                     • Memory management   │
│  • Tool invocation                    • Workflow orchestration
│  ┌──────────────────────────────────────────────────────┐   │
│  │                SKILLS / PLUGIN SYSTEM                 │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │   │
│  │  │ Model    │  │ AnChain  │  │ Community Plugins  │  │   │
│  │  │ Providers│  │   MCP    │  │                    │  │   │
│  │  └──────────┘  └──────────┘  └────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
Core Components
1. Gateway Server
The Gateway is the central control plane. It accepts connections from channels via WebSocket/HTTP, manages sessions, enforces authentication, and dispatches messages to the appropriate agent lane. It also coordinates request handling, load balancing, and observability.

Python Implementation: Built with FastAPI and uvicorn for high‑performance asynchronous I/O. WebSocket endpoints are provided for real‑time control plane communication.

2. Agent Runtime
The Agent Runtime is a long‑running process that executes the core agentic loop. It assembles context (from memory and conversation history), invokes LLMs, executes tool calls, and streams responses back to the Gateway. The runtime is designed to be stateless, with all state held in external memory systems.

Python Implementation: Orchestration can be built using LangChain, Semantic Kernel, or a custom asynchronous ReAct loop. Model integration uses SDKs like openai or anthropic, with support for local models via Ollama.

3. Channel Adapters
Lightweight adapters normalize platform‑specific events (Telegram, WhatsApp, Discord, etc.) into a common internal format (e.g., a BaseMessage Pydantic model). They plug into the Gateway’s dispatching layer and handle bidirectional communication.

Python Implementation:

Telegram: python-telegram-bot (async)

WhatsApp: mowapi or similar bridges

Discord: discord.py

Web UI/CLI: FastAPI routes and WebSocket endpoints

4. Lanes
Lanes are independent processing queues that isolate workloads and provide concurrency control. Each lane has its own queue, agent instances, memory pools, and resource limits. This ensures predictable performance: interactive requests are never blocked by background jobs.

Lane Configuration (example in openclaw.json):

json
{
  "lanes": {
    "fast": {
      "priority": 1,
      "max_concurrency": 5,
      "agent_config": {
        "model": "gpt-4o-mini",
        "memory": "redis",
        "skills": ["web_search", "calculator"]
      },
      "timeout_ms": 3000
    },
    "batch": {
      "priority": 2,
      "max_concurrency": 2,
      "agent_config": {
        "model": "claude-3-opus",
        "memory": "milvus",
        "skills": ["data_analysis", "code_interpreter"]
      },
      "timeout_ms": 30000
    }
  }
}
Lane Selection is based on explicit tags, priority scoring, capability matching, or load balancing.

5. Memory Management (Powered by Angel Recall) https://github.com/Abdur-rahmaanJ/angel-recall
OpenClaw now implements a Memory Operating System (MemOS) using the angel-recall library. This replaces the previous three-tier architecture with a more robust, policy-driven memory system designed for agentic workloads.

Core Architecture: Lane-Based Command Queue
MemOS uses a lane-based command queue for all memory operations, a design that perfectly mirrors OpenClaw's own lane-based concurrency model. This ensures:

Predictable Execution: Memory tasks for a specific session (user) run sequentially, eliminating race conditions without complex async locks.

Clean Logs: No interleaved operations, making debugging and auditing straightforward.

Simplified Development: Developers and agents interact with a simple, synchronous interface while the system handles the complexity.

The MemVault: Storage Engine
The MemVault combines two powerful backends:

ChromaDB: Provides vector-based semantic search for retrieving memories by meaning, not just keywords.

NetworkX: Maintains a relationship graph between memory cubes, enabling the agent to understand connections and context (e.g., "this preference is related to that project").

Intelligent Memory Processing
Interaction with memory is handled by the MemReader, which uses an LLM to parse the intent of an agent's or user's statement. The same process() method is used for storing, retrieving, or deleting memories, making the interface incredibly simple for agents.

Memory Governance & Policies
Angel Recall introduces a comprehensive policy framework that was absent in the original OpenClaw memory design:

Access Governance: Every memory cube has a scope:

PRIVATE: Only accessible by the owner (default).

SHARED: Visible to a defined group of users/sessions.

PUBLIC: Accessible system-wide.
The MemGovernance component enforces these rules on every read/write operation, verifying ownership and permissions. This enables secure multi-user scenarios on a single instance.

Lifecycle Management (MemScheduler): Memories automatically transition through states (GENERATED → ACTIVATED → ARCHIVED). The MemScheduler dynamically selects the most relevant memories based on the current task's context and moves cold memories to long-term archival, keeping the active retrieval context clean and performant.

Time-to-Live (TTL): Any memory can be created with an expiration. Once the TTL is reached, the memory is automatically purged, which is ideal for temporary context or session-specific information.

Sensitivity Masking: Built-in support for PII redaction and sensitive tag handling prevents private data from leaking into LLM prompts, a critical security enhancement.

Integration into the Agent Runtime
Agents interact with MemOS in two primary ways:

Implicit Memory via MemOS.process(): The simplest method. The agent's natural language output or a user's message is passed to memos.process(). The MemReader automatically determines whether to store a new memory, retrieve relevant ones, or perform other actions.

python
from angel_recall import MemOS

# Initialize the Memory OS for a specific user/session lane
memos = MemOS(persist_directory=f"./vaults/{session_id}")

# Agent decides to remember something
memos.process("User emphasized they want verbose, detailed explanations.")

# Later, agent retrieves context
context_result = memos.process("What is the user's preferred explanation style?")
print(context_result["response"]) # Outputs the relevant memory
Explicit Tool Control (get_memory_tools): For more complex agents (e.g., those built with LangGraph), explicit tools can be provided. This gives the agent fine-grained control to decide when and how to manage its memory.

python
from angel_recall import MemOS, get_memory_tools
from langgraph.prebuilt import ToolNode

memos = MemOS(persist_directory=f"./vaults/{session_id}")

# Get explicit tools for the agent to call
memory_tools = get_memory_tools(memos, user="current_user_id")
tool_node = ToolNode(memory_tools)

# Agent can now use tools like 'store_memory', 'search_memories', 
# 'update_memory_access' to manage its own vault.
Developer Experience & Observability
Angel Recall enhances the development and debugging process significantly:

Built-in Dashboard: The angel-recall memos command launches a Flask dashboard. Developers can visually inspect the MemVault, view all memory cubes with their types and scopes, configure API keys, switch LLM models on the fly, and chat with the memory-augmented agent to see real-time memory operations.

Simple Configuration: Initialization is clean and flexible.

python
memos = MemOS(
    persist_directory="./user_vault",   # Where memories are stored
    model="ollama/llama3"               # Any LiteLLM-compatible model
)
By adopting Angel Recall, OpenClaw's memory subsystem is no longer just a storage layer. It has become an intelligent, governed, and observable co-processor for the agent, ensuring that interactions are context-aware, secure, and deterministic, all while adhering to the project's lane-based concurrency principles.

6. Tools and Skills System
The agent can invoke a rich set of tools: system commands, browser automation (via Playwright), file operations, scheduled jobs, etc. Tools are sandboxed for security.

Skills are modular plugins (Markdown‑defined) that encapsulate domain‑specific behaviors. They can be installed from the public registry ClawHub and declare dependencies, environment variables, and required binaries.

Python Implementation: Tools are Python functions with type hints. Sandboxing is achieved via Docker (Python SDK) or restricted subprocess environments. A Sandbox class spawns ephemeral containers for arbitrary code execution.

7. Security & Observability
Sandboxing: By default, tools run on bare metal; Docker mode provides stronger isolation. Allowlists restrict commands/domains.

Exec Approvals: Dangerous operations can require human approval (cryptographic resume tokens via Lobster workflow engine).

Audit System: Three‑level security audit (read‑only scan, live probe, auto‑fix) covering config, filesystem permissions, channel policies, and plugin trust.

Observability: JSONL transcripts of every tool call and LLM decision; health endpoints; event streams; custom logging hooks with credential masking.

Python Implementation Guide
This section provides concrete guidance for building OpenClaw in Python, incorporating PicoClaw’s efficiency principles.

Module Map
Component	Python Module / Library	Purpose
Gateway Entry	app/main.py	FastAPI app wiring
Channel Adapters	app/channels/	python-telegram-bot, discord.py
Agent Runner	app/agent/runner.py	Core async loop
Routing Logic	app/routing/	Session resolution, lane dispatch
Memory System	app/memory/	ChromaDB/FAISS, SQLite
Browser Automation	playwright	Python bindings
Tool Sandbox	app/sandbox/	Docker or restricted subprocess
PicoClaw‑Inspired Optimizations
Dependency Minimization

Use FastAPI instead of Django/Flask.

Lazy‑load heavy libraries (playwright, pandas) to keep initial memory low.

Leverage Pydantic v2 for fast validation.

Fast Startup & Execution

Compile with Nuitka for AOT compilation and smaller distribution.

Enable SQLite WAL mode for faster concurrent access.

Use asyncio for non‑blocking I/O throughout.

Self‑Optimization (The PicoClaw Way)

Implement a “self‑improvement” mode where the agent analyzes its own codebase (app/) and suggests optimizations or refactorings.

Dynamically load skills as lightweight Python modules or JSON‑defined tools to keep core runtime lean.

Implementation Roadmap
Phase 1: Lightweight Gateway
Set up FastAPI server with a WebSocket endpoint.

Implement pydantic‑settings for configuration.

Phase 2: Pythonic Channel Adapters
Build Telegram adapter using python-telegram-bot.

Define BaseMessage Pydantic model for normalization.

Implement Discord and CLI adapters.

Phase 3: The ReAct Loop
Create async loop assembling context from SQLite and vector DB.

Integrate LLM with tool definitions (Python functions with type hints).

Execute tool calls and feed results back to LLM.

Phase 4: Sandboxed Tool Execution
Develop Sandbox class using Docker SDK.

Add “human‑in‑the‑loop” decorator for sensitive functions.

Deployment Models
OpenClaw supports multiple deployment architectures:

Mode	Description
Standalone Mac/mini	Gateway runs locally; access via SSH tunnels or Tailscale.
Isolated VPS	DigitalOcean 1‑Click deploy, hardened, loopback + SSH tunnel.
Cloudflare Moltworker	Gateway inside Cloudflare Workers sandbox, uses R2 for persistence, AI Gateway for routing.
Docker Model Runner	LLMs run via Docker Desktop’s Model Runner (GPU support).
Security & Observability
Built‑in Security Audit
bash
# Level 1: read‑only scan of config + filesystem permissions
openclaw security audit

# Level 2: live WebSocket probe of running gateway
openclaw security audit --deep

# Level 3: apply safe auto‑fixes (chmod, policy changes) then audit
openclaw security audit --fix
The audit covers 50+ checks across 12 categories (channel policies, model hygiene, plugin trust, etc.).

Threat Model Considerations
ClawHub marketplace risks – malicious skills.

Prompt injection – 27 documented examples.

AI self‑misconfiguration – agent modifying its own settings.

Model poisoning – sleeper agent backdoors.

Observability Features
JSONL transcripts for replay and compliance.

Health endpoints and event streams.

Hook system for custom logging, boot scripts, and session persistence.

Credential masking in logs via custom logging filters.

Advanced Topics
Canvas Host & Node Architecture
The Gateway runs a Canvas Host on port 18793, serving:

WebChat interface

iOS/Android thin clients

Nodes connect via WebSocket (LAN/Tailnet/SSH tunnel) and render UI provided by the Canvas Host. The Gateway remains the single source of truth, with no business logic on clients.

Lobster Workflow Engine
Lobster provides cryptographic approval gates for automation pipelines. Certain actions (e.g., posting to social media) require human approval via a resume token—the agent cannot proceed without it.

json
{
  "lobster": {
    "workflows": {
      "social-post": {
        "gates": [
          {
            "type": "human-approval",
            "channel": "discord",
            "timeout": 3600
          }
        ]
      }
    }
  }
}
Hardware Abstraction & Optimization
Platform‑specific adapters enable:

Process‑level isolation via namespaces.

Priority‑based thread pool scheduling.

Memory pooling with object reuse (<200MB footprint).

SIMD/GPU/NPU acceleration where available.

Configuration Deep Dive
Key configuration options (excerpts from openclaw.json):

Category	Example	Description
Elevated Access	"tools.elevated.allowFrom.discord": ["USER_ID"]	Restrict dangerous commands to specific users.
Sandbox Mode	"agents.defaults.sandbox.mode": "docker"	Enable Docker isolation.
Identity Linking	"session.identityLinks.alex": ["whatsapp:+...", "discord:..."]	Recognize same user across platforms.
Hybrid Memory Search	"agents.defaults.memorySearch.query.hybrid.vectorWeight": 0.7	Blend vector and keyword search.
Hooks	"hooks.internal.entries.command-logger.enabled": true	Enable custom event handlers.
Known Limitations & Future Work
Based on current issue tracker:

CLI inconsistency in model ID mappings.

Skill dependency resolution gaps.

Planned improvements: multi‑agent collaboration, reinforcement learning fine‑tuning, expanded edge device support.

Conclusion
OpenClaw’s architecture balances modularity, security, and performance. Its lane‑based concurrency, plugin system, multi‑tier memory, and flexible deployment options make it suitable for a wide range of personal AI agent use cases—from a lightweight local assistant to a serverless edge bot. The Python implementation guide and PicoClaw optimizations provide a clear path for developers to build efficient, private, and extensible agents.