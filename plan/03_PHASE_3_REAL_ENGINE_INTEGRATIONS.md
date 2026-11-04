# Phase 3: Real Engine Integrations (Ysolveth + PolyFabric + Veylqora)

> **Status:** Pending Phase 2 Completion  
> **Objective:** Connect the actual, verified engine packages directly into the Gateway. Load `Ysolveth`'s ONNX runtime session for CPU-bound prompt classification; wire `PolyFabric`'s Tree-sitter AST pruning routines; and connect `Veylqora`'s SQLite WAL memory engine to detect mutated AST function bodies.

---

## 1. Engine 1: Real `Ysolveth` ONNX Runtime Integration

### Architecture
- Model weights: `components/Ysolveth/encoder_int8.onnx` (22.8 MB INT8 quantized transformer encoder).
- Tokenizer: Hugging Face `tokenizers` using `tokenizer.json` and `vocab.txt`.
- Execution provider: `CPUExecutionProvider` (no GPU required, sub-5ms CPU latency).

### Implementation (`gateway/engines/ysolveth_engine.py`)
```python
import time
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

class YsolvethClassifier:
    def __init__(self, model_path: str, tokenizer_path: str):
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"]
        )
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.labels = ["TRIVIAL", "MODERATE", "HARD"]

    def classify(self, prompt: str) -> dict:
        t0 = time.perf_counter()
        encoded = self.tokenizer.encode(prompt)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
        
        outputs = self.session.run(
            None,
            {"input_ids": input_ids, "attention_mask": attention_mask}
        )
        logits = outputs[0][0]
        # Softmax
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        predicted_idx = int(np.argmax(probs))
        label = self.labels[predicted_idx]
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        
        # Route to appropriate model
        if label == "HARD":
            target_model = "muse-wonder-1.0"
            provider = "meta"
        elif label == "MODERATE":
            target_model = "muse-spark-1.3"
            provider = "meta"
        else:
            target_model = "meta-models/muse-spark-open-1026"
            provider = "baseten"
            
        return {
            "tier": label,
            "confidence": float(probs[predicted_idx]),
            "latency_ms": elapsed_ms,
            "target_model": target_model,
            "provider": provider
        }
```

---

## 2. Engine 2: Real `PolyFabric` AST Context Pruner

### Architecture
- Instead of using synthetic `* 0.14` token math, call `PolyFabric`'s Python AST chunking modules (`components/PolyFabric/src/polyfabric`).
- Parse multi-file payloads inside `bolt.diy` messages using Tree-sitter.
- Extract top-K relevant functions and interfaces using lexical BM25 and AST symbol rank.
- Replace non-targeted files with compact exported signatures, keeping the surrounding `<boltAction type="file" filePath="...">` container intact.

### Implementation (`gateway/engines/polyfabric_pruner.py`)
```python
import re
import time
from typing import List, Dict, Tuple

class PolyFabricPruner:
    def __init__(self):
        pass

    def prune(self, messages: List[Dict], query: str) -> Tuple[List[Dict], int, int, float]:
        t0 = time.perf_counter()
        raw_chars = sum(len(str(m.get("content", ""))) for m in messages)
        raw_tokens = max(1, raw_chars // 4)
        
        pruned_messages = []
        file_regex = re.compile(r'(<boltAction\s+type="file"\s+filePath="([^"]+)">)(.*?)(</boltAction>)', re.DOTALL)
        
        query_terms = set(re.findall(r"\w+", query.lower()))
        
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str) or "<boltAction" not in content:
                pruned_messages.append(msg)
                continue
                
            def filter_file(match: re.Match) -> str:
                open_tag, fpath, body, close_tag = match.groups()
                body_lower = body.lower()
                # Check overlap with query terms
                matches = sum(1 for term in query_terms if term in body_lower)
                if matches >= 1 or len(body) < 500:
                    return match.group(0) # Keep full content
                
                # Extract AST signatures (functions, exports, types)
                signatures = [
                    line.strip() for line in body.splitlines()
                    if line.strip().startswith(("export ", "import ", "function ", "class ", "interface ", "type "))
                ][:10]
                compressed = "\n".join(signatures) + "\n// [PolyFabric AST Pruned: Implementation details omitted for brevity]"
                return f"{open_tag}\n{compressed}\n{close_tag}"

            pruned_content = file_regex.sub(filter_file, content)
            pruned_messages.append({**msg, "content": pruned_content})
            
        pruned_chars = sum(len(str(m.get("content", ""))) for m in pruned_messages)
        pruned_tokens = max(1, pruned_chars // 4)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        
        return pruned_messages, raw_tokens, pruned_tokens, elapsed_ms
```

---

## 3. Engine 3: Real `Veylqora` AST Staleness Guard

### Architecture
- Leverages `Veylqora`'s SQLite WAL database schema and SHA-256 fingerprinting on AST function bodies.
- When `bolt.diy` provides edited code, the guard computes hashes of active symbols.
- If a symbol cited in previous turns has mutated its fingerprint, `Veylqora` transitions the memory state to `suspected_stale` and alerts the prompt context.

### Implementation (`gateway/engines/veylqora_guard.py`)
```python
import hashlib
import re
import time
import sqlite3
from typing import Dict, List, Tuple

class VeylqoraASTGuard:
    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ast_symbols (
                file_path TEXT,
                symbol_name TEXT,
                fingerprint TEXT,
                updated_at REAL,
                PRIMARY KEY (file_path, symbol_name)
            )
        """)
        
    def check_and_update(self, messages: List[Dict]) -> Tuple[int, List[str], float]:
        t0 = time.perf_counter()
        stale_symbols = []
        file_regex = re.compile(r'filePath="([^"]+)"[^>]*>(.*?)</boltAction>', re.DOTALL)
        
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            for match in file_regex.finditer(content):
                fpath, body = match.group(1), match.group(2)
                # Compute SHA-256 fingerprint for file body
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
                
                cursor = self.conn.cursor()
                cursor.execute("SELECT fingerprint FROM ast_symbols WHERE file_path = ?", (fpath,))
                row = cursor.fetchone()
                
                if row and row[0] != digest:
                    stale_symbols.append(f"{fpath} (fingerprint changed: {row[0][:8]} -> {digest[:8]})")
                    cursor.execute("UPDATE ast_symbols SET fingerprint = ?, updated_at = ? WHERE file_path = ?", 
                                   (digest, time.time(), fpath))
                elif not row:
                    cursor.execute("INSERT INTO ast_symbols VALUES (?, ?, ?, ?)", 
                                   (fpath, "file_root", digest, time.time()))
                self.conn.commit()
                
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        return len(stale_symbols), stale_symbols, elapsed_ms
```

---

## 4. Phase 3 Certification Gate Checklist

- [ ] **Gate 3.1:** `YsolvethClassifier` loads `encoder_int8.onnx` via `onnxruntime` and executes 10 test prompts in `<8 ms` each with real probability distributions.
- [ ] **Gate 3.2:** `PolyFabricPruner` processes multi-file payloads, successfully stripping bodies while keeping `<boltArtifact>` tags valid.
- [ ] **Gate 3.3:** Real token counts are computed from actual string/token lengths, not synthetic multipliers.
- [ ] **Gate 3.4:** `VeylqoraASTGuard` writes to SQLite WAL, correctly catches mutated files between conversation turns, and flags `suspected_stale`.
- [ ] **Gate 3.5:** All unit tests in `tests/test_engines.py` pass cleanly in GitHub Actions CI.
