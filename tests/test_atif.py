"""ATIF-v1.7 projection tests at the Event Journal boundary."""

import json
import stat
from pathlib import Path

import pytest

from nanopycodeagent.atif import project_atif, write_atif
from nanopycodeagent.event_journal import EventJournal, JournalEntry, NativeEvent


TIMESTAMPS = [
    "2026-08-26T08:00:00.001Z",
    "2026-08-26T08:00:00.002Z",
    "2026-08-26T08:00:00.003Z",
    "2026-08-26T08:00:00.004Z",
    "2026-08-26T08:00:00.005Z",
]


def _journal_entries(tmp_path: Path) -> list[JournalEntry]:
    timestamps = iter(TIMESTAMPS)
    with EventJournal.create(
        "run-atif-1",
        directory=tmp_path,
        clock=lambda: next(timestamps),
    ) as journal:
        journal.append(
            NativeEvent(
                "run.started",
                {
                    "mode": "headless",
                    "model": "requested-model",
                    "max_turns": 50,
                    "producer": {"name": "nanoPyCodeAgent", "version": "0.8.0"},
                    "source_timestamp": "2026-08-26T08:00:00.000Z",
                },
            )
        )
        journal.append(
            NativeEvent(
                "user.message",
                {
                    "message_id": "user-1",
                    "content": "fix it",
                    "source_timestamp": "2026-08-26T08:00:00.010Z",
                },
            )
        )
        journal.append(
            NativeEvent(
                "model.started",
                {
                    "model_call_id": "model-1",
                    "model": "requested-model",
                    "source_timestamp": "2026-08-26T08:00:00.020Z",
                },
            )
        )
        journal.append(
            NativeEvent(
                "model.completed",
                {
                    "model_call_id": "model-1",
                    "message_id": "msg-1",
                    "content": [
                        {"type": "text", "text": "done"},
                        {
                            "type": "extension",
                            "namespace": "anthropic",
                            "source_type": "thinking",
                            "value": {"signature": "opaque"},
                        },
                    ],
                    "tool_calls": [],
                    "model": "actual-model",
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 3,
                        "cache_read_input_tokens": 5,
                        "cache_creation_input_tokens": 2,
                    },
                    "provider_response_id": "provider-1",
                    "generation_id": "generation-1",
                    "duration_ms": 20,
                    "source_timestamp": "2026-08-26T08:00:00.030Z",
                },
            )
        )
        journal.append(
            NativeEvent(
                "run.completed",
                {
                    "outcome": "completed",
                    "duration_ms": 40,
                    "source_timestamp": "2026-08-26T08:00:00.040Z",
                },
            )
        )
    return EventJournal.replay(tmp_path / "run-atif-1.jsonl")


def test_completed_journal_projects_atif_user_model_usage_and_terminal_state(
    tmp_path,
):
    assert project_atif(_journal_entries(tmp_path)) == {
        "schema_version": "ATIF-v1.7",
        "session_id": "run-atif-1",
        "trajectory_id": "run-atif-1",
        "agent": {
            "name": "nanoPyCodeAgent",
            "version": "0.8.0",
            "model_name": "requested-model",
            "extra": {"mode": "headless", "max_turns": 50},
        },
        "steps": [
            {
                "step_id": 1,
                "timestamp": "2026-08-26T08:00:00.010Z",
                "source": "user",
                "message": "fix it",
                "extra": {
                    "message_id": "user-1",
                    "timestamp_source": "source_timestamp",
                },
            },
            {
                "step_id": 2,
                "timestamp": "2026-08-26T08:00:00.030Z",
                "source": "agent",
                "model_name": "actual-model",
                "message": "done",
                "metrics": {
                    "prompt_tokens": 19,
                    "completion_tokens": 3,
                    "cached_tokens": 5,
                    "extra": {"cache_creation_input_tokens": 2},
                },
                "llm_call_count": 1,
                "extra": {
                    "model_call_id": "model-1",
                    "message_id": "msg-1",
                    "provider_response_id": "provider-1",
                    "generation_id": "generation-1",
                    "stop_reason": "end_turn",
                    "duration_ms": 20,
                    "content_extensions": [
                        {
                            "type": "extension",
                            "namespace": "anthropic",
                            "source_type": "thinking",
                            "value": {"signature": "opaque"},
                        }
                    ],
                    "started_at": "2026-08-26T08:00:00.020Z",
                    "started_at_source": "source_timestamp",
                    "timestamp_source": "source_timestamp",
                },
            },
        ],
        "final_metrics": {
            "total_prompt_tokens": 19,
            "total_completion_tokens": 3,
            "total_cached_tokens": 5,
            "total_steps": 2,
        },
        "extra": {
            "terminal": {
                "status": "completed",
                "outcome": "completed",
                "duration_ms": 40,
                "timestamp": "2026-08-26T08:00:00.040Z",
                "timestamp_source": "source_timestamp",
            }
        },
    }


