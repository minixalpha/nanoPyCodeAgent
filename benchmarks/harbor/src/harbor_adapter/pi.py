"""Run an unmodified, hash-pinned Pi distribution with shared Harbor bootstrap."""

import asyncio
import hashlib
import json
from pathlib import Path
import shlex
import uuid

from harbor.agents.installed.base import CliFlag, with_prompt_template
from harbor.agents.model_connection import ModelConnectionSpec

from .adapter import NanoPyCodeAgent

_RUNNER = Path(__file__).with_name("_agent_runner.py").read_text()


def distribution_files(root: Path) -> dict:
    """Include executable permissions and reject links outside the snapshot."""
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("Pi distributions must not contain symbolic links")
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files[path.relative_to(root).as_posix()] = {
                "sha256": digest, "mode": path.stat().st_mode & 0o777,
            }
    if "pi" not in files or "package.json" not in files:
        raise ValueError("Pi distribution requires pi and package.json")
    return files


def distribution_digest(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def read_model_config(path: Path) -> dict:
    """Accept a public DeepSeek connection; credentials stay in the environment."""
    config = json.loads(path.read_text())
    if set(config) != {"providers"} or set(config["providers"]) != {"deepseek"}:
        raise ValueError("Pi benchmark models must configure only DeepSeek")
    provider = config["providers"]["deepseek"]
    if (set(provider) - {"api", "apiKey", "baseUrl", "models"}
            or provider.get("apiKey") != "${DEEPSEEK_API_KEY}"
            or provider.get("api") != "openai-completions"
            or provider.get("baseUrl") != "https://api.deepseek.com"):
        raise ValueError("Pi models must use the official API and an environment key reference")
    if not provider.get("models"):
        raise ValueError("Pi models must explicitly register at least one model")
    return config


class PiCodeAgent(NanoPyCodeAgent):
    """Share verified dependencies/preflight, replacing Nano's install and run."""

    SUPPORTS_ATIF = False
    MODEL_CONNECTION = ModelConnectionSpec(api_key_envs=("DEEPSEEK_API_KEY",))
    CLI_FLAGS = [CliFlag("thinking", cli="--thinking", type="enum", choices=[
        "off", "minimal", "low", "medium", "high", "xhigh", "max",
    ])]

    def __init__(self, *args, distribution_path: str, distribution_sha256: str,
                 model_config_path: str, **kwargs):
        self._distribution = Path(distribution_path).resolve()
        self._distribution_sha256 = distribution_sha256
        self._model_config = read_model_config(Path(model_config_path))
        package = json.loads((self._distribution / "package.json").read_text())
        self._pi_version = package["version"]
        super().__init__(*args, version=self._pi_version, **kwargs)
        provider, separator, model = (self.model_name or "").partition("/")
        if provider != "deepseek" or not separator or model not in {
            item["id"] for item in self._model_config["providers"][provider]["models"]
        }:
            raise ValueError("Pi model_name must identify a registered deepseek/model")

    @staticmethod
    def name() -> str:
        return "pi"

    def get_version_command(self) -> str:
        return "/opt/harbor-pi/pi --version"

    def parse_version(self, stdout: str) -> str:
        return stdout.strip().splitlines()[-1]

    async def _install_agent(self, environment) -> None:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        (self.logs_dir / "process-supervision-required").write_text("pi\n")
        actual = distribution_digest(distribution_files(self._distribution))
        if actual != self._distribution_sha256:
            raise ValueError("Pi distribution changed after registration")
        await environment.upload_dir(self._distribution, "/opt/harbor-pi")
        await self.exec_as_root(environment, command="chmod 755 /opt/harbor-pi/pi")
        result = await self.exec_as_agent(environment, command=self.get_version_command())
        if self.parse_version(result.stdout) != self._pi_version:
            raise ValueError("Installed Pi version differs from its distribution")
        self._bootstrap_record.update(
            pi_version=self._pi_version, distribution_sha256=actual,
        )
        await self.exec_as_agent(environment, command="mkdir -p /tmp/harbor-pi-agent")
        await self._upload_config_text(
            environment, content=json.dumps(self._model_config),
            remote_path="/tmp/harbor-pi-agent/models.json", filename="models.json",
        )
        probe = f"/tmp/harbor-pi-supervision-probe-{uuid.uuid4().hex}"
        await self.exec_as_agent(environment, command=shlex.join([
            "python3", "-I", "-c", _RUNNER, "run", probe + ".json", probe + "-result.json", "true",
        ]))
        self._bootstrap_record["process_supervision_probe"] = "passed"
        # Validate the real binary and provider configuration without a model call.
        await self.exec_as_agent(
            environment,
            command="/opt/harbor-pi/pi --offline --list-models deepseek-flash",
            env={"PI_CODING_AGENT_DIR": "/tmp/harbor-pi-agent", "DEEPSEEK_API_KEY": "preflight-only"},
        )

    @with_prompt_template
    async def run(self, instruction, environment, context) -> None:
        key = self.model_connection.api_key
        if not key:
            raise ValueError("DEEPSEEK_API_KEY is required for Pi model work")
        _, model = self.model_name.split("/", 1)
        # Keep completed events and native sessions; streaming deltas duplicate
        # their contents and can consume substantial disk space.
        event_filter = (
            "import json,sys\n"
            "for line in sys.stdin:\n"
            " try: skip=json.loads(line).get('type') == 'message_update'\n"
            " except (ValueError,AttributeError): skip=False\n"
            " if not skip: print(line,end='',flush=True)\n"
        )
        command = (
            "set -euo pipefail; /opt/harbor-pi/pi --print --mode json --offline "
            "--session-dir /logs/agent/pi/sessions "
            f"--provider deepseek --model {shlex.quote(model)} "
            f"{self.build_cli_flags()} -- {shlex.quote(instruction)} "
            "</dev/null 2>/logs/agent/pi-stderr.txt | "
            f"python3 -I -u -c {shlex.quote(event_filter)} | tee /logs/agent/pi.txt"
        )
        control = f"/tmp/harbor-pi-{uuid.uuid4().hex}.json"
        record = "/logs/agent/process-supervision.json"
        try:
            await self.exec_as_agent(
                environment,
                command=shlex.join(["python3", "-I", "-c", _RUNNER, "run", control, record, command]),
                env={"PI_CODING_AGENT_DIR": "/tmp/harbor-pi-agent", "DEEPSEEK_API_KEY": key},
            )
        except BaseException:
            cleanup = await asyncio.shield(asyncio.wait_for(environment.exec(
                command=shlex.join(["python3", "-I", "-c", _RUNNER, "cancel", control, record]), user="root",
            ), timeout=12))
            if cleanup.return_code != 0:
                raise RuntimeError("Pi subprocess cleanup did not confirm cancellation")
            raise
        # Pi may finish its event stream after an API error with exit code zero.
        # Do not misclassify that as an ordinary scored task failure.
        check = (
            "import json\n"
            "last={}; assistant={}\n"
            "for line in open('/logs/agent/pi.txt'):\n"
            " try: event=json.loads(line)\n"
            " except ValueError: continue\n"
            " last=event\n"
            " if event.get('type')=='message_end' and event.get('message',{}).get('role')=='assistant': assistant=event['message']\n"
            "print(json.dumps({'settled': last.get('type')=='agent_settled' and not last.get('aborted'), 'stop_reason': assistant.get('stopReason')}))\n"
        )
        output = await self.exec_as_agent(environment, command=f"python3 -I -c {shlex.quote(check)}")
        status = json.loads(output.stdout)
        if not status["settled"] or status["stop_reason"] != "stop":
            raise RuntimeError(f"Pi did not finish successfully: {status}")

    def populate_context_post_run(self, context) -> None:
        context.metadata = context.metadata or {}
        context.metadata["bootstrap"] = self._bootstrap_record
        supervision = None
        supervision_path = self.logs_dir / "process-supervision.json"
        if supervision_path.exists():
            try:
                supervision = json.loads(supervision_path.read_text())
            except (OSError, ValueError):
                supervision = {"status": "invalid"}
            context.metadata["process_supervision"] = supervision
        interrupted = supervision is not None and (
            not isinstance(supervision, dict) or supervision.get("status") != "completed"
            or supervision.get("return_code") != 0
        )
        output = self.logs_dir / "pi.txt"
        if not output.exists():
            return
        usages, missing = [], 0
        errors = []
        for line in output.read_text().split("\n"):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            message = event.get("message", {})
            if event.get("type") == "message_end" and message.get("role") == "assistant":
                if message.get("stopReason") in {"error", "aborted"}:
                    errors.append(message.get("stopReason"))
                if "usage" in message:
                    usages.append(message["usage"])
                else:
                    missing += 1
            elif event.get("type") == "compaction_end" and event.get("result"):
                usage = event["result"].get("usage")
                if usage:
                    usages.append(usage)
                else:
                    missing += 1
        context.metadata["pi"] = {
            "version": self._pi_version, "usage_records": len(usages),
            "missing_usage_records": missing, "assistant_errors": errors,
            "cost_is_estimated": True,
            "usage_is_partial": missing > 0 or interrupted,
        }
        if usages:
            context.n_input_tokens = sum(u.get("input", 0) + u.get("cacheRead", 0) + u.get("cacheWrite", 0) for u in usages)
            context.n_output_tokens = sum(u.get("output", 0) for u in usages)
            context.n_cache_tokens = sum(u.get("cacheRead", 0) for u in usages)
            costs = [u["cost"]["total"] for u in usages if "total" in u.get("cost", {})]
            context.cost_usd = sum(costs) if len(costs) == len(usages) else None
            context.metadata["pi"]["cost_is_partial"] = missing > 0 or len(costs) != len(usages) or interrupted
