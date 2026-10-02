"""Does a window made of the claim's most relevant sentences, wherever they are, help?

A memory often joins two sentences that are not next to each other ("I moved to Milan" in
one turn, "that was in 2021" three turns later). Windows of one or two adjacent sentences
cannot support it, and the whole source is a window only when it is short. This adds one
window per claim, the m sentences the prefilter ranks highest joined in source order, and
compares on labelled pairs the best support with and without it, next to the 4 usual
windows. Judge alone: the quantity and context checks are left out, as in window_budget.py.

Usage (from scripts/research):
    python composite_window.py PAIRS.jsonl [...] [--s 200] [--seed 2026] [--dump FILE]
--dump writes one JSON line per claim with every score, for comparisons at equal error rates.
"""

import argparse
import json
import random
from pathlib import Path

from window_budget import ranked_windows

from verimem import Verifier
from verimem.evalkit import auroc, load_pairs
from verimem.policy import Policy
from verimem.text import char_trigrams, content_tokens, is_question, normalize_ws, split_sentences


def composite(source: str, claim: str, m: int) -> str | None:
    """The m non-question sentences most relevant to the claim, in source order."""
    sents = [s for s in split_sentences(source) if not is_question(s.text)]
    if len(sents) <= m:
        return None
    ct, tri = content_tokens(claim), char_trigrams(claim)

    def relevance(text: str) -> float:
        wt, wtri = content_tokens(text), char_trigrams(text)
        tok = len(ct & wt) / len(ct) if ct else 0.0
        jac = len(tri & wtri) / len(tri | wtri) if tri else 0.0
        return tok + 0.5 * jac

    top = sorted(sorted(sents, key=lambda s: relevance(s.text), reverse=True)[:m],
                 key=lambda s: s.start)
    return " ".join(s.text for s in top)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="+", type=Path)
    ap.add_argument("--s", type=int, default=200, help="S pairs sampled per file")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--dump", type=Path)
    a = ap.parse_args()
    dump = a.dump.open("w", encoding="utf-8") if a.dump else None
    rng = random.Random(a.seed)
    judge = Verifier(policy=Policy.default()).judge
    for path in a.pairs:
        pairs = load_pairs(path)
        s = [p for p in pairs if p.label == "S"]
        items = [p for p in pairs if p.label != "S"] + rng.sample(s, min(a.s, len(s)))
        jobs, plan = [], []
        for p in items:
            claim = normalize_ws(p.claim)
            usual = ranked_windows(p.source, claim, limit=4)
            extra = {m: composite(p.source, claim, m) for m in (2, 3)}
            idx = {"usual": list(range(len(jobs), len(jobs) + len(usual)))}
            jobs += [(w, claim) for w in usual]
            for m, text in extra.items():
                if text is not None:
                    idx[m] = [len(jobs)]
                    jobs.append((text, claim))
            plan.append((p.label, idx, p.id))
        scores = [x.entailment for x in judge.score(jobs)]
        if dump:
            for lab, idx, pid in plan:
                dump.write(json.dumps({"set": path.stem, "id": pid, "label": lab, **{
                    str(k): [round(scores[i], 6) for i in v] for k, v in idx.items()}}) + "\n")
        configs = {"4 windows": ("usual",), "+ top-2 sentences": ("usual", 2),
                   "+ top-3 sentences": ("usual", 3), "+ both": ("usual", 2, 3)}
        n = {lab: sum(lab == x for x, _, _ in plan) for lab in "SNC"}
        print(f"\n{path.stem}: {n['S']} S, {n['N']} N, {n['C']} C, {len(jobs)} pairs judged")
        print("  windows | AUROC S/N | AUROC S/C | S >= 0.5 | N >= 0.5 | C >= 0.5")
        for name, parts in configs.items():
            best = {lab: [] for lab in "SNC"}
            for lab, idx, _ in plan:
                pool = [scores[i] for part in parts for i in idx.get(part, [])]
                best[lab].append(max(pool, default=0.0))
            rate = {lab: sum(x >= 0.5 for x in v) / len(v) if v else float("nan")
                    for lab, v in best.items()}
            print(f"  {name:17} | {auroc(best['S'], best['N']):9.3f} | "
                  f"{auroc(best['S'], best['C']):9.3f} | {rate['S']:8.1%} | {rate['N']:8.1%} | "
                  f"{rate['C']:8.1%}")
    if dump:
        dump.close()


if __name__ == "__main__":
    main()
