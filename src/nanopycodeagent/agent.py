"""A minimal agent loop built on the Anthropic Python SDK.

Run the program, type a message, and Agent replies. The full conversation is
kept in memory so each turn has context. The model can call a single ``bash``
tool to run shell commands; every command and its output are echoed to the
terminal as they happen. Type ``/exit`` to quit.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import anthropic
import httpx
from anthropic.types import (
    ContentBlock,
    MessageParam,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
)

# The model used when ANTHROPIC_MODEL is set in neither the environment nor the
# config file.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
SYSTEM_PROMPT = (
    "You are nanoPyCodeAgent, a concise and helpful coding assistant. "
    "Use the bash tool to inspect files, run code, and complete tasks that "
    "need real command output instead of guessing."
)

# Guardrails for the bash tool: a hung command is killed after this many
# seconds, and results are truncated so one command cannot flood the context.
BASH_TIMEOUT_SECONDS = 120
MAX_TOOL_OUTPUT_CHARS = 20_000
# One user input may trigger at most this many API requests: a model stuck
# re-running failing commands must eventually hand control back to the prompt
# instead of burning tokens (and bash executions) until Ctrl-C.
MAX_REQUESTS_PER_TURN = 30

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


# User-level config file. Its ``env`` mapping supplies ANTHROPIC_* values for
# keys that are not already set in the environment (environment variables win).
def _default_settings_path() -> Path | None:
    """Resolve the user-level config path, or ``None`` if home is unknown.

    ``Path.home()`` raises ``RuntimeError`` when the home directory cannot be
    determined (e.g. ``$HOME`` unset and no passwd entry, common in minimal
    containers). Guarding it here keeps ``import nanopycodeagent`` — which runs
    eagerly behind the console script — from crashing at import; a ``None`` path
    simply means "no user config file".
    """
    try:
        return Path.home() / ".nanoPyCodeAgent" / "settings.json"
    except RuntimeError:
        return None


SETTINGS_PATH = _default_settings_path()


def load_settings_env(path: Path | None = None) -> None:
    """Apply the ``env`` mapping from the config file into ``os.environ``.

    ``path`` defaults to the module-level ``SETTINGS_PATH`` (resolved at call
    time, so it stays overridable). Only ``ANTHROPIC_*`` keys that are not
    already present are set, so environment variables take precedence over the
    config file and unrelated variables are never injected. Behaviour by case:

    - Missing file, or a home directory that cannot be resolved: silently
      ignored (running without a config file is normal).
    - Unreadable / non-UTF-8 file, malformed JSON, non-object top level, or a
      non-object ``env``: a warning is printed and the file is otherwise
      ignored — a bad config never blocks startup.
    - Empty, whitespace-only, or non-string values, and values the OS rejects
      (e.g. an embedded NUL): skipped (the documented example ships these keys
      as empty-string placeholders).
    """
    if path is None:
        path = SETTINGS_PATH
    if path is None:
        return  # home dir unresolvable → behave as if no config file exists
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Warning: could not read config file {path}: {exc}")
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Warning: ignoring malformed config file {path}: {exc}")
        return

    if not isinstance(data, dict):
        print(f"Warning: ignoring config file {path}: top level must be an object.")
        return

    env = data.get("env", {})
    if not isinstance(env, dict):
        print(f"Warning: ignoring 'env' in config file {path}: it must be an object.")
        return

    for key, value in env.items():
        # Only honor ANTHROPIC_* keys (the config's documented purpose) so a
        # shared settings.json cannot silently inject unrelated variables such
        # as HTTPS_PROXY into the process environment.
        if not key.startswith("ANTHROPIC_"):
            continue
        if not (isinstance(value, str) and value.strip()):
            continue
        try:
            os.environ.setdefault(key, value.strip())
        except ValueError as exc:
            # e.g. an embedded NUL in the value or '=' in the key name.
            print(f"Warning: ignoring invalid config entry {key!r}: {exc}")


def _read_stream(stream_file) -> str:
    """Read one captured stream from its temp file, bounded and decoded.

    At most ``MAX_TOOL_OUTPUT_CHARS`` bytes are read, so a command that wrote
    gigabytes stays on disk instead of being materialized in the agent's
    memory before truncation (the byte cap can only undershoot the character
    cap: a UTF-8 character is at least one byte). Each stream is bounded on
    its own, before the sections are joined — bounding the joined result
    instead would let a chatty stdout push the ``[stderr]`` section and the
    exit-code marker out of the message entirely, hiding the one part that
    explains a failure.
    """
    size = stream_file.seek(0, os.SEEK_END)
    stream_file.seek(0)
    data = stream_file.read(MAX_TOOL_OUTPUT_CHARS)
    text = data.decode("utf-8", errors="replace").rstrip("\n")
    if size > MAX_TOOL_OUTPUT_CHARS:
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
    non-zero, truncated to ``MAX_TOOL_OUTPUT_CHARS``. ``is_error`` is true when
    bash could not be started, the command timed out, or it exited non-zero.
    Non-UTF-8 output bytes are replaced rather than raising.

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
            try:
                returncode = process.wait(timeout=BASH_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                _kill_process_tree(process)
                return f"Command timed out after {BASH_TIMEOUT_SECONDS} seconds.", True
            except BaseException:  # e.g. Ctrl-C mid-command: never leak the tree
                _kill_process_tree(process)
                raise
            stdout = _read_stream(stdout_file)
            stderr = _read_stream(stderr_file)
    except OSError as exc:  # e.g. bash itself is missing
        return f"Could not run bash: {exc}", True
    except ValueError as exc:
        # Popen rejects arguments the OS cannot represent (e.g. an embedded
        # NUL byte in the command — legal JSON the model can emit). Report it
        # as a tool error the model can recover from instead of crashing.
        return f"Could not run bash: {exc}", True

    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append("[stderr]\n" + stderr)
    if returncode != 0:
        parts.append(f"[exit code: {returncode}]")
    output = "\n".join(parts) or "(no output)"
    return output, returncode != 0


def _terminal_safe(text: str) -> str:
    """Re-encode ``text`` so printing it cannot raise ``UnicodeEncodeError``.

    Command output and model text can contain characters the active stdout
    encoding cannot represent (e.g. U+FFFD replacement characters under
    ``PYTHONIOENCODING=ascii``); ``print`` would then crash the whole
    session, so unencodable characters are replaced before printing.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def _run_one_tool(block: ToolUseBlock) -> tuple[str, bool]:
    """Execute one ``tool_use`` block, echoing the command and its output.

    Unknown tools and malformed inputs become error results instead of raising,
    so the model sees what went wrong and can recover.
    """
    if block.name != "bash":
        return f"Unknown tool: {block.name}", True
    command = block.input.get("command") if isinstance(block.input, dict) else None
    if not (isinstance(command, str) and command.strip()):
        return "Invalid input: 'command' must be a non-empty string.", True
    print(_terminal_safe(f"[bash]$ {command}"))
    output, is_error = run_bash(command)
    print(_terminal_safe(output))
    return output, is_error


