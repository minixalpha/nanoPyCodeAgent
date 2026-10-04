"""Run a Linux verifier inside its container with bounded timeout retries.

This file is sent to the container as Python source and uses only the standard
library. It never starts an agent or changes the task's test script.
"""

import json
import os
from pathlib import Path
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


def run(command, timeout_sec, max_attempts, logs, control):
    """Return execution status; only our own elapsed deadline is retryable."""
    logs = Path(logs)
    control = Path(control)
    cancelled = control.with_suffix(".cancelled")
    attempts = []
    summary = {"timeout_sec": timeout_sec, "max_attempts": max_attempts,
               "attempts": attempts}

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


if __name__ == "__main__":
    if sys.argv[1] == "cancel":
        cancel(sys.argv[2])
    else:
        command, timeout, count, logs, control = sys.argv[1:]
        print(json.dumps(run(command, float(timeout), int(count), logs, control)))
