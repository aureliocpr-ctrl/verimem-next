"""Tried for `ask`, not adopted: answerability from an extractive QA model (SQuAD 2.0).

SQuAD 2.0 has unanswerable questions written to look answerable, like the near misses of the
QA sets. For a question and a fact: score = sigmoid(best span score - no-answer score).
Compared with the current relevance score (template "This text answers the question: ...")
on the same retrieved candidates, at several thresholds; then the misses and false answers.

Usage: python scripts/research/ask_extractive_qa.py MODEL QA.json [...]
(e.g. deepset/xlm-roberta-large-squad2; needs the sentencepiece and protobuf packages)
"""

import json
import math
import sys
import time
from dataclasses import dataclass

import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

from verimem import Memory
from verimem.evalkit import auroc
from verimem.memory import Item


@dataclass
class Row:
    question: str
    want: set[str]
    ids: list[str]
    texts: list[str]
    template: list[float]
    qa: list[float]
    spans: list[str]


def answerability(tok, model, question: str, texts: list[str],
                  max_len: int = 30) -> list[tuple[float, str]]:
    if not texts:
        return []
    enc = tok([question] * len(texts), texts, truncation="only_second", max_length=256,
              padding=True, return_tensors="pt", return_offsets_mapping=True)
    offsets = enc.pop("offset_mapping")
    with torch.inference_mode():
        out = model(**enc)
    res = []
    for b in range(len(texts)):
        ctx = [i for i, s in enumerate(enc.sequence_ids(b)) if s == 1]
        st, en = out.start_logits[b].tolist(), out.end_logits[b].tolist()
        best, span = -1e9, (0, 0)
        for i in ctx:
            for j in ctx:
                if i <= j < i + max_len and st[i] + en[j] > best:
                    best, span = st[i] + en[j], (int(offsets[b][i][0]), int(offsets[b][j][1]))
        res.append((1 / (1 + math.exp(-(best - (st[0] + en[0])))), texts[b][span[0]:span[1]]))
    return res


def report(rows: list[Row], name: str, scores_of, thresholds) -> None:
    n_ans = sum(1 for r in rows if r.want)
    cells, pos, neg = [], [], []
    for th in thresholds:
        right = false = 0
        for r in rows:
            ranked = sorted(zip(r.ids, scores_of(r), strict=True), key=lambda t: -t[1])
            kept = {i for i, s in ranked[:5] if s >= th}  # ask returns at most k=5
            if r.want:
                right += bool(r.want & kept)
            else:
                false += bool(kept)
        cells.append(f"th {th}: {right}/{n_ans} right, {false}/{len(rows) - n_ans} false")
    for r in rows:
        s = dict(zip(r.ids, scores_of(r), strict=True))
        if r.want:
            pos.append(max((s.get(i, 0.0) for i in r.want), default=0.0))
        else:
            neg.append(max(s.values(), default=0.0))
    print(f"  {name:3} AUROC {auroc(pos, neg):.3f} | " + " | ".join(cells))


def run(path: str, tok, model) -> None:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    m = Memory(":memory:")
    res = m.remember_many([Item(f["text"], source=f["text"]) for f in data["facts"]])
    id_of = {f["id"]: r.fact_id for f, r in zip(data["facts"], res, strict=True)}
    text_of = {r.fact_id: f["text"] for f, r in zip(data["facts"], res, strict=True)}
    rows, t_qa, n_pairs = [], 0.0, 0
    for q in data["questions"]:
        ids = [r["id"] for r, _ in m.store.search(q["q"], ["verified"], limit=20)]
        texts = [text_of[i] for i in ids]
        template = m.relevance.score(q["q"], texts) if texts else []
        t = time.perf_counter()
        qa = answerability(tok, model, q["q"], texts)
        t_qa += time.perf_counter() - t
        n_pairs += len(texts)
        rows.append(Row(q["q"], {id_of[x] for x in q["answer"]}, ids, texts, template,
                        [s for s, _ in qa], [sp for _, sp in qa]))
    print(f"  {n_pairs} pairs, QA model {t_qa / max(n_pairs, 1):.3f} s/pair")
    report(rows, "A", lambda r: r.template, (0.2, 0.3, 0.4, 0.5))
    report(rows, "QA", lambda r: r.qa, (0.3, 0.5, 0.7, 0.8, 0.9, 0.95))
    print("  answerable questions the QA model misses (< 0.5), unanswerable ones it answers:")
    for r in rows:
        if r.want:
            right = [k for k, i in enumerate(r.ids) if i in r.want]
            k = max(right, key=lambda k: r.qa[k], default=None)
            if k is None:
                print(f"    miss  0.00  {r.question}  (not retrieved)")
            elif r.qa[k] < 0.5:
                print(f"    miss  {r.qa[k]:.2f}  {r.question}  ->  '{r.spans[k]}'  [{r.texts[k]}]")
        elif r.qa:
            k = max(range(len(r.qa)), key=lambda k: r.qa[k])
            if r.qa[k] >= 0.5:
                print(f"    false {r.qa[k]:.2f}  {r.question}  ->  '{r.spans[k]}'  "
                      f"[{r.texts[k]}]")


def main() -> None:
    model_id = sys.argv[1]
    tok = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForQuestionAnswering.from_pretrained(model_id).eval()
    for path in sys.argv[2:]:
        print(path)
        run(path, tok, model)


if __name__ == "__main__":
    main()
