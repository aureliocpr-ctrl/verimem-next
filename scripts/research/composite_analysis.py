"""Reads the --dump of composite_window.py and compares the window configurations
(1) at equal error rates: the threshold that admits a share of the N+C claims, and the share
of S claims it keeps; (2) at the default threshold 0.5, when a composite window counts only
if it clears a higher bar.

Usage: python scripts/research/composite_analysis.py DUMP.jsonl
"""

import json
import sys

from verimem.evalkit import auroc, threshold_for_admission

CONFIGS = {"4 windows": ("usual",), "+ top-2": ("usual", "2"), "+ top-3": ("usual", "3"),
           "+ both": ("usual", "2", "3")}


def best(row: dict, parts: tuple[str, ...]) -> float:
    return max((x for p in parts for x in row.get(p, [])), default=0.0)


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    sets = sorted({r["set"] for r in rows})
    print("At equal error rates (share of S kept when at most 20% / 10% / 5% of N+C pass):")
    for subset in [None, *sets]:
        sel = [r for r in rows if subset is None or r["set"] == subset]
        print(f"  {subset or 'pooled'} ({sum(r['label'] == 'S' for r in sel)} S, "
              f"{sum(r['label'] != 'S' for r in sel)} N+C)")
        for name, parts in CONFIGS.items():
            s = [best(r, parts) for r in sel if r["label"] == "S"]
            u = [best(r, parts) for r in sel if r["label"] != "S"]
            kept = [sum(x >= threshold_for_admission(u, cap) for x in s) / len(s)
                    for cap in (0.20, 0.10, 0.05)]
            print(f"    {name:10} AUROC S/(N+C) {auroc(s, u):.3f} | "
                  + " / ".join(f"{k:.1%}" for k in kept))
    print("\nAt threshold 0.5, a composite window counting only above a higher bar:")
    for subset in sets:
        sel = [r for r in rows if r["set"] == subset]

        def rate(fn, sel=sel):
            return {lab: sum(fn(r) >= 0.5 for r in sel if r["label"] == lab)
                    / sum(r["label"] == lab for r in sel) for lab in "SNC"}

        base = rate(lambda r: best(r, ("usual",)))
        print(f"  {subset}: 4 windows S {base['S']:.1%} N {base['N']:.1%} C {base['C']:.1%}")
        for key in ("2", "3"):
            for bar in (0.9, 0.95, 0.98):
                def fn(r, key=key, bar=bar):
                    extra = [x for x in r.get(key, []) if x >= bar]
                    return max([best(r, ("usual",)), *extra])
                v = rate(fn)
                print(f"    top-{key} above {bar}: " + "  ".join(
                    f"{lab} {v[lab] - base[lab]:+.1%}" for lab in "SNC"))


if __name__ == "__main__":
    main()
