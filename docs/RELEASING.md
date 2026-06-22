# Releasing

How nanoPyCodeAgent is maintained and released. Two agent skills drive the flow;
this document is the human reference.

## Prerequisites (maintainers)

- **`uv`** — build / publish / run (`uvx`).
- **`gh`** — GitHub CLI, authenticated (`gh auth status`).
- **`git`**.
- One-time: PyPI Trusted Publishing must be configured for this repo (see the
  header comment in `.github/workflows/release.yml`).

## Two skills

| Skill | When | What it does | Publishes? |
|-------|------|--------------|------------|
| `land-pr` | Every feature/bugfix PR | Rewrites the PR description, appends a changelog `[Unreleased]` entry when warranted, syncs dev notes (zh→en) and the bilingual README, then merges after confirmation. | No |
| `release` | Cutting a version | Picks the next version from `[Unreleased]`, cuts the changelog, commits to `main`, pushes the `vX.Y.Z` tag (triggering CI), and verifies PyPI + GitHub Release. | Yes |

The changelog flows across both: `land-pr` accumulates entries under
`[Unreleased]`; `release` turns `[Unreleased]` into a dated version section.

## How it publishes

Pushing a `v*` tag triggers `.github/workflows/release.yml`:
`build` → `publish-to-pypi` (PyPI Trusted Publishing / OIDC) → `github-release`.
The version is derived from the git tag by `hatch-vcs`.

## Triggering the skills

State intent to your agent — "land this PR" / "合并 PR", or "cut a release" /
"发布". The agent loads the matching skill from `.agents/skills/`.
