# Musegix Plan Review: Findings, Issues & Solutions

> **Reviewed:** `plan/00`–`05`, `plan/SECURITY_AND_GOVERNANCE.md`, `plan/ERRORS_AND_LOGS.md`, `gateway/*`, `tests/*`, `scripts/cloud_setup.sh`, `.github/workflows/ci.yml`, `README.md`, `.gitignore`, `.ai/*`
> **Date:** 2026-11-04 (AEDT) · **Deadline:** 2026-11-05 13:00 AEDT (2026-11-04 21:00 EST)
> **Scope note:** This reviews the Musegix plan and the code in this repo. The Ysolveth, PolyFabric and Veylqora repos were **not** inspected; their published numbers are not being questioned here.

---

## 0. Verdict

The rewrite fixed the worst things in the first plan. The `" role"` bug is gone, latencies no longer have constants added, Ysolveth now goes through real `onnxruntime`, and the "Zero Fake Numbers" invariant is stated clearly.

**The plan still breaks its own invariant in several places, and the core feature has no implementation yet:**

1. The gateway that runs **today** (`gateway/streaming.py`) prints a hardcoded banner (`3.2ms`, `780 vs 8450`, `90.8%`) and **never calls an LLM**.
2. The Phase 3 sections labelled "Real PolyFabric" and "Real Veylqora" never import PolyFabric or Veylqora. They are Python regex and `sqlite3` stand-ins.
3. All three Phase 4 MCP tools still return canned JSON.
4. The Phase 5 benchmark prints literal strings (`"<5ms"`, `"Real AST %"`) instead of measured values.
5. `ERRORS_AND_LOGS.md` marks `ERR_PLAN_MOCKED` as **RESOLVED**, which isn't true yet.

There are also several **bolt.diy integration traps** the plan doesn't cover (§3), and any of them can break the live demo. With less than a day left, scope has to be cut (§7).

---

## 1. What Improved (keep these)

| Area | Before | Now |
| :--- | :--- | :--- |
| SSE role key | `" role"` (broken) | `"role"`, also logged as `ERR_SSE_ROLE_WHITESPACE` |
| Latency padding | `+3.1`, `+1.4`, `+21.8` ms | Raw `perf_counter()` deltas |
| Token baseline | `max(raw, 9840)`, clamped to 14% | Computed from the actual pruned text |
| Ysolveth | Keyword heuristic | `onnxruntime` + `tokenizers` |
| Structure | One monolithic file | Phased plan, certification gates, security and error registers, CI |
| Repo hygiene | n/a | `.gitignore` covers secrets, `external/`, SQLite WAL files |

---

## 2. Critical Issues (fix before anything else)

### C1. The running gateway reports hardcoded telemetry and returns no code
**Where:** `gateway/streaming.py:18-23`, `plan/02_...md` §3 (`triage_info = {... "ms": 3.4}`, `prune_info = {... 840, 10290, 91.8}`)
**Problem:** The banner shows fixed numbers. The body is just "Musegix Gateway received your task…", so bolt.diy gets no `<boltArtifact>` and the editor and preview never change. The `# Upstream code generation stream here...` placeholder in Phase 2 is the product itself.
**Solution:** Implement the upstream proxy first and only show metrics that were measured. If an engine isn't wired yet, show `n/a` instead of a number.

```python
# gateway/streaming.py: core shape
async def stream_chat_completion(body: dict) -> AsyncGenerator[str, None]:
    t0 = time.perf_counter()
    route = triage(body)                 # real Ysolveth, or None if not loaded
    msgs, prune = prune_context(body)    # real measurement, or passthrough
    banner = render_banner(route, prune) # prints "n/a" for anything not measured
    yield sse_chunk(delta={"role": "assistant", "content": banner})

    client = clients[route.provider]
    try:
        upstream = await client.chat.completions.create(
            model=route.model, messages=msgs, stream=True,
            stream_options={"include_usage": True},          # real token counts
            **passthrough(body, ["temperature", "max_tokens", "tools", "tool_choice"]),
        )
        usage = None
        async for chunk in upstream:
            if chunk.usage: usage = chunk.usage
            if chunk.choices:
                # strip the upstream role so the banner chunk stays the only role delta
                yield f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"
    except Exception as e:
        yield sse_chunk(delta={"content": f"\n\n> ❌ Upstream error: {type(e).__name__}"},
                        finish_reason="stop")
    yield "data: [DONE]\n\n"
```

