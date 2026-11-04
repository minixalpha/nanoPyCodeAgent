"""Repository benchmark entry point with recorded source and bootstrap policy."""

import argparse
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

from harbor.models.job.config import JobConfig

from .bootstrap import AptCache, default_cache_dir
from .deepseek import distribution_files as deepseek_distribution_files
from .pi import distribution_digest, distribution_files, read_model_config
from .integrity import IntegrityPolicy, RULES, RULES_SHA256

_NANO = "harbor_adapter:NanoPyCodeAgent"
_PI = "harbor_adapter:PiCodeAgent"
_DEEPSEEK = "harbor_adapter:DeepSeekHarnessAgent"


def standard_config(raw: dict) -> JobConfig:
    """Validate policy before building or creating a benchmark environment."""
    raw = json.loads(json.dumps(raw))
    integrity = IntegrityPolicy.model_validate(raw.pop("integrity")) if "integrity" in raw else None
    raw.setdefault("retry", {"max_retries": 0})
    raw.setdefault("n_concurrent_trials", 1)
    raw.setdefault("verifier", {
        "import_path": "harbor_adapter:RetryingVerifier",
        "kwargs": {"max_attempts": 3},
    })
    raw.setdefault("verifier_timeout_multiplier", 4)
    config = JobConfig.model_validate(raw)
    if config.retry.max_retries != 0:
        raise ValueError("The standard workflow disables whole-trial retries")
    if config.verifier.import_path != "harbor_adapter:RetryingVerifier":
        raise ValueError("The standard workflow requires RetryingVerifier")
    attempts = config.verifier.kwargs.get("max_attempts", 3)
    if type(attempts) is not int or attempts != 3:
        raise ValueError("The standard workflow requires max_attempts=3")
    if (
        config.verifier_timeout_multiplier != 4
        or config.verifier.override_timeout_sec is not None
        or config.verifier.max_timeout_sec is not None
    ):
        raise ValueError(
            "Use native per-attempt timeouts and verifier_timeout_multiplier=4"
        )
    if (config.verifier.disable and not config.install_only) or config.source_jobs:
        raise ValueError("The standard workflow runs fresh trials with verification enabled")
    if not config.tasks and not config.datasets:
        raise ValueError("Select at least one task or dataset")
    if not config.agents or config.n_attempts < 1:
        raise ValueError("Select at least one agent and one trial attempt")
    for agent in config.agents:
        identifiers = [value for value in (agent.import_path, agent.name) if value]
        if not identifiers or len(set(identifiers)) != 1 or identifiers[0] not in {_NANO, _PI, _DEEPSEEK}:
            raise ValueError("The standard workflow requires a repository benchmark adapter")
        allowed = ({"max_turns", "max_tokens", "time_budget_seconds"}
                   if identifiers[0] == _NANO else {
                       "distribution_path", "distribution_sha256", "model_config_path", "thinking",
                   } if identifiers[0] == _PI else {
                       "distribution_path", "distribution_sha256", "reasoning_effort",
                   })
        if agent.env or set(agent.kwargs) - allowed:
            raise ValueError(
                "Pass model credentials through the environment; "
                "agent kwargs must use the adapter's supported public settings"
            )
        if identifiers[0] == _PI:
            required = {"distribution_path", "distribution_sha256", "model_config_path"}
            if not required <= agent.kwargs.keys():
                raise ValueError("Pi requires a hash-pinned distribution and public model config")
            read_model_config(Path(agent.kwargs["model_config_path"]))
        if identifiers[0] == _DEEPSEEK:
            if not {"distribution_path", "distribution_sha256"} <= agent.kwargs.keys():
                raise ValueError("DeepSeek requires a hash-pinned distribution")
            if integrity is None and config.verifier.kwargs.get("require_agent_quiescence") is not True:
                raise ValueError("DeepSeek requires confirmed agent quiescence before grading")
            if agent.kwargs.get("reasoning_effort", "high") not in {"off", "low", "high", "max"}:
                raise ValueError("Unsupported DeepSeek reasoning effort")
        if not agent.model_name:
            raise ValueError("Each agent requires an explicit model_name")
    if integrity is not None:
        integrity.network()
        if config.artifacts or config.extra_instruction_paths or config.timeout_multiplier != 1 or config.agent_timeout_multiplier not in (None, 1):
            raise ValueError("restricted-v1 preserves task artifacts and native timeouts")
        if config.environment.import_path or config.environment.type not in (None, "docker"):
            raise ValueError("restricted-v1 requires the Docker environment")
        if (
            any(getattr(config.environment, field) is not None for field in (
                "override_cpus", "override_memory_mb", "override_storage_mb",
                "override_gpus", "override_tpu",
            ))
            or config.environment.cpu_enforcement_policy not in {"auto", "limit"}
            or config.environment.memory_enforcement_policy not in {"auto", "limit"}
        ):
            raise ValueError(
                "restricted-v1 preserves native resource budgets: resource overrides "
                "are forbidden and CPU/memory enforcement must be auto or limit"
            )
        if (config.environment.mounts or config.environment.extra_docker_compose
                or config.environment.kwargs or config.environment.extra_allowed_hosts
                or config.environment.env):
            raise ValueError("restricted-v1 rejects extra mounts, Compose services, environment overrides, and network overrides")
        for agent in config.agents:
            if (agent.skills or agent.mcp_servers or agent.extra_allowed_hosts
                    or agent.load_trajectory or agent.resume_trajectory
                    or agent.include_logs or agent.exclude_logs
                    or agent.override_timeout_sec is not None or agent.max_timeout_sec is not None):
                raise ValueError("restricted-v1 requires fresh agents, complete logs, and no external tools or network overrides")
            agent.kwargs["integrity_policy"] = integrity.model_dump()
        if config.verifier.include_logs or config.verifier.exclude_logs or config.verifier.env:
            raise ValueError("restricted-v1 requires complete verifier logs")
        if any(config.verifier.kwargs.get(key) for key in ("retry_dependency_errors", "retry_collection_errors")):
            raise ValueError("Only verifier timeouts may retry")
        config.environment.type = None
        config.environment.import_path = "harbor_adapter:IntegrityDockerEnvironment"
        config.environment.kwargs["integrity_policy"] = integrity.model_dump()
        config.verifier.kwargs["require_agent_quiescence"] = True
    return config


