"""Controller-owned PyPI transport, absent throughout the evaluated agent phase."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import uuid

from .integrity import write_record

PROTOCOL = "pypi-verified-v1"
# This previously reviewed cache-helper image supplies Python, not task inputs.
HELPER_IMAGE = "alexgshaw/pytorch-model-cli@sha256:c996884b5fb5fb2c0c07d67da2c4f974f271f07234ed28e1a868240375c57a67"
SCRIPTS = ("pypi_wheel_cache.py", "cache_image.py")
PORT = 18744
ENV = {"UV_DEFAULT_INDEX": f"http://127.0.0.1:{PORT}/simple", "UV_HTTP_TIMEOUT": "600"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot_scripts(root, destination, cache):
    """Snapshot the repository's reviewed transport along with every job."""
    destination.mkdir()
    hashes = {}
    for name in SCRIPTS:
        source = root / "benchmarks/harbor/scripts" / name
        hashes[name] = digest(source)
        shutil.copyfile(source, destination / name)
        if digest(destination / name) != hashes[name]:
            raise ValueError("Dependency transport changed while snapshotting")
    return {"protocol": PROTOCOL, "image": HELPER_IMAGE,
            "scripts_dir": str(destination.resolve()), "scripts_sha256": hashes,
            "cache_dir": str((cache / "pypi-ranges").resolve())}


class DependencyCache:
    """One temporary helper per phase; no host mounts enter the task container."""

    def __init__(self, environment, settings):
        if (set(settings) != {"protocol", "image", "scripts_dir", "scripts_sha256", "cache_dir"}
                or settings["protocol"] != PROTOCOL or settings["image"] != HELPER_IMAGE
                or set(settings["scripts_sha256"]) != set(SCRIPTS)):
            raise ValueError("Unsupported dependency cache snapshot")
        self.environment, self.settings = environment, settings
        self.active_name = None
        self.last_name = None
        self.completed_phases = set()

    async def _docker(self, *args):
        process = await asyncio.create_subprocess_exec(
            "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 30)
        except BaseException:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            raise
        if process.returncode:
            raise RuntimeError(f"Dependency cache Docker command failed: {stderr.decode(errors='replace')}")
        return stdout.decode()

    async def _list(self, name):
        return (await self._docker("container", "ls", "--all", "--quiet", "--filter", f"name={name}")).strip()

    async def _reachable(self):
        script = (
            "import socket\n"
            "try:\n"
            f" s=socket.create_connection(('127.0.0.1',{PORT}),timeout=2);s.close();print('open')\n"
            "except ConnectionRefusedError: print('closed')\n"
        )
        result = await self.environment.exec(command=shlex.join(["python3", "-I", "-c", script]), user="root")
        if result.return_code or (result.stdout or "").strip() not in {"open", "closed"}:
            raise RuntimeError("Cannot establish dependency cache socket state")
        return result.stdout.strip() == "open"

    async def assert_stopped(self):
        if self.active_name or (self.last_name and await self._list(self.last_name)) or await self._reachable():
            raise RuntimeError("Dependency cache must be absent during model work")

    def _validate_scripts(self):
        directory = Path(self.settings["scripts_dir"])
        for name, expected in self.settings["scripts_sha256"].items():
            path = directory / name
            if path.is_symlink() or digest(path) != expected:
                raise ValueError("Dependency cache script differs from its snapshot")
        # Docker --mount uses commas as separators even when argv is quoted.
        if any("," in self.settings[key] for key in ("scripts_dir", "cache_dir")):
            raise ValueError("Dependency cache mount paths cannot contain commas")

    async def _start(self, name):
        self._validate_scripts()
        cache = Path(self.settings["cache_dir"])
        cache.mkdir(parents=True, exist_ok=True)
        result = await self.environment._run_docker_compose_command(["ps", "--quiet", "main"], timeout_sec=15)
        container = (result.stdout or "").strip()
        if not re.fullmatch(r"[a-f0-9]{64}", container):
            raise RuntimeError("Cannot identify the task container for dependency preparation")
        await self._docker(
            "run", "--detach", "--pull=never", "--name", name,
            "--network", f"container:{container}", "--user", f"{os.getuid()}:{os.getgid()}",
            "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
            "--cpus=1", "--memory=512m", "--pids-limit=128",
            "--mount", f"type=bind,source={self.settings['scripts_dir']},target=/proxy,readonly",
            "--mount", f"type=bind,source={cache},target=/cache",
            "--entrypoint", "python3", HELPER_IMAGE,
            "/proxy/pypi_wheel_cache.py", "--cache", "/cache", "--bind", "127.0.0.1",
            "--port", str(PORT), "--workers", "16", "--downloads", "2",
        )
        for _ in range(50):
            if '"kind": "ready"' in await self._docker("logs", name):
                if await self._reachable():
                    return
            await asyncio.sleep(.1)
        raise RuntimeError("Dependency cache did not become ready")

    async def _stop(self, name, phase, record):
        try:
            if await self._list(name):
                await self._docker("stop", "--time", "2", name)
                logs = await self._docker("logs", name)
                write_record(self.environment.evidence_dir / f"dependency-cache-{phase}-log.json", {"log": logs})
                await self._docker("rm", name)
            if await self._list(name) or await self._reachable():
                raise RuntimeError("Dependency cache cleanup was not confirmed")
            self.active_name = None
            record["removed"] = True
        finally:
            record["finished_at"] = datetime.now(timezone.utc).isoformat()
            write_record(self.environment.evidence_dir / f"dependency-cache-{phase}.json", record)

    @asynccontextmanager
    async def phase(self, phase):
        if phase not in {"setup", "verifier"} or phase in self.completed_phases:
            raise ValueError("Dependency cache phase must run once as setup or verifier")
        state = self.environment._integrity_state
        if (self.environment._in_agent_phase or self.active_name
                or (phase == "setup" and state["agent_phase"] != "not_started")
                or (phase == "verifier" and state["agent_phase"] not in {"completed", "interrupted"})):
            raise RuntimeError("Dependency cache cannot run during model work")
        await self.assert_stopped()
        name = "nanopy-pypi-" + uuid.uuid4().hex
        self.active_name = self.last_name = name
        record = {"protocol": PROTOCOL, "image": HELPER_IMAGE, "helper": name,
                  "scripts_sha256": self.settings["scripts_sha256"], "phase": phase,
                  "started_at": datetime.now(timezone.utc).isoformat(), "removed": False}
        try:
            await self._start(name)
            write_record(self.environment.evidence_dir / f"dependency-cache-{phase}.json", record)
            yield dict(ENV)
            self.completed_phases.add(phase)
        finally:
            # Cancellation of setup must not leave a network helper for the agent.
            cleanup = asyncio.create_task(self._stop(name, phase, record))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
