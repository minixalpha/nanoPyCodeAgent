"""Harbor's script verifier with up to three attempts after a timeout."""

import asyncio
import json
import math
from pathlib import Path
import shlex
import uuid

from harbor.models.task.config import TaskOS
from harbor.models.trial.config import TrialConfig
from harbor.models.trial.paths import EnvironmentPaths
from harbor.utils.scripts import build_execution_command
from harbor.verifier.verifier import Verifier

_RUNNER = Path(__file__).with_name("_verifier_runner.py").read_text()


class _RetryEnvironment:
    """Delegate Harbor operations, wrapping only the test-script execution."""

    def __init__(self, environment, command, timeout_sec, max_attempts, logger):
        self._environment = environment
        self._command = command
        self._timeout_sec = timeout_sec
        self._max_attempts = max_attempts
        self._logger = logger

    def __getattr__(self, name):
        return getattr(self._environment, name)

    async def exec(self, *, command, **kwargs):
        if command != self._command:
            return await self._environment.exec(command=command, **kwargs)
        control = f"/tmp/nanopy-verifier-{uuid.uuid4().hex}.pid"
        invocation = shlex.join([
            "python3", "-c", _RUNNER, command, str(self._timeout_sec),
            str(self._max_attempts), "/logs/verifier", control,
        ])
        try:
            result = await self._environment.exec(command=invocation, **kwargs)
        except BaseException:
            # Cancelling a Docker exec client alone can leave the command
            # alive inside the container. Stop the runner and its test session.
            try:
                cleanup = await asyncio.wait_for(self._environment.exec(
                    command=shlex.join(["python3", "-c", _RUNNER, "cancel", control]),
                    user="root",
                ), timeout=10)
                if cleanup.return_code != 0:
                    raise RuntimeError(cleanup.stderr)
            except Exception:
                self._logger.exception("Failed to stop the verifier retry runner")
            raise
        if result.return_code != 0:
            raise RuntimeError(f"Verifier retry runner failed: {result.stderr}")
        record = json.loads(result.stdout)
        if record["status"] == "timeout":
            raise TimeoutError(
                f"Verifier timed out after {self._max_attempts} attempts "
                f"of {self._timeout_sec:g} seconds"
            )
        return result


class RetryingVerifier(Verifier):
    """Retry native Linux test-script timeouts without rerunning the agent.

    Select with ``--verifier harbor_adapter:RetryingVerifier`` and allow the
    overall verification phase enough time via ``--verifier-timeout-multiplier
    4``. Each attempt retains the task's native verifier timeout.
    """

    def __init__(self, *, max_attempts=3, **kwargs):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be an integer between 1 and 3")
        super().__init__(**kwargs)
        if self.environment.os != TaskOS.LINUX or self.step_name is not None:
            raise ValueError("RetryingVerifier supports single-step Linux tasks")
        self._max_attempts = max_attempts
        self._attempt_timeout = self.task.config.verifier.timeout_sec
        if not math.isfinite(self._attempt_timeout) or self._attempt_timeout <= 0:
            raise ValueError("The task's verifier timeout must be finite and positive")

    async def verify(self):
        # Harbor's outer watchdog covers the entire custom verifier. Reject an
        # insufficient budget instead of silently losing the promised retries.
        config = TrialConfig.model_validate_json(self.trial_paths.config_path.read_text())
        multiplier = config.verifier_timeout_multiplier
        if multiplier is None:
            multiplier = config.timeout_multiplier
        base_timeout = (
            config.verifier.override_timeout_sec or self._attempt_timeout
        )
        outer_timeout = min(
            base_timeout, config.verifier.max_timeout_sec or float("inf"),
        ) * multiplier
        if outer_timeout <= self._attempt_timeout * self._max_attempts:
            raise ValueError(
                "Allow time for every verifier attempt and log collection: use "
                "--verifier-timeout-multiplier 4 and remove conflicting timeout caps"
            )
        _, tests_source_dir, host_test_path = self._resolve_tests()
        paths = EnvironmentPaths.for_os(self.environment.os)
        command = build_execution_command(
            str(paths.tests_dir / host_test_path.relative_to(tests_source_dir).as_posix()),
            stdout_path=str(paths.verifier_dir / "test-stdout.txt"),
            task_os=self.environment.os,
        )
        environment = self.environment
        self.environment = _RetryEnvironment(
            environment, command, self._attempt_timeout, self._max_attempts, self.logger,
        )
        try:
            return await super().verify()
        finally:
            self.environment = environment
            # The standard verifier downloads logs only after successful exec.
            # Preserve failed attempts too, even on non-mounted environments.
            if not environment.capabilities.mounted:
                try:
                    if self.include_logs or self.exclude_logs:
                        download = environment.download_dir_filtered(
                            source_dir=str(paths.verifier_dir),
                            target_dir=self.trial_paths.verifier_dir,
                            include=self.include_logs or None,
                            exclude=self.exclude_logs or None,
                            protect=["reward.txt", "reward.json", "retry-summary.json"],
                        )
                    else:
                        download = environment.download_dir(
                            source_dir=str(paths.verifier_dir),
                            target_dir=self.trial_paths.verifier_dir,
                        )
                    await asyncio.wait_for(download, timeout=30)
                except Exception:
                    # Collection failure must not hide the original timeout,
                    # cancellation, or reward parsing error.
                    self.logger.exception("Failed to collect verifier attempt logs")
                if self.include_logs or self.exclude_logs:
                    # Harbor protects exact file paths only. Download every
                    # archived attempt separately, regardless of log filters
                    # or failure to collect the current attempt's logs.
                    try:
                        await asyncio.wait_for(environment.download_dir(
                            source_dir=str(paths.verifier_dir / "attempts"),
                            target_dir=self.trial_paths.verifier_dir / "attempts",
                        ), timeout=30)
                    except Exception:
                        self.logger.exception("Failed to collect archived verifier attempts")
