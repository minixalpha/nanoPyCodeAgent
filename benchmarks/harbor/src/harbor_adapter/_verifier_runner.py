"""Run a Linux verifier with bounded, explicitly selected recovery rules.

This file is sent to the container as Python source and uses only the standard
library. It never starts an agent or changes the task's test script.
"""

import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time


def _stop_process(process):
    # GNU timeout and other tools may create additional process groups in the
    # test's session. Snapshot them before killing the session leader.
    members = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[3]) == process.pid:
                members.append(int(entry.name))
        except (OSError, ValueError, IndexError):
            continue
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    for pid in members:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)


def _archive(logs, attempt):
    target = logs / "attempts" / str(attempt)
    target.mkdir(parents=True)
    for source in logs.iterdir():
        if source.name in {"attempts", "retry-summary.json"}:
            continue
        if source.is_dir():
            shutil.copytree(source, target / source.name)
        else:
            shutil.copy2(source, target / source.name)


def dependency_download_failed(logs):
    """Recognize uv network failures before tests, never a completed test score."""
    if (logs / "ctrf.json").exists():
        return False
    for name in ("reward.txt", "reward.json"):
        path = logs / name
        if path.exists():
            try:
                value = (float(path.read_text()) if name.endswith(".txt")
                         else json.loads(path.read_text()).get("reward"))
            except (ValueError, TypeError, AttributeError):
                return False
            if value != 0:
                return False
    path = logs / "test-stdout.txt"
    text = path.read_text(errors="replace") if path.exists() else ""
    if re.search(
        r"test session starts|collected \d+|FAILED |ERROR collecting|"
        r"\b(?:passed|failed|errors?|skipped)\b.*\bin \d", text,
    ):
        return False
    return bool(
        re.search(r"Failed to (?:download|fetch) `[^`]+`", text)
        and re.search(r"network timeout|operation timed out|Request failed after", text)
    )


def collection_failed(logs):
    """Recognize aborted pytest collection without retrying executed test cases."""
    for name in ("reward.txt", "reward.json"):
        path = logs / name
        if path.exists():
            try:
                value = (float(path.read_text()) if name.endswith(".txt")
                         else json.loads(path.read_text()).get("reward"))
            except (ValueError, TypeError, AttributeError):
                return False
            if value != 0:
                return False
    report = logs / "ctrf.json"
    if report.exists():
        try:
            results = json.loads(report.read_text())["results"]
            summary = results["summary"]
            if summary["tests"] != 0 or any(
                summary.get(key, 0) != 0 for key in ("passed", "failed", "skipped")
            ) or results.get("tests"):
                return False
        except (ValueError, KeyError, TypeError, AttributeError):
            return False
    path = logs / "test-stdout.txt"
    text = path.read_text(errors="replace") if path.exists() else ""
    if re.search(r"\b\d+ (?:passed|failed|skipped|xfailed|xpassed)\b", text):
        return False
    return bool(
        re.search(r"\bERROR collecting\b", text)
        and re.search(r"Interrupted: \d+ errors? during collection", text)
    )


