"""Generate MBPP+ solutions from three tiers of models (run locally, keys stay on this PC).

Usage: python scripts/mbpp_generate.py --n 20 --out data/labels/mbpp/gen_pilot.jsonl
Output: one JSON row per (task, model) with the extracted code, latency and token usage.
"""
import argparse, asyncio, json, os, random, re, time
import pyarrow.parquet as pq
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(".env")
MODELS = {
    "cheap": ("baseten", "meta-models/muse-spark-open-1026"),
    "mid": ("meta", "muse-spark-1.3"),
    "strong": ("meta", "muse-wonder-1.0"),
}
CLIENTS = {
    "meta": AsyncOpenAI(api_key=os.environ["META_API_KEY"], base_url=os.environ["META_BASE_URL"], timeout=120),
    "baseten": AsyncOpenAI(api_key=os.environ["BASETEN_API_KEY"], base_url=os.environ["BASETEN_BASE_URL"], timeout=120),
}
SYSTEM = "You write Python. Reply with only one ```python code block that defines the requested function. No explanation."
FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)


def extract(text):
    m = FENCE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


async def one(sem, row, tier, out):
    provider, model = MODELS[tier]
    async with sem:
        t = time.time()
        try:
            r = await CLIENTS[provider].chat.completions.create(
                model=model, max_tokens=2048,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": row["prompt"] + "\nTests:\n" + "\n".join(row["test_list"][:3])}],
            )
            text = r.choices[0].message.content
            usage = {"prompt": r.usage.prompt_tokens, "completion": r.usage.completion_tokens}
            err = None
        except Exception as e:
            text, usage, err = "", {"prompt": 0, "completion": 0}, str(e)[:200]
        out.append({"task_id": row["task_id"], "tier": tier, "model": model,
                    "code": extract(text), "latency_s": round(time.time() - t, 2), "usage": usage, "error": err})


async def main(n, out_path, seed, start=0):
    rows = pq.read_table("data/labels/mbpp/mbppplus.parquet").to_pylist()
    random.Random(seed).shuffle(rows)
    rows = rows[start:start + n]
    sem = asyncio.Semaphore(6)
    out = []
    await asyncio.gather(*[one(sem, row, tier, out) for row in rows for tier in MODELS])
    with open(out_path, "w", encoding="utf-8") as fh:
        for r in sorted(out, key=lambda x: (x["task_id"], x["tier"])):
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    ok = sum(1 for r in out if not r["error"])
    tokens = sum(r["usage"]["prompt"] + r["usage"]["completion"] for r in out)
    print(f"calls={len(out)} ok={ok} errors={len(out)-ok} total_tokens={tokens}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default="data/labels/mbpp/gen_pilot.jsonl")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--start", type=int, default=0)
    a = ap.parse_args()
    asyncio.run(main(a.n, a.out, a.seed, a.start))
