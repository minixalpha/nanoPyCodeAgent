"""Tests for the minimal agent loop.

Every Anthropic API access is mocked, so these tests never hit the network and
never spend tokens. We drive ``run()`` by scripting ``input()`` and the client,
then assert on captured stdout and the recorded calls.
"""

import json
import os
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from nanopycodeagent import agent

_MANAGED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL")


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    """Keep every test off the real config file and ambient ANTHROPIC_* vars.

    ``SETTINGS_PATH`` is redirected into an empty temp dir (so tests never read
    the developer's ~/.nanoPyCodeAgent/settings.json), and the managed env vars
    are cleared up front and restored afterwards — ``load_settings_env`` writes
    to ``os.environ`` directly, which monkeypatch would not roll back on its own.
    """
    monkeypatch.setattr(agent, "SETTINGS_PATH", tmp_path / "settings.json")
    saved = {key: os.environ.pop(key, None) for key in _MANAGED_ENV}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _text_block(text):
    """A minimal stand-in for an SDK text content block."""
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(block_id, command, name="bash"):
    """A minimal stand-in for an SDK tool_use content block."""
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input={"command": command})


def _write_settings(path, env):
    """Write a ``settings.json`` with the given ``env`` mapping."""
    path.write_text(json.dumps({"env": env}), encoding="utf-8")


class _FakeStream:
    """Mimics the SDK's ``MessageStream`` context manager for scripted replies.

    ``mid_stream_error`` simulates a failure while the reply is streaming: the
    text chunks are yielded first, then the exception is raised from within the
    ``text_stream`` iteration — after partial output has already been printed.
    ``stop_reason`` is ``"tool_use"`` when the scripted reply asks to run tools.
    """

    def __init__(self, content, mid_stream_error=None, stop_reason="end_turn"):
        self._content = content
        self._mid_stream_error = mid_stream_error
        self._stop_reason = stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    @property
    def text_stream(self):
        def _gen():
            # Yield each text block's text as a single chunk.
            for b in self._content:
                if b.type == "text":
                    yield b.text
            if self._mid_stream_error is not None:
                raise self._mid_stream_error

        return _gen()

    def get_final_message(self):
        return SimpleNamespace(content=self._content, stop_reason=self._stop_reason)


class _FakeMessages:
    """Records each ``stream()`` call and replays a scripted response or raises."""

    def __init__(self, script):
        # Each script entry is either a list of content blocks to stream as the
        # message's ``content``, a ``BaseException`` instance to raise at request
        # time (an API error, or ``KeyboardInterrupt`` to simulate Ctrl-C while
        # connecting), or a ``_FakeStream`` — e.g. one that fails mid-stream.
        self._script = list(script)
        self.calls = []  # snapshot of the ``messages`` list at each call
        self.kwargs = []  # full kwargs passed to each stream() call

    def stream(self, **kwargs):
        self.calls.append(list(kwargs["messages"]))  # freeze history at call time
        self.kwargs.append(kwargs)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, _FakeStream):
            return item
        return _FakeStream(item)


class _FakeClient:
    def __init__(self, messages, *, api_key="sk-test", auth_token=None):
        self.messages = messages
        self.api_key = api_key
        self.auth_token = auth_token


def _request():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _patch(monkeypatch, *, client, inputs):
    """Wire up a fake Anthropic client and scripted input().

    The config file is isolated by the autouse ``_isolate_config`` fixture, so
    ``run()`` sees no config file unless a test writes one to ``SETTINGS_PATH``.
    """
    monkeypatch.setattr(agent.anthropic, "Anthropic", lambda *a, **k: client)

    answers = iter(inputs)

    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration as exc:  # safety net: behaves like Ctrl-D
            raise EOFError from exc

    monkeypatch.setattr("builtins.input", fake_input)


def test_missing_credentials_exits_early(monkeypatch, capsys):
    messages = _FakeMessages([])
    client = _FakeClient(messages, api_key=None, auth_token=None)
    _patch(monkeypatch, client=client, inputs=[])

    agent.run()

    out = capsys.readouterr().out
    assert "No API credentials found." in out
    # Third-party / proxy users are told how to point the SDK at their endpoint.
    assert "ANTHROPIC_BASE_URL" in out
    assert "Bye!" not in out  # returned before entering the loop
    assert messages.calls == []


