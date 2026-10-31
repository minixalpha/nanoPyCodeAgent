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

_NANO = "harbor_adapter:NanoPyCodeAgent"
_PI = "harbor_adapter:PiCodeAgent"
_DEEPSEEK = "harbor_adapter:DeepSeekHarnessAgent"


def standard_config(raw: dict) -> JobConfig:
    """Validate policy before building or creating a benchmark environment."""
    raw = json.loads(json.dumps(raw))
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
            if config.verifier.kwargs.get("require_agent_quiescence") is not True:
                raise ValueError("DeepSeek requires confirmed agent quiescence before grading")
            if agent.kwargs.get("reasoning_effort", "high") not in {"off", "low", "high", "max"}:
                raise ValueError("Unsupported DeepSeek reasoning effort")
        if not agent.model_name:
            raise ValueError("Each agent requires an explicit model_name")
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
    config = standard_config(json.loads(args.config.read_text()))
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
    }
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
