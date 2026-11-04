"""Ysolveth ONNX Classifier Engine for System One prompt triage and intelligent model routing.

Performs deterministic, sub-5ms CPU mathematical inference:
1. Tokenization with max_length=256 truncation.
2. Quantized int8 ONNX forward pass yielding last_hidden_state [1, seq_len, 384].
3. Attention-mask mean pooling: sum(last_hidden * mask) / sum(mask).
4. L2 normalization: pooled / ||pooled||_2.
5. Calibrated linear projection: dot(weights, normalized) + biases.
6. Temperature scaling: logits / T.
7. Numerically stable softmax producing calibrated tier probabilities.
8. Provider and target model routing.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_COMPONENTS_DIR = PROJECT_ROOT / "components" / "Ysolveth"


def _resolve_component_path(custom_path: Optional[str], filename: str) -> str:
    """Resolve file path across explicit args, env vars, project structure, or cwd."""
    if custom_path and os.path.exists(custom_path):
        return os.path.abspath(custom_path)

    env_var_key = f"YSOLVETH_{filename.upper().replace('.', '_')}"
    if os.environ.get(env_var_key) and os.path.exists(os.environ[env_var_key]):
        return os.path.abspath(os.environ[env_var_key])

    cand_dir = DEFAULT_COMPONENTS_DIR / filename
    if cand_dir.exists():
        return str(cand_dir)

    cand_cwd = Path.cwd() / "components" / "Ysolveth" / filename
    if cand_cwd.exists():
        return str(cand_cwd)

    if custom_path:
        return os.path.abspath(custom_path)
    return str(cand_dir)


class YsolvethClassifier:
    """Production ONNX Runtime classifier for prompt complexity triage."""

    ROUTING_MAP = {
        "hard": ("meta", "muse-wonder-1.0"),
        "moderate": ("meta", "muse-spark-1.3"),
        "trivial": ("baseten", "meta-models/muse-spark-open-1026"),
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        tokenizer_path: Optional[str] = None,
        head_config_path: Optional[str] = None,
        num_threads: int = 2,
    ) -> None:
        """Initialize ONNX session, Tokenizer, and calibrated classification head."""
        resolved_model = _resolve_component_path(model_path, "encoder_int8.onnx")
        resolved_tokenizer = _resolve_component_path(tokenizer_path, "tokenizer.json")
        resolved_head = _resolve_component_path(head_config_path, "head_config.json")

        if not os.path.exists(resolved_model):
            raise FileNotFoundError(f"Ysolveth ONNX model not found at: {resolved_model}")
        if not os.path.exists(resolved_tokenizer):
            raise FileNotFoundError(f"Ysolveth tokenizer not found at: {resolved_tokenizer}")
        if not os.path.exists(resolved_head):
            raise FileNotFoundError(f"Ysolveth head config not found at: {resolved_head}")

        # 1. Load ONNX session with CPUExecutionProvider and optimized thread count
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = num_threads
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(
            resolved_model, sess_options=opts, providers=["CPUExecutionProvider"]
        )

        # 2. Load Tokenizer with max_length=256 truncation
        self.tokenizer = Tokenizer.from_file(resolved_tokenizer)
        self.tokenizer.enable_truncation(max_length=256)

        # 3. Load Calibrated Linear Head Configuration
        with open(resolved_head, "r", encoding="utf-8") as f:
            head_config = json.load(f)

        self.labels = head_config.get("difficulty_labels", ["hard", "moderate", "trivial"])
        self.weights = np.array(head_config["weights"], dtype=np.float32)  # Shape [3, 384]
        biases_raw = head_config.get("biases", head_config.get("bias"))
        self.biases = np.array(biases_raw, dtype=np.float32)  # Shape [3]
        self.temperature = float(head_config.get("temperature", 0.2842))

        # 4. Warm up model once upon initialization to eliminate cold-start overhead
        self.classify("warmup ping")

    def classify(self, prompt: str) -> Dict[str, Any]:
        """Perform verified mathematical classification and model routing for a prompt.

        Args:
            prompt: User coding request string.

        Returns:
            Dictionary with tier, confidence, latency_ms, target_model, provider, and probabilities.
        """
        t0 = time.perf_counter()

        # Step 1: Tokenize with max_length truncation
        encoded = self.tokenizer.encode(prompt or "")
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        # Step 2: ONNX forward pass -> last_hidden_state [1, seq_len, 384]
        outputs = self.session.run(
            ["last_hidden_state"],
            {"input_ids": input_ids, "attention_mask": attention_mask},
        )
        last_hidden = outputs[0]

        # Step 3: Attention-Mask Mean Pooling: sum(last_hidden * mask) / sum(mask)
        mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
        sum_embeddings = np.sum(last_hidden * mask_expanded, axis=1)
        sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        mean_pooled = (sum_embeddings / sum_mask)[0]  # Shape [384]

        # Step 4: L2 Normalization: mean_pooled / ||mean_pooled||_2
        norm = np.linalg.norm(mean_pooled)
        normalized = mean_pooled / max(norm, 1e-12)

        # Step 5: Linear Projection: logits = dot(weights, normalized) + biases
        logits = np.dot(self.weights, normalized) + self.biases

        # Step 6: Temperature Scaling: scaled = logits / temperature
        scaled_logits = logits / self.temperature

        # Step 7: Numerically stable softmax
        exp_logits = np.exp(scaled_logits - np.max(scaled_logits))
        probs = exp_logits / np.sum(exp_logits)
        pred_idx = int(np.argmax(probs))
        label = self.labels[pred_idx]

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Step 8: Route resolution
        # 'hard' -> ('meta', 'muse-wonder-1.0')
        # 'moderate' -> ('meta', 'muse-spark-1.3')
        # 'trivial' -> ('baseten', 'meta-models/muse-spark-open-1026')
        provider, target_model = self.ROUTING_MAP.get(
            label, ("baseten", "meta-models/muse-spark-open-1026")
        )

        return {
            "tier": label.upper(),
            "label": label,
            "confidence": float(probs[pred_idx]),
            "latency_ms": elapsed_ms,
            "target_model": target_model,
            "provider": provider,
            "probabilities": {
                self.labels[i]: float(probs[i]) for i in range(len(self.labels))
            },
        }

    def route(self, prompt: str) -> Tuple[str, str]:
        """Convenience helper returning (provider, target_model) tuple."""
        res = self.classify(prompt)
        return res["provider"], res["target_model"]
