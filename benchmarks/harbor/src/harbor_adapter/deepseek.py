"""Run the upstream DeepSeek benchmark profile from hash-pinned local wheels."""

import asyncio
import hashlib
import json
from pathlib import Path
import re
import shlex
import uuid

from harbor.agents.installed.base import with_prompt_template
from harbor.agents.model_connection import ModelConnectionSpec

from .adapter import NanoPyCodeAgent
from .pi import distribution_digest

_RUNNER = Path(__file__).with_name("_agent_runner.py").read_text()
_CLIENT = Path(__file__).with_name("_dsh_client.py").read_text()
_PYTHON = "/opt/harbor-dsh-venv/bin/python"


def distribution_files(root: Path) -> dict:
    """Pin the complete offline wheelhouse, including source provenance."""
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("DeepSeek distributions must not contain symbolic links")
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files[path.relative_to(root).as_posix()] = {
                "sha256": digest, "mode": path.stat().st_mode & 0o777,
            }
    manifest = json.loads((root / "distribution.json").read_text())
    required = {"version", "source_commit", "source_archive_sha256", "sdk_wheel", "runtime_wheel"}
    if set(manifest) != required or not re.fullmatch(r"[0-9a-f]{40}", manifest["source_commit"]):
        raise ValueError("DeepSeek distribution requires public source provenance")
    if not re.fullmatch(r"[0-9a-f]{64}", manifest["source_archive_sha256"]):
        raise ValueError("DeepSeek source archive SHA256 is required")
    for key in ("sdk_wheel", "runtime_wheel"):
        filename = manifest[key]
        if Path(filename).name != filename or not filename.endswith(".whl") or f"wheels/{filename}" not in files:
            raise ValueError("DeepSeek distribution requires SDK and runtime wheels")
    return files


