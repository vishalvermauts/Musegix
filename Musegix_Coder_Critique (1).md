# Musegix: detailed critique, debate and implementation handoff

**Prepared:** 4 November 2026  
**Repository:** https://github.com/vishalvermauts/Musegix  
**Reviewed baseline:** `d7a7ba9969666672ca8eabcab6bf93577d9beaca`  
**Purpose:** Reconcile the implementation plan and supplied “Findings, Issues & Solutions” review, then guide the AI coder through corrective implementation.

> Evidence boundary: this expands the source review already performed in this conversation. It is not a fresh audit of a newer commit, a deployed-system test, or a completed security assessment. Component READMEs and selected bolt.diy source were inspected; their full implementations, model binaries and external provider endpoints were not executed. Recheck the current checkout and pin dependencies before implementation. Recommendations below are proposed design decisions unless explicitly described as confirmed source findings.

## 1. Executive judgment

Musegix has a useful integration goal: route coding work, retrieve focused code context and invalidate memories when their supporting code changes. The reviewed repository does not yet implement that complete product. Its committed gateway returns hardcoded telemetry and an acknowledgement without an upstream LLM call. The engine, MCP and benchmark examples in the plan contain placeholders or simplified substitutes.

The supplied review is right to prioritize honesty, upstream generation and actual bolt.diy payloads. However, copying its fixes would leave important defects: incomplete Ysolveth inference, unsafe session identity, race-prone telemetry, weak visual verification and an undefined bridge between browser files and server-side engines.

**Recommended decision:** retain the architecture, implement a working generation path first, establish an authoritative workspace revision contract, and integrate the real engines through their supported interfaces. Treat benchmarks as required evidence for performance claims. The visual gate can be optional for the first release.

### Evidence and priority summary

| Finding | Evidence status at reviewed baseline | Priority |
| --- | --- | --- |
| Gateway never calls an upstream model | Confirmed in committed `gateway/streaming.py` | P0 |
| Non-streaming route returns canned text | Confirmed in committed `gateway/routes.py` | P0 |
| Ysolveth plan omits embedding pooling and trained head | Confirmed mismatch with Ysolveth reference inference | P0 |
| Browser workspace synchronization is unspecified | Missing architectural contract in inspected plan | P0 before claiming real engine integration |
| PolyFabric/Veylqora snippets are stand-ins | Confirmed in Phase 3 plan; engine modules absent from tree | P1 |
| MCP and benchmark examples return fixed results | Confirmed in plan; corresponding runtime files absent | P1 for any advertised capability |
| Isolation and staleness semantics are insufficient | Confirmed omissions in proposed guard design | P1 |
| Visual overlap fix is unreliable | Design defect in supplied suggestion | P2; optional feature |
| README presents planned capabilities as verified | Confirmed mismatch with committed runtime | P0 documentation correction |

P0 means a foundational blocker or immediate truthfulness issue. P1 means necessary for a claimed core feature. P2 means a secondary capability that can be deferred explicitly.

## 2. What to accept from the supplied review

Accept these recommendations, with the qualifications developed below:

- Replace both streaming and non-streaming acknowledgements with real upstream behavior.
- Remove fabricated latency, token and staleness values from runtime output immediately.
- Capture sanitized requests from the exact bolt.diy version being integrated.
- Validate tokenizer paths, ONNX input/output contracts and label mappings.
- Stop describing regex signature extraction as the real PolyFabric engine.
- Stop describing Python whole-file hashes as Veylqora's C++ symbol-aware memory engine.
- Preserve tools, tool calls and results across provider requests and responses.
- Replace benchmark expected values with observed predictions and measurements.
- Reopen `ERR_PLAN_MOCKED` until the remaining placeholders are actually removed or excluded from claimed functionality.
- Align provisioning, CI, reproduction instructions and dependency versions.

The reviewer is also right that mocks in tests are useful. The problem is mocked production behavior presented as measured or verified output.

## 3. Detailed findings and recommended fixes

