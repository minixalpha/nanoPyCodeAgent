"""Docker enforcement outside the evaluated process, with host-owned evidence.

Version one supports Linux Dockerfile/image tasks, not arbitrary Compose graphs.
It preserves task images and tests. Shared verification remains shared and is
explicitly recorded; this is not a replacement for separate verifier tasks.
"""

from contextlib import asynccontextmanager
import asyncio
import codecs
from datetime import datetime, timezone
import hashlib
from ipaddress import ip_address
import json
from pathlib import Path
import shlex
import tempfile
import tomllib

from harbor.environments.docker.docker import DockerEnvironment
from harbor.environments.base import ExecResult
from harbor.models.task.config import NetworkMode, NetworkPolicy, TaskOS

from .integrity import IntegrityPolicy, RULES_SHA256, write_record


_PROBE = '''import json, urllib.request, urllib.error, sys
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
try:
    with opener.open(sys.argv[1], timeout=15) as response:
        response.read(1)
    result = {"reachable": True}
except urllib.error.HTTPError:
    result = {"reachable": True}
except (OSError, ValueError) as error:
    result = {"reachable": False, "error_type": type(error).__name__,
              "reason_type": type(getattr(error, "reason", None)).__name__}
print(json.dumps(result))
'''


def dns_upstreams(resolv_conf):
    """Read Docker's trusted sidecar resolver, not the agent's writable copy."""
    candidates = []
    for line in resolv_conf.splitlines():
        if line.startswith("nameserver "):
            candidates.append(line.split()[1])
        elif line.startswith("# ExtServers: [") and line.endswith("]"):
            candidates.extend(line.removeprefix("# ExtServers: [")[:-1].split())
    addresses = set()
    for item in candidates:
        if item.startswith("host(") and item.endswith(")"):
            item = item[5:-1]
        address = ip_address(item)
        if not address.is_loopback:
            addresses.add(address.compressed)
    return sorted(addresses)


