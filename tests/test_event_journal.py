"""Behavioral tests for runtime events and the append-only Event Journal."""

import json
import stat

import pytest

from nanopycodeagent.event_journal import EventJournal, NativeEvent


def test_journal_entry_wraps_the_native_event_with_ordering_metadata(tmp_path):
    event = NativeEvent(
        "tool.completed",
        {
            "tool_call_id": "call-read-1",
            "tool_name": "read",
            "result": "file contents",
            "is_error": False,
            "duration_ms": 330,
            "source_timestamp": None,
        },
    )

    with EventJournal.create(
        "run-123",
        directory=tmp_path,
        clock=lambda: "2026-08-23T08:00:01.420Z",
    ) as journal:
        entry = journal.append(event)

    assert event.to_dict() == {
        "type": "tool.completed",
        "payload": {
            "tool_call_id": "call-read-1",
            "tool_name": "read",
            "result": "file contents",
            "is_error": False,
            "duration_ms": 330,
            "source_timestamp": None,
        },
    }
    assert entry.to_dict() == {
        "schema_version": 1,
        "run_id": "run-123",
        "seq": 1,
        "recorded_at": "2026-08-23T08:00:01.420Z",
        "type": "tool.completed",
        "payload": event.payload,
    }

    with pytest.raises(ValueError, match="unsupported Native Event type"):
        NativeEvent("trajectory.step", {})


def test_jsonl_journal_replays_entries_in_append_order(tmp_path):
    timestamps = iter(
        ["2026-08-23T08:00:00.000Z", "2026-08-23T08:00:00.001Z"]
    )
    with EventJournal.create(
        "run-order",
        directory=tmp_path,
        clock=lambda: next(timestamps),
    ) as journal:
        path = journal.path
        journal.append(
            NativeEvent(
                "user.message",
                {"message_id": "user-1", "content": "你好"},
            )
        )
        journal.append(
            NativeEvent(
                "run.completed",
                {"outcome": "completed", "duration_ms": 12.5},
            )
        )

    entries = EventJournal.replay(path)

    assert [entry.seq for entry in entries] == [1, 2]
    assert [entry.type for entry in entries] == ["user.message", "run.completed"]
    assert entries[0].payload["content"] == "你好"
    assert path.read_bytes().count(b"\n") == 2


def test_journal_storage_is_restricted_to_the_current_user(tmp_path):
    directory = tmp_path / "journals"
    directory.mkdir(mode=0o755)
    directory.chmod(0o755)

    with EventJournal.create(
        "run-sensitive",
        directory=directory,
        clock=lambda: "2026-08-23T08:00:00.000Z",
    ) as journal:
        path = journal.path

    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_large_strings_are_truncated_only_in_the_persisted_entry(tmp_path):
    event = NativeEvent(
        "tool.completed",
        {
            "tool_call_id": "tool-1",
            "result": "abcdefghij",
            "is_error": False,
        },
    )

    with EventJournal.create(
        "run-large-output",
        directory=tmp_path,
        clock=lambda: "2026-08-23T08:00:00.000Z",
        max_string_chars=4,
    ) as journal:
        entry = journal.append(event)
        path = journal.path

    assert event.payload["result"] == "abcdefghij"
    assert entry.payload["result"] == "abcd"
    assert entry.to_dict()["truncation"] == {
        "fields": [
            {
                "path": "/result",
                "original_chars": 10,
                "retained_chars": 4,
            }
        ]
    }
    assert EventJournal.replay(path) == [entry]


def test_replay_ignores_only_a_trailing_partial_entry(tmp_path):
    with EventJournal.create(
        "run-interrupted",
        directory=tmp_path,
        clock=lambda: "2026-08-23T08:00:00.000Z",
    ) as journal:
        expected = journal.append(
            NativeEvent("run.started", {"mode": "headless"})
        )
        path = journal.path

    with path.open("ab") as journal_file:
        journal_file.write(b'{"schema_version":1,"run_id":"run-interrupted"')

    assert EventJournal.replay(path) == [expected]


def test_run_id_cannot_escape_the_journal_directory(tmp_path):
    with pytest.raises(ValueError, match="safe filename component"):
        EventJournal.create(
            "../escape",
            directory=tmp_path,
            clock=lambda: "2026-08-23T08:00:00.000Z",
        )

    assert list(tmp_path.parent.glob("escape.jsonl")) == []


def test_recorded_at_must_be_an_rfc3339_utc_timestamp(tmp_path):
    with EventJournal.create(
        "run-invalid-time",
        directory=tmp_path,
        clock=lambda: "2026-08-23 08:00:00",
    ) as journal:
        with pytest.raises(ValueError, match="recorded_at must be RFC 3339 UTC"):
            journal.append(NativeEvent("run.started", {"mode": "headless"}))


def test_replay_rejects_non_increasing_sequence_numbers(tmp_path):
    with EventJournal.create(
        "run-bad-order",
        directory=tmp_path,
        clock=lambda: "2026-08-23T08:00:00.000Z",
    ) as journal:
        first = journal.append(NativeEvent("run.started", {"mode": "headless"}))
        path = journal.path

    duplicate = first.to_dict() | {"type": "run.completed"}
    with path.open("a", encoding="utf-8") as journal_file:
        journal_file.write(json.dumps(duplicate) + "\n")

    with pytest.raises(ValueError, match="strictly increasing seq"):
        EventJournal.replay(path)
