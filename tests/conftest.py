"""Shared fixtures for the test suite."""

import os

import pytest

from nanopycodeagent import settings

_MANAGED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL")


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path):
    """Keep every test off the real config file and ambient ANTHROPIC_* vars.

    ``settings.SETTINGS_PATH`` is redirected into an empty temp dir (so tests
    never read the developer's ~/.nanoPyCodeAgent/settings.json), and the
    managed env vars are cleared up front and restored afterwards —
    ``load_settings_env`` writes to ``os.environ`` directly, which monkeypatch
    would not roll back on its own.
    """
    monkeypatch.setattr(settings, "SETTINGS_PATH", tmp_path / "settings.json")
    saved = {key: os.environ.pop(key, None) for key in _MANAGED_ENV}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
