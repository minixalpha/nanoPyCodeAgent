"""Run a frozen comparison plan through the standard Harbor entry point.

This orchestrates existing repository worktrees; it does not install dependencies,
modify task environments, implement an adapter, or retry a trial.
"""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_from_source(path):
    values = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in {
                "_TOOL_GUIDANCE", "HEADLESS_SYSTEM_PROMPT",
            }:
                values[target.id] = eval(
                    compile(ast.Expression(node.value), str(path), "eval"),
                    {"__builtins__": {}}, values,
                )
    return values["HEADLESS_SYSTEM_PROMPT"]


def validate_plan(root, plan_path, plan):
    jobs = plan["preflight"] + plan["queue"]
    names = [job["job_name"] for job in jobs]
    if len(names) != len(set(names)):
        raise ValueError("Job names must be unique")
    if len(plan["queue"]) != plan["total_model_runs"]:
        raise ValueError("Model run count does not match the registered queue")
    if plan["max_concurrent_trials"] != 2 or plan["whole_trial_retries"] != 0:
        raise ValueError("This runner requires concurrency two and no trial retries")
    for arm in plan["arms"].values():
        source = root / arm["source_root"]
        actual_ref = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True,
        ).strip()
        if actual_ref != arm["source_ref"]:
            raise ValueError(f"Source revision changed: {source}")
        subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "src", "benchmarks/harbor/src"],
            cwd=source, check=True, stdout=subprocess.DEVNULL,
        )
        expected = plan_path.parent / arm["prompt_file"]
        if digest(expected) != arm["prompt_sha256"]:
            raise ValueError(f"Prompt file changed: {expected}")
        if prompt_from_source(source / "src/nanopycodeagent/agent.py") != expected.read_text():
            raise ValueError(f"Source prompt does not match the plan: {source}")
    for task in plan["tasks"]:
        cache = Path.home() / ".cache/harbor/tasks/packages" / task["name"] / task["ref"].split(":")[1]
        for name, expected in task["task_file_sha256"].items():
            if digest(cache / name) != expected:
                raise ValueError(f"Task file changed: {cache / name}")
    for job in jobs:
        config_path = root / job["config"]
        if digest(config_path) != job["config_sha256"]:
            raise ValueError(f"Configuration changed: {config_path}")
        config = json.loads(config_path.read_text())
        limit = 1 if job in plan["queue"] else 2
        if config["n_concurrent_trials"] > limit or config["n_attempts"] != 1:
            raise ValueError("Per-job concurrency or attempts exceed the plan")


def run_job(root, plan, job, record, install_only):
    status_path = record / (job["job_name"] + ".json")
    if status_path.exists():
        previous = json.loads(status_path.read_text())
        if previous["status"] == "finished":
            return previous
        raise RuntimeError(f"Previously started job requires inspection; refusing to retry: {status_path}")
    source = root / plan["arms"][job["arm"]]["source_root"]
    command = [
        "uv", "run", "--project", "benchmarks/harbor", "python", "-m", "harbor_adapter",
        "run", "--config", str(root / job["config"]), "--job-name", job["job_name"],
        "--cache-dir", str(root / ".cache/nanopy-harbor"),
    ]
    if install_only:
        command.append("--install-only")
    summary_path = source / "jobs" / (job["job_name"] + "-input") / "summary.json"
    state = {
        **job, "status": "started", "started_at": datetime.now(timezone.utc).isoformat(),
        "command": command, "cwd": str(source), "summary_path": str(summary_path),
    }
    status_path.write_text(json.dumps(state, indent=2) + "\n")
    with (record / (job["job_name"] + ".log")).open("w") as log:
        code = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT).returncode
    state.update(status="finished", exit_code=code, finished_at=datetime.now(timezone.utc).isoformat())
    if summary_path.exists():
        state["summary"] = json.loads(summary_path.read_text())
    status_path.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps({"job": job["job_name"], "exit_code": code, "status": state["status"]}), flush=True)
    return state


def preflight_passed(states):
    return bool(states) and all(
        s.get("exit_code") == 0
        and s.get("summary", {}).get("trials")
        and all(t["status"] == "setup_passed" for t in s["summary"]["trials"])
        for s in states
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--phase", choices=["preflight", "model"], required=True)
    args = parser.parse_args()
    root, plan_path = Path.cwd(), args.plan.resolve()
    plan = json.loads(plan_path.read_text())
    validate_plan(root, plan_path, plan)
    record = root / plan["log_dir"]
    record.mkdir(parents=True, exist_ok=True)
    record.chmod(0o700)
    registration = record / "registration.json"
    current = {"plan_sha256": digest(plan_path), "plan": plan}
    if registration.exists():
        if json.loads(registration.read_text()) != current:
            raise ValueError("The registered plan is immutable")
    else:
        registration.write_text(json.dumps(current, indent=2) + "\n")
    if args.phase == "preflight":
        states = [run_job(root, plan, j, record, True) for j in plan["preflight"]]
        return 0 if preflight_passed(states) else 1
    preflight = [json.loads((record / (j["job_name"] + ".json")).read_text()) for j in plan["preflight"]]
    if not preflight_passed(preflight):
        raise RuntimeError("Install-only checks must finish successfully before model work")
    states = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for offset in range(0, len(plan["queue"]), 2):
            batch = plan["queue"][offset:offset + 2]
            futures = [pool.submit(run_job, root, plan, job, record, False) for job in batch]
            states.extend(f.result() for f in futures)
    return int(any(s["exit_code"] != 0 for s in states))


if __name__ == "__main__":
    raise SystemExit(main())
