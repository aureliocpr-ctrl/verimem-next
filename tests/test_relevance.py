from collections.abc import Sequence

import pytest

from conftest import FakeJudge, make_policy
from verimem.memory import Memory
from verimem.relevance import HybridRelevance, covers
from verimem.verifier import Verifier


@pytest.mark.parametrize(("question", "passage"), [
    ("Who leads the data platform team?", "Anna leads the data platform team."),
    ("On which day does the team deploy to production?",
     "The team deploys to production on Thursdays."),
    ("Is Laura allergic to anything?", "Laura is allergic to peanuts."),
    ("Come si chiama il gatto di Laura?", "Laura ha un gatto di nome Miele."),
    ("When did Laura move to Bologna?", "Laura moved to Bologna in March 2024."),
    ("Quando si riunisce il comitato?", "Il comitato si riunisce ogni lunedì."),
])
def test_a_passage_that_mentions_everything_asked_covers_the_question(question, passage):
    assert covers(question, passage)


@pytest.mark.parametrize(("question", "passage"), [
    ("Who leads the sales team?", "Anna leads the data platform team."),
    ("Why did Laura move to Bologna?", "Laura moved to Bologna in 2024."),  # reasons: no
    ("When did Laura move to Bologna?", "Laura moved to Bologna."),  # no time in the passage
    ("How many people work at Finvia?", "Laura works at Finvia."),
    ("What is it?", "Anything at all."),  # nothing left to check
    ("How old is Laura?", "Laura moved to Bologna in March 2024."),  # one word is too little
    # The kind of answer asked for ("which car") cannot be checked by matching words:
    ("Which motorbike does Laura ride?", "Laura rides a Vespa every day."),
    ("Quale lingua parla Laura?", "Laura parla tedesco."),
])
def test_a_passage_that_misses_part_of_the_question_does_not(question, passage):
    assert not covers(question, passage)


class FixedRelevance:
    id = "fixed"

    def __init__(self, value: float) -> None:
        self.value = value

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        return [self.value] * len(passages)


def test_hybrid_lifts_covered_passages_and_keeps_the_model_order():
    hybrid = HybridRelevance(FixedRelevance(0.1))
    covered, other = hybrid.score("Who leads the data platform team?",
                                  ["Anna leads the data platform team.", "Anna likes jazz."])
    assert covered == pytest.approx(0.55) and other == pytest.approx(0.1)
    assert hybrid.id == "fixed+coverage"


def make_memory(**policy) -> Memory:
    pol = make_policy(relevance_threshold=0.4, **policy)
    return Memory(verifier=Verifier(judge=FakeJudge(), policy=pol), policy=pol)


def test_ask_answers_a_direct_question_the_model_alone_misses():
    # The fake judge never entails "This text answers the question: ...", like the real
    # model on "Who leads the data platform team?" (0.11).
    fact = "Anna leads the data platform team."
    on = make_memory()
    on.remember(fact, source=fact)
    assert [r.fact.text for r in on.ask("Who leads the data platform team?").facts] == [fact]
    off = make_memory(relevance_coverage=False)
    off.remember(fact, source=fact)
    assert off.ask("Who leads the data platform team?").abstained
