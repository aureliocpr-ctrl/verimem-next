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


def test_code_defaults_match_the_bundled_policy():
    # A Policy built in code (tests, embedders) must behave like the bundled one.
    bundled = Policy.default().to_dict()
    bare = Policy(version=bundled["version"], judge=bundled["judge"]).to_dict()
    assert {k: v for k, v in bare.items() if k != "calibration"} == {
        k: v for k, v in bundled.items() if k != "calibration"}


def test_judge_precision_is_float32_unless_the_policy_says_bfloat16():
    d = Policy.default().to_dict()
    assert Policy.default().judge_dtype == "float32"
    assert Policy.from_dict({**d, "judge_dtype": "bfloat16"}).judge_dtype == "bfloat16"
    with pytest.raises(ValueError, match="judge_dtype"):
        Policy.from_dict({**d, "judge_dtype": "float16"})


def test_bundled_policies_load_by_name():
    assert "default" in Policy.bundled_names()
    assert Policy.load("default") == Policy.default()
    with pytest.raises(FileNotFoundError, match="bundled policies: default"):
        Policy.load("no-such-policy")


def test_a_path_is_always_read_as_a_file(tmp_path):
    p = tmp_path / "default"  # same name as a bundled policy, but a path
    Policy.from_dict({**Policy.default().to_dict(), "version": "mine"}).save(p)
    assert Policy.load(p).version == "mine"
