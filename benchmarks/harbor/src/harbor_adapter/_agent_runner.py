"""Supervise one Linux agent command, including detached tool subprocesses."""

import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def processes():
    result = {}
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
            result[int(path.name)] = (int(fields[1]), int(fields[19]), fields[0])
        except (OSError, ValueError, IndexError):
            continue
    return result


def descendants(root, table):
    owned = {root}
    while True:
        updated = owned | {pid for pid, (parent, _, _) in table.items() if parent in owned}
        if updated == owned:
            return {pid: table[pid][1] for pid in owned - {root} if pid in table}
        owned = updated


def signal_same_process(pid, started, number):
    entry = processes().get(pid)
    if entry is not None and entry[1] == started and entry[2] != "Z":
        try:
            os.kill(pid, number)
        except ProcessLookupError:
            pass


def stop_descendants():
    """Freeze parents before killing the forest, including new sessions."""
    owned = {}
    for _ in range(4):
        current = descendants(os.getpid(), processes())
        previous = set(owned)
        owned.update(current)
        for pid, started in current.items():
            signal_same_process(pid, started, signal.SIGSTOP)
        if set(owned) == previous:
            break
    deadline = time.monotonic() + 5
    while True:
        owned.update(descendants(os.getpid(), processes()))
        for pid, started in owned.items():
            signal_same_process(pid, started, signal.SIGKILL)
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                break
            if pid == 0:
                break
        table = processes()
        alive = [pid for pid, started in owned.items()
                 if pid in table and table[pid][1] == started and table[pid][2] != "Z"]
        if not alive and not descendants(os.getpid(), table):
            return len(owned)
        if time.monotonic() >= deadline:
            raise RuntimeError("Agent subprocesses did not stop")
        time.sleep(.02)


def write_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value) + "\n")
    temporary.replace(path)


def run(control, record, command):
    control, record = Path(control), Path(record)
    cancelled = control.with_suffix(".cancelled")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), "Cannot supervise orphaned agent tools")
    stopping = False

    def interrupted(signum, frame):
        if not stopping:
            raise InterruptedError("Agent execution cancelled")

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    write_json(control, {"pid": os.getpid(), "started": processes()[os.getpid()][1]})
    try:
        if cancelled.exists():
            write_json(record, {"status": "cancelled", "processes_stopped": True, "before_start": True})
            return 130
        write_json(record, {"status": "running"})
        child = subprocess.Popen(["bash", "-c", command], stdin=subprocess.DEVNULL, start_new_session=True)
        code = child.wait()
        if code:
            stopping = True
            stop_descendants()
        # Successful solutions may intentionally leave a server running.
        write_json(record, {"status": "completed", "return_code": code})
        return code
    except BaseException as error:
        stopping = True
        try:
            count = stop_descendants()
            write_json(record, {"status": "cancelled" if isinstance(error, InterruptedError) else "error_stopped",
                                "processes_stopped": True, "stopped_processes": count})
        except BaseException:
            write_json(record, {"status": "cleanup_failed", "processes_stopped": False})
            raise
        if isinstance(error, InterruptedError):
            return 130
        raise
    finally:
        control.unlink(missing_ok=True)


def cancel(control, record):
    control, record = Path(control), Path(record)
    control.with_suffix(".cancelled").touch()
    try:
        owner = json.loads(control.read_text())
    except FileNotFoundError:
        return  # A later startup observes the marker before spawning the agent.
    signal_same_process(owner["pid"], owner["started"], signal.SIGTERM)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if record.exists():
            state = json.loads(record.read_text())
            if state.get("status") == "completed" or (
                state.get("status") in {"cancelled", "error_stopped"} and state.get("processes_stopped") is True
            ):
                return
            if state.get("status") == "cleanup_failed":
                raise RuntimeError("Agent subprocess cleanup failed")
        time.sleep(.02)
    raise RuntimeError("Agent supervisor did not confirm cancellation")


if __name__ == "__main__":
    if sys.argv[1] == "cancel":
        cancel(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(run(sys.argv[2], sys.argv[3], sys.argv[4]))
