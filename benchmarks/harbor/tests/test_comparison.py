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


def test_low_disk_space_stops_before_recording_or_starting_a_trial(tmp_path, monkeypatch):
    monkeypatch.setattr(comparison.shutil, "disk_usage", lambda path: SimpleNamespace(free=1))
    with pytest.raises(RuntimeError, match="Insufficient free disk"):
        comparison.run_job(tmp_path, {"minimum_free_disk_bytes": 2}, {"job_name": "new"}, tmp_path, False)
    assert not (tmp_path / "new.json").exists()


@pytest.fixture
def batch_images(tmp_path, monkeypatch):
    entry = {"task": "org/task", "image": "owner/task:tag", "image_id": "sha256:expected",
             "repo_digests": ["owner/task@sha256:expected"]}
    (tmp_path / "images.json").write_text(json.dumps({"images": [entry]}))
    (tmp_path / "config.json").write_text(json.dumps({"tasks": [{"name": "org/task"}]}))
    monkeypatch.setattr(comparison.subprocess, "check_output", lambda *a, **k: "sha256:protected\n")
    monkeypatch.setattr(comparison.shutil, "disk_usage", lambda p: SimpleNamespace(free=100))
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(comparison.subprocess, "run", run)
    plan = {"batch_images": {"manifest": "images.json", "storage_path": str(tmp_path),
                              "minimum_free_disk_bytes": 50}}
    manager = comparison.BatchImages(tmp_path, plan, tmp_path)
    return manager, [{"config": "config.json"}], entry, calls


def test_batch_restores_by_digest_and_verifies_identity(batch_images, monkeypatch):
    manager, jobs, entry, calls = batch_images
    sequence = iter([None, {"Id": entry["image_id"], "RepoDigests": entry["repo_digests"]}])
    monkeypatch.setattr(manager, "inspect", lambda image: next(sequence))
    manager.prepare(jobs)
    assert calls == [["docker", "pull", entry["repo_digests"][0]],
                     ["docker", "tag", entry["repo_digests"][0], entry["image"]]]


def test_batch_can_use_existing_verified_range_cache(batch_images, monkeypatch):
    manager, jobs, entry, calls = batch_images
    manager.policy["cache_dir"] = "/cache/images"
    sequence = iter([None, {"Id": entry["image_id"], "RepoDigests": entry["repo_digests"]}])
    monkeypatch.setattr(manager, "inspect", lambda image: next(sequence))
    manager.prepare(jobs)
    assert len(calls) == 1
    assert calls[0][1].endswith("scripts/cache_image.py")
    assert calls[0][2:] == [entry["image"], "--cache", "/cache/images", "--load"]


def test_batch_rejects_a_changed_tag_before_running_jobs(batch_images, monkeypatch):
    manager, jobs, _, _ = batch_images
    monkeypatch.setattr(manager, "inspect", lambda image: {"Id": "sha256:different", "RepoDigests": []})
    with pytest.raises(ValueError, match="differs from registration"):
        manager.prepare(jobs)


def test_batch_preserves_preexisting_images_and_never_forces_eviction(batch_images, monkeypatch):
    manager, jobs, entry, calls = batch_images
    monkeypatch.setattr(manager, "inspect", lambda image: {"Id": entry["image_id"]})
    manager.release(jobs)
    assert calls == [["docker", "image", "rm", entry["image"]],
                     ["docker", "image", "rm", entry["repo_digests"][0]]]
    calls.clear()
    manager.protected.add(entry["image_id"])
    manager.release(jobs)
    assert calls == []


def test_batch_checks_actual_docker_storage_before_downloading(batch_images, monkeypatch):
    manager, jobs, _, calls = batch_images
    monkeypatch.setattr(comparison.shutil, "disk_usage", lambda path: SimpleNamespace(free=1))
    with pytest.raises(RuntimeError, match="Insufficient Docker storage"):
        manager.prepare(jobs)
    assert calls == []


def test_registered_transport_files_cannot_change(tmp_path):
    path = tmp_path / "apt-cache.conf"
    path.write_text("original configuration")
    plan = {"additional_file_sha256": {path.name: comparison.digest(path)},
            "preflight": [], "queue": [], "total_model_runs": 0,
            "max_concurrent_trials": 2, "whole_trial_retries": 0,
            "arms": {}, "tasks": []}
    comparison.validate_plan(tmp_path, tmp_path / "plan.json", plan)
    path.write_text("changed proxy endpoint")
    with pytest.raises(ValueError, match="infrastructure file changed"):
        comparison.validate_plan(tmp_path, tmp_path / "plan.json", plan)


def test_registered_transport_paths_cannot_escape_repository(tmp_path):
    plan = {"additional_file_sha256": {"../outside": "untrusted"}}
    with pytest.raises(ValueError, match="infrastructure file changed"):
        comparison.validate_plan(tmp_path, tmp_path / "plan.json", plan)


