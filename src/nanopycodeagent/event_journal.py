"""Versioned runtime facts and their internal append-only Event Journal.

Journal files contain prompts, model replies, tool inputs, and tool results.
They are sensitive internal reconstruction data, not public run output or an
ATIF trajectory.
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping

from . import settings

SCHEMA_VERSION = 1
DEFAULT_MAX_STRING_CHARS = 100_000

EVENT_TYPES = frozenset(
    {
        "run.started",
        "user.message",
        "model.started",
        "model.output_delta",
        "model.completed",
        "tool.started",
        "tool.completed",
        "run.completed",
        "run.failed",
    }
)

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]
type EventSubscriber = Callable[[NativeEvent], None]

_NON_TRUNCATABLE_FIELDS = frozenset(
    {
        "error_type",
        "generation_id",
        "message_id",
        "mode",
        "model",
        "model_call_id",
        "outcome",
        "producer",
        "provider_response_id",
        "source_timestamp",
        "stop_reason",
        "tool_call_id",
        "tool_name",
    }
)

_REQUIRED_PAYLOAD_FIELDS = {
    "run.started": frozenset(
        {"mode", "model", "max_turns", "producer", "source_timestamp"}
    ),
    "user.message": frozenset({"message_id", "content", "source_timestamp"}),
    "model.started": frozenset({"model_call_id", "model", "source_timestamp"}),
    "model.output_delta": frozenset(
        {"model_call_id", "delta", "source_timestamp"}
    ),
    "model.completed": frozenset(
        {
            "model_call_id",
            "message_id",
            "content",
            "tool_calls",
            "model",
            "stop_reason",
            "usage",
            "provider_response_id",
            "generation_id",
            "duration_ms",
            "source_timestamp",
        }
    ),
    "tool.started": frozenset(
        {"tool_call_id", "tool_name", "input", "source_timestamp"}
    ),
    "tool.completed": frozenset(
        {
            "tool_call_id",
            "tool_name",
            "result",
            "is_error",
            "duration_ms",
            "source_timestamp",
        }
    ),
    "run.completed": frozenset({"outcome", "duration_ms", "source_timestamp"}),
    "run.failed": frozenset(
        {"error_type", "message", "duration_ms", "source_timestamp"}
    ),
}


def utc_now() -> str:
    """Return the current UTC time in the journal's RFC 3339 format."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_rfc3339_utc(value: str, field: str) -> None:
    if re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
        value,
    ) is None:
        raise ValueError(f"{field} must be RFC 3339 UTC")
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be RFC 3339 UTC") from exc


def _validate_recorded_at(value: str) -> None:
    _validate_rfc3339_utc(value, "Journal Entry recorded_at")


def _require_string(payload: JsonObject, field: str, event_type: str) -> str:
    value = payload[field]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{event_type}.{field} must be a non-empty string")
    return value


