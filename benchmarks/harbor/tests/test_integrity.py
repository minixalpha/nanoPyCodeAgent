"""Enforcement must fail closed before model calls, independently of the agent."""

import asyncio
import json
import shlex
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from harbor.environments.base import ExecResult
from harbor.models.task.config import EnvironmentConfig, NetworkPolicy
from harbor.models.trial.paths import TrialPaths

from harbor_adapter import NanoPyCodeAgent, PiCodeAgent, DeepSeekHarnessAgent
from harbor_adapter.__main__ import standard_config
from harbor_adapter.integrity import RULES
from harbor_adapter.integrity_environment import IntegrityDockerEnvironment, dns_upstreams


POLICY = {"allowed_hosts": ["api.deepseek.com"]}


def raw_config():
    return {
        "tasks": [{"name": "org/task", "ref": "sha256:abc"}],
        "agents": [{"name": "harbor_adapter:NanoPyCodeAgent", "model_name": "deepseek/test"}],
        "integrity": POLICY,
    }


def test_standard_workflow_injects_one_identical_policy_and_requires_quiescence():
    raw = raw_config()
    config = standard_config(raw)
    policy = config.agents[0].kwargs["integrity_policy"]
    assert policy == config.environment.kwargs["integrity_policy"]
    assert config.environment.import_path == "harbor_adapter:IntegrityDockerEnvironment"
    assert config.verifier.kwargs["require_agent_quiescence"] is True
    assert "integrity_policy" not in raw["agents"][0].get("kwargs", {})


def test_entrypoint_requires_explicit_protocol_before_preparing_files(tmp_path):
    from harbor_adapter.__main__ import run
    config = tmp_path / "config.json"
    raw = raw_config()
    raw.pop("integrity")
    config.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="New runs require"):
        run(SimpleNamespace(config=config))
    config.write_text(json.dumps(raw_config()))
    with pytest.raises(ValueError, match="Cannot combine"):
        run(SimpleNamespace(config=config, legacy_open_network=True))


@pytest.mark.parametrize("policy", [
    {}, {"allowed_hosts": []}, {"allowed_hosts": ["*.github.com"]},
    {"allowed_hosts": ["0.0.0.0/0"]}, {"allowed_hosts": ["1.1.1.1"]},
    {"allowed_hosts": ["https://api.deepseek.com"]},
    POLICY | {"protocol": "open"}, POLICY | {"skip_probe": True},
    POLICY | {"probe_url": "https://user:password@example.com"},
    POLICY | {"probe_url": "https://api.deepseek.com/"},
])
def test_ambiguous_or_ineffective_policies_are_rejected(policy):
    with pytest.raises(ValueError):
        standard_config(raw_config() | {"integrity": policy})


@pytest.mark.parametrize("overrides", [
    {"environment": {"type": "daytona"}},
    {"environment": {"extra_docker_compose": ["cache.yaml"]}},
    {"environment": {"extra_allowed_hosts": ["github.com"]}},
    {"environment": {"kwargs": {"privileged": True}}},
    {"environment": {"env": {"HTTPS_PROXY": "https://proxy.example"}}},
])
def test_unreviewed_network_and_environment_escape_routes_are_rejected(overrides):
    with pytest.raises(ValueError):
        standard_config(raw_config() | overrides)


@pytest.mark.parametrize("overrides", [
    {"skills": ["/tmp/skills"]}, {"extra_allowed_hosts": ["github.com"]},
    {"load_trajectory": "/tmp/old.json"}, {"exclude_logs": ["*"]},
])
def test_external_agent_context_and_filtered_logs_are_rejected(overrides):
    raw = raw_config()
    raw["agents"][0].update(overrides)
    with pytest.raises(ValueError):
        standard_config(raw)


@pytest.fixture
def environment(tmp_path):
    directory = tmp_path / "environment"
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n")
    paths = TrialPaths(trial_dir=tmp_path / "trial")
    paths.mkdir()
    return IntegrityDockerEnvironment(
        environment_dir=directory, environment_name="probe",
        session_id="probe__env", trial_paths=paths,
        task_env_config=EnvironmentConfig(), integrity_policy=POLICY,
        mounts=[{"type": "bind", "source": str(paths.verifier_dir), "target": "/logs/verifier"}],
    )


def fake_sidecar(environment, monkeypatch):
    async def command(args, **kwargs):
        if args[-1] == "show":
            return ExecResult(return_code=0, stdout="mode: controlled egress\napi.deepseek.com")
        if args[-1] == "rules":
            return ExecResult(return_code=0, stdout="table inet gost_egress {}")
        return ExecResult(return_code=0, stdout="")
    mock = AsyncMock(side_effect=command)
    monkeypatch.setattr(environment, "_run_docker_compose_command", mock)
    return mock


def test_environment_removes_all_host_mounts_and_drops_network_capabilities(environment):
    assert environment._mounts == []
    assert environment.capabilities.mounted is False
    assert environment.capabilities.dynamic_network_policy is True
    main = json.loads(environment._hardening_path.read_text())["services"]["main"]
    assert {"NET_RAW", "NET_ADMIN"} <= set(main["cap_drop"])
    assert main["security_opt"] == ["no-new-privileges:true"]
    assert environment._hardening_path in environment._docker_compose_paths


def test_dns_exceptions_are_only_exact_daemon_selected_addresses():
    assert dns_upstreams("nameserver 127.0.0.11\n# ExtServers: [172.17.0.1 host(2001:db8::53)]") == ["172.17.0.1", "2001:db8::53"]
    with pytest.raises(ValueError):
        dns_upstreams("# ExtServers: [0.0.0.0/0]")