### C2. The Phase 3 "Real" PolyFabric and Veylqora engines are not the real engines
**Where:** `plan/03_...md` §2 and §3
**Problem:**
- `PolyFabricPruner` is the same regex and keyword-overlap logic as the old plan. It has no Tree-sitter, BM25, LanceDB or RRF, and it imports nothing from `components/PolyFabric`.
- `VeylqoraASTGuard` uses Python's `sqlite3` and hashes the **whole file body**, storing it as `symbol_name="file_root"`. It does no AST or symbol-level hashing and doesn't use the C++20 engine.
- The demo voiceover still says "Tree-sitter AST", "Asymmetric RRF" and "SHA-256 AST mismatch". Judges who read the code will see the gap.

**Solution:** For each engine, pick one option and say which in the README.
- **(a) Real binding.** Import PolyFabric's Python package (`components/PolyFabric/src/polyfabric`) and call its chunker and ranker. For Veylqora, call the C++ binary or library through `subprocess`, `pybind11` or its CLI. Check what each repo actually exposes **before** writing the plan.
- **(b) Honest stand-in.** Keep the Python code but call it what it is, for example "file-level SHA-256 staleness check (Veylqora-style)". Remove "AST", "C++20" and "RRF" from the banner and voiceover for that engine.

Option (b) is fine for a hackathon. Calling a stand-in the real engine is not.

### C3. The Phase 4 MCP tools are still entirely mocked
**Where:** `plan/04_...md` §1
**Problem:**
- `polyfabric_symbol_search` returns fixed `Header.tsx` and `useAuth.ts` results.
- `veylqora_memory_inspect` always returns `ACTIVE`.
- `ui_visual_render_gate` always returns `PASSED` with `42` elements and never launches Playwright.
- The demo (2:00–2:40) presents this as verification.

**Solution:** Implement the render gate for real. It's small:

```python
from playwright.async_api import async_playwright

@mcp.tool()
async def ui_visual_render_gate(preview_url: str) -> dict:
    t0 = time.perf_counter()
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(preview_url, wait_until="networkidle")
        boxes = await page.evaluate("""() => [...document.querySelectorAll(
            'button,a,input,nav,header,[role]')].map(e => {const r=e.getBoundingClientRect();
            return {tag:e.tagName, x:r.x, y:r.y, w:r.width, h:r.height}}).filter(b=>b.w&&b.h)""")
        overflow = await page.evaluate("document.documentElement.scrollWidth > innerWidth")
        await browser.close()
    collisions = count_overlaps(boxes)  # pairwise rectangle intersection
    return {"status": "PASSED" if not (errors or collisions or overflow) else "FAILED",
            "elements_checked": len(boxes), "collisions": collisions,
            "horizontal_overflow": overflow, "console_errors": errors[:10],
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
```

Add `playwright` to `requirements.txt` and run `playwright install --with-deps chromium` in `cloud_setup.sh`. Note that the WebContainer preview URL is **not** `localhost:5173`, which serves the bolt.diy IDE. Read the preview URL from bolt.diy's preview pane. It is usually a `*.webcontainer-api.io` / `local-credentialless` URL, and it only lives in the browser tab. Make sure Playwright can reach it, or render the generated project separately with `pnpm dev` in a sandbox.

If SAM 3.1 is dropped, remove it from every remaining doc and from the README.

### C4. The benchmark harness prints placeholders as results
**Where:** `plan/05_...md` §1
**Problem:**
- It prints `expected_model` instead of the **predicted** model, and the literal strings `"<5ms"` and `"Real AST %"`.
- It has 3 tasks, but the text says 10 and earlier material says 26 ("FarmWatch").
- It measures no accuracy.

**Solution:**
- Have the gateway also return telemetry as JSON. Either add an `X-Musegix-Telemetry` response header or add a `GET /v1/telemetry/last` endpoint so the benchmark doesn't scrape markdown.
- Compute per task: predicted tier vs. labelled tier (routing accuracy and a confusion matrix), triage p50/p95, raw vs. sent prompt tokens (from upstream `usage`), and end-to-end TTFT and total time.
- Run each task N≥5 times and report median and p95.
- Use **real bolt.diy payloads** as inputs (§3, B1), not one-line prompts. Pruning a 7-word prompt measures nothing.
- Pick one task count and use it everywhere.

