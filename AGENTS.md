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
