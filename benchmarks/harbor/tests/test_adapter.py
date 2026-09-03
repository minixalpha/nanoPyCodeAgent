"""Contract tests for the repository-local Harbor installed-agent adapter."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from harbor.models.agent.context import AgentContext

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


def write_trajectory(tmp_path: Path, final_metrics: dict) -> None:
    (tmp_path / "trajectory.json").write_text(
        json.dumps(
            {
                "schema_version": "ATIF-v1.7",
                "session_id": "run-1",
                "trajectory_id": "run-1",
                "agent": {
                    "name": "nanoPyCodeAgent",
                    "version": "0.8.0",
                    "model_name": "test-model",
                },
                "steps": [
                    {
                        "step_id": 1,
                        "source": "user",
                        "message": "fix it",
                    }
                ],
                "final_metrics": final_metrics,
            }
        ),
        encoding="utf-8",
    )


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


def test_install_source_rejects_a_revision_coerced_to_a_number(tmp_path):
    with pytest.raises(
        ValueError,
        match="use a full commit SHA or quote an abbreviated revision",
    ):
        make_adapter(tmp_path, git_ref=float("inf"))


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
    assert "--trajectory /logs/agent/trajectory.json" in command
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


def test_adapter_declares_atif_support_and_populates_complete_context(tmp_path):
    adapter = make_adapter(tmp_path)
    write_trajectory(
        tmp_path,
        {
            "total_prompt_tokens": 120,
            "total_completion_tokens": 30,
            "total_cached_tokens": 20,
            "total_cost_usd": 0.0042,
            "total_steps": 1,
        },
    )
    context = AgentContext()

    adapter.populate_context_post_run(context)

    assert adapter.SUPPORTS_ATIF is True
    assert context.n_input_tokens == 120
    assert context.n_output_tokens == 30
    assert context.n_cache_tokens == 20
    assert context.cost_usd == 0.0042
    assert context.metadata == {
        "trajectory": {
            "format": "ATIF-v1.7",
            "status": "complete",
            "total_steps": 1,
        }
    }


def test_partial_trajectory_preserves_known_values_and_completeness(tmp_path):
    adapter = make_adapter(tmp_path)
    write_trajectory(
        tmp_path,
        {
            "total_steps": 1,
            "extra": {
                "usage_complete": False,
                "known_cost_usd": 0.001,
                "cost_is_partial": True,
                "missing_generation_ids": ["generation-1"],
            },
        },
    )
    context = AgentContext()

    adapter.populate_context_post_run(context)

    assert context.n_input_tokens is None
    assert context.n_output_tokens is None
    assert context.n_cache_tokens is None
    assert context.cost_usd is None
    assert context.metadata == {
        "trajectory": {
            "format": "ATIF-v1.7",
            "status": "partial",
            "total_steps": 1,
            "usage_complete": False,
            "cost_is_partial": True,
            "known_cost_usd": 0.001,
            "missing_generation_ids": ["generation-1"],
        }
    }


@pytest.mark.parametrize(
    ("contents", "expected_status"),
    [
        (None, "missing"),
        ("not JSON", "invalid"),
        (
            json.dumps(
                {
                    "schema_version": "ATIF-v1.6",
                    "agent": {"name": "agent", "version": "1"},
                    "steps": [
                        {"step_id": 1, "source": "user", "message": "task"}
                    ],
                }
            ),
            "invalid",
        ),
    ],
)
def test_missing_or_invalid_trajectory_records_a_diagnostic(
    tmp_path,
    contents,
    expected_status,
):
    adapter = make_adapter(tmp_path)
    if contents is not None:
        (tmp_path / "trajectory.json").write_text(contents, encoding="utf-8")
    context = AgentContext()

    adapter.populate_context_post_run(context)

    diagnostic = context.metadata["trajectory"]
    assert diagnostic["format"] == "ATIF-v1.7"
    assert diagnostic["status"] == expected_status
    assert ("error" in diagnostic) is (expected_status == "invalid")
