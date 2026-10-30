"""DeepSeek provenance, official SDK driving, and accounting contracts."""

import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from harbor.models.agent.context import AgentContext

from harbor_adapter import DeepSeekHarnessAgent
from harbor_adapter.__main__ import snapshot_deepseek, standard_config
from harbor_adapter.deepseek import distribution_files
from harbor_adapter.pi import distribution_digest


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path / "distribution"
    (root / "wheels").mkdir(parents=True)
    manifest = {
        "version": "0.2.2-alpha.2", "source_commit": "a" * 40,
        "source_archive_sha256": "b" * 64,
        "sdk_wheel": "deepseek_harness_sdk-0.2.2a2-py3-none-any.whl",
        "runtime_wheel": "deepseek_harness_runtime_bin-0.2.2a2-py3-none-linux_x86_64.whl",
    }
    (root / "distribution.json").write_text(json.dumps(manifest))
    for key in ("sdk_wheel", "runtime_wheel"):
        (root / "wheels" / manifest[key]).write_bytes(b"wheel-fixture")
    return {"distribution_path": str(root),
            "distribution_sha256": distribution_digest(distribution_files(root)),
            "reasoning_effort": "high"}


def config(inputs):
    return {"tasks": [{"name": "org/task"}], "agents": [{
        "name": "harbor_adapter:DeepSeekHarnessAgent",
        "model_name": "deepseek/deepseek-flash", "kwargs": inputs,
    }], "verifier": {"import_path": "harbor_adapter:RetryingVerifier", "kwargs": {
        "max_attempts": 3, "require_agent_quiescence": True,
    }}}


def test_workflow_requires_public_inputs_and_quiescence(inputs):
    assert standard_config(config(inputs)).agents[0].kwargs["reasoning_effort"] == "high"
    with pytest.raises(ValueError, match="credentials"):
        standard_config(config(inputs | {"api_key": "secret"}))
    raw = config(inputs)
    raw["verifier"]["kwargs"].pop("require_agent_quiescence")
    with pytest.raises(ValueError, match="quiescence"):
        standard_config(raw)
    with pytest.raises(ValueError, match="reasoning effort"):
        standard_config(config(inputs | {"reasoning_effort": "invented"}))


def test_snapshot_pins_wheels_and_source_and_detects_corruption(tmp_path, inputs):
    agent = SimpleNamespace(kwargs=inputs.copy())
    result = snapshot_deepseek(agent, tmp_path / "cache", tmp_path / "record")
    assert result["provenance"]["source_commit"] == "a" * 40
    root = Path(agent.kwargs["distribution_path"])
    assert root != Path(inputs["distribution_path"])
    next(root.glob("wheels/*.whl")).write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="corrupt"):
        snapshot_deepseek(SimpleNamespace(kwargs=inputs.copy()), tmp_path / "cache", tmp_path)


def test_symlinks_and_missing_wheels_fail_registration(tmp_path, inputs):
    root = Path(inputs["distribution_path"])
    (root / "escape").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symbolic links"):
        distribution_files(root)
    (root / "escape").unlink()
    next(root.glob("wheels/*.whl")).unlink()
    with pytest.raises(ValueError, match="SDK and runtime"):
        distribution_files(root)


class Environment:
    default_user = None

    def __init__(self, cancel=False):
        self.calls, self.uploads = [], []
        self.cancel = cancel

    async def exec(self, **kwargs):
        self.calls.append(kwargs)
        command = kwargs["command"]
        if self.cancel and "dsh-instruction.txt" in command and " run " in command:
            raise asyncio.CancelledError()
        stdout = ""
        if command.endswith("--version"):
            stdout = "0.2.2-alpha.2\n"
        elif "--preflight" in command:
            stdout = '{"initialized": true, "model": "deepseek-flash"}\n'
        return SimpleNamespace(return_code=0, stdout=stdout, stderr="")

    async def upload_dir(self, source, target):
        self.uploads.append((source, target))

    async def upload_file(self, source, target):
        self.uploads.append((Path(source).read_text(), target))


