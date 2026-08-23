"""Behavioral tests for runtime events and the append-only Event Journal."""

import json
import stat

import pytest

from nanopycodeagent import settings
from nanopycodeagent.event_journal import EventJournal, NativeEvent


def _run_started_event():
    return NativeEvent(
        "run.started",
        {
            "mode": "headless",
            "model": "test-model",
            "max_turns": 50,
            "source_timestamp": "2026-08-23T08:00:00.000Z",
        },
    )


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
                {
                    "message_id": "user-1",
                    "content": "hello",
                    "source_timestamp": "2026-08-23T08:00:00.000Z",
                },
            )
        )
        journal.append(
            NativeEvent(
                "run.completed",
                {
                    "outcome": "completed",
                    "duration_ms": 12.5,
                    "source_timestamp": "2026-08-23T08:00:00.001Z",
                },
            )
        )

    entries = EventJournal.replay(path)

    assert [entry.seq for entry in entries] == [1, 2]
    assert [entry.type for entry in entries] == ["user.message", "run.completed"]
    assert entries[0].payload["content"] == "hello"
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


def test_default_journal_storage_restricts_the_configuration_root(
    monkeypatch, tmp_path
):
    config_root = tmp_path / "config"
    config_root.mkdir(mode=0o755)
    config_root.chmod(0o755)
    monkeypatch.setattr(settings, "SETTINGS_PATH", config_root / "settings.json")

    with EventJournal.create(
        "run-default-storage",
        clock=lambda: "2026-08-23T08:00:00.000Z",
    ) as journal:
        path = journal.path

    assert stat.S_IMODE(config_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_large_strings_are_truncated_only_in_the_persisted_entry(tmp_path):
    event = NativeEvent(
        "tool.completed",
        {
            "tool_call_id": "tool-1",
            "tool_name": "read",
            "result": "abcdefghij",
            "is_error": False,
            "duration_ms": 10,
            "source_timestamp": "2026-08-23T08:00:00.000Z",
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
        expected = journal.append(_run_started_event())
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
            journal.append(_run_started_event())


def test_replay_rejects_non_increasing_sequence_numbers(tmp_path):
    with EventJournal.create(
        "run-bad-order",
        directory=tmp_path,
        clock=lambda: "2026-08-23T08:00:00.000Z",
    ) as journal:
        first = journal.append(_run_started_event())
        path = journal.path

    duplicate = first.to_dict()
    with path.open("a", encoding="utf-8") as journal_file:
        journal_file.write(json.dumps(duplicate) + "\n")

    with pytest.raises(ValueError, match="strictly increasing seq"):
        EventJournal.replay(path)


def test_native_event_contract_rejects_missing_fields_and_untrusted_measurements():
    with pytest.raises(ValueError, match="model.completed missing required fields"):
        NativeEvent("model.completed", {})

    with pytest.raises(ValueError, match="duration_ms must be non-negative"):
        NativeEvent(
            "run.completed",
            {
                "outcome": "completed",
                "duration_ms": -1,
                "source_timestamp": "2026-08-23T08:00:00.000Z",
            },
        )

    with pytest.raises(ValueError, match="source_timestamp must be RFC 3339 UTC"):
        NativeEvent(
            "run.failed",
            {
                "error_type": "RuntimeError",
                "message": "failed",
                "duration_ms": 1,
                "source_timestamp": "yesterday",
            },
        )


def test_model_completed_contract_validates_nested_content_and_usage():
    payload = {
        "model_call_id": "model-1",
        "message_id": "message-1",
        "content": [],
        "tool_calls": [],
        "model": "test-model",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 2},
        "provider_response_id": "message-1",
        "generation_id": None,
        "duration_ms": 25,
        "source_timestamp": "2026-08-23T08:00:00.000Z",
    }

    with pytest.raises(ValueError, match="content items must be objects"):
        NativeEvent("model.completed", payload | {"content": [42]})

    with pytest.raises(ValueError, match="tool_call_id must be a non-empty string"):
        invalid_call = {"type": "tool_call", "tool_name": "read", "input": {}}
        NativeEvent(
            "model.completed",
            payload | {"content": [invalid_call], "tool_calls": [invalid_call]},
        )

    with pytest.raises(ValueError, match="usage.input_tokens must be non-negative"):
        NativeEvent(
            "model.completed",
            payload | {"usage": {"input_tokens": "10", "output_tokens": 2}},
        )

    with pytest.raises(ValueError, match="tool_calls must match content tool calls"):
        valid_call = {
            "type": "tool_call",
            "tool_call_id": "tool-1",
            "tool_name": "read",
            "input": {"path": "README.md"},
        }
        NativeEvent(
            "model.completed",
            payload | {"content": [valid_call], "tool_calls": []},
        )
