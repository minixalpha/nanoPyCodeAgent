"""User-level configuration for nanoPyCodeAgent.

The config file at ``~/.nanoPyCodeAgent/settings.json`` may carry an ``env``
mapping that supplies ``ANTHROPIC_*`` values for keys that are not already set
in the environment (environment variables win). Its top-level
``permission_mode`` is read once when an invocation starts.
"""

import json
import os
from pathlib import Path

SETTINGS_PATH = Path.home() / ".nanoPyCodeAgent" / "settings.json"
DEFAULT_MAX_TOKENS = 32768


def load_permission_mode(path: Path | None = None) -> str:
    """Read the startup-only permission mode; missing settings default to auto."""
    try:
        value = json.loads((path or SETTINGS_PATH).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "auto"
    if not isinstance(value, dict):
        raise ValueError("settings.json must contain a JSON object")
    mode = value.get("permission_mode", "auto")
    if mode not in ("auto", "full"):
        raise ValueError('permission_mode must be "auto" or "full"')
    return mode


def resolve_max_tokens(override: int | None = None) -> int:
    """Resolve the per-reply limit: explicit value, environment, file, default."""
    if override is not None:
        if isinstance(override, bool) or not isinstance(override, int) or override < 1:
            raise ValueError("--max-tokens must be a positive integer")
        return override
    load_settings_env()
    value = os.environ.get("ANTHROPIC_MAX_TOKENS")
    if value is None:
        return DEFAULT_MAX_TOKENS
    try:
        limit = int(value)
    except ValueError:
        raise ValueError("ANTHROPIC_MAX_TOKENS must be a positive integer") from None
    if limit < 1:
        raise ValueError("ANTHROPIC_MAX_TOKENS must be a positive integer")
    return limit


def load_settings_env(path: Path | None = None) -> None:
    """Apply the ``env`` mapping from the config file into ``os.environ``.

    Only ``ANTHROPIC_*`` keys that are not already present are set, so
    environment variables take precedence over the config file and unrelated
    variables are never injected. Empty, whitespace-only, and non-string
    values are skipped (the documented example ships the keys as empty-string
    placeholders). A missing file is normal; a malformed one raises — fix or
    delete it.
    """
    if path is None:
        path = SETTINGS_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    for key, value in json.loads(raw).get("env", {}).items():
        if not key.startswith("ANTHROPIC_"):
            continue
        if isinstance(value, str) and value.strip():
            os.environ.setdefault(key, value.strip())
