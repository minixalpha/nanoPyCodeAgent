"""Exercise permission decisions through real tool dispatch with fake models."""

import json
from pathlib import Path

import pytest

from nanopycodeagent import agent, settings
from nanopycodeagent.event_journal import EventJournal
from nanopycodeagent.permissions import (
    REVIEW_PROMPT, authorize, extreme_risk_reason, parse_review,
)
from helpers import (
    FakeClient, FakeMessages, FakeStream, edit_tool_use_block, patch_client,
    patch_client_and_input, read_tool_use_block, text_block, tool_use_block,
    write_tool_use_block,
)


def decision(result="pass", reason="Within the requested scope."):
    return FakeStream([text_block(json.dumps({"audit_result": result, "reason": reason}))])


def entries():
    path, = (settings.SETTINGS_PATH.parent / "journals").glob("*.jsonl")
    return EventJournal.replay(path)


@pytest.mark.parametrize("value", [None, "ask", "AUTO", "", True, 1, [], {}])
def test_invalid_permission_mode_is_not_silently_full(value):
    settings.SETTINGS_PATH.write_text(json.dumps({"permission_mode": value}))
    with pytest.raises(ValueError, match="permission_mode"):
        settings.load_permission_mode()


def test_permission_mode_defaults_to_auto_and_accepts_only_documented_values():
    assert settings.load_permission_mode() == "auto"
    for mode in ("auto", "full"):
        settings.SETTINGS_PATH.write_text(json.dumps({"permission_mode": mode}))
        assert settings.load_permission_mode() == mode
    settings.SETTINGS_PATH.write_text('{"env":{}}')
    assert settings.load_permission_mode() == "auto"


@pytest.mark.parametrize("response", [
    "", "not json", "[]", "null", '"pass"',
    '{"audit_result":"pass"}',
    '{"audit_result":"allow","reason":"ok"}',
    '{"audit_result":true,"reason":"ok"}',
    '{"audit_result":"pass","reason":""}',
    '{"audit_result":"pass","reason":"   "}',
    '{"audit_result":"pass","reason":200}',
    '{"audit_result":"pass","audit_result":"not_pass","reason":"ok"}',
    '{"audit_result":"pass","reason":"ok","extra":true}',
    '```json\n{"audit_result":"pass","reason":"ok"}\n```',
])
def test_invalid_review_output_cannot_approve(response):
    with pytest.raises(ValueError):
        parse_review(response)


@pytest.mark.parametrize("result", ["pass", "not_pass"])
@pytest.mark.parametrize("reason", ["x" * 199, "x" * 200, "x" * 201, "\U0001f680" * 201], ids=["199-chars", "200-chars", "201-chars", "201-unicode-chars"])
def test_reason_length_is_bounded_without_changing_the_decision(result, reason):
    parsed = parse_review(json.dumps({"audit_result": result, "reason": reason}))
    assert parsed.allowed == (result == "pass")
    assert parsed.source == "model"
    expected = reason if len(reason) <= 200 else reason[:199] + "…"
    assert parsed.reason == expected


def test_reason_whitespace_is_normalized_before_length_limit():
    reason = "x" * 200
    parsed = parse_review(json.dumps({"audit_result": "pass", "reason": "  " + reason + "\n"}))
    assert parsed.reason == reason


@pytest.mark.parametrize("result", ["pass", "not_pass"])
def test_verbose_review_does_not_trigger_manual_approval(monkeypatch, tmp_path, result):
    # Reproduces the 216-character explanation from the first live write test.
    reason = (
        'User explicitly asked to create pass.txt containing "hello" in the '
        'working directory; the write matches that target and content (only '
        'a trailing newline added) and is a bounded, easily reversible local '
        'file creation.'
    )
    assert len(reason) == 216
    target = tmp_path / "verbose"
    messages = FakeMessages([
        FakeStream([write_tool_use_block("verbose", path=str(target), content="hello\n")], stop_reason="tool_use"),
        decision(result, reason), [text_block("done")],
    ])
    prompts = patch_client_and_input(
        monkeypatch, client=FakeClient(messages), inputs=["create it", "/exit"],
        permission_mode=None,
    )
    agent.run()
    assert prompts == ["You> ", "You> "]
    assert target.exists() == (result == "pass")
    completed = next(event for event in entries() if event.type == "tool.completed")
    permission = completed.payload["permission"]
    assert permission["source"] == "model"
    assert permission["audit_result"] == result
    assert permission["reason"] == reason[:199] + "…"
    raw_review = next(event for event in entries() if event.type == "model.completed" and event.payload.get("purpose") == "permission_review")
    assert json.loads(raw_review.payload["content"][0]["text"])["reason"] == reason


