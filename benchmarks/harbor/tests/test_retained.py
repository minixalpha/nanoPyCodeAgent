"""Retained verifier batches must preserve previously published evidence."""

import asyncio
import json
import hashlib
import shlex
import subprocess
import sys
from unittest.mock import Mock

import pytest

from harbor_adapter.retained import hashes
from harbor_adapter.verifier import _RUNNER


@pytest.mark.parametrize("timeout", [False, True])
def test_batch_restores_old_attempts_and_keeps_new_logs_separate(tmp_path, timeout):
    logs = tmp_path / "logs"
    (logs / "attempts/1").mkdir(parents=True)
    (logs / "attempts/1/test-stdout.txt").write_text("original attempt\n")
    (logs / "retry-summary.json").write_text('{"old": true}\n')
    (logs / "reward.txt").write_text("1\n")
    before = hashes(logs)
    archive = tmp_path / "batch"
    command = f"echo 0 > {shlex.quote(str(logs / 'reward.txt'))}"
    if timeout:
        command += "; sleep 10"
    result = subprocess.run([
        sys.executable, "-c", _RUNNER, "batch", str(archive), command,
        "0.1", "3", "0", "0", str(logs), str(tmp_path / "control.pid"),
    ], capture_output=True, text=True, check=True)
    assert hashes(logs) == before
    summary = json.loads((archive / "verifier/retry-summary.json").read_text())
    assert len(summary["attempts"]) == (3 if timeout else 1)
    assert json.loads(result.stdout)["status"] == ("timeout" if timeout else "completed")
    assert (archive / "verifier/reward.txt").exists() is not timeout
    assert (archive / "verifier/attempts/1/reward.txt").read_text() == "0\n"


def test_batch_restores_original_logs_if_runner_raises(tmp_path):
    from harbor_adapter._verifier_runner import run_batch

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.txt").write_text("original evidence")
    before = hashes(logs)
    # An unavailable control directory fails before any verifier process starts.
    with pytest.raises(FileNotFoundError):
        run_batch("true", 1, 3, logs, tmp_path / "absent/control.pid", tmp_path / "batch")
    assert hashes(logs) == before


def test_batch_refuses_to_overwrite_an_existing_archive(tmp_path):
    from harbor_adapter._verifier_runner import run_batch

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.txt").write_text("original evidence")
    before = hashes(logs)
    archive = tmp_path / "batch"
    archive.mkdir()
    with pytest.raises(FileExistsError):
        run_batch("true", 1, 3, logs, tmp_path / "control.pid", archive)
    assert hashes(logs) == before


