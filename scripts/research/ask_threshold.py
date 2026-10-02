"""How Memory.ask trades answers for abstentions as the relevance threshold moves.

Loads the QA set's facts into a memory, scores every question's candidates once, then
counts, for each threshold, questions answered with the right fact and unanswerable
questions that got a fact anyway.

Usage: python scripts/research/ask_threshold.py datasets/qa-mini.json
"""

import json
import sys
from pathlib import Path

from verimem import Memory
from verimem.memory import Item


def main(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    memory = Memory(":memory:")
    results = memory.remember_many([Item(f["text"], source=f["text"]) for f in data["facts"]])
    id_of = {f["id"]: r.fact_id for f, r in zip(data["facts"], results, strict=True)}
    answerable, unanswerable = [], []
    for q in data["questions"]:
        scores = dict(memory.ask(q["q"]).candidates)
        want = {id_of[a] for a in q["answer"]}
        if want:
            right = max((scores.get(i, 0.0) for i in want), default=0.0)
            other = max((s for i, s in scores.items() if i not in want), default=0.0)
            answerable.append((right, other))
        else:
            unanswerable.append(max(scores.values(), default=0.0))
    print(f"{len(answerable)} answerable, {len(unanswerable)} unanswerable questions")
    print("threshold | right fact first | a wrong fact first | unanswerable given a fact")
    for th in (0.1, 0.2, 0.3, 0.35, 0.4, 0.5):
        right = sum(r >= th and r >= o for r, o in answerable)
        wrong = sum(o >= th and o > r for r, o in answerable)
        false = sum(s >= th for s in unanswerable)
        print(f"{th:9.2f} | {right:16d} | {wrong:18d} | {false:25d}")


if __name__ == "__main__":
    main(sys.argv[1])
