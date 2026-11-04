# Musegix

> **Intelligent Multi-Model Routing, AST Context Pruning & Staleness-Aware Agent Memory for `bolt.diy`**

[![CI Gate](https://github.com/vishalvermauts/Musegix/actions/workflows/ci.yml/badge.svg)](https://github.com/vishalvermauts/Musegix/actions/workflows/ci.yml)
[![Target Event](https://img.shields.io/badge/Hackathon-Meta_Global_AI_Developer-purple.svg)](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Musegix** is an intelligent AI IDE gateway designed to solve the three biggest problems in browser-based AI code generation: **context window bloat**, **stale memory hallucinations**, and **wasteful model over-provisioning**.

It seamlessly integrates with [bolt.diy](https://github.com/stackblitz-labs/bolt.diy) as an OpenAI-compatible SSE proxy, connecting real, verified developer tools:
- **[Ysolveth](https://github.com/vishalvermauts/Ysolveth):** A real `<5 ms` INT8 ONNX System One complexity classifier running on CPU to route requests between Meta's Muse Spark and Muse Wonder models.
- **[PolyFabric](https://github.com/vishalvermauts/PolyFabric):** Local Tree-sitter AST symbol indexing and context pruning, saving 85%+ prompt tokens while preserving `bolt.diy`'s `<boltArtifact>` format.
- **[Veylqora](https://github.com/vishalvermauts/Veylqora):** C++20 SQLite WAL memory engine tracking SHA-256 AST fingerprints to flag stale agent assumptions in real-time.

---

## Architecture Overview

```
+---------------------------------------------------------------------------------------+
|                                    bolt.diy (Browser IDE)                             |
|         Left: AI Chat        Center: Streaming Editor & Diffs      Right: WebContainer|
+------------------------------------------+--------------------------------------------+
                                           | POST /v1/chat/completions (OpenAI SSE)
                                           v
+---------------------------------------------------------------------------------------+
|                               Musegix Gateway (FastAPI SSE Proxy)                     |
|                                                                                       |
|  [1. Ysolveth ONNX Classifier]  -->  CPU-bound prompt complexity routing in <5ms      |
|  [2. Veylqora AST Guard]        -->  Catches mutated code symbols via SQLite WAL      |
|  [3. PolyFabric AST Pruner]     -->  Prunes raw file dumps into compact AST stubs     |
|  [4. SSE Telemetry Streamer]    -->  Streams live metrics, code diffs, & HMR updates  |
+---------------------------------------------------------------------------------------+
```

---

## 5-Phase Master Plan & Certification Gates

See our detailed documentation suite in [`plan/`](plan/):
- [Master Single Source of Truth (SSOT)](plan/00_MASTER_SSOT.md)
- [Phase 1: Bootstrap, Cloud Sandbox & Gateway](plan/01_PHASE_1_BOOTSTRAP_AND_GATEWAY.md)
- [Phase 2: Full UI Integration with `bolt.diy`](plan/02_PHASE_2_BOLT_DIY_UI_INTEGRATION.md)
- [Phase 3: Real Engine Integrations](plan/03_PHASE_3_REAL_ENGINE_INTEGRATIONS.md)
- [Phase 4: FastMCP Server & Visual Render Gate](plan/04_PHASE_4_MCP_AND_VISION_GATE.md)
- [Phase 5: Automated Benchmarks & Final Release](plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md)
- [Security & Governance Architecture](plan/SECURITY_AND_GOVERNANCE.md)
- [Errors, Logs & Incident Register](plan/ERRORS_AND_LOGS.md)

---

## Quick Start (Cloud Sandbox)

```bash
# Clone the repository
git clone https://github.com/vishalvermauts/Musegix.git
cd Musegix

# Run Cloud Provisioning Script
bash scripts/cloud_setup.sh

# Start Gateway
uvicorn gateway.app:app --host 0.0.0.0 --port 8000
```
