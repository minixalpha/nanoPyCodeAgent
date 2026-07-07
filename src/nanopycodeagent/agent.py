"""A minimal agent loop built on the Anthropic Python SDK.

Run the program, type a message, and Agent replies. The full conversation is
kept in memory so each turn has context. Type ``/exit`` to quit.
"""

import json
import os
from pathlib import Path

import anthropic
from anthropic.types import MessageParam

# The model used when ANTHROPIC_MODEL is set in neither the environment nor the
# config file.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
SYSTEM_PROMPT = "You are nanoPyCodeAgent, a concise and helpful coding assistant."

# User-level config file. Its ``env`` mapping supplies ANTHROPIC_* values for
# keys that are not already set in the environment (environment variables win).
SETTINGS_PATH = Path.home() / ".nanoPyCodeAgent" / "settings.json"


def load_settings_env(path: Path | None = None) -> None:
    """Apply the ``env`` mapping from the config file into ``os.environ``.

    ``path`` defaults to the module-level ``SETTINGS_PATH`` (resolved at call
    time, so it stays overridable). Only keys not already present are set, so
    environment variables take precedence over the config file. Behaviour by
    case:

    - Missing file: silently ignored (running without a config file is normal).
    - Malformed JSON, non-object top level, or a non-object ``env``: a warning is
      printed and the file is otherwise ignored — a bad config never blocks
      startup.
    - Empty, whitespace-only, or non-string values: skipped (the documented
      example ships these keys as empty-string placeholders).
    """
    if path is None:
        path = SETTINGS_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError as exc:
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
        if isinstance(value, str) and value.strip():
            os.environ.setdefault(key, value.strip())


def run() -> None:
    """Start the read → ask → answer loop until the user types ``/exit``."""
    # Fill any unset ANTHROPIC_* keys from the config file (environment variables
    # take precedence), then let the SDK read credentials from os.environ.
    load_settings_env()
    client = anthropic.Anthropic()
    if client.api_key is None and client.auth_token is None:
        print(
            "No API credentials found. Set the ANTHROPIC_API_KEY environment variable."
        )
        print(
            "If you use a third-party / proxy service, also set ANTHROPIC_BASE_URL "
            "to point at its endpoint."
        )
        return

    # Resolve the model after load_settings_env() so a config-file ANTHROPIC_MODEL
    # is honored. An empty or whitespace-only value falls back to the default.
    model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    messages: list[MessageParam] = []
    if model == DEFAULT_MODEL:
        print(
            f"nanoPyCodeAgent — using default model {model} "
            "(set ANTHROPIC_MODEL to override)."
        )
    else:
        print(f"nanoPyCodeAgent — using model {model} (from ANTHROPIC_MODEL).")
    print("Type a message to chat, or /exit to quit.")

    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input == "/exit":
            break

        messages.append({"role": "user", "content": user_input})

        try:
            print("\nAgent> ", end="", flush=True)
            message = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            text = "".join(b.text for b in message.content if b.type == "text")
            print(text, end="", flush=True)
            print()
        except anthropic.AuthenticationError:
            print(
                "\nAuthentication failed. Check that ANTHROPIC_API_KEY is set correctly."
            )
            break
        except anthropic.APIError as exc:
            print(f"\nRequest failed: {exc}")
            messages.pop()  # drop the unanswered user turn so history stays valid
            continue

        # Append the full content blocks so the next turn carries complete context.
        messages.append({"role": "assistant", "content": message.content})

    print("Bye!")
