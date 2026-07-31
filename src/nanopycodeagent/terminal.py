"""Background shading for tool activity in the terminal."""

import os
import sys

# Grays from the 256-color palette. The echoed call sits on a lighter shade
# than its output so the two read apart at a glance, and both read apart
# from the user's prompts and the model's prose. The output keeps the
# darker shade: it stays subdued while remaining visible on common dark
# terminal backgrounds.
_USE_BG = "\x1b[48;5;238m"
_OUTPUT_BG = "\x1b[48;5;236m"
_RESET = "\x1b[0m"


def _use_color() -> bool:
    """Whether to emit ANSI colors: a real terminal, and NO_COLOR unset."""
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _print_shaded(text: str, bg: str) -> None:
    """Print ``text`` with every line shaded in ``bg``.

    Each line carries its own set-background / erase-to-EOL / reset, so the
    shading spans the full terminal width and never leaks past a line
    boundary. Escape sequences inside ``text`` are printed as-is and may
    disrupt the shading — a cosmetic trade for staying simple.
    """
    if _use_color():
        text = "\n".join(f"{bg}{line}\x1b[K{_RESET}" for line in text.split("\n"))
    print(text, flush=True)


def print_tool_use(text: str) -> None:
    """Print an echoed tool call (e.g. ``[bash]$ ls``) on the lighter shade."""
    _print_shaded(text, _USE_BG)


def print_tool_output(text: str) -> None:
    """Print a tool's output on the darker shade."""
    _print_shaded(text, _OUTPUT_BG)
