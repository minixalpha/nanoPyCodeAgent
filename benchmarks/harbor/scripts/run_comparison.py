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
import shutil
import subprocess


class BatchImages:
    """Restore pinned images per batch and evict only this run's new cache."""

    def __init__(self, root, plan, record):
        self.policy = plan.get("batch_images")
        self.record = record
        if not self.policy:
            return
        evidence = json.loads((root / self.policy["manifest"]).read_text())
        self.images = {item["task"]: item for item in evidence["images"]}
        inventory = record / "initial-docker-images.json"
        if not inventory.exists():
            ids = subprocess.check_output(["docker", "image", "ls", "--quiet", "--no-trunc"], text=True).splitlines()
            inventory.write_text(json.dumps(sorted(set(ids)), indent=2) + "\n")
        self.protected = set(json.loads(inventory.read_text()))
        self.root = root

    def inspect(self, image):
        result = subprocess.run(["docker", "image", "inspect", image], text=True, capture_output=True)
        if result.returncode:
            if "No such image" in result.stderr or "No such object" in result.stderr:
                return None
            raise RuntimeError(f"Cannot inspect Docker image: {result.stderr}")
        return json.loads(result.stdout)[0]

    def entries(self, jobs):
        result = {}
        for job in jobs:
            config = json.loads((self.root / job["config"]).read_text())
            for task in config["tasks"]:
                entry = self.images[task["name"]]
                result[entry["image"]] = entry
        return list(result.values())

    def event(self, action, entry):
        with (self.record / "image-cache.jsonl").open("a") as stream:
            stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "action": action, "image": entry["image"], "image_id": entry["image_id"]}) + "\n")

    def prepare(self, jobs):
        if not self.policy:
            return
        free = shutil.disk_usage(self.policy["storage_path"]).free
        if free < self.policy["minimum_free_disk_bytes"]:
            raise RuntimeError("Insufficient Docker storage before image restoration")
        for entry in self.entries(jobs):
            installed = self.inspect(entry["image"])
            if installed is None:
                reference = entry["repo_digests"][0]
                with (self.record / "image-downloads.log").open("a") as log:
                    subprocess.run(["docker", "pull", reference], check=True, stdout=log, stderr=subprocess.STDOUT)
                    subprocess.run(["docker", "tag", reference, entry["image"]], check=True, stdout=log, stderr=subprocess.STDOUT)
                installed = self.inspect(entry["image"])
                self.event("restored", entry)
            if (installed["Id"] != entry["image_id"]
                    or not set(entry["repo_digests"]) <= set(installed["RepoDigests"])):
                raise ValueError(f"Docker image differs from registration: {entry['image']}")
            self.event("verified", entry)

    def release(self, jobs):
        if not self.policy:
            return
        for entry in self.entries(jobs):
            if entry["image_id"] in self.protected:
                continue
            installed = self.inspect(entry["image"])
            if installed is None:
                continue
            if installed["Id"] != entry["image_id"]:
                raise ValueError("Refusing to evict a different image")
            # No force: Docker preserves images referenced by any remaining
            # container. Keep both successful and failed task files/logs.
            with (self.record / "image-downloads.log").open("a") as log:
                for reference in [entry["image"], *entry["repo_digests"]]:
                    if self.inspect(reference) is None:
                        continue
                    subprocess.run(["docker", "image", "rm", reference], check=True, stdout=log, stderr=subprocess.STDOUT)
            self.event("evicted", entry)


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
    for name, expected in plan.get("additional_file_sha256", {}).items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError(f"Registered infrastructure file changed: {name}")
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
        if arm.get("agent") == "pi":
            from harbor_adapter.pi import distribution_digest, distribution_files
            if distribution_digest(distribution_files(Path(arm["distribution_path"]))) != arm["distribution_sha256"]:
                raise ValueError("Registered Pi distribution changed")
        else:
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
    minimum = plan.get("minimum_free_disk_bytes", 0)
    if shutil.disk_usage(root).free < minimum:
        raise RuntimeError(f"Insufficient free disk space: this plan requires {minimum} bytes")
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


def preflight_passed(states, expected_counts):
    return bool(states) and len(states) == len(expected_counts) and all(
        s.get("exit_code") == 0
        and s.get("summary", {}).get("trials")
        and len(s["summary"]["trials"]) == expected
        and all(t["status"] == "setup_passed" for t in s["summary"]["trials"])
        for s, expected in zip(states, expected_counts)
    )