def _run_tool_calls(content: list[ContentBlock]) -> list[ToolResultBlockParam]:
    """Execute every ``tool_use`` block and return matching ``tool_result``s."""
    results: list[ToolResultBlockParam] = []
    for block in content:
        if block.type != "tool_use":
            continue
        output, is_error = _run_one_tool(block)
        results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
                "is_error": is_error,
            }
        )
    return results


def _error_tool_results(
    content: list[ContentBlock], note: str
) -> list[ToolResultBlockParam]:
    """Pair every ``tool_use`` block with an error ``tool_result``, unexecuted.

    Once an assistant message is in the history, the API rejects every later
    request until each of its ``tool_use`` blocks has a matching
    ``tool_result`` — so tool calls that must not (or could not) run still
    need an error result to keep the conversation alive.
    """
    return [
        {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": note,
            "is_error": True,
        }
        for block in content
        if getattr(block, "type", None) == "tool_use"
    ]


def run() -> None:
    """Start the read → ask → answer loop until the user types ``/exit``.

    A reply may include bash tool calls; they are executed and their results
    fed back to the model until it finishes the turn without tool use.
    """
    # Fill any unset ANTHROPIC_* keys from the config file (environment variables
    # take precedence), then let the SDK read credentials from os.environ.
    load_settings_env()
    client = anthropic.Anthropic()
    if client.api_key is None and client.auth_token is None:
        print(
            "No API credentials found. Set the ANTHROPIC_API_KEY environment variable."
        )
        print(
            "If you use a third-party / proxy service, also set ANTHROPIC_BASE_URL "
            "to point at its endpoint."
        )
        return

    # Resolve the model after load_settings_env() so a config-file ANTHROPIC_MODEL
    # is honored. An empty or whitespace-only value falls back to the default.
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    model = configured_model or DEFAULT_MODEL

    messages: list[MessageParam] = []
    if configured_model:
        print(f"nanoPyCodeAgent — using model {model} (from ANTHROPIC_MODEL).")
    else:
        print(
            f"nanoPyCodeAgent — using default model {model} "
            "(set ANTHROPIC_MODEL to override)."
        )
    print("Type a message to chat, or /exit to quit.")

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input == "/exit":
            break

        turn_start = len(messages)
        messages.append({"role": "user", "content": user_input})

        try:
            # The model may ask to run tools; keep streaming replies and
            # feeding results back until it answers without tool calls (or
            # exhausts the per-turn request budget).
            for _ in range(MAX_REQUESTS_PER_TURN):
                print("\nAgent> ", end="", flush=True)
                # Stream the reply so text shows up as it is generated, then
                # grab the accumulated message for the conversation history.
                with client.messages.stream(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_PROMPT,
                    tools=[BASH_TOOL],
                    messages=messages,
                ) as stream:
                    for text in stream.text_stream:
                        print(_terminal_safe(text), end="", flush=True)
                    message = stream.get_final_message()
                print()

                # Append the full content blocks so the next request (and the
                # next user turn) carries complete context.
                messages.append({"role": "assistant", "content": message.content})

                if message.stop_reason == "tool_use":
                    tool_results = _run_tool_calls(message.content)
                    if not tool_results:
                        break  # defensive: tool_use stop with no tool_use blocks
                    messages.append({"role": "user", "content": tool_results})
                    continue

                # Any other stop reason ends the turn — but a reply truncated
                # at the max_tokens limit can still carry tool_use blocks. A
                # truncated command must never be executed, yet each block
                # still needs a tool_result or the history is poisoned.
                truncated = _error_tool_results(
                    message.content,
                    "Reply was truncated before this tool call could run.",
                )
                if truncated:
                    messages.append({"role": "user", "content": truncated})
                    print("[Reply truncated: its tool calls were not executed.]")
                break
            else:
                # Budget exhausted. The last append was a tool_result message,
                # so the history is valid; hand control back to the user.
                print(
                    f"[Stopped: {MAX_REQUESTS_PER_TURN} requests in one turn; "
                    "reply to continue.]"
                )
        except KeyboardInterrupt:
            # Ctrl-C cancels the current turn, not the session — a turn can
            # now run bash for minutes, and aborting one command must not
            # throw away the whole conversation. (Ctrl-C at the You> prompt
            # still quits.)
            print("\n[Interrupted — turn cancelled]")
            last = messages[-1]
            if last["role"] == "assistant":
                # Interrupted between the tool_use reply and its results:
                # commands may have partially run, so keep the record but pair
                # every dangling tool_use with an error tool_result — the API
                # rejects the history otherwise.
                cancelled = _error_tool_results(
                    last["content"],
                    "Interrupted by user; the command may have partially run.",
                )
                if cancelled:
                    messages.append({"role": "user", "content": cancelled})
            elif len(messages) == turn_start + 1:
                # Nothing but the user prompt made it in: drop the turn as if
                # it was never sent. (Otherwise the turn already holds a
                # completed tool exchange, which stays — see the API-error
                # handler below.)
                del messages[turn_start:]
            continue
        except anthropic.AuthenticationError:
            print(
                "\nAuthentication failed. Check that ANTHROPIC_API_KEY is set correctly."
            )
            break
        except (anthropic.APIError, httpx.HTTPError) as exc:
            # httpx.HTTPError: the SDK wraps transport errors only around the
            # initial send, so a network failure mid-stream surfaces as a raw
            # httpx error during iteration rather than an anthropic.APIError.
            print(f"\nRequest failed: {exc}")
            # Tool calls that already ran had real side effects (files
            # written, commands executed); erasing them from history would
            # make the model unknowingly re-run them on the next attempt.
            # Keep any completed tool exchange — the failure always strikes
            # inside stream(), before the next assistant message is appended,
            # so what has been appended so far is a valid history — and roll
            # back only a turn that never reached a tool call.
            if any(
                m["role"] == "user" and isinstance(m["content"], list)
                for m in messages[turn_start:]
            ):
                print("(Tool calls already executed this turn stay in history.)")
            else:
                del messages[turn_start:]
            continue

    print("Bye!")
