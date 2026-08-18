# Research

Notes from surveying how other projects solve a problem, written before
building the equivalent here. Unlike changelogs and dev notes, these are not
tied to a release series — each file stands on its own, and the decisions they
feed into are recorded in [`../dev_notes/`](../dev_notes/).

Research notes are bilingual, split by language:

- [`zh-CN/`](zh-CN/) — **hand-written Chinese source** (source of truth)
- [`en/`](en/) — **English, generated from the Chinese source** (do not edit by
  hand)

When a pull request adds or updates a Chinese source, its corresponding English
version also needs to be translated or refreshed. The agent preparing or
landing the pull request must remind the user and report whether the two
versions are in sync.

- Built-in tools of Pi, Claude Code, Codex, OpenCode, and Grok Build:
  [English](en/agent_tools.md) | [Chinese](zh-CN/agent_tools.md)
- How five agent projects express a localized edit, and what contract a first
  Edit tool here should commit to:
  [English](en/edit_tool.md) | [Chinese](zh-CN/edit_tool.md)
- How five agent projects read files, and what a dedicated read tool buys over
  plain Bash:
  [English](en/read_tool.md) | [Chinese](zh-CN/read_tool.md)
- How five agent projects write whole files, and why a structured write beats a
  heredoc:
  [English](en/write_tool.md) | [Chinese](zh-CN/write_tool.md)
- Which code-agent benchmarks six 2026 model releases reported, which ones fit
  this project, and what it still needs to run them:
  [English](en/code_agent_benchmark.md) | [Chinese](zh-CN/code_agent_benchmark.md)
- What Terminal-Bench 2.1, SWE-bench Verified, and NL2Repo-Bench actually
  require of a headless agent, read down to the source level:
  [English](en/benchmark_headless_interface.md) | [Chinese](zh-CN/benchmark_headless_interface.md)
