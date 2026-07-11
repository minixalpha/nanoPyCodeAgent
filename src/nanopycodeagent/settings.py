"""User-level configuration for nanoPyCodeAgent.

The config file at ``~/.nanoPyCodeAgent/settings.json`` may carry an ``env``
mapping that supplies ``ANTHROPIC_*`` values for keys that are not already set
in the environment (environment variables win).
"""

import json
import os
from pathlib import Path


def _default_settings_path() -> Path | None:
    """Resolve the user-level config path, or ``None`` if home is unknown.

    ``Path.home()`` raises ``RuntimeError`` when the home directory cannot be
    determined (e.g. ``$HOME`` unset and no passwd entry, common in minimal
    containers). Guarding it here keeps ``import nanopycodeagent`` — which runs
    eagerly behind the console script — from crashing at import; a ``None`` path
    simply means "no user config file".
    """
    try:
        return Path.home() / ".nanoPyCodeAgent" / "settings.json"
    except RuntimeError:
        return None


SETTINGS_PATH = _default_settings_path()


def load_settings_env(path: Path | None = None) -> None:
    """Apply the ``env`` mapping from the config file into ``os.environ``.

    ``path`` defaults to the module-level ``SETTINGS_PATH`` (resolved at call
    time, so it stays overridable). Only ``ANTHROPIC_*`` keys that are not
    already present are set, so environment variables take precedence over the
    config file and unrelated variables are never injected. Behaviour by case:

    - Missing file, or a home directory that cannot be resolved: silently
      ignored (running without a config file is normal).
    - Unreadable / non-UTF-8 file, malformed JSON, non-object top level, or a
      non-object ``env``: a warning is printed and the file is otherwise
      ignored — a bad config never blocks startup.
    - Empty, whitespace-only, or non-string values, and values the OS rejects
      (e.g. an embedded NUL): skipped (the documented example ships these keys
      as empty-string placeholders).
    """
    if path is None:
        path = SETTINGS_PATH
    if path is None:
        return  # home dir unresolvable → behave as if no config file exists
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Warning: could not read config file {path}: {exc}")
        return

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"Warning: ignoring malformed config file {path}: {exc}")
        return

    if not isinstance(data, dict):
        print(f"Warning: ignoring config file {path}: top level must be an object.")
        return

    env = data.get("env", {})
    if not isinstance(env, dict):
        print(f"Warning: ignoring 'env' in config file {path}: it must be an object.")
        return

    for key, value in env.items():
        # Only honor ANTHROPIC_* keys (the config's documented purpose) so a
        # shared settings.json cannot silently inject unrelated variables such
        # as HTTPS_PROXY into the process environment.
        if not key.startswith("ANTHROPIC_"):
            continue
        if not (isinstance(value, str) and value.strip()):
            continue
        try:
            os.environ.setdefault(key, value.strip())
        except ValueError as exc:
            # e.g. an embedded NUL in the value or '=' in the key name.
            print(f"Warning: ignoring invalid config entry {key!r}: {exc}")
