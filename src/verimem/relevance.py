"""Answerability: does a stored fact answer a question? Used by `Memory.ask` to abstain.

Two signals. The NLI judge already loaded for verification (premise = the fact, hypothesis =
a per-language template built from the question) understands paraphrase but misses plain
direct questions: "Who leads the data platform team?" scores 0.11 against "Anna leads the
data platform team." Coverage is lexical: a fact covers a question when it mentions
everything the question asks about apart from the answer itself. `HybridRelevance` counts a
covered fact as relevant and otherwise falls back on the model.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise
from typing import Protocol

from .judges import Judge
from .numbers import extract
from .text import content_tokens, guess_language, words


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


# ---------------------------------------------------------------- coverage

# Words that frame a question rather than say what it is about (question words included:
# the stopword lists miss some).
_FRAME = frozenset("""
    whose anything something anyone someone anybody somebody many much long old often kind
    type sort name named called exactly usually currently now still ever yet really please
    tell quale quali qual cosa cos quanto quanta quanti quante qualcosa qualcuno qualche fa
    fare fanno tipo genere nome chiama chiamano chiamato chiamata esattamente solitamente
    attualmente adesso ora
""".split())
# The word after these names the kind of answer ("which car", "che città"). Words cannot
# check that a fact gives that kind of answer, except for times.
_ANSWER_TYPE = frozenset({"which", "what", "che", "quale", "quali"})
_TIME_TYPES = frozenset({"day", "days", "date", "time", "year", "month", "hour", "week",
                         "giorno", "giorni", "data", "anno", "mese", "settimana"})
# Reasons are rarely stated in the words of the question: coverage cannot tell.
_REASON = frozenset({"why", "perché", "perche"})
# Questions whose answer is a time or an amount: the fact must contain one.
_TIME_OR_AMOUNT = frozenset({"when", "quando", "quanto", "quanta", "quanti", "quante"})
_HOW_AMOUNT = frozenset({"many", "much", "long", "old", "often"})
_TIME_WORDS = frozenset("""
    monday tuesday wednesday thursday friday saturday sunday mondays tuesdays wednesdays
    thursdays fridays saturdays sundays weekday weekdays weekend weekends morning mornings
    afternoon evening evenings night nights today yesterday tomorrow daily weekly monthly
    yearly annually every lunedì martedì mercoledì giovedì venerdì sabato domenica
    weekend mattina mattino pomeriggio sera notte oggi ieri domani ogni
""".split())


def _same_word(a: str, b: str) -> bool:
    """Equal, an inflection of each other by prefix (lead/leads, use/uses), or sharing a
    long stem (vegetariano/vegetariana)."""
    if a == b:
        return True
    short, long_ = sorted((a, b), key=len)
    if len(short) >= 3 and long_.startswith(short):
        return True
    common = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        common += 1
    return common >= 5


def _asks_for_time_or_amount(ws: list[str]) -> bool:
    if any(w in _TIME_OR_AMOUNT for w in ws):
        return True
    pairs = set(pairwise(ws))
    return (any(("how", w) in pairs for w in _HOW_AMOUNT)
            or ("what", "time") in pairs or ("che", "ora") in pairs)


def covers(question: str, passage: str) -> bool:
    """True when `passage` mentions everything `question` asks about, apart from the answer.

    It declines (and leaves the question to the model) when it cannot tell: reasons
    ("why"), a kind of answer other than a time ("which car"), or fewer than two words to
    match. For "when", "how many", "which day" and the like the passage must also contain a
    time, a date or an amount."""
    ws = words(question)
    if not ws or any(w in _REASON for w in ws):
        return False
    asked = set(content_tokens(question)) - _FRAME
    wants_time = _asks_for_time_or_amount(ws)
    for w, nxt in pairwise(ws):
        if w in _ANSWER_TYPE and nxt in asked:
            if nxt not in _TIME_TYPES:
                return False
            asked.discard(nxt)
            wants_time = True
    if len(asked) < 2:
        return False
    have = content_tokens(passage)
    if not all(any(_same_word(a, h) for h in have) for a in asked):
        return False
    if wants_time:
        return bool(extract(passage)) or any(w in _TIME_WORDS for w in words(passage))
    return True


class HybridRelevance:
    """A covered fact is relevant: its score is lifted to at least 0.5, still ordered by the
    model's score. Anything else keeps the model's score."""

    def __init__(self, model: Relevance) -> None:
        self.model = model

    @property
    def id(self) -> str:
        return f"{self.model.id}+coverage"

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        scores = self.model.score(question, passages)
        return [max(s, 0.5 + s / 2) if covers(question, p) else s
                for s, p in zip(scores, passages, strict=True)]
