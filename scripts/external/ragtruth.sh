#!/usr/bin/env bash
# External validation on RAGTruth (ParticleMedia, MIT): regenerates docs/eval/ragtruth-*.md.
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
    # train split ("dev"): design data, never reported as a result
    verimem eval "data/external/ragtruth-$x-dev.jsonl" \
        --pairs-out "data/external/scores/$x-dev.jsonl" > /dev/null
    verimem eval "data/external/ragtruth-$x-test.jsonl" --markdown "docs/eval/ragtruth-$x.md" \
        --pairs-out "data/external/scores/$x-test.jsonl" > /dev/null
    verimem eval "data/external/ragtruth-$x-test.jsonl" --judge lexical \
        --markdown "docs/eval/ragtruth-$x-lexical.md" > /dev/null
done
