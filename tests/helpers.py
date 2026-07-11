"""Shared fakes and helpers for driving ``run()`` without the network.

Every Anthropic API access is mocked, so tests never hit the network and never
spend tokens: ``FakeMessages`` replays scripted replies and records each call,
and ``patch_client_and_input`` wires a fake client and a scripted ``input()``
into the loop.
"""

import json
from types import SimpleNamespace

import anthropic
import httpx


def text_block(text):
    """A minimal stand-in for an SDK text content block."""
    return SimpleNamespace(type="text", text=text)


def tool_use_block(block_id, command, name="bash"):
    """A minimal stand-in for an SDK tool_use content block."""
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input={"command": command})


def write_settings(path, env):
    """Write a ``settings.json`` with the given ``env`` mapping."""
    path.write_text(json.dumps({"env": env}), encoding="utf-8")


class FakeStream:
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


class FakeMessages:
    """Records each ``stream()`` call and replays a scripted response or raises."""

    def __init__(self, script):
        # Each script entry is either a list of content blocks to stream as the
        # message's ``content``, a ``BaseException`` instance to raise at request
        # time (an API error, or ``KeyboardInterrupt`` to simulate Ctrl-C while
        # connecting), or a ``FakeStream`` — e.g. one that fails mid-stream.
        self._script = list(script)
        self.calls = []  # snapshot of the ``messages`` list at each call
        self.kwargs = []  # full kwargs passed to each stream() call

    def stream(self, **kwargs):
        self.calls.append(list(kwargs["messages"]))  # freeze history at call time
        self.kwargs.append(kwargs)
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, FakeStream):
            return item
        return FakeStream(item)


class FakeClient:
    def __init__(self, messages, *, api_key="sk-test", auth_token=None):
        self.messages = messages
        self.api_key = api_key
        self.auth_token = auth_token


def api_request():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def patch_client_and_input(monkeypatch, *, client, inputs):
    """Wire up a fake Anthropic client and scripted input().

    The config file is isolated by the autouse ``_isolate_config`` fixture in
    conftest.py, so ``run()`` sees no config file unless a test writes one to
    ``settings.SETTINGS_PATH``.
    """
    monkeypatch.setattr(anthropic, "Anthropic", lambda *a, **k: client)

    answers = iter(inputs)

    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration as exc:  # safety net: behaves like Ctrl-D
            raise EOFError from exc

    monkeypatch.setattr("builtins.input", fake_input)
