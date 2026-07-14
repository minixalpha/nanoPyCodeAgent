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
    assert "Bye!" in out


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
