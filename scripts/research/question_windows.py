"""Why the verifier skips windows made only of questions (commit "a question is never
evidence on its own").

Compares, on labelled pairs, the AUROC of S vs N for:
  raw     the judge on the whole source, no windows
  before  windows of 1 and 2 sentences plus the whole source, questions included
  after   the verifier as it is (windows made only of questions skipped)

Usage: python scripts/research/question_windows.py datasets/truthfulqa-pairs.jsonl
"""

import sys

from verimem import Verifier
from verimem.evalkit import auroc, load_pairs
from verimem.text import normalize_ws, split_sentences


def windows_with_questions(source: str, max_chars: int = 1500) -> list[str]:
    sents = split_sentences(source)
    spans = {(sents[i].start, sents[i + n - 1].end)
             for n in (1, 2) for i in range(len(sents) - n + 1)}
    if len(source) <= max_chars and sents:
        spans.add((sents[0].start, sents[-1].end))
    return [source[s:e] for s, e in sorted(spans)]


def main(path: str) -> None:
    pairs = load_pairs(path)
    verifier = Verifier.default()
    judge = verifier.judge
    claims = [normalize_ws(p.claim) for p in pairs]
    whole = [(p.source, c) for p, c in zip(pairs, claims, strict=True)]
    raw = [s.entailment for s in judge.score(whole)]
    before = []
    for p, c in zip(pairs, claims, strict=True):
        before.append(max(s.entailment for s in judge.score(
            [(w, c) for w in windows_with_questions(p.source)])))
    after = [v.support for v in verifier.check_many([(p.source, p.claim) for p in pairs])]
    for name, scores in (("raw", raw), ("before", before), ("after", after)):
        s = [x for x, p in zip(scores, pairs, strict=True) if p.label == "S"]
        n = [x for x, p in zip(scores, pairs, strict=True) if p.label == "N"]
        print(f"{name:7} AUROC S vs N {auroc(s, n):.3f}  ({len(s)} S, {len(n)} N)")


if __name__ == "__main__":
    main(sys.argv[1])
