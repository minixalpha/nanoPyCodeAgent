"""Project one Event Journal into an ATIF-v1.7 trajectory."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .event_journal import JsonObject, JsonValue, JournalEntry, SCHEMA_VERSION

ATIF_SCHEMA_VERSION = "ATIF-v1.7"


class AtifProjectionError(ValueError):
    """The Event Journal cannot be represented as a complete ATIF document."""


def _timestamp(entry: JournalEntry) -> tuple[str, str]:
    source_timestamp = entry.payload.get("source_timestamp")
    if isinstance(source_timestamp, str):
        return source_timestamp, "source_timestamp"
    return entry.recorded_at, "recorded_at"


def _message(content: JsonValue) -> str | list[JsonObject]:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise AtifProjectionError("ATIF message content must be text or content parts")

    text_parts = [
        {"type": "text", "text": block["text"]}
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]
    if not text_parts:
        return ""
    if len(text_parts) == 1:
        text = text_parts[0]["text"]
        assert isinstance(text, str)
        return text
    return text_parts


def _metrics(usage: JsonObject | None) -> JsonObject | None:
    if usage is None:
        return None
    input_tokens = usage["input_tokens"]
    output_tokens = usage["output_tokens"]
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_creation = usage.get("cache_creation_input_tokens", 0)
    assert isinstance(input_tokens, int)
    assert isinstance(output_tokens, int)
    assert isinstance(cache_read, int)
    assert isinstance(cache_creation, int)

    metrics: JsonObject = {
        "prompt_tokens": input_tokens + cache_read + cache_creation,
        "completion_tokens": output_tokens,
        "cached_tokens": cache_read,
    }
    metrics_extra: JsonObject = {}
    if "cache_creation_input_tokens" in usage:
        metrics_extra["cache_creation_input_tokens"] = cache_creation
    provider_usage = {
        key: value
        for key, value in usage.items()
        if key
        not in {
            "input_tokens",
            "output_tokens",
            "cache_read_input_tokens",
            "cache_creation_input_tokens",
        }
    }
    if provider_usage:
        metrics_extra["provider_usage"] = provider_usage
    if metrics_extra:
        metrics["extra"] = metrics_extra
    return metrics


def _step_extra(
    entry: JournalEntry,
    started: JournalEntry | None,
) -> JsonObject:
    payload = entry.payload
    _, timestamp_source = _timestamp(entry)
    extra: JsonObject = {
        "model_call_id": payload["model_call_id"],
        "message_id": payload["message_id"],
        "provider_response_id": payload["provider_response_id"],
        "generation_id": payload["generation_id"],
        "stop_reason": payload["stop_reason"],
        "duration_ms": payload["duration_ms"],
    }
    content = payload["content"]
    assert isinstance(content, list)
    content_extensions = [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") == "extension"
    ]
    if content_extensions:
        extra["content_extensions"] = content_extensions
    if started is not None:
        started_at, started_source = _timestamp(started)
        extra["started_at"] = started_at
        extra["started_at_source"] = started_source
    extra["timestamp_source"] = timestamp_source
    return extra


def _tool_calls_and_observation(
    entry: JournalEntry,
    tool_starts: dict[str, JournalEntry],
    tool_completions: dict[str, JournalEntry],
) -> tuple[list[JsonObject], JsonObject | None]:
    model_call_id = entry.payload["model_call_id"]
    native_tool_calls = entry.payload["tool_calls"]
    assert isinstance(model_call_id, str)
    assert isinstance(native_tool_calls, list)
    tool_calls: list[JsonObject] = []
    results: list[JsonObject] = []
    for native_tool_call in native_tool_calls:
        assert isinstance(native_tool_call, dict)
        tool_call_id = native_tool_call["tool_call_id"]
        assert isinstance(tool_call_id, str)
        tool_call: JsonObject = {
            "tool_call_id": tool_call_id,
            "function_name": native_tool_call["tool_name"],
            "arguments": native_tool_call["input"],
        }
        started = tool_starts.get(tool_call_id)
        if started is not None and started.payload.get("model_call_id") in {
            None,
            model_call_id,
        }:
            started_at, timestamp_source = _timestamp(started)
            tool_call["extra"] = {
                "started_at": started_at,
                "timestamp_source": timestamp_source,
            }
        tool_calls.append(tool_call)

        completed = tool_completions.get(tool_call_id)
        if completed is None or completed.payload.get("model_call_id") not in {
            None,
            model_call_id,
        }:
            continue
        completed_at, timestamp_source = _timestamp(completed)
        completed_payload = completed.payload
        result_extra: JsonObject = {
            "is_error": completed_payload["is_error"],
            "duration_ms": completed_payload["duration_ms"],
            "timestamp": completed_at,
            "timestamp_source": timestamp_source,
        }
        if "error" in completed_payload:
            result_extra["error"] = completed_payload["error"]
        results.append(
            {
                "source_call_id": tool_call_id,
                "content": completed_payload["result"],
                "extra": result_extra,
            }
        )
    observation: JsonObject | None = {"results": results} if results else None
    return tool_calls, observation


def project_atif(entries: Sequence[JournalEntry]) -> JsonObject:
    """Fold a complete headless Event Journal into one ATIF-v1.7 document."""
    if not entries:
        raise AtifProjectionError("cannot project an empty Event Journal")
    if any(entry.schema_version != SCHEMA_VERSION for entry in entries):
        raise AtifProjectionError("unsupported Event Journal schema")
    run_ids = {entry.run_id for entry in entries}
    if len(run_ids) != 1:
        raise AtifProjectionError("Event Journal contains more than one run")
    if entries[0].type != "run.started":
        raise AtifProjectionError("Event Journal must start with run.started")

    started_run = entries[0]
    run_payload = started_run.payload
    if run_payload["mode"] != "headless":
        raise AtifProjectionError("ATIF projection supports headless runs only")
    producer = run_payload["producer"]
    assert isinstance(producer, dict)

    steps: list[JsonObject] = []
    model_starts: dict[str, JournalEntry] = {}
    model_deltas: dict[str, list[JournalEntry]] = {}
    completed_model_calls: set[str] = set()
    tool_starts = {
        str(entry.payload["tool_call_id"]): entry
        for entry in entries
        if entry.type == "tool.started"
    }
    tool_completions = {
        str(entry.payload["tool_call_id"]): entry
        for entry in entries
        if entry.type == "tool.completed"
    }
    terminal: JournalEntry | None = None
    for entry in entries[1:]:
        payload = entry.payload
        if entry.type == "user.message":
            timestamp, timestamp_source = _timestamp(entry)
            steps.append(
                {
                    "step_id": len(steps) + 1,
                    "timestamp": timestamp,
                    "source": "user",
                    "message": _message(payload["content"]),
                    "extra": {
                        "message_id": payload["message_id"],
                        "timestamp_source": timestamp_source,
                    },
                }
            )
        elif entry.type == "model.started":
            model_call_id = payload["model_call_id"]
            assert isinstance(model_call_id, str)
            model_starts[model_call_id] = entry
        elif entry.type == "model.output_delta":
            model_call_id = payload["model_call_id"]
            assert isinstance(model_call_id, str)
            model_deltas.setdefault(model_call_id, []).append(entry)
        elif entry.type == "model.completed":
            model_call_id = payload["model_call_id"]
            assert isinstance(model_call_id, str)
            completed_model_calls.add(model_call_id)
            timestamp, _ = _timestamp(entry)
            usage = payload["usage"]
            assert usage is None or isinstance(usage, dict)
            step: JsonObject = {
                "step_id": len(steps) + 1,
                "timestamp": timestamp,
                "source": "agent",
                "model_name": payload["model"],
                "message": _message(payload["content"]),
                "llm_call_count": 1,
                "extra": _step_extra(entry, model_starts.get(model_call_id)),
            }
            metrics = _metrics(usage)
            if metrics is not None:
                step["metrics"] = metrics
            tool_calls, observation = _tool_calls_and_observation(
                entry,
                tool_starts,
                tool_completions,
            )
            if tool_calls:
                step["tool_calls"] = tool_calls
            if observation is not None:
                step["observation"] = observation
            steps.append(step)
        elif entry.type in {"run.completed", "run.failed"}:
            terminal = entry

    for model_call_id, started in model_starts.items():
        if model_call_id in completed_model_calls:
            continue
        deltas = model_deltas.get(model_call_id, [])
        timestamp_entry = deltas[-1] if deltas else started
        timestamp, timestamp_source = _timestamp(timestamp_entry)
        started_at, started_at_source = _timestamp(started)
        steps.append(
            {
                "step_id": len(steps) + 1,
                "timestamp": timestamp,
                "source": "agent",
                "model_name": started.payload["model"],
                "message": "".join(str(delta.payload["delta"]) for delta in deltas),
                "llm_call_count": 1,
                "extra": {
                    "model_call_id": model_call_id,
                    "incomplete": True,
                    "started_at": started_at,
                    "started_at_source": started_at_source,
                    "timestamp_source": timestamp_source,
                },
            }
        )

    if not steps:
        raise AtifProjectionError("ATIF trajectory requires at least one step")
    if terminal is None:
        raise AtifProjectionError("Event Journal has no terminal event")

    terminal_timestamp, terminal_timestamp_source = _timestamp(terminal)
    terminal_payload = terminal.payload
    terminal_data: JsonObject = {
        "status": "completed" if terminal.type == "run.completed" else "failed",
        "duration_ms": terminal_payload["duration_ms"],
        "timestamp": terminal_timestamp,
        "timestamp_source": terminal_timestamp_source,
    }
    if terminal.type == "run.completed":
        terminal_data["outcome"] = terminal_payload["outcome"]
    else:
        terminal_data["error_type"] = terminal_payload["error_type"]
        terminal_data["message"] = terminal_payload["message"]

    trajectory: JsonObject = {
        "schema_version": ATIF_SCHEMA_VERSION,
        "session_id": entries[0].run_id,
        "trajectory_id": entries[0].run_id,
        "agent": {
            "name": producer["name"],
            "version": producer["version"],
            "model_name": run_payload["model"],
            "extra": {
                "mode": run_payload["mode"],
                "max_turns": run_payload["max_turns"],
            },
        },
        "steps": steps,
        "final_metrics": {"total_steps": len(steps)},
        "extra": {"terminal": terminal_data},
    }

    step_metrics = [
        step["metrics"]
        for step in steps
        if isinstance(step.get("metrics"), dict)
    ]
    llm_steps = [step for step in steps if step.get("llm_call_count") == 1]
    final_metrics = trajectory["final_metrics"]
    assert isinstance(final_metrics, dict)
    if llm_steps and len(step_metrics) == len(llm_steps):
        final_metrics["total_prompt_tokens"] = sum(
            int(metrics["prompt_tokens"]) for metrics in step_metrics
        )
        final_metrics["total_completion_tokens"] = sum(
            int(metrics["completion_tokens"]) for metrics in step_metrics
        )
        final_metrics["total_cached_tokens"] = sum(
            int(metrics["cached_tokens"]) for metrics in step_metrics
        )
    elif llm_steps:
        final_metrics["extra"] = {"usage_complete": False}
    return trajectory


def write_atif(trajectory: JsonObject, path: Path) -> None:
    """Atomically publish one owner-only ATIF JSON file without overwriting."""
    encoded = (
        json.dumps(
            trajectory,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    descriptor = -1
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        remaining = memoryview(encoded)
        while remaining:
            written = os.write(descriptor, remaining)
            if written == 0:
                raise OSError("could not write ATIF trajectory")
            remaining = remaining[written:]
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.link(temporary_path, path)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
