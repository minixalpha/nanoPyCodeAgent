"""Cache integrity and setup-before-model contracts for benchmark bootstrap."""

import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from harbor.models.trial.config import TrialConfig

from harbor_adapter import NanoPyCodeAgent
from harbor_adapter.bootstrap import AptCache, Package, QEMU_REF, QEMU_TASK, parse_apt_plan, verifier_profile


def package(data=b"verified deb", filename="curl_1_amd64.deb"):
    return Package("https://deb.example/" + filename, filename, len(data), hashlib.sha256(data).hexdigest())


def apt_line(item):
    return f"'{item.url}' {item.filename} {item.size} SHA256:{item.sha256}"


class AptEnvironment:
    def __init__(self, item, data):
        self.item = item
        self.data = data
        self.uploaded = []
        self.downloaded = []
        self.commands = []

    async def upload_file(self, source, target):
        self.uploaded.append((Path(source).read_bytes(), target))

    async def download_file(self, source_path, target_path):
        self.downloaded.append(source_path)
        Path(target_path).write_bytes(self.data)

    async def exec_as_root(self, environment, command, **kwargs):
        self.commands.append(command)
        return SimpleNamespace(stdout=apt_line(self.item) if "--print-uris" in command else "")


def test_restores_only_the_current_index_hash_and_saves_downloads(tmp_path):
    cache = AptCache(tmp_path)
    data = b"current package"
    item = package(data)
    stale = package(b"old package")
    source = tmp_path / "download.deb"
    source.write_bytes(b"old package")
    cache.store(stale, source)
    first = AptEnvironment(item, data)
    record = {}
    asyncio.run(cache.install(first, first, ("curl",), record))
    assert first.uploaded == []
    assert len(first.downloaded) == 1
    assert cache.path(item).read_bytes() == data
    assert record["apt"][0]["saved"] == [item.filename]
    assert first.commands[-1] == "apt-get install -y curl"

    second = AptEnvironment(item, data)
    record = {}
    asyncio.run(cache.install(second, second, ("curl",), record))
    assert second.uploaded == [(data, "/var/cache/apt/archives/" + item.filename)]
    assert second.downloaded == []
    assert record["apt"][0]["restored"] == [item.filename]


def test_corrupt_cache_fails_before_upload_or_install(tmp_path):
    item = package()
    cache = AptCache(tmp_path)
    cache.path(item).parent.mkdir(parents=True)
    cache.path(item).write_bytes(b"tampered")
    environment = AptEnvironment(item, b"verified deb")
    with pytest.raises(ValueError, match="checksum/size"):
        asyncio.run(cache.install(environment, environment, ("curl",), {}))
    assert not environment.uploaded
    assert not any(command.startswith("apt-get install") for command in environment.commands)


def test_invalid_download_is_never_published_or_installed(tmp_path):
    item = package()
    cache = AptCache(tmp_path)
    environment = AptEnvironment(item, b"corrupt response")
    with pytest.raises(ValueError, match="checksum/size"):
        asyncio.run(cache.install(environment, environment, ("curl",), {}))
    assert not cache.path(item).exists()
    assert not any(command.startswith("apt-get install") for command in environment.commands)


def test_import_validates_all_packages_before_publishing(tmp_path):
    source = tmp_path / "old"
    (source / "packages").mkdir(parents=True)
    first = package()
    second = package(b"another", "git_1_amd64.deb")
    (source / "packages" / first.filename).write_bytes(b"verified deb")
    (source / "packages" / second.filename).write_bytes(b"bad")
    manifest = source / "manifest.json"
    manifest.write_text(json.dumps([asdict(first), asdict(second)]))
    cache = AptCache(tmp_path / "cache")
    with pytest.raises(ValueError, match="checksum/size"):
        cache.import_manifest(manifest)
    assert not cache.root.exists()
    (source / "packages" / second.filename).write_bytes(b"another")
    assert cache.import_manifest(manifest) == 2
    assert cache.path(second).read_bytes() == b"another"


@pytest.mark.parametrize("filename", ["../escape.deb", "/tmp/escape.deb", "$(id).deb"])
def test_manifest_rejects_unsafe_filenames(filename):
    with pytest.raises(ValueError, match="Unsafe"):
        package(filename=filename)


def test_apt_parser_requires_strong_hashes_and_handles_epoch_filenames():
    item = package(filename="git_1%3a2.30.2-1+deb11u5_amd64.deb")
    assert parse_apt_plan("Reading package lists...\n" + apt_line(item)) == [item]
    with pytest.raises(ValueError, match="SHA256"):
        parse_apt_plan(apt_line(item).replace("SHA256:", "MD5Sum:"))


def write_task(logs_dir, ref=QEMU_REF):
    logs_dir.mkdir(parents=True)
    (logs_dir.parent / "config.json").write_text(json.dumps({"task": {"name": QEMU_TASK, "ref": ref}}))


