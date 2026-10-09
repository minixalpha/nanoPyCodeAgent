"""Comparison orchestration must preserve failed trials and preflight gates."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location(
    "run_comparison", Path(__file__).parents[1] / "scripts/run_comparison.py",
)
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


@pytest.mark.parametrize("states", [
    [], [{"exit_code": 0}],
    [{"exit_code": 0, "summary": {"trials": []}}],
    [{"exit_code": 1, "summary": {"trials": [{"status": "setup_passed"}]}}],
    [{"exit_code": 0, "summary": {"trials": [{"status": "setup_failed"}]}}],
])
def test_incomplete_or_failed_preflight_cannot_start_models(states):
    assert not comparison.preflight_passed(states, [1] * len(states))


def test_successful_installation_does_not_require_a_registered_profile():
    state = {"exit_code": 0, "summary": {"trials": [{
        "status": "setup_passed", "bootstrap": {"verifier_preflight": {"status": "not_configured"}},
    }]}}
    assert comparison.preflight_passed([state], [1])
    assert not comparison.preflight_passed([state], [4])
    assert not comparison.preflight_passed([state], [1, 1])


def test_failed_job_is_recorded_and_never_retried(tmp_path, monkeypatch):
    plan = {"arms": {"control": {"source_root": "source"}}}
    job = {"arm": "control", "config": "config.json", "job_name": "test-job"}
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(comparison.subprocess, "run", run)
    first = comparison.run_job(tmp_path, plan, job, tmp_path, False)
    second = comparison.run_job(tmp_path, plan, job, tmp_path, False)
    assert first == second
    assert first["exit_code"] == 1
    assert len(calls) == 1
    assert calls[0][:8] == ["uv", "run", "--project", "benchmarks/harbor", "python", "-m", "harbor_adapter", "run"]


def test_interrupted_job_cannot_silently_restart(tmp_path):
    job = {"job_name": "interrupted"}
    (tmp_path / "interrupted.json").write_text(json.dumps({"status": "started"}))
    with pytest.raises(RuntimeError, match="refusing to retry"):
        comparison.run_job(tmp_path, {}, job, tmp_path, False)
