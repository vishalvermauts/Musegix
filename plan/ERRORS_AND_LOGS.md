# Musegix Errors, Edge Cases & Operational Log Register

> **Centralized Incident Register & Error Catalog**  
> *Track all encountered runtime errors, build defects, and resolutions.*

---

## 1. Active Incident Register

| Timestamp (AEDT) | Error ID | Severity | Description | Status | Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-04 14:19 | `ERR_PLAN_MOCKED` | CRITICAL | Gateway had hardcoded telemetry and plan had mock stand-ins. | **OPEN** | Plan revised to SSOT v2.0; removing all mock constants and adding real Ysolveth head. |
| 2026-11-04 15:13 | `ERR_ONNX_HEAD_MISMATCH` | CRITICAL | Phase 3 assumed ONNX output 3-class logits. Verified ONNX outputs 384-dim embeddings. | **RESOLVED** | Inspected `head_config.json`; updated Phase 3 with mean pooling, L2 normalization, weights projection, and temperature scaling. |
| 2026-11-04 15:15 | `ERR_VENV_ENSUREPIP` | MEDIUM | Ubuntu package `python3.14-venv` missing in cloud sandbox. | **RESOLVED** | Installed `python3-venv` via `apt-get` and created `/home/agent/venv`. |
| 2026-11-04 15:18 | `LOG_ONNX_INSTALLED` | INFO | `onnxruntime`, `tokenizers`, and `numpy` installed and verified in cloud venv. | **RESOLVED** | Verified `encoder_int8.onnx` loads cleanly on 8-CPU sandbox. |

---

## 2. Error Signatures & Defenses

1. `ERR_SSE_ROLE_WHITESPACE`:
   - Enforce `"role": "assistant"` in all JSON chunk serializations.
2. `ERR_AUXILIARY_INJECTION`:
   - Detect prompt enhancement or title summary calls; never inject telemetry banners into them.
3. `ERR_TARGET_FILE_TRUNCATION`:
   - Pruner must never truncate the active edit target file; only background dependency files can be pruned to AST stubs.