def test_resolved_and_missing_costs_project_as_partial_metrics(tmp_path):
    entries = _journal_entries(tmp_path)
    completed = next(entry for entry in entries if entry.type == "model.completed")
    completed.payload["cost"] = {
        "status": "pending",
        "source": "provider_generation",
    }
    terminal = entries.pop()
    entries.append(
        JournalEntry(
            schema_version=1,
            run_id=completed.run_id,
            seq=terminal.seq,
            recorded_at=terminal.recorded_at,
            type="model.cost_resolved",
            payload={
                "generation_id": "generation-1",
                "amount": "0.00072",
                "currency": "USD",
                "source": "provider_generation.total_cost",
                "source_timestamp": terminal.payload["source_timestamp"],
            },
        )
    )
    entries.append(
        JournalEntry(
            schema_version=1,
            run_id=terminal.run_id,
            seq=terminal.seq + 1,
            recorded_at=terminal.recorded_at,
            type=terminal.type,
            payload=terminal.payload,
        )
    )

    trajectory = project_atif(entries)
    assert trajectory["steps"][1]["metrics"]["cost_usd"] == 0.00072
    assert trajectory["steps"][1]["metrics"]["extra"] == {
        "cache_creation_input_tokens": 2,
        "cost_source": "provider_generation.total_cost",
        "generation_id": "generation-1",
    }
    assert trajectory["final_metrics"]["total_cost_usd"] == 0.00072


def test_cost_reconciliation_diagnostics_project_to_terminal_extra(tmp_path):
    entries = _journal_entries(tmp_path)
    entries[-1].payload["cost_reconciliation"] = [
        {
            "generation_id": "generation-1",
            "status": "unresolved",
            "attempts": [
                {"attempt": 1, "status": "http_error", "http_status": 404}
            ],
        }
    ]

    assert project_atif(entries)["extra"]["terminal"]["cost_reconciliation"] == [
        {
            "generation_id": "generation-1",
            "status": "unresolved",
            "attempts": [
                {"attempt": 1, "status": "http_error", "http_status": 404}
            ],
        }
    ]


