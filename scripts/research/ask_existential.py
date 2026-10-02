"""Tried for `ask`, not adopted: relevance as entailment of an existential statement.

The question becomes a statement with an indefinite in place of the question word ("Who
leads the team?" -> "Someone leads the team"; Italian yes/no questions are already
statements), and the judge says whether the fact entails it. Compared, per QA set and on the
same retrieved candidates: the current template score (A), the existential score (E), and
max(A, E). Hand-written rules, English and Italian only.

Usage: python scripts/research/ask_existential.py QA.json [...]
"""

import json
import sys

from verimem import Memory
from verimem.evalkit import auroc
from verimem.memory import Item

AUX = {"is", "are", "was", "were", "do", "does", "did", "can", "could", "will", "would",
       "has", "have", "had", "should", "may", "might"}
EN_INDEF = {"who": "someone", "whom": "someone", "what": "something", "which": "something",
            "where": "somewhere", "when": "at some time", "why": "for some reason",
            "how": "in some way"}
QUANT = {"many", "much", "long", "old", "often"}


EN_PREP = {"on", "in", "at", "for", "to", "from", "with", "by", "of"}


def en(q: str) -> str | None:
    toks = q.rstrip(" ?").split()
    if not toks:
        return None
    prep = None
    if toks[0].lower() in EN_PREP and len(toks) > 1 and toks[1].lower() in EN_INDEF:
        prep, toks = toks[0].lower(), toks[1:]
    w = toks[0].lower()
    if w in AUX:  # yes/no question: drop the auxiliary
        return " ".join(toks[1:])
    if w not in EN_INDEF:
        return None
    rest = toks[1:]
    indef = EN_INDEF[w]
    if w == "how" and rest and rest[0].lower() in QUANT:
        indef = "some amount" if rest[0].lower() != "many" else "some number of"
        rest = rest[1:]
        if indef == "some number of" and rest and rest[0].lower() not in AUX:
            indef += " " + rest[0]
            rest = rest[1:]
    elif w in ("what", "which") and rest and rest[0].lower() not in AUX:
        indef = "some " + rest[0]
        rest = rest[1:]
    if w == "how" and indef == "some amount" and toks[1].lower() == "old":
        indef = "some age"
    if prep:
        indef = f"{prep} {indef}"
    if rest and rest[0].lower() in AUX:
        aux, rest = rest[0].lower(), rest[1:]
        if aux in ("is", "are", "was", "were"):
            return " ".join([*rest, aux, indef])
        return " ".join([*rest, indef])
    return " ".join([indef[0].upper() + indef[1:], *rest])


IT_LEAD = {"chi": "qualcuno", "cosa": "qualcosa", "dove": "da qualche parte",
           "quando": "in un certo momento", "come": "in qualche modo",
           "perché": "per qualche motivo",
           "quanto": "una certa quantità", "quanta": "una certa quantità",
           "quanti": "un certo numero di", "quante": "un certo numero di"}


def it(q: str) -> str | None:
    toks = q.rstrip(" ?").split()
    if not toks:
        return None
    toks = [t for t in toks]
    low = [t.lower() for t in toks]
    i = 0
    if low[0] in ("in", "a", "da", "di", "per") and len(low) > 1:  # "In che città", "A che ora"
        i = 1
    w = low[i]
    if w == "che" and len(low) > i + 1 and low[i + 1] == "cosa":
        w, i = "cosa", i + 1
    if w in ("qual", "quale") and len(low) > i + 1 and low[i + 1] in ("è", "sono"):
        return " ".join([*toks[i + 2:], toks[i + 1], "qualcosa"])
    if w in ("che", "quale", "quali") and len(low) > i + 1:
        noun = toks[i + 1]
        rest = toks[i + 2:]
        return " ".join([*rest, "un certo", noun])
    if w in ("quanti", "quante") and len(low) > i + 1:
        noun = toks[i + 1]
        return " ".join([*toks[i + 2:], "un certo numero di", noun])
    if w in IT_LEAD:
        rest = toks[i + 1:]
        if w in ("chi", "cosa"):
            if rest and rest[0].lower() in ("è", "sono"):
                return " ".join([*rest[1:], rest[0], IT_LEAD[w]])
            return " ".join([IT_LEAD[w].capitalize(), *rest])
        return " ".join([*rest, IT_LEAD[w]])
    if i == 0:
        return q.rstrip(" ?")  # yes/no: an Italian question is already a statement
    return None


IT_FIRST = {"chi", "cosa", "che", "quale", "quali", "qual", "dove", "quando", "come", "perché",
            "quanto", "quanta", "quanti", "quante"}


def existential(q: str) -> str | None:
    words_ = q.lower().split()
    if len(words_) > 1 and words_[0] in ("in", "a", "da", "di", "per"):
        first = words_[1]
    else:
        first = words_[0] if words_ else ""
    if first in IT_FIRST:
        return it(q)
    out = en(q)
    if out is None:  # no English question word or auxiliary: read it as a statement
        return q.rstrip(" ?")
    return out


def run(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    m = Memory(":memory:")
    res = m.remember_many([Item(f["text"], source=f["text"]) for f in data["facts"]])
    id_of = {f["id"]: r.fact_id for f, r in zip(data["facts"], res, strict=True)}
    text_of = {r.fact_id: f["text"] for f, r in zip(data["facts"], res, strict=True)}
    judge = m.verifier.judge
    rows = []  # (statement, wanted fact ids, candidate ids, template scores, existential)
    for q in data["questions"]:
        ids = [r["id"] for r, _ in m.store.search(q["q"], ["verified"], limit=20)]
        texts = [text_of[i] for i in ids]
        a = m.relevance.score(q["q"], texts) if texts else []
        h = existential(q["q"])
        e = ([s.entailment for s in judge.score([(t, h) for t in texts])]
             if texts and h else [0.0] * len(texts))
        rows.append((h, {id_of[x] for x in q["answer"]}, ids, a, e))
    n_ans = sum(1 for r in rows if r[1])
    for name, combine in (("A", lambda a, e: a), ("E", lambda a, e: e),
                          ("max", lambda a, e: max(a, e))):
        cells, pos, neg = [], [], []
        for th in (0.2, 0.3, 0.4, 0.5):
            right = false = 0
            for _, want, ids, a, e in rows:
                scores = [combine(x, y) for x, y in zip(a, e, strict=True)]
                ranked = sorted(zip(ids, scores, strict=True), key=lambda t: -t[1])
                kept = {i for i, s in ranked[:5] if s >= th}  # ask returns at most k=5
                if want:
                    right += bool(want & kept)
                else:
                    false += bool(kept)
            cells.append(f"th {th}: {right}/{n_ans} right, {false}/{len(rows) - n_ans} false")
        for _, want, ids, a, e in rows:
            sc = dict(zip(ids, [combine(x, y) for x, y in zip(a, e, strict=True)], strict=True))
            if want:
                pos.append(max((sc.get(i, 0.0) for i in want), default=0.0))
            else:
                neg.append(max(sc.values(), default=0.0))
        print(f"  {name:4} AUROC {auroc(pos, neg):.3f} | " + " | ".join(cells))
    print("  no statement for:", [r for r in rows if r[0] is None])


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p)
        run(p)