def test_install_initializes_native_sdk_without_model_prompt(tmp_path, inputs):
    agent = DeepSeekHarnessAgent(logs_dir=tmp_path, model_name="deepseek/deepseek-flash", **inputs)
    env = Environment()
    asyncio.run(agent._install_agent(env))
    commands = "\n".join(call["command"] for call in env.calls)
    assert "--no-index --find-links /opt/harbor-dsh/wheels" in commands
    assert "--preflight" in commands
    assert "--instruction" not in commands
    assert agent._bootstrap_record["sdk_initialization"] == "passed"
    assert (tmp_path / "process-supervision-required").exists()


def test_cancellation_waits_for_process_supervisor(tmp_path, inputs, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    agent = DeepSeekHarnessAgent(logs_dir=tmp_path, model_name="deepseek/deepseek-flash", **inputs)
    env = Environment(cancel=True)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent.run("task", env, AgentContext()))
    assert " cancel " in env.calls[-1]["command"]
    assert env.calls[-1]["user"] == "root"


@pytest.mark.parametrize("reason,expected", [("completed", 0), ("max-tokens", 1), ("error", 1), (None, 1)])
def test_sdk_driver_requires_completed_finish_reason(tmp_path, monkeypatch, reason, expected):
    from harbor_adapter import _dsh_client

    calls = []

    class Harness:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def run(self, prompt, **kwargs):
            calls.append(prompt)
            return SimpleNamespace(session_id="benchmark", finish_reason=reason, final_response="done")

    monkeypatch.setitem(sys.modules, "deepseek_harness", SimpleNamespace(DeepSeekHarness=Harness))
    instruction = tmp_path / "instruction.txt"
    instruction.write_text("original task\n")
    monkeypatch.setattr(sys, "argv", ["driver", "--home", str(tmp_path / "home"), "--model", "deepseek-flash", "--instruction", str(instruction)])
    assert _dsh_client.main() == expected
    assert calls[0]["profile"] == "sdk-minimal"
    assert "max_tokens" not in calls[0]
    assert calls[1] == "original task\n"


def test_usage_includes_compaction_and_marks_interrupted_records_partial(tmp_path, inputs):
    agent = DeepSeekHarnessAgent(logs_dir=tmp_path, model_name="deepseek/deepseek-flash", **inputs)
    events = [
        {"type": "assistant/message", "data": {"usage": {"inputTokens": 100, "outputTokens": 10, "cacheReadTokens": 30}}},
        {"type": "compaction/summary", "data": {"usage": {"inputTokens": 200, "outputTokens": 20}}},
        {"type": "assistant/attempt", "data": {}},
    ]
    (tmp_path / "dsh-events.jsonl").write_text("".join(json.dumps({"payload": {"event": e}}) + "\n" for e in events))
    (tmp_path / "process-supervision.json").write_text('{"status":"cancelled","processes_stopped":true}')
    context = AgentContext()
    agent.populate_context_post_run(context)
    assert context.n_input_tokens == 330
    assert context.n_output_tokens == 30
    assert context.n_cache_tokens == 30
    assert context.cost_usd is None
    metadata = context.metadata["deepseek_harness"]
    assert metadata["usage_records"] == 2
    assert metadata["usage_is_partial"] is True
    assert metadata["missing_usage_records"] == 1


def test_missing_usage_stays_unknown(tmp_path, inputs):
    agent = DeepSeekHarnessAgent(logs_dir=tmp_path, model_name="deepseek/deepseek-flash", **inputs)
    context = AgentContext()
    agent.populate_context_post_run(context)
    assert context.n_input_tokens is None
    assert context.cost_usd is None
    assert context.metadata["deepseek_harness"]["usage_is_partial"] is True
