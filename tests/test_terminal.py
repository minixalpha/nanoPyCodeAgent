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