@pytest.fixture
def accepted_installation(tmp_path):
    source = tmp_path / "source"
    module = source / "src/nanopycodeagent/agent.py"
    module.parent.mkdir(parents=True)
    module.write_text("# frozen runtime\n")
    trial = source / "jobs/preflight/task__one"
    (trial / "agent").mkdir(parents=True)
    inputs = source / "jobs/preflight-input"
    (inputs / "dist").mkdir(parents=True)
    wheel = inputs / "dist/runtime.whl"
    wheel.write_bytes(b"recorded wheel bytes")
    files = {
        "result": (trial / "result.json", {
            "task_name": "org/task", "task_id": {"ref": "sha256:task"},
            "finished_at": "2026-10-11T00:00:00Z", "exception_info": None,
            "agent_execution": None, "verifier": None, "verifier_result": None,
            "config": {"agent": {"kwargs": {"wheel_path": str(wheel)}}},
        }),
        "bootstrap": (trial / "agent/bootstrap.json", {
            "status": "ready", "stage": "complete",
            "verifier_preflight": {"status": "not_configured"},
            "wheel_sha256": comparison.digest(wheel),
        }),
        "manifest": (inputs / "manifest.json", {
            "commit": "frozen", "wheel_sha256": comparison.digest(wheel),
            "source_sha256": {"nanopycodeagent/agent.py": comparison.digest(module)},
        }),
        "input_config": (inputs / "config.json", {"install_only": True}),
    }
    evidence = {"arm": "main", "task": "org/task", "result_path": str((trial / "result.json").relative_to(tmp_path))}
    for name, (path, data) in files.items():
        path.write_text(json.dumps(data))
        evidence[name + "_sha256"] = comparison.digest(path)
    plan = {
        "preflight": [], "queue": [{"arm": "main", "task": "org/task"}],
        "arms": {"main": {"source_root": "source", "source_ref": "frozen"}},
        "tasks": [{"name": "org/task", "ref": "sha256:task"}],
        "accepted_preflight_trials": [evidence],
    }
    return plan, files, evidence, module, wheel


def test_accept_native_success_even_when_a_sibling_failed(tmp_path, accepted_installation):
    plan, files, _, _, _ = accepted_installation
    sibling = files["result"][0].parent.parent / "failed__two"
    sibling.mkdir()
    (sibling / "result.json").write_text(json.dumps({"exception_info": {"exception_type": "NetworkConnectionError"}}))
    assert comparison.accepted_preflights_passed(tmp_path, plan)
    assert (sibling / "result.json").exists()


@pytest.mark.parametrize("change", ["missing", "duplicate", "mixed"])
def test_every_pair_needs_exactly_one_success(tmp_path, accepted_installation, change):
    plan, _, evidence, _, _ = accepted_installation
    if change == "missing":
        plan["queue"].append({"arm": "main", "task": "org/second"})
    elif change == "duplicate":
        plan["accepted_preflight_trials"].append(evidence.copy())
    else:
        plan["preflight"].append({"job_name": "another"})
    with pytest.raises(ValueError):
        comparison.accepted_preflights_passed(tmp_path, plan)


@pytest.mark.parametrize("field,value", [
    ("exception_info", {"exception_type": "AgentSetupTimeoutError"}),
    ("agent_execution", {"started_at": "2026-10-11T00:00:00Z"}),
    ("verifier_result", {"rewards": {"reward": 1}}),
    ("finished_at", None),
    ("task_id", {"ref": "sha256:different"}),
])
def test_ineligible_trials_cannot_be_accepted(tmp_path, accepted_installation, field, value):
    plan, files, evidence, _, _ = accepted_installation
    path, data = files["result"]
    data[field] = value
    path.write_text(json.dumps(data))
    evidence["result_sha256"] = comparison.digest(path)
    with pytest.raises(ValueError):
        comparison.accepted_preflights_passed(tmp_path, plan)


@pytest.mark.parametrize("changed", ["result", "source", "wheel"])
def test_evidence_and_installed_source_must_still_match(tmp_path, accepted_installation, changed):
    plan, files, _, module, wheel = accepted_installation
    path = files["result"][0] if changed == "result" else module if changed == "source" else wheel
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        comparison.accepted_preflights_passed(tmp_path, plan)


@pytest.mark.parametrize("name,field,value", [
    ("bootstrap", "verifier_preflight", {"status": "pending"}),
    ("manifest", "commit", "another-revision"),
    ("input_config", "install_only", False),
])
def test_required_preflight_mode_and_revision_cannot_be_bypassed(tmp_path, accepted_installation, name, field, value):
    plan, files, evidence, _, _ = accepted_installation
    path, data = files[name]
    data[field] = value
    path.write_text(json.dumps(data))
    evidence[name + "_sha256"] = comparison.digest(path)
    with pytest.raises(ValueError):
        comparison.accepted_preflights_passed(tmp_path, plan)