### F01 — The committed gateway is scaffolding, not a generation proxy

**Evidence:** `gateway/streaming.py` assigns `triage_ms = 3.2`, `selected_tokens = 780`, `raw_tokens = 8450` and `reduction_pct = 90.8`. It emits a banner, acknowledgement, stop chunk and `[DONE]`. No upstream model client is invoked. `gateway/routes.py` returns “Musegix gateway ready.” for non-streaming calls.

**Impact:** bolt.diy cannot create or edit an application through this gateway. Model discovery and health tests can pass while the primary product path is absent.

**Debate:** implementing the upstream proxy first is correct. The supplied replacement is only a sketch: it mixes a synthetic first chunk with unmodified upstream identities, claims to strip the upstream role without doing so, and turns an upstream exception into ordinary assistant content with a normal stop reason.

**Recommended fix:** choose either a transparent upstream stream or a consistently normalized gateway stream. If normalizing, assign one identity for the request and preserve choice indexes, content, tool-call fragments, usage and actual finish reasons. Validate configuration before sending response headers where practical. Once streaming has started, report failures using the pinned client's supported error behavior; do not label a partial generation successful. Close upstream streams in `finally`, propagate cancellation, and avoid unbounded automatic retries after output begins.

**Acceptance criteria:** a first prompt creates working files; a second prompt edits them; non-streaming auxiliary requests return genuine model output; tool-call arguments survive fragmentation; a provider error is distinguishable from success; Stop closes upstream work; all chunks have the chosen consistent identity; no placeholder values remain.

### F02 — Ysolveth's proposed inference pipeline is materially wrong

**Evidence:** Phase 3 interprets `outputs[0][0]` as three-class logits. Ysolveth's README describes an INT8 MiniLM embedding encoder plus a separate calibrated head in `head_config.json`. Its reference example performs attention-mask mean pooling, embedding normalization, linear projection, temperature scaling and softmax.

**Impact:** the wrapper may fail because expected inputs are missing, misinterpret dimensions, or produce an invalid class prediction. Fixing the tokenizer filename alone does not fix inference.

**Recommended fix:** implement the reference preprocessing and head exactly for a pinned artifact set. Inspect ONNX input names, shapes and dtypes. Supply `token_type_ids` if the graph requires them. Read classes, weights, bias and temperature from the matching head config; validate dimensions, finite values and positive temperature. Confirm truncation and special-token behavior against the reference. Verify checksums for the encoder, head and tokenizer as one compatible bundle.

Load once during service startup. Use bounded CPU execution capacity so inference does not block every async request. Report model-load time, cold inference and warm inference separately. Treat confidence as a model output, not a guaranteed probability of task success.

**Debate:** E3 in the original review described embeddings as a possibility. The inspected reference makes the missing pooling/head an established integration mismatch. E2's proposed 256-token limit matches the README example, but still needs validation against the pinned artifacts.

**Acceptance criteria:** reference and gateway predictions/probabilities agree within a declared numerical tolerance on fixed examples; long prompts are handled deterministically; invalid artifact combinations fail readiness; cold/warm measurements are real; dependency failure produces the configured fallback or explicit unavailable status.

### F03 — Workspace synchronization is the largest missing integration contract

**Evidence:** bolt.diy generates files in a browser WebContainer. The plan clones PolyFabric and Veylqora into a cloud workspace without defining how those engines receive the current generated project. Component repositories are engine source, not the user's generated workspace.

**Impact:** real engines can index the wrong filesystem or obsolete code while returning convincing-looking results. Manual browser edits, deleted files and renamed symbols may never reach the server.

**Recommended design:** introduce a thin workspace adapter before engine integration. This does not require replacing bolt.diy's filesystem. It requires an explicit bridge carrying identity and authoritative source revisions.

