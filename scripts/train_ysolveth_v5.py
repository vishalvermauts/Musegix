"""Train candidate head v5 on a task-level split (run in the sandbox).

Usage: python train_ysolveth_v5.py labels_v2.jsonl reviewed.jsonl split_v2.json <encoder_dir> <v1_head.json> <out_dir>
Same method as train_ysolveth_v4.py: frozen MiniLM int8 encoder, mean pooling, LogisticRegression(C=1.5, class_weight=balanced).
Split: bolt-style records split by task_id from split_v2.json. MBPP+ outcome labels are always training data.
"""
import collections, json, os, sys
import numpy as np
import onnxruntime as ort
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from tokenizers import Tokenizer

mbpp_path, reviewed_path, split_path, enc_dir, v1_path, out_dir = sys.argv[1:7]
LABELS = ["hard", "moderate", "trivial"]

mbpp = [json.loads(l) for l in open(mbpp_path, encoding="utf-8")]
for r in mbpp:
    r.setdefault("label_source", "outcome")
all_bolt = [json.loads(l) for l in open(reviewed_path, encoding="utf-8")]
bolt = [r for r in all_bolt if r.get("label_source") == "reviewed_rubric_v1_assistant"]
split = json.load(open(split_path, encoding="utf-8"))
test_ids = set(split["test_task_ids"])
train_bolt = [r for r in bolt if r["task_id"] not in test_ids]
test_bolt = [r for r in bolt if r["task_id"] in test_ids]
assert len(set(r["task_id"] for r in train_bolt) & test_ids) == 0
print("bolt:", len(bolt), "train:", len(train_bolt), "test:", len(test_bolt))
print("test label counts:", collections.Counter(r["label"] for r in test_bolt))

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

train = mbpp + train_bolt
X_tr = np.stack([embed(r["prompt"]) for r in train])
y_tr = np.array([LABELS.index(r["label"]) if r.get("label") in LABELS else LABELS.index(r["label"]) for r in train])
X_te = np.stack([embed(r["prompt"]) for r in test_bolt])
y_te = np.array([LABELS.index(r["label"]) for r in test_bolt])

clf = LogisticRegression(C=1.5, max_iter=2000, class_weight="balanced", random_state=42)
clf.fit(X_tr, y_tr)
pred = clf.predict(X_te)

v1 = json.load(open(v1_path, encoding="utf-8"))
W1 = np.array(v1["weights"], dtype=np.float32)
b1 = np.array(v1["biases"], dtype=np.float32)
v1_labels = v1.get("difficulty_labels", LABELS)
v1_idx = np.argmax(X_te @ W1.T + b1, axis=1)
v1_pred = np.array([LABELS.index(v1_labels[i]) for i in v1_idx])

def block(yp):
    cm = confusion_matrix(y_te, yp, labels=[0, 1, 2])
    rep = classification_report(y_te, yp, labels=[0, 1, 2], target_names=LABELS, zero_division=0)
    p, r, f, s = precision_recall_fscore_support(y_te, yp, labels=[0, 1, 2], zero_division=0)
    return cm, rep, p, r, int(cm[0, 1] + cm[0, 2])

cm, report, p5, r5, down5 = block(pred)
cm1, report1, p1, r1, down1 = block(v1_pred)
print(report); print("v5 cm\n", cm); print(report1); print("v1 cm\n", cm1)
print("HARD downgraded: v5", down5, "v1", down1)

head = {
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "version": "1.7.0-candidate-task-split",
    "difficulty_labels": LABELS,
    "label_to_idx": {"hard": 0, "moderate": 1, "trivial": 2},
    "hidden_size": 384, "num_classes": 3,
    "weights": clf.coef_.tolist(), "biases": clf.intercept_.tolist(),
    "temperature": 0.2842, "epsilon_threshold": 0.1,
    "training_metadata": {
        "library": "scikit-learn", "model_type": "LogisticRegression", "C": 1.5,
        "class_weight": "balanced", "seed": 42, "split": "task_id split_v2 (seed 42, 80/20)",
        "train_samples": len(train), "test_samples": len(test_bolt),
        "test_task_ids": split["test_task_ids"],
        "label_source": "MBPP+ outcome + bolt-style reviewed_rubric_v1_assistant (human spot-check pending)",
    },
}
os.makedirs(out_dir, exist_ok=True)
json.dump(head, open(os.path.join(out_dir, "head_config.v5.json"), "w"), indent=2)

def fmt(cm, rep, down, n_hard):
    return "```\n" + rep + "\n```\nconfusion (rows true hard/moderate/trivial):\n```\n" + str(cm) + "\n```\nHARD routed to a lower tier: %d of %d\n" % (down, n_hard)

os.makedirs("reports", exist_ok=True)
n_hard = int(cm[0].sum())
with open("reports/ysolveth_v5.md", "w", encoding="utf-8") as f:
    f.write("# Ysolveth head v5 candidate (rubric v1, task-level split)\n\n")
    f.write(f"Bolt-style records: {len(bolt)}. Tasks: {split['n_tasks']} (train {split['n_train_tasks']}, test {split['n_test_tasks']}), split seed 42.\n")
    f.write(f"Train: MBPP+ {len(mbpp)} + bolt-style {len(train_bolt)}. Test: bolt-style {len(test_bolt)}.\n")
    f.write(f"Test label counts: {dict(collections.Counter(r['label'] for r in test_bolt))}\n\n")
    f.write("## v5 candidate\n" + fmt(cm, report, down5, n_hard) + "\n")
    f.write("## v1 current, same test set\n" + fmt(cm1, report1, down1, int(cm1[0].sum())) + "\n")
