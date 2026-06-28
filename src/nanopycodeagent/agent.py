"""A minimal agent loop built on the Anthropic Python SDK.

Run the program, type a message, and Agent replies. The full conversation is
kept in memory so each turn has context. Type ``/exit`` to quit.
"""

import os

import anthropic
from anthropic.types import MessageParam
from dotenv import find_dotenv, load_dotenv

# The model used when ANTHROPIC_MODEL is not set in the environment / .env file.
DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
SYSTEM_PROMPT = "You are nanoPyCodeAgent, a concise and helpful coding assistant."


def run() -> None:
    """Start the read → ask → answer loop until the user types ``/exit``."""
    # Load a .env from the current working directory (walking upward), then
    # resolve credentials from the environment (ANTHROPIC_API_KEY). usecwd=True
    # makes discovery relative to where the user runs the tool, not where this
    # module happens to be installed.
    load_dotenv(find_dotenv(usecwd=True))
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

    # Resolve the model after load_dotenv() so a .env ANTHROPIC_MODEL is honored.
    # An empty or whitespace-only value falls back to the default.
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