class DeepSeekHarnessAgent(NanoPyCodeAgent):
    """Preserve the official sdk-minimal prompt, tools, and agent loop."""

    SUPPORTS_ATIF = False
    MODEL_CONNECTION = ModelConnectionSpec(api_key_envs=("DEEPSEEK_API_KEY",))
    CLI_FLAGS = []

    def __init__(self, *args, distribution_path: str, distribution_sha256: str,
                 reasoning_effort: str = "high", **kwargs):
        self._distribution = Path(distribution_path).expanduser().resolve()
        self._distribution_sha256 = distribution_sha256
        self._manifest = json.loads((self._distribution / "distribution.json").read_text())
        if reasoning_effort not in {"off", "low", "high", "max"}:
            raise ValueError("Unsupported DeepSeek reasoning effort")
        self._reasoning_effort = reasoning_effort
        super().__init__(*args, version=self._manifest["version"], **kwargs)
        provider, separator, model = (self.model_name or "").partition("/")
        if provider != "deepseek" or not separator or not model:
            raise ValueError("DeepSeek Harness requires deepseek/model")

    @staticmethod
    def name() -> str:
        return "deepseek-harness"

    def get_version_command(self) -> str:
        return "/opt/harbor-dsh-venv/bin/dsh --version"

    def parse_version(self, stdout: str) -> str:
        return stdout.strip().splitlines()[-1]

    async def _install_agent(self, environment) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "process-supervision-required").write_text("deepseek-harness\n")
        actual = distribution_digest(distribution_files(self._distribution))
        if actual != self._distribution_sha256:
            raise ValueError("DeepSeek distribution changed after registration")
        await environment.upload_dir(self._distribution, "/opt/harbor-dsh")
        sdk = "/opt/harbor-dsh/wheels/" + self._manifest["sdk_wheel"]
        await self.exec_as_root(environment, command=(
            "set -euo pipefail; "
            "if ! command -v uv >/dev/null 2>&1; then "
            "curl -LsSf https://astral.sh/uv/0.9.11/install.sh | sh; fi; "
            'export PATH="$HOME/.local/bin:$PATH"; '
            "uv venv --python 3.13 /opt/harbor-dsh-venv; "
            "uv pip install --python /opt/harbor-dsh-venv/bin/python "
            "--no-index --find-links /opt/harbor-dsh/wheels " + shlex.quote(sdk)
        ))
        await self._upload_config_text(
            environment, content=_CLIENT, remote_path="/opt/harbor-dsh-client.py",
            filename="dsh-client.py",
        )
        version = await self.exec_as_agent(environment, command=self.get_version_command())
        if self.parse_version(version.stdout) != self._manifest["version"]:
            raise ValueError("Installed DeepSeek version differs from its distribution")
        self._bootstrap_record.update(
            deepseek_version=self._manifest["version"], distribution_sha256=actual,
            source_commit=self._manifest["source_commit"], profile="sdk-minimal",
        )
        probe = f"/tmp/harbor-dsh-probe-{uuid.uuid4().hex}"
        command = shlex.join([
            _PYTHON, "/opt/harbor-dsh-client.py", "--home", probe + "-home",
            "--model", self.model_name.split("/", 1)[1],
            "--reasoning-effort", self._reasoning_effort, "--preflight",
        ])
        initialized = await self.exec_as_agent(
            environment,
            command=shlex.join(["python3", "-I", "-c", _RUNNER, "run", probe + ".json", probe + "-result.json", command]),
            env={"DEEPSEEK_API_KEY": "preflight-only", "DEEPSEEK_BASE_URL": "https://api.deepseek.com/anthropic"},
        )
        if not any(line.strip().startswith('{"initialized": true,') for line in initialized.stdout.splitlines()):
            raise ValueError("DeepSeek SDK initialization did not complete")
        self._bootstrap_record["process_supervision_probe"] = "passed"
        self._bootstrap_record["sdk_initialization"] = "passed"

    @with_prompt_template
    async def run(self, instruction, environment, context) -> None:
        key = self.model_connection.api_key
        if not key:
            raise ValueError("DEEPSEEK_API_KEY is required for DeepSeek model work")
        await self._upload_config_text(
            environment, content=instruction, remote_path="/tmp/harbor-dsh-instruction.txt",
            filename="dsh-instruction.txt",
        )
        command = shlex.join([
            _PYTHON, "/opt/harbor-dsh-client.py", "--home", "/logs/agent/dsh",
            "--model", self.model_name.split("/", 1)[1],
            "--reasoning-effort", self._reasoning_effort,
            "--instruction", "/tmp/harbor-dsh-instruction.txt",
        ]) + " > /logs/agent/dsh-stdout.txt 2> /logs/agent/dsh-stderr.txt"
        control = f"/tmp/harbor-dsh-{uuid.uuid4().hex}.json"
        record = "/logs/agent/process-supervision.json"
        try:
            await self.exec_as_agent(
                environment,
                command=shlex.join(["python3", "-I", "-c", _RUNNER, "run", control, record, command]),
                env={"DEEPSEEK_API_KEY": key, "DEEPSEEK_BASE_URL": "https://api.deepseek.com/anthropic"},
            )
        except BaseException:
            cleanup = await asyncio.shield(asyncio.wait_for(environment.exec(
                command=shlex.join(["python3", "-I", "-c", _RUNNER, "cancel", control, record]), user="root",
            ), timeout=12))
            if cleanup.return_code != 0:
                raise RuntimeError("DeepSeek subprocess cleanup did not confirm cancellation")
            raise

    def populate_context_post_run(self, context) -> None:
        context.metadata = context.metadata or {}
        context.metadata["bootstrap"] = self._bootstrap_record
        supervision_path = self.logs_dir / "process-supervision.json"
        try:
            supervision = json.loads(supervision_path.read_text())
        except (OSError, ValueError):
            supervision = {"status": "missing_or_invalid"}
        context.metadata["process_supervision"] = supervision
        usage, missing, malformed = [], 0, 0
        path = self.logs_dir / "dsh-events.jsonl"
        if path.exists():
            with path.open() as stream:
                for line in stream:
                    try:
                        event = json.loads(line)["payload"]["event"]
                        if event["type"] not in {"assistant/message", "assistant/attempt", "compaction/summary"}:
                            continue
                        value = event["data"].get("usage")
                        if value is None:
                            missing += 1
                        else:
                            usage.append(value)
                    except (ValueError, KeyError, TypeError):
                        malformed += 1
        context.metadata["deepseek_harness"] = {
            "profile": "sdk-minimal", "source_commit": self._manifest["source_commit"],
            "usage_records": len(usage), "missing_usage_records": missing,
            "malformed_event_records": malformed,
            "usage_is_partial": not usage or bool(missing or malformed) or supervision.get("status") != "completed" or supervision.get("return_code") != 0,
            "cost_is_unknown": True,
        }
        if usage:
            # The native Messages adapter counts uncached input separately.
            context.n_input_tokens = sum(u["inputTokens"] + u.get("cacheReadTokens", 0) + u.get("cacheWriteTokens", 0) for u in usage)
            context.n_output_tokens = sum(u["outputTokens"] for u in usage)
            context.n_cache_tokens = sum(u.get("cacheReadTokens", 0) for u in usage)
