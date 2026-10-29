"""A timed-out agent must stop before any verifier can observe its output."""

import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from harbor_adapter import _agent_runner as runner
from harbor_adapter.verifier import AgentQuiescenceError, RetryingVerifier, check_agent_quiescence


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError("Timed out waiting for the supervision fixture")


def alive(pid):
    entry = runner.processes().get(pid)
    return entry is not None and entry[2] != "Z"


def start(tmp_path, command):
    control, record = tmp_path / "control.json", tmp_path / "supervision.json"
    child = subprocess.Popen(
        [sys.executable, runner.__file__, "run", str(control), str(record), command],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return child, control, record


def command_with_detached_writer(tmp_path, *, exit_code=None):
    pidfile, counter = tmp_path / "writer.pid", tmp_path / "counter"
    writer = (
        f"import os,time; from pathlib import Path; Path({str(pidfile)!r}).write_text(str(os.getpid()))\n"
        f"with open({str(counter)!r},'a',buffering=1) as stream:\n"
        " while True: stream.write('x'); stream.flush(); time.sleep(.01)\n"
    )
    launcher = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{writer!r}],start_new_session=True, "
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
    )
    if exit_code is None:
        launcher += "time.sleep(60)"
    else:
        launcher += "time.sleep(.15); sys.exit(" + str(exit_code) + ")"
    return shlex.join([sys.executable, "-c", launcher]), pidfile, counter


def cleanup(child, pidfile):
    if child.poll() is None:
        child.kill()
        child.wait(timeout=5)
    if pidfile.exists():
        pid = int(pidfile.read_text())
        if alive(pid):
            os.kill(pid, signal.SIGKILL)


def test_cancellation_stops_detached_tools_and_freezes_output(tmp_path):
    command, pidfile, counter = command_with_detached_writer(tmp_path)
    child, control, record = start(tmp_path, command)
    try:
        wait_for(lambda: pidfile.exists() and counter.exists() and counter.stat().st_size > 2)
        subprocess.run([sys.executable, runner.__file__, "cancel", str(control), str(record)], check=True, timeout=12)
        assert child.wait(timeout=5) == 130
        assert not alive(int(pidfile.read_text()))
        value = counter.read_bytes()
        time.sleep(.1)
        assert counter.read_bytes() == value
        state = json.loads(record.read_text())
        assert state["status"] == "cancelled" and state["processes_stopped"] is True
    finally:
        cleanup(child, pidfile)


def test_cancellation_before_launch_prevents_agent_work(tmp_path):
    control, record, output = tmp_path / "control.json", tmp_path / "supervision.json", tmp_path / "output"
    runner.cancel(control, record)
    command = shlex.join([sys.executable, "-c", f"from pathlib import Path; Path({str(output)!r}).touch()"])
    child, _, _ = start(tmp_path, command)
    assert child.wait(timeout=5) == 130
    assert not output.exists()
    assert json.loads(record.read_text())["before_start"] is True


def test_successful_agent_keeps_intentional_background_service(tmp_path):
    command, pidfile, _ = command_with_detached_writer(tmp_path, exit_code=0)
    child, _, record = start(tmp_path, command)
    try:
        assert child.wait(timeout=5) == 0
        assert alive(int(pidfile.read_text()))
        assert json.loads(record.read_text()) == {"status": "completed", "return_code": 0}
    finally:
        cleanup(child, pidfile)


def test_nonzero_agent_stops_detached_tool_and_preserves_exit_code(tmp_path):
    command, pidfile, _ = command_with_detached_writer(tmp_path, exit_code=7)
    child, _, record = start(tmp_path, command)
    try:
        assert child.wait(timeout=5) == 7
        assert not alive(int(pidfile.read_text()))
        assert json.loads(record.read_text())["return_code"] == 7
    finally:
        cleanup(child, pidfile)


@pytest.mark.parametrize("state", [None, {"status": "running"}, {"status": "cleanup_failed"},
                                  {"status": "cancelled", "processes_stopped": False}, {"status": "completed"}])
def test_verifier_refuses_an_unconfirmed_agent_boundary(tmp_path, state):
    (tmp_path / "process-supervision-required").touch()
    if state is not None:
        (tmp_path / "process-supervision.json").write_text(json.dumps(state))
    with pytest.raises(AgentQuiescenceError):
        check_agent_quiescence(tmp_path)


@pytest.mark.parametrize("state", [{"status": "completed", "return_code": 0},
                                  {"status": "cancelled", "processes_stopped": True}])
def test_verifier_accepts_a_confirmed_agent_boundary(tmp_path, state):
    (tmp_path / "process-supervision-required").touch()
    (tmp_path / "process-supervision.json").write_text(json.dumps(state))
    check_agent_quiescence(tmp_path)


def test_registered_guard_cannot_be_disabled_by_a_missing_marker(tmp_path):
    with pytest.raises(AgentQuiescenceError):
        check_agent_quiescence(tmp_path, required=True)


def test_verifier_checks_the_boundary_before_accessing_task_assertions(tmp_path):
    import asyncio
    verifier = object.__new__(RetryingVerifier)
    verifier.trial_paths = SimpleNamespace(agent_dir=tmp_path)
    verifier._require_agent_quiescence = True
    with pytest.raises(AgentQuiescenceError):
        asyncio.run(verifier.verify())
