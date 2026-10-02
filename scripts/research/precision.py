"""Same judge weights in float16, float32 and bfloat16: time per pair and score changes.

transformers 5 loads the default judge's float16 checkpoint as float16 and transformers 4 as
float32, so the precision is now set explicitly (float32 unless the policy says bfloat16).
This measures what each choice costs: the (window, claim) pairs are the top 4 windows of a
seeded sample of claims, scored in batches of 16 sorted by length, as the judge does.

Usage: python scripts/research/precision.py PAIRS.jsonl [...] [--claims 150]
(run from scripts/research, which holds window_budget.py)
"""

import argparse
import random
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from window_budget import ranked_windows

from verimem.evalkit import load_pairs
from verimem.policy import Policy
from verimem.text import normalize_ws


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", type=Path)
    ap.add_argument("--claims", type=int, default=150)
    a = ap.parse_args()
    model_id = Policy.default().judge.removeprefix("hf:")
    rng = random.Random(5)
    pool = [p for path in a.pairs for p in load_pairs(path)]
    jobs = []
    for p in rng.sample(pool, min(a.claims, len(pool))):
        claim = normalize_ws(p.claim)
        jobs += [(w, claim) for w in ranked_windows(p.source, claim, limit=4)]
    order = sorted(range(len(jobs)), key=lambda i: len(jobs[i][0]) + len(jobs[i][1]))
    tok = AutoTokenizer.from_pretrained(model_id, local_files_only=True)
    scores = {}
    for name in ("float16", "float32", "bfloat16"):
        model = AutoModelForSequenceClassification.from_pretrained(model_id,
                                                                   local_files_only=True).eval()
        model.to(getattr(torch, name))
        entail = next(i for i, v in model.config.id2label.items()
                      if "entail" in v.lower() and "not" not in v.lower())
        out = [0.0] * len(jobs)
        t = time.perf_counter()
        with torch.inference_mode():
            for s in range(0, len(order), 16):
                idx = order[s : s + 16]
                enc = tok([jobs[i][0] for i in idx], [jobs[i][1] for i in idx],
                          truncation=True, max_length=512, padding=True, return_tensors="pt")
                probs = model(**enc).logits.float().softmax(-1)[:, entail].tolist()
                for i, pr in zip(idx, probs, strict=True):
                    out[i] = pr
        elapsed = time.perf_counter() - t
        scores[name] = out
        print(f"{name:9} {elapsed / len(jobs):.4f} s/pair over {len(jobs)} pairs", flush=True)
    for name in ("float16", "bfloat16"):
        d = [abs(x - y) for x, y in zip(scores[name], scores["float32"], strict=True)]
        flips = sum((x >= 0.5) != (y >= 0.5)
                    for x, y in zip(scores[name], scores["float32"], strict=True))
        print(f"{name} vs float32: max diff {max(d):.4f}, mean {sum(d) / len(d):.5f}, "
              f"crossings of 0.5: {flips} of {len(d)}")


if __name__ == "__main__":
    main()
