---
name: land-pr
description: >
  Use when merging a feature/bugfix PR into main — the everyday, no-release flow.
  Makes the PR self-contained: rewrites the PR description from the PR's own
  contents, appends a changelog [Unreleased] entry when warranted, regenerates the
  English dev notes from the Chinese source when touched, and keeps the bilingual
  README in sync. It also checks bilingual research notes and reminds the maintainer
  when their English version needs refreshing. Then — only after explicit maintainer
  confirmation — merges the PR. Does NOT tag or publish. Triggers on
  "合并 PR / land PR / 合并这个 PR / merge this PR".
---

# Land a PR

Merge a feature/bugfix PR into `main`, making the PR **self-contained** first:
its code, changelog entry, dev notes (zh + en), research-note translation status,
and README (zh + en) all accounted for within the PR. This skill never tags or
publishes — that is the `release` skill's job.

## Prerequisites

`git` and `gh` (authenticated). See `docs/RELEASING.md`.

## Steps

Work on the PR's feature branch (not `main`). `<series>` is the current series
file, e.g. `docs/changelogs/0.1.x.md` / `docs/dev_notes/{zh-CN,en}/0.1.x.md`.

### 1. Preflight — stop if any check fails
- `command -v git gh` — present.
- `gh auth status` — authenticated.
- `git status --porcelain` — empty (clean tree).
- current branch is **not** `main` (`git branch --show-current`).

### 2. Check English research notes before PR creation
If the branch modified any `docs/research/zh-CN/<name>.md`, check the
corresponding `docs/research/en/<name>.md`. Explicitly remind the maintainer
that the English version must also be translated or refreshed, and report
whether it is in sync. Do this even when the English file was already updated.
If it is missing or stale, surface that clearly before opening or landing the
PR; do not silently treat the Chinese-only change as complete.

### 3. Ensure a PR exists
```bash
gh pr view --json number,url 2>/dev/null || gh pr create --fill
```
Note the PR number for later steps.

### 4. Append a changelog entry (when warranted)
Inspect `git diff main...HEAD`. If the changes are worth recording for users, add
an entry under `## [Unreleased]` in `<series>` (changelogs) in the right group
(Added / Changed / Fixed / Removed). Purely internal/tooling changes may need
**no** entry — decide, and surface the decision at the gate.

### 5. Sync English dev notes (if the Chinese source changed)
If this PR modified `docs/dev_notes/zh-CN/<series>.md`, regenerate the whole
`docs/dev_notes/en/<series>.md` by translating the Chinese source. The English
file is generated — do not hand-edit beyond this regeneration.

### 6. Keep the bilingual README in sync
If this PR changed only one of `README.md` / `README.zh-CN.md`, mirror the change
into the other (translate/align) so the pair stays consistent. Both READMEs are
hand-written sources — propose the synced change and let the maintainer adjust the
wording at the gate; do not blindly overwrite. If both were already changed, skip.

### 7. Commit and push the sync changes
Commit any changes from steps 4–6 to the feature branch and push:
```bash
git commit -am "docs: sync changelog/dev-notes/README for this PR"
git push
```
(Skip if steps 4–6 produced no changes.)

### 8. Rewrite the PR description from scratch
Build the description **only** from the PR's actual contents — commits, changed
files, `gh pr diff`. **Do not read or extend the old description** (it may be
stale). Update via the GitHub API (`gh pr edit` can fail on deprecated Projects
Classic):
```bash
gh api repos/{owner}/{repo}/pulls/{number} -X PATCH -f body="..." --silent
```

### 9. ⛔ Confirmation gate (mandatory)
Present to the maintainer: the rewritten **PR description**, the **changelog
entry** added (or "none, because …"), and any **dev notes / README sync** done
(or a README drift warning), plus the **English research-note sync status** when
applicable. **Wait for explicit confirmation** (e.g. "确认 / go"). Do not merge
until approved.

### 10. Merge
```bash
gh pr merge --merge
```
Use the project's existing convention (merge commit; `--squash` only if asked).
Done — do **not** tag or publish.