@pytest.mark.parametrize("command", [
    "rm -rf /", "rm --recursive --force '/'", "rm -rf /*",
    "rm -rf /tmp/..", "rm -rf //", "echo ok && /bin/rm -rf /",
    "echo ok\nrm -rf /", "sudo rm -rf /", "env rm -rf /",
    "bash -c 'rm -rf /'", "sh -lc 'rm -rf /'",
    "dd if=/dev/zero of=/dev/sda", "mkfs.ext4 /dev/nvme0n1p1",
])
def test_literal_catastrophic_commands_are_denied_even_in_full(command):
    def unexpected_review():
        pytest.fail("the guard must decide before model review")

    result = authorize("full", "bash", {"command": command}, unexpected_review, interactive=False)
    assert not result.allowed and result.source == "guard"


@pytest.mark.parametrize("command", [
    "echo hello", "printf '%s' 'rm -rf /'", "cat /etc/os-release",
    "rm -rf /tmp/task-build", "git diff", "mkdir /tmp/scratch",
])
def test_guard_does_not_mistake_ordinary_reads_or_quoted_examples_for_destruction(command):
    assert extreme_risk_reason("bash", {"command": command}) is None


def test_default_auto_reviews_every_tool_and_retains_previous_batch_results(monkeypatch, tmp_path):
    path = tmp_path / "output.txt"
    batch = FakeStream([
        write_tool_use_block("write", path=str(path), content="first\n"),
        read_tool_use_block("read", path=str(path)),
        edit_tool_use_block("edit", path=str(path), old_text="first", new_text="second"),
        tool_use_block("bash", "echo checked"),
    ], stop_reason="tool_use")
    messages = FakeMessages([batch, decision(), decision(), decision(), decision(), [text_block("done")]])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)

    assert agent.run_headless("Create and check the output", max_turns=2) == 0
    assert path.read_text() == "second\n"
    reviews = [kw for kw in messages.kwargs if kw["system"] == REVIEW_PROMPT]
    assert len(reviews) == 4
    for index, review in enumerate(reviews):
        assert "tools" not in review
        snapshot = json.loads(review["messages"][0]["content"])
        pending = snapshot["pending_tool_call"]
        assert pending["name"] in {"read", "write", "edit", "bash"}
        assert pending["description"] and pending["parameters"]["properties"]
        retained = snapshot["messages"][-1]["content"]
        assert len(retained) == index + 1  # no future sibling calls
        assert len(snapshot["completed_tool_results"]) == index
        assert pending["id"] == retained[-1]["id"]
        assert pending["arguments"] == retained[-1]["input"]
    results = [item for item in messages.calls[-1][-1]["content"] if item["type"] == "tool_result"]
    assert len(results) == 4
    assert all(not item["is_error"] for item in results)


