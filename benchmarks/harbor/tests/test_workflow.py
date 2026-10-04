"""Standard workflow policy and score/infra separation."""

import json

import pytest

from harbor_adapter.__main__ import standard_config, summarize


def config():
    return {
        "tasks": [{"name": "terminal-bench/test", "ref": "sha256:abc"}],
        "agents": [{"name": "harbor_adapter:NanoPyCodeAgent", "model_name": "test/model"}],
    }


def test_standard_policy_enables_native_verifier_retries_without_agent_retries():
    result = standard_config(config())
    assert result.n_attempts == 1
    assert result.retry.max_retries == 0
    assert result.verifier.import_path == "harbor_adapter:RetryingVerifier"
    assert result.verifier.kwargs == {"max_attempts": 3}
    assert result.verifier_timeout_multiplier == 4


@pytest.mark.parametrize("change", [
    {"retry": {"max_retries": 1}},
    {"verifier_timeout_multiplier": 1},
    {"verifier": {"disable": True}},
    {"verifier": {"import_path": "custom:Verifier"}},
    {"agents": [{"name": "custom:Agent", "model_name": "test/model"}]},
    {"agents": [{"name": "custom:Agent", "import_path": "harbor_adapter:NanoPyCodeAgent", "model_name": "test/model"}]},
    {"agents": []},
    {"agents": [{"name": "harbor_adapter:NanoPyCodeAgent", "model_name": "test/model", "kwargs": {"version": "old"}}]},
])
def test_conflicting_workflows_fail_before_a_run(change):
    with pytest.raises(ValueError):
        standard_config(config() | change)


def test_summary_does_not_turn_infrastructure_failure_into_zero(tmp_path):
    failed = tmp_path / "failed"
    failed.mkdir()
    (failed / "result.json").write_text(json.dumps({"task_name": "qemu", "exception_info": {"exception_type": "AgentSetupTimeoutError"}, "verifier_result": None}))
    scored = tmp_path / "scored"
    scored.mkdir()
    (scored / "result.json").write_text(json.dumps({"task_name": "qemu", "exception_info": None, "verifier_result": {"rewards": {"reward": 0.0}}}))
    rows = summarize(tmp_path)["trials"]
    assert rows[0]["exception_type"] == "AgentSetupTimeoutError"
    assert rows[0]["rewards"] is None
    assert rows[1]["status"] == "scored"
    assert rows[1]["rewards"] == {"reward": 0.0}


def test_install_only_success_is_reported_without_a_score(tmp_path):
    trial = tmp_path / "installed"
    (trial / "agent").mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps({"task_name": "qemu"}))
    (trial / "agent/bootstrap.json").write_text(json.dumps({"status": "ready", "cache_used": True}))
    row, = summarize(tmp_path, install_only=True)["trials"]
    assert row["status"] == "setup_passed"
    assert row["rewards"] is None
    assert row["bootstrap"]["cache_used"] is True


def test_exception_invalidates_a_partial_reward(tmp_path):
    trial = tmp_path / "errored"
    trial.mkdir()
    (trial / "result.json").write_text(json.dumps({
        "exception_info": {"exception_type": "VerifierTimeoutError"},
        "verifier_result": {"rewards": {"reward": 0.0}},
    }))
    row, = summarize(tmp_path)["trials"]
    assert row["status"] == "execution_error"
    assert row["rewards"] is None
