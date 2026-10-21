"""Verify an unchanged solution in a stopped, retained Docker trial."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

from harbor.models.task.config import TaskOS
from harbor.models.task.task import Task
from harbor.utils.scripts import build_execution_command

from .verifier import _RUNNER


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def docker(*args):
    return subprocess.check_output(["docker", *map(str, args)], text=True)


def check_container_files(container, expected):
    script = (
        "import hashlib,json,sys; from pathlib import Path; "
        "expected=json.loads(sys.argv[1]); "
        "actual={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in expected}; "
        "assert actual==expected, 'Retained task files differ from frozen evidence'"
    )
    docker("exec", "--user", "root", container, "python3", "-c", script,
           json.dumps(expected))


def wait_for_services(services, timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        states = [m["State"] for m in json.loads(docker("inspect", *services))]
        if any(not s["Running"] or s.get("Health", {}).get("Status") == "unhealthy"
               for s in states):
            raise RuntimeError("A retained project service failed to start")
        if all(s.get("Health", {}).get("Status", "healthy") == "healthy" for s in states):
            return
        if time.monotonic() >= deadline:
            raise TimeoutError("Retained project health checks did not become ready")
        time.sleep(0.2)


def batch_result(output, record):
    result = {"status": "verifier_error", "rewards": None,
              "last_attempt": record}
    if record["status"] != "completed":
        result["error"] = record["status"]
        return result
    try:
        logs = output / "verifier"
        if (logs / "reward.txt").exists():
            rewards = {"reward": float((logs / "reward.txt").read_text())}
        else:
            rewards = json.loads((logs / "reward.json").read_text())
        if not isinstance(rewards, dict) or not rewards or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in rewards.values()
        ):
            raise ValueError("Rewards must be a nonempty mapping of finite numbers")
    except (OSError, ValueError, TypeError) as exc:
        result["error"] = type(exc).__name__
        return result
    return result | {"status": "scored", "rewards": rewards}


def verify_retained(args):
    """Run no agent, preserve native evidence, and stop on any completed score."""
    trial, task_dir, output = (p.resolve() for p in
                               (args.trial_dir, args.task_dir, args.output_dir))
    if trial == output or trial in output.parents or output in trial.parents:
        raise ValueError("Use an output directory outside the original trial")
    if not 1 <= args.max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3 per authorized batch")
    task = Task(task_dir)
    if task.config.environment.os != TaskOS.LINUX:
        raise ValueError("Retained verification supports Linux tasks")
    timeout = task.config.verifier.timeout_sec
    if not 0 < timeout < float("inf"):
        raise ValueError("A finite, positive native verifier timeout is required")
    info, = json.loads(docker("inspect", args.container))
    if info["State"]["Running"]:
        raise ValueError("Stop the retained trial before verifying it")
    mounts = {m["Destination"]: m["Source"] for m in info["Mounts"]}
    if Path(mounts.get("/logs/verifier", "")).resolve() != trial / "verifier":
        raise ValueError("Container verifier mount does not match the original trial")
    project = info["Config"]["Labels"]["com.docker.compose.project"]
    services = docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={project}").split()
    members = json.loads(docker("inspect", *services))
    if any(m["State"]["Running"] for m in members):
        raise ValueError("All retained project services must be stopped")
    expected = {"/app/" + p: digest for p, digest in hashes(trial / "artifacts/app").items()}
    if not expected:
        raise ValueError("Retained verification requires frozen /app artifacts")
    expected.update({"/tests/" + p: digest for p, digest in hashes(task_dir / "tests").items()})
    original = hashes(trial)
    output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).parent
    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "kind": "separate retained-solution verifier batch", "model_calls": 0,
        "trial_dir": str(trial), "task_dir": str(task_dir),
        "task_toml_sha256": hashlib.sha256((task_dir / "task.toml").read_bytes()).hexdigest(),
        "container_id": info["Id"], "image_id": info["Image"],
        "project_services": services, "native_timeout_seconds": timeout,
        "max_attempts": args.max_attempts,
        "retry_dependency_errors": args.retry_dependency_errors,
        "retry_collection_errors": args.retry_collection_errors,
        "original_trial_sha256": original, "expected_container_sha256": expected,
        "source_sha256": {name: hashlib.sha256((source / name).read_bytes()).hexdigest()
                          for name in ("retained.py", "_verifier_runner.py")},
    }
    archive = f"/tmp/nanopy-retained-{uuid.uuid4().hex}"
    control = archive + ".pid"
    manifest["container_batch_archive"] = archive
    (output / "source").mkdir()
    for name in manifest["source_sha256"]:
        (output / "source" / name).write_bytes((source / name).read_bytes())
    (output / "registration.json").write_text(json.dumps(manifest, indent=2) + "\n")
    command = build_execution_command(
        "/tests/" + task.paths.test_path.relative_to(task.paths.tests_dir).as_posix(),
        stdout_path="/logs/verifier/test-stdout.txt", task_os=TaskOS.LINUX,
    )
    started = []
    try:
        for container in [info["Id"], *[s for s in services if s != info["Id"]]]:
            # docker ps returns short IDs; compare against inspected IDs.
            if any(previous.startswith(container) for previous in started):
                continue
            docker("start", container)
            started.append(container)
        wait_for_services(services)
        check_container_files(info["Id"], expected)
        with (output / "runner-stdout.txt").open("w") as stdout, (output / "runner-stderr.txt").open("w") as stderr:
            process = subprocess.Popen([
                "docker", "exec", "--user", "root", info["Id"], "python3", "-c", _RUNNER,
                "batch", archive, command, str(timeout), str(args.max_attempts),
                str(int(args.retry_dependency_errors)), str(int(args.retry_collection_errors)),
                "/logs/verifier", control,
            ], stdout=stdout, stderr=stderr)
            try:
                code = process.wait(timeout=timeout * args.max_attempts + 120)
            except BaseException:
                docker("exec", "--user", "root", info["Id"], "python3", "-c", _RUNNER, "cancel", control)
                process.wait(timeout=30)
                raise
        docker("cp", info["Id"] + ":" + archive + "/verifier", output / "verifier")
        if code:
            raise RuntimeError(f"Verifier runner exited {code}; see {output}")
        check_container_files(info["Id"], expected)
        if hashes(trial) != original:
            raise RuntimeError("Original trial evidence was not restored byte for byte")
        (output / "integrity.json").write_text(json.dumps({
            "original_trial_unchanged": True, "frozen_solution_unchanged": True,
            "original_tests_unchanged": True,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }, indent=2) + "\n")
    finally:
        try:
            for container in reversed(started):
                docker("stop", "--time", "10", container)
        finally:
            (output / "completion.json").write_text(json.dumps({
                "status": "finished", "finished_at": datetime.now(timezone.utc).isoformat(),
            }, indent=2) + "\n")
    record = json.loads((output / "runner-stdout.txt").read_text())
    result = batch_result(output, record)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"output_dir": str(output), **result}), flush=True)
    return int(result["status"] != "scored")
