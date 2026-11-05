"""Cache transport cannot survive or start inside the evaluated model phase."""

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from harbor_adapter.__main__ import standard_config
from harbor_adapter.dependency_cache import DependencyCache, ENV, HELPER_IMAGE, PROTOCOL, SCRIPTS, snapshot_scripts


@pytest.fixture
def cache(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in SCRIPTS:
        (scripts / name).write_text("reviewed script\n")
    settings = {"protocol": PROTOCOL, "image": HELPER_IMAGE,
                "scripts_dir": str(scripts), "cache_dir": str(tmp_path / "cache"),
                "scripts_sha256": {name: hashlib.sha256((scripts / name).read_bytes()).hexdigest() for name in SCRIPTS}}
    state = {"open": False, "containers": set(), "commands": [], "fail_removal": False}
    environment = SimpleNamespace(
        evidence_dir=tmp_path / "evidence", _in_agent_phase=False,
        _integrity_state={"agent_phase": "not_started"},
        _run_docker_compose_command=AsyncMock(return_value=SimpleNamespace(stdout="a" * 64 + "\n")),
    )

    async def execute(**kwargs):
        return SimpleNamespace(return_code=0, stdout="open\n" if state["open"] else "closed\n")

    async def docker(*args):
        state["commands"].append(args)
        if args[0] == "container":
            name = args[-1].split("=", 1)[1]
            return "b" * 64 if name in state["containers"] else ""
        if args[0] == "run":
            state["containers"].add(args[args.index("--name") + 1])
            state["open"] = True
            return "b" * 64
        if args[0] == "logs":
            return '{"kind": "ready"}\n'
        if args[0] == "stop":
            state["open"] = False
            return args[-1]
        if args[0] == "rm":
            if not state["fail_removal"]:
                state["containers"].remove(args[-1])
            return args[-1]
        raise AssertionError(args)

    environment.exec = execute
    instance = DependencyCache(environment, settings)
    monkeypatch.setattr(instance, "_docker", docker)
    return instance, environment, state


def test_cache_phases_mount_only_helper_and_remove_it_before_agent(cache):
    instance, env, state = cache

    async def run():
        async with instance.phase("setup") as variables:
            assert variables == ENV
            assert instance.active_name and state["open"]
        await instance.assert_stopped()
        env._integrity_state["agent_phase"] = "completed"
        async with instance.phase("verifier"):
            assert state["open"]
        await instance.assert_stopped()

    asyncio.run(run())
    assert instance.completed_phases == {"setup", "verifier"}
    assert not state["containers"]
    commands = [args for args in state["commands"] if args[0] == "run"]
    for args in commands:
        assert args[args.index("--network") + 1] == "container:" + "a" * 64
        assert "--cap-drop=ALL" in args and "--read-only" in args
        assert "--security-opt=no-new-privileges:true" in args
        assert "--pull=never" in args
        mounts = [args[i + 1] for i, arg in enumerate(args) if arg == "--mount"]
        assert len(mounts) == 2
        assert all("target=/proxy" in mount or "target=/cache" in mount for mount in mounts)
    for phase in ("setup", "verifier"):
        assert json.loads((env.evidence_dir / f"dependency-cache-{phase}.json").read_text())["removed"] is True


@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError])
def test_failed_or_cancelled_dependency_install_still_removes_helper(cache, error):
    instance, env, state = cache

    async def run():
        with pytest.raises(error):
            async with instance.phase("setup"):
                raise error()
        await instance.assert_stopped()

    asyncio.run(run())
    assert not instance.completed_phases
    assert not state["containers"]
    assert json.loads((env.evidence_dir / "dependency-cache-setup.json").read_text())["removed"] is True


def test_cleanup_failure_blocks_agent_boundary(cache):
    instance, _, state = cache
    state["fail_removal"] = True

    async def run():
        with pytest.raises(RuntimeError, match="cleanup"):
            async with instance.phase("setup"):
                pass
        with pytest.raises(RuntimeError, match="absent"):
            await instance.assert_stopped()

    asyncio.run(run())
    assert instance.active_name


