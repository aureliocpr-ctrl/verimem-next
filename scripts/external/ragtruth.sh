#!/usr/bin/env bash
# External validation on RAGTruth (ParticleMedia, MIT): regenerates docs/eval/ragtruth-*.md
# and the bundled strict policy (src/verimem/policies/strict.json).
# Needs response.jsonl and source_info.jsonl from
# https://github.com/ParticleMedia/RAGTruth/tree/main/dataset in DIR (first argument).
# The pairs and the per-pair scores stay in data/external/, which is not committed: the
# sources keep their own licenses.
set -euo pipefail
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1
raw=${1:?usage: scripts/external/ragtruth.sh DIR_WITH_RAGTRUTH_JSONL}
python scripts/external/ragtruth_pairs.py --data "$raw" --out data/external --max-s 600
mkdir -p data/external/scores
for x in summary qa data2txt; do
    verimem eval "data/external/ragtruth-$x-test.jsonl" --markdown "docs/eval/ragtruth-$x.md" \
        --pairs-out "data/external/scores/$x-test.jsonl" > /dev/null
    verimem eval "data/external/ragtruth-$x-test.jsonl" --judge lexical \
        --markdown "docs/eval/ragtruth-$x-lexical.md" > /dev/null
done
# The strict policy: the support threshold that lets through at most 5% of the unsupported
# claims of RAGTruth's train split, Summary and QA (Data2txt describes JSON records, not
# prose). Chosen on the train split, measured on the test split.
cat data/external/ragtruth-summary-dev.jsonl data/external/ragtruth-qa-dev.jsonl \
    > data/external/ragtruth-design-dev.jsonl
verimem calibrate data/external/ragtruth-design-dev.jsonl --max-admitted 0.05 \
    --out src/verimem/policies/strict.json --version 0.9.0-strict.1
for x in summary qa data2txt; do
    verimem eval "data/external/ragtruth-$x-test.jsonl" --policy src/verimem/policies/strict.json \
        --markdown "docs/eval/ragtruth-$x-strict.md" > /dev/null
done
