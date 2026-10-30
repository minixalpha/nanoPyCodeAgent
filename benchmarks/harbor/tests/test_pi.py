"""Pi provenance, native execution, and usage accounting contracts."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from harbor.models.agent.context import AgentContext

from harbor_adapter import PiCodeAgent
from harbor_adapter import __main__ as workflow
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
        self.model_listing = "provider  model\ndeepseek  deepseek-flash\n"
        self.model_warning = ""

    async def exec(self, **kwargs):
        self.calls.append(kwargs)
        command = kwargs["command"]
        stdout = ""
        if command.endswith("--version"):
            stdout = "1.4.0\n"
        elif "; python3 -c " in command or "; python3 -I -c " in command:
            stdout = json.dumps(self.completion)
        elif "--list-models" in command:
            return SimpleNamespace(return_code=0, stdout=self.model_listing, stderr=self.model_warning)
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


def test_snapshot_preserves_distinct_model_settings_in_one_job(tmp_path, inputs):
    first = SimpleNamespace(kwargs=inputs.copy())
    alternate = tmp_path / "alternate-models.json"
    models = json.loads(Path(inputs["model_config_path"]).read_text())
    models["providers"]["deepseek"]["models"][0]["maxTokens"] = 1000
    alternate.write_text(json.dumps(models))
    second = SimpleNamespace(kwargs=inputs | {"model_config_path": str(alternate)})
    record = tmp_path / "job-input"
    record.mkdir()
    manifests = [snapshot_pi(agent, tmp_path / "cache", record) for agent in [first, second]]
    paths = [Path(agent.kwargs["model_config_path"]) for agent in [first, second]]
    assert paths[0] != paths[1]
    assert "maxTokens" not in json.loads(paths[0].read_text())["providers"]["deepseek"]["models"][0]
    assert json.loads(paths[1].read_text())["providers"]["deepseek"]["models"][0]["maxTokens"] == 1000
    for path, manifest in zip(paths, manifests):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["model_config_sha256"]
        assert record / manifest["model_config_file"] == path
    third = SimpleNamespace(kwargs=inputs | {"model_config_path": str(alternate)})
    snapshot_pi(third, tmp_path / "cache", record)
    assert third.kwargs["model_config_path"] == str(paths[1])


@pytest.mark.parametrize("same_record_name", [False, True])
def test_concurrent_distribution_publication_reuses_verified_winner(tmp_path, inputs, monkeypatch, same_record_name):
    barrier = Barrier(2)
    copytree = workflow.shutil.copytree
    original = Path(inputs["distribution_path"])

    def stage_together(source, target, *args, **kwargs):
        result = copytree(source, target, *args, **kwargs)
        if Path(source) == original:
            barrier.wait(timeout=5)
        return result

    monkeypatch.setattr(workflow.shutil, "copytree", stage_together)
    records = [tmp_path / "a" / "job-input", tmp_path / "b" / ("job-input" if same_record_name else "other-input")]
    for record in records:
        record.mkdir(parents=True)
    agents = [SimpleNamespace(kwargs=inputs.copy()) for _ in records]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(snapshot_pi, agent, tmp_path / "cache", record) for agent, record in zip(agents, records)]
        manifests = [future.result(timeout=10) for future in futures]
    assert manifests[0] == manifests[1]
    destination = Path(agents[0].kwargs["distribution_path"])
    assert destination == Path(agents[1].kwargs["distribution_path"])
    assert distribution_digest(distribution_files(destination)) == inputs["distribution_sha256"]
    assert list(destination.parent.iterdir()) == [destination]


def test_concurrent_cache_winner_is_rejected_if_corrupt(tmp_path, inputs, monkeypatch):
    cache = tmp_path / "cache"
    record = tmp_path / "job-input"
    record.mkdir()
    destination = cache / "pi-distributions" / inputs["distribution_sha256"]

    def publish_corrupt_winner(source, target):
        target.mkdir()
        (target / "pi").write_text("corrupt")
        (target / "package.json").write_text('{"version": "1.4.0"}')
        raise OSError(errno.ENOTEMPTY, "Directory not empty")

    monkeypatch.setattr(Path, "rename", publish_corrupt_winner)
    with pytest.raises(ValueError, match="Cached Pi distribution is corrupt"):
        snapshot_pi(SimpleNamespace(kwargs=inputs.copy()), cache, record)
    assert list(destination.parent.iterdir()) == [destination]


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


@pytest.mark.parametrize("listing,warning", [
    ("provider model\ndeepseek deepseek-flash\n", "Warning: errors loading models.json: maxTokens must be number"),
    ("No models found", ""),
    ("provider model\nother deepseek-flash\n", ""),
    ("provider model\ndeepseek other-model\n", ""),
])
def test_install_rejects_model_fallback_or_missing_registration(tmp_path, inputs, listing, warning):
    environment = Environment()
    environment.model_listing = listing
    environment.model_warning = warning
    with pytest.raises(ValueError, match="Pi model registration failed"):
        asyncio.run(adapter(tmp_path, inputs).install(environment))
    assert json.loads((tmp_path / "bootstrap.json").read_text())["status"] == "failed"


def test_install_probes_the_requested_model_instead_of_a_fixed_id(tmp_path, inputs):
    models = Path(inputs["model_config_path"])
    models.write_text(models.read_text().replace('deepseek-flash', 'registered-alternate'))
    agent = PiCodeAgent(logs_dir=tmp_path, model_name="deepseek/registered-alternate", **inputs)
    environment = Environment()
    environment.model_listing = "provider model\ndeepseek registered-alternate\n"
    asyncio.run(agent.install(environment))
    assert environment.calls[-1]["command"].endswith("--list-models registered-alternate")


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


@pytest.mark.parametrize("stop_reason", ["error", "aborted"])
def test_failed_stream_zero_usage_stays_partial_after_successful_retry(tmp_path, inputs, stop_reason):
    (tmp_path / "process-supervision.json").write_text(json.dumps({"status": "completed", "return_code": 0}))
    zero = {key: 0 for key in ["input", "output", "cacheRead", "cacheWrite", "totalTokens"]}
    zero["cost"] = {"total": 0}
    known = {"input": 10, "output": 5, "cacheRead": 20, "cost": {"total": .2}}
    events = [{"type": "message_end", "message": {
        "role": "assistant", "stopReason": reason,
        "content": [{"type": "text", "text": "Streamed text"}], "usage": usage,
    }} for reason, usage in [(stop_reason, zero), ("stop", known)]]
    (tmp_path / "pi.txt").write_text("\n".join(map(json.dumps, events)))
    context = AgentContext()
    adapter(tmp_path, inputs).populate_context_post_run(context)
    assert context.n_input_tokens == 30
    assert context.n_output_tokens == 5
    assert context.n_cache_tokens == 20
    assert context.cost_usd == .2
    assert context.metadata["pi"]["usage_records"] == 1
    assert context.metadata["pi"]["missing_usage_records"] == 1
    assert context.metadata["pi"]["usage_is_partial"] is True
    assert context.metadata["pi"]["cost_is_partial"] is True


def test_failed_stream_only_keeps_token_and_cost_totals_unknown(tmp_path, inputs):
    (tmp_path / "pi.txt").write_text(json.dumps({"type": "message_end", "message": {
        "role": "assistant", "stopReason": "error", "content": [{"type": "text", "text": "Partial"}],
        "usage": {"input": 0, "output": 0, "cost": {"total": 0}},
    }}))
    context = AgentContext()
    adapter(tmp_path, inputs).populate_context_post_run(context)
    assert context.n_input_tokens is None
    assert context.cost_usd is None
    assert context.metadata["pi"]["usage_is_partial"] is True
    assert context.metadata["pi"]["cost_is_partial"] is True


def test_missing_cost_keeps_the_reported_cost_subtotal(tmp_path, inputs):
    events = [{"type": "message_end", "message": {"role": "assistant", "usage": usage}} for usage in [
        {"input": 10, "output": 5, "cost": {"total": .2}}, {"input": 10, "output": 5},
    ]]
    (tmp_path / "pi.txt").write_text("\n".join(map(json.dumps, events)))
    context = AgentContext()
    adapter(tmp_path, inputs).populate_context_post_run(context)
    assert context.n_input_tokens == 20
    assert context.cost_usd == .2
    assert context.metadata["pi"]["usage_is_partial"] is False
    assert context.metadata["pi"]["cost_is_partial"] is True


def test_transport_cancellation_waits_for_root_process_cleanup(tmp_path, inputs, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-secret")
    class CancelledEnvironment(Environment):
        async def exec(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise asyncio.CancelledError()
            return SimpleNamespace(return_code=0, stdout="", stderr="")
    environment = CancelledEnvironment()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(adapter(tmp_path, inputs).run("test", environment, AgentContext()))
    assert environment.calls[-1]["user"] == "root"
    assert "cancel" in environment.calls[-1]["command"]
    assert environment.calls[-1].get("env") is None


def test_cancelled_run_marks_known_usage_and_cost_as_partial(tmp_path, inputs):
    (tmp_path / "process-supervision.json").write_text(json.dumps({"status": "cancelled", "processes_stopped": True}))
    (tmp_path / "pi.txt").write_text(json.dumps({"type": "message_end", "message": {
        "role": "assistant", "usage": {"input": 10, "output": 5, "cost": {"total": .1}},
    }}))
    context = AgentContext()
    adapter(tmp_path, inputs).populate_context_post_run(context)
    assert context.cost_usd == .1
    assert context.metadata["pi"]["usage_is_partial"] is True
    assert context.metadata["pi"]["cost_is_partial"] is True
