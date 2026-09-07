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
