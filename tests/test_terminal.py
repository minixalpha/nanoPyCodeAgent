"""Tests for terminal-display sanitizing (``terminal.py``)."""

from types import SimpleNamespace

from nanopycodeagent import terminal


def test_terminal_safe_replaces_chars_stdout_cannot_encode(monkeypatch):
    # Under an ascii stdout (e.g. PYTHONIOENCODING=ascii), printing bash
    # output containing non-ASCII (like the U+FFFD replacements produced by
    # errors="replace" decoding) must degrade, not raise and kill the agent.
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(encoding="ascii"))

    assert terminal.terminal_safe("café �") == "caf? ?"


def test_terminal_safe_passes_utf8_through_unchanged(monkeypatch):
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(encoding="utf-8"))

    assert terminal.terminal_safe("café �") == "café �"


def test_terminal_safe_strips_control_characters(monkeypatch):
    # \r + erase-line sequences could rewrite the echoed "[bash]$ ..." line —
    # the user's only view of what actually executed — so control characters
    # are stripped for display; newlines and tabs stay.
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(encoding="utf-8"))

    assert terminal.terminal_safe("evil\r\x1b[2Kmasked") == "evil[2Kmasked"
    assert terminal.terminal_safe("keep\nlines\tand tabs") == "keep\nlines\tand tabs"


def test_use_color_requires_tty_and_unset_no_color(monkeypatch):
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert terminal._use_color()

    monkeypatch.setenv("NO_COLOR", "1")
    assert not terminal._use_color()

    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(isatty=lambda: False))
    assert not terminal._use_color()


def test_safe_print_tool_bg_shades_each_line_to_full_width(monkeypatch, capsys):
    # Every line carries its own set-background / erase-to-EOL / reset so the
    # shading spans the terminal width and never leaks past a line boundary.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    terminal.safe_print("[bash]$ ls\nout", tool_bg=True)

    assert capsys.readouterr().out == (
        "\x1b[48;5;236m[bash]$ ls\x1b[K\x1b[0m\n\x1b[48;5;236mout\x1b[K\x1b[0m\n"
    )


def test_safe_print_tool_bg_styles_after_sanitizing(monkeypatch, capsys):
    # An ESC smuggled in the text must be stripped as usual; only the fixed
    # sequences safe_print itself adds may reach the terminal.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    terminal.safe_print("x\x1b[0my", tool_bg=True)

    assert capsys.readouterr().out == "\x1b[48;5;236mx[0my\x1b[K\x1b[0m\n"


def test_safe_print_tool_bg_plain_without_terminal(monkeypatch, capsys):
    # Redirected output (pipes, log files) must stay free of escape codes.
    monkeypatch.setattr(terminal, "_use_color", lambda: False)

    terminal.safe_print("[bash]$ ls\nout", tool_bg=True)

    assert capsys.readouterr().out == "[bash]$ ls\nout\n"
