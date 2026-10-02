#!/usr/bin/env bash
# Regenerates every number in docs/EVAL.md and the example report in examples/audit/.
# Needs: pip install -e ".[nli]" and, once, `verimem warmup` (downloads the default judge).
set -euo pipefail
cd "$(dirname "$0")/.."
export HF_HUB_OFFLINE=1
mkdir -p docs/eval

verimem eval datasets/review-cases.csv --markdown docs/eval/review-cases.md
verimem eval datasets/review-cases.csv --judge lexical --markdown docs/eval/review-cases-lexical.md
verimem eval datasets/truthfulqa-pairs.jsonl --markdown docs/eval/truthfulqa.md
verimem eval datasets/truthfulqa-pairs.jsonl --judge lexical --markdown docs/eval/truthfulqa-lexical.md
verimem eval datasets/crosslingual-cases.csv --markdown docs/eval/crosslingual-cases.md
# The strict policy (made by scripts/external/ragtruth.sh) on the paraphrase-heavy sets
verimem eval datasets/review-cases.csv --policy src/verimem/policies/strict.json --markdown docs/eval/review-cases-strict.md
verimem eval datasets/truthfulqa-pairs.jsonl --policy src/verimem/policies/strict.json --markdown docs/eval/truthfulqa-strict.md
verimem eval-ask datasets/qa-mini.json --markdown docs/eval/qa-mini.md
verimem eval-ask datasets/qa-heldout.json --markdown docs/eval/qa-heldout.md
verimem eval examples/audit/pairs.jsonl --markdown docs/eval/example-pairs.md

verimem audit examples/audit/pairs.jsonl --out examples/audit/report-en --lang en
verimem audit examples/audit/pairs.jsonl --out examples/audit/report-it --lang it

# The example's review column is filled from its answer key, to show the last step.
for lang in en it; do
    python examples/audit/fill_review_from_labels.py "examples/audit/report-$lang"
    verimem audit-review "examples/audit/report-$lang" --lang "$lang" > /dev/null
done