def test_review_and_execution_use_frozen_arguments(monkeypatch, tmp_path):
    original = tmp_path / "original"
    replaced = tmp_path / "replaced"
    block = write_tool_use_block("frozen", path=str(original), content="reviewed")

    class MutatingMessages(FakeMessages):
        def stream(self, **kwargs):
            if kwargs["system"] == REVIEW_PROMPT:
                block.input.update(path=str(replaced), content="not reviewed")
            return super().stream(**kwargs)

    messages = MutatingMessages([
        FakeStream([block], stop_reason="tool_use"), decision(), [text_block("done")],
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    agent.run_headless("write")
    assert original.read_text() == "reviewed"
    assert not replaced.exists()


def test_invalid_tool_arguments_are_rejected_before_review(monkeypatch):
    messages = FakeMessages([
        FakeStream([read_tool_use_block("invalid")], stop_reason="tool_use"),
        [text_block("Missing a path.")],
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    agent.run_headless("read")
    assert len(messages.calls) == 2
    assert messages.calls[-1][-1]["content"][0]["is_error"]
    assert not any(kw["system"] == REVIEW_PROMPT for kw in messages.kwargs)


def test_denial_is_returned_to_main_model_without_writing_or_asking(monkeypatch, tmp_path):
    target = tmp_path / "must-not-exist"
    messages = FakeMessages([
        FakeStream([write_tool_use_block("denied", path=str(target), content="oops")], stop_reason="tool_use"),
        decision("not_pass", "The user requested analysis only."),
        [text_block("I will only analyze.")],
    ])
    prompts = patch_client_and_input(
        monkeypatch, client=FakeClient(messages), inputs=["Analyze only", "/exit"],
        permission_mode=None,
    )
    agent.run()
    assert not target.exists()
    assert prompts == ["You> ", "You> "]
    result = messages.calls[-1][-1]["content"][0]
    assert result["tool_use_id"] == "denied" and result["is_error"]
    assert "analysis only" in result["content"]
    completed = next(event for event in entries() if event.type == "tool.completed")
    assert completed.payload["permission"]["source"] == "model"
    assert completed.payload["error"]["type"] == "PermissionDenied"


@pytest.mark.parametrize("answer,allowed", [("yes", True), ("y", True), ("no", False), ("", False), (None, False)])
def test_review_failure_asks_for_exact_call_and_only_explicit_yes_executes(monkeypatch, tmp_path, answer, allowed):
    target = tmp_path / "manual"
    messages = FakeMessages([
        FakeStream([write_tool_use_block("manual", path=str(target), content="approved")], stop_reason="tool_use"),
        [text_block("invalid review JSON")], [text_block("done")],
    ])
    # An exhausted input iterator supplies EOF during manual approval.
    inputs = ["write it"] + ([] if answer is None else [answer, "/exit"])
    prompts = patch_client_and_input(
        monkeypatch, client=FakeClient(messages), inputs=inputs, permission_mode=None,
    )
    agent.run()
    assert target.exists() == allowed
    assert "Allow this tool call once? [y/N] " in prompts
    assert messages.calls[-1][-1]["content"][0]["is_error"] != allowed


def test_review_transport_failure_in_headless_never_reads_stdin_or_executes(monkeypatch, tmp_path):
    target = tmp_path / "offline"

    class OfflineReviewer(FakeMessages):
        def stream(self, **kwargs):
            if kwargs["system"] == REVIEW_PROMPT:
                raise RuntimeError("review endpoint unavailable")
            return super().stream(**kwargs)

    messages = OfflineReviewer([
        FakeStream([write_tool_use_block("offline", path=str(target), content="no")], stop_reason="tool_use"),
        [text_block("Could not obtain approval.")],
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("headless must not request input"))
    assert agent.run_headless("write it") == 0
    assert not target.exists()
    result = messages.calls[-1][-1]["content"][0]
    assert result["is_error"] and "no manual approval" in result["content"]
    failed = next(event for event in entries() if event.type == "model.failed")
    assert failed.payload["purpose"] == "permission_review"
    completed = next(event for event in entries() if event.type == "tool.completed")
    assert completed.payload["error"]["type"] == "PermissionReviewFailed"


@pytest.mark.parametrize("stop_reason", ["max_tokens", "tool_use"])
def test_incomplete_review_cannot_allow_even_with_pass_json(monkeypatch, tmp_path, stop_reason):
    path = tmp_path / "truncated"
    review = decision()
    review._stop_reason = stop_reason
    messages = FakeMessages([
        FakeStream([write_tool_use_block("truncated", path=str(path), content="no")], stop_reason="tool_use"),
        review, [text_block("done")],
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    agent.run_headless("write it")
    assert not path.exists()
    assert "Review failed" in messages.calls[-1][-1]["content"][0]["content"]


def test_full_skips_review_but_still_blocks_literal_root_deletion(monkeypatch, tmp_path):
    settings.SETTINGS_PATH.write_text('{"permission_mode":"full"}')
    target = tmp_path / "full"
    messages = FakeMessages([
        FakeStream([
            write_tool_use_block("safe", path=str(target), content="ok"),
            tool_use_block("unsafe", "rm -rf /"),
        ], stop_reason="tool_use"), [text_block("done")],
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    monkeypatch.setattr(agent, "run_bash", lambda *a, **k: pytest.fail("destructive command reached executor"))
    agent.run_headless("work")
    assert target.read_text() == "ok" and len(messages.calls) == 2
    assert messages.calls[-1][-1]["content"][1]["is_error"]


def test_mode_is_fixed_across_exchanges_and_earlier_user_constraints_are_retained(monkeypatch):
    class ChangeSettings(FakeMessages):
        def stream(self, **kwargs):
            if len(self.calls) == 0:
                settings.SETTINGS_PATH.write_text('{"permission_mode":"full"}')
            return super().stream(**kwargs)

    messages = ChangeSettings([
        [text_block("Understood.")],
        FakeStream([tool_use_block("next", "echo ok")], stop_reason="tool_use"),
        decision(), [text_block("done")],
    ])
    patch_client_and_input(
        monkeypatch, client=FakeClient(messages), inputs=["Do not push", "continue", "/exit"],
        permission_mode=None,
    )
    agent.run()
    review, = [kw for kw in messages.kwargs if kw["system"] == REVIEW_PROMPT]
    snapshot = json.loads(review["messages"][0]["content"])
    assert snapshot["messages"][0] == {"role": "user", "content": "Do not push"}


def test_review_usage_and_permission_outcomes_survive_atif(monkeypatch, tmp_path):
    usage = {"input_tokens": 10, "output_tokens": 5, "cost": 0.01}
    review = decision()
    review._usage = usage
    messages = FakeMessages([
        FakeStream([tool_use_block("cost", "echo ok")], stop_reason="tool_use", usage=usage),
        review, FakeStream([text_block("done")], usage=usage),
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    trajectory = tmp_path / "trajectory.json"
    agent.run_headless("check", trajectory_path=trajectory)
    data = json.loads(trajectory.read_text())
    assert data["final_metrics"]["total_prompt_tokens"] == 30
    assert data["final_metrics"]["total_completion_tokens"] == 15
    assert data["final_metrics"]["total_cost_usd"] == pytest.approx(0.03)
    step, = [step for step in data["steps"] if step["extra"].get("purpose") == "permission_review"]
    assert step["extra"]["reviewed_tool_call_id"] == "cost"
    tool_step = next(step for step in data["steps"] if step.get("tool_calls"))
    assert tool_step["observation"]["results"][0]["extra"]["permission"]["audit_result"] == "pass"


def test_review_time_counts_toward_task_deadline(monkeypatch, tmp_path):
    from test_time_budget import FakeTime

    clock = FakeTime()
    monkeypatch.setattr(agent, "time", clock)
    target = tmp_path / "expired"

    class SlowReview(FakeMessages):
        def stream(self, **kwargs):
            if kwargs["system"] == REVIEW_PROMPT:
                clock.advance(11)
            return super().stream(**kwargs)

    messages = SlowReview([
        FakeStream([write_tool_use_block("deadline", path=str(target), content="no")], stop_reason="tool_use"),
        decision(),
    ])
    patch_client(monkeypatch, FakeClient(messages), permission_mode=None)
    agent.run_headless("write", time_budget_seconds=10)
    assert not target.exists()
    assert entries()[-1].payload["outcome"] == "time_budget_exhausted"


def test_runtime_review_prompt_matches_english_development_notes():
    notes = (Path(__file__).parents[1] / "docs/dev_notes/en/0.11.0.md").read_text()
    assert notes.split("```text\n", 1)[1].split("\n```", 1)[0] == REVIEW_PROMPT


def test_real_sdk_routes_review_separately_and_returns_denial(monkeypatch):
    import anthropic
    from helpers import sdk_http_module

    http = sdk_http_module()
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        first = len(requests) == 1
        is_review = payload["system"] == REVIEW_PROMPT
        if first:
            content = {"type": "tool_use", "id": "real-sdk", "name": "bash", "input": {"command": "echo forbidden"}}
        else:
            content = {"type": "text", "text": json.dumps({"audit_result": "not_pass", "reason": "Not authorized."}) if is_review else "I will not execute it."}
        events = [
            {"type": "message_start", "message": {
                "id": f"msg-{len(requests)}", "type": "message", "role": "assistant",
                "model": "test-model", "content": [], "stop_reason": None,
                "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0},
            }},
            {"type": "content_block_start", "index": 0, "content_block": content},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use" if first else "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 20}},
            {"type": "message_stop"},
        ]
        wire = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
        return http.Response(200, headers={"content-type": "text/event-stream"}, content=wire)

    monkeypatch.setattr(agent, "run_bash", lambda *a, **kw: pytest.fail("denied call executed"))
    with anthropic.Anthropic(
        api_key="test", base_url="https://example.test",
        http_client=http.Client(transport=http.MockTransport(respond)),
    ) as client:
        patch_client(monkeypatch, client, permission_mode=None)
        assert agent.run_headless("analyze", max_turns=2) == 0
    assert len(requests) == 3
    assert requests[1]["system"] == REVIEW_PROMPT and "tools" not in requests[1]
    result = requests[2]["messages"][-1]["content"][0]
    assert result["tool_use_id"] == "real-sdk" and result["is_error"]