def test_tool_lifecycle_is_folded_into_the_originating_agent_step(tmp_path):
    recorded_at = iter(
        [f"2026-08-26T09:00:00.00{index}Z" for index in range(1, 8)]
    )
    with EventJournal.create(
        "run-atif-tool",
        directory=tmp_path,
        clock=lambda: next(recorded_at),
    ) as journal:
        events = [
            NativeEvent(
                "run.started",
                {
                    "mode": "headless",
                    "model": "model-a",
                    "max_turns": 5,
                    "producer": {"name": "nanoPyCodeAgent", "version": "0.8.0"},
                    "source_timestamp": "2026-08-26T09:00:00.000Z",
                },
            ),
            NativeEvent(
                "user.message",
                {
                    "message_id": "user-tool",
                    "content": "read it",
                    "source_timestamp": "2026-08-26T09:00:00.010Z",
                },
            ),
            NativeEvent(
                "model.started",
                {
                    "model_call_id": "model-tool",
                    "model": "model-a",
                    "source_timestamp": "2026-08-26T09:00:00.020Z",
                },
            ),
            NativeEvent(
                "model.completed",
                {
                    "model_call_id": "model-tool",
                    "message_id": "msg-tool",
                    "content": [
                        {"type": "text", "text": "checking"},
                        {
                            "type": "tool_call",
                            "tool_call_id": "call-read",
                            "tool_name": "read",
                            "input": {"path": "README.md"},
                        },
                    ],
                    "tool_calls": [
                        {
                            "type": "tool_call",
                            "tool_call_id": "call-read",
                            "tool_name": "read",
                            "input": {"path": "README.md"},
                        }
                    ],
                    "model": "model-a",
                    "stop_reason": "tool_use",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "service_tier": "standard",
                    },
                    "provider_response_id": "msg-tool",
                    "generation_id": None,
                    "duration_ms": 15,
                    "source_timestamp": "2026-08-26T09:00:00.030Z",
                },
            ),
            NativeEvent(
                "tool.started",
                {
                    "model_call_id": "model-tool",
                    "tool_call_id": "call-read",
                    "tool_name": "read",
                    "input": {"path": "README.md"},
                    "source_timestamp": None,
                },
            ),
            NativeEvent(
                "tool.completed",
                {
                    "model_call_id": "model-tool",
                    "tool_call_id": "call-read",
                    "tool_name": "read",
                    "result": "contents",
                    "is_error": False,
                    "duration_ms": 4,
                    "source_timestamp": None,
                },
            ),
            NativeEvent(
                "run.completed",
                {
                    "outcome": "completed",
                    "duration_ms": 30,
                    "source_timestamp": "2026-08-26T09:00:00.060Z",
                },
            ),
        ]
        for event in events:
            journal.append(event)

    entries = EventJournal.replay(tmp_path / "run-atif-tool.jsonl")
    agent_step = project_atif(entries)["steps"][1]

    assert agent_step == {
        "step_id": 2,
        "timestamp": "2026-08-26T09:00:00.030Z",
        "source": "agent",
        "model_name": "model-a",
        "message": "checking",
        "tool_calls": [
            {
                "tool_call_id": "call-read",
                "function_name": "read",
                "arguments": {"path": "README.md"},
                "extra": {
                    "started_at": "2026-08-26T09:00:00.005Z",
                    "timestamp_source": "recorded_at",
                },
            }
        ],
        "observation": {
            "results": [
                {
                    "source_call_id": "call-read",
                    "content": "contents",
                    "extra": {
                        "is_error": False,
                        "duration_ms": 4,
                        "timestamp": "2026-08-26T09:00:00.006Z",
                        "timestamp_source": "recorded_at",
                    },
                }
            ]
        },
        "metrics": {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "cached_tokens": 0,
            "extra": {"provider_usage": {"service_tier": "standard"}},
        },
        "llm_call_count": 1,
        "extra": {
            "model_call_id": "model-tool",
            "message_id": "msg-tool",
            "provider_response_id": "msg-tool",
            "generation_id": None,
            "stop_reason": "tool_use",
            "duration_ms": 15,
            "started_at": "2026-08-26T09:00:00.020Z",
            "started_at_source": "source_timestamp",
            "timestamp_source": "source_timestamp",
        },
    }


