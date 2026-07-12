"""Tests for the agent loop: startup, streaming, and tool dispatch.

Every Anthropic API access is mocked, so these tests never hit the network and
never spend tokens. We drive ``run()`` by scripting ``input()`` and the client,
then assert on captured stdout and the recorded calls.
"""

from nanopycodeagent import agent

from helpers import (
    FakeClient,
    FakeMessages,
    FakeStream,
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
    # With credentials configured, the banner names the model in use.
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


def test_exit_command_quits_without_api_call(monkeypatch, capsys):
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Bye!" in out
    assert messages.calls == []  # /exit never reaches the API


def test_eof_at_the_prompt_quits(monkeypatch, capsys):
    # Ctrl-D (or Ctrl-C) at the You> prompt ends the session cleanly.
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=[])  # immediate EOF

    agent.run()

    assert "Bye!" in capsys.readouterr().out


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


def test_tool_echo_is_sanitized_but_the_model_sees_raw_output(capsys):
    # Display is sanitized; the tool_result content keeps the real escape
    # codes so the model works with what the command actually produced.
    block = tool_use_block("tu_1", "printf 'ab\\033[2K'")

    result = agent._run_one_tool(block)

    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert "\x1b" in result["content"]
    assert result["is_error"] is False


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