def snapshot_deepseek(agent, cache: Path, record: Path) -> dict:
    """Publish a verified, immutable offline wheelhouse for all task installs."""
    original = Path(agent.kwargs["distribution_path"]).expanduser().resolve()
    files = deepseek_distribution_files(original)
    digest = distribution_digest(files)
    if digest != agent.kwargs["distribution_sha256"]:
        raise ValueError("DeepSeek distribution differs from its registered SHA256")
    destination = cache / "deepseek-distributions" / digest
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=digest + ".tmp-", dir=destination.parent) as temporary:
            staged = Path(temporary) / "distribution"
            shutil.copytree(original, staged)
            if deepseek_distribution_files(staged) != files:
                raise ValueError("DeepSeek distribution changed while snapshotting")
            try:
                staged.rename(destination)
            except OSError as error:
                if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
    if deepseek_distribution_files(destination) != files:
        raise ValueError("Cached DeepSeek distribution is corrupt")
    agent.kwargs["distribution_path"] = str(destination)
    return {"distribution_sha256": digest, "files": files,
            "provenance": json.loads((destination / "distribution.json").read_text())}


def snapshot_pi(agent, cache: Path, record: Path) -> dict:
    """Share one content-addressed binary snapshot across the full task pool."""
    original = Path(agent.kwargs["distribution_path"]).expanduser().resolve()
    files = distribution_files(original)
    digest = distribution_digest(files)
    if digest != agent.kwargs["distribution_sha256"]:
        raise ValueError("Pi distribution differs from its registered SHA256")
    destination = cache / "pi-distributions" / digest
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=digest + ".tmp-", dir=destination.parent) as temporary:
            staged = Path(temporary) / "distribution"
            shutil.copytree(original, staged)
            if distribution_files(staged) != files:
                raise ValueError("Pi distribution changed while snapshotting")
            try:
                staged.rename(destination)
            except OSError as error:
                if error.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
                # Another invocation published first. Validate its bytes below
                # before reusing it; never overwrite a corrupt cache entry.
    if distribution_files(destination) != files:
        raise ValueError("Cached Pi distribution is corrupt")
    public_models = read_model_config(Path(agent.kwargs["model_config_path"]))
    model_bytes = (json.dumps(public_models, indent=2) + "\n").encode()
    model_digest = hashlib.sha256(model_bytes).hexdigest()
    models = record / "pi-models.json"
    if models.exists() and models.read_bytes() != model_bytes:
        models = record / f"pi-models-{model_digest}.json"
    if models.exists():
        if models.read_bytes() != model_bytes:
            raise ValueError("Recorded Pi model configuration is corrupt")
    else:
        models.write_bytes(model_bytes)
    agent.kwargs.update(distribution_path=str(destination), model_config_path=str(models))
    return {
        "distribution_sha256": digest, "files": files,
        "model_config_file": models.name, "model_config_sha256": model_digest,
    }


