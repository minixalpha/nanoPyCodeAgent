"""Sanitizing text for terminal display."""

import re
import sys

# Control characters other than newline and tab: C0 controls (\r, ESC, ...),
# DEL, and the C1 range. Stripping single characters (not whole escape
# sequences) also stays correct when streamed text splits a sequence across
# chunks — the ESC is removed wherever it lands.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


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
