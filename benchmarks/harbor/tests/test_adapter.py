"""Contract tests for the repository-local Harbor installed-agent adapter."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from harbor_adapter import NanoPyCodeAgent


class RecordingEnvironment:
    """Record the commands Harbor would execute inside a task container."""

    default_user = "agent"

    def __init__(self):
        self.calls = []

    async def exec(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(return_code=0, stdout="", stderr="")


def make_adapter(tmp_path: Path, **kwargs) -> NanoPyCodeAgent:
    return NanoPyCodeAgent(logs_dir=tmp_path, **kwargs)


def test_install_pins_the_requested_release_and_checks_its_version(tmp_path):
    adapter = make_adapter(tmp_path, version="0.8.0")
    environment = RecordingEnvironment()

    asyncio.run(adapter.install(environment))

    install_call = environment.calls[-1]
    assert install_call["user"] is None
    assert "uv tool install --force nanoPyCodeAgent==0.8.0" in install_call[
        "command"
    ]
    assert "https://astral.sh/uv/0.9.11/install.sh" in install_call["command"]
    assert install_call["command"].endswith("nanoPyCodeAgent --version")
    assert (
        adapter.get_version_command()
        == 'export PATH="$HOME/.local/bin:$PATH"; nanoPyCodeAgent --version'
    )
    assert adapter.parse_version("nanoPyCodeAgent 0.8.0\n") == "0.8.0"


def test_install_can_pin_an_unreleased_git_revision(tmp_path):
    revision = "0123456789abcdef0123456789abcdef01234567"
    adapter = make_adapter(tmp_path, git_ref=revision)
    environment = RecordingEnvironment()

    asyncio.run(adapter.install(environment))

    assert (
        "uv tool install --force "
        "git+https://github.com/minixalpha/nanoPyCodeAgent.git@"
        f"{revision}"
    ) in environment.calls[-1]["command"]


def test_install_source_rejects_ambiguous_or_blank_pins(tmp_path):
    with pytest.raises(ValueError, match="mutually exclusive"):
        make_adapter(tmp_path, version="0.8.0", git_ref="main")
    with pytest.raises(ValueError, match="git_ref must not be blank"):
        make_adapter(tmp_path, git_ref="  ")


def test_run_pipes_the_instruction_and_forwards_anthropic_configuration(tmp_path):
    instruction = 'fix "quoted" input; echo $TOKEN\nthen run the tests'
    adapter = make_adapter(
        tmp_path,
        model_name="openrouter/deepseek/deepseek-v4-flash-0731",
        extra_env={
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_BASE_URL": "https://gateway.example/v1",
            "ANTHROPIC_MODEL": "deepseek/deepseek-v4-flash-0731",
        },
        max_turns=20,
    )
    environment = RecordingEnvironment()

    asyncio.run(adapter.run(instruction, environment, SimpleNamespace()))

    run_call = environment.calls[-1]
    command = run_call["command"]
    assert instruction not in command
    assert 'printf "%s" "$harbor_nanopycodeagent_instruction_' in command
    assert "nanoPyCodeAgent --max-turns 20" in command
    assert command.endswith("2>&1 | tee /logs/agent/nanopycodeagent.txt")

    run_env = run_call["env"]
    instruction_keys = [
        key
        for key in run_env
        if key.startswith("HARBOR_NANOPYCODEAGENT_INSTRUCTION_")
    ]
    assert len(instruction_keys) == 1
    assert run_env[instruction_keys[0]] == instruction
    assert run_env["ANTHROPIC_API_KEY"] == "sk-test"
    assert run_env["ANTHROPIC_BASE_URL"] == "https://gateway.example/v1"
    assert run_env["ANTHROPIC_MODEL"] == "deepseek/deepseek-v4-flash-0731"


def test_run_normalizes_harbor_provider_configuration_for_the_anthropic_sdk(
    tmp_path,
):
    adapter = make_adapter(
        tmp_path,
        model_name="openrouter/deepseek/deepseek-v4-flash-0731",
        extra_env={
            "OPENROUTER_API_KEY": "sk-openrouter",
            "OPENROUTER_BASE_URL": "https://openrouter.example/api",
        },
    )
    environment = RecordingEnvironment()

    asyncio.run(adapter.run("fix it", environment, SimpleNamespace()))

    run_env = environment.calls[-1]["env"]
    assert run_env["ANTHROPIC_API_KEY"] == "sk-openrouter"
    assert run_env["ANTHROPIC_BASE_URL"] == "https://openrouter.example/api"
    assert run_env["ANTHROPIC_MODEL"] == "deepseek/deepseek-v4-flash-0731"
    assert "OPENROUTER_API_KEY" not in run_env
