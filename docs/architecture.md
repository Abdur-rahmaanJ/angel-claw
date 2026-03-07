# Architecture: The Agent OS

Angel Claw is built as a high-density, multi-tenant **Agent Operating System**. This document outlines the core components that enable secure, isolated, and scalable agent execution.

## Core Philosophy: Shared-Nothing

Traditional agent frameworks often share state (history, memory, configuration) across a single global instance. Angel Claw adopts a **Shared-Nothing** architecture. Every user is treated as a first-class tenant with a completely isolated environment.

---

## 1. UserRuntime

The `UserRuntime` is the heartbeat of the system. Every active user has an instance of this class which manages their specific context:

- **Isolated History**: A private database connection. Supports **SQLite** (per-user file) or **PostgreSQL** (centralized table with Row-Level Security logic).
- **Isolated Memory**: Dedicated vector database paths for `angel-recall`.
- **Personalized Soul**: Hierarchical loading of `SOUL.md` (User-specific > Global default).
- **Private Skills**: Access to both platform-wide tools and the user's custom `skills/` directory.
- **Fair-Share Scheduler**: A dedicated lane in the task queue to prevent cross-tenant resource starvation.

## 2. RuntimeManager

To support thousands of users on a single server, Angel Claw uses a dynamic **LRU (Least Recently Used) Cache** for runtimes.

- **On-Demand Activation**: Runtimes are only instantiated when a message arrives (via Web, Telegram, or API).
- **Automatic Eviction**: If a runtime is idle for more than 30 minutes, it is cleared from system memory.
- **State Persistence**: Because all critical data (History, Vault, Memory) is persisted to disk, runtimes are effectively stateless between activations.

## 3. Tiered Skill Registry

The registry manages how tools are discovered and executed:

1.  **Platform Skills**: Read-only, built-in capabilities (Todo, Calendar, Email).
2.  **Custom Skills**: User-uploaded Python scripts in their workspace.
3.  **MCP Tools**: External tools connected via the Model Context Protocol.

## 4. Fair-Share Scheduler & Lane Queue

Angel Claw uses a "Lane Queue" architecture to manage task execution. Each user has their own "Lane" to ensure fairness and prevent resource starvation.

- **In-Memory Queue**: The default implementation for standalone or development deployments.
- **Redis-Backed Queue (Optional)**: Enables horizontal scaling by allowing multiple Gateway or Worker nodes to share a unified task backlog.
- **LLM Response Caching (Optional)**: Utilizes Redis to cache common LLM completions, reducing latency and API costs for repeated queries.

## 5. The Request Flow

When a message enters the system (e.g., from Telegram):

1.  **Gateway**: Validates the identity and routes the request.
2.  **RuntimeManager**: Fetches the existing `UserRuntime` or creates a new one.
3.  **Engine**: Processes the message using the tenant's specific Soul and Memory.
4.  **Sandbox**: Any tool calls are executed within the tenant's sandboxed environment.
5.  **Persistence**: History and Memory are updated in the tenant's private storage.
