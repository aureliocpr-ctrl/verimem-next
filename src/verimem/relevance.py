"""Answerability: does a stored fact answer a question? Used by `Memory.ask` to abstain.

The default reuses the verifier's NLI judge (no second model to download or license-check):
premise = the fact, hypothesis = a per-language template built from the question.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .judges import Judge
from .text import guess_language


class Relevance(Protocol):
    @property
    def id(self) -> str: ...

    def score(self, question: str, passages: Sequence[str]) -> list[float]: ...


class NLIRelevance:
    """Relevance as entailment of "this text answers the question: <question>"."""

    def __init__(self, judge: Judge, templates: dict[str, str]) -> None:
        if "en" not in templates:
            raise ValueError("relevance templates need at least an 'en' entry")
        self.judge = judge
        self.templates = templates

    @property
    def id(self) -> str:
        return f"nli-relevance:{self.judge.id}"

    def hypothesis(self, question: str) -> str:
        lang = guess_language(question)
        template = self.templates.get(lang, self.templates["en"])
        return template.format(question=" ".join(question.split()))

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        if not passages:
            return []
        h = self.hypothesis(question)
        return [s.entailment for s in self.judge.score([(p, h) for p in passages])]
