import pytest

from verimem.policy import Policy, Thresholds


def test_default_policy_loads_and_names_its_judge():
    p = Policy.default()
    assert p.judge.startswith("hf:")
    assert 0 <= p.thresholds.uncertain <= p.thresholds.support <= 1
    assert "user" in p.trusted_authors and "web" not in p.trusted_authors


def test_round_trip(tmp_path):
    p = Policy.default()
    p.save(tmp_path / "p.json")
    assert Policy.load(tmp_path / "p.json") == p


def test_invalid_thresholds_are_rejected():
    with pytest.raises(ValueError):
        Thresholds(support=1.5)
    with pytest.raises(ValueError):
        Thresholds(support=0.3, uncertain=0.6)


def test_unknown_fields_are_rejected():
    d = Policy.default().to_dict()
    d["typo_field"] = 1
    with pytest.raises(ValueError):
        Policy.from_dict(d)


def test_language_specific_thresholds():
    p = Policy.from_dict({**Policy.default().to_dict(),
                          "per_language": {"it": {"support": 0.7, "uncertain": 0.3,
                                                  "contradiction": 0.8}}})
    assert p.thresholds_for("it").support == 0.7
    assert p.thresholds_for("en") == p.thresholds
