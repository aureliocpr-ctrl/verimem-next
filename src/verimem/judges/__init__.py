"""Judges score whether a premise (a window of the source) entails a hypothesis (the claim).

A judge is anything with `id`, `is_model`, `three_way` and `score(pairs)`. Only judges with
`is_model=True` can make a fact `verified` (ADR-0004).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class NLIScores:
    """Probabilities for one (premise, hypothesis) pair."""

    entailment: float
    contradiction: float | None = None
    neutral: float | None = None


@runtime_checkable
class Judge(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def is_model(self) -> bool: ...

    @property
    def three_way(self) -> bool: ...

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]: ...


class JudgeUnavailable(RuntimeError):
    """The judge cannot run here (missing extra, model not downloaded, load failure)."""


def load_judge(spec: str, *, allow_download: bool = False) -> Judge:
    """Build a judge from a spec string.

    - ``hf:<model id>`` or ``hf:<model id>@<revision>``: a Hugging Face NLI classifier.
    - ``lexical``: word-overlap baseline (never trusted to verify).
    """
    if spec == "lexical" or spec.startswith("lexical:"):
        from .lexical import LexicalJudge

        return LexicalJudge()
    if spec.startswith("hf:"):
        from .hf import HFNLIJudge

        model, _, revision = spec[3:].partition("@")
        return HFNLIJudge(model, revision=revision or None, allow_download=allow_download)
    raise ValueError(f"unknown judge spec: {spec!r} (expected 'hf:<model>' or 'lexical')")


__all__ = ["Judge", "JudgeUnavailable", "NLIScores", "load_judge"]
