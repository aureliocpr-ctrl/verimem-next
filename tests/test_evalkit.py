import json
import random

import pytest

from conftest import FakeJudge, make_policy
from verimem.evalkit import (
    Pair,
    auroc,
    bootstrap_ci,
    calibrate,
    evaluate_ask,
    evaluate_verifier,
    held_out,
    load_pairs,
    render_verifier_report,
    threshold_for_loss,
)
from verimem.judges import NLIScores
from verimem.memory import Memory
from verimem.verifier import Verifier


def test_auroc_basics():
    assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auroc([0.1], [0.9]) == 0.0
    assert auroc([0.5], [0.5]) == 0.5


def test_bootstrap_interval_contains_the_estimate():
    rng = random.Random(1)
    pos = [rng.gauss(1, 1) for _ in range(60)]
    neg = [rng.gauss(0, 1) for _ in range(60)]
    lo, hi = bootstrap_ci(pos, neg, rounds=300)
    assert lo < auroc(pos, neg) < hi


def test_threshold_for_loss_targets_the_expected_share():
    scores = [i / 100 for i in range(100)]
    th = threshold_for_loss(scores, 0.08)
    assert 0.06 <= sum(s < th for s in scores) / len(scores) <= 0.09


def test_held_out_on_a_perfect_separator_admits_nothing_unstated():
    support = [0.9 + i / 1000 for i in range(60)] + [0.1 + i / 1000 for i in range(60)]
    labels = ["S"] * 60 + ["N"] * 60
    ho = held_out(support, labels)
    assert ho.unstated_admitted == 0.0
    assert ho.true_lost <= 0.10


def test_load_pairs_accepts_italian_headers_and_semicolons(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("﻿id;lingua;fonte;fatto;etichetta\n1;IT;a b;a;S\n2;IT;a b;c;n\n3;;;x;S\n",
                 encoding="utf-8")
    pairs = load_pairs(p)
    assert [(q.id, q.label, q.lang) for q in pairs] == [("1", "S", "it"), ("2", "N", "it")]


def pairs() -> list[Pair]:
    out = []
    for i in range(30):
        out.append(Pair(f"Fact {i} says alpha{i} beta{i}.", f"alpha{i} beta{i}", "S", "en",
                        f"s{i}"))
        out.append(Pair(f"Fact {i} says alpha{i}.", f"alpha{i} gamma{i}", "N", "en", f"n{i}"))
    return out


def test_evaluate_verifier_reports_rates_and_errors():
    v = Verifier(judge=FakeJudge(), policy=make_policy())
    rep, verdicts = evaluate_verifier(v, pairs(), bootstrap_rounds=100)
    assert rep.n == {"S": 30, "N": 30, "C": 0}
    assert rep.auroc_s_vs_n == 1.0
    assert rep.supported_rate["S"] == 1.0 and rep.supported_rate["N"] == 0.0
    assert rep.errors == [] and len(verdicts) == 60


def test_calibrate_picks_a_threshold_between_the_classes():
    def graded(premise, hypothesis):
        i = int(hypothesis.split("alpha")[1].split()[0])
        return NLIScores(entailment=0.6 + i / 100 if "beta" in hypothesis else 0.1 + i / 200)

    v = Verifier(judge=FakeJudge(graded), policy=make_policy())
    th, prov = calibrate(v, pairs())
    assert 0.25 < th.support <= 0.66
    assert th.uncertain <= th.support
    assert prov["held_out_unstated_admitted"] == 0.0


def test_calibrate_refuses_tiny_sets():
    v = Verifier(judge=FakeJudge(), policy=make_policy())
    with pytest.raises(ValueError):
        calibrate(v, pairs()[:6])


def test_evaluate_ask_counts_answers_and_abstentions(tmp_path):
    qa = {"facts": [{"id": "f1", "text": "Laura works at Finvia."},
                    {"id": "f2", "text": "Laura drives a Panda."}],
          "questions": [{"q": "Where does Laura work?", "answer": ["f1"]},
                        {"q": "What does Laura drive?", "answer": ["f2"]},
                        {"q": "How old is Laura?", "answer": []},
                        {"q": "Capital of Peru?", "answer": []}]}
    path = tmp_path / "qa.json"
    path.write_text(json.dumps(qa))

    class Rel:
        id = "rel"

        def score(self, question, passages):
            pairs_ = {"work": "Finvia", "drive": "Panda"}
            return [0.9 if any(k in question and v in p for k, v in pairs_.items()) else 0.1
                    for p in passages]

    v = Verifier(judge=FakeJudge(), policy=make_policy(relevance_threshold=0.5))
    rep = evaluate_ask(lambda: Memory(verifier=v, relevance=Rel()), path)
    assert (rep.answered_right, rep.wrong_abstentions, rep.right_abstentions,
            rep.false_answers) == (2, 0, 2, 0)
    assert rep.auroc == 1.0
    # "How old is Laura?" gets both Laura facts as related (0.1 is above the 0.05 floor)
    assert (rep.right_in_related, rep.unanswerable_with_related) == (0, 1)


def test_evaluate_ask_counts_right_facts_handed_over_as_related(tmp_path):
    qa = {"facts": [{"id": "f1", "text": "Laura works at Finvia."}],
          "questions": [{"q": "Where is Laura employed?", "answer": ["f1"]}]}
    path = tmp_path / "qa.json"
    path.write_text(json.dumps(qa))

    class Rel:
        id = "rel"

        def score(self, question, passages):
            return [0.2 for _ in passages]  # related, not confirmed as an answer

    v = Verifier(judge=FakeJudge(), policy=make_policy(relevance_threshold=0.5))
    rep = evaluate_ask(lambda: Memory(verifier=v, relevance=Rel()), path)
    assert (rep.answered_right, rep.wrong_abstentions, rep.right_in_related) == (0, 1, 1)


def test_report_lists_false_accepts_before_misses():
    misses = [Pair(f"Alpha{i} beta{i}.", f"alpha{i} gamma{i}", "S", "en", f"s{i}")
              for i in range(20)]
    accept = Pair("Delta epsilon zeta.", "delta epsilon", "N", "en", "n0")
    v = Verifier(judge=FakeJudge(), policy=make_policy())
    rep, _ = evaluate_verifier(v, [*misses, accept], bootstrap_rounds=20)
    md = render_verifier_report(rep, dataset="d", command="c")
    assert "Verified although labelled N or C (1 of 1)" in md
    assert "Not verified although labelled S (15 of 20)" in md
    assert md.index("delta epsilon") < md.index("alpha0 gamma0")


def test_load_pairs_keeps_the_lines_of_a_multi_line_source(tmp_path):
    p = tmp_path / "m.csv"
    p.write_bytes(b'source,claim,label\n"User: hi\r\nAgent: hello\nUser: I live in Turin",'
                  b"The user lives in Turin.,S\n")
    [pair] = load_pairs(p)
    assert pair.source.splitlines() == ["User: hi", "Agent: hello", "User: I live in Turin"]


def test_load_pairs_reads_json_lines_holding_a_unicode_line_separator(tmp_path):
    p = tmp_path / "m.jsonl"
    row = {"source": "Line one line two.", "claim": "Line one.", "label": "S"}
    p.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    assert [q.source for q in load_pairs(p)] == ["Line one line two."]
