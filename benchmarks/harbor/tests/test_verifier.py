"""Execute the retry runner with real processes and Harbor's reward parser."""

import asyncio
import json
import os
from pathlib import Path
import shlex
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from harbor.environments.base import ExecResult
from harbor.models.task.config import TaskOS
from harbor.models.task.task import Task
from harbor.models.trial.config import TrialConfig, VerifierConfig
from harbor.models.trial.paths import TrialPaths
from harbor.trial.single_step import SingleStepTrial
from harbor.trial.trial import Trial
from harbor.trial.errors import VerifierTimeoutError
from harbor.verifier.factory import VerifierFactory
from harbor.verifier.verifier import RewardFileNotFoundError, VerifierOutputParseError

from harbor_adapter import RetryingVerifier


class LocalEnvironment:
    """Map container paths locally while executing the real runner and scripts."""

    os = TaskOS.LINUX

    def __init__(self, task, paths, mounted):
        self.task = task
        self.paths = paths
        self.capabilities = SimpleNamespace(mounted=mounted)
        self.logs = paths.verifier_dir if mounted else paths.trial_dir / "remote-logs"
        self.logs.mkdir(exist_ok=True)
        self.uploads = 0
        self.downloads = 0
        self.processes = []

    async def upload_dir(self, **kwargs):
        self.uploads += 1

    async def download_dir(self, *, source_dir, target_dir):
        self.downloads += 1
        shutil.copytree(self.logs, target_dir, dirs_exist_ok=True)

    async def exec(self, *, command, env=None, **kwargs):
        if command.startswith("chmod +x"):
            self.task.paths.test_path.chmod(0o755)
            return ExecResult(return_code=0)
        args = shlex.split(command)
        assert args[:2] == ["python3", "-c"]
        if args[3] != "cancel":
            args[3] = args[3].replace("/tests/", str(self.task.paths.tests_dir) + "/")
            args[3] = args[3].replace("/logs/verifier", str(self.logs))
            args[-2] = str(self.logs)
        args[-1] = str(self.paths.trial_dir / Path(args[-1]).name)
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "LOGS": str(self.logs),
                 "STATE": str(self.paths.trial_dir / "count"),
                 "CHILD_PID": str(self.paths.trial_dir / "child.pid"), **(env or {})},
        )
        self.processes.append(process)
        stdout, stderr = await process.communicate()
        return ExecResult(return_code=process.returncode, stdout=stdout.decode(), stderr=stderr.decode())


def make_verifier(tmp_path, script, *, mounted=True, max_attempts=3):
    task_dir = tmp_path / "task"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Write the solution.")
    (task_dir / "task.toml").write_text("[verifier]\ntimeout_sec = 0.3\n")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\nset -eu\n" + script)
    task = Task(task_dir)
    paths = TrialPaths(trial_dir=tmp_path / "trial")
    paths.mkdir()
    config = TrialConfig(
        task={"path": task_dir}, verifier_timeout_multiplier=4,
        verifier=VerifierConfig(
            import_path="harbor_adapter:RetryingVerifier",
            kwargs={"max_attempts": max_attempts},
        ),
    )
    paths.config_path.write_text(config.model_dump_json())
    environment = LocalEnvironment(task, paths, mounted)
    verifier = VerifierFactory.create_verifier_from_config(
        config.verifier, task=task, trial_paths=paths, environment=environment,
    )
    return verifier, environment, config


def summary(verifier):
    return json.loads((verifier.trial_paths.verifier_dir / "retry-summary.json").read_text())


@pytest.mark.parametrize("mounted", [True, False])
def test_timeout_retries_preserve_logs_clear_rewards_and_run_agent_once(tmp_path, mounted):
    verifier, environment, config = make_verifier(tmp_path, '''
count=$(cat "$STATE" 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > "$STATE"
echo "attempt $count"
if [ "$count" -lt 3 ]; then
    echo '{"reward": 1}' > "$LOGS/reward.json"
    touch "$LOGS/stale.log"
    sleep 10
fi
test ! -e "$LOGS/stale.log"
test ! -e "$LOGS/reward.json"
echo 0 > "$LOGS/reward.txt"
''', mounted=mounted)
    # Exercise Harbor's single-step lifecycle with a local verifier and its
    # real outer watchdog. No installation, Docker, or model call is needed.
    trial = object.__new__(SingleStepTrial)
    trial.task = verifier.task
    trial.config = config
    for name in ("_run_agent", "_upload_agent_logs", "_collect_artifacts", "_stop_agent_environment"):
        setattr(trial, name, AsyncMock())
    results = []

    async def verify():
        results.append(await asyncio.wait_for(
            verifier.verify(), timeout=Trial._compute_verifier_timeout_sec(trial),
        ))

    trial._run_verifier = verify
    asyncio.run(trial._run())

    trial._run_agent.assert_awaited_once()
    assert results[0].rewards == {"reward": 0.0}
    assert environment.uploads == 1
    assert [item["status"] for item in summary(verifier)["attempts"]] == [
        "timeout", "timeout", "completed",
    ]
    logs = verifier.trial_paths.verifier_dir
    for attempt in (1, 2, 3):
        assert (logs / "attempts" / str(attempt) / "test-stdout.txt").read_text() == f"attempt {attempt}\n"
    assert (logs / "attempts/1/reward.json").exists()
    assert not (logs / "reward.json").exists()


