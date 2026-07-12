"""The ``bash`` tool: its definition and its execution.

Each call runs a command with ``bash -c`` in a fresh shell and returns one
result string: stdout, then labelled stderr, then the exit code when non-zero.
"""

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


def run_bash(command: str) -> tuple[str, bool]:
    """Run ``command`` with ``bash -c`` and return ``(output, is_error)``.

    ``is_error`` is true only when the tool itself failed — here, a timeout.
    A command that ran to completion is a successful tool call whatever its
    exit code: the code is reported in the output text, where the model can
    tell a negative answer (``grep`` finding nothing) from a failure.
    Non-UTF-8 output bytes are replaced rather than raising, and stdin is
    ``/dev/null`` so a command that prompts sees EOF instead of eating the
    user's keystrokes.

    Known trades for simplicity: a background child inherits the output
    pipes, so ``some_server &`` blocks until the timeout; the timeout kills
    bash itself, not necessarily everything it forked; and text mode
    translates ``\\r`` in output to ``\\n`` (universal newlines).
    """
    try:
        process = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=BASH_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"[command timed out after {BASH_TIMEOUT_SECONDS} seconds]", True

    parts = []
    if stdout := process.stdout.rstrip("\n"):
        parts.append(stdout)
    if stderr := process.stderr.rstrip("\n"):
        parts.append("[stderr]\n" + stderr)
    if process.returncode != 0:
        parts.append(f"[exit code: {process.returncode}]")
    output = "\n".join(parts) or "(no output)"
    if len(output) > MAX_TOOL_OUTPUT_CHARS:
        output = output[:MAX_TOOL_OUTPUT_CHARS] + "\n[... output truncated ...]"
    return output, False
