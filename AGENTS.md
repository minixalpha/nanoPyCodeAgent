# AGENTS.md

nanoPyCodeAgent — a nano code agent built from scratch in pure Python.

This is the shared project instruction file for coding agents. Codex reads
`AGENTS.md`; Claude Code reads `CLAUDE.md`, a symlink to this file.

## Skills

Project skills live in `.agents/skills/` and are auto-discovered by Codex and pi
(`.agents/skills/**/SKILL.md`); Claude Code discovers them via `.claude/skills`
(a symlink to `.agents/skills`). Use a skill by stating intent — the agent loads
the matching one:

- **Landing a PR** (everyday, no release) — merge a feature/bugfix PR into `main`:
  `.agents/skills/land-pr/SKILL.md`
- **Releasing** (cut a version, publish to PyPI + GitHub):
  `.agents/skills/release/SKILL.md`

See `docs/RELEASING.md` for the release process and prerequisites.

## Commits & PRs

All agents working in this repo MUST follow
[Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
for **commit messages** and **PR titles** (squash-merge often uses the PR
title as the commit subject).

**Format:**

```
<type>[optional scope][!]: <description>

[optional body]

[optional footer(s)]
```

**Allowed types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`,
`test`, `build`, `ci`, `chore`, `revert`.

**Rules:**

- Description: imperative mood, lowercase, no trailing period.
- Breaking changes: add `!` after the type/scope and/or include a
  `BREAKING CHANGE:` footer.
- Separate the optional body and footer(s) from the description with a
  blank line.

**Examples:**

- `feat: add streaming output to the agent loop`
- `fix(parser): handle empty tool-call arguments`
- `docs: require Conventional Commits in AGENTS.md`
- `refactor!: drop Python 3.9 support` (breaking change)
