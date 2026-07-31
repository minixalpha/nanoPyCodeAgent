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


def test_print_tool_use_shades_each_line_to_full_width(monkeypatch, capsys):
    # Every line carries its own set-background / erase-to-EOL / reset so the
    # shading spans the terminal width and never leaks past a line boundary.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    terminal.print_tool_use("[bash]$ ls")

    assert capsys.readouterr().out == "\x1b[48;5;238m[bash]$ ls\x1b[K\x1b[0m\n"


def test_print_tool_output_uses_a_darker_shade_than_the_call(monkeypatch, capsys):
    # The echoed call and its output sit on different shades so where one
    # ends and the other begins is visible at a glance.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    terminal.print_tool_output("a\nb")

    assert capsys.readouterr().out == (
        "\x1b[48;5;236ma\x1b[K\x1b[0m\n\x1b[48;5;236mb\x1b[K\x1b[0m\n"
    )
    assert terminal._OUTPUT_BG != terminal._USE_BG


def test_print_tool_plain_without_terminal(monkeypatch, capsys):
    # Redirected output (pipes, log files) must stay free of escape codes.
    monkeypatch.setattr(terminal, "_use_color", lambda: False)

    terminal.print_tool_use("[bash]$ ls")
    terminal.print_tool_output("out")

    assert capsys.readouterr().out == "[bash]$ ls\nout\n"


def test_spinner_draws_frames_and_erases_itself(monkeypatch, capsys):
    # The spinner redraws one line in place with carriage returns; stopping
    # erases the line so the transcript keeps no trace of the animation.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    spinner = terminal.Spinner("Working...")
    spinner.start()
    spinner.stop()

    out = capsys.readouterr().out
    assert out.startswith("\r⠋ Working...")  # the first frame drew immediately
    assert out.endswith("\r\x1b[K")  # and stopping erased the line


def test_spinner_stop_is_idempotent(monkeypatch, capsys):
    # An early stop (first streamed token) followed by the context-manager
    # exit must erase the line exactly once.
    monkeypatch.setattr(terminal, "_use_color", lambda: True)

    with terminal.Spinner() as spinner:
        spinner.stop()

    assert capsys.readouterr().out.count("\x1b[K") == 1


def test_spinner_silent_without_terminal(monkeypatch, capsys):
    # Redirected output (pipes, log files) must stay free of animation.
    monkeypatch.setattr(terminal, "_use_color", lambda: False)

    with terminal.Spinner():
        pass

    assert capsys.readouterr().out == ""
