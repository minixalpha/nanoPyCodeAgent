"""A minimal agent loop built on the Anthropic Python SDK.

There are two ways in, and both land in the same loop. Interactively, run
the program, type a message, and Agent replies; the full conversation is
kept in memory so each turn has context, and ``/exit`` quits. Headlessly,
hand the program one task up front (see ``cli.py``) and it works that task
to completion and exits, with no prompt and nobody to ask.

The model can call a ``read`` tool to view files, a ``write`` tool to create
or overwrite them, an ``edit`` tool to replace part of one, and a ``bash``
tool to run shell commands; every call and its output are echoed to the
terminal as they happen.

The interactive loop handles only the happy path: anything unexpected — a
network error, a Ctrl-C mid-turn — crashes the session, and restarting it is
the recovery. That trade keeps the core flow readable; the hardened variant
it replaced is preserved at the ``hardened-agent-loop`` tag. A headless run
has no one to restart it, so it catches API errors, reports them verbatim,
and turns them into an exit code.
"""

import os
import sys
import time
import uuid
from importlib.metadata import PackageNotFoundError, version

try:
    # Importing readline routes input() through a line editor that redraws the
    # whole line. Without it the tty erases one column per backspace, which
    # leaves half of a double-width character (CJK, emoji) on screen even
    # though it is gone from the buffer. Editing and history come along for
    # the ride. Not available on every platform, so the import is optional.
    import readline  # noqa: F401
except ImportError:  # pragma: no cover - platform without readline
    pass

import anthropic
import httpx
from anthropic.types import MessageParam, ToolResultBlockParam, ToolUseBlock

from .bash_tool import BASH_TOOL, run_bash
from .edit_tool import EDIT_TOOL, edit_preview, run_edit
from .event_journal import (
    EventEmitter,
    EventJournal,
    JsonObject,
    JsonValue,
    NativeEvent,
    utc_now,
)
from .read_tool import READ_TOOL, run_read
from .settings import load_settings_env
from .terminal import Spinner, print_tool_output, print_tool_use
from .write_tool import WRITE_TOOL, content_preview, run_write

# The model used when ANTHROPIC_MODEL is set in neither the environment nor
# the config file.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192

# How many model replies one headless task may spend before the run stops on
# its own. The interactive loop needs no such cap — a human watching the
# visible output can interrupt a model that keeps retrying the same command —
# but an unattended run would keep paying for that loop until the API
# refuses it.
DEFAULT_MAX_TURNS = 50

# Shared by both system prompts: which tool to reach for is the same question
# whoever is asking.
_TOOL_GUIDANCE = (
    "Prefer the read tool for viewing files, the edit tool for changing "
    "part of an existing file, and the write tool for creating files or "
    "rewriting them whole. Use the bash tool to run commands, search with "
    "grep, and complete tasks that need real command output instead of "
    "guessing."
)

SYSTEM_PROMPT = (
    "You are nanoPyCodeAgent, a concise and helpful coding assistant. "
) + _TOOL_GUIDANCE

# The headless variant. None of this is a matter of tone: with no user at the
# other end, a clarifying question or a pause for approval ends the run with
# the task untouched, and a benchmark scores that exactly like a wrong answer.
HEADLESS_SYSTEM_PROMPT = (
    "You are nanoPyCodeAgent, a coding agent running non-interactively on a "
    "task handed to you up front. There is no user to reply to you: never "
    "ask a clarifying question, never stop to wait for confirmation, and "
    "never present a plan for approval — decide on your own and carry it "
    "out. Work the task through to the end, then check the result with the "
    "tools instead of assuming it worked. When it is done, answer with a "
    "short summary and no further tool calls: that reply is what ends the "
    "run. "
) + _TOOL_GUIDANCE

# Every tool offered to the model on each request.
TOOLS = [READ_TOOL, WRITE_TOOL, EDIT_TOOL, BASH_TOOL]


def _json_value(value: object) -> JsonValue:
    """Convert an SDK value into the provider-neutral event representation."""
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_value(model_dump(mode="json", exclude_none=True))
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        return {
            key: _json_value(item)
            for key, item in attributes.items()
            if not key.startswith("_")
        }
    raise TypeError(f"cannot represent {type(value).__name__} as event JSON")


