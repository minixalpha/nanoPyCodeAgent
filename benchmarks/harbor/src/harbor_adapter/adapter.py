"""Harbor adapter for running nanoPyCodeAgent in benchmark containers."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import shlex
import uuid
from typing import override

from harbor.agents.installed.base import (
    BaseInstalledAgent,
    CliFlag,
    NonZeroAgentExitCodeError,
    with_prompt_template,
)
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trajectories.trajectory import Trajectory

from .bootstrap import AptCache, default_cache_dir, verifier_profile

_DEFAULT_MAX_TURNS = 50
_SYSTEM_DEPENDENCIES = ("curl", "bash", "git", "python3", "ca_certificates")
# A 404 can reflect a stale index or an unavailable file. Restore verified
# downloads first, then retry the package transaction at most twice.
_DEPENDENCY_RETRY_DELAYS = (2.0, 4.0)
_PACKAGE_NAME = "nanoPyCodeAgent"
_REPOSITORY_URL = "https://github.com/minixalpha/nanoPyCodeAgent.git"
_UV_VERSION = "0.9.11"
_PATH_SETUP = 'export PATH="$HOME/.local/bin:$PATH"; '
_TRAJECTORY_PATH = "/logs/agent/trajectory.json"


class NanoPyCodeAgent(BaseInstalledAgent):
    """Install and run nanoPyCodeAgent inside a Harbor task environment."""

    SUPPORTS_ATIF = True
    MODEL_CONNECTION = ModelConnectionSpec(
        api_key_envs=("ANTHROPIC_API_KEY",),
        base_url_envs=("ANTHROPIC_BASE_URL",),
    )
    CLI_FLAGS = [
        CliFlag(
            "max_turns",
            cli="--max-turns",
            type="int",
            default=_DEFAULT_MAX_TURNS,
        ),
        CliFlag("max_tokens", cli="--max-tokens", type="int"),
        CliFlag("time_budget_seconds", cli="--time-budget-seconds", type="int"),
    ]

    def __init__(
        self, *args, git_ref: str | None = None, wheel_path: str | None = None,
        bootstrap_cache: str | None = None, **kwargs,
    ):
        if git_ref is not None:
            if not isinstance(git_ref, str):
                raise ValueError(
                    "git_ref must be a string; use a full commit SHA or quote "
                    "an abbreviated revision in --agent-kwarg"
                )
            git_ref = git_ref.strip()
            if not git_ref:
                raise ValueError("git_ref must not be blank")
        pins = (git_ref, wheel_path, kwargs.get("version"))
        if sum(pin is not None for pin in pins) > 1:
            raise ValueError("version, git_ref, and wheel_path are mutually exclusive")
        self._git_ref = git_ref
        self._wheel_path = (
            Path(wheel_path).expanduser().resolve() if wheel_path else None
        )
        if self._wheel_path is not None and (
            not self._wheel_path.is_file() or self._wheel_path.suffix != ".whl"
        ):
            raise ValueError("wheel_path must point to an existing wheel")
        self._bootstrap_cache = AptCache(
            Path(bootstrap_cache).expanduser().resolve()
            if bootstrap_cache else default_cache_dir()
        )
        self._bootstrap_record: dict = {}
        super().__init__(*args, **kwargs)
        max_tokens = self._resolved_flags.get("max_tokens")
        if max_tokens is not None and max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")

    @staticmethod
    @override
    def name() -> str:
        return "nanopycodeagent"

    @override
    def get_version_command(self) -> str:
        return f"{_PATH_SETUP}nanoPyCodeAgent --version"

    @override
    def parse_version(self, stdout: str) -> str:
        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
        if not lines:
            return ""
        match = re.fullmatch(r"nanoPyCodeAgent\s+(\S+)", lines[-1])
        return match.group(1) if match else lines[-1]

    def _install_target(self) -> str:
        if self._wheel_path is not None:
            return "/tmp/" + self._wheel_path.name
        if self._git_ref is not None:
            return f"git+{_REPOSITORY_URL}@{self._git_ref}"
        if self._version is not None:
            return f"{_PACKAGE_NAME}=={self._version}"
        return _PACKAGE_NAME

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        record = self._bootstrap_record
        record.update(
            status="running", stage="profile",
            cache_dir=str(self._bootstrap_cache.root),
        )
        try:
            profile = verifier_profile(
                self.logs_dir, getattr(environment, "environment_name", None),
            )
            record["verifier_preflight"] = {
                "profile": profile.name if profile else None,
                "status": "pending" if profile else "not_configured",
            }
            record["stage"] = "system_dependencies"
            await self._ensure_system_dependencies(environment)
            record["stage"] = "agent_install"
            await self._install_agent(environment)
            if profile:
                record["stage"] = "verifier_dependencies"
                await self._install_apt(environment, profile.apt_packages)
                await self.exec_as_agent(environment, command=profile.command)
                record["verifier_preflight"]["status"] = "passed"
            record.update(status="ready", stage="complete")
        except BaseException as exc:
            record.update(status="failed", error_type=type(exc).__name__)
            if record.get("verifier_preflight", {}).get("status") == "pending":
                record["verifier_preflight"]["status"] = "incomplete"
            raise
        finally:
            record["cache_used"] = any(
                a["restored"] for a in record.get("apt", [])
            )
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            (self.logs_dir / "bootstrap.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )

    async def _install_agent(self, environment: BaseEnvironment) -> None:
        if self._wheel_path is not None:
            await environment.upload_file(self._wheel_path, self._install_target())
            self._bootstrap_record["wheel_sha256"] = hashlib.sha256(
                self._wheel_path.read_bytes()
            ).hexdigest()
        install_target = shlex.quote(self._install_target())
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                "if ! command -v uv >/dev/null 2>&1; then "
                f"curl -LsSf https://astral.sh/uv/{_UV_VERSION}/install.sh | sh; "
                "fi; "
                f"{_PATH_SETUP}"
                f"uv tool install --force {install_target}; "
                "nanoPyCodeAgent --version"
            ),
        )

    async def _ensure_system_dependencies(
        self, environment: BaseEnvironment
    ) -> None:
        """Install base dependencies, retrying a transient package-index 404.

        The retry only covers the system-package step, so it cannot replay any
        model work; a non-404 failure or the final attempt propagates.
        """
        if await self._get_system_package_manager(environment) == "apt-get":
            packages = tuple(
                package for dependency in _SYSTEM_DEPENDENCIES
                for package in self.SYSTEM_PACKAGES[dependency].packages["apt-get"]
            )
            await self._install_apt(environment, packages)
            return
        await self._retry_dependency_install(
            lambda: self.ensure_system_dependencies(environment, _SYSTEM_DEPENDENCIES)
        )

    async def _install_apt(self, environment, packages) -> None:
        await self._retry_dependency_install(
            lambda: self._bootstrap_cache.install(
                self, environment, packages, self._bootstrap_record,
            )
        )

    async def _retry_dependency_install(self, install) -> None:
        total_attempts = len(_DEPENDENCY_RETRY_DELAYS) + 1
        for attempt, delay in enumerate((*_DEPENDENCY_RETRY_DELAYS, None)):
            try:
                await install()
                return
            except NonZeroAgentExitCodeError as error:
                if delay is None or "404" not in str(error):
                    raise
                self.logger.warning(
                    "Retrying system dependency installation after HTTP 404 "
                    "(attempt %s/%s); no model call has started.",
                    attempt + 1,
                    total_attempts,
                )
                await asyncio.sleep(delay)

    def _runtime_env(self) -> dict[str, str]:
        model_connection = self.model_connection
        env: dict[str, str] = {}
        if model_connection.api_key:
            env["ANTHROPIC_API_KEY"] = model_connection.api_key
        if model_connection.configured_base_url:
            env["ANTHROPIC_BASE_URL"] = model_connection.configured_base_url

        model = (self._get_env("ANTHROPIC_MODEL") or "").strip()
        if not model and self.model_name:
            model = self.model_name.split("/", 1)[-1]
        if model:
            env["ANTHROPIC_MODEL"] = model
        max_tokens = self._get_env("ANTHROPIC_MAX_TOKENS")
        if max_tokens is not None:
            env["ANTHROPIC_MAX_TOKENS"] = max_tokens
        return env

    @override
    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        instruction_shell_var = (
            f"harbor_nanopycodeagent_instruction_{uuid.uuid4().hex}"
        )
        instruction_env_var = instruction_shell_var.upper()
        env = {
            **self._runtime_env(),
            instruction_env_var: instruction,
        }
        cli_flags = self.build_cli_flags()
        await self.exec_as_agent(
            environment,
            command=(
                f"{_PATH_SETUP}"
                f'{instruction_shell_var}="${instruction_env_var}"; '
                f"unset {instruction_env_var}; "
                f'printf "%s" "${instruction_shell_var}" | '
                f"nanoPyCodeAgent {cli_flags} "
                f"--trajectory {_TRAJECTORY_PATH} "
                "2>&1 | tee /logs/agent/nanopycodeagent.txt"
            ),
            env=env,
        )

    @override
    def populate_context_post_run(self, context: AgentContext) -> None:
        if self._bootstrap_record:
            context.metadata = context.metadata or {}
            context.metadata["bootstrap"] = self._bootstrap_record
        trajectory_path = self.logs_dir / "trajectory.json"
        try:
            trajectory = Trajectory.model_validate_json(
                trajectory_path.read_text(encoding="utf-8")
            )
            if trajectory.schema_version != "ATIF-v1.7":
                raise ValueError(
                    f"expected ATIF-v1.7, got {trajectory.schema_version}"
                )
        except FileNotFoundError:
            self._record_trajectory_diagnostic(context, "missing")
            self.logger.warning("No ATIF trajectory found at %s", trajectory_path)
            return
        except (OSError, UnicodeError, ValueError) as exc:
            self._record_trajectory_diagnostic(
                context,
                "invalid",
                error=f"{type(exc).__name__}: {exc}",
            )
            self.logger.warning(
                "Failed to read ATIF trajectory at %s: %s",
                trajectory_path,
                exc,
            )
            return

        metrics = trajectory.final_metrics
        extra = metrics.extra if metrics and metrics.extra else {}
        is_partial = extra.get("usage_complete") is False or (
            extra.get("cost_is_partial") is True
        )
        self._record_trajectory_diagnostic(
            context,
            "partial" if is_partial else "complete",
            total_steps=len(trajectory.steps),
            usage_complete=extra.get("usage_complete"),
            cost_is_partial=extra.get("cost_is_partial"),
            known_cost_usd=extra.get("known_cost_usd"),
            cost_is_estimated=extra.get("cost_is_estimated"),
            estimated_cost_usd=extra.get("estimated_cost_usd"),
            missing_generation_ids=extra.get("missing_generation_ids"),
        )
        if metrics is None:
            return
        context.n_input_tokens = metrics.total_prompt_tokens
        context.n_output_tokens = metrics.total_completion_tokens
        context.n_cache_tokens = metrics.total_cached_tokens
        context.cost_usd = metrics.total_cost_usd

    @staticmethod
    def _record_trajectory_diagnostic(
        context: AgentContext,
        status: str,
        **details: object,
    ) -> None:
        context.metadata = context.metadata or {}
        context.metadata["trajectory"] = {
            "format": "ATIF-v1.7",
            "status": status,
            **{key: value for key, value in details.items() if value is not None},
        }
