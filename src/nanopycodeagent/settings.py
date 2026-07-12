"""User-level configuration for nanoPyCodeAgent.

The config file at ``~/.nanoPyCodeAgent/settings.json`` may carry an ``env``
mapping that supplies ``ANTHROPIC_*`` values for keys that are not already set
in the environment (environment variables win).
"""

import json
import os
from pathlib import Path

SETTINGS_PATH = Path.home() / ".nanoPyCodeAgent" / "settings.json"


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
