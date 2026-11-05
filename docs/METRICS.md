# Musegix metrics: where each number comes from

Every number below is written to the gateway log (`uvicorn` stdout) or to the banner the gateway
streams at the top of a chat reply. Nothing here is estimated; a value is only reported when it was measured.

| Number | Log line or banner | Source in code |
|---|---|---|
| Triage tier and target model | Banner: `> ⚡ **Ysolveth Triage**: \`TIER\` → \`model\` (X ms ONNX CPU)` | `gateway/streaming.py` `get_default_telemetry_banner`; `triage_ms` is the classifier latency |
| Triage fallback (classifier failed, defaults to MODERATE) | `Ysolveth triage fallback: ...` (WARNING) | `gateway/routes.py` |
| PolyFabric context pruning: raw vs pruned tokens, files kept/pruned, time | `[polyfabric] RAW -> PRUNED tokens kept=N pruned=M files (T ms)` | `gateway/routes.py` (per prompt, per context message) |
| PolyFabric banner (first pruning of a turn) | Banner: `> 🔍 **PolyFabric AST**: ...` | `gateway/routes.py` |
| Old tool results pruned | `[polyfabric-tools] old tool results BEFORE -> AFTER tokens` | `gateway/routes.py`, `gateway/engines/tool_result_pruner.py` |
| Symbol map size (files indexed, map tokens) | `[symbolmap] N files indexed, map T tokens` | `gateway/routes.py`, `gateway/engines/symbol_index.py` |
| Repair step kept whole | `[polyfabric-repair] keeping PATH in full, stubbing the rest` | `gateway/routes.py`, `gateway/engines/repair.py` |
| Veylqora stale memories | Banner: `> 🧠 **Veylqora Memory**: ...` | `gateway/routes.py`, `gateway/engines/veylqora_guard.py` |
| Veylqora impact (changed exports still used by other files) | Banner: `> 🧠 **Veylqora impact**: ...` | `gateway/engines/repair.py` |
| Model call summary: finish reason, completion tokens, tool calls | `[stream] model=... finish=... completion_tokens=... tool_calls=[...]` | `gateway/streaming.py` |
| Request bodies (for replaying a turn) | `[dump] FILE roles=... tools=N` when `MUSEGIX_DUMP_REQUESTS=1` | `gateway/routes.py`, saved to `data/requests/` |

## How to read them

- Tokens: `count_tokens` in `gateway/engines/polyfabric_pruner.py` (tiktoken `cl100k_base`, with a
  fallback counter if tiktoken is missing). The same counter is used for raw, pruned and map sizes.
- Wall time per step: the `[stream]` line is written after the upstream stream ends. Triage and PolyFabric
  times come from the banner and the `[polyfabric]` line.
- Tiers are only in the Triage banner and in the `Ysolveth Triage` line of the first step. Later tool steps show the
  PolyFabric and Veylqora lines only.
- Model prices are not in this file. Dollar figures need the provider's current price list and are not quoted here.

## Commands

- Start the gateway: `bash scripts/run_demo.sh` (prints the bolt.diy URL).
- Save requests for replay: set `MUSEGIX_DUMP_REQUESTS=1` before starting the gateway.