@pytest.mark.parametrize("reward", [0, 1])
def test_any_valid_score_stops_after_first_attempt(tmp_path, reward):
    verifier, _, _ = make_verifier(tmp_path, f'echo {reward} > "$LOGS/reward.txt"\n')
    assert asyncio.run(verifier.verify()).rewards == {"reward": reward}
    assert len(summary(verifier)["attempts"]) == 1


@pytest.mark.parametrize("mounted", [True, False])
def test_three_timeouts_leave_no_canonical_reward_and_keep_all_logs(tmp_path, mounted):
    verifier, environment, _ = make_verifier(tmp_path, '''
echo started
echo 1 > "$LOGS/reward.txt"
sleep 10
''', mounted=mounted)
    with pytest.raises(TimeoutError, match="3 attempts"):
        asyncio.run(verifier.verify())
    assert len(summary(verifier)["attempts"]) == 3
    assert all(item["status"] == "timeout" for item in summary(verifier)["attempts"])
    assert not verifier.trial_paths.reward_text_path.exists()
    assert (verifier.trial_paths.verifier_dir / "attempts/3/test-stdout.txt").read_text() == "started\n"
    assert environment.downloads == (0 if mounted else 1)


@pytest.mark.parametrize(("script", "error"), [
    ("exit 124\n", RewardFileNotFoundError),
    ('echo invalid > "$LOGS/reward.txt"\n', VerifierOutputParseError),
])
def test_non_timeout_failures_are_not_retried(tmp_path, script, error):
    verifier, _, _ = make_verifier(tmp_path, script)
    with pytest.raises(error):
        asyncio.run(verifier.verify())
    assert len(summary(verifier)["attempts"]) == 1
    assert summary(verifier)["attempts"][0]["status"] == "completed"


def process_is_running(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return False
    return stat[0] != "Z"


def test_timeout_stops_children_in_additional_process_groups(tmp_path):
    verifier, _, _ = make_verifier(tmp_path, '''
timeout 30 bash -c 'echo $$ > "$CHILD_PID"; sleep 30' &
wait
''', max_attempts=1)
    with pytest.raises(TimeoutError, match="1 attempts"):
        asyncio.run(verifier.verify())
    pid = int((verifier.trial_paths.trial_dir / "child.pid").read_text())
    assert not process_is_running(pid)


def test_cancellation_stops_the_runner_and_never_retries(tmp_path):
    verifier, environment, _ = make_verifier(tmp_path, 'echo $$ > "$CHILD_PID"\nsleep 30\n')

    async def cancel():
        verification = asyncio.create_task(verifier.verify())
        pid_file = verifier.trial_paths.trial_dir / "child.pid"
        async with asyncio.timeout(5):
            while not pid_file.exists():
                await asyncio.sleep(0.01)
        verification.cancel()
        with pytest.raises(asyncio.CancelledError):
            await verification
        for process in environment.processes:
            await asyncio.wait_for(process.wait(), 2)

    asyncio.run(cancel())
    assert len(summary(verifier)["attempts"]) == 1
    assert summary(verifier)["attempts"][0]["status"] == "cancelled"
    pid = int((verifier.trial_paths.trial_dir / "child.pid").read_text())
    assert not process_is_running(pid)


@pytest.mark.parametrize("value", [0, 4, -1, True, "3", 1.5])
def test_invalid_attempt_limits_are_rejected(value):
    with pytest.raises(ValueError, match="max_attempts"):
        RetryingVerifier(max_attempts=value)


def test_outer_watchdog_must_allow_all_attempts(tmp_path):
    verifier, environment, config = make_verifier(tmp_path, "exit 0\n")
    config.verifier_timeout_multiplier = 1
    verifier.trial_paths.config_path.write_text(config.model_dump_json())
    with pytest.raises(ValueError, match="verifier-timeout-multiplier 4"):
        asyncio.run(verifier.verify())
    assert environment.uploads == 0


def test_log_download_failure_preserves_harbor_timeout_error(tmp_path, caplog):
    verifier, environment, config = make_verifier(
        tmp_path, "sleep 10\n", mounted=False, max_attempts=1,
    )
    environment.download_dir = AsyncMock(side_effect=OSError("download failed"))
    trial = object.__new__(SingleStepTrial)
    trial.task = verifier.task
    trial.config = config
    trial._verifier_timeout_sec = Trial._compute_verifier_timeout_sec(trial)
    trial._result = SimpleNamespace(verifier=None)
    trial._emit = AsyncMock()
    trial._run_shared_verifier = lambda **kwargs: verifier.verify()

    with pytest.raises(VerifierTimeoutError):
        asyncio.run(trial._run_verifier())
    assert "Failed to collect verifier attempt logs" in caplog.text
    environment.download_dir.assert_awaited_once()


def test_outer_timeout_cap_is_applied_before_multiplier(tmp_path):
    verifier, _, config = make_verifier(tmp_path, 'echo 1 > "$LOGS/reward.txt"\n')
    config.verifier.max_timeout_sec = 0.3
    verifier.trial_paths.config_path.write_text(config.model_dump_json())
    assert asyncio.run(verifier.verify()).rewards == {"reward": 1}
