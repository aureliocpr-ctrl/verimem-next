"""The invariants of docs/DESIGN.md §3, as tests."""

import hmac
import itertools
import json

import pytest

from conftest import FakeJudge, cover, make_policy
from verimem.judges import NLIScores
from verimem.judges.lexical import LexicalJudge
from verimem.memory import Memory, status_for
from verimem.types import Label, Status, Verdict
from verimem.verifier import Verifier

SRC = "Maria told us she moved from Rome to Milan in 2021 for a job at a bank."


def memory(judge, path=":memory:") -> Memory:
    return Memory(path, verifier=Verifier(judge=judge, policy=make_policy()))


def verdict(label: Label) -> Verdict:
    return Verdict(label=label, support=0.9, contradiction=None, evidence=None, checks=(),
                   judge="j", policy="p", language="en", reason="r")


@pytest.mark.parametrize(("label", "trusted", "model"),
                         list(itertools.product(Label, [True, False], [True, False])))
def test_verified_only_from_a_trusted_source_and_a_model_judge(label, trusted, model):
    status, _ = status_for(verdict(label), trusted_source=trusted, judge_is_model=model)
    expected = label is Label.SUPPORTED and trusted and model
    assert (status is Status.VERIFIED) == expected


def test_a_heuristic_judge_never_verifies():
    m = memory(LexicalJudge())
    r = m.remember("Maria moved from Rome to Milan.", source=SRC)
    assert r.verdict.label is Label.SUPPORTED
    assert r.status is Status.UNVERIFIED


@pytest.mark.parametrize("author", ["web", "tool", "agent"])
def test_untrusted_sources_never_verify(author):
    m = memory(FakeJudge())
    r = m.remember("Maria moved to Milan.", source=SRC, author=author)
    assert r.status is Status.UNVERIFIED
    assert "not trusted" in m.get(r.fact_id).reason


def test_an_unavailable_judge_never_verifies():
    r = memory(FakeJudge(unavailable="no model here")).remember("Maria moved to Milan.",
                                                                source=SRC)
    assert r.status is Status.UNVERIFIED and r.verdict.label is Label.UNJUDGED


def test_forget_erases_text_from_the_database_file(tmp_path):
    path = tmp_path / "mem.db"
    # long enough to spill into overflow pages, which SQLite frees (but would not wipe
    # without secure_delete) when the text is removed
    filler = " ".join(f"Note {i} about ZEPHYRQUILL logistics." for i in range(400))
    secret_source = f"Codename ZEPHYRQUILL: Maria moved to Milan in 2021. {filler}"
    with memory(FakeJudge(), path) as m:
        r = m.remember("Maria moved to Milan in 2021 (ZEPHYRQUILL).", source=secret_source,
                       subject="maria.city")
        m.forget(r.fact_id, reason="user request")
        assert m.get(r.fact_id).status is Status.FORGOTTEN
        assert m.get(r.fact_id).text == ""
        assert m.audit.verify().ok
        events = json.dumps(m.audit.tail(10))
        assert "ZEPHYRQUILL" not in events and "zephyrquill" not in events
    raw = b"".join(p.read_bytes() for p in tmp_path.iterdir() if p.is_file())
    assert b"ZEPHYRQUILL" not in raw and b"zephyrquill" not in raw


def test_forget_leaves_nothing_of_a_duplicate_writes_source(tmp_path):
    # Writing a known fact again adds nothing to the memory, so once the fact is forgotten
    # no trace of the second source may be left in the file.
    with memory(FakeJudge(), tmp_path / "m.db") as m:
        a = m.remember("Maria moved to Milan.", source=SRC)
        b = m.remember("Maria moved to Milan.",
                       source="Call of 3 May, case QUILLMARK: Maria moved to Milan.")
        assert b.duplicate_of == a.fact_id
        m.forget(a.fact_id)
    raw = b"".join(p.read_bytes() for p in tmp_path.iterdir() if p.is_file())
    assert b"QUILLMARK" not in raw


def test_after_forget_every_keyed_hash_of_its_words_lost_its_key(tmp_path, monkeypatch):
    # Whatever the construction, a keyed hash computed from the forgotten words (or from
    # such a hash) and still in the file must have a key that is no longer in the file.
    computed = []
    real_new = hmac.new

    def spy(key, msg=None, digestmod=None):
        h = real_new(key, msg, digestmod)
        computed.append((bytes(key), bytes(msg or b""), h.hexdigest()))
        return h

    monkeypatch.setattr(hmac, "new", spy)
    claim, reason = "Maria moved to Milan in 2021.", "asked by Maria on the phone"
    other = "Call of 3 May: Maria moved to Milan in 2021, she said."
    with memory(FakeJudge(), tmp_path / "m.db") as m:
        r = m.remember(claim, source=SRC, origin="chat:42")
        m.remember(claim, source=other)
        m.remember("Maria had a job at a bank.", source="Maria: I had a job at a bank.")
        m.forget(r.fact_id, reason=reason)
    raw = b"".join(p.read_bytes() for p in tmp_path.iterdir() if p.is_file())
    tainted: set[str] = set()
    for key, msg, digest in computed:
        text = msg.decode("utf-8", "replace")
        if any(w in text for w in (claim, reason, SRC, other)) or any(t in text for t in tainted):
            tainted.add(digest)
            if digest.encode() in raw:
                assert key.hex().encode() not in raw and key not in raw, digest
    assert tainted


def test_after_forget_no_score_is_left_to_confirm_a_guess(tmp_path):
    # Rerun on the exact claim and source, the judge reproduces the score: a score left in
    # the file would confirm a guess about the forgotten fact.
    def judge(premise: str, hypothesis: str) -> NLIScores:
        return NLIScores(entailment=0.873461 if cover(premise, hypothesis).entailment else 0.0)

    with memory(FakeJudge(judge), tmp_path / "m.db") as m:
        r = m.remember("Maria moved to Milan in 2021.", source=SRC)
        assert r.verdict.support == pytest.approx(0.873461)
        m.forget(r.fact_id)
        assert m.get(r.fact_id).support == 0.0
        assert "0.87" not in json.dumps(m.audit.tail(10))


def test_source_text_survives_while_another_fact_uses_it(tmp_path):
    with memory(FakeJudge(), tmp_path / "m.db") as m:
        a = m.remember("Maria moved to Milan in 2021.", source=SRC)
        b = m.remember("Maria had a job at a bank.", source=SRC)
        source_id = m.get(b.fact_id).source_id
        m.forget(a.fact_id)
        assert m.get(a.fact_id).source_id is None
        assert m.store.get_source(source_id)["text"] == SRC
        m.forget(b.fact_id)
        assert m.get(b.fact_id).source_id is None
        assert m.store.get_source(source_id) is None
        assert m.store.count("sources") == 0


def test_audit_chain_detects_tampering(tmp_path):
    with memory(FakeJudge(), tmp_path / "m.db") as m:
        for claim in ("Maria moved to Milan.", "Maria had a job at a bank.", "Maria owns a boat."):
            m.remember(claim, source=SRC)
        assert m.audit.verify().ok
        with m.store.transaction() as c:
            c.execute("UPDATE events SET payload = replace(payload, 'quarantined', 'verified') "
                      "WHERE seq = 3")
        check = m.audit.verify()
        assert not check.ok and check.first_bad == 3
