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

## Language

Write everything in **English** by default — source code (identifiers,
comments, string literals), commit messages, PR titles/descriptions, changelog
entries, and Markdown documentation.

The **only** exception is documentation explicitly designated as Chinese:

- `README.zh-CN.md` and any other `*.zh-CN.*` file.
- Files under a `zh-CN/` directory (e.g. `docs/dev_notes/zh-CN/`).
- Design specs under `docs/superpowers/specs/` — the prose may be Chinese for
  review convenience, but the deliverables the spec produces (code under
  `src/`, tests, and any English documentation) remain English.
- Any document with an explicit requirement to be written in Chinese.

Everything outside that list — including code under `src/`, this file, and all
other docs — is English.

### Bilingual research notes

Research notes are bilingual:

- `docs/research/zh-CN/` contains the Chinese sources of truth.
- `docs/research/en/` contains English versions generated from the Chinese
  sources; regenerate the whole corresponding file instead of hand-editing it.

When a change to a Chinese research source is headed into a pull request, the
agent MUST remind the user that the corresponding English version also needs to
be translated or refreshed. Before opening or landing the PR, report whether
the English version is in sync, even when it has already been updated.

## Commits & PRs

### Branch and pull request workflow

All non-release changes MUST be made on a dedicated branch and merged into
`main` through a GitHub pull request.

- Before modifying repository files, agents MUST verify that the current branch
  is not `main`. If it is `main`, create or switch to a dedicated branch first.
- Agents MUST NOT commit directly to `main` or push non-release commits to
  `origin/main`.
- Open a pull request targeting `main`, and use the `land-pr` skill to merge it.
  Do not merge without the skill's mandatory maintainer confirmation.
- If work was accidentally started on `main`, move the changes to a dedicated
  branch before committing or pushing them.

The sole exception is the release workflow in `.agents/skills/release/SKILL.md`.
Only when the maintainer explicitly requests a release may that skill commit and
push its release-only changes directly to `main`, and only after its mandatory
confirmation gate. Documentation, chores, hotfixes, and all other work still
require a branch and pull request.

### Commit and PR title format

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