def accepted_preflights_passed(root, plan):
    """Validate previously completed installation trials without replaying jobs.

    A failed sibling trial does not invalidate a successful installation. Every
    task/arm pair still needs native, hash-bound evidence from the frozen source.
    This mode cannot be combined with new preflight jobs in the same plan.
    """
    if plan["preflight"]:
        raise ValueError("Accepted installation evidence cannot mix with new preflight jobs")
    expected = {(j["arm"], j["task"]) for j in plan["queue"]}
    evidence = plan["accepted_preflight_trials"]
    pairs = [(e["arm"], e["task"]) for e in evidence]
    if not expected or set(pairs) != expected or len(pairs) != len(expected):
        raise ValueError("Every queued task/arm pair needs exactly one accepted preflight")
    tasks = {t["name"]: t for t in plan["tasks"]}

    def checked(path, expected_hash):
        if digest(path) != expected_hash:
            raise ValueError(f"Accepted preflight evidence changed: {path}")
        return json.loads(path.read_text())

    for item in evidence:
        arm = plan["arms"][item["arm"]]
        source = root / arm["source_root"]
        result_path = (root / item["result_path"]).resolve()
        if not result_path.is_relative_to((source / "jobs").resolve()) or result_path.name != "result.json":
            raise ValueError("Accepted trial must belong to the frozen source checkout")
        result = checked(result_path, item["result_sha256"])
        task = tasks[item["task"]]
        task_id = result["task_id"]
        if result["task_name"] != item["task"] or task_id["ref"] != task["ref"]:
            raise ValueError("Accepted preflight has a different task revision")
        if (not result.get("finished_at") or result.get("exception_info")
                or result.get("agent_execution") is not None
                or result.get("verifier") is not None
                or result.get("verifier_result") is not None):
            raise ValueError("Accepted evidence must be a successful installation-only trial")
        bootstrap = checked(result_path.parent / "agent/bootstrap.json", item["bootstrap_sha256"])
        if (bootstrap.get("status") != "ready" or bootstrap.get("stage") != "complete"
                or bootstrap.get("verifier_preflight", {}).get("status") not in {"passed", "not_configured"}):
            raise ValueError("Accepted installation did not finish its required preflight")
        job_dir = result_path.parent.parent
        inputs = job_dir.with_name(job_dir.name + "-input")
        manifest = checked(inputs / "manifest.json", item["manifest_sha256"])
        config = checked(inputs / "config.json", item["input_config_sha256"])
        if config.get("install_only") is not True or manifest["commit"] != arm["source_ref"]:
            raise ValueError("Accepted installation used a different mode or source revision")
        expected_sources = {}
        packages = [("benchmarks/harbor/src", "harbor_adapter")]
        if arm.get("agent") != "pi":
            packages.append(("src", "nanopycodeagent"))
        for prefix, package in packages:
            for path in (source / prefix / package).rglob("*.py"):
                expected_sources[str(path.relative_to(source / prefix))] = digest(path)
        if not expected_sources or manifest["source_sha256"] != expected_sources:
            raise ValueError("Accepted installation source snapshot differs from the frozen source")
        if arm.get("agent") == "pi":
            pin = arm["distribution_sha256"]
            pi_input, = manifest["pi_inputs"]
            if not (pi_input["distribution_sha256"] == bootstrap["distribution_sha256"] == pin):
                raise ValueError("Accepted Pi distribution differs from its provenance")
            from harbor_adapter.pi import distribution_digest
            if distribution_digest(pi_input["files"]) != pin:
                raise ValueError("Accepted Pi file manifest differs from its provenance")
            if digest(inputs / "pi-models.json") != pi_input["model_config_sha256"]:
                raise ValueError("Accepted Pi model config differs from its provenance")
        else:
            wheel = Path(result["config"]["agent"]["kwargs"]["wheel_path"]).resolve()
            if not wheel.is_relative_to((inputs / "dist").resolve()):
                raise ValueError("Accepted installation wheel must belong to its recorded inputs")
            if not (digest(wheel) == manifest["wheel_sha256"] == bootstrap["wheel_sha256"]):
                raise ValueError("Accepted installation wheel digest differs from its provenance")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--phase", choices=["preflight", "model", "all"], required=True)
    args = parser.parse_args()
    root, plan_path = Path.cwd(), args.plan.resolve()
    plan = json.loads(plan_path.read_text())
    validate_plan(root, plan_path, plan)
    accepted = (
        accepted_preflights_passed(root, plan)
        if "accepted_preflight_trials" in plan else False
    )
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
    images = BatchImages(root, plan, record)
    expected_counts = [
        len(json.loads((root / job["config"]).read_text())["tasks"])
        for job in plan["preflight"]
    ]
    if args.phase in {"preflight", "all"}:
        states = []
        for job in plan["preflight"]:
            images.prepare([job])
            states.append(run_job(root, plan, job, record, True))
            images.release([job])
        if not accepted and not preflight_passed(states, expected_counts):
            return 1
        if args.phase == "preflight":
            return 0
    if not accepted:
        preflight = [json.loads((record / (j["job_name"] + ".json")).read_text()) for j in plan["preflight"]]
        if not preflight_passed(preflight, expected_counts):
            raise RuntimeError("Install-only checks must finish successfully before model work")
    states = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for offset in range(0, len(plan["queue"]), 2):
            batch = plan["queue"][offset:offset + 2]
            images.prepare(batch)
            futures = [pool.submit(run_job, root, plan, job, record, False) for job in batch]
            states.extend(f.result() for f in futures)
            images.release(batch)
    return int(any(s["exit_code"] != 0 for s in states))


if __name__ == "__main__":
    raise SystemExit(main())
