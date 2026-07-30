"""End-to-end check that backspace erases wide characters cleanly.

Erasing a double-width character (CJK, emoji) used to leave half its glyph on
screen: the tty clears one column per backspace while the character occupies
two, so the buffer emptied but the display did not. Showing that needs a real
terminal, so this test drives the agent over a pty and replays everything it
writes onto a model of a terminal line — the assertion is on what the user
would see, not on the escape sequences a particular readline build emits.

The child never reaches the API: the session ends at ``/exit``.
"""

import locale
import os
import select
import sys
import time
import unicodedata

import pytest


def _ctype_is_utf8() -> bool:
    """Whether this environment's character type is UTF-8.

    readline only treats a multibyte character as a single unit under a UTF-8
    ctype, so under, say, an explicit ``LC_ALL=C`` there is nothing sensible
    to assert about erasing a CJK character.
    """
    if not hasattr(locale, "nl_langinfo"):  # not POSIX
        return False
    return "utf-8" in locale.nl_langinfo(locale.CODESET).replace("_", "-").lower()


pytestmark = [
    pytest.mark.skipif(not hasattr(os, "fork"), reason="needs a pty (POSIX only)"),
    pytest.mark.skipif(not _ctype_is_utf8(), reason="needs a UTF-8 locale"),
]

CHILD = "from nanopycodeagent.agent import run; run()"
PROMPT = b"You> "


def render(stream: str) -> str:
    """Replay a terminal write stream and return the last line it leaves.

    Enough of a terminal to judge this: printable characters (one cell wide,
    or two for East Asian wide/fullwidth ones), carriage return, backspace,
    and the two escapes a line editor redraws with — ``ESC[<n>G`` to move to
    an absolute column and ``ESC[K`` to erase to end of line.
    """
    cells: list[str] = []  # one entry per column; "" continues a wide glyph
    col = 0
    i = 0
    while i < len(stream):
        char = stream[i]
        if char == "\x1b" and stream[i + 1 : i + 2] == "[":
            end = i + 2
            while end < len(stream) and not stream[end].isalpha():
                end += 1
            params, final = stream[i + 2 : end], stream[end : end + 1]
            if final == "G":
                col = max(int(params or "1") - 1, 0)
            elif final == "K":
                del cells[col:]
            i = end + 1
            continue
        if char == "\r":
            col = 0
        elif char == "\n":
            cells, col = [], 0  # only the line the prompt sits on matters
        elif char == "\b":
            col = max(col - 1, 0)
        else:
            width = 2 if unicodedata.east_asian_width(char) in "WF" else 1
            cells.extend(" " for _ in range(col + width - len(cells)))
            cells[col] = char
            for offset in range(1, width):
                cells[col + offset] = ""
            col += width
        i += 1
    return "".join(cells).rstrip()


def drive(keystrokes: bytes, home) -> str:
    """Run the agent on a pty and type ``keystrokes`` at the prompt.

    Returns everything the child wrote up to that point — the snapshot is
    taken before ``/exit`` is sent, so it is exactly the screen the user is
    looking at mid-edit.
    """
    import pty
    import termios

    # The autouse _isolate_config fixture has already cleared the ambient
    # ANTHROPIC_* vars; HOME is redirected so the child cannot read the
    # developer's ~/.nanoPyCodeAgent/settings.json either.
    env = {**os.environ, "HOME": str(home), "ANTHROPIC_API_KEY": "sk-test"}

    pid, fd = pty.fork()
    if pid == 0:  # child: replaced by exec, or dies trying
        try:
            os.execve(sys.executable, [sys.executable, "-c", CHILD], env)
        finally:
            os._exit(1)

    attrs = termios.tcgetattr(fd)
    attrs[0] |= termios.IUTF8  # multibyte-aware ERASE, as a real terminal has
    termios.tcsetattr(fd, termios.TCSANOW, attrs)

    output = b""

    def drain(seconds: float) -> bool:
        """Read what is ready within ``seconds``; False once the child is done."""
        nonlocal output
        if not select.select([fd], [], [], seconds)[0]:
            return True  # nothing to read yet, but the child is still up
        try:
            chunk = os.read(fd, 4096)
        except OSError:  # child exited and closed its end
            return False
        if not chunk:
            return False
        output += chunk
        return True

    def wait_for(marker: bytes, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while marker not in output and time.monotonic() < deadline:
            if not drain(0.1):
                return

    def settle(quiet: float = 0.3, timeout: float = 5.0) -> None:
        """Read until the child has written nothing for ``quiet`` seconds."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            before = len(output)
            if not drain(quiet) or len(output) == before:
                return

    try:
        wait_for(PROMPT)
        assert PROMPT in output, f"never reached the prompt: {output!r}"
        os.write(fd, keystrokes)
        settle()
        screen = output.decode("utf-8", "replace")
        os.write(fd, b"/exit\r")
        wait_for(b"Bye!", timeout=5.0)
    finally:
        os.close(fd)
        os.waitpid(pid, 0)
    return screen


def test_backspace_clears_a_wide_character(tmp_path):
    # Type two CJK characters, then erase both.
    screen = drive("你好".encode() + b"\x7f\x7f", tmp_path)

    # Nothing of either character is left beside the prompt. Before the fix
    # two backspaces cleared two columns of the four they had filled, so
    # "You> 你" stayed on screen after the input was already empty.
    assert render(screen) == PROMPT.decode().rstrip()


def test_backspace_keeps_the_characters_it_should(tmp_path):
    # Erasing one of three leaves the other two intact and correctly placed.
    screen = drive("中文字".encode() + b"\x7f", tmp_path)

    assert render(screen) == "You> 中文"
