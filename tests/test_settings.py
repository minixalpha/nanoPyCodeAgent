"""Tests for user-level config loading (``settings.py``).

The pure ``load_settings_env`` cases call it directly; the startup cases drive
``run()`` with a fake client to check the config file is honored end to end.
"""

import os

from nanopycodeagent import agent, settings

from helpers import (
    FakeClient,
    FakeMessages,
    patch_client_and_input,
    text_block,
    write_settings,
)


def test_settings_file_supplies_model(monkeypatch):
    # With ANTHROPIC_MODEL unset in the environment, the config file supplies it.
    write_settings(settings.SETTINGS_PATH, {"ANTHROPIC_MODEL": "claude-opus-4-8"})
    messages = FakeMessages([[text_block("ok")]])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    assert messages.kwargs[0]["model"] == "claude-opus-4-8"  # reaches the API


def test_env_var_overrides_settings_file(monkeypatch):
    # A real environment variable wins over the config file's value.
    write_settings(settings.SETTINGS_PATH, {"ANTHROPIC_MODEL": "from-settings"})
    monkeypatch.setenv("ANTHROPIC_MODEL", "from-env")
    messages = FakeMessages([[text_block("ok")]])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["hi", "/exit"])

    agent.run()

    assert messages.kwargs[0]["model"] == "from-env"


def test_missing_settings_file_starts_cleanly(monkeypatch, capsys):
    # No config file exists (SETTINGS_PATH points into an empty temp dir).
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Warning" not in out  # a missing config file is not an error
    assert "Bye!" in out


def test_malformed_settings_file_warns_but_continues(monkeypatch, capsys):
    # A broken config file degrades gracefully: warn, then start anyway.
    settings.SETTINGS_PATH.write_text("{ not valid json", encoding="utf-8")
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Warning" in out  # the malformed file was reported
    assert "Bye!" in out  # but startup still proceeded


def test_non_utf8_settings_file_warns_but_continues(monkeypatch, capsys):
    # A config file with non-UTF-8 bytes degrades gracefully instead of crashing.
    settings.SETTINGS_PATH.write_bytes(b"\xff\xfe not utf-8")
    messages = FakeMessages([])
    client = FakeClient(messages)
    patch_client_and_input(monkeypatch, client=client, inputs=["/exit"])

    agent.run()

    out = capsys.readouterr().out
    assert "Warning" in out  # the unreadable file was reported
    assert "Bye!" in out  # but startup still proceeded


def test_load_settings_env_fills_only_unset_keys(monkeypatch, tmp_path):
    # Existing env vars are preserved; only unset keys are filled from the file.
    monkeypatch.setenv("ANTHROPIC_MODEL", "already-set")
    path = tmp_path / "settings.json"
    write_settings(path, {"ANTHROPIC_MODEL": "ignored", "ANTHROPIC_API_KEY": "sk-cfg"})

    settings.load_settings_env(path)

    assert os.environ["ANTHROPIC_MODEL"] == "already-set"  # env var wins
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-cfg"  # the gap gets filled


def test_load_settings_env_skips_empty_and_non_string(tmp_path):
    path = tmp_path / "settings.json"
    write_settings(
        path,
        {
            "ANTHROPIC_API_KEY": "sk-real",
            "ANTHROPIC_BASE_URL": "",  # empty -> skipped
            "ANTHROPIC_MODEL": "   ",  # whitespace-only -> skipped
            "SOME_FLAG": 123,  # non-string -> skipped
        },
    )

    settings.load_settings_env(path)

    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-real"
    assert "ANTHROPIC_BASE_URL" not in os.environ
    assert "ANTHROPIC_MODEL" not in os.environ
    assert "SOME_FLAG" not in os.environ


def test_load_settings_env_ignores_non_anthropic_keys(monkeypatch, tmp_path):
    # Only ANTHROPIC_* keys are honored; unrelated (string) vars are never
    # injected into the environment, even when unset.
    monkeypatch.delenv("UNRELATED_PROXY_VAR", raising=False)
    path = tmp_path / "settings.json"
    write_settings(
        path,
        {"UNRELATED_PROXY_VAR": "http://proxy:8080", "ANTHROPIC_API_KEY": "sk-real"},
    )

    settings.load_settings_env(path)

    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-real"  # allowed key fills
    assert "UNRELATED_PROXY_VAR" not in os.environ  # foreign key ignored


def test_load_settings_env_skips_os_rejected_values(tmp_path, capsys):
    # A value the OS rejects (embedded NUL) is warned about, not fatal, and the
    # key is left unset — a bad config never blocks startup.
    path = tmp_path / "settings.json"
    write_settings(path, {"ANTHROPIC_API_KEY": "sk-\x00bad"})

    settings.load_settings_env(path)  # must not raise

    out = capsys.readouterr().out
    assert "Warning" in out
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_load_settings_env_handles_unresolvable_home(monkeypatch):
    # When the home dir can't be resolved, SETTINGS_PATH is None and the default
    # load is a silent no-op rather than a crash.
    monkeypatch.setattr(settings, "SETTINGS_PATH", None)

    settings.load_settings_env()  # must not raise


def test_default_settings_path_survives_unresolvable_home(monkeypatch):
    # Path.home() raising RuntimeError yields a None path instead of propagating
    # out at import time.
    def _no_home(*args, **kwargs):
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(settings.Path, "home", _no_home)

    assert settings._default_settings_path() is None
