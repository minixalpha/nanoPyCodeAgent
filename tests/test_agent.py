"""Tests for the agent loop: startup, streaming, tool dispatch, and recovery.

Every Anthropic API access is mocked, so these tests never hit the network and
never spend tokens. We drive ``run()`` by scripting ``input()`` and the client,
then assert on captured stdout and the recorded calls.
"""

from types import SimpleNamespace

import anthropic
import httpx

from nanopycodeagent import agent

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
    api_request,
    patch_client_and_input,
    text_block,
    tool_use_block,
)


def test_missing_credentials_exits_early(monkeypatch, capsys):
    messages = FakeMessages([])
    client = FakeClient(messages, api_key=None, auth_token=None)
    patch_client_and_input(monkeypatch, client=client, inputs=[])

    agent.run()

    out = capsys.readouterr().out
    assert "No API credentials found." in out
    # Third-party / proxy users are told how to point the SDK at their endpoint.
    assert "ANTHROPIC_BASE_URL" in out
    assert "Bye!" not in out  # returned before entering the loop
    assert messages.calls == []


def test_startup_message_shows_default_model(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    # With credentials configured, the banner names the default model in use.
    assert agent.DEFAULT_MODEL in out


def test_model_can_be_overridden_via_env(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    reply = [text_block("ok")]
    messages = FakeMessages([reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "claude-opus-4-8" in out  # banner reflects the configured model
    assert messages.kwargs[0]["model"] == "claude-opus-4-8"  # and it reaches the API


def test_blank_model_env_falls_back_to_default(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_MODEL", "   ")  # empty / whitespace-only
    reply = [text_block("ok")]
    messages = FakeMessages([reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    assert messages.kwargs[0]["model"] == agent.DEFAULT_MODEL


def test_startup_message_labels_explicit_default_model_as_configured(monkeypatch, capsys):
    # Explicitly pinning the model to the default value is still reported as a
    # configured override, not as the fallback.
    monkeypatch.setenv("ANTHROPIC_MODEL", agent.DEFAULT_MODEL)
    messages = FakeMessages([[text_block("ok")]])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "from ANTHROPIC_MODEL" in out
    assert "using default model" not in out


def test_exit_command_quits_without_api_call(monkeypatch, capsys):
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Bye!" in out
    assert messages.calls == []  # /exit never reaches the API


def test_single_turn_prints_reply(monkeypatch, capsys):
    reply = [text_block("Hi there")]
    messages = FakeMessages([reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Hi there" in out  # reply text was printed
    assert "Bye!" in out
    assert len(messages.calls) == 1
    assert messages.calls[0] == [{"role": "user", "content": "hello"}]


def test_multi_turn_accumulates_history(monkeypatch, capsys):
    reply1 = [text_block("Nice to meet you, Alice.")]
    reply2 = [text_block("Your name is Alice.")]
    messages = FakeMessages([reply1, reply2])
    client = FakeClient(messages)
    patch_client_and_input(
        monkeypatch, client=client, inputs=["I'm Alice", "What's my name?", "/exit"]
    )

    agent.run()

    assert len(messages.calls) == 2
    # First call carries only the first user turn.
    assert messages.calls[0] == [{"role": "user", "content": "I'm Alice"}]
    # Second call carries the full prior history plus the new question.
    assert messages.calls[1] == [
        {"role": "user", "content": "I'm Alice"},
        {"role": "assistant", "content": reply1},
        {"role": "user", "content": "What's my name?"},
    ]


def test_blank_input_is_skipped(monkeypatch, capsys):
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["", "   ", "/exit"])

    agent.run()

    assert messages.calls == []  # blank / whitespace lines never reach the API


def test_authentication_error_breaks_loop(monkeypatch, capsys):
    err = anthropic.AuthenticationError(
        "unauthorized", response=httpx.Response(401, request=api_request()), body=None
    )
    messages = FakeMessages([err])
    client = FakeClient(messages)
    # The second input is provided but must never be read (the loop breaks).
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "should be ignored"])

    agent.run()

    out = capsys.readouterr().out
    assert "Authentication failed." in out
    assert "Bye!" in out
    assert len(messages.calls) == 1  # broke right after the failed call


def test_api_error_drops_turn_and_continues(monkeypatch, capsys):
    conn_err = anthropic.APIConnectionError(request=api_request())
    reply = [text_block("ok now")]
    messages = FakeMessages([conn_err, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 2
    # First (failed) call saw the "fails" turn.
    assert messages.calls[0] == [{"role": "user", "content": "fails"}]
    # That turn was popped on error, so the next call's history is clean.
    assert messages.calls[1] == [{"role": "user", "content": "hello"}]


def test_keyboard_interrupt_during_request_cancels_turn_only(monkeypatch, capsys):
    # Ctrl-C while waiting on the model reply cancels just that turn: the
    # prompt is rolled back and the session keeps going.
    reply = [text_block("ok now")]
    messages = FakeMessages([KeyboardInterrupt(), reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "again", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Interrupted" in out
    assert "Bye!" in out  # the session survived until /exit
    assert len(messages.calls) == 2
    # The cancelled turn left no trace in the next call's history.
    assert messages.calls[1] == [{"role": "user", "content": "again"}]


def test_keyboard_interrupt_mid_stream_cancels_turn_only(monkeypatch, capsys):
    # Ctrl-C after part of the reply has already streamed cancels the turn
    # cleanly and returns to the prompt.
    stream = FakeStream([text_block("partial")], mid_stream_error=KeyboardInterrupt())
    reply = [text_block("ok now")]
    messages = FakeMessages([stream, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "again", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "partial" in out  # the streamed text made it out before the interrupt
    assert "Interrupted" in out
    assert "Bye!" in out
    assert len(messages.calls) == 2
    assert messages.calls[1] == [{"role": "user", "content": "again"}]


def test_keyboard_interrupt_during_tool_run_repairs_history_and_continues(
    monkeypatch, capsys
):
    # Ctrl-C while a bash command runs: the tool_use reply is already in
    # history, so it must gain an error tool_result (or the API rejects every
    # later request), and the session returns to the prompt instead of dying.
    tool_turn = FakeStream(
        [tool_use_block("tu_1", "sleep 100")], stop_reason="tool_use"
    )
    reply = [text_block("ok now")]
    messages = FakeMessages([tool_turn, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["go", "next", "/exit"])

    def _interrupt(command):
        raise KeyboardInterrupt

    monkeypatch.setattr(agent, "run_bash", _interrupt)

    agent.run()

    out = capsys.readouterr().out
    assert "Interrupted" in out
    assert "Bye!" in out
    assert len(messages.calls) == 2
    # The interrupted exchange stays, with the dangling tool_use answered.
    history = messages.calls[1]
    assert history[1] == {"role": "assistant", "content": tool_turn._content}
    (result,) = history[2]["content"]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tu_1"
    assert result["is_error"] is True
    assert history[3] == {"role": "user", "content": "next"}


def test_api_error_mid_stream_drops_turn_and_continues(monkeypatch, capsys):
    # An SDK error surfacing mid-stream (e.g. an SSE error event) is handled
    # the same as one raised at request time: drop the turn and keep going.
    err = anthropic.APIConnectionError(request=api_request())
    stream = FakeStream([text_block("partial")], mid_stream_error=err)
    reply = [text_block("ok now")]
    messages = FakeMessages([stream, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 2
    # The failed turn was popped, so the next call's history is clean.
    assert messages.calls[1] == [{"role": "user", "content": "hello"}]


def test_tool_echo_is_sanitized_but_the_model_sees_raw_output(capsys):
    # Display is sanitized; the tool_result content keeps the real bytes so
    # the model works with what the command actually produced.
    block = tool_use_block("tu_1", "printf 'a\\rb\\033[2K'")

    output, is_error = agent._run_one_tool(block)

    out = capsys.readouterr().out
    assert "\r" not in out and "\x1b" not in out
    assert "\r" in output and "\x1b" in output
    assert is_error is False


def test_tool_use_turn_runs_bash_and_feeds_result_back(monkeypatch, capsys):
    # First reply asks to run a command; the second one answers with text.
    tool_turn = FakeStream(
        [text_block("Let me check."), tool_use_block("tu_1", "echo hello")],
        stop_reason="tool_use",
    )
    final = [text_block("It printed hello.")]
    messages = FakeMessages([tool_turn, final])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["run echo", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "[bash]$ echo hello" in out  # the command was echoed to the user
    assert "hello" in out  # and so was its output
    assert "It printed hello." in out
    assert len(messages.calls) == 2
    # The bash tool is offered on every request.
    assert messages.kwargs[0]["tools"] == [agent.BASH_TOOL]
    # The second call carries the tool_use turn plus a matching tool_result.
    assert messages.calls[1][-2] == {"role": "assistant", "content": tool_turn._content}
    assert messages.calls[1][-1] == {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "tu_1",
                "content": "hello",
                "is_error": False,
            }
        ],
    }


def test_tool_use_turn_runs_multiple_tool_calls(monkeypatch, capsys):
    tool_turn = FakeStream(
        [tool_use_block("tu_1", "echo one"), tool_use_block("tu_2", "echo two")],
        stop_reason="tool_use",
    )
    final = [text_block("done")]
    messages = FakeMessages([tool_turn, final])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["go", "/exit"])

    agent.run()

    results = messages.calls[1][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["tu_1", "tu_2"]
    assert [r["content"] for r in results] == ["one", "two"]


def test_unknown_tool_returns_error_result(monkeypatch, capsys):
    # A tool name we never registered comes back as an error result instead of
    # crashing the loop, so the model can see the problem and recover.
    tool_turn = FakeStream(
        [tool_use_block("tu_1", "whatever", name="python")], stop_reason="tool_use"
    )
    final = [text_block("ok")]
    messages = FakeMessages([tool_turn, final])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["go", "/exit"])

    agent.run()

    (result,) = messages.calls[1][-1]["content"]
    assert result["is_error"] is True
    assert "Unknown tool: python" in result["content"]


def test_bash_tool_with_invalid_input_returns_error_result(monkeypatch, capsys):
    # A tool_use block without a usable 'command' string becomes an error
    # result; nothing is executed.
    bad_block = SimpleNamespace(type="tool_use", id="tu_1", name="bash", input={})
    tool_turn = FakeStream([bad_block], stop_reason="tool_use")
    final = [text_block("ok")]
    messages = FakeMessages([tool_turn, final])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["go", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "[bash]$" not in out  # nothing ran
    (result,) = messages.calls[1][-1]["content"]
    assert result["is_error"] is True
    assert "'command'" in result["content"]


def test_max_tokens_truncated_tool_call_is_not_run_and_history_stays_valid(
    monkeypatch, capsys
):
    # A reply that hits the token limit mid-tool-call still carries tool_use
    # blocks. They must not be executed (the command may be cut off), but each
    # one needs an error tool_result in history — otherwise the API rejects
    # every later request and the session is unrecoverable.
    truncated = FakeStream(
        [text_block("Let me check."), tool_use_block("tu_1", "echo hi")],
        stop_reason="max_tokens",
    )
    reply = [text_block("second turn ok")]
    messages = FakeMessages([truncated, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["go", "again", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "[bash]$" not in out  # the truncated tool call never ran
    assert "truncated" in out  # and the user was told why the turn stopped
    assert len(messages.calls) == 2  # the turn ended; no automatic retry
    # The next turn's history pairs the dangling tool_use with an error result.
    history = messages.calls[1]
    assert history[1] == {"role": "assistant", "content": truncated._content}
    (result,) = history[2]["content"]
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "tu_1"
    assert result["is_error"] is True
    assert history[3] == {"role": "user", "content": "again"}


def test_tool_loop_stops_at_the_per_turn_request_budget(monkeypatch, capsys):
    # A model that keeps asking for tools must not loop forever: after the
    # per-turn request budget the agent returns to the prompt with a valid
    # history (the last tool_use has its tool_result) instead of burning
    # tokens until Ctrl-C. The script only covers the budgeted calls, so one
    # request too many would fail loudly.
    monkeypatch.setattr(agent, "MAX_REQUESTS_PER_TURN", 2)
    turns = [
        FakeStream([tool_use_block(f"tu_{i}", "echo hi")], stop_reason="tool_use")
        for i in range(2)
    ]
    reply = [text_block("ok now")]
    messages = FakeMessages(turns + [reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["go", "next", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "[Stopped: 2 requests in one turn" in out
    assert "Bye!" in out  # control returned to the prompt
    assert len(messages.calls) == 3  # 2 budgeted requests + the next turn
    # History stayed valid: even the budget-cutoff tool_use got its result.
    history = messages.calls[2]
    assert history[3] == {"role": "assistant", "content": turns[1]._content}
    (result,) = history[4]["content"]
    assert result["tool_use_id"] == "tu_1"
    assert history[5] == {"role": "user", "content": "next"}


def test_api_error_after_tool_run_keeps_executed_commands_in_history(
    monkeypatch, capsys
):
    # The follow-up request after a tool run fails. The command already
    # executed — its side effects are real — so the tool exchange must stay
    # in history; dropping it would make the model re-run the command on the
    # next attempt. Only the failed request itself is abandoned.
    tool_turn = FakeStream([tool_use_block("tu_1", "echo hi")], stop_reason="tool_use")
    conn_err = anthropic.APIConnectionError(request=api_request())
    reply = [text_block("ok now")]
    messages = FakeMessages([tool_turn, conn_err, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert "stay in history" in out  # the user is told the record is kept
    assert len(messages.calls) == 3
    # The executed tool exchange survives into the next turn's history.
    assert messages.calls[2] == [
        {"role": "user", "content": "fails"},
        {"role": "assistant", "content": tool_turn._content},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu_1",
                    "content": "hi",
                    "is_error": False,
                }
            ],
        },
        {"role": "user", "content": "hello"},
    ]


def test_network_error_mid_stream_drops_turn_and_continues(monkeypatch, capsys):
    # A network failure mid-stream raises a raw httpx error (the SDK only wraps
    # transport errors around the initial send, not around SSE iteration); the
    # loop must survive it instead of crashing with a traceback.
    err = httpx.ReadError("connection lost mid-stream")
    stream = FakeStream([text_block("partial")], mid_stream_error=err)
    reply = [text_block("ok now")]
    messages = FakeMessages([stream, reply])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 2
    # The failed turn was popped, so the next call's history is clean.
    assert messages.calls[1] == [{"role": "user", "content": "hello"}]
