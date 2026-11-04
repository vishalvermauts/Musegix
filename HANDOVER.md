# MUSEGIX — AI ENGINEER HANDOVER & SYSTEM COMPENDIUM
**Event:** Meta Global AI Developer Hackathon  
**Repository:** [https://github.com/vishalvermauts/Musegix.git](https://github.com/vishalvermauts/Musegix.git)  
**Primary Branch:** `main` (Latest commit certified: `d7cfc0f`)  
**Target Environment:** Local Windows PC (`c:\AI\Hackathon\Meta`) + Cloud Sandbox (`musegix-builder`)

---

## 1. Executive Summary & Purpose

**Musegix** is an Intelligent AI Gateway and Code Intelligence Engine that sits between developer IDEs (specifically [bolt.diy](file:///c:/AI/Hackathon/Meta/external/bolt.diy)) and frontier Meta foundation models. 

### Core Innovations & Capabilities:
1. **Ysolveth System One ONNX Classifier**:
   - Sub-2ms local CPU inference (`components/Ysolveth/encoder_int8.onnx`).
   - Mathematically classifies incoming prompts into `TRIVIAL`, `MODERATE`, or `HARD`.
   - Routes requests dynamically to the optimal model and provider without manual user switching:
     - `TRIVIAL` → Baseten (`meta-models/muse-spark-open-1026`)
     - `MODERATE` → Meta API (`muse-spark-1.3`)
     - `HARD` → Meta API (`muse-wonder-1.0`)
2. **PolyFabric Tree-sitter AST Context Pruner**:
   - Reduces token consumption by **-32.8%** across multi-file contexts.
   - Preserves the **Target File Invariant at 100%** (the active editing file is never pruned).
   - AST-prunes background helper files, dropping internal function bodies while retaining interface declarations.
3. **Veylqora Evidence-Anchored SQLite WAL Memory Guard**:
   - Computes SHA-256 AST symbol hashes in Write-Ahead Logging (WAL) mode (`data/veylqora_memory.db`).
   - Detects when functions or classes referenced in earlier turns have mutated, preventing stale symbol hallucinations across chat turns.
4. **Resilient AI SDK Gateway Streamer**:
   - Emits an instant Markdown telemetry banner as chunk #1.
   - Standardizes Server-Sent Events (SSE) chunks to maintain full wire-compatibility with `@ai-sdk/openai`.

---

## 2. Infrastructure & Live Service State

### A. Ports & Running Daemons

| Port | Service | Process / Task | Command to Start |
| :--- | :--- | :--- | :--- |
| **8000** | **Musegix Gateway** | Python Uvicorn (`gateway.app:app`) | `python -m uvicorn gateway.app:app --host 0.0.0.0 --port 8000` |
| **5173** | **bolt.diy Web IDE** | Vite + React Router dev server | `cd external/bolt.diy && pnpm run dev` |
| **Sandbox** | **Cloud VM** | Docker Sandbox (`musegix-builder`) | `sbx --cloud exec musegix-builder bash` |

### B. Environment Configuration (`.env`)
The root `.env` must exist and contain the following variables:
```ini
# Meta Model API
META_API_KEY=YOUR_META_API_KEY
META_BASE_URL=https://api.meta.ai/v1

# Baseten Model API
BASETEN_API_KEY=YOUR_BASETEN_API_KEY
BASETEN_BASE_URL=https://inference.baseten.co/v1

# Optional OpenAI Fallback
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_BASE_URL=https://api.openai.com/v1

# Gateway Networking
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8000
```
> [!IMPORTANT]
> Never commit `.env` or raw API keys to Git. The `.gitignore` strictly excludes all `.env` files and `.db` files.

### C. bolt.diy Client Configuration (`external/bolt.diy/.env.local`)
```ini
OPENAI_LIKE_API_BASE_URL=http://localhost:8000/v1
OPENAI_LIKE_API_KEY=musegix-authenticated-key
OPENAI_LIKE_API_MODELS=musecontext-auto:Musegix Auto-Router:128000,muse-spark-1.3:Meta Muse Spark:128000,muse-wonder-1.0:Meta Muse Wonder:128000,muse-spark-open:Meta Muse Spark Open:128000
```

---

## 3. Repository Architecture & Key Files

```
c:\AI\Hackathon\Meta\
├── components/
│   └── Ysolveth/
│       ├── encoder_int8.onnx           # Quantized MiniLM/Bert ONNX model (384-dim hidden state)
│       ├── head_config.json            # Calibrated projection weights, biases & temperature T=0.2842
│       └── tokenizer.json              # Fast HuggingFace Rust tokenizer
├── gateway/
│   ├── app.py                          # FastAPI gateway entry point with load_dotenv()
│   ├── routes.py                       # POST /v1/chat/completions (Ysolveth triage + PolyFabric + Veylqora)
│   ├── streaming.py                    # Multi-provider client manager & SSE chunk generator
│   └── engines/
│       ├── ysolveth_classifier.py      # ONNX forward pass, mean pooling, L2 norm, softmax (<2ms CPU)
│       ├── polyfabric_pruner.py        # Tree-sitter AST pruning with Target File Invariant
│       └── veylqora_guard.py           # SQLite WAL symbol fingerprinting engine
├── mcp_servers/
│   ├── musegix_mcp.py                  # FastMCP MCP server exposing triage, pruner & guard tools
│   └── render_gate.py                  # Playwright headless DOM layout collision & overflow gate
├── benchmarks/
│   ├── benchmark_results.json          # 10-task evaluation matrix raw runtime metrics
│   └── benchmark_results.md            # Verified benchmark table (100% accuracy, -32.8% tokens)
├── scripts/
│   ├── run_benchmarks.py               # Complete 10-task automated benchmark runner
│   ├── run_full_e2e.py                 # Full Playwright E2E browser automation test
│   ├── test_browser_ui.py              # Headless Playwright integration test
│   └── test_local_browser_headed.py    # Headed local browser testing utility
├── tests/                              # Pytest test suite (43 passed in 14.8s)
│   ├── test_gateway.py
│   ├── test_guard.py
│   ├── test_mcp_render.py
│   ├── test_pruner.py
│   ├── test_streaming.py
│   └── test_ysolveth.py
├── external/bolt.diy/                  # Subtree of bolt.diy pre-configured for Musegix
│   ├── app/lib/stores/toolAccess.ts    # Configured to default to 'full-access'
│   └── app/lib/modules/llm/manager.ts  # Configured to default to OpenAILike provider
├── run_live_browser_test.bat           # 1-click Windows batch runner for full E2E test
├── README.md                           # Main documentation & benchmark overview
└── requirements.txt                    # Python dependencies
```

---

## 4. Key Fixes Implemented & Critical Gotchas

### 1. The Vercel AI SDK Object Spread Bug
* **Symptom:** `TypeError: Cannot read properties of undefined (reading 'split')` at `streamLanguageModelCall`.
* **Root Cause:** In `external/bolt.diy/app/lib/.server/llm/agent-stream.ts`, `withAgentStreamDeadlines` used `{ ...normalized }`. Object spread only copies own enumerable properties, dropping prototype getters (`.provider`, `.modelId`, `.specificationVersion`).
* **Fix:** In `agent-stream.ts` (lines 21 and 256), explicitly assign:
  `provider: (model as any).provider ?? 'openai.chat'`,
  `modelId: (model as any).modelId`,
  `specificationVersion: 'v4'`,
  `supportedUrls: []`.

### 2. Auxiliary Non-Streaming Reasoning Token Headroom
* **Symptom:** `AI_APICallError: Invalid JSON response` during `create-summary` / chat title generation.
* **Root Cause:** Meta's `muse-spark-1.3` is an advanced reasoning model that consumes ~300+ reasoning tokens before emitting text. When `bolt.diy` called chat summary with `max_tokens: 100`, the reasoning tokens exhausted the budget, returning `content: null`.
* **Fix:** In `gateway/routes.py`, any auxiliary or non-streaming request with `max_tokens < 512` is promoted to `max_tokens: 1024`, and `choices[0].message.content` is guarded against `null` by extracting reasoning tokens if content is empty.

### 3. Tool Access Mode Default
* **Symptom:** Model paused after creating `package.json` asking for confirmation on every command.
* **Fix:** In `external/bolt.diy/app/lib/stores/toolAccess.ts`, `getInitialMode()` was changed from `'ask-for-all'` to `'full-access'`.

### 4. Windows Desktop Session Isolation (`WinSta0\exebox`)
* **Gotcha:** Commands run via agent tool runners execute on a background desktop (`WinSta0\exebox-*`). A standard `subprocess.Popen("chrome.exe")` from the agent will render to the invisible sandbox desktop.
* **Solution:** To see the browser window visibly on your monitor, run `python scripts\run_full_e2e.py` or double-click `run_live_browser_test.bat` from your user desktop.

---

## 5. How to Run & Verify

### Step 1: Start Background Servers (if not already running)

**Terminal 1 (Musegix Gateway):**
```powershell
cd C:\AI\Hackathon\Meta
python -m uvicorn gateway.app:app --host 0.0.0.0 --port 8000
```
*Health check:* `curl http://127.0.0.1:8000/v1/models` (should return 4 models including `musecontext-auto`).

**Terminal 2 (bolt.diy Web IDE):**
```powershell
cd C:\AI\Hackathon\Meta\external\bolt.diy
pnpm run dev
```
*Health check:* Open `http://localhost:5173` in any browser.

---

### Step 2: Run Unit Tests
```powershell
cd C:\AI\Hackathon\Meta
python -m pytest tests/
```
*Expected output:* `43 passed in ~14s`.

---

### Step 3: Run Full Benchmark Suite (Live Model Verification)
```powershell
cd C:\AI\Hackathon\Meta
python scripts\run_benchmarks.py
```
*Expected output:* Evaluates all 10 tasks across Trivial, Moderate, and Hard tiers against real Meta and Baseten APIs, writing results to `benchmarks/benchmark_results.json`.

---

### Step 4: Run Live E2E Browser Test
```powershell
cd C:\AI\Hackathon\Meta
python scripts\run_full_e2e.py
```
*(Or double-click `run_live_browser_test.bat`)*

**What this script performs:**
1. Spawns Chrome with a dedicated user data profile (`~/.gemini/musegix-test-chrome-profile`).
2. Navigates to `http://localhost:5173`.
3. Verifies `OpenAILike` + `musecontext-auto` are set.
4. Activates **Full Access** mode.
5. Types: *"Create a simple counter button component in React with Tailwind CSS"*.
6. Submits to port 8000.
7. Waits for `⚡ Ysolveth Triage` block (`<2ms` ONNX CPU).
8. Waits for Meta model code generation and project scaffolding.
9. Automatically clicks the **Preview** tab in the Workbench.
10. Keeps the browser open indefinitely until you close it.

---

## 6. Submission & Hackathon Assets Checklist
- [x] **Git Repository:** `https://github.com/vishalvermauts/Musegix.git` (clean working tree, pushed).
- [x] **CI Certification:** Remote GitHub Actions green (`41775193591`).
- [x] **Benchmark Matrix:** 10 live tasks documented in `README.md` and `benchmarks/`.
- [x] **Screenshots & Visual Evidence:** Captured and saved in artifact directory.
- [x] **Demo Video Script:** Located in `plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md` (3-minute presentation flow).
