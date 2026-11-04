# Phase 2: Full UI Integration & Live Test Run with `bolt.diy`

> **Status:** Pending Phase 1 Completion  
> **Objective:** Clone, build, configure, and run `bolt.diy` in the cloud environment; wire its OpenAI-compatible provider to the Musegix Gateway; verify bidirectional streaming of `<boltArtifact>` and `<boltAction>` tags; and test end-to-end app generation inside WebContainer.

---

## 1. `bolt.diy` Architecture & Protocol Constraints

`bolt.diy` communicates with AI providers through a strict conversational contract:
1. **Model Discovery:** Reads `GET /v1/models` and selects `musecontext-auto`.
2. **Context Packaging:** Injects system instructions enforcing `<boltArtifact>` format, followed by all files in the active workspace represented inside `<boltAction type="file" filePath="...">` tags.
3. **SSE Chunk Parsing:** Expects OpenAI streaming format:
   ```json
   data: {"id":"chatcmpl-...","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"..."},"finish_reason":null}]}
   ```
   *(Crucial invariant: `role` must not have leading whitespace).*
4. **Hot-Reloading:** When `<boltAction type="file" filePath="src/App.tsx">` content finishes streaming, `bolt.diy` writes the file to its internal WebContainer virtual file system and triggers Vite hot module replacement (HMR).

---

## 2. Cloud Sandbox Port Forwarding & Setup

Run `bolt.diy` inside the cloud sandbox with exposed ports:
- **Port 5173:** `bolt.diy` Web UI & Vite dev server.
- **Port 8000:** Musegix Gateway proxy.

### Setup Commands inside Sandbox
```bash
cd /workspace/Musegix
git clone --depth 1 https://github.com/stackblitz-labs/bolt.diy.git external/bolt.diy
cd external/bolt.diy
pnpm install

# Write bolt.diy local configuration to point to Musegix Gateway
cat << 'EOF' > .env.local
OPENAI_LIKE_API_BASE_URL=http://localhost:8000/v1
OPENAI_LIKE_API_KEY=musegix-local-key
OPENAI_LIKE_API_MODELS=musecontext-auto:Musegix System (Ysolveth + PolyFabric + Veylqora):128000
VITE_LOG_LEVEL=debug
EOF
```

---

## 3. Telemetry Header Injection Specification

The gateway must inject an informative Markdown Telemetry Banner as the **very first SSE chunk** so the user and hackathon judges immediately see model selection and routing status in `bolt.diy`'s left chat pane:

```markdown
> ⚡ **Ysolveth Model Triage**: `MODERATE` → `muse-spark-1.3` (3.4ms ONNX CPU)  
> 🔍 **PolyFabric Context**: `840` tokens selected from `10,290` raw (91.8% pruned)  
> 🧠 **Veylqora AST Guard**: `ACTIVE` (0 stale memories detected)  
```

### Handling the SSE Stream in `gateway/streaming.py`
```python
import json
import time
from typing import AsyncGenerator

async def stream_chat_completion(payload: dict) -> AsyncGenerator[str, None]:
    t0 = time.perf_counter()
    messages = payload.get("messages", [])
    
    # Run triage, AST check, and context pruning (Phase 3 modules)
    triage_info = {"model": "muse-spark-1.3", "tier": "MODERATE", "ms": 3.4}
    prune_info = {"selected_tok": 840, "raw_tok": 10290, "pct": 91.8}
    memory_info = {"status": "ACTIVE"}
    
    # 1. First SSE chunk with Telemetry
    banner = (
        f"> ⚡ **Ysolveth Model Triage**: `{triage_info['tier']}` → `{triage_info['model']}` ({triage_info['ms']}ms ONNX)\n"
        f"> 🔍 **PolyFabric Context**: `{prune_info['selected_tok']}` tokens vs `{prune_info['raw_tok']}` raw ({prune_info['pct']}% pruned)\n"
        f"> 🧠 **Veylqora AST Guard**: `{memory_info['status']}`\n\n"
    )
    
    first_chunk = {
        "id": f"chatcmpl-{int(time.time()*1000)}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": triage_info["model"],
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": banner},
                "finish_reason": None
            }
        ]
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"
    
    # 2. Forward upstream LLM stream (preserving <boltArtifact> tags)
    # Upstream code generation stream here...
    
    # 3. Stream closing chunk
    yield "data: [DONE]\n\n"
```

---

## 4. Phase 2 Certification Gate Checklist

- [ ] **Gate 2.1:** `bolt.diy` installs dependencies without errors via `pnpm install` in the cloud sandbox.
- [ ] **Gate 2.2:** `bolt.diy` starts up on port 5173 and successfully queries `http://localhost:8000/v1/models`.
- [ ] **Gate 2.3:** A simple prompt (e.g. *"Create a modern Tailwind counter component"*) sent from `bolt.diy` chat successfully passes through the Gateway.
- [ ] **Gate 2.4:** Telemetry banner renders cleanly at the top of the chat bubble in `bolt.diy`.
- [ ] **Gate 2.5:** `<boltArtifact>` and `<boltAction>` tags correctly trigger file creation and live hot-reloading in the right-hand WebContainer preview pane.
- [ ] **Gate 2.6:** Zero WebSocket or SSE drop errors in browser console during full file streaming.