def test_startup_message_shows_default_model(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    messages = _FakeMessages([])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    # With credentials configured, the banner names the default model in use.
    assert agent.DEFAULT_MODEL in out


def test_model_can_be_overridden_via_env(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    reply = [_text_block("ok")]
    messages = _FakeMessages([reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "claude-opus-4-8" in out  # banner reflects the configured model
    assert messages.kwargs[0]["model"] == "claude-opus-4-8"  # and it reaches the API


def test_blank_model_env_falls_back_to_default(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_MODEL", "   ")  # empty / whitespace-only
    reply = [_text_block("ok")]
    messages = _FakeMessages([reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    assert messages.kwargs[0]["model"] == agent.DEFAULT_MODEL


def test_exit_command_quits_without_api_call(monkeypatch, capsys):
    messages = _FakeMessages([])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Bye!" in out
    assert messages.calls == []  # /exit never reaches the API


def test_single_turn_prints_reply(monkeypatch, capsys):
    reply = [_text_block("Hi there")]
    messages = _FakeMessages([reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Hi there" in out  # reply text was printed
    assert "Bye!" in out
    assert len(messages.calls) == 1
    assert messages.calls[0] == [{"role": "user", "content": "hello"}]


def test_multi_turn_accumulates_history(monkeypatch, capsys):
    reply1 = [_text_block("Nice to meet you, Alice.")]
    reply2 = [_text_block("Your name is Alice.")]
    messages = _FakeMessages([reply1, reply2])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["I'm Alice", "What's my name?", "/exit"])

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
    messages = _FakeMessages([])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["", "   ", "/exit"])

    agent.run()

    assert messages.calls == []  # blank / whitespace lines never reach the API


def test_authentication_error_breaks_loop(monkeypatch, capsys):
    err = anthropic.AuthenticationError(
        "unauthorized", response=httpx.Response(401, request=_request()), body=None
    )
    messages = _FakeMessages([err])
    client = _FakeClient(messages)
    # The second input is provided but must never be read (the loop breaks).
    _patch(monkeypatch, client=client, inputs=["hi", "should be ignored"])

    agent.run()

    out = capsys.readouterr().out
    assert "Authentication failed." in out
    assert "Bye!" in out
    assert len(messages.calls) == 1  # broke right after the failed call


def test_api_error_drops_turn_and_continues(monkeypatch, capsys):
    conn_err = anthropic.APIConnectionError(request=_request())
    reply = [_text_block("ok now")]
    messages = _FakeMessages([conn_err, reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 2
    # First (failed) call saw the "fails" turn.
    assert messages.calls[0] == [{"role": "user", "content": "fails"}]
    # That turn was popped on error, so the next call's history is clean.
    assert messages.calls[1] == [{"role": "user", "content": "hello"}]


def test_settings_file_supplies_model(monkeypatch):
    # With ANTHROPIC_MODEL unset in the environment, the config file supplies it.
    _write_settings(agent.SETTINGS_PATH, {"ANTHROPIC_MODEL": "claude-opus-4-8"})
    messages = _FakeMessages([[_text_block("ok")]])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    assert messages.kwargs[0]["model"] == "claude-opus-4-8"  # reaches the API


def test_env_var_overrides_settings_file(monkeypatch):
    # A real environment variable wins over the config file's value.
    _write_settings(agent.SETTINGS_PATH, {"ANTHROPIC_MODEL": "from-settings"})
    monkeypatch.setenv("ANTHROPIC_MODEL", "from-env")
    messages = _FakeMessages([[_text_block("ok")]])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    assert messages.kwargs[0]["model"] == "from-env"


def test_missing_settings_file_starts_cleanly(monkeypatch, capsys):
    # No config file exists (SETTINGS_PATH points into an empty temp dir).
    messages = _FakeMessages([])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Warning" not in out  # a missing config file is not an error
    assert "Bye!" in out


def test_malformed_settings_file_warns_but_continues(monkeypatch, capsys):
    # A broken config file degrades gracefully: warn, then start anyway.
    agent.SETTINGS_PATH.write_text("{ not valid json", encoding="utf-8")
    messages = _FakeMessages([])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Warning" in out  # the malformed file was reported
    assert "Bye!" in out  # but startup still proceeded


def test_load_settings_env_fills_only_unset_keys(monkeypatch, tmp_path):
    # Existing env vars are preserved; only unset keys are filled from the file.
    monkeypatch.setenv("ANTHROPIC_MODEL", "already-set")
    path = tmp_path / "settings.json"
    _write_settings(path, {"ANTHROPIC_MODEL": "ignored", "ANTHROPIC_API_KEY": "sk-cfg"})

    agent.load_settings_env(path)

    assert os.environ["ANTHROPIC_MODEL"] == "already-set"  # env var wins
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-cfg"  # the gap gets filled


def test_load_settings_env_skips_empty_and_non_string(tmp_path):
    path = tmp_path / "settings.json"
    _write_settings(
        path,
        {
            "ANTHROPIC_API_KEY": "sk-real",
            "ANTHROPIC_BASE_URL": "",  # empty -> skipped
            "ANTHROPIC_MODEL": "   ",  # whitespace-only -> skipped
            "SOME_FLAG": 123,  # non-string -> skipped
        },
    )

    agent.load_settings_env(path)

    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-real"
    assert "ANTHROPIC_BASE_URL" not in os.environ
    assert "ANTHROPIC_MODEL" not in os.environ
    assert "SOME_FLAG" not in os.environ


def test_load_settings_env_ignores_non_anthropic_keys(monkeypatch, tmp_path):
    # Only ANTHROPIC_* keys are honored; unrelated (string) vars are never
    # injected into the environment, even when unset.
    monkeypatch.delenv("UNRELATED_PROXY_VAR", raising=False)
    path = tmp_path / "settings.json"
    _write_settings(
        path,
        {"UNRELATED_PROXY_VAR": "http://proxy:8080", "ANTHROPIC_API_KEY": "sk-real"},
    )

    agent.load_settings_env(path)

    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-real"  # allowed key fills
    assert "UNRELATED_PROXY_VAR" not in os.environ  # foreign key ignored


def test_load_settings_env_skips_os_rejected_values(tmp_path, capsys):
    # A value the OS rejects (embedded NUL) is warned about, not fatal, and the
    # key is left unset — a bad config never blocks startup.
    path = tmp_path / "settings.json"
    _write_settings(path, {"ANTHROPIC_API_KEY": "sk-\x00bad"})

    agent.load_settings_env(path)  # must not raise

    out = capsys.readouterr().out
    assert "Warning" in out
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_load_settings_env_handles_unresolvable_home(monkeypatch):
    # When the home dir can't be resolved, SETTINGS_PATH is None and the default
    # load is a silent no-op rather than a crash.
    monkeypatch.setattr(agent, "SETTINGS_PATH", None)

    agent.load_settings_env()  # must not raise


def test_default_settings_path_survives_unresolvable_home(monkeypatch):
    # Path.home() raising RuntimeError yields a None path instead of propagating
    # out at import time.
    def _no_home(*args, **kwargs):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(agent.Path, "home", _no_home)

    assert agent._default_settings_path() is None


def test_non_utf8_settings_file_warns_but_continues(monkeypatch, capsys):
    # A config file with non-UTF-8 bytes degrades gracefully instead of crashing.
    agent.SETTINGS_PATH.write_bytes(b"\xff\xfe not utf-8")
    messages = _FakeMessages([])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Warning" in out  # the unreadable file was reported
    assert "Bye!" in out  # but startup still proceeded


def test_startup_message_labels_explicit_default_model_as_configured(monkeypatch, capsys):
    # Explicitly pinning the model to the default value is still reported as a
    # configured override, not as the fallback.
    monkeypatch.setenv("ANTHROPIC_MODEL", agent.DEFAULT_MODEL)
    messages = _FakeMessages([[_text_block("ok")]])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "from ANTHROPIC_MODEL" in out
    assert "using default model" not in out


def test_keyboard_interrupt_during_request_exits_gracefully(monkeypatch, capsys):
    # Ctrl-C while waiting on the model reply quits cleanly, not with a traceback.
    messages = _FakeMessages([KeyboardInterrupt()])
    client = _FakeClient(messages)
    # The second input is provided but must never be read (the loop breaks).
    _patch(monkeypatch, client=client, inputs=["hi", "should be ignored"])

    agent.run()

    out = capsys.readouterr().out
    assert "Bye!" in out
    assert len(messages.calls) == 1  # broke right after the interrupted call


def test_keyboard_interrupt_mid_stream_exits_gracefully(monkeypatch, capsys):
    # Ctrl-C after part of the reply has already streamed quits cleanly.
    stream = _FakeStream([_text_block("partial")], mid_stream_error=KeyboardInterrupt())
    messages = _FakeMessages([stream])
    client = _FakeClient(messages)
    # The second input is provided but must never be read (the loop breaks).
    _patch(monkeypatch, client=client, inputs=["hi", "should be ignored"])

    agent.run()

    out = capsys.readouterr().out
    assert "partial" in out  # the streamed text made it out before the interrupt
    assert "Bye!" in out
    assert len(messages.calls) == 1


def test_api_error_mid_stream_drops_turn_and_continues(monkeypatch, capsys):
    # An SDK error surfacing mid-stream (e.g. an SSE error event) is handled
    # the same as one raised at request time: drop the turn and keep going.
    err = anthropic.APIConnectionError(request=_request())
    stream = _FakeStream([_text_block("partial")], mid_stream_error=err)
    reply = [_text_block("ok now")]
    messages = _FakeMessages([stream, reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 2
    # The failed turn was popped, so the next call's history is clean.
    assert messages.calls[1] == [{"role": "user", "content": "hello"}]


def test_run_bash_captures_stdout():
    output, is_error = agent.run_bash("echo hello")

    assert output == "hello"
    assert is_error is False


def test_run_bash_reports_stderr_and_exit_code():
    output, is_error = agent.run_bash("echo oops >&2; exit 3")

    assert "[stderr]\noops" in output
    assert "[exit code: 3]" in output
    assert is_error is True


def test_run_bash_placeholder_for_empty_output():
    output, is_error = agent.run_bash("true")

    assert output == "(no output)"
    assert is_error is False


def test_run_bash_times_out(monkeypatch):
    monkeypatch.setattr(agent, "BASH_TIMEOUT_SECONDS", 0.2)

    output, is_error = agent.run_bash("sleep 5")

    assert "timed out" in output
    assert is_error is True


def test_run_bash_truncates_long_output(monkeypatch):
    monkeypatch.setattr(agent, "MAX_TOOL_OUTPUT_CHARS", 10)

    output, is_error = agent.run_bash("printf 'a%.0s' {1..100}")

    assert output.startswith("a" * 10)
    assert output.endswith("[... output truncated ...]")
    assert is_error is False


def test_tool_use_turn_runs_bash_and_feeds_result_back(monkeypatch, capsys):
    # First reply asks to run a command; the second one answers with text.
    tool_turn = _FakeStream(
        [_text_block("Let me check."), _tool_use_block("tu_1", "echo hello")],
        stop_reason="tool_use",
    )
    final = [_text_block("It printed hello.")]
    messages = _FakeMessages([tool_turn, final])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["run echo", "/exit"])

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
    tool_turn = _FakeStream(
        [_tool_use_block("tu_1", "echo one"), _tool_use_block("tu_2", "echo two")],
        stop_reason="tool_use",
    )
    final = [_text_block("done")]
    messages = _FakeMessages([tool_turn, final])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["go", "/exit"])

    agent.run()

    results = messages.calls[1][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["tu_1", "tu_2"]
    assert [r["content"] for r in results] == ["one", "two"]


def test_unknown_tool_returns_error_result(monkeypatch, capsys):
    # A tool name we never registered comes back as an error result instead of
    # crashing the loop, so the model can see the problem and recover.
    tool_turn = _FakeStream(
        [_tool_use_block("tu_1", "whatever", name="python")], stop_reason="tool_use"
    )
    final = [_text_block("ok")]
    messages = _FakeMessages([tool_turn, final])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["go", "/exit"])

    agent.run()

    (result,) = messages.calls[1][-1]["content"]
    assert result["is_error"] is True
    assert "Unknown tool: python" in result["content"]


def test_bash_tool_with_invalid_input_returns_error_result(monkeypatch, capsys):
    # A tool_use block without a usable 'command' string becomes an error
    # result; nothing is executed.
    bad_block = SimpleNamespace(type="tool_use", id="tu_1", name="bash", input={})
    tool_turn = _FakeStream([bad_block], stop_reason="tool_use")
    final = [_text_block("ok")]
    messages = _FakeMessages([tool_turn, final])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["go", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "[bash]$" not in out  # nothing ran
    (result,) = messages.calls[1][-1]["content"]
    assert result["is_error"] is True
    assert "'command'" in result["content"]


def test_api_error_during_tool_loop_drops_whole_turn(monkeypatch, capsys):
    # The follow-up request after a tool run fails: the whole turn — user
    # prompt, tool_use reply, and tool_result — is rolled back so the next
    # turn starts from a valid history.
    tool_turn = _FakeStream([_tool_use_block("tu_1", "echo hi")], stop_reason="tool_use")
    conn_err = anthropic.APIConnectionError(request=_request())
    reply = [_text_block("ok now")]
    messages = _FakeMessages([tool_turn, conn_err, reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 3
    # The partial tool exchange was rolled back, so the next call is clean.
    assert messages.calls[2] == [{"role": "user", "content": "hello"}]


def test_network_error_mid_stream_drops_turn_and_continues(monkeypatch, capsys):
    # A network failure mid-stream raises a raw httpx error (the SDK only wraps
    # transport errors around the initial send, not around SSE iteration); the
    # loop must survive it instead of crashing with a traceback.
    err = httpx.ReadError("connection lost mid-stream")
    stream = _FakeStream([_text_block("partial")], mid_stream_error=err)
    reply = [_text_block("ok now")]
    messages = _FakeMessages([stream, reply])
    client = _FakeClient(messages)
    _patch(monkeypatch, client=client, inputs=["fails", "hello", "/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Request failed:" in out
    assert len(messages.calls) == 2
    # The failed turn was popped, so the next call's history is clean.
    assert messages.calls[1] == [{"role": "user", "content": "hello"}]