def _validate_tool_call(value: JsonValue, field: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ValueError(f"{field} items must be objects")
    if value.get("type") != "tool_call":
        raise ValueError(f"{field} items must have type tool_call")
    for name in ("tool_call_id", "tool_name"):
        item = value.get(name)
        if not isinstance(item, str) or not item:
            raise ValueError(f"{field}.{name} must be a non-empty string")
    if not isinstance(value.get("input"), dict):
        raise ValueError(f"{field}.input must be an object")
    return value


def _validate_model_content(content: list[JsonValue]) -> list[JsonObject]:
    tool_calls: list[JsonObject] = []
    for block in content:
        if not isinstance(block, dict):
            raise ValueError("model.completed.content items must be objects")
        block_type = block.get("type")
        if block_type == "text":
            if not isinstance(block.get("text"), str):
                raise ValueError("model.completed.content.text must be a string")
        elif block_type == "tool_call":
            tool_calls.append(
                _validate_tool_call(block, "model.completed.content")
            )
        elif block_type == "extension":
            namespace = block.get("namespace")
            if not isinstance(namespace, str) or not namespace:
                raise ValueError(
                    "model.completed.content.extension namespace must be a string"
                )
            source_type = block.get("source_type")
            if source_type is not None and not isinstance(source_type, str):
                raise ValueError(
                    "model.completed.content.extension source_type is invalid"
                )
            if "value" not in block:
                raise ValueError(
                    "model.completed.content.extension value is required"
                )
        else:
            raise ValueError(f"unsupported model content type: {block_type}")
    return tool_calls


def _validate_usage(usage: JsonObject) -> None:
    for field in ("input_tokens", "output_tokens"):
        if field not in usage:
            raise ValueError(f"model.completed.usage.{field} is required")
    for field in (
        "input_tokens",
        "output_tokens",
        "cache_read_input_tokens",
        "cache_creation_input_tokens",
    ):
        if field not in usage:
            continue
        value = usage[field]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(
                f"model.completed.usage.{field} must be non-negative"
            )


def _validate_native_payload(event_type: str, payload: JsonObject) -> None:
    required = _REQUIRED_PAYLOAD_FIELDS[event_type]
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(
            f"{event_type} missing required fields: {', '.join(missing)}"
        )
    if "timestamp_source" in payload:
        raise ValueError(f"{event_type}.timestamp_source is not supported")

    source_timestamp = payload["source_timestamp"]
    if source_timestamp is not None:
        if not isinstance(source_timestamp, str):
            raise ValueError(f"{event_type}.source_timestamp must be RFC 3339 UTC")
        _validate_rfc3339_utc(
            source_timestamp,
            f"{event_type}.source_timestamp",
        )

    for field in ("message_id", "model_call_id", "tool_call_id", "tool_name"):
        if field in payload:
            _require_string(payload, field, event_type)

    if "duration_ms" in payload:
        duration = payload["duration_ms"]
        if (
            not isinstance(duration, int | float)
            or isinstance(duration, bool)
            or duration < 0
        ):
            raise ValueError(f"{event_type}.duration_ms must be non-negative")

    if event_type == "run.started":
        if payload["mode"] not in {"interactive", "headless"}:
            raise ValueError("run.started.mode must be interactive or headless")
        _require_string(payload, "model", event_type)
        producer = payload["producer"]
        if not isinstance(producer, dict):
            raise ValueError("run.started.producer must be an object")
        for field in ("name", "version"):
            value = producer.get(field)
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"run.started.producer.{field} must be a non-empty string"
                )
        max_turns = payload["max_turns"]
        if max_turns is not None and (
            not isinstance(max_turns, int)
            or isinstance(max_turns, bool)
            or max_turns < 1
        ):
            raise ValueError("run.started.max_turns must be positive or null")
    elif event_type == "model.started":
        _require_string(payload, "model", event_type)
    elif event_type == "model.output_delta":
        if not isinstance(payload["delta"], str):
            raise ValueError("model.output_delta.delta must be a string")
    elif event_type == "model.completed":
        _require_string(payload, "model", event_type)
        if not isinstance(payload["content"], list):
            raise ValueError("model.completed.content must be a list")
        if not isinstance(payload["tool_calls"], list):
            raise ValueError("model.completed.tool_calls must be a list")
        content_tool_calls = _validate_model_content(payload["content"])
        tool_calls = [
            _validate_tool_call(item, "model.completed.tool_calls")
            for item in payload["tool_calls"]
        ]
        if tool_calls != content_tool_calls:
            raise ValueError(
                "model.completed.tool_calls must match content tool calls"
            )
        if payload["stop_reason"] is not None and not isinstance(
            payload["stop_reason"], str
        ):
            raise ValueError("model.completed.stop_reason must be a string or null")
        if payload["usage"] is not None and not isinstance(payload["usage"], dict):
            raise ValueError("model.completed.usage must be an object or null")
        if isinstance(payload["usage"], dict):
            _validate_usage(payload["usage"])
        for field in ("provider_response_id", "generation_id"):
            value = payload[field]
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"model.completed.{field} must be a string or null")
    elif event_type == "tool.started":
        if not isinstance(payload["input"], dict):
            raise ValueError("tool.started.input must be an object")
    elif event_type == "tool.completed":
        result = payload["result"]
        if result is not None and not isinstance(result, str):
            raise ValueError("tool.completed.result must be a string or null")
        if not isinstance(payload["is_error"], bool):
            raise ValueError("tool.completed.is_error must be a boolean")
        if result is None and not isinstance(payload.get("error"), dict):
            raise ValueError("tool.completed.error is required when result is null")
    elif event_type == "run.completed":
        if payload["outcome"] not in {"completed", "max_turns_exhausted"}:
            raise ValueError("run.completed.outcome is unsupported")
    elif event_type == "run.failed":
        _require_string(payload, "error_type", event_type)
        if not isinstance(payload["message"], str):
            raise ValueError("run.failed.message must be a string")