def test_projection_preserves_journal_truncation_metadata(tmp_path):
    recorded_at = iter(
        [f"2026-08-26T09:30:00.00{index}Z" for index in range(1, 8)]
    )
    with EventJournal.create(
        "run-atif-truncated",
        directory=tmp_path,
        clock=lambda: next(recorded_at),
        max_string_chars=4,
    ) as journal:
        events = [
            NativeEvent(
                "run.started",
                {
                    "mode": "headless",
                    "model": "model-a",
                    "max_turns": 5,
                    "producer": {"name": "nanoPyCodeAgent", "version": "0.8.0"},
                    "source_timestamp": "2026-08-26T09:30:00.000Z",
                },
            ),
            NativeEvent(
                "user.message",
                {
                    "message_id": "user-truncated",
                    "content": "abcdefghij",
                    "source_timestamp": "2026-08-26T09:30:00.010Z",
                },
            ),
            NativeEvent(
                "model.started",
                {
                    "model_call_id": "model-truncated",
                    "model": "model-a",
                    "source_timestamp": "2026-08-26T09:30:00.020Z",
                },
            ),
            NativeEvent(
                "model.completed",
                {
                    "model_call_id": "model-truncated",
                    "message_id": "message-truncated",
                    "content": [
                        {"type": "text", "text": "klmnopqrst"},
                        {
                            "type": "tool_call",
                            "tool_call_id": "tool-truncated",
                            "tool_name": "read",
                            "input": {"path": "uvwxyzabcd"},
                        },
                    ],
                    "tool_calls": [
                        {
                            "type": "tool_call",
                            "tool_call_id": "tool-truncated",
                            "tool_name": "read",
                            "input": {"path": "uvwxyzabcd"},
                        }
                    ],
                    "model": "model-a",
                    "stop_reason": "tool_use",
                    "usage": None,
                    "provider_response_id": "provider-truncated",
                    "generation_id": None,
                    "duration_ms": 10,
                    "source_timestamp": "2026-08-26T09:30:00.030Z",
                },
            ),
            NativeEvent(
                "tool.started",
                {
                    "model_call_id": "model-truncated",
                    "tool_call_id": "tool-truncated",
                    "tool_name": "read",
                    "input": {"path": "uvwxyzabcd"},
                    "source_timestamp": "2026-08-26T09:30:00.040Z",
                },
            ),
            NativeEvent(
                "tool.completed",
                {
                    "model_call_id": "model-truncated",
                    "tool_call_id": "tool-truncated",
                    "tool_name": "read",
                    "result": "0123456789",
                    "is_error": False,
                    "duration_ms": 5,
                    "source_timestamp": "2026-08-26T09:30:00.050Z",
                },
            ),
            NativeEvent(
                "run.completed",
                {
                    "outcome": "completed",
                    "duration_ms": 20,
                    "source_timestamp": "2026-08-26T09:30:00.060Z",
                },
            ),
        ]
        for event in events:
            journal.append(event)

    trajectory = project_atif(
        EventJournal.replay(tmp_path / "run-atif-truncated.jsonl")
    )
    user_step, agent_step = trajectory["steps"]
    assert user_step["message"] == "abcd"
    assert user_step["extra"]["journal_truncation"] == {
        "fields": [
            {"path": "/content", "original_chars": 10, "retained_chars": 4}
        ]
    }
    assert agent_step["message"] == "klmn"
    assert agent_step["extra"]["journal_truncation"] == {
        "fields": [
            {
                "path": "/content/0/text",
                "original_chars": 10,
                "retained_chars": 4,
            },
            {
                "path": "/content/1/input/path",
                "original_chars": 10,
                "retained_chars": 4,
            },
        ]
    }
    tool_call = agent_step["tool_calls"][0]
    assert tool_call["arguments"] == {"path": "uvwx"}
    assert tool_call["extra"]["journal_truncation"] == {
        "fields": [
            {
                "path": "/tool_calls/0/input/path",
                "original_chars": 10,
                "retained_chars": 4,
            }
        ]
    }
    result = agent_step["observation"]["results"][0]
    assert result["content"] == "0123"
    assert result["extra"]["journal_truncation"] == {
        "fields": [
            {"path": "/result", "original_chars": 10, "retained_chars": 4}
        ]
    }


def test_atif_file_is_owner_only_complete_json_and_never_overwrites(tmp_path):
    trajectory_path = tmp_path / "trajectory.json"
    expected = project_atif(_journal_entries(tmp_path))

    write_atif(expected, trajectory_path)

    assert json.loads(trajectory_path.read_text(encoding="utf-8")) == expected
    assert stat.S_IMODE(trajectory_path.stat().st_mode) == 0o600

    trajectory_path.write_text("keep me", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_atif(expected, trajectory_path)
    assert trajectory_path.read_text(encoding="utf-8") == "keep me"
