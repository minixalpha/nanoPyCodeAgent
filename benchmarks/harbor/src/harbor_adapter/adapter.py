"""Harbor adapter for running nanoPyCodeAgent in benchmark containers."""

import re
import shlex
import uuid
from typing import override

from harbor.agents.installed.base import (
    BaseInstalledAgent,
    CliFlag,
    with_prompt_template,
)
from harbor.agents.model_connection import ModelConnectionSpec
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

_DEFAULT_MAX_TURNS = 50
_PACKAGE_NAME = "nanoPyCodeAgent"
_REPOSITORY_URL = "https://github.com/minixalpha/nanoPyCodeAgent.git"
_UV_VERSION = "0.9.11"
_PATH_SETUP = 'export PATH="$HOME/.local/bin:$PATH"; '


class NanoPyCodeAgent(BaseInstalledAgent):
    """Install and run nanoPyCodeAgent inside a Harbor task environment."""

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
        )
    ]

    def __init__(self, *args, git_ref: str | None = None, **kwargs):
        if git_ref is not None:
            git_ref = git_ref.strip()
            if not git_ref:
                raise ValueError("git_ref must not be blank")
        if git_ref is not None and kwargs.get("version") is not None:
            raise ValueError("version and git_ref are mutually exclusive")
        self._git_ref = git_ref
        super().__init__(*args, **kwargs)

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
        if self._git_ref is not None:
            return f"git+{_REPOSITORY_URL}@{self._git_ref}"
        if self._version is not None:
            return f"{_PACKAGE_NAME}=={self._version}"
        return _PACKAGE_NAME

    @override
    async def install(self, environment: BaseEnvironment) -> None:
        await self.ensure_system_dependencies(
            environment,
            ("curl", "bash", "git", "python3", "ca_certificates"),
        )
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
                "2>&1 | tee /logs/agent/nanopycodeagent.txt"
            ),
            env=env,
        )