def test_dns_failure_does_not_count_as_https_blocking(environment, monkeypatch):
    fake_sidecar(environment, monkeypatch)
    monkeypatch.setattr(environment, "_probe", AsyncMock(side_effect=[
        {"reachable": True}, {"reachable": False, "reason_type": "gaierror"},
    ]))
    with pytest.raises(RuntimeError, match="failed to resolve"):
        asyncio.run(environment.integrity_preflight())


@pytest.mark.parametrize("responses,match", [
    ([False], "positive control"),
    ([True, True], "disallowed HTTPS"),
    ([True, False, False], "allowed host is unreachable"),
])
def test_preflight_requires_positive_negative_and_allowed_controls(environment, monkeypatch, responses, match):
    fake_sidecar(environment, monkeypatch)
    monkeypatch.setattr(environment, "_probe", AsyncMock(side_effect=[{"reachable": r} for r in responses]))
    with pytest.raises(RuntimeError, match=match):
        asyncio.run(environment.integrity_preflight())
    assert environment._integrity_state["preflight"] == "failed"


def test_run_captures_host_evidence_and_does_not_reopen_network_on_error(environment, monkeypatch):
    fake_sidecar(environment, monkeypatch)
    monkeypatch.setattr(environment, "_probe", AsyncMock(side_effect=[
        {"reachable": r} for r in (True, False, True, False)
    ]))

    async def run():
        await environment.integrity_preflight()
        with pytest.raises(RuntimeError, match="model failed"):
            async with environment.agent_phase():
                with pytest.raises(RuntimeError, match="Cannot relax"):
                    await environment.set_network_policy(NetworkPolicy())
                await environment._output_callback()("tool evidence", "stdout")
                raise RuntimeError("model failed")
        assert environment.network_policy == environment.integrity_policy.network()
        assert environment._integrity_state["agent_phase"] == "interrupted"
        assert "tool evidence" in (environment.evidence_dir / "live-output.jsonl").read_text()
        assert (environment.evidence_dir / "network-after-agent.json").exists()
        await environment.prepare_verification()
        assert environment.network_policy == NetworkPolicy()
    asyncio.run(run())


def test_no_model_work_before_preflight(environment):
    async def run():
        async with environment.agent_phase():
            pytest.fail("model work started")
    with pytest.raises(RuntimeError, match="preflight"):
        asyncio.run(run())


@pytest.mark.parametrize("kind", ["nano", "pi", "deepseek"])
def test_actual_adapters_deliver_the_same_rules_and_supervise_commands(environment, monkeypatch, tmp_path, kind):
    from test_pi import inputs as pi_fixture
    from test_deepseek import inputs as deepseek_fixture
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    logs = tmp_path / "agent"
    logs.mkdir()
    kwargs = dict(logs_dir=logs, model_name="deepseek/deepseek-flash", integrity_policy=POLICY)
    if kind == "pi":
        agent = PiCodeAgent(**kwargs, **pi_fixture.__wrapped__(tmp_path))
    elif kind == "deepseek":
        agent = DeepSeekHarnessAgent(**kwargs, **deepseek_fixture.__wrapped__(tmp_path))
    else:
        agent = NanoPyCodeAgent(**kwargs)
    fake_sidecar(environment, monkeypatch)
    environment._integrity_state["preflight"] = "passed"
    monkeypatch.setattr(environment, "_probe", AsyncMock(return_value={"reachable": False}))

    async def execute(**kwargs):
        stdout = '{"settled": true, "stop_reason": "stop"}'
        return ExecResult(return_code=0, stdout=stdout)
    execute_mock = AsyncMock(side_effect=execute)
    monkeypatch.setattr(environment, "exec", execute_mock)
    upload = AsyncMock()
    if kind == "deepseek":
        monkeypatch.setattr(agent, "_upload_config_text", upload)
    asyncio.run(agent.run("original task", environment, None))
    invocation = execute_mock.call_args_list[0].kwargs
    parts = shlex.split(invocation["command"])
    parts = parts[parts.index("python3"):]
    assert parts[4] == "run" and parts[6] == "/logs/agent/process-supervision.json"
    expected = RULES + "\nTask:\noriginal task"
    if kind == "nano":
        assert expected in invocation["env"].values()
    elif kind == "pi":
        assert expected in shlex.split(parts[-1])
    else:
        assert upload.call_args.kwargs["content"] == expected
        assert "--stream-events" in parts[-1]
    assert environment._integrity_state["agent_phase"] == "completed"


def test_restricted_adapter_cannot_run_in_plain_environment(tmp_path):
    agent = NanoPyCodeAgent(logs_dir=tmp_path, integrity_policy=POLICY)
    with pytest.raises(ValueError, match="IntegrityDockerEnvironment"):
        asyncio.run(agent.run("task", SimpleNamespace(), None))


def test_nano_cancellation_stops_supervisor_before_leaving_restricted_phase(environment, monkeypatch, tmp_path):
    fake_sidecar(environment, monkeypatch)
    environment._integrity_state["preflight"] = "passed"
    monkeypatch.setattr(environment, "_probe", AsyncMock(return_value={"reachable": False}))
    calls = []

    async def execute(**kwargs):
        calls.append(kwargs)
        if " run " in kwargs["command"]:
            raise asyncio.CancelledError()
        return ExecResult(return_code=0)
    monkeypatch.setattr(environment, "exec", execute)
    agent = NanoPyCodeAgent(logs_dir=tmp_path, integrity_policy=POLICY)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent.run("task", environment, None))
    assert " cancel " in calls[-1]["command"]
    assert calls[-1]["user"] == "root"
    assert environment.network_policy == environment.integrity_policy.network()
    assert environment._integrity_state["agent_phase"] == "interrupted"
