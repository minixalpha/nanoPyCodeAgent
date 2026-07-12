"""Sanitizing text for terminal display."""

import os
import re
import sys

# Control characters other than newline and tab: C0 controls (\r, ESC, ...),
# DEL, and the C1 range. Stripping single characters (not whole escape
# sequences) also stays correct when streamed text splits a sequence across
# chunks — the ESC is removed wherever it lands.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")

# Background shading for tool activity (echoed commands and their output),
# so it reads apart from the user's prompts and the model's prose.
_TOOL_BG = "\x1b[48;5;236m"  # dark gray, 256-color palette
_RESET = "\x1b[0m"


def _use_color() -> bool:
    """Whether to emit ANSI colors: a real terminal, and NO_COLOR unset."""
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def terminal_safe(text: str) -> str:
    """Sanitize ``text`` for terminal display.

    Two hazards guarded here. Control characters in a model-written command
    or in command output (\\r, ESC[2K, ...) could rewrite the echoed
    ``[bash]$`` line — the user's only view of what actually executed, since
    there is no confirmation gate — so everything but newline and tab is
    stripped. And characters the active stdout encoding cannot represent
    (e.g. U+FFFD under ``PYTHONIOENCODING=ascii``) would make ``print``
    raise and kill the session, so they are replaced.
    """
    text = _CONTROL_CHARS.sub("", text)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding, errors="replace")


def safe_print(text: str, end: str = "\n", tool_bg: bool = False) -> None:
    """Print ``text`` sanitized by ``terminal_safe``.

    The single chokepoint for displaying text that the program does not
    control — model replies, command output, error messages, config values.
    Call sites that print such text through ``safe_print`` cannot forget to
    sanitize it.

    With ``tool_bg=True`` each line is shaded with a background color so tool
    activity stands apart from the surrounding conversation. The shading is
    applied after sanitization (``terminal_safe`` strips ESC, so it cannot be
    embedded in ``text``), and only when writing to a terminal. ``\\x1b[K``
    before the reset extends the background to the full line width.
    """
    text = terminal_safe(text)
    if tool_bg and _use_color():
        text = "\n".join(
            f"{_TOOL_BG}{line}\x1b[K{_RESET}" for line in text.split("\n")
        )
    print(text, end=end, flush=True)
