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

_IDENTITY_FIELDS = frozenset(
    {
        "generation_id",
        "message_id",
        "model_call_id",
        "provider_response_id",
        "tool_call_id",
        "tool_name",
    }
)


def utc_now() -> str:
    """Return the current UTC time in the journal's RFC 3339 format."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_recorded_at(value: str) -> None:
    if re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
        value,
    ) is None:
        raise ValueError("Journal Entry recorded_at must be RFC 3339 UTC")
    try:
        datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError("Journal Entry recorded_at must be RFC 3339 UTC") from exc


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
                if key in _IDENTITY_FIELDS
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
            directory = settings.SETTINGS_PATH.parent / "journals"
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