| Field | Purpose |
| --- | --- |
| `workspace_id` | Identifies the generated project, separate from a conversation |
| `session_id` | Identifies a conversation where needed |
| `revision` | Identifies an accepted workspace state |
| `base_revision` | Detects stale or out-of-order deltas |
| File upserts/deletions | Represents actual source changes, including renames as explicit operations or delete/upsert |
| `request_id` | Correlates generation, indexing and telemetry |

Prefer explicit client/server integration for identity and file state. Reconstructing from request payloads can be an interim adapter only when fixtures establish that the relevant context is complete and authoritative. Partial context must never be interpreted as a complete filesystem snapshot.

Engine results should carry `indexed_revision`. For a request needing revision R, use results for R, wait within a bounded budget, or declare indexing unavailable and follow the configured conservative path. Do not silently claim freshness. Serialize or otherwise order updates per workspace, and make retried deltas idempotent.

**Acceptance criteria:** edits, deletions, renames, repeated updates and out-of-order updates behave correctly; two projects using the same filenames remain isolated; no request consumes a partially applied revision; browser and engine snapshots agree for the demonstrated revision.

### F04 — Real PolyFabric integration needs supported APIs and safe context assembly

**Evidence:** the proposed `PolyFabricPruner` uses substring overlap and line-prefix extraction. It imports neither PolyFabric nor Tree-sitter. Its one-match rule can retain most files for common query terms. The supplied review repeats an assumed `src/polyfabric` path, whereas the inspected PolyFabric README documents `infinite_memory` entry points and tools such as `mesh_build_task_context`.

**Impact:** the implementation does not support the advertised engine claims. More seriously, compression may omit code required for a correct edit.

**Recommended fix:** inspect the pinned package's public API or existing MCP task-context interface. Prefer reuse over inventing a second retrieval engine. Use one workspace source bridge for both retrieval and memory. Avoid redundant parsing where practical, but do not tightly couple the two packages merely to share an optimization.

Separate historical messages from current source context. Keep complete current contents for files that the generation protocol expects the model to replace in full. Supporting snippets should be explicitly marked excerpts with path, revision, symbol and line provenance. Provide a way to expand evidence. Include relevant imports, callers, types and configuration where required; top-K rank alone does not establish completeness.

**Debate:** preserving `<boltAction>` tags while substituting partial file bodies preserves syntax, not meaning. The model may infer that omitted implementation never existed. Renaming that mechanism “AST pruning” does not resolve this correctness issue.

**Acceptance criteria:** retrieval runs against the requested revision; absent symbols return an honest empty result; target-file edits preserve unrelated content; generated projects still build; focused context has traceable provenance; token reductions are accompanied by task-correctness results.

### F05 — Veylqora needs memory evidence, not just file-change badges

**Evidence:** Phase 3 hashes complete file bodies using Python, stores `file_root`, uses `:memory:` SQLite and scans every message chronologically. It has no persistent memory records tied to cited symbols and no workspace key.

**Impact:** replayed history can repeatedly compare old and new versions, causing false stale signals. Separate chats can contaminate state. File changes are presented as proof of invalidated assumptions without establishing dependencies.

**Recommended fix:** use Veylqora's supported CLI/HTTP/MCP interfaces after inspecting their exact contracts. Record a memory with explicit symbol evidence and the fingerprint/revision it was based on. Refresh the workspace, then ask the real validity mechanism which memories lost valid evidence. Distinguish changed evidence, missing evidence, verified invalidity and normal active state.

If a temporary file-diff detector is retained, call it “workspace changes detected.” Do not call it the real Veylqora memory lifecycle. A file-backed database is required for a WAL/persistence claim; verify the journal mode actually selected. Respect the documented single-writer design rather than sharing one unsynchronized connection across workers.

**Debate:** hashing the opening user/system prompts is not safe session identity; identical openings collide and edited openings split state. “Changed file referenced in recent assistant text” is still only a heuristic. Extracting and hashing raw AST node text is also not automatically equivalent to Veylqora's documented normalization of comments and whitespace.

