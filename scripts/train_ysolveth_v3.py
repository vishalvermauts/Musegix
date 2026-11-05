"""Retrain the Ysolveth head v3 (run in the sandbox).

Training data: MBPP+ outcome labels (all) + 80% of bolt-style draft labels.
Test data: 20% of bolt-style draft labels (stratified, seed 42), never trained on.
Also scores the current v1 head on the same test set as a baseline.

Usage: python train_ysolveth_v3.py mbpp_labels.jsonl bolt_labels.jsonl <encoder_dir> <v1_head.json> <out_dir>
"""
import json
import os
import random
import sys

import numpy as np
import onnxruntime as ort
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from tokenizers import Tokenizer

mbpp_path, bolt_path, enc_dir, v1_path, out_dir = sys.argv[1:6]
LABELS = ["hard", "moderate", "trivial"]

mbpp = [json.loads(l) for l in open(mbpp_path, encoding="utf-8")]
bolt = [json.loads(l) for l in open(bolt_path, encoding="utf-8")]

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


# Stratified 80/20 split of the bolt-style drafts (the target domain).
rng = random.Random(42)
train_bolt, test_bolt = [], []
for lab in ("moderate", "hard"):
    idx = [r for r in bolt if r["label"] == lab]
    rng.shuffle(idx)
    k = int(round(len(idx) * 0.2))
    test_bolt += idx[:k]
    train_bolt += idx[k:]

train = mbpp + train_bolt
X_tr = np.stack([embed(r["prompt"]) for r in train])
y_tr = np.array([LABELS.index(r["label"]) for r in train])
X_te = np.stack([embed(r["prompt"]) for r in test_bolt])
y_te = np.array([LABELS.index(r["label"]) for r in test_bolt])

clf = LogisticRegression(C=1.5, max_iter=1000, class_weight="balanced", random_state=42)
clf.fit(X_tr, y_tr)
pred = clf.predict(X_te)

# v1 head: prediction = argmax(W x + b); temperature is positive so it does not change argmax.
v1 = json.load(open(v1_path, encoding="utf-8"))
W1 = np.array(v1["weights"], dtype=np.float32)
b1 = np.array(v1["biases"], dtype=np.float32)
v1_labels = v1.get("difficulty_labels", LABELS)
v1_pred = np.array([LABELS.index(v1_labels[i]) for i in np.argmax(X_te @ W1.T + b1, axis=1)])


def score(p):
    acc = float((p == y_te).mean())
    cm = confusion_matrix(y_te, p, labels=[0, 1, 2])
    return acc, cm


v2_acc, v2_cm = score(pred)
v1_acc, v1_cm = score(v1_pred)
report = classification_report(y_te, pred, labels=[0, 1, 2], target_names=LABELS, zero_division=0)

head = {
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "version": "1.5.0-candidate-mbpp-bolt",
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
        "train_samples": len(train), "test_samples": len(test_bolt),
        "label_source": "MBPP+ outcome labels + bolt-style draft labels (unreviewed)",
    },
}
os.makedirs(out_dir, exist_ok=True)
json.dump(head, open(os.path.join(out_dir, "head_config.v3.json"), "w"), indent=2)

os.makedirs("reports", exist_ok=True)
with open("reports/ysolveth_v3.md", "w", encoding="utf-8") as f:
    f.write("# Ysolveth head v3 (MBPP+ outcome + bolt-style drafts)\n\n")
    f.write(f"Train {len(train)} (MBPP+ {len(mbpp)} + bolt-style {len(train_bolt)}). "
            f"Test {len(test_bolt)} bolt-style prompts, never trained on.\n\n")
    f.write("Bolt-style labels are unreviewed drafts written by the assistant. Treat results as provisional.\n\n")
    f.write(f"## v3 (candidate)\naccuracy: {v2_acc:.3f}\n\n```\n{report}\n```\nconfusion (rows true hard/moderate, cols hard/moderate/trivial):\n```\n{v2_cm}\n```\n\n")
    f.write(f"## v1 (current, baseline) on the same test set\naccuracy: {v1_acc:.3f}\n\n```\n{v1_cm}\n```\n")
print(report)
print("v3 acc", round(v2_acc, 3), "v1 acc", round(v1_acc, 3))
print("v3 cm\n", v2_cm)
print("v1 cm\n", v1_cm)