def run(command, timeout_sec, max_attempts, logs, control, retry_dependency_errors=False,
        retry_collection_errors=False):
    """Retry deadlines and explicitly authorized pre-assertion failures."""
    logs = Path(logs)
    control = Path(control)
    cancelled = control.with_suffix(".cancelled")
    attempts = []
    summary = {"timeout_sec": timeout_sec, "max_attempts": max_attempts,
               "retry_dependency_errors": retry_dependency_errors,
               "retry_collection_errors": retry_collection_errors, "attempts": attempts}

    def interrupted(signum, frame):
        raise InterruptedError("Verifier execution cancelled")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    control.write_text(str(os.getpid()))
    try:
        for attempt in range(1, max_attempts + 1):
            if cancelled.exists():
                raise InterruptedError("Verifier execution cancelled")
            # A timed-out test may have written a reward before hanging. It
            # must never be mistaken for the next attempt's result.
            for previous in logs.iterdir():
                if previous.name in {"attempts", "retry-summary.json"}:
                    continue
                if previous.is_dir():
                    shutil.rmtree(previous)
                else:
                    previous.unlink()
            started = time.monotonic()
            record = {"attempt": attempt, "status": "error"}
            attempts.append(record)
            process = None
            try:
                process = subprocess.Popen(
                    ["bash", "-c", command], stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                try:
                    record["return_code"] = process.wait(timeout=timeout_sec)
                    record["status"] = "completed"
                    if retry_dependency_errors and dependency_download_failed(logs):
                        record["status"] = "dependency_error"
                    elif retry_collection_errors and collection_failed(logs):
                        record["status"] = "collection_error"
                except subprocess.TimeoutExpired:
                    _stop_process(process)
                    record["status"] = "timeout"
            except BaseException:
                if process is not None:
                    _stop_process(process)
                record["status"] = "cancelled"
                raise
            finally:
                record["duration_seconds"] = time.monotonic() - started
                _archive(logs, attempt)
                # Remove even the last timed-out attempt's reward from the
                # canonical location; the original stays in its archive.
                if record["status"] != "completed":
                    for name in ("reward.txt", "reward.json"):
                        (logs / name).unlink(missing_ok=True)
                (logs / "retry-summary.json").write_text(json.dumps(summary, indent=2))
            if record["status"] == "completed":
                return record
        return attempts[-1]
    finally:
        control.unlink(missing_ok=True)


def cancel(control):
    """Stop this runner, or prevent it starting after a transport cancellation."""
    control = Path(control)
    control.with_suffix(".cancelled").touch()
    try:
        pid = int(control.read_text())
    except FileNotFoundError:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    for _ in range(100):
        if not control.exists():
            return
        time.sleep(0.05)
    raise RuntimeError("Verifier runner did not stop after cancellation")


def run_batch(command, timeout_sec, max_attempts, logs, control, archive,
              retry_dependency_errors=False, retry_collection_errors=False):
    """Keep a new batch separate and restore the previous verifier evidence."""
    logs, archive = Path(logs).resolve(), Path(archive).resolve()
    if logs == archive or logs in archive.parents or archive in logs.parents:
        raise ValueError("Batch archive must be outside the verifier directory")
    archive.mkdir(parents=True, exist_ok=False)
    original, current = archive / "original", archive / "verifier"
    original.mkdir()
    current.mkdir()
    moved = []
    try:
        for path in list(logs.iterdir()):
            shutil.move(str(path), original / path.name)
            moved.append(path.name)
    except BaseException:
        for name in moved:
            shutil.move(str(original / name), logs / name)
        raise
    try:
        return run(command, timeout_sec, max_attempts, logs, control,
                   retry_dependency_errors, retry_collection_errors)
    finally:
        try:
            for path in list(logs.iterdir()):
                shutil.move(str(path), current / path.name)
        finally:
            for name in moved:
                shutil.move(str(original / name), logs / name)


if __name__ == "__main__":
    if sys.argv[1] == "cancel":
        cancel(sys.argv[2])
    else:
        arguments = sys.argv[1:]
        archive = arguments.pop(1) if arguments[0] == "batch" else None
        if archive is not None:
            arguments.pop(0)
        if len(arguments) == 5:
            command, timeout, count, logs, control = arguments
            retry_dependencies = False
            retry_collection = False
        elif len(arguments) == 6:
            command, timeout, count, retry, logs, control = arguments
            retry_dependencies = retry == "1"
            retry_collection = False
        else:
            command, timeout, count, retry, collection, logs, control = arguments
            retry_dependencies = retry == "1"
            retry_collection = collection == "1"
        runner = run if archive is None else lambda *args: run_batch(
            *args[:5], archive, *args[5:])
        print(json.dumps(runner(
            command, float(timeout), int(count), logs, control, retry_dependencies,
            retry_collection,
        )))
