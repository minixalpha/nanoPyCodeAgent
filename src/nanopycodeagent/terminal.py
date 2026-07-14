"""Background shading for tool activity in the terminal."""

import os
import sys

# Dark gray from the 256-color palette, so echoed commands and their output
# read apart from the user's prompts and the model's prose.
_TOOL_BG = "\x1b[48;5;236m"
_RESET = "\x1b[0m"


def _use_color() -> bool:
    """Whether to emit ANSI colors: a real terminal, and NO_COLOR unset."""
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def print_tool(text: str) -> None:
    """Print tool activity (an echoed command or its output) shaded.

    Each line carries its own set-background / erase-to-EOL / reset, so the
    shading spans the full terminal width and never leaks past a line
    boundary. Escape sequences inside ``text`` are printed as-is and may
    disrupt the shading — a cosmetic trade for staying simple.
    """
    if _use_color():
        text = "\n".join(
            f"{_TOOL_BG}{line}\x1b[K{_RESET}" for line in text.split("\n")
        )
    print(text, flush=True)
