# Phase 3: Real Engine Integrations (Ysolveth + PolyFabric + Veylqora)

> **Status:** Queued (Follows Phase 2)  
> **Objective:** Integrate verified mathematical inference for Ysolveth (<5ms CPU ONNX + calibrated linear head), implement AST background context pruning via PolyFabric, and anchor Veylqora memory invalidations to AST symbol fingerprints.

---

## 1. Engine 1: Verified Ysolveth Pipeline (ONNX + Calibrated Head)

### Verified Architecture
- **ONNX Graph:** `components/Ysolveth/encoder_int8.onnx`
  - Input: `input_ids` `[1, seq_len]`, `attention_mask` `[1, seq_len]` (truncated to 256 tokens).
  - Output: `last_hidden_state` `[1, seq_len, 384]`.
- **Attention-Mask Mean Pooling:**
  $$\mathbf{u} = \frac{\sum_{i=1}^L \mathbf{h}_i \cdot m_i}{\sum_{i=1}^L m_i}$$
- **L2 Normalization:**
  $$\mathbf{e} = \frac{\mathbf{u}}{\|\mathbf{u}\|_2}$$
- **Calibrated Linear Head (`components/Ysolveth/head_config.json`):**
  - Linear projection: $\mathbf{z} = \mathbf{e} W^T + \mathbf{b}$ (where $W$ is $3 \times 384$, $\mathbf{b}$ is $[0.2398, -0.3032, 0.0634]$).
  - Temperature Scaling: $\mathbf{s} = \frac{\mathbf{z}}{T}$ (where $T = 0.2842$).
  - Softmax $\to$ Class probabilities for `['hard', 'moderate', 'trivial']`.

### Implementation (`gateway/engines/ysolveth_classifier.py`)
```python
import json
import time
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

class YsolvethClassifier:
    def __init__(self, model_path: str, tokenizer_path: str, head_config_path: str):
        # Load ONNX session with CPUExecutionProvider
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])
        
        # Load HuggingFace tokenizer with truncation
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.tokenizer.enable_truncation(max_length=256)
        
        # Load Calibrated Head
        with open(head_config_path, "r", encoding="utf-8") as f:
            head = json.load(f)
        self.labels = head["difficulty_labels"]  # ['hard', 'moderate', 'trivial']
        self.weights = np.array(head["weights"], dtype=np.float32)  # [3, 384]
        self.biases = np.array(head["biases"], dtype=np.float32)    # [3]
        self.temperature = float(head.get("temperature", 0.2842))

        # Warm-up pass
        self.classify("warmup ping")

    def classify(self, prompt: str) -> dict:
        t0 = time.perf_counter()
        
        # 1. Tokenize
        encoded = self.tokenizer.encode(prompt)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)
        
        # 2. ONNX Forward Pass
        outputs = self.session.run(
            ["last_hidden_state"],
            {"input_ids": input_ids, "attention_mask": attention_mask}
        )
        last_hidden = outputs[0]  # [1, seq_len, 384]
        
        # 3. Attention-Mask Mean Pooling
        mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
        sum_embeddings = np.sum(last_hidden * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = (sum_embeddings / sum_mask)[0]  # [384]
        
        # 4. L2 Normalization
        norm = np.linalg.norm(mean_pooled)
        normalized = mean_pooled / max(norm, 1e-12)
        
        # 5. Linear Projection + Temperature Scaling
        logits = np.dot(self.weights, normalized) + self.biases
        scaled_logits = logits / self.temperature
        
        # 6. Softmax
        exp_l = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_l / np.sum(exp_l)
        pred_idx = int(np.argmax(probs))
        label = self.labels[pred_idx]
        
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        
        # Routing policy
        if label == "hard":
            target_model = "muse-wonder-1.0"
            provider = "meta"
        elif label == "moderate":
            target_model = "muse-spark-1.3"
            provider = "meta"
        else:
            target_model = "meta-models/muse-spark-open-1026"
            provider = "baseten"
            
        return {
            "tier": label.upper(),
            "confidence": float(probs[pred_idx]),
            "latency_ms": elapsed_ms,
            "target_model": target_model,
            "provider": provider,
            "probabilities": {self.labels[i]: float(probs[i]) for i in range(len(self.labels))}
        }
```

---

## 2. Engine 2: PolyFabric Safe Context Pruner

### Design Invariant
- **Target File Preservation:** The file explicitly being targeted by the user's prompt is NEVER pruned. It retains 100% full content inside `<boltAction type="file" filePath="...">`.
- **Background File Compression:** Unrelated background files are reduced to AST symbol signatures (functions, classes, interfaces).
- **True Token Counts:** Measured using character approximation or upstream provider `usage.prompt_tokens`.

---

## 3. Engine 3: Veylqora Evidence-Anchored Memory Guard

### Design Invariant
- **Snapshot Diff per Chat:** State is isolated by `workspace_id` or session hash.
- **Evidence Anchor:** Memories are linked to specific function/symbol fingerprints.
- Only when an existing function signature changes does Veylqora flag `SUSPECTED_STALE`.

---

## 4. Phase 3 Certification Gate Checklist

- [ ] **Gate 3.1:** Ysolveth mean-pooling and linear projection executes against real `head_config.json` weights in `<5 ms` on CPU.
- [ ] **Gate 3.2:** Ysolveth test suite outputs calibrated probabilities across 10 sample coding prompts.
- [ ] **Gate 3.3:** PolyFabric pruner preserves full contents of the edit target file while stubbing background files.
- [ ] **Gate 3.4:** Token calculations reflect measured counts without hardcoded multipliers.
- [ ] **Gate 3.5:** Veylqora flags stale state only when cited symbol fingerprints mutate.
