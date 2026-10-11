"""Prevent infrastructure failures and incomplete accounting from becoming wins."""

import importlib.util
from pathlib import Path
import sys

import pytest


scripts = Path(__file__).parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("collect_comparison", scripts / "collect_comparison.py")
collector = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(scripts))
try:
    spec.loader.exec_module(collector)
finally:
    sys.path.remove(str(scripts))


def test_native_zero_preserved_when_tests_never_started():
    result = {"verifier_result": {"rewards": {"reward": 0.0}}}
    audit = {"score_classification": "verifier_dependency_error",
             "score_valid_for_capability_comparison": False}
    row = collector.classify(result, audit)
    assert row["native_status"] == "scored"
    assert row["native_reward"] == 0
    assert row["status"] == "verifier_error"
    assert row["reward"] is None
    assert not row["eligible_as_independent_capability_evidence"]


def test_missing_usage_is_not_zero_cost_or_complete():
    unknown = collector.accounting({})
    assert unknown == {"known_cost_usd": None, "cost_complete": False, "usage_complete": False}
    partial = collector.accounting({"extra": {"known_cost_usd": 0.12, "cost_is_partial": True}})
    assert partial == {"known_cost_usd": 0.12, "cost_complete": False, "usage_complete": False}


def test_accounted_zero_is_distinct_from_missing_cost():
    metrics = {"total_cost_usd": 0.0, "total_prompt_tokens": 0,
               "total_completion_tokens": 0, "total_cached_tokens": 0}
    assert collector.accounting(metrics) == {
        "known_cost_usd": 0.0, "cost_complete": True, "usage_complete": True,
    }


def test_common_comparison_excludes_invalid_controls_and_exposed_candidates():
    rows = [dict(arm=a, task=t, repeat=1, eligible_as_independent_capability_evidence=True)
            for a in ("control", "verification", "operations") for t in ("infra", "exposed", "valid")]
    rows[0]["eligible_as_independent_capability_evidence"] = False
    rows[4]["eligible_as_independent_capability_evidence"] = False
    assert collector.common_cases(rows, ["control", "verification", "operations"]) == {("valid", 1)}


def test_unreviewed_scores_are_not_eligible():
    row = collector.classify({"verifier_result": {"rewards": {"reward": 1}}}, {})
    assert row["reward"] == 1
    assert not row["eligible_as_independent_capability_evidence"]


def test_evidence_modified_since_review_is_rejected(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text('{"value": 1}')
    reviewed_hash = collector.digest(path)
    path.write_text('{"value": 2}')
    with pytest.raises(ValueError, match="Evidence hash mismatch"):
        collector.load_checked(path, reviewed_hash)
