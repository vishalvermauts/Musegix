# Musegix Project Architecture & Single Source of Truth (SSOT)

> **Project Name:** Musegix  
> **Repository:** [https://github.com/vishalvermauts/Musegix.git](https://github.com/vishalvermauts/Musegix.git)  
> **Target Event:** Meta Global AI Developer Hackathon  
> **Core Architecture:** Autonomous AI IDE Integration combining `bolt.diy` (Browser IDE UI), `Ysolveth` (INT8 ONNX Model Complexity Triage Router), `PolyFabric` (Tree-sitter AST Context Pruning & RRF Retrieval), and `Veylqora` (C++20 SQLite WAL AST-bounded Agent Memory Engine).  
> **Build Environment:** Docker Cloud Sandboxes (`sbx --cloud` 8-CPU / 16GiB instance: `musegix-builder`) + GitHub Actions Workflows.

---

## 1. System Vision & The Core Problem

When modern AI coding agents operate inside multi-file IDEs (like `bolt.diy`):
1. **Context Bloat:** They dump entire repositories into the prompt, exhausting context windows, increasing latency, and wasting tokens.
2. **Stale Memory Hallucinations:** As code gets iteratively modified in the editor, previous assumptions in the conversation become stale, causing agents to write code against deleted or mutated function signatures.
3. **One-Size-Fits-All Model Routing:** Simple CSS/text changes are needlessly routed to massive 400B+ models, incurring latency and quota penalties, while complex multi-file architectural refactors need high-tier reasoning.
4. **Visual UI Regressions:** Generative agents edit code blindly without verifying whether component layouts, buttons, or navigation bars collide or break in the rendered DOM.

**Musegix** solves this with a unified, high-performance gateway and MCP tool suite:
```
+---------------------------------------------------------------------------------------+
|                                    bolt.diy (Browser IDE)                             |
|         Left: AI Chat        Center: Streaming Editor & Diffs      Right: WebContainer|
+------------------------------------------+--------------------------------------------+
                                           | OpenAI-compatible POST /v1/chat/completions
                                           v
+---------------------------------------------------------------------------------------+
|                               Musegix Gateway (FastAPI SSE Proxy)                     |
|                                                                                       |
|  [Step 1: Ysolveth System One Model]                                                  |
|  -> Real INT8 ONNX Encoder (<5ms CPU) classifies prompt: TRIVIAL / MODERATE / HARD   |
|  -> Routes to: Baseten (Muse Spark Open) or Meta API (Muse Spark 1.3 / Muse Wonder)   |
|                                                                                       |
|  [Step 2: Veylqora AST Memory Engine]                                                 |
|  -> Checks SHA-256 digests of Tree-sitter AST bodies                                  |
|  -> Flags SUSPECTED_STALE memories when code mutates between turns                    |
|                                                                                       |
|  [Step 3: PolyFabric AST Context Pruner]                                              |
|  -> Strips raw file dumps into compact Tree-sitter symbol intervals (Tantivy+LanceDB) |
|  -> Preserves required <boltArtifact> and <boltAction> XML specifications             |
|                                                                                       |
|  [Step 4: Real-time Telemetry SSE Stream]                                             |
|  -> Emits instant latency, model routing, and token reduction metrics                |
|  -> Streams live diffs directly into bolt.diy editor & WebContainer preview           |
+---------------------------------------------------------------------------------------+
```

---

## 2. Hard Architectural Invariants (Non-Negotiable)

1. **Zero Fake Numbers or Mock Heuristics:**
   * All metrics reported to judges and UI must stem from real code execution:
     - `Ysolveth`: Real inference via `onnxruntime` using `encoder_int8.onnx` and Hugging Face tokenizer.
     - `PolyFabric`: Real AST parsing and symbol chunking.
     - `Veylqora`: Real symbol fingerprinting and WAL state checks.
2. **Zero Local Heavy Lifting:**
   * Local machine is strictly for lightweight orchestration and git commits.
   * All compilations, Docker builds, benchmark runs, and tests must execute on the Docker Cloud Sandbox (`musegix-builder`) or GitHub Actions runners.
3. **Strict Credential & Secret Hygiene:**
   * No API keys, tokens, or private secrets in `.ai/`, git history, or logs.
   * All authentication via environment variables (`BASETEN_API_KEY`, `META_API_KEY`).
4. **Preserve `bolt.diy` Contract:**
   * Never tamper with `<boltArtifact id="..." title="...">` or `<boltAction type="file" filePath="...">` tags; otherwise `bolt.diy`'s WebContainer execution engine will fail.

---

## 3. Plan Organization

The complete 5-phase execution plan is split into modular specifications within `plan/`:
- [`plan/01_PHASE_1_BOOTSTRAP_AND_GATEWAY.md`](file:///C:/AI/Hackathon/Meta/plan/01_PHASE_1_BOOTSTRAP_AND_GATEWAY.md): Cloud sandbox setup, repo subtrees, gateway scaffolding, and CI workflow.
- [`plan/02_PHASE_2_BOLT_DIY_UI_INTEGRATION.md`](file:///C:/AI/Hackathon/Meta/plan/02_PHASE_2_BOLT_DIY_UI_INTEGRATION.md): Full `bolt.diy` UI wiring, SSE streaming proxy, WebContainer verification, and test run.
- [`plan/03_PHASE_3_REAL_ENGINE_INTEGRATIONS.md`](file:///C:/AI/Hackathon/Meta/plan/03_PHASE_3_REAL_ENGINE_INTEGRATIONS.md): ONNX Ysolveth integration, PolyFabric AST pruning, Veylqora AST stale memory guard.
- [`plan/04_PHASE_4_MCP_AND_VISION_GATE.md`](file:///C:/AI/Hackathon/Meta/plan/04_PHASE_4_MCP_AND_VISION_GATE.md): FastMCP server, SAM 3.1 visual verification loop, and automated layout checking.
- [`plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md`](file:///C:/AI/Hackathon/Meta/plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md): 26-task benchmark evaluation on cloud sandbox, submission demo script, and final certification gate.
- [`plan/SECURITY_AND_GOVERNANCE.md`](file:///C:/AI/Hackathon/Meta/plan/SECURITY_AND_GOVERNANCE.md): Threat modeling, prompt injection defenses, credential protection, and sandbox isolation.
- [`plan/ERRORS_AND_LOGS.md`](file:///C:/AI/Hackathon/Meta/plan/ERRORS_AND_LOGS.md): Centralized issue tracking, error classification catalog, and run logs.
