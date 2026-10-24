"""Pi provenance, native execution, and usage accounting contracts."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from harbor.models.agent.context import AgentContext

from harbor_adapter import PiCodeAgent
from harbor_adapter.__main__ import snapshot_pi, standard_config
from harbor_adapter.pi import distribution_digest, distribution_files, read_model_config


@pytest.fixture
def inputs(tmp_path):
    distribution = tmp_path / "distribution"
    distribution.mkdir()
    (distribution / "pi").write_text("binary")
    (distribution / "pi").chmod(0o755)
    (distribution / "package.json").write_text(json.dumps({"version": "1.4.0"}))
    models = tmp_path / "models.json"
    models.write_text(json.dumps({"providers": {"deepseek": {
        "api": "openai-completions", "baseUrl": "https://api.deepseek.com",
        "apiKey": "${DEEPSEEK_API_KEY}", "models": [{"id": "deepseek-flash"}],
    }}}))
    return {
        "distribution_path": str(distribution),
        "distribution_sha256": distribution_digest(distribution_files(distribution)),
        "model_config_path": str(models), "thinking": "high",
    }


def adapter(tmp_path, inputs):
    return PiCodeAgent(logs_dir=tmp_path, model_name="deepseek/deepseek-flash", **inputs)


class Environment:
    default_user = None

    def __init__(self):
        self.calls = []
        self.uploads = []
        self.completion = {"settled": True, "stop_reason": "stop"}

    async def exec(self, **kwargs):
        self.calls.append(kwargs)
        command = kwargs["command"]
        stdout = ""
        if command.endswith("--version"):
            stdout = "1.4.0\n"
        elif "; python3 -c " in command:
            stdout = json.dumps(self.completion)
        return SimpleNamespace(return_code=0, stdout=stdout, stderr="")

    async def upload_dir(self, source, target):
        self.uploads.append((source, target))

    async def upload_file(self, source, target):
        self.uploads.append((Path(source).read_text(), target))


def test_public_pi_config_is_accepted_without_allowing_credentials(tmp_path, inputs):
    raw = {"tasks": [{"name": "org/task"}], "agents": [{
        "name": "harbor_adapter:PiCodeAgent", "model_name": "deepseek/deepseek-flash",
        "kwargs": inputs,
    }]}
    assert standard_config(raw).agents[0].kwargs["thinking"] == "high"
    raw["agents"][0]["kwargs"] = inputs | {"api_key": "private"}
    with pytest.raises(ValueError, match="credentials"):
        standard_config(raw)
    models = Path(inputs["model_config_path"])
    models.write_text(models.read_text().replace("${DEEPSEEK_API_KEY}", "private"))
    with pytest.raises(ValueError, match="environment key"):
        read_model_config(models)


def test_snapshot_reuses_identical_binary_but_detects_corruption(tmp_path, inputs):
    cache = tmp_path / "cache"
    agent = SimpleNamespace(kwargs=inputs.copy())
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    manifest = snapshot_pi(agent, cache, first)
    assert snapshot_pi(SimpleNamespace(kwargs=inputs.copy()), cache, second) == manifest
    destination = Path(agent.kwargs["distribution_path"])
    assert destination != Path(inputs["distribution_path"])
    (destination / "pi").write_text("corrupted")
    with pytest.raises(ValueError, match="corrupt"):
        snapshot_pi(SimpleNamespace(kwargs=inputs.copy()), cache, second)


def test_changed_executable_permissions_and_symlinks_are_rejected(tmp_path, inputs):
    root = Path(inputs["distribution_path"])
    (root / "pi").chmod(0o644)
    assert distribution_digest(distribution_files(root)) != inputs["distribution_sha256"]
    (root / "link").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="symbolic links"):
        distribution_files(root)


def test_install_verifies_binary_and_provider_without_calling_model(tmp_path, inputs):
    agent = adapter(tmp_path, inputs)
    env = Environment()
    asyncio.run(agent.install(env))
    record = json.loads((tmp_path / "bootstrap.json").read_text())
    assert record["status"] == "ready"
    assert record["distribution_sha256"] == inputs["distribution_sha256"]
    assert record["verifier_preflight"]["status"] == "not_configured"
    assert env.calls[-1]["command"].endswith("--list-models deepseek-flash")
    assert env.calls[-1]["env"]["DEEPSEEK_API_KEY"] == "preflight-only"
    assert not any("--print" in call["command"] for call in env.calls)


def test_install_refuses_modified_binary(tmp_path, inputs):
    agent = adapter(tmp_path, inputs)
    Path(inputs["distribution_path"], "pi").write_text("changed")
    with pytest.raises(ValueError, match="changed after registration"):
        asyncio.run(agent.install(Environment()))
    assert json.loads((tmp_path / "bootstrap.json").read_text())["status"] == "failed"


def test_native_run_preserves_failure_status_and_uses_only_environment_key(tmp_path, inputs, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    agent = adapter(tmp_path, inputs)
    env = Environment()
    asyncio.run(agent.run("Handle '$HOME' and `literal`", env, AgentContext()))
    call = env.calls[0]
    assert "set -euo pipefail" in call["command"]
    assert "--thinking high" in call["command"]
    assert "--session-dir /logs/agent/pi/sessions" in call["command"]
    assert "test-secret" not in call["command"]
    assert call["env"]["DEEPSEEK_API_KEY"] == "test-secret"
    assert "--system-prompt" not in call["command"]


def test_usage_includes_compaction_and_cache_without_pricing_missing_calls_as_zero(tmp_path, inputs):
    agent = adapter(tmp_path, inputs)
    usage = {"input": 10, "output": 5, "cacheRead": 20, "cacheWrite": 3, "cost": {"total": 0.2}}
    (tmp_path / "pi.txt").write_text("\n".join(json.dumps(event) for event in [
        {"type": "message_end", "message": {"role": "assistant", "usage": usage}},
        {"type": "compaction_end", "result": {"usage": usage}},
        {"type": "message_end", "message": {"role": "assistant"}},
    ]))
    context = AgentContext()
    agent.populate_context_post_run(context)
    assert context.n_input_tokens == 66
    assert context.n_output_tokens == 10
    assert context.n_cache_tokens == 40
    assert context.cost_usd == 0.4
    assert context.metadata["pi"]["missing_usage_records"] == 1
    assert context.metadata["pi"]["cost_is_estimated"] is True
    assert context.metadata["pi"]["cost_is_partial"] is True


@pytest.mark.parametrize("completion", [
    {"settled": True, "stop_reason": "error"},
    {"settled": False, "stop_reason": "stop"},
    {"settled": True, "stop_reason": None},
])
def test_zero_exit_with_failed_or_missing_response_is_an_execution_error(tmp_path, inputs, monkeypatch, completion):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    environment = Environment()
    environment.completion = completion
    with pytest.raises(RuntimeError, match="did not finish successfully"):
        asyncio.run(adapter(tmp_path, inputs).run("test", environment, AgentContext()))


def test_missing_output_keeps_usage_unknown(tmp_path, inputs):
    context = AgentContext()
    adapter(tmp_path, inputs).populate_context_post_run(context)
    assert context.n_input_tokens is None
    assert context.cost_usd is None
