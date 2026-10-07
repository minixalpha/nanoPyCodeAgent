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

Both modes retry interrupted response streams before changing conversation
history or running tools. Other unexpected failures and Ctrl-C mid-turn still
end an interactive session. Headless mode catches exhausted API/transport
errors, reports them verbatim, and turns them into an exit code.
"""

import json
import os
import sys
import time
import uuid
from copy import copy
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

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
from anthropic.types import MessageParam, ToolResultBlockParam, ToolUseBlock

from .atif import project_atif, write_atif
from .bash_tool import run_bash
from .cost import (
    estimated_cost,
    pending_cost,
    resolve_generation_cost,
    usage_cost,
)
from .edit_tool import edit_preview, run_edit
from .deadline import DeadlineExceeded, check_deadline_support, wall_clock_limit
from .event_journal import (
    EventEmitter,
    EventJournal,
    JsonObject,
    JsonValue,
    NativeEvent,
    RunOutcome,
    utc_now,
)
from .read_tool import run_read
from .settings import DEFAULT_MAX_TOKENS, load_settings_env, resolve_max_tokens
from .terminal import Spinner, print_tool_output, print_tool_use
from .tool_validation import TOOLS, tool_input_error
from .transport import HTTP_ERRORS, RETRYABLE_STREAM_ERRORS
from .write_tool import content_preview, run_write

# The model used when ANTHROPIC_MODEL is set in neither the environment nor
# the config file.
DEFAULT_MODEL = "claude-sonnet-4-6"

# The SDK retries failures before streaming begins. Recover interrupted response
# bodies here, before committing a reply to history or executing any of its tools.
STREAM_RETRY_DELAYS = (1.0, 2.0)
STREAM_RETRY_WINDOW_SECONDS = 300.0

_TRUNCATION_NOTICE = (
    "[response truncated: reached max_tokens before finishing the task. "
    "Tool calls from this response were not executed.]"
)
_TRUNCATION_RECOVERY_NOTE = (
    "The previous response reached its output limit without finishing the task. "
    "No tool calls from that response were executed. Continue from the last "
    "confirmed tool results and current files within the remaining budget. "
    "This is the only automatic truncation recovery for this run."
)

# How many model replies one headless task may spend before the run stops on
# its own. The interactive loop needs no such cap — a human watching the
# visible output can interrupt a model that keeps retrying the same command —
# but an unattended run would keep paying for that loop until the API
# refuses it.
DEFAULT_MAX_TURNS = 50

# A headless run may also be given a wall-clock budget. When it is, the loop
# tells the model how much time is left and stops before the harness's own
# timeout can kill the process with nothing written. The last stretch is
# reserved so the model still has room to write the task's output file.
_FINALIZATION_RESERVE_SECONDS = 180
_FINALIZATION_RESERVE_FRACTION = 0.15
_FINALIZATION_RESERVE_TURNS = 10
_COST_RECONCILIATION_SECONDS = 30


def _format_duration(total_seconds: float) -> str:
    total = max(0, int(total_seconds))
    return f"{total // 60}:{total % 60:02d}"


def _time_budget_note(
    *, turn: int, elapsed: float, budget: float | None, remaining: float | None,
    max_turns: int | None = None,
) -> str:
    """Tell the model about both limits before either prevents finalization."""
    replies_left = None if max_turns is None else max_turns - turn + 1
    turn_note = f"Turn {turn}. " if max_turns is None else (
        f"Turn {turn} of {max_turns}; {replies_left} replies remaining including "
        "this one. The last reply must be a final summary: its tool calls "
        "will not execute. "
    )
    time_low = remaining is not None and remaining <= max(
        _FINALIZATION_RESERVE_FRACTION * budget, _FINALIZATION_RESERVE_SECONDS
    )
    note = "[runtime budget] " + turn_note
    if remaining is not None:
        note += (
            f"Only {_format_duration(remaining)} of {_format_duration(budget)} left. "
            if time_low else
            f"Elapsed {_format_duration(elapsed)} of {_format_duration(budget)}; "
            f"{_format_duration(remaining)} remaining. "
        )
    if time_low or (replies_left is not None and replies_left <= _FINALIZATION_RESERVE_TURNS):
        note += (
            "Finalize now. Stop investigating new approaches. Complete and save "
            "the required deliverables, perform only the necessary checks, then "
            "reply with a short summary and no further tool calls. If incomplete, "
            "save useful progress and state the remaining limitation honestly."
        )
    else:
        note += (
            "Keep required deliverables up to date. Once the requirements are "
            "satisfied and checked, finish immediately; unused budget is not "
            "a reason to continue investigating."
        )
    return note


def _append_budget_note(
    messages: list[MessageParam],
    note: str,
    *,
    emitter: EventEmitter,
    model_call_id: str,
    reason: str = "time_budget",
) -> None:
    """Append a wall-clock reminder to the tail of the conversation.

    The reminder goes into the most recent user message — the initial task, or
    the tool results — rather than the system prompt. Rewriting the system
    prompt each turn changes the very first tokens of every request and defeats
    the provider's prefix cache; appending to the tail keeps each request an
    extension of the previous one, so the cached prefix survives.
    """
    last = messages[-1]
    content = last["content"]
    if isinstance(content, str):
        last["content"] = f"{content}\n\n{note}"
    else:
        content.append({"type": "text", "text": note})
    emitter.emit(
        "input.injected",
        {
            "model_call_id": model_call_id,
            "content": note,
            "reason": reason,
            "source_timestamp": utc_now(),
        },
    )

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
    "run. Runtime budget reminders report remaining time and model replies; "
    "when either is running low, prioritize saving the required deliverables, "
    "necessary verification, and a final summary. Do not start optional work "
    "after the requirements are satisfied.\n\n"
    "Identify the required deliverables, interfaces, and constraints. Treat "
    "examples as evidence, not as the full contract unless the task says so. "
    "Inspect relevant files, dependencies, and existing checks instead of "
    "guessing.\n\n"
    "Verify the requested behavior through the real entry point when feasible. "
    "Check the content and meaning of outputs, not only command success or "
    "file existence. For logic or numerical work, choose a few representative "
    "and boundary cases justified by the task, using an independent reference, "
    "invariant, or consistency check when available. Do not derive every "
    "expectation from the implementation being tested or weaken requirements "
    "to make a check pass. Keep verification proportional to the task and "
    "remaining budget.\n\n"
    "When a check fails, inspect the error and relevant output, revise the "
    "underlying assumption or implementation, and rerun the affected check. "
    "Keep the task's constraints intact. Once appropriate checks support the "
    "required behavior, save the deliverables and finish. State what was "
    "verified and any remaining limitation without claiming unobserved "
    "success.\n\n"
) + _TOOL_GUIDANCE

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
            arguments = source_block.get("input")
            content.append(
                {
                    "type": "tool_call",
                    "tool_call_id": source_block.get("id"),
                    "tool_name": source_block.get("name"),
                    # Journal/ATIF require object arguments. Keep rejected
                    # non-object input separately instead of discarding it.
                    "input": arguments if isinstance(arguments, dict) else {},
                    **(
                        {"raw_input": arguments}
                        if not isinstance(arguments, dict) else {}
                    ),
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
            if event.payload["stop_reason"] == "max_tokens":
                print(_TRUNCATION_NOTICE, file=sys.stderr)
        elif event.type == "input.injected" and event.payload["reason"] == "truncation_recovery":
            print("[continuing after response truncation; recovery 1/1]", file=sys.stderr)
        elif event.type == "model.failed" and event.payload["will_retry"]:
            if str(event.payload["model_call_id"]) in self._model_calls_with_text:
                print()
            print(
                f"[response interrupted: {event.payload['error_type']}; "
                f"retrying in {event.payload['retry_delay_seconds']:g}s]",
                file=sys.stderr,
            )
        elif event.type == "tool.started":
            tool_name = str(event.payload["tool_name"])
            arguments = event.payload["input"]
            error = event.payload.get("input_error") or tool_input_error(
                tool_name, arguments
            )
            if error:
                print_tool_use(f"[{tool_name}] (invalid arguments; not executed)")
            elif tool_name == "read":
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
            elif tool_name == "bash":
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
    *,
    input_error: str | None = None,
    remaining_seconds: float | None = None,
) -> ToolResultBlockParam:
    """Execute one ``tool_use`` block and emit its runtime facts."""
    tool_input = _json_value(block.input)
    input_error = input_error or tool_input_error(block.name, tool_input)
    emitter.emit(
        "tool.started",
        {
            "model_call_id": model_call_id,
            "tool_call_id": block.id,
            "tool_name": block.name,
            "input": tool_input if isinstance(tool_input, dict) else {},
            **({"input_error": input_error} if input_error else {}),
            "source_timestamp": utc_now(),
        },
    )
    tool_started_ns = time.perf_counter_ns()
    try:
        if input_error:
            output, is_error = input_error, True
        elif block.name == "read":
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
        else:  # bash; unknown names have already been rejected
            command = block.input["command"]
            with Spinner("Running..."):
                output, is_error = run_bash(command, **(
                    {"timeout_seconds": remaining_seconds}
                    if remaining_seconds is not None else {}
                ))
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
            **(
                {"error": {"type": "ToolInputError", "message": input_error}}
                if input_error else {}
            ),
            "duration_ms": (time.perf_counter_ns() - tool_started_ns) / 1_000_000,
            "source_timestamp": utc_now(),
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
    max_tokens: int = DEFAULT_MAX_TOKENS,
    time_budget_seconds: int | None = None,
    reply_prefix: str = "\nAgent> ",
    trajectory_path: Path | None = None,
) -> RunOutcome:
    """Reply to the conversation so far, running tools until the model stops.

    Appends assistant replies and tool results to ``messages`` in place.
    A truncated reply retains only its text and a notice in request history;
    the original response is kept in the journal. Headless runs may recover
    once within the original budgets. Returns the stopping outcome,
    distinguishing completion, turn-budget exhaustion, and response truncation.
    """
    run_id = f"run-{uuid.uuid4()}"
    if time_budget_seconds is not None:
        check_deadline_support()
    run_started_ns = time.perf_counter_ns()
    projector = _TextOutputProjector(reply_prefix)
    with EventJournal.create(run_id) as journal:
        emitter = EventEmitter(journal, projector)
        emitter.emit(
            "run.started",
            {
                "mode": (
                    "headless"
                    if max_turns is not None or time_budget_seconds is not None
                    else "interactive"
                ),
                "model": model,
                "max_turns": max_turns,
                "max_tokens": max_tokens,
                "time_budget_seconds": time_budget_seconds,
                "producer": {
                    "name": "nanoPyCodeAgent",
                    "version": _package_version(),
                },
                "source_timestamp": utc_now(),
            },
        )
        user_content = messages[-1]["content"]
        emitter.emit(
            "user.message",
            {
                "message_id": f"user-{uuid.uuid4()}",
                "content": _json_value(user_content),
                "source_timestamp": utc_now(),
            },
        )
        try:
            outcome = _run_model_loop(
                client,
                model,
                messages,
                system,
                emitter=emitter,
                max_turns=max_turns,
                max_tokens=max_tokens,
                time_budget_seconds=time_budget_seconds,
            )
        except BaseException as exc:
            cost_reconciliation = _reconcile_costs(
                client, journal, emitter,
                max_seconds=_COST_RECONCILIATION_SECONDS if time_budget_seconds else None,
            )
            emitter.emit(
                "run.failed",
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "duration_ms": (time.perf_counter_ns() - run_started_ns)
                    / 1_000_000,
                    **(
                        {"cost_reconciliation": cost_reconciliation}
                        if cost_reconciliation
                        else {}
                    ),
                    "source_timestamp": utc_now(),
                },
            )
            raise
        else:
            cost_reconciliation = _reconcile_costs(
                client, journal, emitter,
                max_seconds=_COST_RECONCILIATION_SECONDS if time_budget_seconds else None,
            )
            emitter.emit(
                "run.completed",
                {
                    "outcome": outcome,
                    "duration_ms": (time.perf_counter_ns() - run_started_ns)
                    / 1_000_000,
                    **(
                        {"cost_reconciliation": cost_reconciliation}
                        if cost_reconciliation
                        else {}
                    ),
                    "source_timestamp": utc_now(),
                },
            )
        finally:
            if trajectory_path is not None:
                write_atif(
                    project_atif(EventJournal.replay(journal.path)),
                    trajectory_path,
                )
        return outcome


def _run_model_loop(
    client: anthropic.Anthropic,
    model: str,
    messages: list[MessageParam],
    system: str,
    *,
    emitter: EventEmitter,
    max_turns: int | None,
    max_tokens: int,
    time_budget_seconds: int | None = None,
) -> RunOutcome:
    """Run model replies and tool calls for an already-started Agent Run."""
    turns = 0
    retries = 0
    retry_deadline = None
    truncation_recovered = False
    recovery_pending = False
    deadline = (
        time.monotonic() + time_budget_seconds
        if time_budget_seconds is not None and time_budget_seconds > 0
        else None
    )
    while True:
        model_call_id = f"model-{uuid.uuid4()}"
        remaining = None
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "time_budget_exhausted"
        if recovery_pending:
            messages.append({"role": "user", "content": _TRUNCATION_RECOVERY_NOTE})
            emitter.emit("input.injected", {
                "model_call_id": model_call_id,
                "content": _TRUNCATION_RECOVERY_NOTE,
                "reason": "truncation_recovery",
                "source_timestamp": utc_now(),
            })
            recovery_pending = False
        if deadline is not None or (max_turns is not None and retries == 0):
            _append_budget_note(
                messages,
                _time_budget_note(
                    turn=turns + 1,
                    elapsed=time_budget_seconds - remaining if deadline is not None else 0,
                    budget=time_budget_seconds,
                    remaining=remaining,
                    max_turns=max_turns,
                ),
                emitter=emitter,
                model_call_id=model_call_id,
                reason="time_budget" if deadline is not None else "turn_budget",
            )
        # A spinner marks the wait for the reply; the first streamed
        # token replaces it with the reply prefix. A tool-only reply
        # streams no text, so the prefix is skipped for it entirely.
        emitter.emit(
            "model.started",
            {
                "model_call_id": model_call_id,
                "model": model,
                "source_timestamp": utc_now(),
            },
        )
        model_started_ns = time.perf_counter_ns()
        # Stream the reply so text shows up as it is generated, then grab
        # the accumulated message for the conversation history.
        generation_id = None
        stream_entered = False
        try:
            with wall_clock_limit(remaining), Spinner() as spinner, client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                tools=TOOLS,
                messages=messages,
                **({"timeout": remaining} if remaining is not None else {}),
            ) as stream:
                stream_entered = True
                generation_id = _response_header(stream, "x-generation-id")
                input_json: dict[int, list[str]] = {}
                for event in stream:
                    if event.type == "text":
                        spinner.stop()
                        emitter.emit(
                            "model.output_delta",
                            {
                                "model_call_id": model_call_id,
                                "delta": event.text,
                                "source_timestamp": utc_now(),
                            },
                        )
                    elif (
                        event.type == "content_block_delta"
                        and event.delta.type == "input_json_delta"
                    ):
                        input_json.setdefault(event.index, []).append(
                            event.delta.partial_json
                        )
                message = stream.get_final_message()
                model_completed_ns = time.perf_counter_ns()
        except DeadlineExceeded as exc:
            emitter.emit("model.failed", {
                "model_call_id": model_call_id,
                "error_type": type(exc).__name__, "message": str(exc),
                "generation_id": generation_id,
                "duration_ms": (time.perf_counter_ns() - model_started_ns) / 1_000_000,
                "will_retry": False, "retry_delay_seconds": 0,
                "source_timestamp": utc_now(),
            })
            return "time_budget_exhausted"
        except (anthropic.APIError, *HTTP_ERRORS) as exc:
            now = time.monotonic()
            if retry_deadline is None:
                retry_deadline = now + STREAM_RETRY_WINDOW_SECONDS
            delay = STREAM_RETRY_DELAYS[retries] if retries < len(STREAM_RETRY_DELAYS) else 0
            retryable = (
                stream_entered
                and isinstance(exc, RETRYABLE_STREAM_ERRORS)
                and retries < len(STREAM_RETRY_DELAYS)
                and now + delay <= retry_deadline
            )
            will_retry = retryable and (deadline is None or now + delay < deadline)
            emitter.emit(
                "model.failed",
                {
                    "model_call_id": model_call_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "generation_id": generation_id,
                    "duration_ms": (time.perf_counter_ns() - model_started_ns) / 1_000_000,
                    "will_retry": will_retry,
                    "retry_delay_seconds": delay if will_retry else 0,
                    "source_timestamp": utc_now(),
                },
            )
            if not will_retry:
                if deadline is not None and (now >= deadline or (retryable and now + delay >= deadline)):
                    return "time_budget_exhausted"
                raise
            # The retry delay fits inside both the recovery window and budget.
            time.sleep(delay)
            retries += 1
            continue

        retries = 0
        retry_deadline = None

        content = _native_content_blocks(message.content)
        input_errors: dict[str, str] = {}
        invalid_json_ids: set[str] = set()
        for index, block in enumerate(message.content):
            if block.type != "tool_use":
                continue
            error = tool_input_error(block.name, block.input)
            if index in input_json:
                raw_json = "".join(input_json[index])
                try:
                    json.loads(raw_json)
                except json.JSONDecodeError:
                    # The SDK parses partial JSON while streaming. Even a
                    # complete-looking dict is not permission to execute an
                    # unfinished call after a provider reports tool_use.
                    error = (
                        "Invalid tool argument JSON: incomplete or malformed. "
                        "Resend a complete JSON object."
                    )
                    invalid_json_ids.add(block.id)
                    content[index]["input_json"] = raw_json
            if error:
                input_errors[block.id] = error
                content[index]["input_error"] = error
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
            "cost": usage_cost(usage if isinstance(usage, dict) else None)
            or estimated_cost(
                str(getattr(message, "model", None) or model),
                usage if isinstance(usage, dict) else None,
            )
            or pending_cost(generation_id),
            "duration_ms": (model_completed_ns - model_started_ns) / 1_000_000,
            "source_timestamp": utc_now(),
        }
        emitter.emit("model.completed", payload)

        turns += 1
        if deadline is not None and time.monotonic() >= deadline:
            return "time_budget_exhausted"
        if message.stop_reason == "max_tokens":
            # Do not execute partial tool calls or replay them without results.
            # Thinking may also be cut off before its signature arrives. Keep
            # visible text and an explicit notice for a safe follow-up request.
            text = "".join(
                block.text for block in message.content if block.type == "text"
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": (f"{text}\n\n" if text else "") + _TRUNCATION_NOTICE,
                }
            )
            if (
                not truncation_recovered
                and (max_turns is not None or time_budget_seconds is not None)
                and (max_turns is None or turns < max_turns)
            ):
                truncation_recovered = True
                recovery_pending = True
                continue
            return "response_truncated"
        request_content = []
        for block in message.content:
            if block.type == "tool_use" and (
                block.id in invalid_json_ids or not isinstance(block.input, dict)
            ):
                block = copy(block)
                block.input = {}
            request_content.append(block)
        messages.append({"role": "assistant", "content": request_content})
        if message.stop_reason != "tool_use":
            return "completed"
        if max_turns is not None and turns >= max_turns:
            # Stop before running the tools: their results would only be
            # useful to a reply this budget can no longer pay for.
            return "max_turns_exhausted"
        # Every tool_use block needs a matching tool_result in the next
        # user message, or the API rejects the request.
        results = []
        for block in message.content:
            if block.type != "tool_use":
                continue
            if deadline is not None and time.monotonic() >= deadline:
                # The reply or a preceding tool consumed the remaining time.
                # Stop the run without starting another tool or model call.
                return "time_budget_exhausted"
            remaining = None if deadline is None else deadline - time.monotonic()
            try:
                with wall_clock_limit(remaining):
                    result = _run_one_tool(
                        block, emitter, model_call_id,
                        input_error=input_errors.get(block.id),
                        remaining_seconds=remaining,
                    )
            except DeadlineExceeded:
                return "time_budget_exhausted"
            results.append(result)
        messages.append({"role": "user", "content": results})


def _reconcile_costs(
    client: anthropic.Anthropic,
    journal: EventJournal,
    emitter: EventEmitter,
    *,
    max_seconds: float | None = None,
) -> list[JsonObject]:
    """Reconcile pending or estimated costs without affecting the run outcome."""
    base_url = getattr(client, "base_url", "")
    credential = client.api_key or client.auth_token
    if not isinstance(credential, str) or not credential:
        return []
    outcomes: list[JsonObject] = []
    deadline = None if max_seconds is None else time.monotonic() + max_seconds
    entries = EventJournal.replay(journal.path)
    already_resolved = {
        str(entry.payload["generation_id"])
        for entry in entries
        if entry.type == "model.cost_resolved"
    }
    for entry in entries:
        if entry.type not in {"model.completed", "model.failed"}:
            continue
        generation_id = entry.payload.get("generation_id")
        cost = (
            pending_cost(generation_id)
            if entry.type == "model.failed"
            else entry.payload.get("cost")
        )
        if (
            not isinstance(generation_id, str)
            or generation_id in already_resolved
            or not isinstance(cost, dict)
            or (cost.get("status") != "pending" and cost.get("kind") != "estimated")
        ):
            continue
        diagnostics: list[JsonObject] = []
        if deadline is not None and time.monotonic() >= deadline:
            break
        try:
            with wall_clock_limit(None if deadline is None else deadline - time.monotonic()):
                resolved = resolve_generation_cost(
                    base_url, generation_id, credential, diagnostics=diagnostics,
                )
        except DeadlineExceeded:
            outcomes.append({"generation_id": generation_id, "status": "unresolved",
                             "attempts": diagnostics, "reason": "finalization_deadline"})
            break
        if resolved is not None:
            resolved["source_timestamp"] = utc_now()
            emitter.emit("model.cost_resolved", resolved)
        outcomes.append(
            {
                "generation_id": generation_id,
                "status": "resolved" if resolved is not None else "unresolved",
                "attempts": diagnostics,
            }
        )
    return outcomes


def run(*, max_tokens: int | None = None) -> int:
    """Start the read → ask → answer loop until the user types ``/exit``.

    A reply may include tool calls; they are executed and their results
    fed back to the model until it finishes the turn without tool use.
    Returns the process exit code.
    """
    max_tokens = resolve_max_tokens(max_tokens)
    client = _create_client()
    if client is None:
        return 1

    model = _resolve_model()
    print(
        f"nanoPyCodeAgent v{_package_version()} — model {model}, "
        f"max tokens {max_tokens} "
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
        _run_exchange(client, model, messages, SYSTEM_PROMPT, max_tokens=max_tokens)

    print("Bye!")
    return 0


def run_headless(
    task: str,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_tokens: int | None = None,
    time_budget_seconds: int | None = None,
    trajectory_path: Path | None = None,
) -> int:
    """Work ``task`` to completion without a user, and return the exit code.

    The exit code answers one question — did the *harness* fail, or did the
    *task*? A benchmark reads a non-zero code as "this agent broke", drops
    the trial, and may pay to retry it, so everything that is merely a bad
    outcome for the task (the model gave up, the turn budget ran out, the
    work is half done) still exits 0 and leaves the verdict to whatever
    scores the result. Only a run that could not happen at all — no
    credentials, an API that keeps refusing — exits non-zero.
    """
    max_tokens = resolve_max_tokens(max_tokens)
    client = _create_client()
    if client is None:
        return 1

    model = _resolve_model()
    # The banner goes to stderr so stdout carries the run itself: the
    # model's prose and the echoed tool calls, nothing else.
    print(
        f"nanoPyCodeAgent v{_package_version()} — model {model}, "
        f"max turns {max_turns}, max tokens {max_tokens}, "
        f"time budget {time_budget_seconds if time_budget_seconds else 'none'}",
        file=sys.stderr,
    )

    messages: list[MessageParam] = [{"role": "user", "content": task}]
    try:
        outcome = _run_exchange(
            client,
            model,
            messages,
            HEADLESS_SYSTEM_PROMPT,
            max_turns=max_turns,
            max_tokens=max_tokens,
            time_budget_seconds=time_budget_seconds,
            reply_prefix="",
            trajectory_path=trajectory_path,
        )
    except (anthropic.APIError, *HTTP_ERRORS) as exc:
        # Printed verbatim on purpose: a harness classifies a failed run by
        # pattern-matching this text (rate limit, overloaded, context length,
        # …) to decide whether retrying is worth anything. Rewording it, or
        # swallowing it, throws that away.
        print(f"API error: {exc}", file=sys.stderr)
        return 1
    if outcome == "max_turns_exhausted":
        turns = "turn" if max_turns == 1 else "turns"
        print(
            f"[stopped after {max_turns} {turns} without finishing the task]",
            file=sys.stderr,
        )
    elif outcome == "time_budget_exhausted":
        print(
            f"[stopped after the {time_budget_seconds}s time budget without "
            "finishing the task]",
            file=sys.stderr,
        )
    return 0
