# Musegix Errors, Edge Cases & Operational Log Register

> **Centralized Error Tracking & Incident Log**  
> *All encountered runtime errors, build issues, and resolution steps must be recorded here.*

---

## 1. Error Classification Standard

| Severity | Code Pattern | Description | Action Required |
| :--- | :--- | :--- | :--- |
| **FATAL** | `ERR_CRIT_*` | Gateway crash, unhandled exception in SSE stream, or security boundary violation. | Immediate halt, fix, and rerun certification gate. |
| **ERROR** | `ERR_ENG_*` | Failure in an external engine (`Ysolveth` ONNX, `PolyFabric` AST, `Veylqora` SQLite). | Fall back to safe baseline (e.g. default model), log warning. |
| **WARN** | `ERR_CTX_*` | Context pruning dropped a borderline file or token calculation slight mismatch. | Record in session log, refine regex or AST interval boundaries. |
| **INFO** | `LOG_GATE_*` | Normal operational transition (e.g. stale memory detected and refreshed). | Stream in telemetry banner. |

---

## 2. Known Error Signatures & Standard Mitigations

### 1. `ERR_SSE_ROLE_WHITESPACE`
- **Symptom:** `bolt.diy` chat hangs or fails to render assistant message.
- **Cause:** SSE delta dictionary formatted as `{" role": "assistant"}` with leading space.
- **Mitigation:** Ensure exact key `"role": "assistant"` in all SSE JSON serialization.

### 2. `ERR_ONNX_TOKENIZER_MISMATCH`
- **Symptom:** `onnxruntime.InferenceSession` throws shape or datatype error on `input_ids`.
- **Cause:** Passing int32 instead of int64 or missing `attention_mask`.
- **Mitigation:** Explicitly cast numpy arrays: `np.array([encoded.ids], dtype=np.int64)`.

### 3. `ERR_BOLTACTION_TAG_CORRUPTION`
- **Symptom:** `bolt.diy` center code editor stops streaming diffs or right preview fails to hot-reload.
- **Cause:** AST context pruner truncated `<boltArtifact>` or `<boltAction>` XML tag boundaries.
- **Mitigation:** AST pruning logic MUST only operate on file bodies between matching `<boltAction>...</boltAction>` tags, never on the tags themselves.

---

## 3. Active Incident Log Register

| Timestamp (AEDT) | Error ID | Severity | Description | Status | Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-04 14:19 | `ERR_PLAN_MOCKED` | ERROR | Previous plan contained mocked heuristics and fake math. | **RESOLVED** | Deleted old plan; authored new 5-phase plan with real engine bindings. |
| 2026-11-04 14:41 | `LOG_SBX_INIT` | INFO | Created Docker Cloud Sandbox `musegix-builder` (8 CPUs, 16 GiB). | **RESOLVED** | Provisioned and verified online. |