def test_profile_is_scoped_to_reviewed_task_revision(tmp_path):
    logs_dir = tmp_path / "agent"
    write_task(logs_dir)
    assert verifier_profile(logs_dir, "qemu-alpine-ssh").name == "qemu-alpine-ssh-v1"
    (logs_dir.parent / "config.json").write_text(json.dumps({"task": {"name": QEMU_TASK, "ref": "latest"}}))
    with pytest.raises(ValueError, match="Unknown"):
        verifier_profile(logs_dir, "qemu-alpine-ssh")


@pytest.mark.parametrize("task", [
    {"path": "/tasks/qemu-alpine-ssh"},
    {"path": "/dataset/qemu-alpine-ssh", "source": "local-dataset"},
    {
        "path": "tasks/qemu-alpine-ssh", "source": "git-dataset",
        "git_url": "https://example.com/tasks.git", "git_commit_id": "a" * 40,
    },
], ids=["local-path", "local-dataset", "git-dataset"])
def test_unresolved_qemu_revision_stops_setup_before_install(tmp_path, monkeypatch, task):
    logs_dir = tmp_path / "agent"
    logs_dir.mkdir()
    (tmp_path / "config.json").write_text(TrialConfig(task=task).model_dump_json())
    adapter = NanoPyCodeAgent(logs_dir=logs_dir)
    dependencies = AsyncMock()
    install = AsyncMock()
    monkeypatch.setattr(adapter, "_ensure_system_dependencies", dependencies)
    monkeypatch.setattr(adapter, "_install_agent", install)

    with pytest.raises(ValueError, match="Unknown .*qemu-alpine-ssh revision"):
        asyncio.run(adapter.install(SimpleNamespace(environment_name="qemu-alpine-ssh")))

    dependencies.assert_not_awaited()
    install.assert_not_awaited()
    report = json.loads((logs_dir / "bootstrap.json").read_text())
    assert report["status"] == "failed"
    assert report["stage"] == "profile"


def test_known_environment_requires_trial_config(tmp_path):
    with pytest.raises(ValueError, match="pinned trial config"):
        verifier_profile(tmp_path / "agent", "qemu-alpine-ssh")


@pytest.mark.parametrize("has_config", [False, True])
def test_unregistered_task_does_not_require_a_profile(tmp_path, has_config):
    if has_config:
        config = TrialConfig(task={"path": "/tasks/other-task"})
        (tmp_path / "config.json").write_text(config.model_dump_json())
    assert verifier_profile(tmp_path / "agent", "other-task") is None


def test_preflight_failure_stops_setup_and_records_the_failing_stage(tmp_path, monkeypatch):
    logs_dir = tmp_path / "agent"
    write_task(logs_dir)
    adapter = NanoPyCodeAgent(logs_dir=logs_dir)
    calls = []

    async def dependencies(*args):
        calls.append("system")

    async def install(*args):
        calls.append("agent_install")

    async def apt(*args):
        calls.append("verifier_packages")

    async def fail(*args, command):
        calls.append("verifier_preflight")
        assert "pytest --version" in command
        assert "/tests" not in command
        raise RuntimeError("dependency download failed")

    monkeypatch.setattr(adapter, "_ensure_system_dependencies", dependencies)
    monkeypatch.setattr(adapter, "_install_agent", install)
    monkeypatch.setattr(adapter, "_install_apt", apt)
    monkeypatch.setattr(adapter, "exec_as_agent", fail)
    with pytest.raises(RuntimeError, match="dependency download"):
        asyncio.run(adapter.install(SimpleNamespace(environment_name="qemu-alpine-ssh")))
    assert calls == ["system", "agent_install", "verifier_packages", "verifier_preflight"]
    report = json.loads((logs_dir / "bootstrap.json").read_text())
    assert report["status"] == "failed"
    assert report["stage"] == "verifier_dependencies"
    assert report["verifier_preflight"]["status"] == "incomplete"


def test_local_wheel_is_uploaded_and_logged(tmp_path, monkeypatch):
    wheel = tmp_path / "nanopycodeagent-0.1-py3-none-any.whl"
    wheel.write_bytes(b"wheel contents")
    adapter = NanoPyCodeAgent(logs_dir=tmp_path / "logs", wheel_path=str(wheel))
    environment = AptEnvironment(package(), b"")
    calls = []

    async def execute(*args, **kwargs):
        calls.append(kwargs["command"])

    monkeypatch.setattr(adapter, "exec_as_agent", execute)
    asyncio.run(adapter._install_agent(environment))
    assert environment.uploaded == [(b"wheel contents", "/tmp/" + wheel.name)]
    assert "uv tool install --force /tmp/" + wheel.name in calls[0]
    assert adapter._bootstrap_record["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="mutually exclusive"):
        NanoPyCodeAgent(logs_dir=tmp_path, wheel_path=str(wheel), git_ref="main")
