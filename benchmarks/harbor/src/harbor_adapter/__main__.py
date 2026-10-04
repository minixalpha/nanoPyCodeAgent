"""Repository benchmark entry point with recorded source and bootstrap policy."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

from harbor.models.job.config import JobConfig

from .bootstrap import AptCache, default_cache_dir


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
    if config.verifier.disable or config.source_jobs:
        raise ValueError("The standard workflow runs fresh trials with verification enabled")
    if not config.tasks and not config.datasets:
        raise ValueError("Select at least one task or dataset")
    if not config.agents or config.n_attempts < 1:
        raise ValueError("Select at least one agent and one trial attempt")
    for agent in config.agents:
        identifiers = [value for value in (agent.import_path, agent.name) if value]
        if not identifiers or any(
            value != "harbor_adapter:NanoPyCodeAgent" for value in identifiers
        ):
            raise ValueError("The standard workflow requires harbor_adapter:NanoPyCodeAgent")
        if agent.env or set(agent.kwargs) - {
            "max_turns", "max_tokens", "time_budget_seconds",
        }:
            raise ValueError(
                "Pass model credentials through the environment; "
                "agent kwargs may only set budgets"
            )
        if not agent.model_name:
            raise ValueError("Each agent requires an explicit model_name")
    return config


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
    shutil.copytree(root / "src/nanopycodeagent", source / "nanopycodeagent", ignore=shutil.ignore_patterns("__pycache__"))
    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(record / "dist")], check=True)
    wheel, = (record / "dist").glob("*.whl")
    with ZipFile(wheel) as archive:
        for path in (source / "nanopycodeagent").rglob("*.py"):
            if archive.read(path.relative_to(source).as_posix()) != path.read_bytes():
                raise ValueError("Source changed during preparation; prepare a new job")
    cache = args.cache_dir.expanduser().resolve()
    for agent in config.agents:
        agent.kwargs.update(wheel_path=str(wheel), bootstrap_cache=str(cache))
    config_path = record / "config.json"
    config_path.write_text(config.model_dump_json(indent=2) + "\n")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
        "source_kind": "working tree including uncommitted files",
        "source_sha256": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob("*.py"))},
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "cache_dir": str(cache),
    }
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
    args = parser.parse_args()
    if args.command == "import-apt":
        count = AptCache(args.cache_dir.expanduser().resolve()).import_manifest(args.manifest)
        print(f"Imported {count} verified APT packages into {args.cache_dir}")
        return 0
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
