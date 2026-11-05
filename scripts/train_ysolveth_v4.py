"""Train candidate head v4 (run in the sandbox).

Loader rules:
- Use only bolt-style records with label_source == reviewed_rubric_v1_assistant.
- Exclude draft_unreviewed and needs_context records; report the counts.
- MBPP+ outcome labels (source: outcome) are always training data, never test data.

Split rules:
- Bolt-style records are split by task family: each family goes entirely to train or entirely to test.
  Family choice is seeded and must give every class at least MIN_TEST per class in test.

Usage: python train_ysolveth_v4.py mbpp_labels.jsonl reviewed.jsonl <encoder_dir> <v1_head.json> <out_dir>
"""
import collections
import json
import os
import random
import sys

import numpy as np
import onnxruntime as ort
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from tokenizers import Tokenizer

mbpp_path, reviewed_path, enc_dir, v1_path, out_dir = sys.argv[1:6]
LABELS = ["hard", "moderate", "trivial"]
MIN_TEST = 8

mbpp = [json.loads(l) for l in open(mbpp_path, encoding="utf-8")]
for r in mbpp:
    r.setdefault("label_source", "outcome")
all_bolt = [json.loads(l) for l in open(reviewed_path, encoding="utf-8")]
bolt = [r for r in all_bolt if r.get("label_source") == "reviewed_rubric_v1_assistant"]
# Topic families are almost single-label (e.g. product-ui is 49 moderate, 2 hard), so a
# topic split cannot test all three classes. Group by the first two words of the prompt instead.
for r in bolt:
    r["family"] = " ".join(r["prompt"].lower().split()[:2])
excluded = collections.Counter(r.get("label_source", "?") for r in all_bolt if r not in bolt)
print("bolt records:", len(all_bolt), "included:", len(bolt), "excluded:", dict(excluded))

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


# Family-level split: search seeds until every class has at least MIN_TEST records in test.
families = sorted({r["family"] for r in bolt})
chosen = None
for seed in range(1, 500):
    rng = random.Random(seed)
    order = families[:]
    rng.shuffle(order)
    test_fams, test_n = set(), 0
    for fam in order:
        n = sum(1 for r in bolt if r["family"] == fam)
        if test_n >= 0.2 * len(bolt):
            break
        test_fams.add(fam)
        test_n += n
    test = [r for r in bolt if r["family"] in test_fams]
    counts = collections.Counter(r["label"] for r in test)
    if all(counts[l] >= MIN_TEST for l in LABELS) and len(test) <= 0.35 * len(bolt):
        chosen = (seed, test_fams)
        break
if chosen is None:
    raise SystemExit("no family split satisfies the per-class minimum; reduce MIN_TEST or add data")
seed, test_fams = chosen
train_bolt = [r for r in bolt if r["family"] not in test_fams]
test_bolt = [r for r in bolt if r["family"] in test_fams]
print("split seed:", seed, "test families:", sorted(test_fams))
print("train bolt:", collections.Counter(r["label"] for r in train_bolt), "test bolt:", collections.Counter(r["label"] for r in test_bolt))

train = mbpp + train_bolt
X_tr = np.stack([embed(r["prompt"]) for r in train])
y_tr = np.array([LABELS.index(r["label"]) for r in train])
X_te = np.stack([embed(r["prompt"]) for r in test_bolt])
y_te = np.array([LABELS.index(r["label"]) for r in test_bolt])

clf = LogisticRegression(C=1.5, max_iter=2000, class_weight="balanced", random_state=42)
clf.fit(X_tr, y_tr)
pred = clf.predict(X_te)

v1 = json.load(open(v1_path, encoding="utf-8"))
W1 = np.array(v1["weights"], dtype=np.float32)
b1 = np.array(v1["biases"], dtype=np.float32)
v1_labels = v1.get("difficulty_labels", LABELS)
v1_pred = np.array([LABELS.index(v1_labels[i]) for i in np.argmax(X_te @ W1.T + b1, axis=1)])

cm = confusion_matrix(y_te, pred, labels=[0, 1, 2])
cm1 = confusion_matrix(y_te, v1_pred, labels=[0, 1, 2])
report = classification_report(y_te, pred, labels=[0, 1, 2], target_names=LABELS, zero_division=0)
report1 = classification_report(y_te, v1_pred, labels=[0, 1, 2], target_names=LABELS, zero_division=0)
hard_down = int(cm[0, 1] + cm[0, 2])
hard_down1 = int(cm1[0, 1] + cm1[0, 2])

head = {
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "version": "1.6.0-candidate-rubric-v1",
    "difficulty_labels": LABELS,
    "label_to_idx": {"hard": 0, "moderate": 1, "trivial": 2},
    "hidden_size": 384,
    "num_classes": 3,
    "weights": clf.coef_.tolist(),
    "biases": clf.intercept_.tolist(),
    "temperature": 0.2842,
    "epsilon_threshold": 0.1,
    "training_metadata": {
        "library": "scikit-learn", "model_type": "LogisticRegression", "C": 1.5,
        "class_weight": "balanced", "seed": seed,
        "train_samples": len(train), "test_samples": len(test_bolt),
        "test_families": sorted(test_fams),
        "label_source": "MBPP+ outcome + bolt-style reviewed_rubric_v1_assistant (human spot-check pending)",
    },
}
os.makedirs(out_dir, exist_ok=True)
json.dump(head, open(os.path.join(out_dir, "head_config.v4.json"), "w"), indent=2)

os.makedirs("reports", exist_ok=True)
with open("reports/ysolveth_v4.md", "w", encoding="utf-8") as f:
    f.write("# Ysolveth head v4 candidate (rubric v1, family-level split)\n\n")
    f.write(f"Included bolt-style records: {len(bolt)}. Excluded: {dict(excluded)}.\n\n")
    f.write(f"Split seed {seed}. Test families: {sorted(test_fams)}.\n")
    f.write(f"Train: MBPP+ {len(mbpp)} + bolt-style {len(train_bolt)}. Test: bolt-style {len(test_bolt)}.\n\n")
    f.write("## v4 candidate\n```\n" + report + "\n```\nconfusion (rows true hard/moderate/trivial):\n```\n" + str(cm) + "\n```\n")
    f.write(f"HARD routed to a lower tier: {hard_down} of {int(cm[0].sum())}\n\n")
    f.write("## v1 current, same test set\n```\n" + report1 + "\n```\nconfusion:\n```\n" + str(cm1) + "\n```\n")
    f.write(f"HARD routed to a lower tier: {hard_down1} of {int(cm1[0].sum())}\n")
print(report)
print("v4 cm\n", cm)
print("v1 cm\n", cm1)
print("HARD downgraded: v4", hard_down, "v1", hard_down1)
