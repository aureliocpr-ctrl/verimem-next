"""How many memories must a person review for `verimem audit-review` to be precise?

Simulates audits: a population of judged memories split into the judge's groups, a true rate
of "not stated" in each group, a person reviewing n random memories per group. Prints the
average width of the 95% interval of the estimate, and how often it contains the truth.

The scenario is an assumption, not a measurement: 30% of memories flagged by the judge, 5%
uncertain, 65% verified; of those, 90%, 50% and 10% truly not stated by their source.

Usage: python scripts/research/review_sample_size.py
"""

import random
import statistics

from verimem.report import summarize_review

SHARES = {"not_supported": 0.30, "uncertain": 0.05, "supported": 0.65}
TRUE_RATE = {"not_supported": 0.90, "uncertain": 0.50, "supported": 0.10}


def simulate(total: int, per_group: int, trials: int, rng: random.Random) -> tuple[float, float]:
    widths, covered = [], 0
    for _ in range(trials):
        rows, truth = [], {}
        for verdict, share in SHARES.items():
            for i in range(round(total * share)):
                rid = f"{verdict}-{i}"
                rows.append({"id": rid, "verdict": verdict})
                truth[rid] = rng.random() < TRUE_RATE[verdict]
        marks = {}
        for verdict in SHARES:
            ids = [r["id"] for r in rows if r["verdict"] == verdict]
            for rid in rng.sample(ids, min(per_group, len(ids))):
                marks[rid] = "no" if truth[rid] else "yes"
        s = summarize_review({"rows": rows}, marks, rounds=1000, seed=rng.randrange(1 << 30))
        true_share = sum(truth.values()) / len(truth)
        lo, hi = s.ci
        widths.append(hi - lo)
        covered += lo <= true_share <= hi
    return statistics.fmean(widths), covered / trials


def main() -> None:
    rng = random.Random(2026)
    print("memories | reviewed per group | reviewed in all | mean 95% width | coverage")
    for total in (500, 2000):
        for n in (10, 20, 30, 50, 100):
            width, coverage = simulate(total, n, trials=200, rng=rng)
            print(f"{total:8d} | {n:18d} | {3 * n:15d} | {width:13.1%} | {coverage:8.0%}")


if __name__ == "__main__":
    main()
