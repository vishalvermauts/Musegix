# Musegix Security, Safety & Governance Architecture

> **Single Source of Truth for System Security & Data Integrity**

---

## 1. Threat Modeling & Attack Surfaces

Because Musegix operates as an intermediary proxy between an untrusted browser IDE (`bolt.diy`), local agent engines, and upstream LLM APIs, it enforces strict boundaries across four core threat vectors:

```
[Threat Vector 1: Prompt Injection & Code Tampering]
       |
       v
[bolt.diy UI] ----(Proxy SSE)----> [Musegix Gateway] ----(MCP stdio)----> [Host / Sandbox Filesystem]
                                           |                                      ^
                                           v                                      |
                                  [Threat Vector 2: Credential Leak]    [Threat Vector 3: Sandbox Escape]
```

### Threat Vector 1: Prompt Injection & Malicious `<boltAction>` Injection
- **Risk:** An attacker submits a prompt that attempts to break out of `<boltArtifact>` tags or trick the model into overwriting sensitive system files (e.g. `/etc/passwd` or `.env`).
- **Defense Mechanism:**
  - Strict path sanitization on all `filePath` attributes extracted from `<boltAction>`.
  - Disallow absolute paths (`/`) or directory traversal (`../`). All file targets are strictly jailed to the active workspace root.

### Threat Vector 2: API Credential & Secret Leakage
- **Risk:** Model outputs or conversation history logging dumps `BASETEN_API_KEY` or `META_API_KEY` into `bolt.diy` WebContainer files or chat logs.
- **Defense Mechanism:**
  - Automated redaction in SSE streaming buffer for known key patterns (e.g. `meta_...`, `sec_...`, `bearer ...`).
  - `.gitignore` explicitly prohibits `.env*`, `.ai/` secret storage, and memory database dumps.

### Threat Vector 3: Sandbox Isolation & Resource Exhaustion
- **Risk:** Node / WebContainer processes or AST indexing operations consume excessive memory or spawn runaway child processes.
- **Defense Mechanism:**
  - All heavy builds and benchmarking are strictly confined to the Docker Cloud Sandbox (`musegix-builder`) with CPU limits and memory clamping.
  - Veylqora and PolyFabric operations run with strict execution timeouts (<200ms per turn).

### Threat Vector 4: Memory Poisoning & Stale Memory Exploitation
- **Risk:** Stale memory references in the agent store cause malicious or invalid dependencies to persist across chat sessions.
- **Defense Mechanism:**
  - Mandatory SHA-256 fingerprint validation of all function and symbol bodies before accepting cached memory state.
  - Automatic memory transition to `suspected_stale` upon hash discrepancy.

---

## 2. Security Invariants Checklist

- [ ] Invariant 1: **Zero Plaintext Secrets:** No credentials written to disk, git commits, or telemetry banners.
- [ ] Invariant 2: **Sandboxed File Operations:** No file write operations outside WebContainer virtual file system.
- [ ] Invariant 3: **Path Traversal Guard:** Regex reject any `<boltAction filePath="..*">` occurrences.
- [ ] Invariant 4: **Fail-Closed Routing:** If ONNX classifier or upstream API fails, return clean HTTP error; never crash silent or leak stack traces.