**Acceptance criteria:** an anchored memory becomes suspected stale after its dependency changes; unrelated changes do not invalidate it; deleted evidence gets the correct missing state; replaying unchanged history produces no new false event; projects and sessions remain isolated; restart persistence matches the advertised behavior.

### F06 — Telemetry must be separate, attributable and temporally possible

**Evidence:** Phase 2 requires a telemetry banner as the first assistant chunk, including token-reduction values. The supplied review proposes a response header or `/v1/telemetry/last` for benchmarks.

**Impact:** banners can enter future conversation history, alter structured outputs and pollute prompt enhancement. A global last-result endpoint races across requests. Final provider usage is generally unavailable before streaming headers are sent.

**Recommended fix:** assign a request ID and store a bounded, authenticated telemetry record for it. Separate pre-generation facts from final generation outcomes. A small UI integration or side panel is preferable to changing assistant text. If a banner is temporarily retained, enable it only for explicitly identified user-facing generation, and prevent it becoming engine evidence or future prompt content.

Record provider/model, selected tier, component readiness, workspace/index revision, stage timings, token-count method and final success/failure/cancellation. Do not store raw private source in telemetry by default.

**Measurement rules:** distinguish estimated tokens from provider-reported input tokens; count identical regions when calculating reduction; include message/tool overhead where relevant; do not call prompt reduction total-token savings; do not call token savings billing savings without billing evidence. Measure first upstream content separately from an immediate synthetic banner. Tool-only responses need their own first-output timing definition.

**Acceptance criteria:** concurrent requests retrieve only their own records; missing usage stays unavailable; a banner cannot improve reported model TTFT; failure/cancellation is retained; no unmeasured metric becomes a numeric zero or fabricated constant.

### F07 — bolt.diy integration assumptions require a pinned version

**Evidence:** the inspected upstream source contains context-selection calls, MCP support and an OpenAI-like model parser. Its fallback environment format is `model:limit`, with semicolon-separated entries. Musegix proposes `model:display-label:128000`. Successful model discovery currently maps models to `maxTokenAllowed: 8000`.

**Impact:** configuration can parse incorrectly or establish an unexpected budget. Integrating against a moving default branch makes payload and SDK assumptions unstable.

**Recommended fix:** pin a bolt.diy commit and maintain sanitized fixtures from that build. Verify configuration parsing, model discovery, request construction, tool capabilities and auxiliary calls. Prefer explicit call-type metadata from a thin integration adapter over guessing request purpose from system-prompt substrings. Until proven, use conservative passthrough for unknown call types.

Normalize text only for routing input. Preserve images and other content parts in the actual forwarded request. Preserve tool-call IDs and result relationships. Test providers for the exact capabilities required rather than routing solely by complexity.

Confirm secure-origin/cross-origin-isolation and preview reachability in the actual deployment topology. The IDE URL and generated preview URL are different targets. Loopback addresses refer to the process/container making the request, not automatically to the user's laptop.

**Acceptance criteria:** initial generation, follow-up edit, enhancement, context selection/summary when enabled, image content when supported, and a complete tool-call/result round trip work on the pinned build. The generated preview actually boots.

### F08 — The proposed visual gate overstates what it verifies

**Evidence:** the plan returns `PASSED` and `42` without launching a browser. The supplied replacement launches Playwright but references an undefined overlap function, takes no screenshot and treats rectangle intersections as failures.

**Impact:** nested elements, intentional overlays, sticky headers and badges can trigger false positives. A blank or wrong page can pass weak checks. The cloud browser may not reach a browser-owned WebContainer preview.

**Recommended fix:** first prove preview accessibility. If a separately launched sandbox copy is rendered, identify that copy and revision; do not imply it is the live browser preview. Use bounded navigation and an explicit application-ready condition rather than relying solely on network idle. Capture runtime failures, expected controls and targeted layout assertions. Add screenshots where visual evidence is needed. A smoke test must not claim zero visual defects.