### C5. The error register says the mocks are resolved
**Where:** `plan/ERRORS_AND_LOGS.md` §3
**Solution:** Reopen `ERR_PLAN_MOCKED` and list the remaining mocks: `streaming.py` banner, the non-streaming route, the MCP tools, the benchmark output, and the engine labels. Close it only when Gate 5.3 passes. Add a CI grep for known fake constants (`3.2`, `8450`, `90.8`, `"PASSED"` literals in MCP) as a cheap guard.

---

## 3. bolt.diy Integration Traps (High, these break the demo)

### B1. Capture real bolt.diy payloads before writing the pruner or guard
The plan assumes files arrive as `<boltAction type="file" filePath="...">` blocks inside messages. bolt.diy's actual request shape depends on version and settings:
- File context may sit in the **system prompt**, with Context Optimization on.
- User edits may be sent as a separate file-modifications block or diff.
- History may contain the model's own earlier `<boltArtifact>` outputs.

**Solution:** Make Phase 2 step 0 "log 5 real requests to `tests/fixtures/bolt_*.json`" (with secrets redacted). Write every regex and every unit test against those fixtures. Treat this as the highest-value hour in the plan.

### B2. bolt.diy sends auxiliary LLM calls through the same provider
bolt.diy also calls the selected model for **prompt enhancement**. With **Context Optimization** on, it also makes context-selection and chat-summary calls, and those parse the model's output for specific tags. All of these reach your gateway:
- A telemetry banner injected into the **enhancer** stream ends up inside the user's prompt box.
- Non-streaming calls hit `routes.py`'s mock `"Musegix gateway ready."` and break context selection and summaries.

**Solution:**
- Implement non-streaming as a real upstream passthrough. Delete the mock.
- Detect auxiliary calls by their distinctive system prompt or text, from the fixtures in B1, and **pass them through with no banner and no pruning**.
- Or disable Context Optimization for the demo and document that.

### B3. The user message carries a bolt.diy prefix and may not be a string
bolt.diy prepends `[Model: …]` and `[Provider: …]` lines to the user content, which you can confirm from the fixtures. Content can also be a **list** of parts when images are attached. The current code does `str(content)` on a list, so Ysolveth would classify `"[{'type': 'text', ...}]"`.
**Solution:** Normalize first by joining the `text` parts and stripping the `[Model:…]` and `[Provider:…]` header, then classify.

### B4. Tool calling must pass through for MCP to work
In bolt.diy, MCP tools reach the model as OpenAI `tools`, and the model answers with `tool_calls` deltas. The gateway currently drops `tools` and `tool_choice`, so MCP tools will **never** be invoked through Musegix.
**Solution:** Forward `tools` and `tool_choice`, stream `tool_calls` deltas unchanged, and confirm each upstream model (Baseten Muse Spark Open, Meta API models) supports function calling. Otherwise, route tool-bearing requests to a model that does.

### B5. WebContainers need cross-origin isolation on a secure origin
WebContainers need `SharedArrayBuffer`, which requires COOP/COEP on a **secure context** (`https` or `localhost`). Opening bolt.diy from a cloud sandbox as `http://<sandbox-ip>:5173` will load the IDE but **the preview will never boot**.
**Solution:** Reach the sandbox with an SSH or port-forward tunnel so the browser sees `http://localhost:5173`, or serve it over HTTPS. Test this in Phase 2, not on recording day.

### B6. Model id naming drift
The project is called **Musegix**, but the model id is still `musecontext-auto` in `routes.py`, `.env.local`, `config.py` and the tests. Rename it to `musegix-auto` everywhere in one commit.

---

## 4. Engine-Level Bugs in the Phase 3 Code

### E1. Ysolveth: the tokenizer path points to a directory
`config.py` sets `YSOLVETH_TOKENIZER_PATH = "components/Ysolveth"`, but `Tokenizer.from_file()` needs the **file** (`.../tokenizer.json`). It will raise at startup.

### E2. Ysolveth: no truncation, so long prompts will crash or blow the latency budget
bolt.diy prompts can be thousands of tokens. Without truncation, the encoder gets a sequence longer than its max positions (often 512) and fails.
**Solution:** Call `tokenizer.enable_truncation(max_length=256)` (or whatever the model was trained with) and classify only the normalized latest user message.

