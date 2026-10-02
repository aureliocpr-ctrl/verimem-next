"""How many windows does the verifier need to judge per claim on long sources?

The verifier judges up to `max_windows` windows per claim, ranked by a lexical prefilter,
and keeps the best. On long sources that is most of the cost. This scores the top 12 windows
of each pair once (12 was the default before this study, 4 after it), then asks what judging
only the top k would have given:
the AUROC of S vs N and of S vs C, the share of S and N whose support passes 0.5, and where
the best window sits in the prefilter's ranking.

Usage: python scripts/research/window_budget.py PAIRS.jsonl [PAIRS.jsonl ...] --cache FILE
(all N and C pairs of each file plus a seeded sample of --s S pairs). The cache is written as
it goes, one claim per line, so an interrupted run resumes where it stopped.
"""

import argparse
import json
import random
from pathlib import Path

from verimem import Verifier
from verimem.evalkit import auroc, load_pairs
from verimem.policy import Policy
from verimem.text import (
    char_trigrams,
    content_tokens,
    is_question,
    normalize_ws,
    split_sentences,
)

KS = (1, 2, 3, 4, 6, 8, 12)


def ranked_windows(source: str, claim: str, limit: int = 12) -> list[str]:
    sents = split_sentences(source)
    asks = [is_question(s.text) for s in sents]
    spans: dict[tuple[int, int], str] = {}
    for size in (1, 2):
        for i in range(len(sents) - size + 1):
            if all(asks[i : i + size]):
                continue
            s, e = sents[i].start, sents[i + size - 1].end
            spans.setdefault((s, e), source[s:e])
    if sents and len(source) <= 1500 and not all(asks):
        spans.setdefault((sents[0].start, sents[-1].end), source[sents[0].start:sents[-1].end])
    ct, tri = content_tokens(claim), char_trigrams(claim)

    def relevance(text: str) -> float:
        wt, wtri = content_tokens(text), char_trigrams(text)
        tok = len(ct & wt) / len(ct) if ct else 0.0
        jac = len(tri & wtri) / len(tri | wtri) if tri else 0.0
        return tok + 0.5 * jac

    return sorted(spans.values(), key=relevance, reverse=True)[:limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", type=Path)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--s", type=int, default=200, help="S pairs sampled per file")
    a = ap.parse_args()
    rng = random.Random(2026)
    items = []
    for path in a.pairs:
        pairs = load_pairs(path)
        s = [p for p in pairs if p.label == "S"]
        keep = [p for p in pairs if p.label != "S"] + rng.sample(s, min(a.s, len(s)))
        items += [(path.stem, p) for p in keep]
    done = set()
    if a.cache.exists():
        done = {(r["set"], r["id"]) for r in map(json.loads, a.cache.read_text().splitlines())}
    todo = [(name, p) for name, p in items if (name, p.id) not in done]
    if todo:
        judge = Verifier(policy=Policy.default()).judge
        with a.cache.open("a") as f:
            for start in range(0, len(todo), 50):
                chunk, jobs, rows = todo[start : start + 50], [], []
                for name, p in chunk:
                    claim = normalize_ws(p.claim)
                    wins = ranked_windows(p.source, claim)
                    rows.append({"set": name, "id": p.id, "label": p.label, "n": len(wins)})
                    jobs += [(w, claim) for w in wins]
                scores = [x.entailment for x in judge.score(jobs)]
                pos = 0
                for row in rows:
                    row["scores"] = scores[pos : pos + row["n"]]
                    pos += row["n"]
                    f.write(json.dumps(row) + "\n")
                f.flush()
                print(f"{start + len(chunk)}/{len(todo)} claims scored", flush=True)
    wanted = {(name, p.id) for name, p in items}
    cache = [r for r in map(json.loads, a.cache.read_text().splitlines())
             if (r["set"], r["id"]) in wanted]
    for name in sorted({r["set"] for r in cache}):
        rows = [r for r in cache if r["set"] == name]
        print(f"\n{name}: {sum(r['label'] == 'S' for r in rows)} S, "
              f"{sum(r['label'] == 'N' for r in rows)} N, {sum(r['label'] == 'C' for r in rows)} C")
        print("  k | AUROC S/N | AUROC S/C | S >= 0.5 | N >= 0.5 | C >= 0.5")
        for k in KS:
            best = {lab: [max(r["scores"][:k]) for r in rows if r["label"] == lab and r["scores"]]
                    for lab in "SNC"}
            rate = {lab: sum(x >= 0.5 for x in v) / len(v) if v else float("nan")
                    for lab, v in best.items()}
            sn, sc = auroc(best["S"], best["N"]), auroc(best["S"], best["C"])
            print(f"{k:3d} | {sn:9.3f} | {sc:9.3f} | "
                  f"{rate['S']:8.1%} | {rate['N']:8.1%} | {rate['C']:8.1%}")
        ranks = [max(range(len(r["scores"])), key=r["scores"].__getitem__) + 1
                 for r in rows if r["scores"] and r["label"] == "S"]
        print("  rank of the best window for S claims:",
              {k: round(sum(x <= k for x in ranks) / len(ranks), 3) for k in KS})


if __name__ == "__main__":
    main()