def _native_content_blocks(value: object) -> list[JsonValue]:
    """Normalize Anthropic response blocks into provider-neutral content."""
    source_blocks = _json_value(value)
    if not isinstance(source_blocks, list):
        raise TypeError("model response content must be a list")
    content: list[JsonValue] = []
    for source_block in source_blocks:
        if not isinstance(source_block, dict):
            raise TypeError("model response content blocks must be objects")
        source_type = source_block.get("type")
        if source_type == "text":
            content.append({"type": "text", "text": source_block.get("text", "")})
        elif source_type == "tool_use":
            content.append(
                {
                    "type": "tool_call",
                    "tool_call_id": source_block.get("id"),
                    "tool_name": source_block.get("name"),
                    "input": source_block.get("input"),
                }
            )
        else:
            # Preserve an unfamiliar block without declaring its SDK shape to
            # be part of the core schema. A future transport can normalize a
            # corresponding provider block into the same content vocabulary.
            content.append(
                {
                    "type": "extension",
                    "namespace": "anthropic",
                    "source_type": source_type,
                    "value": source_block,
                }
            )
    return content


def _response_header(stream: object, name: str) -> str | None:
    response = getattr(stream, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    value = headers.get(name)
    if value is None:
        value = headers.get(name.title())
    return str(value) if value is not None else None


class _TextOutputProjector:
    """Preserve the existing text Run Output as a Native Event projection."""

    def __init__(self, reply_prefix: str) -> None:
        self._reply_prefix = reply_prefix
        self._model_calls_with_text: set[str] = set()

    def __call__(self, event: NativeEvent) -> None:
        if event.type == "model.output_delta":
            model_call_id = str(event.payload["model_call_id"])
            if model_call_id not in self._model_calls_with_text:
                if self._reply_prefix:
                    print(self._reply_prefix, end="", flush=True)
                self._model_calls_with_text.add(model_call_id)
            print(str(event.payload["delta"]), end="", flush=True)
        elif event.type == "model.completed":
            model_call_id = str(event.payload["model_call_id"])
            if model_call_id in self._model_calls_with_text:
                print()
        elif event.type == "tool.started":
            tool_name = str(event.payload["tool_name"])
            arguments = event.payload["input"]
            if not isinstance(arguments, dict):
                raise TypeError("tool input event payload must be an object")
            if tool_name == "read":
                print_tool_use(f"[read] {arguments['path']}")
            elif tool_name == "write":
                content = str(arguments["content"])
                print_tool_use(
                    f"[write] {arguments['path']}\n{content_preview(content)}"
                )
            elif tool_name == "edit":
                old_text = str(arguments["old_text"])
                new_text = str(arguments["new_text"])
                print_tool_use(
                    f"[edit] {arguments['path']}\n"
                    f"{edit_preview(old_text, new_text)}"
                )
            else:
                print_tool_use(f"[bash]$ {arguments['command']}")
        elif event.type == "tool.completed":
            result = event.payload["result"]
            if isinstance(result, str):
                print_tool_output(result)


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


def _run_one_tool(
    block: ToolUseBlock,
    emitter: EventEmitter,
    model_call_id: str,
) -> ToolResultBlockParam:
    """Execute one ``tool_use`` block and emit its runtime facts."""
    tool_input = _json_value(block.input)
    if not isinstance(tool_input, dict):
        raise TypeError("tool input must be an object")
    emitter.emit(
        "tool.started",
        {
            "model_call_id": model_call_id,
            "tool_call_id": block.id,
            "tool_name": block.name,
            "input": tool_input,
            "source_timestamp": utc_now(),
            "timestamp_source": "core",
        },
    )
    tool_started_ns = time.perf_counter_ns()
    try:
        if block.name == "read":
            path = block.input["path"]
            output, is_error = run_read(
                path,
                offset=block.input.get("offset", 1),
                limit=block.input.get("limit"),
            )
        elif block.name == "write":
            path = block.input["path"]
            content = block.input["content"]
            output, is_error = run_write(path, content)
        elif block.name == "edit":
            path = block.input["path"]
            old_text = block.input["old_text"]
            new_text = block.input["new_text"]
            output, is_error = run_edit(
                path,
                old_text,
                new_text,
                replace_all=block.input.get("replace_all", False),
            )
        else:  # bash — the only other tool offered
            command = block.input["command"]
            with Spinner("Running..."):
                output, is_error = run_bash(command)
    except BaseException as exc:
        emitter.emit(
            "tool.completed",
            {
                "model_call_id": model_call_id,
                "tool_call_id": block.id,
                "tool_name": block.name,
                "result": None,
                "is_error": True,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "duration_ms": (time.perf_counter_ns() - tool_started_ns)
                / 1_000_000,
                "source_timestamp": utc_now(),
                "timestamp_source": "core",
            },
        )
        raise
    emitter.emit(
        "tool.completed",
        {
            "model_call_id": model_call_id,
            "tool_call_id": block.id,
            "tool_name": block.name,
            "result": output,
            "is_error": is_error,
            "duration_ms": (time.perf_counter_ns() - tool_started_ns) / 1_000_000,
            "source_timestamp": utc_now(),
            "timestamp_source": "core",
        },
    )
    return {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": output,
        "is_error": is_error,
    }


def _create_client() -> anthropic.Anthropic | None:
    """Build the SDK client, or explain on stderr why it cannot be built.

    Any unset ``ANTHROPIC_*`` key is filled from the config file first
    (environment variables take precedence), then the SDK reads credentials
    from ``os.environ``. Missing credentials are a configuration failure, not
    a task failure, so the explanation goes to stderr and the caller turns it
    into a non-zero exit code.
    """
    load_settings_env()
    client = anthropic.Anthropic()
    if client.api_key is None and client.auth_token is None:
        print(
            "No API credentials found. Set the ANTHROPIC_API_KEY environment variable.",
            file=sys.stderr,
        )
        print(
            "If you use a third-party / proxy service, also set ANTHROPIC_BASE_URL "
            "to point at its endpoint.",
            file=sys.stderr,
        )
        return None
    return client


def _resolve_model() -> str:
    """The configured model, or the default when nothing usable is set."""
    return os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL


def _run_exchange(
    client: anthropic.Anthropic,
    model: str,
    messages: list[MessageParam],
    system: str,
    *,
    max_turns: int | None = None,
    reply_prefix: str = "\nAgent> ",
) -> bool:
    """Reply to the conversation so far, running tools until the model stops.

    Appends every assistant reply and tool result to ``messages`` in place.
    Returns True when the model ended a reply without asking for tools, and
    False when ``max_turns`` replies were spent while it was still calling
    them — the caller decides what an exhausted budget means.
    """
    run_id = f"run-{uuid.uuid4()}"
    run_started_ns = time.perf_counter_ns()
    projector = _TextOutputProjector(reply_prefix)
    with EventJournal.create(run_id) as journal:
        emitter = EventEmitter(journal, projector)
        emitter.emit(
            "run.started",
            {
                "mode": "headless" if max_turns is not None else "interactive",
                "model": model,
                "max_turns": max_turns,
                "source_timestamp": utc_now(),
                "timestamp_source": "core",
            },
        )
        user_content = messages[-1]["content"]
        emitter.emit(
            "user.message",
            {
                "message_id": f"user-{uuid.uuid4()}",
                "content": _json_value(user_content),
                "source_timestamp": utc_now(),
                "timestamp_source": "core",
            },
        )
        try:
            finished = _run_model_loop(
                client,
                model,
                messages,
                system,
                emitter=emitter,
                max_turns=max_turns,
            )
        except BaseException as exc:
            emitter.emit(
                "run.failed",
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "duration_ms": (time.perf_counter_ns() - run_started_ns)
                    / 1_000_000,
                    "source_timestamp": utc_now(),
                    "timestamp_source": "core",
                },
            )
            raise
        emitter.emit(
            "run.completed",
            {
                "outcome": "completed" if finished else "max_turns_exhausted",
                "duration_ms": (time.perf_counter_ns() - run_started_ns) / 1_000_000,
                "source_timestamp": utc_now(),
                "timestamp_source": "core",
            },
        )
        return finished


