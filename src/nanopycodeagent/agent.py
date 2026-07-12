"""A minimal agent loop built on the Anthropic Python SDK.

Run the program, type a message, and Agent replies. The full conversation is
kept in memory so each turn has context. The model can call a single ``bash``
tool to run shell commands; every command and its output are echoed to the
terminal as they happen. Type ``/exit`` to quit.
"""

import os

import anthropic
import httpx
from anthropic.types import (
    ContentBlock,
    MessageParam,
    ToolResultBlockParam,
    ToolUseBlock,
)

from .bash_tool import BASH_TOOL, run_bash
from .settings import load_settings_env
from .terminal import safe_print

# The model used when ANTHROPIC_MODEL is set in neither the environment nor the
# config file.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
SYSTEM_PROMPT = (
    "You are nanoPyCodeAgent, a concise and helpful coding assistant. "
    "Use the bash tool to inspect files, run code, and complete tasks that "
    "need real command output instead of guessing."
)

# One user input may trigger at most this many API requests: a model stuck
# re-running failing commands must eventually hand control back to the prompt
# instead of burning tokens (and bash executions) until Ctrl-C.
MAX_REQUESTS_PER_TURN = 30


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
    safe_print(f"[bash]$ {command}", tool_bg=True)
    output, is_error = run_bash(command)
    safe_print(output, tool_bg=True)
    return output, is_error


def _tool_result(
    tool_use_id: str, content: str, is_error: bool
) -> ToolResultBlockParam:
    """Build the ``tool_result`` block answering one ``tool_use`` block."""
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
        "is_error": is_error,
    }


def _run_tool_calls(content: list[ContentBlock]) -> list[ToolResultBlockParam]:
    """Execute every ``tool_use`` block and return matching ``tool_result``s."""
    results: list[ToolResultBlockParam] = []
    for block in content:
        if block.type != "tool_use":
            continue
        output, is_error = _run_one_tool(block)
        results.append(_tool_result(block.id, output, is_error))
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
        _tool_result(block.id, note, True)
        for block in content
        if block.type == "tool_use"
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
        # Whether this turn executed tool calls yet — real side effects (files
        # written, commands run) that the error handlers below must not erase.
        ran_tools = False
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
                        safe_print(text, end="")
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
                    ran_tools = True
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
            elif not ran_tools:
                # No side effects yet: drop the turn as if it was never sent.
                # (A turn whose tool calls already ran stays — same policy as
                # the API-error handler below.)
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
            # The error text can come from a proxy or server — sanitize it
            # like any other externally controlled text.
            safe_print(f"\nRequest failed: {exc}")
            # Tool calls that already ran had real side effects (files
            # written, commands executed); erasing them from history would
            # make the model unknowingly re-run them on the next attempt.
            # Keep any completed tool exchange — the failure always strikes
            # inside stream(), before the next assistant message is appended,
            # so what has been appended so far is a valid history — and roll
            # back only a turn that never reached a tool call.
            if ran_tools:
                print("(Tool calls already executed this turn stay in history.)")
            else:
                del messages[turn_start:]
            continue

    print("Bye!")
