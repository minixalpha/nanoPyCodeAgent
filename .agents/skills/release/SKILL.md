---
name: release
description: >
  Use when cutting a new release of nanoPyCodeAgent (low-frequency). Does release
  work only — assumes dev notes and README were already kept in sync per-PR by
  land-pr. Picks the next version from the changelog [Unreleased], cuts the
  changelog, then — only after explicit maintainer confirmation — commits the
  changelog straight to main, pushes the vX.Y.Z tag (which triggers the PyPI +
  GitHub Release CI), and verifies the published artifacts via uvx. Triggers on
  "发布 / 发版 / cut a release / publish a release / 打 tag 发版".
---

# Release

Cut and publish a new release of **nanoPyCodeAgent**. This skill does release
work only; per-PR docs (dev notes, README) are kept in sync by the `land-pr`
skill, not here.

The version is derived from the git tag by `hatch-vcs` — **the tag is the source
of truth**. Pushing a `v*` tag triggers `.github/workflows/release.yml`
(`build` → `publish-to-pypi` → `github-release`).

## Prerequisites

`git`, `gh` (authenticated), and `uv` installed. See `docs/RELEASING.md`.

## Steps

Work entirely on `main`. `<series>` is the current series changelog file,
e.g. `docs/changelogs/0.1.x.md`.

### 1. Preflight — stop if any check fails
- `command -v git gh uv` — all present.
- `gh auth status` — authenticated.
- `git status --porcelain` — empty (clean tree).
- `<series>` has entries under `## [Unreleased]`. If empty, there is nothing to
  release — stop.

### 2. Switch to main and update
```bash
git checkout main && git pull --ff-only
```

### 3. Decide the version
Read the entries under `## [Unreleased]` and propose the next semver `X.Y.Z`:
- a `Removed`/breaking entry → major
- an `Added` entry → minor
- only `Fixed` → patch

**0.x caveat:** on `0.y.z` a minor may still contain breaking changes; treat the
proposal as a suggestion. The maintainer makes the final call at the gate (step 5).

### 4. Cut the changelog
In `<series>`:
- rename `## [Unreleased]` to `## [X.Y.Z] - <today YYYY-MM-DD>`, keeping its entries;
- add a fresh empty `## [Unreleased]` section above it.

Touch no other file — dev notes and README were synced per-PR by `land-pr`.

### 5. ⛔ Confirmation gate (mandatory)
Present to the maintainer: the proposed **version** `X.Y.Z` and the **changelog
diff** (`git diff <series>`). **Wait for explicit confirmation** (e.g. "确认 / go").
Do not commit, push, or tag until approved. If the version changes, redo step 4.

### 6. Commit and push to main
```bash
git commit -am "Release vX.Y.Z"
git push origin main
```

### 7. Tag and push (triggers the release workflow)
```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

### 8. Watch the release workflow
```bash
gh run watch
```
Confirm `build` → `publish-to-pypi` → `github-release` succeed. Publish steps are
idempotent (`--check-url`, `gh release view || create`); a failed run is safe to re-run.

### 9. Verify and report
```bash
.agents/skills/release/scripts/verify-release.sh vX.Y.Z
```
Polls official PyPI for the version, checks the GitHub Release has wheel + sdist,
and runs a `uvx` smoke test. Report success, or surface the failure verbatim.
