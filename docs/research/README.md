# Research

Notes from surveying how other projects solve a problem, written before
building the equivalent here. Unlike changelogs and dev notes, these are not
tied to a release series — each file stands on its own, and the decisions they
feed into are recorded in [`../dev_notes/`](../dev_notes/).

These notes are **written and maintained in Chinese**; each file says so at the
top.

- [`agent_tools.md`](agent_tools.md) — the built-in tools of Pi, Claude Code,
  Codex, OpenCode and Grok Build.
- [`edit_tool.md`](edit_tool.md) — how five agent projects express a localized
  edit, and what contract a first Edit tool here should commit to.
- [`read_tool.md`](read_tool.md) — how five agent projects read files, and what
  a dedicated read tool buys over plain bash.
- [`write_tool.md`](write_tool.md) — how five agent projects write whole files,
  and why a structured write beats a heredoc.
