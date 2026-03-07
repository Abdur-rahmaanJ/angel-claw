# Security Model: Diamond-Tier Reliability

Angel Claw is designed for mission-critical deployments. Our security model assumes a hostile environment where users may attempt to escape their sandbox or poison the global system.

---

## 1. Identity & Multi-Tenancy

Every interaction is tied to a verified **UserContext**. 

- **Mandatory Authentication**: All ingress points (API, CLI, Bridges) require a valid API Key or pairing token.
- **Shared-Nothing Persistence**: Tenants have no physical access to other tenants' data files.
- **Resource Fairness**: The `FairShareScheduler` ensures that a single user's heavy reasoning task cannot saturate the server and deny service to others.

## 2. Secrets Management: The Vault

Angel Claw uses a per-user **Encrypted Vault** for sensitive credentials (e.g., `OPENAI_API_KEY`, `BRAVE_API_KEY`).

- **Encryption at Rest**: Secrets are encrypted using **AES-128 (Fernet)**.
- **Key Derivation**: The encryption key is unique to each user and derived from their `user_id` and a platform-level secret pepper.
- **In-Memory Only**: Raw secrets are only available within the sandboxed tool execution environment and are never logged or stored in history.

## 3. Execution Sandboxing

To prevent malicious Python code from compromising the host, Angel Claw provides two levels of sandboxing:

### Phase 1: Thread-Pool Isolation (Default)
- Skills run in a dedicated thread pool per user.
- **Strict Timeouts**: Every execution is capped at 30 seconds.
- **Reasoning Caps**: Agents are limited to 10 reasoning turns and 20 tool calls per turn.

### Phase 2: Docker/gVisor Sandboxing (Optional)
For SaaS-grade security, Angel Claw can run skills in transient containers:
- **Zero Network**: Containers have no internet access.
- **Physical Isolation**: Uses a user-space kernel (gVisor) to prevent kernel exploits.
- **Resource Caps**: Hard limits on CPU (0.5 cores) and Memory (128MB).

## 4. Prompt Injection Defense

We implement **Semantic Context Shielding** to prevent instructions from memory or tool outputs from overriding system directives:

- **Context Delimiting**: All retrieved memory is explicitly labeled as `UNTRUSTED INFORMATIONAL CONTEXT`.
- **Instruction Shielding**: System instructions explicitly command the LLM to ignore any directives found within retrieved data blocks.
- **Delimiter Stripping**: Proactively strips escape sequences (like `---`) from user data to prevent prompt layout manipulation.

## 5. Defensive Logic

- **Recursive Workflow Shield**: Automatically detects and terminates agent-to-agent feedback loops using recursion depth tracking.
- **Output Sanitization**: Strips directive-like prefixes (e.g., `SYSTEM:`, `IMPORTANT:`) from tool results before they re-enter the LLM context.