### E3. Ysolveth: input and output contract unverified
The plan assumes the inputs are `input_ids` and `attention_mask`, that `outputs[0]` is 3-class logits, and that the label order is `[TRIVIAL, MODERATE, HARD]`. A file named `encoder_int8.onnx` may output **embeddings**, needing a separate head, and BERT-style graphs often also need `token_type_ids`.
**Solution:** Before writing the wrapper, inspect `session.get_inputs()` and `session.get_outputs()` and read the label map from the Ysolveth repo. Build the feed dict from `get_inputs()` names.

### E4. Ysolveth: load once and warm up
Create the session at FastAPI startup (`lifespan`) and run one warm-up inference. Otherwise the first request's latency includes model load. Report the warm p50, which is honest and still fast. Set `intra_op_num_threads` explicitly so results are reproducible.

### E5. Ysolveth: fail-closed vs. fail-open
`SECURITY_AND_GOVERNANCE.md` Invariant 4 says *fail-closed* ("return clean HTTP error"), but `ERRORS_AND_LOGS.md` `ERR_ENG_*` says *fall back to the default model*. Pick one: falling back to MODERATE with a banner note is better for a demo. Make both docs agree.

### E6. PolyFabric pruner: every file matches, so nothing gets pruned
The new version dropped the `len(term) > 2` filter, so terms like `a`, `to`, `in` and `the` match **every** body. `matches >= 1` is then always true and nothing is pruned.
**Solution:** Use a stopword list plus `len >= 3`, or better, use PolyFabric's actual BM25 ranking: keep the top-K files or symbols by score and stub the rest.

### E7. PolyFabric pruner: it rewrites conversation history
It also rewrites the **model's own earlier assistant messages**, which contain prior `<boltArtifact>` output. That can confuse the model about what it already wrote.
**Solution:** Prune only the current file-context block, located from the B1 fixtures, and leave earlier assistant turns alone or truncate them separately.

### E8. Token counts are estimates labelled as real
`chars // 4` is an estimate, but Gate 3.3 says "actual token lengths".
**Solution:** Use the upstream `usage.prompt_tokens` (via `stream_options.include_usage`) for the *sent* count. For the *raw* count, either tokenize with the same tokenizer or label it "≈ tokens (chars/4)" in the banner.

### E9. Veylqora guard flags stale files on every turn
Each request re-sends the whole history. The guard walks messages **chronologically**, so an old version of `App.tsx` in history is compared with the stored newest digest, which flags stale, and then the newest version flags stale again. The badge fires on every turn and the "stale memory" demo becomes meaningless.
**Solution:** Hash only the **current workspace snapshot**, the latest file context, once per request. Compare against the snapshot from the **previous request in the same chat**. Report files whose digest changed **and** that are referenced in recent assistant turns. That is what "stale memory" actually means.

### E10. Veylqora guard: global state across chats
`AST_DIGEST_STORE` and the `:memory:` SQLite DB are shared by every chat. Opening a second chat with different files produces false stale hits.
**Solution:** Key by chat id. bolt.diy doesn't send one in the OpenAI body, so derive one, for example a hash of the first user message plus the system prompt, or add a custom header in bolt.diy's provider config if it supports one.

### E11. Veylqora guard: WAL on `:memory:` is a no-op
`PRAGMA journal_mode=WAL` on `:memory:` silently returns `memory`, so "writes to SQLite WAL" (Gate 3.4) is false.
**Solution:** Use a file DB under a gitignored `data/` folder, or drop the WAL claim for the Python stand-in.

### E12. Veylqora guard: digest is file-level, not AST-level
To make the "AST" claim true, use `tree-sitter` with `tree-sitter-typescript` and `tree-sitter-javascript` to extract top-level function and component nodes. Hash each body and report `fileName::symbolName` changes. Expect about 40 lines of Python if Veylqora's own extractor can't be reused. Otherwise, stop saying "AST".

---

## 5. Gateway, Infra & CI Issues (Medium)