def test_cancelled_batch_restores_original_evidence(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.txt").write_text("original evidence")
    before = hashes(logs)
    archive, control = tmp_path / "batch", tmp_path / "control.pid"
    ready = tmp_path / "ready"
    command = f"touch {shlex.quote(str(ready))}; sleep 30"

    async def cancel():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-c", _RUNNER, "batch", str(archive), command,
            "10", "3", "0", "0", str(logs), str(control),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        async with asyncio.timeout(5):
            while not ready.exists():
                await asyncio.sleep(0.01)
        cleanup = await asyncio.create_subprocess_exec(
            sys.executable, "-c", _RUNNER, "cancel", str(control),
        )
        assert await cleanup.wait() == 0
        await asyncio.wait_for(process.communicate(), 5)
        assert process.returncode != 0

    asyncio.run(cancel())
    assert hashes(logs) == before
    summary = json.loads((archive / "verifier/retry-summary.json").read_text())
    assert [a["status"] for a in summary["attempts"]] == ["cancelled"]


def test_retained_batch_waits_for_dependency_services(monkeypatch):
    from harbor_adapter.retained import wait_for_services

    inspect = Mock(side_effect=[
        json.dumps([{"State": {"Running": True, "Health": {"Status": "starting"}}}]),
        json.dumps([{"State": {"Running": True, "Health": {"Status": "healthy"}}}]),
    ])
    monkeypatch.setattr("harbor_adapter.retained.docker", inspect)
    monkeypatch.setattr("harbor_adapter.retained.time.sleep", lambda _: None)
    wait_for_services(["cache-service"])
    assert inspect.call_count == 2


def test_retained_batch_rejects_failed_services(monkeypatch):
    from harbor_adapter.retained import wait_for_services

    monkeypatch.setattr("harbor_adapter.retained.docker", lambda *args: json.dumps([
        {"State": {"Running": False}},
    ]))
    with pytest.raises(RuntimeError, match="failed to start"):
        wait_for_services(["cache-service"])


@pytest.mark.parametrize("reward", ["0", "1", "invalid", "nan", None])
def test_retained_result_distinguishes_valid_scores_from_verifier_errors(tmp_path, reward):
    from harbor_adapter.retained import batch_result

    (tmp_path / "verifier").mkdir()
    if reward is not None:
        (tmp_path / "verifier/reward.txt").write_text(reward)
    result = batch_result(tmp_path, {"status": "completed"})
    valid = reward in {"0", "1"}
    assert result["status"] == ("scored" if valid else "verifier_error")
    assert result["rewards"] == ({"reward": float(reward)} if valid else None)


def test_retained_timeout_does_not_publish_an_archived_reward(tmp_path):
    from harbor_adapter.retained import batch_result

    (tmp_path / "verifier").mkdir()
    (tmp_path / "verifier/reward.txt").write_text("1")
    assert batch_result(tmp_path, {"status": "timeout"})["rewards"] is None


@pytest.mark.parametrize("preparation", ["sleep 1", "exit 2", "sleep 10"])
def test_dependency_preparation_has_its_own_budget_and_gates_verification(tmp_path, preparation):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.txt").write_text("original evidence")
    before = hashes(logs)
    archive = tmp_path / "batch"
    marker = tmp_path / "verification-started"
    command = f"touch {shlex.quote(str(marker))}; echo 0 > {shlex.quote(str(logs / 'reward.txt'))}"
    result = subprocess.run([
        sys.executable, "-c", _RUNNER, "prepared-batch", str(archive), preparation,
        "2", command, "0.5", "1", "0", "0", str(logs), str(tmp_path / "control.pid"),
    ], capture_output=True, text=True, check=True)
    record = json.loads(result.stdout)
    success = preparation == "sleep 1"
    assert marker.exists() is success
    assert hashes(logs) == before
    if success:
        assert record["preparation"]["duration_seconds"] > 0.5
        assert record["verification"]["status"] == "completed"
        assert (archive / "verifier/reward.txt").read_text() == "0\n"
    else:
        assert record["verification"] is None
        assert not archive.exists()
    summary = json.loads((tmp_path / "batch-dependencies/retry-summary.json").read_text())
    assert summary["timeout_sec"] == 2
    assert len(summary["attempts"]) == 1


def test_long_preparation_budget_does_not_extend_the_formal_verifier(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "old.txt").write_text("original evidence")
    before = hashes(logs)
    result = subprocess.run([
        sys.executable, "-c", _RUNNER, "prepared-batch", str(tmp_path / "batch"),
        "true", "10", "sleep 5", "0.1", "1", "0", "0", str(logs), str(tmp_path / "control.pid"),
    ], capture_output=True, text=True, check=True)
    record = json.loads(result.stdout)
    assert record["verification"]["status"] == "timeout"
    assert record["verification"]["duration_seconds"] < 2
    assert hashes(logs) == before


def test_dependency_preparation_requires_a_reviewed_revision_and_matching_files(tmp_path, monkeypatch):
    from harbor_adapter.bootstrap import VERIFIER_PROFILES, VerifierProfile
    from harbor_adapter.retained import dependency_plan

    trial, task = tmp_path / "trial", tmp_path / "task"
    trial.mkdir()
    task.mkdir()
    (trial / "config.json").write_text(json.dumps({"task": {"name": "terminal-bench/reviewed", "ref": "sha256:abc"}}))
    (task / "task.toml").write_text("reviewed task")
    digest = hashlib.sha256((task / "task.toml").read_bytes()).hexdigest()
    monkeypatch.setitem(VERIFIER_PROFILES, ("terminal-bench/reviewed", "sha256:abc"),
                        VerifierProfile("reviewed-v1", (), "true", (("task.toml", digest),)))
    assert dependency_plan(trial, task, 3600)["timeout_seconds"] == 3600
    (task / "task.toml").write_text("modified task")
    with pytest.raises(ValueError, match="profile mismatch"):
        dependency_plan(trial, task, 3600)
    (trial / "config.json").write_text(json.dumps({"task": {"name": "terminal-bench/reviewed", "ref": "latest"}}))
    with pytest.raises(ValueError, match="Unknown"):
        dependency_plan(trial, task, 3600)