Restrict URLs to approved project origins, account for redirects, block unintended internal targets, and run rendering in an isolated browser environment. Browser cleanup belongs in `finally`.

**Acceptance criteria:** detect a deliberate runtime failure, missing expected control and known overflow; accept normal nesting; fail or report unavailable for an inaccessible preview; record the rendered revision and viewport. Defer this feature explicitly if it threatens the working core demo.

### F09 — Failure policies and security claims need component-specific behavior

**Evidence:** the security plan demands fail-closed routing while the error register recommends default-model fallback. The committed app permits broad CORS and has no gateway authentication. Planned path/redaction defenses are not implemented in the inspected runtime.

**Recommended policy:**

| Failure | Proposed behavior |
| --- | --- |
| Invalid credentials or unauthorized workspace | Reject; no provider request |
| Classifier unavailable | Use an explicitly configured supported default, or return unavailable |
| Retrieval unavailable | Send permitted full context if it fits; otherwise request a bounded alternative or fail clearly |
| Memory validation unavailable | Exclude unvalidated memory or clearly mark it untrusted |
| Provider failure before output | Permit only configured, capability-compatible fallback with recorded attribution |
| Provider failure after partial output | Report incomplete generation; do not silently concatenate a second model's answer |
| Render unavailable | Report unavailable; never convert it to passed |

Authenticate any reachable billable gateway. Bind addresses according to container topology; `127.0.0.1` is not universally reachable from another container. Restrict or remove CORS according to actual browser access, while recognizing that CORS is not authentication. Bound request sizes, concurrent work and retry budgets.

Validate filesystem paths at actual file-operation boundaries using canonical workspace containment, not one regex. Handle traversal, absolute paths and symlink escapes where applicable. Match defenses to the process that can actually write files. A proxy-level filter does not establish host sandbox isolation.

Streaming secret redaction must handle chunk boundaries if implemented. Broad substitutions can corrupt generated code and cannot guarantee confidentiality. Keep provider credentials out of prompts and source context in the first place; do not claim unimplemented redaction is protection.

**Acceptance criteria:** unauthorized requests trigger no billable work; fallback cannot change data destinations unexpectedly; invalid paths cannot escape the mirror root; errors and logs do not reveal credentials; readiness and component degradation are observable.

### F10 — Benchmarks must establish useful outcomes, not attractive routing labels

**Evidence:** Phase 5 lists three tasks while describing ten; the SSOT references 26. The harness prints expected tiers/models and literal timing/pruning strings. It stops after the first JSON event, without establishing completed generation.

**Impact:** the report cannot support routing accuracy, successful edits, token savings or latency claims. A telemetry banner can make an incomplete request look fast.

**Recommended evaluation:** maintain a fixed task manifest with source revision, task instructions, expected behavior and executable acceptance checks. Separate classifier evaluation from coding outcome evaluation. Include first generation, local changes, cross-file changes, stale evidence, missing symbols and negative cases.

At minimum compare a configured fixed-model/full-context baseline with the complete Musegix path. If attributing gains to individual components, add controlled ablations: routing only, retrieval only and memory validation on relevant tasks. Use the same initial workspace and comparable model settings. Restore state between independent runs, and document caching, warm-up and provider variability.

Report task success, first-pass success, repairs, build/test outcomes, input/output tokens, preprocessing time, first upstream content and completion time. Count failures and timeouts in denominators. Publish sample size; five repeats are a smoke check, not strong tail-latency evidence. Use enough observations for percentile claims and report uncertainty where practical.

**Acceptance criteria:** all rows derive from machine-readable records; predictions are observed; full streams are consumed/closed; task counts agree; run metadata contains commits, artifact identifiers and configuration; failed trials remain visible. Comparative evaluation is required for improvement claims; the visual feature remains optional.

### F11 — Provisioning, CI and documentation must describe the same system

**Evidence:** the real setup script lacks the plan's Node/pnpm installation and component clones. Planned config/schema/engine modules are absent. CI runs only two endpoint tests. README links a missing license and claims verified tools plus 85%+ reduction. `components/` is not ignored; the plan refers to master while CI uses main.

