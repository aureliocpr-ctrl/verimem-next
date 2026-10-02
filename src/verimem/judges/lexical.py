"""Word-overlap baseline. Useful as a sanity control in evaluations: if a dataset is solved by
this, the dataset measures surface overlap, not understanding. Never trusted to verify."""

from __future__ import annotations

from collections.abc import Sequence

from ..text import content_tokens
from . import NLIScores


class LexicalJudge:
    id = "lexical:v1"
    is_model = False
    three_way = False

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]:
        out = []
        for premise, hypothesis in pairs:
            claim = content_tokens(hypothesis)
            share = len(claim & content_tokens(premise)) / len(claim) if claim else 0.0
            out.append(NLIScores(entailment=share))
        return out
