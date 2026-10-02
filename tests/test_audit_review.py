import csv
import json

import pytest

from conftest import FakeJudge, make_policy
from verimem.report import (
    AuditRow,
    audit_pairs,
    load_review,
    render_review_markdown,
    summarize_review,
    write_report,
)
from verimem.verifier import Verifier


def read_csv(path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def report(flagged: int, verified: int, uncertain: int = 0) -> dict:
    rows = ([{"id": f"f{i}", "verdict": "not_supported"} for i in range(flagged)]
            + [{"id": f"v{i}", "verdict": "supported"} for i in range(verified)]
            + [{"id": f"u{i}", "verdict": "uncertain"} for i in range(uncertain)]
            + [{"id": "x", "verdict": "unjudged"}])
    return {"rows": rows}


def test_estimate_weights_each_group_by_its_size():
    rep = report(flagged=10, verified=30)
    # The reviewer finds 9 of 10 flagged memories really unstated, and 3 of 10 sampled
    # verified memories unstated too.
    marks = {f"f{i}": ("no" if i < 9 else "yes") for i in range(10)}
    marks |= {f"v{i}": ("no" if i < 3 else "yes") for i in range(10)}
    s = summarize_review(rep, marks)
    assert s.groups["flagged"] == {"memories": 10, "reviewed": 10, "not_stated": 9}
    assert s.groups["verified"] == {"memories": 30, "reviewed": 10, "not_stated": 3}
    assert s.estimate == pytest.approx(10 / 40 * 0.9 + 30 / 40 * 0.3)
    lo, hi = s.ci
    assert lo < s.estimate < hi


def test_no_estimate_while_a_group_is_unreviewed():
    s = summarize_review(report(flagged=5, verified=5), {"f0": "no", "f1": "sì"})
    assert s.estimate is None and s.ci is None
    assert s.missing_groups == ["verified"]
    assert s.groups["flagged"]["not_stated"] == 1  # "sì" means the source states it


def test_unknown_answers_are_rejected_with_the_row_id():
    with pytest.raises(ValueError, match="f1"):
        summarize_review(report(flagged=2, verified=0), {"f0": "no", "f1": "maybe"})


def test_review_file_round_trip_and_random_order_within_groups(tmp_path):
    rows = [AuditRow(str(i), "Maria moved from Rome to Milan in 2021.",
                     "Maria moved to Milan in 2021." if i % 2 else "Maria is an analyst.")
            for i in range(12)]
    rep = audit_pairs(rows, Verifier(judge=FakeJudge(), policy=make_policy()))
    write_report(rep, tmp_path / "a", lang="en")
    write_report(rep, tmp_path / "b", lang="en")
    order = [r[0] for r in read_csv(tmp_path / "a" / "review.csv")[1:]]
    again = [r[0] for r in read_csv(tmp_path / "b" / "review.csv")[1:]]
    flagged = [str(i) for i in range(0, 12, 2)]
    assert order == again  # reproducible
    assert sorted(order[:6]) == sorted(flagged)  # flagged first
    assert order[:6] != flagged  # shuffled, so the top rows are a random sample

    path = tmp_path / "a" / "review.csv"
    lines = read_csv(path)
    col = lines[0].index("stated_by_source")
    for line in lines[1:4]:
        line[col] = "no"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(lines)
    assert load_review(path) == {line[0]: "no" for line in lines[1:4]}


def test_summary_markdown_in_both_languages():
    marks = {"f0": "no", "f1": "no", "v0": "yes"}
    s = summarize_review(report(flagged=2, verified=2), marks)
    en = render_review_markdown(s, lang="en")
    it = render_review_markdown(s, lang="it")
    assert "not stated by their source" in en and "100%" in en
    assert "non dette dalla loro fonte" in it
    assert json.dumps(s.to_dict())  # serialisable


def test_reviewing_every_memory_leaves_no_sampling_error():
    marks = {f"f{i}": "no" for i in range(4)}
    marks |= {f"v{i}": ("no" if i == 0 else "yes") for i in range(4)}
    s = summarize_review(report(flagged=4, verified=4), marks)
    assert s.estimate == pytest.approx(5 / 8)
    assert s.ci == pytest.approx((5 / 8, 5 / 8))
    assert "every memory was reviewed" in render_review_markdown(s, lang="en")
    assert "tutte le memorie sono state riviste" in render_review_markdown(s, lang="it")


def test_a_small_sample_of_a_large_group_is_uncertain_even_without_errors():
    marks = {f"f{i}": "no" for i in range(5)} | {f"v{i}": "yes" for i in range(5)}
    s = summarize_review(report(flagged=500, verified=500), marks)
    assert s.estimate == pytest.approx(0.5)
    lo, hi = s.ci
    assert hi - lo > 0.1
