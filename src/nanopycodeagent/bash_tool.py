"""The ``bash`` tool: its definition and its execution.

Each call runs a command with ``bash -c`` in a fresh shell. Output is captured
to temp files, bounded, and combined into one result string for the model.
"""

import os
import signal
import subprocess
import tempfile

from anthropic.types import ToolParam

# Guardrails for the bash tool: a hung command is killed after this many
# seconds, and results are truncated so one command cannot flood the context.
BASH_TIMEOUT_SECONDS = 120
MAX_TOOL_OUTPUT_BYTES = 20_000

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


def _read_stream(stream_file) -> str:
    """Read one captured stream from its temp file, bounded and decoded.

    At most ``MAX_TOOL_OUTPUT_BYTES`` bytes are read, so a command that wrote
    gigabytes stays on disk instead of being materialized in the agent's
    memory before truncation (a UTF-8 character is at least one byte, so the
    byte cap also bounds the decoded text). Each stream is bounded on
    its own, before the sections are joined — bounding the joined result
    instead would let a chatty stdout push the ``[stderr]`` section and the
    exit-code marker out of the message entirely, hiding the one part that
    explains a failure.
    """
    size = stream_file.seek(0, os.SEEK_END)
    stream_file.seek(0)
    data = stream_file.read(MAX_TOOL_OUTPUT_BYTES)
    text = data.decode("utf-8", errors="replace").rstrip("\n")
    if size > MAX_TOOL_OUTPUT_BYTES:
        text += "\n[... output truncated ...]"
    return text


def _kill_process_tree(process: subprocess.Popen) -> None:
    """Kill the bash child and every process in its group, then reap it.

    ``process`` must have been started with ``start_new_session=True`` so its
    pid doubles as the process-group id.
    """
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:  # the whole group already exited
        pass
    process.wait()


def run_bash(command: str) -> tuple[str, bool]:
    """Run ``command`` with ``bash -c`` and return ``(output, is_error)``.

    The output combines stdout, labelled stderr, and the exit code when
    non-zero, truncated to ``MAX_TOOL_OUTPUT_BYTES``. ``is_error`` is true
    only when the tool itself failed — bash could not be started or the
    command timed out. A command that ran to completion is a successful tool
    call whatever its exit code: the code is reported in the output text,
    where the model can tell a negative answer (``grep`` finding nothing)
    from a failure. Non-UTF-8 output bytes are replaced rather than raising.

    Output is captured into temp files, not pipes: a pipe only reaches EOF
    once every inherited copy is closed, so a background child (e.g.
    ``some_server &``) would stall a pipe read until the timeout even though
    bash itself exited immediately. Files let us wait on bash alone.
    """
    try:
        with (
            tempfile.TemporaryFile() as stdout_file,
            tempfile.TemporaryFile() as stderr_file,
        ):
            # stdin is closed off: the child must not share the terminal with
            # the agent, or a command that prompts (or falls back to reading
            # stdin) blocks until the timeout while eating the user's keys.
            # start_new_session puts bash and its descendants in their own
            # process group, so a timeout can kill the work the command
            # actually forked (builds, servers), not just the bash wrapper.
            process = subprocess.Popen(
                ["bash", "-c", command],
                stdin=subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True,
            )
            timed_out = False
            try:
                returncode = process.wait(timeout=BASH_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                # The tree is killed, but everything it wrote until now is in
                # the temp files — forward it, so a slow build or test run
                # shows how far it got instead of a bare timeout notice.
                _kill_process_tree(process)
                returncode = None
                timed_out = True
            except BaseException:  # e.g. Ctrl-C mid-command: never leak the tree
                _kill_process_tree(process)
                raise
            stdout = _read_stream(stdout_file)
            stderr = _read_stream(stderr_file)
    except (OSError, ValueError) as exc:
        # OSError: bash itself could not be started (e.g. missing). ValueError:
        # Popen rejects arguments the OS cannot represent (e.g. an embedded NUL
        # byte in the command — legal JSON the model can emit). Either way,
        # report a tool error the model can recover from instead of crashing.
        return f"Could not run bash: {exc}", True

    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append("[stderr]\n" + stderr)
    if timed_out:
        parts.append(f"[command timed out after {BASH_TIMEOUT_SECONDS} seconds]")
    elif returncode != 0:
        parts.append(f"[exit code: {returncode}]")
    output = "\n".join(parts) or "(no output)"
    return output, timed_out
