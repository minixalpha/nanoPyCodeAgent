"""Compatibility checks against Harbor's pinned ATIF-v1.7 validator."""

import json
from pathlib import Path

import pytest
from harbor.models.agent.context import AgentContext
from harbor.utils.trajectory_validator import TrajectoryValidator
from nanopycodeagent.atif import project_atif
from nanopycodeagent.cost import estimated_cost, usage_cost
from nanopycodeagent.event_journal import EventJournal, NativeEvent
from harbor_adapter import NanoPyCodeAgent


def test_projector_output_passes_harbor_atif_validator():
    journal_path = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    trajectory = project_atif(EventJournal.replay(journal_path))
    validator = TrajectoryValidator()

    assert validator.validate(trajectory), validator.get_errors()


@pytest.mark.parametrize("other_kind", [None, "estimated", "provider_reported", "pending"])
def test_estimated_costs_survive_projection_validation_and_harbor_context(tmp_path, other_kind):
    fixture = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    usage = {"input_tokens": 1000, "output_tokens": 1000}
    with EventJournal.create("run-estimated", directory=tmp_path) as journal:
        for entry in EventJournal.replay(fixture):
            payload = entry.payload
            if entry.type == "model.completed":
                payload = payload | {
                    "generation_id": None,
                    "cost": estimated_cost("deepseek-flash", usage),
                }
            journal.append(NativeEvent(entry.type, payload))
            if entry.type == "model.completed" and other_kind is not None:
                other_cost = {
                    "estimated": estimated_cost("deepseek-flash", usage),
                    "provider_reported": usage_cost({"cost": "0.002"}),
                    "pending": {"status": "pending", "source": "provider_generation"},
                }[other_kind]
                journal.append(NativeEvent("model.completed", payload | {
                    "model_call_id": "model-2", "generation_id": "generation-2",
                    "message_id": "msg-2", "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "done"}],
                    "tool_calls": [], "cost": other_cost,
                }))

    trajectory = project_atif(EventJournal.replay(journal.path))
    validator = TrajectoryValidator()
    assert validator.validate(trajectory), validator.get_errors()
    (tmp_path / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    context = AgentContext()
    NanoPyCodeAgent(logs_dir=tmp_path).populate_context_post_run(context)

    diagnostic = context.metadata["trajectory"]
    assert diagnostic["cost_is_estimated"] is True
    assert diagnostic["estimated_cost_usd"] == (0.003 if other_kind == "estimated" else 0.0015)
    if other_kind == "pending":
        assert context.cost_usd is None
        assert diagnostic["status"] == "partial"
        assert diagnostic["known_cost_usd"] == 0.0015
        assert diagnostic["missing_generation_ids"] == ["generation-2"]
    else:
        assert context.cost_usd == {
            None: 0.0015, "estimated": 0.003, "provider_reported": 0.0035,
        }[other_kind]
        assert diagnostic["status"] == "complete"


def test_time_budget_v4_passes_harbor_atif_validator(tmp_path):
    fixture = Path(__file__).parent / "fixtures" / "atif-journal-v1.jsonl"
    note = "[time budget] Stop investigating now. Write your best answer to the output file."
    with EventJournal.create("run-budgeted", directory=tmp_path) as journal:
        for entry in EventJournal.replay(fixture):
            if entry.type == "model.started":
                journal.append(NativeEvent("input.injected", {
                    "model_call_id": entry.payload["model_call_id"],
                    "content": note,
                    "reason": "time_budget",
                    "source_timestamp": entry.payload["source_timestamp"],
                }))
            payload = entry.payload
            if entry.type == "run.completed":
                payload = payload | {"outcome": "time_budget_exhausted"}
            journal.append(NativeEvent(entry.type, payload))

    entries = EventJournal.replay(journal.path)
    assert all(entry.schema_version == 4 for entry in entries)
    trajectory = project_atif(entries)
    validator = TrajectoryValidator()
    assert validator.validate(trajectory), validator.get_errors()
    assert trajectory["extra"]["terminal"]["outcome"] == "time_budget_exhausted"
    reminder = trajectory["steps"][1]
    assert reminder["source"] == "user"
    assert reminder["message"] == note
    assert reminder["extra"]["injected"] is True
    assert reminder["extra"]["model_call_id"] == trajectory["steps"][2]["extra"]["model_call_id"]


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
@pytest.mark.parametrize("recover", [False, True])
def test_truncated_journal_passes_harbor_atif_validator(tmp_path, content, recover):
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
                truncated_payload = payload
            elif entry.type == "run.completed":
                if recover:
                    journal.append(NativeEvent("input.injected", {
                        "model_call_id": "recovered", "content": "Continue within the remaining budget.",
                        "reason": "truncation_recovery", "source_timestamp": payload["source_timestamp"],
                    }))
                    journal.append(NativeEvent("model.started", {
                        "model_call_id": "recovered", "model": truncated_payload["model"],
                        "source_timestamp": payload["source_timestamp"],
                    }))
                    journal.append(NativeEvent("model.completed", truncated_payload | {
                        "model_call_id": "recovered", "message_id": "msg-recovered",
                        "content": [{"type": "text", "text": "done"}], "tool_calls": [],
                        "stop_reason": "end_turn",
                    }))
                payload = payload | {"outcome": "completed" if recover else "response_truncated"}
            journal.append(NativeEvent(entry.type, payload))

    trajectory = project_atif(EventJournal.replay(journal.path))
    validator = TrajectoryValidator()
    assert validator.validate(trajectory), validator.get_errors()
    assert trajectory["extra"]["terminal"]["outcome"] == ("completed" if recover else "response_truncated")
    assert "observation" not in trajectory["steps"][1]
    assert trajectory["steps"][1]["extra"]["stop_reason"] == "max_tokens"
    if recover:
        assert trajectory["steps"][2]["extra"]["reason"] == "truncation_recovery"
        assert trajectory["steps"][3]["extra"]["stop_reason"] == "end_turn"
