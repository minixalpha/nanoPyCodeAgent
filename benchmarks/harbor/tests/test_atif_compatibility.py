"""Compatibility checks against Harbor's pinned ATIF-v1.7 validator."""

from pathlib import Path

import pytest
from harbor.utils.trajectory_validator import TrajectoryValidator
from nanopycodeagent.atif import project_atif
from nanopycodeagent.event_journal import EventJournal, NativeEvent


def test_projector_output_passes_harbor_atif_validator():
    journal_path = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    trajectory = project_atif(EventJournal.replay(journal_path))
    validator = TrajectoryValidator()

    assert validator.validate(trajectory), validator.get_errors()


@pytest.mark.parametrize("resolved", [False, True])
def test_recovered_stream_v3_passes_harbor_atif_validator(tmp_path, resolved):
    fixture = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    with EventJournal.create("run-recovered", directory=tmp_path) as journal:
        for entry in EventJournal.replay(fixture):
            if entry.type == "model.started":
                journal.append(NativeEvent("model.started", entry.payload | {
                    "model_call_id": "failed-attempt",
                }))
                journal.append(NativeEvent("model.failed", {
                    "model_call_id": "failed-attempt", "error_type": "RemoteProtocolError",
                    "message": "interrupted", "generation_id": "gen-interrupted",
                    "duration_ms": 10, "will_retry": True, "retry_delay_seconds": 1,
                    "source_timestamp": entry.payload["source_timestamp"],
                }))
            if entry.type == "run.completed" and resolved:
                journal.append(NativeEvent("model.cost_resolved", {
                    "generation_id": "gen-interrupted", "amount": "0.02",
                    "currency": "USD", "source": "test",
                    "source_timestamp": entry.payload["source_timestamp"],
                }))
            journal.append(NativeEvent(entry.type, entry.payload))
    trajectory = project_atif(EventJournal.replay(journal.path))
    validator = TrajectoryValidator()
    assert validator.validate(trajectory), validator.get_errors()
    assert trajectory["steps"][1]["extra"]["incomplete"] is True
    assert trajectory["final_metrics"]["extra"]["usage_complete"] is False


@pytest.mark.parametrize("content", [
    [{"type": "text", "text": "Partial answer"}],
    [{"type": "extension", "namespace": "anthropic", "source_type": "thinking",
      "value": {"type": "thinking", "thinking": "Still analyzing", "signature": ""}}],
    [{"type": "tool_call", "tool_call_id": "call-1", "tool_name": "write", "input": {}}],
    [],
])
def test_truncated_v2_journal_passes_harbor_atif_validator(tmp_path, content):
    fixture = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    with EventJournal.create("run-truncated", directory=tmp_path) as journal:
        for entry in EventJournal.replay(fixture):
            if entry.type.startswith("tool."):
                continue
            payload = entry.payload
            if entry.type == "model.completed":
                payload = payload | {
                    "stop_reason": "max_tokens", "content": content,
                    "tool_calls": [block for block in content if block["type"] == "tool_call"],
                }
            elif entry.type == "run.completed":
                payload = payload | {"outcome": "response_truncated"}
            journal.append(NativeEvent(entry.type, payload))

    trajectory = project_atif(EventJournal.replay(journal.path))
    validator = TrajectoryValidator()
    assert validator.validate(trajectory), validator.get_errors()
    assert trajectory["extra"]["terminal"]["outcome"] == "response_truncated"
    assert "observation" not in trajectory["steps"][1]
