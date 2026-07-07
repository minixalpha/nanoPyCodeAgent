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


def _write_settings(path, env):
    """Write a ``settings.json`` with the given ``env`` mapping."""
    path.write_text(json.dumps({"env": env}), encoding="utf-8")


class _FakeMessages:
    """Records each ``create()`` call and replays a scripted response or raises."""

    def __init__(self, script):
        # Each script entry is either a list of content blocks to return as the
        # message's ``content``, or an ``Exception`` instance to raise.
        self._script = list(script)
        self.calls = []  # snapshot of the ``messages`` list at each call
        self.kwargs = []  # full kwargs passed to each create() call

    def create(self, **kwargs):
        self.calls.append(list(kwargs["messages"]))  # freeze history at call time
        self.kwargs.append(kwargs)
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(content=item)


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
