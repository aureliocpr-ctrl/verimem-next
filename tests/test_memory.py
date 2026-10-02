from collections.abc import Sequence

import pytest

from conftest import FakeJudge, make_policy
from verimem.memory import Item, Memory
from verimem.types import Label, Status
from verimem.verifier import Verifier

SRC = "Maria told us she moved from Rome to Milan in 2021 for a job at a bank."


class FakeRelevance:
    """Relevance by keyword pairs: a passage answers a question when the question contains
    one word of a pair and the passage the other."""

    id = "fake-relevance"

    def __init__(self, pairs: dict[str, str]) -> None:
        self.pairs = pairs

    def score(self, question: str, passages: Sequence[str]) -> list[float]:
        q = question.lower()
        return [0.9 if any(k in q and v in p for k, v in self.pairs.items()) else 0.05
                for p in passages]


def make_memory(judge=None, relevance=None, path=":memory:", **policy) -> Memory:
    v = Verifier(judge=judge or FakeJudge(), policy=make_policy(**policy))
    return Memory(path, verifier=v, relevance=relevance)


def test_supported_claim_is_verified_with_evidence_and_provenance():
    m = make_memory()
    r = m.remember("Maria moved to Milan in 2021.", source=SRC, origin="chat:42")
    assert r.status is Status.VERIFIED and r.verified
    fact = m.get(r.fact_id)
    assert fact.evidence is not None and "Milan in 2021" in fact.evidence.text
    assert fact.source_origin == "chat:42" and fact.source_author == "user"
    assert fact.judge == "fake:v1" and fact.policy == "test"


def test_unsupported_claim_is_quarantined_and_not_served_by_default():
    m = make_memory()
    r = m.remember("Maria works as a financial analyst.", source=SRC)
    assert r.status is Status.QUARANTINED
    assert m.recall("Maria analyst") == []
    hits = m.recall("Maria analyst", include=[Status.QUARANTINED])
    assert [h.fact.id for h in hits] == [r.fact_id]


def test_claim_without_source_is_unverified():
    r = make_memory().remember("Maria likes jazz.")
    assert r.status is Status.UNVERIFIED and r.verdict.label is Label.UNJUDGED


def test_duplicate_verified_claim_returns_the_existing_fact():
    m = make_memory()
    a = m.remember("Maria moved to Milan in 2021.", source=SRC)
    b = m.remember("maria moved to milan in 2021", source=SRC + " She is happy.")
    assert b.duplicate_of == a.fact_id and b.fact_id == a.fact_id
    assert m.stats()["facts"] == {"verified": 1}


def test_newer_fact_on_a_subject_supersedes_the_older_one():
    m = make_memory()
    old = m.remember("The user lives in Rome.", source="User: the user lives in Rome.",
                     subject="user.city", observed_at="2025-01-10")
    new = m.remember("The user lives in Milan.", source="User: the user lives in Milan now.",
                     subject="user.city", observed_at="2026-03-01")
    assert new.superseded == (old.fact_id,)
    assert m.get(old.fact_id).status is Status.SUPERSEDED
    assert m.get(old.fact_id).superseded_by == new.fact_id
    assert [f.text for f in m.history("user.city")] == ["The user lives in Rome.",
                                                         "The user lives in Milan."]
    assert [h.fact.id for h in m.recall("user lives")] == [new.fact_id]


def test_an_older_fact_arriving_late_is_history_from_the_start():
    m = make_memory()
    new = m.remember("The user lives in Milan.", source="User: the user lives in Milan now.",
                     subject="user.city", observed_at="2026-03-01")
    late = m.remember("The user lives in Rome.", source="User: the user lives in Rome.",
                      subject="user.city", observed_at="2025-01-10")
    assert late.status is Status.SUPERSEDED
    assert m.get(new.fact_id).status is Status.VERIFIED


def test_human_review_can_verify_or_reject():
    m = make_memory()
    q = m.remember("Maria works as a financial analyst.", source=SRC)
    assert [f.id for f in m.review_queue()] == [q.fact_id]
    approved = m.review(q.fact_id, approve=True, reviewer="aurelio")
    assert approved.status is Status.VERIFIED and approved.reviewed_by == "aurelio"
    assert m.review_queue() == []
    with pytest.raises(ValueError):
        m.review(q.fact_id, approve=False, reviewer="aurelio")  # verified: not reviewable
    u = m.remember("Maria likes jazz.")
    with pytest.raises(ValueError):
        m.review(u.fact_id, approve=True, reviewer="  ")
    assert m.review(u.fact_id, approve=False, reviewer="ops").status is Status.REJECTED


def test_recall_matches_inflected_italian_words():
    m = make_memory()
    m.remember("Il fornitore ha consegnato i pezzi.", source="Il fornitore ha consegnato i pezzi.")
    hits = m.recall("pezzi consegnati")
    assert len(hits) == 1


def test_recall_matches_english_inflections():
    m = make_memory()
    fact = "Orders above 50 euros ship for free."
    m.remember(fact, source=fact)
    assert [h.fact.text for h in m.recall("shipping on a 60 euro order")] == [fact]


def test_ask_answers_with_relevant_facts_or_abstains():
    rel = FakeRelevance({"move": "Milan"})
    m = make_memory(relevance=rel)
    m.remember("Maria moved to Milan in 2021.", source=SRC)
    m.remember("Maria had a job at a bank.", source=SRC)
    a = m.ask("Where did Maria move to?")
    assert not a.abstained and [r.fact.text for r in a.facts] == ["Maria moved to Milan in 2021."]
    b = m.ask("What is Maria's salary?")
    assert b.abstained and "best relevance" in b.reason
    c = m.ask("Who won the 2018 World Cup?")
    assert c.abstained and "shares words" in c.reason


def test_ask_does_not_use_unverified_facts():
    m = make_memory(relevance=FakeRelevance({"jazz": "jazz"}))
    m.remember("Maria likes jazz.")  # no source: unverified
    assert m.ask("Does Maria like jazz?").abstained


def test_remember_many_uses_one_judge_call():
    judge = FakeJudge()
    m = make_memory(judge)
    out = m.remember_many([Item("Maria moved to Milan.", SRC),
                           Item("Maria had a job at a bank.", SRC),
                           Item("Maria owns a boat.", SRC)])
    assert [r.status for r in out] == [Status.VERIFIED, Status.VERIFIED, Status.QUARANTINED]
    assert len(judge.calls) == 1


def test_bad_inputs_are_rejected():
    m = make_memory()
    with pytest.raises(ValueError):
        m.remember("   ", source=SRC)
    with pytest.raises(ValueError):
        m.remember("Maria moved.", source=SRC, author="hacker")
    with pytest.raises(ValueError):
        m.remember("Maria moved.", source=SRC, observed_at="last tuesday")
    with pytest.raises(KeyError):
        m.review("nope", approve=True, reviewer="x")


def test_store_survives_reopening(tmp_path):
    path = tmp_path / "mem.db"
    with make_memory(path=path) as m:
        r = m.remember("Maria moved to Milan in 2021.", source=SRC)
    with make_memory(path=path) as m:
        assert m.get(r.fact_id).status is Status.VERIFIED
        assert m.stats()["audit_chain_ok"] is True