@dataclass(frozen=True, slots=True)
class NativeEvent:
    """One version-one runtime fact produced by the agent core."""

    type: str
    payload: JsonObject

    def __post_init__(self) -> None:
        if self.type not in EVENT_TYPES:
            raise ValueError(f"unsupported Native Event type: {self.type}")
        try:
            json.dumps(self.payload, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Native Event payload must be valid JSON") from exc
        _validate_native_payload(self.type, self.payload)

    def to_dict(self) -> JsonObject:
        """Return the version-one wire representation of this fact."""
        return {"type": self.type, "payload": self.payload}


class EventEmitter:
    """Send each Native Event to durable history and live projectors."""

    def __init__(
        self,
        journal: EventJournal,
        *subscribers: EventSubscriber,
    ) -> None:
        self._journal = journal
        self._subscribers = subscribers

    def emit(self, event_type: str, payload: JsonObject) -> NativeEvent:
        """Create, persist, and project one runtime fact."""
        event = NativeEvent(event_type, payload)
        self._journal.append(event)
        for subscriber in self._subscribers:
            subscriber(event)
        return event


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """A Native Event with durable identity and ordering metadata."""

    schema_version: int
    run_id: str
    seq: int
    recorded_at: str
    type: str
    payload: JsonObject
    truncation: JsonObject | None = None

    def to_dict(self) -> JsonObject:
        """Return the JSONL record representation."""
        value: JsonObject = {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "seq": self.seq,
            "recorded_at": self.recorded_at,
            "type": self.type,
            "payload": self.payload,
        }
        if self.truncation is not None:
            value["truncation"] = self.truncation
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> JournalEntry:
        """Validate and rebuild one version-one Journal Entry."""
        schema_version = value.get("schema_version")
        run_id = value.get("run_id")
        seq = value.get("seq")
        recorded_at = value.get("recorded_at")
        event_type = value.get("type")
        payload = value.get("payload")
        truncation = value.get("truncation")
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported Journal Entry schema: {schema_version}")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("Journal Entry run_id must be a non-empty string")
        if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
            raise ValueError("Journal Entry seq must be a positive integer")
        if not isinstance(recorded_at, str) or not recorded_at:
            raise ValueError("Journal Entry recorded_at must be a non-empty string")
        _validate_recorded_at(recorded_at)
        if not isinstance(event_type, str) or not isinstance(payload, dict):
            raise ValueError("Journal Entry must contain a Native Event")
        if truncation is not None and not isinstance(truncation, dict):
            raise ValueError("Journal Entry truncation must be an object")
        event = NativeEvent(event_type, payload)
        return cls(
            schema_version=schema_version,
            run_id=run_id,
            seq=seq,
            recorded_at=recorded_at,
            type=event.type,
            payload=event.payload,
            truncation=truncation,
        )


def _json_pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _truncate_strings(
    value: JsonValue,
    *,
    path: str,
    limit: int,
    fields: list[JsonObject],
) -> JsonValue:
    if isinstance(value, str):
        if len(value) <= limit:
            return value
        fields.append(
            {
                "path": path,
                "original_chars": len(value),
                "retained_chars": limit,
            }
        )
        return value[:limit]
    if isinstance(value, list):
        return [
            _truncate_strings(
                item,
                path=f"{path}/{index}",
                limit=limit,
                fields=fields,
            )
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        return {
            key: (
                item
                if key in _NON_TRUNCATABLE_FIELDS
                else _truncate_strings(
                    item,
                    path=f"{path}/{_json_pointer_part(key)}",
                    limit=limit,
                    fields=fields,
                )
            )
            for key, item in value.items()
        }
    return value


class EventJournal:
    """Append Journal Entries for one Agent Run to a sensitive JSONL file."""

    def __init__(
        self,
        *,
        path: Path,
        run_id: str,
        descriptor: int,
        clock: Callable[[], str],
        max_string_chars: int,
    ) -> None:
        self.path = path
        self.run_id = run_id
        self._descriptor = descriptor
        self._clock = clock
        self._max_string_chars = max_string_chars
        self._next_seq = 1
        self._lock = threading.Lock()

    @classmethod
    def create(
        cls,
        run_id: str,
        *,
        directory: Path | None = None,
        clock: Callable[[], str] = utc_now,
        max_string_chars: int = DEFAULT_MAX_STRING_CHARS,
    ) -> EventJournal:
        """Create a new journal file for ``run_id``."""
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id) is None:
            raise ValueError("run_id must be a safe filename component")
        if max_string_chars < 1:
            raise ValueError("max_string_chars must be positive")
        if directory is None:
            config_root = settings.SETTINGS_PATH.parent
            config_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            config_root.chmod(0o700)
            directory = config_root / "journals"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        path = directory / f"{run_id}.jsonl"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND
        flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags, 0o600)
        os.fchmod(descriptor, 0o600)
        return cls(
            path=path,
            run_id=run_id,
            descriptor=descriptor,
            clock=clock,
            max_string_chars=max_string_chars,
        )

    def append(self, event: NativeEvent) -> JournalEntry:
        """Wrap and append one runtime fact."""
        with self._lock:
            if self._descriptor < 0:
                raise ValueError("cannot append to a closed Event Journal")
            truncated_fields: list[JsonObject] = []
            payload = _truncate_strings(
                event.payload,
                path="",
                limit=self._max_string_chars,
                fields=truncated_fields,
            )
            assert isinstance(payload, dict)
            recorded_at = self._clock()
            _validate_recorded_at(recorded_at)
            entry = JournalEntry(
                schema_version=SCHEMA_VERSION,
                run_id=self.run_id,
                seq=self._next_seq,
                recorded_at=recorded_at,
                type=event.type,
                payload=payload,
                truncation={"fields": truncated_fields} if truncated_fields else None,
            )
            encoded = json.dumps(
                entry.to_dict(), ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8") + b"\n"
            remaining = memoryview(encoded)
            while remaining:
                written = os.write(self._descriptor, remaining)
                if written == 0:
                    raise OSError("could not append to Event Journal")
                remaining = remaining[written:]
            self._next_seq += 1
            return entry

    @staticmethod
    def replay(path: Path) -> list[JournalEntry]:
        """Read and validate the complete Journal Entries in ``path``."""
        entries: list[JournalEntry] = []
        with path.open("rb") as journal_file:
            for raw_line in journal_file:
                # The writer always terminates complete entries with a newline.
                # A process killed during its final write can leave one partial
                # tail; all entries before it remain independently replayable.
                if not raw_line.endswith(b"\n"):
                    break
                try:
                    value = json.loads(raw_line)
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    line_number = len(entries) + 1
                    raise ValueError(
                        f"invalid Journal Entry at line {line_number}"
                    ) from exc
                if not isinstance(value, dict):
                    raise ValueError(
                        f"invalid Journal Entry at line {len(entries) + 1}"
                    )
                entry = JournalEntry.from_dict(value)
                if entries and entry.run_id != entries[0].run_id:
                    raise ValueError("Event Journal contains more than one run_id")
                if entries and entry.seq <= entries[-1].seq:
                    raise ValueError(
                        "Event Journal entries must have strictly increasing seq"
                    )
                entries.append(entry)
        return entries

    def close(self) -> None:
        """Close the underlying journal file."""
        with self._lock:
            if self._descriptor >= 0:
                os.fsync(self._descriptor)
                os.close(self._descriptor)
                self._descriptor = -1

    def __enter__(self) -> EventJournal:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