**Recommended fix:** link executable setup files from the plan instead of maintaining divergent code copies. Pin component commits and use a reproducible dependency lock/constraints process. A raw global `pip freeze` is not automatically a clean project lock. Decide explicitly between external clones and submodules; ignoring `components/` is appropriate for disposable clones, not a universal dependency policy. Either approach needs recorded revisions and license compliance.

Add meaningful gateway contract tests and workspace/engine integration tests. Unit mocks are appropriate, but required engine integration CI must not silently pass because artifacts are missing. Separate lightweight tests from an artifact-provisioned required integration job. Do not require paid live LLM calls on every PR; use controlled provider smoke checks and offline protocol fixtures.

Correct the branch name, model alias consistently, Linux shell line endings and dead document links. Inspect licensing ownership before adding the intended license. Mark each feature as planned, implemented or verified with evidence. Keep historical engine benchmark numbers separate from new Musegix integration results.

**Acceptance criteria:** a clean environment follows documented commands successfully; CI's required checks exercise advertised components; expected missing artifacts fail the integration job; README claims match stored evidence; no placeholder is described as completed.

## 4. Decisions the coder should make explicitly

| Decision | Recommended default | Why |
| --- | --- | --- |
| Workspace ownership | Browser is authoritative; server mirror is revisioned | Avoid treating history as filesystem truth |
| Session identity | Explicit generated identifiers, scoped to authorized workspace | Prevent collisions and leakage |
| Engine integration | Existing public APIs/MCP before custom bindings | Reduce duplicated functionality |
| Telemetry | Separate authenticated request-scoped records | Preserve generation contracts |
| Pruning | Complete target files plus bounded supporting evidence | Reduce destructive whole-file edits |
| Staleness | Explicit memory-to-symbol evidence | Establish what a change actually invalidates |
| Visual validation | Optional smoke/targeted checks with honest scope | Avoid unsupported universal guarantees |
| Release evidence | Required baseline comparison for improvement claims | Distinguish a working integration from a proven improvement |

These are proposed defaults, not a requirement to build a large new platform. Keep adapters small and justify departures with evidence from the pinned code.

## 5. Revised implementation sequence

### Milestone A — Functional transport

Verify provider URLs, exact model IDs and capabilities with authorized credentials. Implement authentication, upstream streaming/non-streaming, cancellation and structured failure behavior. Remove fake telemetry. Prove an app can be generated and edited through bolt.diy before adding engine complexity.

**Exit evidence:** sanitized request/response fixtures, protocol tests and a working generated preview.

### Milestone B — Authoritative workspace and request contracts

Pin bolt.diy. Implement explicit identity and revision synchronization. Distinguish generation, auxiliary and tool-bearing calls. Confirm engine source mirrors and deletion/rename handling.

**Exit evidence:** workspace revision tests, isolation tests and current-source agreement.

### Milestone C — Correct Ysolveth routing

Load compatible encoder/head/tokenizer artifacts, implement reference inference, validate output and constrain routing by provider capability. Measure cold/warm behavior.

**Exit evidence:** reference-parity results and actual route attribution.

### Milestone D — Real PolyFabric retrieval

Index the synchronized workspace and call supported retrieval/context interfaces. Assemble safe context; preserve full edit targets and provenance. Verify index freshness before use.

**Exit evidence:** retrieval examples and successful edits against the requested revision.

### Milestone E — Real Veylqora memory validity

Record explicit memory evidence, update the index after a relevant edit and observe the correct state transition. Test isolation, replay and persistence.

**Exit evidence:** a repeatable active → suspected-stale or evidence-missing demonstration tied to actual stored evidence.

### Milestone F — Evaluation and release

Run the declared baseline comparison, retain machine-readable records and generate honest reports. Add the render gate only if its environment and assertions are proven. Update documentation, incident statuses and demo claims from actual evidence.