class IntegrityDockerEnvironment(DockerEnvironment):
    """Enable Harbor's external egress sidecar before any container starts."""

    def __init__(self, *, integrity_policy, dependency_cache=None, mounts=None, **kwargs):
        self.integrity_policy = IntegrityPolicy.model_validate(integrity_policy)
        policy = self.integrity_policy.network()
        self._separate_verifier = "__verifier__" in kwargs["session_id"]
        if kwargs["task_env_config"].os != TaskOS.LINUX:
            raise ValueError("restricted-v1 supports Linux Docker environments only")
        directory = Path(kwargs["environment_dir"])
        task_config = directory.parent / "task.toml"
        task_data = tomllib.loads(task_config.read_text()) if task_config.exists() else {}
        if task_data.get("steps"):
            raise ValueError("restricted-v1 supports single-step tasks only")
        verifier = task_data.get("verifier", {})
        if dependency_cache is not None and (
            self._separate_verifier or verifier.get("environment_mode") == "separate"
            or verifier.get("environment") is not None
        ):
            raise ValueError("Dependency cache currently requires a shared verifier")
        if (directory / "docker-compose.yaml").exists() or kwargs.get("extra_docker_compose"):
            raise ValueError("restricted-v1 does not support unreviewed Docker Compose services")
        if kwargs["task_env_config"].mcp_servers:
            raise ValueError("restricted-v1 does not support task MCP servers")
        self._integrity_baseline = kwargs.get("network_policy") or NetworkPolicy()
        # Do not widen a task's own baseline or phase restrictions.
        if not self._separate_verifier and any(p.network_mode != NetworkMode.PUBLIC for p in (
            self._integrity_baseline, *kwargs.get("phase_network_policies", ()),
        )):
            raise ValueError("restricted-v1 requires public native network policies; review restricted tasks separately")
        kwargs["phase_network_policies"] = [*kwargs.get("phase_network_policies", ()), policy]
        # Harbor 0.21 mounts verifier logs in the agent by default. Use file
        # transfer for all logs/artifacts; no host directory is agent-writable.
        super().__init__(mounts=[], **kwargs)
        if not self.capabilities.dynamic_network_policy:
            raise ValueError("Docker runtime cannot enforce integrity network policies")
        self._hardening_dir = tempfile.TemporaryDirectory(prefix="nanopy-integrity-")
        self._hardening_path = Path(self._hardening_dir.name) / "compose.json"
        self._hardening_path.write_text(json.dumps({"services": {"main": {
            "cap_drop": ["NET_RAW", "NET_ADMIN", "SYS_ADMIN", "SYS_PTRACE"],
            "security_opt": ["no-new-privileges:true"],
        }}}))
        # Keep controller evidence outside Harbor's native trial log rewriting
        # (including credential scrubbing), as well as outside every container.
        self.evidence_dir = self.trial_paths.trial_dir.parent / ".integrity" / self.trial_paths.trial_dir.name
        self._integrity_state = {
            "protocol": self.integrity_policy.protocol,
            "policy": self.integrity_policy.model_dump(),
            "rules_sha256": RULES_SHA256,
            "preflight": "pending", "agent_phase": "not_started",
            "host_mounts": False,
            "verifier_isolation": "task_defined; shared tasks remain shared",
        }
        self._in_agent_phase = False
        self._dns_upstreams = []
        self.dependency_cache = None
        if dependency_cache is not None:
            from .dependency_cache import DependencyCache
            self.dependency_cache = DependencyCache(self, dependency_cache)
            self._integrity_state["dependency_cache"] = {
                "protocol": dependency_cache["protocol"], "absent_before_agent": False,
            }
        if not self._separate_verifier:
            self._save()

    @property
    def capabilities(self):
        return super().capabilities.model_copy(update={"mounted": False})

    @property
    def _docker_compose_paths(self):
        paths = super()._docker_compose_paths
        if hasattr(self, "_hardening_path"):
            paths = [*paths, self._hardening_path]
        return paths

    def _save(self):
        write_record(self.evidence_dir / "enforcement.json", self._integrity_state)

    @staticmethod
    async def _collect_streamed_output(process, *, timeout_sec, stdin_data=None, on_output):
        """Preserve arbitrarily long JSON events without StreamReader line limits."""
        if process.stdout is None:
            raise RuntimeError("Streaming requires a captured stdout pipe")
        chunks = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        async def emit(text):
            if text:
                chunks.append(text)
                await on_output(text, "stdout")

        async def read():
            while data := await process.stdout.read(64 * 1024):
                await emit(decoder.decode(data))
            await emit(decoder.decode(b"", final=True))
            # Keep process exit inside the deadline even after stdout closes.
            await process.wait()

        async def write():
            if process.stdin is None:
                raise RuntimeError("stdin_data requires a stdin pipe")
            process.stdin.write(stdin_data)
            await process.stdin.drain()
            process.stdin.close()
            await process.stdin.wait_closed()

        async def collect():
            if stdin_data is None:
                await read()
            else:
                async with asyncio.TaskGroup() as group:
                    group.create_task(write())
                    group.create_task(read())

        try:
            if timeout_sec:
                await asyncio.wait_for(collect(), timeout=timeout_sec)
            else:
                await collect()
        except asyncio.TimeoutError:
            await DockerEnvironment._terminate_process(process)
            raise RuntimeError(f"Command timed out after {timeout_sec} seconds")
        except BaseException:
            if process.returncode is None:
                await DockerEnvironment._terminate_process(process)
            raise
        return ExecResult(stdout="".join(chunks) or None, stderr=None, return_code=process.returncode or 0)

    async def start(self, force_build):
        await super().start(force_build)
        self._dns_upstreams = dns_upstreams(await self._sidecar("cat", "/etc/resolv.conf"))
        self._integrity_state["dns_upstreams"] = self._dns_upstreams
        paths = ["/logs/verifier"] if self._separate_verifier else ["/logs/agent", "/logs/artifacts"]
        await self.ensure_dirs(paths)

    async def _apply_network_policy(self, network_policy):
        await super()._apply_network_policy(network_policy)
        if network_policy.network_mode == NetworkMode.ALLOWLIST:
            # Docker's embedded resolver forwards UDP from this namespace.
            # Permit DNS only to the daemon-selected resolver addresses. The
            # upstream 0.21 rules otherwise reject those forwarded datagrams.
            for address in self._dns_upstreams:
                family = "ip" if ip_address(address).version == 4 else "ip6"
                await self._sidecar("nft", "insert", "rule", "inet", "gost_egress", "egress",
                                    family, "daddr", address, "udp", "dport", "53", "accept")

    async def _probe(self, url):
        result = await self.exec(
            command=shlex.join(["python3", "-I", "-c", _PROBE, url]),
            timeout_sec=20, user="root",
        )
        if result.return_code != 0:
            raise RuntimeError("Integrity network probe could not execute")
        result = json.loads(result.stdout or "null")
        if not isinstance(result, dict) or type(result.get("reachable")) is not bool:
            raise RuntimeError("Integrity network probe returned invalid evidence")
        return result

    async def _sidecar(self, *command):
        result = await self._run_docker_compose_command([
            "exec", "--no-TTY", self._EGRESS_CONTROL_SERVICE_NAME, *command,
        ], timeout_sec=15)
        return result.stdout or ""

    async def _network_snapshot(self, name):
        show = await self._sidecar("network-policy", "show")
        rules = await self._sidecar("network-policy", "rules")
        # The sidecar runs outside the agent PID/mount namespace and the agent
        # has neither NET_ADMIN nor NET_RAW (which can also set SO_MARK).
        if "controlled egress" not in show or "table inet gost_egress" not in rules:
            raise RuntimeError("External egress enforcement is not active")
        write_record(self.evidence_dir / (name + ".json"), {
            "policy": show, "rules": rules,
        })

    async def integrity_preflight(self):
        """Require a working positive control before accepting a denied probe."""
        self._integrity_state["preflight"] = "running"
        self._save()
        try:
            if self.dependency_cache is not None:
                await self.dependency_cache.assert_stopped()
                if "setup" not in self.dependency_cache.completed_phases:
                    raise RuntimeError("Dependency cache setup did not complete")
            before = await self._probe(self.integrity_policy.probe_url)
            self._integrity_state["positive_control"] = before
            if not before["reachable"]:
                raise RuntimeError("Integrity positive control failed; blocking is unproven")
            await self.set_network_policy(self.integrity_policy.network())
            after = await self._probe(self.integrity_policy.probe_url)
            self._integrity_state["negative_control"] = after
            if after["reachable"]:
                raise RuntimeError("Integrity restriction failed: disallowed HTTPS remains reachable")
            if after.get("reason_type") == "gaierror":
                raise RuntimeError("Integrity negative control failed to resolve; HTTPS blocking is unproven")
            allowed = {}
            self._integrity_state["allowed_controls"] = allowed
            for host in self.integrity_policy.allowed_hosts:
                allowed[host] = await self._probe("https://" + host + "/")
                if not allowed[host]["reachable"]:
                    raise RuntimeError(f"Integrity allowed host is unreachable: {host}")
            self._integrity_state["allowed_controls"] = allowed
            await self._network_snapshot("network-preflight")
            self._integrity_state["preflight"] = "passed"
        except BaseException:
            self._integrity_state["preflight"] = "failed"
            raise
        finally:
            self._save()
        # Remain restricted after installation. The run boundary checks again.

    async def set_network_policy(self, network_policy):
        if getattr(self, "_in_agent_phase", False) and network_policy != self.integrity_policy.network():
            raise RuntimeError("Cannot relax network policy during model work")
        await super().set_network_policy(network_policy)

    @asynccontextmanager
    async def agent_phase(self):
        if self._integrity_state["preflight"] != "passed":
            raise RuntimeError("Integrity preflight must pass before model work")
        if self.dependency_cache is not None:
            await self.dependency_cache.assert_stopped()
            self._integrity_state["dependency_cache"]["absent_before_agent"] = True
        await self.set_network_policy(self.integrity_policy.network())
        await self._network_snapshot("network-before-agent")
        if (await self._probe(self.integrity_policy.probe_url))["reachable"]:
            raise RuntimeError("Integrity network restriction disappeared before model work")
        self._in_agent_phase = True
        self._integrity_state.update(agent_phase="running", started_at=datetime.now(timezone.utc).isoformat())
        self._save()
        stream_path = self.evidence_dir / "live-output.jsonl"
        try:
            with stream_path.open("x", encoding="utf-8") as output:
                stream_path.chmod(0o600)

                async def collect(text, stream):
                    output.write(json.dumps({"stream": str(stream), "text": text}) + "\n")
                    output.flush()

                with self.scoped_output_callback(collect):
                    yield
            self._integrity_state["agent_phase"] = "completed"
        except BaseException:
            self._integrity_state["agent_phase"] = "interrupted"
            raise
        finally:
            self._in_agent_phase = False
            self._integrity_state["finished_at"] = datetime.now(timezone.utc).isoformat()
            if stream_path.exists():
                with stream_path.open("rb") as source:
                    self._integrity_state["live_output_sha256"] = hashlib.file_digest(source, "sha256").hexdigest()
            self._save()
            await self._network_snapshot("network-after-agent")
            logs = await self._run_docker_compose_command([
                "logs", "--no-color", "--no-log-prefix", self._EGRESS_CONTROL_SERVICE_NAME,
            ], timeout_sec=15)
            write_record(self.evidence_dir / "egress-log.json", {"log": logs.stdout or ""})
            # Do not restore public access here, including on cancellation.

    async def prepare_verification(self):
        """Keep network evidence outside the sandbox before official tests run."""
        if self._separate_verifier:
            state = json.loads((self.evidence_dir / "enforcement.json").read_text())
            if state.get("agent_phase") not in {"completed", "interrupted"}:
                raise RuntimeError("Missing completed integrity agent boundary")
            state["verifier_isolation"] = "separate"
            write_record(self.evidence_dir / "enforcement.json", state)
            return
        if self._integrity_state["agent_phase"] not in {"completed", "interrupted"}:
            raise RuntimeError("Integrity agent phase never reached its end boundary")
        await self._network_snapshot("network-after-agent")
        self._integrity_state["verifier_isolation"] = "shared"
        self._integrity_state["verification_started_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        await self.ensure_dirs(["/logs/verifier"])
        await self.exec(command="rm -f /logs/verifier/reward.txt /logs/verifier/reward.json", user="root")
        # Official shared verifiers may install dependencies. This transition
        # is explicitly recorded and does not claim independent verification.
        await self.set_network_policy(self._integrity_baseline)
