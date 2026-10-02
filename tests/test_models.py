"""Tests with the real default judge. Run with VERIMEM_TEST_MODELS=1 (downloads ~2 GB once)."""

import csv
from pathlib import Path

import pytest

from verimem.judges.hf import HFNLIJudge
from verimem.policy import Policy
from verimem.types import Label
from verimem.verifier import Verifier

pytestmark = pytest.mark.model
CASES = Path(__file__).resolve().parents[1] / "datasets" / "review-cases.csv"
MODEL = Policy.default().judge.removeprefix("hf:")


@pytest.fixture(scope="module")
def verifier() -> Verifier:
    return Verifier(judge=HFNLIJudge(MODEL), policy=Policy.default())


def test_default_judge_loads_with_a_pinned_revision(verifier):
    verifier.warmup()
    assert "@unresolved" not in verifier.judge.id


def test_review_cases_are_separated(verifier):
    with CASES.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = verifier.check_many([(r["source"], r["claim"]) for r in rows])
    by_label: dict[str, list] = {"S": [], "N": [], "C": []}
    for r, v in zip(rows, out, strict=True):
        by_label[r["label"]].append(v)
    # every true paraphrase is verified, no unstated addition or contradiction is
    assert all(v.label is Label.SUPPORTED for v in by_label["S"])
    assert not any(v.label is Label.SUPPORTED for v in by_label["N"] + by_label["C"])
