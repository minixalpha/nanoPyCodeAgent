"""Terminal presentation: tool-activity shading and a wait spinner."""

import itertools
import os
import sys
import threading

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


# The classic braille "dots" spinner: one glyph per frame, different dots
# raised in each, cycled fast enough to read as rotation.
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_INTERVAL = 0.08


class Spinner:
    """Animate ``⠋ Working...`` in place on one line until stopped.

    A background thread redraws the line with carriage returns while the
    caller blocks on slow work, and erases it on stop, so the spinner
    leaves no trace in the transcript. When stdout is not a terminal (or
    NO_COLOR is set) nothing is printed at all. ``stop`` is idempotent:
    stopping early — say, when the first streamed token arrives — and
    again on context-manager exit is fine.
    """

    def __init__(self, text: str = "Working..."):
        self._text = text
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not _use_color():
            return
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join()

    def __enter__(self) -> "Spinner":
        self.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stop()

    def _spin(self) -> None:
        # Draw a frame, then sleep on the stop event so stop() interrupts
        # the pause instead of waiting out the full interval.
        for frame in itertools.cycle(_SPINNER_FRAMES):
            sys.stdout.write(f"\r{frame} {self._text}")
            sys.stdout.flush()
            if self._stop_event.wait(_SPINNER_INTERVAL):
                break
        sys.stdout.write("\r\x1b[K")  # erase the spinner line
        sys.stdout.flush()