def summarize(job_dir: Path, *, install_only: bool = False) -> dict:
    trials = []
    for path in sorted(job_dir.glob("*/result.json")):
        result = json.loads(path.read_text())
        bootstrap_path = path.parent / "agent/bootstrap.json"
        bootstrap = json.loads(bootstrap_path.read_text()) if bootstrap_path.exists() else {}
        exception = result.get("exception_info")
        verifier = result.get("verifier_result") or {}
        retry_path = path.parent / "verifier/retry-summary.json"
        if exception:
            status = "setup_failed" if bootstrap.get("status") == "failed" else "execution_error"
        elif install_only and bootstrap.get("status") == "ready":
            status = "setup_passed"
        else:
            status = "scored" if verifier.get("rewards") is not None else "unscored"
        trials.append({
            "task": result.get("task_name"), "trial": path.parent.name,
            "status": status,
            "exception_type": exception.get("exception_type") if exception else None,
            "rewards": None if exception else verifier.get("rewards"),
            "bootstrap": bootstrap,
            "verifier_attempts": json.loads(retry_path.read_text()) if retry_path.exists() else None,
        })
    return {"trials": trials}


def run(args) -> int:
    root = Path.cwd()
    if not (root / "src/nanopycodeagent").is_dir():
        raise ValueError("Run from the nanoPyCodeAgent repository root")
    raw = json.loads(args.config.read_text())
    if "integrity" not in raw and not getattr(args, "legacy_open_network", False):
        raise ValueError("New runs require an integrity policy; use --legacy-open-network only for explicitly registered historical-protocol runs")
    if "integrity" in raw and getattr(args, "legacy_open_network", False):
        raise ValueError("Cannot combine integrity with --legacy-open-network")
    config = standard_config(raw)
    if args.job_name:
        config.job_name = args.job_name
    if Path(config.job_name).name != config.job_name or config.job_name in {".", ".."}:
        raise ValueError("job_name must be a single directory name")
    config.install_only = args.install_only or config.install_only
    config.jobs_dir = config.jobs_dir.resolve()
    job_dir = config.jobs_dir / config.job_name
    record = config.jobs_dir / (config.job_name + "-input")
    if job_dir.exists() or record.exists():
        raise ValueError("Use a new job_name; existing jobs and inputs are never overwritten")
    record.mkdir(parents=True)
    record.chmod(0o700)
    source = record / "source"
    shutil.copytree(root / "benchmarks/harbor/src/harbor_adapter", source / "harbor_adapter", ignore=shutil.ignore_patterns("__pycache__"))
    cache = args.cache_dir.expanduser().resolve()
    wheel = None
    if any((agent.import_path or agent.name) == _NANO for agent in config.agents):
        shutil.copytree(root / "src/nanopycodeagent", source / "nanopycodeagent", ignore=shutil.ignore_patterns("__pycache__"))
        subprocess.run(["uv", "build", "--wheel", "--out-dir", str(record / "dist")], check=True)
        wheel, = (record / "dist").glob("*.whl")
        with ZipFile(wheel) as archive:
            for path in (source / "nanopycodeagent").rglob("*.py"):
                if archive.read(path.relative_to(source).as_posix()) != path.read_bytes():
                    raise ValueError("Source changed during preparation; prepare a new job")
    pi_inputs, deepseek_inputs = [], []
    for agent in config.agents:
        if (agent.import_path or agent.name) == _PI:
            pi_inputs.append(snapshot_pi(agent, cache, record))
        elif (agent.import_path or agent.name) == _DEEPSEEK:
            deepseek_inputs.append(snapshot_deepseek(agent, cache, record))
        else:
            agent.kwargs["wheel_path"] = str(wheel)
        agent.kwargs["bootstrap_cache"] = str(cache)
    config_path = record / "config.json"
    config_path.write_text(config.model_dump_json(indent=2) + "\n")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "source_kind": "working tree including uncommitted files",
        "source_sha256": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob("*.py"))},
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest() if wheel else None,
        "cache_dir": str(cache),
        "evaluation_protocol": raw.get("integrity", {"protocol": "legacy-open-network"}),
        "integrity_rules_sha256": RULES_SHA256 if "integrity" in raw else None,
    }
    if "integrity" in raw:
        (record / "integrity-rules.txt").write_text(RULES)
    if pi_inputs:
        manifest["pi_inputs"] = pi_inputs
    if deepseek_inputs:
        manifest["deepseek_inputs"] = deepseek_inputs
    (record / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (record / "working-tree.patch").write_bytes(subprocess.check_output(["git", "diff", "HEAD"]))
    print(f"Prepared {record}", flush=True)
    if args.prepare_only:
        return 0
    env = dict(os.environ)
    env["PYTHONPATH"] = str(source)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    code = None
    try:
        with (record / "harbor.log").open("w") as log:
            code = subprocess.run(
                ["harbor", "run", "--config", str(config_path), "--yes"],
                env=env, stdout=log, stderr=subprocess.STDOUT,
            ).returncode
    finally:
        summary = summarize(job_dir, install_only=config.install_only)
        summary["harbor_exit_code"] = code
        (record / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Results: {record / 'summary.json'}", flush=True)
    if "integrity" in raw and not config.install_only and (job_dir / "result.json").exists():
        from .audit import audit_job
        audit = audit_job(job_dir, record / "audit")
        summary["integrity_audit"] = {"path": str(record / "audit" / "audit.json"), **audit["summary"]}
        (record / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"Integrity review: {record / 'audit' / 'audit.json'}", flush=True)
    incomplete = not summary["trials"] or any(
        row["status"] not in {"scored", "setup_passed"} for row in summary["trials"]
    )
    return code or int(incomplete)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    benchmark = commands.add_parser("run", help="Record the working tree and run the standard Harbor workflow")
    benchmark.add_argument("--config", type=Path, required=True)
    benchmark.add_argument("--job-name")
    benchmark.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    benchmark.add_argument("--prepare-only", action="store_true", help="Build and record inputs without starting containers or calling the model")
    benchmark.add_argument("--install-only", action="store_true", help="Run setup and dependency preflight without calling the model or verifier")
    benchmark.add_argument("--legacy-open-network", action="store_true", help="Explicitly reproduce an earlier protocol without integrity enforcement")
    audit = commands.add_parser("audit", help="Freeze completed outputs and produce evidence-bound integrity accounting")
    audit.add_argument("--job-dir", type=Path, required=True)
    audit.add_argument("--output-dir", type=Path, required=True)
    audit.add_argument("--review", type=Path, help="Reviewed verdicts bound to this output freeze")
    cache = commands.add_parser("import-apt", help="Import a manifest and its sibling packages/ directory")
    cache.add_argument("manifest", type=Path)
    cache.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    retained = commands.add_parser("verify-retained", help="Run an authorized verifier batch on an unchanged retained solution, without model calls")
    retained.add_argument("--trial-dir", type=Path, required=True)
    retained.add_argument("--task-dir", type=Path, required=True)
    retained.add_argument("--container", required=True)
    retained.add_argument("--output-dir", type=Path, required=True)
    retained.add_argument("--max-attempts", type=int, default=3)
    retained.add_argument("--dependency-timeout-sec", type=float, help="Prepare a reviewed dependency profile before verification, with a separate deadline")
    retained.add_argument("--retry-dependency-errors", action="store_true")
    retained.add_argument("--retry-collection-errors", action="store_true")
    args = parser.parse_args()
    if args.command == "audit":
        from .audit import audit_job
        audit_job(args.job_dir, args.output_dir, args.review)
        return 0
    if args.command == "verify-retained":
        from .retained import verify_retained
        return verify_retained(args)
    if args.command == "import-apt":
        count = AptCache(args.cache_dir.expanduser().resolve()).import_manifest(args.manifest)
        print(f"Imported {count} verified APT packages into {args.cache_dir}")
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
