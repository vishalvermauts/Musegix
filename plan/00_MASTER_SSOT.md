# Musegix Project Architecture & Single Source of Truth (SSOT) - v2.0

> **Project Name:** Musegix  
> **Repository:** [https://github.com/vishalvermauts/Musegix.git](https://github.com/vishalvermauts/Musegix.git)  
> **Target Event:** Meta Global AI Developer Hackathon  
> **Core Architecture:** Autonomous AI IDE Gateway combining `bolt.diy` (Browser IDE UI), `Ysolveth` (INT8 ONNX MiniLM Embedding Encoder + Calibrated Linear Head), `PolyFabric` (Tree-sitter AST Context Pruning & Bounded Retrieval), and `Veylqora` (Evidence-Anchored Memory Invalidation Engine).  
> **Build Environment:** Docker Cloud Sandboxes (`musegix-builder` on `sbx --cloud`, 8 vCPUs / 16 GiB RAM) + GitHub Actions CI.

---

## 1. System Vision & Architecture

Musegix sits as an intelligent, high-performance gateway between the browser IDE (`bolt.diy`) and Meta's model family (Muse Spark / Muse Wonder):

```
+-------------------------------------------------------------------------------------------------+
|                                    bolt.diy (Browser IDE)                                       |
|             Left: AI Chat        Center: Live Editor & Diffs        Right: WebContainer Preview |
+------------------------------------------------+------------------------------------------------+
                                                 |
                                                 | POST /v1/chat/completions (OpenAI SSE)
                                                 v
+-------------------------------------------------------------------------------------------------+
|                                    Musegix Gateway (FastAPI)                                    |
|                                                                                                 |
|  [Step 1: Request Intercept & Context Separation]                                               |
|  -> Identifies request type: User Generation vs. Prompt Enhancer vs. Context Selection          |
|  -> Auxiliary calls pass through untouched with ZERO banner pollution                          |
|                                                                                                 |
|  [Step 2: Ysolveth System One Model (<5ms CPU)]                                                 |
|  -> Runs real ONNX encoder (input_ids, attention_mask) -> last_hidden_state (384-dim)           |
|  -> Performs Attention-Mask Mean Pooling + L2 Normalization                                     |
|  -> Projects via trained weights & bias from head_config.json                                   |
|  -> Calibrates via temperature scaling (T=0.2842) -> Softmax (hard, moderate, trivial)         |
|  -> Routes: TRIVIAL -> Muse Spark Open | MODERATE -> Muse Spark 1.3 | HARD -> Muse Wonder 1.0   |
|                                                                                                 |
|  [Step 3: Veylqora Evidence-Anchored Memory Guard]                                              |
|  -> Tracks AST symbol fingerprints across workspace turns                                       |
|  -> Flags SUSPECTED_STALE only when code cited in prior turns has mutated its fingerprint       |
|                                                                                                 |
|  [Step 4: PolyFabric AST Context Pruner]                                                        |
|  -> Keeps 100% of the active target file intact (preserves <boltArtifact> & <boltAction>)       |
|  -> Compresses non-targeted background files into exported AST symbol signatures                |
|                                                                                                 |
|  [Step 5: Upstream Bidirectional SSE Streaming]                                                 |
|  -> Establishes single stable request ID (chatcmpl-...)                                         |
|  -> Emits measured telemetry banner (or X-Musegix-Telemetry header)                             |
|  -> Transparently forwards chunks, delta content, usage tokens, and tool_calls                  |
|  -> Propagates client disconnection and closes upstream streams cleanly                         |
+-------------------------------------------------------------------------------------------------+
```

---

## 2. Hard Invariants (Zero Exceptions)

1. **Absolute Honesty — Zero Fake Constants or Mock Heuristics:**
   * No hardcoded latencies (e.g. `+ 3.1 ms` or `3.2 ms`).
   * No hardcoded token multipliers (e.g. `* 0.14` or `90.8%`).
   * Any metric that is not measured at runtime must display `n/a` or be omitted.
2. **Transparent Generation First:**
   * The gateway MUST deliver live model streaming to `bolt.diy` so files are created and previewed in WebContainer. A gateway that only echoes an acknowledgement is non-functional.
3. **Verified Mathematical Inference for Ysolveth:**
   * Ysolveth must execute the true verified pipeline: ONNX encoder $\to$ Attention-Mask Mean Pooling $\to$ L2 Normalization $\to$ Linear Projection with `weights` ($3 \times 384$) & `biases` ($3$) $\to$ Temperature Scaling ($T=0.2842$) $\to$ Softmax.
4. **Preserve `bolt.diy` Protocols:**
   * Auxiliary calls (prompt enhancement, summaries) pass through cleanly.
   * `role` key in SSE chunks must never have leading spaces.
   * Target edit files must retain full content; only background files are pruned into AST signatures.
5. **Clean Resource Execution:**
   * Heavy builds, indexing, and benchmarks run on the Docker Cloud Sandbox (`musegix-builder`).
   * Local PC runs only lightweight git sync and orchestration.

---

## 3. Modular Specification Suite

- [`plan/01_PHASE_1_BOOTSTRAP_AND_GATEWAY.md`](file:///C:/AI/Hackathon/Meta/plan/01_PHASE_1_BOOTSTRAP_AND_GATEWAY.md): Cloud sandbox, repo subtrees, gateway scaffolding, and CI gate. *(Status: CERTIFIED)*
- [`plan/02_PHASE_2_BOLT_DIY_UI_INTEGRATION.md`](file:///C:/AI/Hackathon/Meta/plan/02_PHASE_2_BOLT_DIY_UI_INTEGRATION.md): Upstream LLM proxy, auxiliary request passthrough, and live WebContainer hot-reloading.
- [`plan/03_PHASE_3_REAL_ENGINE_INTEGRATIONS.md`](file:///C:/AI/Hackathon/Meta/plan/03_PHASE_3_REAL_ENGINE_INTEGRATIONS.md): Verified Ysolveth ONNX mean-pooling head, PolyFabric AST pruning, and Veylqora anchored memory.
- [`plan/04_PHASE_4_MCP_AND_VISION_GATE.md`](file:///C:/AI/Hackathon/Meta/plan/04_PHASE_4_MCP_AND_VISION_GATE.md): FastMCP server, Playwright DOM verification gate, and tool-call passthrough.
- [`plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md`](file:///C:/AI/Hackathon/Meta/plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md): Measured benchmark harness, JSON telemetry, and demo video script.
- [`plan/SECURITY_AND_GOVERNANCE.md`](file:///C:/AI/Hackathon/Meta/plan/SECURITY_AND_GOVERNANCE.md): Path sanitization, bearer token authentication, credential protection, and sandbox isolation.
- [`plan/ERRORS_AND_LOGS.md`](file:///C:/AI/Hackathon/Meta/plan/ERRORS_AND_LOGS.md): Centralized error catalog and incident register.
