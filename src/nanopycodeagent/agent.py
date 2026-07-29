"""A minimal agent loop built on the Anthropic Python SDK.

Run the program, type a message, and Agent replies. The full conversation is
kept in memory so each turn has context. The model can call a ``read`` tool
to view files and a ``bash`` tool to run shell commands; every call and its
output are echoed to the terminal as they happen. Type ``/exit`` to quit.

The loop handles only the happy path: anything unexpected — a network error,
a Ctrl-C mid-turn — crashes the session, and restarting it is the recovery.
That trade keeps the core flow readable; the hardened variant it replaced is
preserved at the ``hardened-agent-loop`` tag.
"""

import os
from importlib.metadata import PackageNotFoundError, version

import anthropic
from anthropic.types import MessageParam, ToolResultBlockParam, ToolUseBlock

from .bash_tool import BASH_TOOL, run_bash
from .read_tool import READ_TOOL, run_read
from .settings import load_settings_env
from .terminal import print_tool

# The model used when ANTHROPIC_MODEL is set in neither the environment nor
# the config file.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
SYSTEM_PROMPT = (
    "You are nanoPyCodeAgent, a concise and helpful coding assistant. "
    "Prefer the read tool for viewing files. Use the bash tool to run "
    "commands, search with grep, and complete tasks that need real command "
    "output instead of guessing."
)

# Every tool offered to the model on each request.
TOOLS = [READ_TOOL, BASH_TOOL]


def _package_version() -> str:
    """Return the installed package version.

    The version comes from the package metadata written at install time
    (hatch-vcs derives it from the git tag). When the package is not
    installed — e.g. the module is run straight from a source checkout —
    there is no metadata to read, so fall back to a placeholder.
    """
    try:
        return version("nanoPyCodeAgent")
    except PackageNotFoundError:
        return "unknown"


def _run_one_tool(block: ToolUseBlock) -> ToolResultBlockParam:
    """Execute one ``tool_use`` block, echoing the call and its output."""
    if block.name == "read":
        path = block.input["path"]
        print_tool(f"[read] {path}")
        output, is_error = run_read(
            path,
            offset=block.input.get("offset", 1),
            limit=block.input.get("limit"),
        )
    else:  # bash — the only other tool offered
        command = block.input["command"]
        print_tool(f"[bash]$ {command}")
        output, is_error = run_bash(command)
    print_tool(output)
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": output,
        "is_error": is_error,
    }


def run() -> None:
    """Start the read → ask → answer loop until the user types ``/exit``.

    A reply may include tool calls; they are executed and their results
    fed back to the model until it finishes the turn without tool use.
    """
    # Fill any unset ANTHROPIC_* keys from the config file (environment
    # variables take precedence), then let the SDK read credentials from
    # os.environ.
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

    model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL
    print(
        f"nanoPyCodeAgent v{_package_version()} — model {model} "
        "(set ANTHROPIC_MODEL to override)."
    )
    print("Type a message to chat, or /exit to quit.")

    messages: list[MessageParam] = []
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

        messages.append({"role": "user", "content": user_input})
        # The model may ask to run tools; keep streaming replies and feeding
        # results back until it finishes a reply without tool calls.
        while True:
            print("\nAgent> ", end="", flush=True)
            # Stream the reply so text shows up as it is generated, then grab
            # the accumulated message for the conversation history.
            with client.messages.stream(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                message = stream.get_final_message()
            print()

            messages.append({"role": "assistant", "content": message.content})
            if message.stop_reason != "tool_use":
                break
            # Every tool_use block needs a matching tool_result in the next
            # user message, or the API rejects the request.
            results = [
                _run_one_tool(block)
                for block in message.content
                if block.type == "tool_use"
            ]
            messages.append({"role": "user", "content": results})

    print("Bye!")