| # | Issue | Where | Solution |
| :--- | :--- | :--- | :--- |
| M1 | No upstream client config: Meta API base URL and Baseten client are gone from `config.py`. Model ids `muse-spark-1.3`, `muse-wonder-1.0` and `meta-models/muse-spark-open-1026` are unverified. | `plan/01` §2 | Add `META_BASE_URL` and `BASETEN_BASE_URL` to settings. Make a single test call to each model **today** and record the exact ids in the SSOT. `.ai/CONSTRAINTS.md` #1 ("No Guessing APIs") already requires this. |
| M2 | Gateway binds `0.0.0.0` with **no auth**. `OPENAI_LIKE_API_KEY=musegix-local-key` is never checked, so anyone who can reach port 8000 spends your Meta and Baseten quota. | `routes.py` | Check `Authorization: Bearer <MUSEGIX_GATEWAY_KEY>` and bind to `127.0.0.1` inside the sandbox. |
| M3 | `allow_origins=["*"]` combined with `allow_credentials=True` is overly permissive and not needed. bolt.diy calls the provider server-side. | `app.py` | Restrict to `http://localhost:5173` or remove CORS entirely. |
| M4 | `config.py`, `schemas.py` and `gateway/engines/` are listed in the plan but don't exist. The real `cloud_setup.sh` differs from the plan version: no Node/pnpm and no component clones, so Phase 3 paths won't exist. | `plan/01`, `scripts/` | Keep one source of truth. Update the script and regenerate the plan snippet from it, or link to the file instead of inlining it. |
| M5 | `components/` is **not** in `.gitignore`. Cloning the three repos there and running `git add .` creates nested gitlinks or vendored history, the eligibility problem the clean-slate design is meant to avoid. `.gitignore` lists `*_repo/`, which nothing uses. | `.gitignore` | Add `components/`. Remove the unused `*_repo/` entries. |
| M6 | Gate 1.5 says "**master** branch", but the repo is on `main` and CI triggers on `main`. | `plan/01` §4 | Change it to `main`. |
| M7 | Gate 3.5 runs engine tests in CI, but CI has no ONNX weights and no component repos. Tests will fail or have to be skipped. | `ci.yml` | Add a CI step that clones components with `--depth 1`, or download the ONNX artifact. Use `pytest.mark.skipif(not model_path.exists())` for local runs. Commit small bolt.diy payload fixtures (B1) so the pruner and guard tests run anywhere. |
| M8 | Tests cover only `/` and `/v1/models`. Nothing covers SSE format, banner-then-content order, `[DONE]`, the first chunk's `role`, or the error path. | `tests/` | Add an SSE contract test that parses every `data:` line as JSON, asserts exactly one `role` delta, a final `[DONE]`, and no `" role"` keys, using a mocked upstream (`respx` or a fake client). That is a mock **in tests**, which is fine. |
| M9 | No client-disconnect, timeout or cancellation handling. A user pressing Stop in bolt.diy leaves the upstream stream running and spending tokens. | `streaming.py` | Use `await request.is_disconnected()` in the loop, `httpx.Timeout(connect=5, read=120)` on clients, and close the upstream stream in `finally`. |
| M10 | The "secret redaction in SSE buffer" and "path-traversal guard" in the Security doc are not implemented anywhere. The Invariant 3 regex `filePath="..*"` would also reject legitimate dotfiles such as `.env.example` and `.gitignore`. | `SECURITY_AND_GOVERNANCE.md` | Either implement them (match `\.\./` or a leading `/` as **whole path segments**, and redact with key-specific patterns) or move them to a "Future work" section. Unimplemented security claims are a credibility risk. |
| M11 | `README.md` links a `LICENSE` that doesn't exist and claims "real, verified" tools and "85%+" savings before any measurement. | `README.md` | Add the Apache-2.0 `LICENSE`. Fill in numbers only from the Phase 5 run, with the date and commit hash. |
| M12 | `.ai/` contains template boilerplate (`docs/backend.md` points to `backend/`, which doesn't exist; `CONSTRAINTS.md` mentions "Lovable project history"). | `.ai/` | Trim or fix it. Judges browse the repo. |
| M13 | `requirements.txt` has no upper bounds. `mcp>=1.0.0` and `openai>=1.14.0` have had breaking changes. `playwright` and `tree-sitter` are missing for Phases 3 and 4. | `requirements.txt` | Pin exact versions after the first working install (`pip freeze`). Split out `requirements-dev.txt`. |
| M14 | Line endings: git warns that LF will be replaced by CRLF on every file. `cloud_setup.sh` with CRLF fails in Linux with `bash\r: not found`. | repo | Add `.gitattributes` with `* text=auto eol=lf` and `*.sh text eol=lf`. |
| M15 | The plan relies entirely on `sbx --cloud` sandboxes ("Zero Local Heavy Lifting"). If the sandbox or its port-forwarding fails near the deadline, there is no fallback. | `plan/00` §2 | Document a local fallback: gateway plus bolt.diy run fine on a laptop. Treat the invariant as a preference, not a hard rule, on demo day. |

---

## 6. Demo Script Corrections

| Time | Current claim | Problem | Replace with |
| :--- | :--- | :--- | :--- |
| 0:30–1:15 | "slashing tokens by over 85%" | Not measured yet. E6 means current pruning may be 0%. | "PolyFabric cut this prompt from **X** to **Y** tokens", using the banner's live number. |
| 0:30–1:15 | "routing to Muse Spark Open on Baseten" | Only true if Ysolveth actually predicts TRIVIAL for that prompt. | Pick the demo prompt **after** testing it, and read the tier from the banner. |
| 1:15–2:00 | "catches the SHA-256 AST mismatch in 2ms" | It's a file-level digest (E12), and it fires every turn (E9). | Fix E9. Then say "file fingerprint" or implement symbol-level hashing. |
| 2:00–2:40 | "ensuring zero layout collisions" | The tool is mocked (C3). | Show the real Playwright output, including a deliberate failing case first. A FAILED→fix→PASSED sequence is a much stronger demo. |
| 2:40–3:00 | "passing CI badges and benchmark reports" | The benchmark doesn't exist yet. | Show the generated `benchmarks/results.md` with its commit hash. |

---

## 7. Prioritized Action Plan (time-boxed to the deadline)

Each phase can take hours, so cut scope to an **honest MVP** and add extras only if time allows.

| Priority | Task | Est. | Done when |
| :--- | :--- | :--- | :--- |
| **P0** | Verify Meta API and Baseten base URLs, model ids and function-calling support with real calls (M1) | 30m | Exact ids recorded in the SSOT |
| **P0** | Real upstream streaming proxy plus a real non-streaming passthrough (C1, B2) | 1h | bolt.diy builds a counter app through the gateway |
| **P0** | Capture 5 real bolt.diy payloads as fixtures (B1). Normalize the user message (B3). Tunnel to localhost (B5). | 45m | Fixtures committed; WebContainer preview boots |
| **P0** | Ysolveth real wiring (E1–E4), loaded at startup | 1h | Banner shows the real tier and warm latency; 10-prompt test passes |
| **P1** | Pruner: real top-K ranking (PolyFabric's BM25, or an honest stand-in), only on the current file context, with real token counts (E6–E8) | 1.5h | Banner shows the measured reduction on fixture payloads |
| **P1** | Staleness guard: snapshot diff per chat (E9–E11) | 1h | Badge fires only after a manual edit |
| **P1** | Auth, bind to localhost, client-disconnect handling (M2, M9) | 30m | Unauthorized request returns 401 |
| **P2** | Real Playwright render gate plus tool-call passthrough (C3, B4) | 1.5h | Tool runs from bolt.diy chat |
| **P2** | Benchmark with JSON telemetry, N≥5 runs, real payloads (C4) | 1h | `benchmarks/results.md` generated |
| **P3** | README numbers, LICENSE, `.gitattributes`, `.gitignore` `components/`, rename the model id, clean up `.ai/` (M5, M6, M11, M12, M14, B6) | 30m | Repo looks clean to a judge |
| **P3** | Record the demo using live numbers (§6) | 1h | Video submitted **before** 13:00 AEDT |

**Cut line:** If P2 isn't done by roughly 08:00 AEDT tomorrow, drop the MCP and render-gate segment from the video and spend that time on a smooth P0/P1 demo. An honest, working demo with three integrated engines beats a five-feature demo with mocks.

---

## 8. Quick Checklist

- [ ] No literal metric values in `gateway/` (grep in CI)
- [ ] Banner shows `n/a` for any engine that isn't wired
- [ ] Every "Real …" heading in `plan/03` either imports the real repo or is renamed
- [ ] All MCP tools do real work or are removed from the demo
- [ ] Benchmark prints predicted values and measured timings, never expected or literal strings
- [ ] `ERR_PLAN_MOCKED` reopened until Gate 5.3 passes
- [ ] bolt.diy auxiliary calls (enhancer, context optimization) pass through untouched
- [ ] `tools` and `tool_calls` pass through
- [ ] Gateway requires a bearer key and binds to localhost
- [ ] `components/` gitignored; `.gitattributes` forces LF
- [ ] Model id `musegix-auto` everywhere; branch `main` everywhere
- [ ] README numbers come from `benchmarks/results.md` with a commit hash
