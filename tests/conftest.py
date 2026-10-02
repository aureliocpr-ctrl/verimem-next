from __future__ import annotations

import os
from collections.abc import Callable, Sequence

import pytest

from verimem.judges import JudgeUnavailable, NLIScores
from verimem.policy import Policy, Thresholds
from verimem.text import content_tokens


def cover(premise: str, hypothesis: str) -> NLIScores:
    """Entailment 1 when every content word of the hypothesis is in the premise, else 0."""
    hyp = content_tokens(hypothesis)
    ok = bool(hyp) and hyp <= content_tokens(premise)
    return NLIScores(entailment=1.0 if ok else 0.0)


class FakeJudge:
    """Deterministic stand-in for a model judge, for control-flow tests."""

    is_model = True

    def __init__(self, fn: Callable[[str, str], NLIScores] = cover, *, three_way: bool = False,
                 judge_id: str = "fake:v1", unavailable: str | None = None) -> None:
        self.fn = fn
        self.three_way = three_way
        self.id = judge_id
        self.unavailable = unavailable
        self.calls: list[int] = []

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]:
        if self.unavailable:
            raise JudgeUnavailable(self.unavailable)
        self.calls.append(len(pairs))
        return [self.fn(p, h) for p, h in pairs]


def make_policy(**overrides) -> Policy:
    base = Policy(version="test", judge="fake:v1",
                  thresholds=Thresholds(support=0.5, uncertain=0.2, contradiction=0.8))
    d = base.to_dict()
    return Policy.from_dict({**d, **overrides,
                             "thresholds": overrides.get("thresholds", d["thresholds"])})


@pytest.fixture
def fake_judge() -> FakeJudge:
    return FakeJudge()


def pytest_collection_modifyitems(config, items):
    if os.environ.get("VERIMEM_TEST_MODELS") == "1":
        return
    skip = pytest.mark.skip(reason="set VERIMEM_TEST_MODELS=1 to run tests with real models")
    for item in items:
        if "model" in item.keywords:
            item.add_marker(skip)
