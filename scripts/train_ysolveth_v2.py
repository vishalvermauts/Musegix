"""Retrain the Ysolveth head (frozen MiniLM ONNX encoder + logistic regression). Run in the sandbox.

Usage: python train_ysolveth_v2.py labels_v2.jsonl <encoder_dir> <out_dir>
Writes head_config.v2.json (same format as v1) and reports/ysolveth_v2.md.
"""
import json, os, sys, random
import numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix

labels_path, enc_dir, out_dir = sys.argv[1:4]
LABELS = ["hard", "moderate", "trivial"]
rows = [json.loads(l) for l in open(labels_path, encoding="utf-8")]

tok = Tokenizer.from_file(os.path.join(enc_dir, "tokenizer.json"))
tok.enable_truncation(max_length=256)
sess = ort.InferenceSession(os.path.join(enc_dir, "encoder_int8.onnx"), providers=["CPUExecutionProvider"])


def embed(text):
    enc = tok.encode(text or "")
    ids = np.array([enc.ids], dtype=np.int64)
    mask = np.array([enc.attention_mask], dtype=np.int64)
    hidden = sess.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask})[0]
    m = np.expand_dims(mask, -1).astype(np.float32)
    pooled = (np.sum(hidden * m, axis=1) / np.clip(m.sum(axis=1), 1e-9, None))[0]
    return pooled / max(np.linalg.norm(pooled), 1e-12)


X = np.stack([embed(r["prompt"]) for r in rows])
y = np.array([LABELS.index(r["label"]) for r in rows])

# Split by task so no prompt appears on both sides; stratify by label with a fixed seed.
rng = random.Random(42)
train_idx, test_idx = [], []
for c in range(len(LABELS)):
    idx = [i for i in range(len(rows)) if y[i] == c]
    rng.shuffle(idx)
    k = max(1, int(round(len(idx) * 0.2))) if len(idx) > 1 else 0
    test_idx += idx[:k]
    train_idx += idx[k:]

clf = LogisticRegression(C=1.5, max_iter=500, class_weight="balanced", random_state=42)
clf.fit(X[train_idx], y[train_idx])
pred = clf.predict(X[test_idx])
report = classification_report(y[test_idx], pred, labels=[0, 1, 2], target_names=LABELS, zero_division=0)
cm = confusion_matrix(y[test_idx], pred, labels=[0, 1, 2])

# Re-order coefficients to the v1 layout: rows = [hard, moderate, trivial].
head = {
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "version": "1.4.0-mbpp-outcome",
    "difficulty_labels": LABELS,
    "label_to_idx": {"hard": 0, "moderate": 1, "trivial": 2},
    "hidden_size": 384,
    "num_classes": 3,
    "weights": clf.coef_.tolist(),
    "biases": clf.intercept_.tolist(),
    "temperature": 0.2842,
    "epsilon_threshold": 0.1,
    "training_metadata": {
        "library": "scikit-learn", "model_type": "LogisticRegression", "solver": "lbfgs",
        "C": 1.5, "class_weight": "balanced", "seed": 42,
        "train_samples": len(train_idx), "test_samples": len(test_idx),
        "label_source": "MBPP+ outcome labels (cheap/mid/strong pass)",
    },
}
os.makedirs(out_dir, exist_ok=True)
json.dump(head, open(os.path.join(out_dir, "head_config.v2.json"), "w"), indent=2)
os.makedirs("reports", exist_ok=True)
with open("reports/ysolveth_v2.md", "w", encoding="utf-8") as f:
    f.write("# Ysolveth head v2 (MBPP+ outcome labels)\n\n")
    f.write(f"Train {len(train_idx)} / test {len(test_idx)} (split by prompt, stratified, seed 42).\n\n")
    f.write("```\n" + report + "\n```\n\nConfusion matrix (rows = true hard/moderate/trivial):\n\n```\n" + str(cm) + "\n```\n")
print(report)
print(cm)