**Exit evidence:** reproducible outcomes and bounded claims. Do not substitute a polished video or green health-check CI for this milestone.

## 6. Required handoff outputs from the implementing coder

1. A current-state reconciliation against this review, marking each item applicable, fixed or superseded with evidence.
2. An updated implementation plan with actual API entry points, pinned versions, workspace contract and failure policies.
3. Working code and focused tests for the implemented paths.
4. A compact verification record: checked commit, commands/checks, pass/fail results, known limits and remaining work.
5. A benchmark report whose numbers trace to retained run records and whose claims distinguish measured improvement from demonstration only.
6. Updated README and incident register without invented completion or performance claims.

Work within the user's authorized scope and existing resource constraints. Do not infer a real deployment, credential availability, paid-test budget or hackathon eligibility from this document. Do not create duplicate branches or new mock engine implementations merely to claim progress.

## 7. Final acceptance checklist

- [ ] Real generation and follow-up editing work through the gateway.
- [ ] Non-streaming auxiliary requests and supported tool cycles work.
- [ ] Stream errors, cancellation and partial outputs are handled honestly.
- [ ] Ysolveth matches its complete reference inference pipeline.
- [ ] Workspace/session identities and revision synchronization are explicit.
- [ ] Retrieval and memory refer to the correct project and revision.
- [ ] PolyFabric and Veylqora use actual supported interfaces, or stand-ins are clearly labelled and excluded from engine claims.
- [ ] Pruning preserves task correctness and complete file replacements.
- [ ] Staleness is demonstrated using anchored memory evidence.
- [ ] Telemetry is measured, request-scoped and separate from auxiliary/model output.
- [ ] Visual checks, if included, detect deliberate failures without treating normal nesting as a defect.
- [ ] Authentication, path boundaries and provider destinations match the deployment.
- [ ] CI tests meaningful functionality and required integration artifacts.
- [ ] Comparative evaluation supports every claimed improvement.
- [ ] README, demo, setup and incident status agree with the verified implementation.

## 8. Source references and limitations

Musegix links below are pinned to the inspected commit:

- [Committed gateway streaming](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/gateway/streaming.py)
- [Committed gateway routes](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/gateway/routes.py)
- [Engine integration plan](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/plan/03_PHASE_3_REAL_ENGINE_INTEGRATIONS.md)
- [MCP and render plan](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/plan/04_PHASE_4_MCP_AND_VISION_GATE.md)
- [Benchmark and release plan](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/plan/05_PHASE_5_BENCHMARKS_AND_RELEASE.md)
- [Security plan](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/plan/SECURITY_AND_GOVERNANCE.md)
- [Error register](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/plan/ERRORS_AND_LOGS.md)
- [Current baseline tests](https://github.com/vishalvermauts/Musegix/blob/d7a7ba9969666672ca8eabcab6bf93577d9beaca/tests/test_gateway.py)

External references inspected during the initial review follow default branches and may change:

- [Ysolveth reference inference and artifact contract](https://github.com/vishalvermauts/Ysolveth#how-to-run-inference)
- [PolyFabric supported setup and interfaces](https://github.com/vishalvermauts/PolyFabric#4-quickstart--installation)
- [Veylqora interfaces and memory lifecycle](https://github.com/vishalvermauts/Veylqora)
- [bolt.diy OpenAI-like provider](https://github.com/stackblitz-labs/bolt.diy/blob/main/app/lib/modules/llm/providers/openai-like.ts)
- [bolt.diy context selection](https://github.com/stackblitz-labs/bolt.diy/blob/main/app/lib/.server/llm/select-context.ts)
- [bolt.diy MCP service](https://github.com/stackblitz-labs/bolt.diy/blob/main/app/lib/services/mcpService.ts)

Published component performance numbers were not independently reproduced. The supplied review's hackathon cutoff, provider availability, model identifiers, sandbox health and hourly estimates remain unverified here. Do not treat those assertions as implementation facts.
