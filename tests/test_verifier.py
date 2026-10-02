from conftest import FakeJudge, cover, make_policy
from verimem.judges import NLIScores
from verimem.types import Label, Verdict
from verimem.verifier import Verifier

SOURCE = ("Maria told us she moved from Rome to Milan in 2021 for a job at a bank. "
          "She lives near the station.")


def verifier(judge=None, **policy) -> Verifier:
    return Verifier(judge=judge or FakeJudge(), policy=make_policy(**policy))


def test_supported_claim_carries_the_sentence_that_supports_it():
    v = verifier().check(SOURCE, "Maria moved to Milan in 2021.")
    assert v.label is Label.SUPPORTED
    assert v.evidence is not None
    assert SOURCE[v.evidence.start : v.evidence.end] == v.evidence.text
    assert "Milan in 2021" in v.evidence.text
    assert v.judge == "fake:v1" and v.policy == "test"


def test_unstated_detail_is_not_supported():
    v = verifier().check(SOURCE, "Maria works as a financial analyst.")
    assert v.label is Label.NOT_SUPPORTED


def test_missing_quantity_vetoes_even_a_confident_judge():
    always_yes = FakeJudge(lambda p, h: NLIScores(entailment=0.99))
    v = verifier(always_yes).check("We migrated the index last week.",
                                   "The migration cut latency by 40%.")
    assert v.label is Label.NOT_SUPPORTED
    assert "40%" in v.reason
    assert v.checks[0].name == "quantities" and not v.checks[0].passed


def test_numeric_check_can_be_disabled_by_policy():
    always_yes = FakeJudge(lambda p, h: NLIScores(entailment=0.99))
    v = verifier(always_yes, numeric_check=False).check("We migrated last week.",
                                                         "Latency fell by 40%.")
    assert v.label is Label.SUPPORTED


def test_no_source_is_unjudged():
    for source in (None, "", "   "):
        assert verifier().check(source, "Anything at all.").label is Label.UNJUDGED


def test_unavailable_judge_is_unjudged_with_the_reason():
    v = verifier(FakeJudge(unavailable="model not downloaded")).check(SOURCE, "Maria moved.")
    assert v.label is Label.UNJUDGED
    assert "not downloaded" in v.reason


def test_context_reversal_downgrades_to_uncertain():
    def judge(premise, hypothesis):
        if "moved to Friday" in premise:
            return NLIScores(entailment=0.02)
        return cover(premise, hypothesis)

    src = "The demo was planned for Thursday. Update from Anna: it has been moved to Friday."
    v = verifier(FakeJudge(judge)).check(src, "The demo was planned for Thursday.")
    assert v.label is Label.UNCERTAIN
    assert "context" in v.reason
    off = verifier(FakeJudge(judge), context_check=False).check(
        src, "The demo was planned for Thursday.")
    assert off.label is Label.SUPPORTED


def test_a_question_is_never_evidence_on_its_own():
    src = "Luca: Is Maria the new head of sales?\nMaria: I would not bet on it."
    v = verifier(window_sizes=[1], full_source_max_chars=0).check(
        src, "Maria is the new head of sales.")
    assert v.label is Label.NOT_SUPPORTED
    assert v.evidence is None or "?" not in v.evidence.text


def test_a_question_still_gives_context_to_its_answer():
    def judge(premise, hypothesis):
        both = "Where do you live" in premise and "Milan" in premise
        return NLIScores(entailment=1.0 if both else 0.0)

    src = "Assistant: Where do you live now?\nUser: In Milan, since 2021."
    v = verifier(FakeJudge(judge), full_source_max_chars=0).check(
        src, "The user lives in Milan since 2021.")
    assert v.label is Label.SUPPORTED
    assert v.evidence is not None and v.evidence.text == src


def test_a_source_that_only_asks_questions_supports_nothing():
    judge = FakeJudge()
    v = verifier(judge).check("Has Maria moved to Milan? Since when?", "Maria moved to Milan.")
    assert v.label is Label.NOT_SUPPORTED
    assert v.evidence is None and "question" in v.reason
    assert judge.calls == []


def test_three_way_judge_reports_contradictions():
    def judge(premise, hypothesis):
        if "not allergic" in premise and "allergic" in hypothesis:
            return NLIScores(entailment=0.01, contradiction=0.97, neutral=0.02)
        return NLIScores(entailment=0.05, contradiction=0.05, neutral=0.9)

    v = verifier(FakeJudge(judge, three_way=True)).check(
        "The patient is not allergic to penicillin.", "The patient is allergic to penicillin.")
    assert v.label is Label.CONTRADICTED
    assert v.contradiction == 0.97


def test_per_language_thresholds_apply():
    half = FakeJudge(lambda p, h: NLIScores(entailment=0.6))
    strict = {"it": {"support": 0.9, "uncertain": 0.2, "contradiction": 0.8}}
    pol = verifier(half, per_language=strict)
    assert pol.check("Il fornitore ha consegnato i pezzi.", "I pezzi sono stati consegnati "
                     "dal fornitore.").label is Label.UNCERTAIN
    assert pol.check("The supplier delivered the parts.",
                     "The parts were delivered.").label is Label.SUPPORTED


def test_check_many_makes_one_judge_call():
    judge = FakeJudge()
    out = verifier(judge).check_many([(SOURCE, "Maria moved to Milan."),
                                      ("Anna joined the data team.", "Anna joined the team."),
                                      (None, "No source here.")])
    assert [v.label for v in out] == [Label.SUPPORTED, Label.SUPPORTED, Label.UNJUDGED]
    assert len(judge.calls) == 1


def test_long_sources_are_prefiltered_but_keep_the_answer():
    filler = " ".join(f"Line {i} talks about the weather in town." for i in range(40))
    src = filler + " The API limit is 100 requests per minute. " + filler
    v = verifier(max_windows=6).check(src, "The API limit is 100 requests per minute.")
    assert v.label is Label.SUPPORTED
    assert "100 requests" in v.evidence.text


def test_verdict_round_trips_through_dict():
    v = verifier().check(SOURCE, "Maria moved to Milan in 2021.")
    assert Verdict.from_dict(v.to_dict()) == v


def test_empty_claim_is_an_error():
    import pytest

    with pytest.raises(ValueError):
        verifier().check(SOURCE, "  ")


def test_a_verdict_records_the_verimem_version_that_produced_it():
    from verimem import __version__

    v = verifier().check("Maria moved to Milan in 2021.", "Maria moved to Milan.")
    assert v.verimem_version == __version__
    assert Verdict.from_dict(v.to_dict()) == v
    old = {k: x for k, x in v.to_dict().items() if k != "verimem_version"}
    assert Verdict.from_dict(old).verimem_version == ""  # stored before the field existed


def test_the_judge_gets_the_policys_precision_and_names_it():
    import pytest

    from verimem.judges import load_judge

    j = load_judge("hf:some/model@abc", dtype="bfloat16")
    assert j.dtype == "bfloat16" and j.id == "hf:some/model@abc+bfloat16"
    assert load_judge("hf:some/model@abc").id == "hf:some/model@abc"
    with pytest.raises(ValueError, match="float16"):
        load_judge("hf:some/model", dtype="float16")
    v = Verifier(policy=make_policy(judge="hf:some/model", judge_dtype="bfloat16"))
    assert v.judge.dtype == "bfloat16"
