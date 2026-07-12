"""Tests for tool background shading (``terminal.py``)."""

from types import SimpleNamespace

from nanopycodeagent import terminal


def test_use_color_requires_tty_and_unset_no_color(monkeypatch):
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert terminal._use_color()

    monkeypatch.setenv("NO_COLOR", "1")
    assert not terminal._use_color()

    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setattr(terminal.sys, "stdout", SimpleNamespace(isatty=lambda: False))
    assert not terminal._use_color()


def test_print_tool_shades_each_line_to_full_width(monkeypatch, capsys):
    # Every line carries its own set-background / erase-to-EOL / reset so the
    # shading spans the terminal width and never leaks past a line boundary.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    terminal.print_tool("[bash]$ ls\nout")

    assert capsys.readouterr().out == (
        "\x1b[48;5;236m[bash]$ ls\x1b[K\x1b[0m\n\x1b[48;5;236mout\x1b[K\x1b[0m\n"
    )


def test_print_tool_plain_without_terminal(monkeypatch, capsys):
    # Redirected output (pipes, log files) must stay free of escape codes.
    monkeypatch.setattr(terminal, "_use_color", lambda: False)

    terminal.print_tool("[bash]$ ls\nout")

    assert capsys.readouterr().out == "[bash]$ ls\nout\n"
