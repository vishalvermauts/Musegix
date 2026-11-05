"""Run generated MBPP+ solutions against their asserts in a subprocess (run inside the sandbox).

Usage: python mbpp_run_tests.py gen.jsonl tasks.parquet out.jsonl
Each (task, model) row gets passed=true/false. A solution passes only if every assert in test_list passes.
"""
import json, subprocess, sys, tempfile, os
import pyarrow.parquet as pq

gen_path, tasks_path, out_path = sys.argv[1:4]
tests = {r["task_id"]: r["test_list"] for r in pq.read_table(tasks_path).to_pylist()}
results = []
for line in open(gen_path, encoding="utf-8"):
    row = json.loads(line)
    asserts = tests[row["task_id"]]
    program = row["code"] + "\n\n" + "\n".join(asserts) + "\nprint('PASS')\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(program)
        path = fh.name
    try:
        p = subprocess.run([sys.executable, path], capture_output=True, text=True, timeout=10)
        passed = p.returncode == 0 and "PASS" in p.stdout
        err = (p.stderr.strip().splitlines() or [""])[-1][:200] if not passed else ""
    except subprocess.TimeoutExpired:
        passed, err = False, "timeout"
    finally:
        os.unlink(path)
    results.append({"task_id": row["task_id"], "tier": row["tier"], "passed": passed, "error": err})

with open(out_path, "w", encoding="utf-8") as fh:
    for r in results:
        fh.write(json.dumps(r) + "\n")
print(f"tested={len(results)} passed={sum(r['passed'] for r in results)}")
