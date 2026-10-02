"""Turn RAGTruth into labelled (source, claim) pairs for `verimem eval` and `verimem calibrate`.

RAGTruth (ParticleMedia, MIT license, https://github.com/ParticleMedia/RAGTruth) holds about
18,000 responses written by six LLMs from a source: a news article to summarise (Summary),
passages to answer a question (QA, passages from MS MARCO) or business data to describe
(Data2txt, from Yelp). Annotators marked every hallucinated span. The sources keep their own
licenses, so the pairs are written to a local folder and not redistributed with verimem.

Rules, fixed before running verimem on these data:
- Responses whose quality is not "good" (refusals, truncated answers) are skipped, and so
  are responses that answer "Unable to answer based on given passages".
- Each response is split into sentences (verimem.text.split_sentences); each sentence is a
  claim, checked against the source of its response.
- A sentence that overlaps a span labelled "Evident Conflict" or "Subtle Conflict" is C;
  otherwise one that overlaps "Evident Baseless Info" or "Subtle Baseless Info" is N;
  otherwise S. Spans flagged implicit_true (true, but not in the source) count as N: the
  rule of verimem is that the source must say it.
- Sentences with fewer than 4 words are dropped (headings, list markers, "Sure!").
- Sources: the article (Summary), the passages without the question (QA), the business data
  as JSON text (Data2txt).
- Splits: RAGTruth's train split becomes "dev" (for calibration, sampled), its test split
  "test" (for reporting, complete).

Usage:
    python scripts/external/ragtruth_pairs.py --data DIR_WITH_JSONL --out DIR [--dev-responses 400]
writes DIR/ragtruth-{summary,qa,data2txt}-{dev,test}.jsonl.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

from verimem.text import split_sentences, words

CONFLICT = {"Evident Conflict", "Subtle Conflict"}
BASELESS = {"Evident Baseless Info", "Subtle Baseless Info"}
TASKS = {"Summary": "summary", "QA": "qa", "Data2txt": "data2txt"}


def source_text(info: dict) -> str:
    data = info["source_info"]
    if info["task_type"] == "Summary":
        return str(data)
    if info["task_type"] == "QA":
        return str(data["passages"])
    return json.dumps(data, ensure_ascii=False)


def label_for(start: int, end: int, spans: list[dict]) -> str:
    hits = [s for s in spans if s["start"] < end and start < s["end"]]
    if any(s["label_type"] in CONFLICT for s in hits):
        return "C"
    if any(s["label_type"] in BASELESS for s in hits):
        return "N"
    return "S"


def pairs_for(response: dict, info: dict) -> list[dict]:
    text = response["response"]
    if response["quality"] != "good" or "Unable to answer based on given passages" in text:
        return []
    source = source_text(info)
    out = []
    for i, sent in enumerate(split_sentences(text)):
        if len(words(sent.text)) < 4:
            continue
        out.append({"id": f"{response['id']}.{i}", "source": source, "claim": sent.text,
                    "label": label_for(sent.start, sent.end, response["labels"]),
                    "lang": "en", "model": response["model"]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dev-responses", type=int, default=400,
                    help="responses sampled per task from the train split")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    sources = {}
    for line in (a.data / "source_info.jsonl").read_text(encoding="utf-8").splitlines():
        info = json.loads(line)
        sources[info["source_id"]] = info
    responses = [json.loads(line) for line in
                 (a.data / "response.jsonl").read_text(encoding="utf-8").splitlines()]
    a.out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    for task, name in TASKS.items():
        mine = [r for r in responses if sources[r["source_id"]]["task_type"] == task]
        train = [r for r in mine if r["split"] == "train"]
        splits = {"dev": rng.sample(train, min(a.dev_responses, len(train))),
                  "test": [r for r in mine if r["split"] == "test"]}
        for split, rows in splits.items():
            pairs = [p for r in rows for p in pairs_for(r, sources[r["source_id"]])]
            path = a.out / f"ragtruth-{name}-{split}.jsonl"
            with path.open("w", encoding="utf-8") as f:
                for p in pairs:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")
            counts = Counter(p["label"] for p in pairs)
            print(f"{path.name}: {len(rows)} responses, {len(pairs)} pairs, "
                  f"S {counts['S']} / N {counts['N']} / C {counts['C']}")


if __name__ == "__main__":
    main()
