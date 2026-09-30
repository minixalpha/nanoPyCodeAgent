"""The ``bash`` tool: its definition and its execution.

Each call runs a command with ``bash -c`` in a fresh shell and returns one
result string: stdout, then labelled stderr, then the exit code when non-zero.
"""

import os
from pathlib import Path
import signal
import subprocess

from anthropic.types import ToolParam

# Guardrails for the bash tool: a hung command is killed after this many
# seconds, and results are truncated so one command cannot flood the context.
BASH_TIMEOUT_SECONDS = 120
MAX_TOOL_OUTPUT_CHARS = 20_000

BASH_TOOL: ToolParam = {
    "name": "bash",
    "description": (
        "Run a command with `bash -c` on the user's machine and return its "
        "output: stdout, then stderr (labelled), then the exit code when "
        "non-zero. Each call is a fresh shell in the agent's working "
        "directory, so environment variables and `cd` do not persist between "
        "calls. Long output is truncated and long-running commands are killed "
        "after a timeout."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to run.",
            }
        },
        "required": ["command"],
    },
}


def _stop_command(process: subprocess.Popen) -> None:
    """Stop a timed-out command without draining pipes held by descendants."""
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # GNU timeout and job control can move children to another process
        # group in the command's session. On Linux, stop those children too.
        proc = Path("/proc")
        if proc.is_dir():
            for entry in proc.iterdir():
                if not entry.name.isdecimal():
                    continue
                try:
                    fields = (entry / "stat").read_text().rpartition(")")[2].split()
                    if int(fields[3]) == process.pid:
                        os.kill(int(entry.name), signal.SIGKILL)
                except (OSError, ValueError, IndexError):
                    continue
    try:
        process.kill()
    except ProcessLookupError:
        pass
    # A detached descendant can still hold either pipe open. Closing our
    # readers makes teardown independent of that descendant's lifetime.
    for pipe in (process.stdout, process.stderr):
        if pipe is not None:
            pipe.close()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def run_bash(command: str, *, timeout_seconds: float | None = None) -> tuple[str, bool]:
    """Run ``command`` with ``bash -c`` and return ``(output, is_error)``.

    ``is_error`` is true only when the tool itself failed — here, a timeout.
    A command that ran to completion is a successful tool call whatever its
    exit code: the code is reported in the output text, where the model can
    tell a negative answer (``grep`` finding nothing) from a failure.
    Non-UTF-8 output bytes are replaced rather than raising, and stdin is
    ``/dev/null`` so a command that prompts sees EOF instead of eating the
    user's keystrokes.

    Background children inherit output pipes unless redirected. On POSIX,
    timeouts and interruptions kill the command's process group (and other
    members of its session on Linux). A normally completed command leaves
    background services available to later tools.
    Text mode translates ``\\r`` to ``\\n`` (universal newlines).
    """
    timeout = BASH_TIMEOUT_SECONDS if timeout_seconds is None else min(
        BASH_TIMEOUT_SECONDS, timeout_seconds
    )
    if timeout <= 0:
        return "[command not started: time budget exhausted]", True
    process = subprocess.Popen(
            ["bash", "-c", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
            start_new_session=os.name == "posix",
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as exc:
        _stop_command(process)
        if isinstance(exc, subprocess.TimeoutExpired):
            return f"[command timed out after {timeout:g} seconds]", True
        raise
    finally:
        for pipe in (process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()

    parts = []
    if stdout := stdout.rstrip("\n"):
        parts.append(stdout)
    if stderr := stderr.rstrip("\n"):
        parts.append("[stderr]\n" + stderr)
    if process.returncode != 0:
        parts.append(f"[exit code: {process.returncode}]")
    output = "\n".join(parts) or "(no output)"
    if len(output) > MAX_TOOL_OUTPUT_CHARS:
        output = output[:MAX_TOOL_OUTPUT_CHARS] + "\n[... output truncated ...]"
    return output, False