def _run_model_loop(
    client: anthropic.Anthropic,
    model: str,
    messages: list[MessageParam],
    system: str,
    *,
    emitter: EventEmitter,
    max_turns: int | None,
) -> bool:
    """Run model replies and tool calls for an already-started Agent Run."""
    turns = 0
    while True:
        # A spinner marks the wait for the reply; the first streamed
        # token replaces it with the reply prefix. A tool-only reply
        # streams no text, so the prefix is skipped for it entirely.
        model_call_id = f"model-{uuid.uuid4()}"
        emitter.emit(
            "model.started",
            {
                "model_call_id": model_call_id,
                "model": model,
                "source_timestamp": utc_now(),
                "timestamp_source": "core",
            },
        )
        model_started_ns = time.perf_counter_ns()
        # Stream the reply so text shows up as it is generated, then grab
        # the accumulated message for the conversation history.
        with Spinner() as spinner, client.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            tools=TOOLS,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                spinner.stop()
                emitter.emit(
                    "model.output_delta",
                    {
                        "model_call_id": model_call_id,
                        "delta": text,
                        "source_timestamp": utc_now(),
                        "timestamp_source": "core",
                    },
                )
            message = stream.get_final_message()
            generation_id = _response_header(stream, "x-generation-id")

        content = _native_content_blocks(message.content)
        tool_calls = [
            item
            for item in content
            if isinstance(item, dict) and item.get("type") == "tool_call"
        ]
        provider_response_id = getattr(message, "id", None)
        usage = _json_value(getattr(message, "usage", None))
        payload: JsonObject = {
            "model_call_id": model_call_id,
            "message_id": str(provider_response_id or model_call_id),
            "content": content,
            "tool_calls": tool_calls,
            "model": str(getattr(message, "model", None) or model),
            "stop_reason": getattr(message, "stop_reason", None),
            "usage": usage,
            "provider_response_id": (
                str(provider_response_id) if provider_response_id is not None else None
            ),
            "generation_id": generation_id,
            "duration_ms": (time.perf_counter_ns() - model_started_ns) / 1_000_000,
            "source_timestamp": utc_now(),
            "timestamp_source": "core",
        }
        emitter.emit("model.completed", payload)

        turns += 1
        messages.append({"role": "assistant", "content": message.content})
        if message.stop_reason != "tool_use":
            return True
        if max_turns is not None and turns >= max_turns:
            # Stop before running the tools: their results would only be
            # useful to a reply this budget can no longer pay for.
            return False
        # Every tool_use block needs a matching tool_result in the next
        # user message, or the API rejects the request.
        results = [
            _run_one_tool(block, emitter, model_call_id)
            for block in message.content
            if block.type == "tool_use"
        ]
        messages.append({"role": "user", "content": results})