@pytest.mark.parametrize("phase,agent_phase,in_agent", [
    ("setup", "running", True), ("verifier", "running", True),
    ("setup", "completed", False), ("verifier", "not_started", False),
])
def test_helper_cannot_start_at_an_invalid_phase(cache, phase, agent_phase, in_agent):
    instance, env, state = cache
    env._integrity_state["agent_phase"] = agent_phase
    env._in_agent_phase = in_agent

    async def run():
        with pytest.raises(RuntimeError, match="model work"):
            async with instance.phase(phase):
                pytest.fail("Invalid phase reached dependency installation")

    asyncio.run(run())
    assert not state["commands"]


def test_existing_listener_cannot_impersonate_cache(cache):
    instance, _, state = cache
    state["open"] = True

    async def run():
        with pytest.raises(RuntimeError, match="absent"):
            async with instance.phase("setup"):
                pytest.fail("Existing listener was accepted")

    asyncio.run(run())
    assert not any(args[0] == "run" for args in state["commands"])


def test_modified_script_is_rejected_before_helper_start(cache):
    instance, _, state = cache
    (Path(instance.settings["scripts_dir"]) / SCRIPTS[0]).write_text("changed")

    async def run():
        with pytest.raises(ValueError, match="snapshot"):
            async with instance.phase("setup"):
                pytest.fail("Modified cache code ran")

    asyncio.run(run())
    assert not any(args[0] == "run" for args in state["commands"])


def test_snapshot_pins_original_cache_scripts(tmp_path):
    source = tmp_path / "repo/benchmarks/harbor/scripts"
    source.mkdir(parents=True)
    for name in SCRIPTS:
        (source / name).write_text(name)
    output = tmp_path / "snapshot"
    settings = snapshot_scripts(tmp_path / "repo", output, tmp_path / "cache")
    assert settings["protocol"] == PROTOCOL and settings["image"] == HELPER_IMAGE
    assert all((output / name).read_bytes() == (source / name).read_bytes() for name in SCRIPTS)
    assert settings["scripts_sha256"] == {name: hashlib.sha256(name.encode()).hexdigest() for name in SCRIPTS}


@pytest.mark.parametrize("policy", [None, "unreviewed", {"image": "custom"}])
def test_unregistered_cache_settings_are_rejected(policy):
    raw = {"tasks": [{"name": "org/task", "ref": "sha256:abc"}],
           "agents": [{"name": "harbor_adapter:NanoPyCodeAgent", "model_name": "deepseek/test"}],
           "dependency_cache": PROTOCOL}
    if policy is not None:
        raw["integrity"] = {"allowed_hosts": ["api.deepseek.com"]}
        raw["dependency_cache"] = policy
    with pytest.raises(ValueError, match="dependency_cache"):
        standard_config(raw)


@pytest.mark.parametrize("verifier", [
    '[verifier]\nenvironment_mode = "separate"\n',
    '[verifier.environment]\ndocker_image = "example/image"\n',
])
def test_separate_verifier_cache_is_rejected_before_container_start(tmp_path, cache, verifier):
    from harbor.models.task.config import EnvironmentConfig
    from harbor.models.trial.paths import TrialPaths
    from harbor_adapter.integrity_environment import IntegrityDockerEnvironment
    directory = tmp_path / "task/environment"
    directory.mkdir(parents=True)
    (directory.parent / "task.toml").write_text(verifier)
    paths = TrialPaths(trial_dir=tmp_path / "trial")
    paths.mkdir()
    with pytest.raises(ValueError, match="shared verifier"):
        IntegrityDockerEnvironment(
            environment_dir=directory, environment_name="probe", session_id="probe__env",
            trial_paths=paths, task_env_config=EnvironmentConfig(),
            integrity_policy={"allowed_hosts": ["api.deepseek.com"]},
            dependency_cache=cache[0].settings,
        )