def run() -> int:
    """Start the read → ask → answer loop until the user types ``/exit``.

    A reply may include tool calls; they are executed and their results
    fed back to the model until it finishes the turn without tool use.
    Returns the process exit code.
    """
    client = _create_client()
    if client is None:
        return 1

    model = _resolve_model()
    print(
        f"nanoPyCodeAgent v{_package_version()} — model {model} "
        "(set ANTHROPIC_MODEL to override)."
    )
    print("Type a message to chat, or /exit to quit.")

    messages: list[MessageParam] = []
    while True:
        try:
            # The blank line before the prompt is printed separately: readline
            # measures the prompt to place the cursor, and a newline inside it
            # throws that off.
            print()
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input == "/exit":
            break

        messages.append({"role": "user", "content": user_input})
        _run_exchange(client, model, messages, SYSTEM_PROMPT)

    print("Bye!")
    return 0


def run_headless(task: str, *, max_turns: int = DEFAULT_MAX_TURNS) -> int:
    """Work ``task`` to completion without a user, and return the exit code.

    The exit code answers one question — did the *harness* fail, or did the
    *task*? A benchmark reads a non-zero code as "this agent broke", drops
    the trial, and may pay to retry it, so everything that is merely a bad
    outcome for the task (the model gave up, the turn budget ran out, the
    work is half done) still exits 0 and leaves the verdict to whatever
    scores the result. Only a run that could not happen at all — no
    credentials, an API that keeps refusing — exits non-zero.
    """
    client = _create_client()
    if client is None:
        return 1

    model = _resolve_model()
    # The banner goes to stderr so stdout carries the run itself: the
    # model's prose and the echoed tool calls, nothing else.
    print(
        f"nanoPyCodeAgent v{_package_version()} — model {model}, "
        f"max turns {max_turns}",
        file=sys.stderr,
    )

    messages: list[MessageParam] = [{"role": "user", "content": task}]
    try:
        finished = _run_exchange(
            client,
            model,
            messages,
            HEADLESS_SYSTEM_PROMPT,
            max_turns=max_turns,
            reply_prefix="",
        )
    except (anthropic.APIError, httpx.HTTPError) as exc:
        # Printed verbatim on purpose: a harness classifies a failed run by
        # pattern-matching this text (rate limit, overloaded, context length,
        # …) to decide whether retrying is worth anything. Rewording it, or
        # swallowing it, throws that away.
        print(f"API error: {exc}", file=sys.stderr)
        return 1
    if not finished:
        turns = "turn" if max_turns == 1 else "turns"
        print(
            f"[stopped after {max_turns} {turns} without finishing the task]",
            file=sys.stderr,
        )
    return 0
