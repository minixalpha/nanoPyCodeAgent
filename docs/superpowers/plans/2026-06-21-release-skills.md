# Release Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two project-level, cross-agent skills — `land-pr` (everyday PR merge, no publish) and `release` (cut + publish a version) — plus their discovery wiring and maintainer docs.

**Architecture:** Skills are vendor-neutral `SKILL.md` files under `.agents/skills/` (auto-discovered by Codex/pi; Claude Code via a `.claude/skills` symlink). `release` ships one helper bash script for post-publish verification; everything else is instruction-only. A root `AGENTS.md` (with `CLAUDE.md` symlinked to it) carries project instructions, and `docs/RELEASING.md` is the human maintainer guide.

**Tech Stack:** Markdown (`SKILL.md`/docs), Bash (`verify-release.sh`), git symlinks, `gh`, `uv`/`uvx`. Existing release CI: `.github/workflows/release.yml` (tag-triggered, hatch-vcs version).

## Global Constraints

- All skill/instruction deliverables — `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, `docs/RELEASING.md` — are written in **English**.
- Skill content has a **single source** at `.agents/skills/<name>/SKILL.md`; never copy content elsewhere (Claude discovers via the `.claude/skills` symlink).
- Both skills MUST contain a **mandatory human confirmation gate**: no merge (`land-pr`) and no commit/tag/publish (`release`) before explicit maintainer approval.
- `release` commits/pushes **straight to `main`** and never opens a PR; `land-pr` merges via PR and never tags or publishes.
- PR descriptions are **rewritten from scratch** from the PR's own contents (never extend the old body), updated via `gh api ... -X PATCH`.
- Per-PR doc sync (dev notes zh→en, bilingual README, changelog `[Unreleased]` append) belongs to `land-pr`; `release` does not touch dev notes or README.
- The git tag is the version source of truth (`hatch-vcs`); the release workflow's publish steps are idempotent and safe to re-run.

---

## File Structure

- `.agents/skills/release/scripts/verify-release.sh` — post-publish verification (PyPI + GitHub Release + uvx smoke). The only script.
- `.agents/skills/release/SKILL.md` — the `release` skill (instruction-only).
- `.agents/skills/land-pr/SKILL.md` — the `land-pr` skill (instruction-only).
- `.claude/skills` — symlink → `../.agents/skills` (Claude Code discovery).
- `docs/RELEASING.md` — maintainer guide (prerequisites + skill split).
- `AGENTS.md` — root project instructions, points to the skills + RELEASING.md.
- `CLAUDE.md` — symlink → `AGENTS.md` (Claude reads the same project instructions).
- `README.md` / `README.zh-CN.md` — add one pointer line each → `docs/RELEASING.md`.
- `docs/changelogs/0.1.x.md` — append an `[Unreleased]` entry for this work.

---

### Task 1: `verify-release.sh` helper script

**Files:**
- Create: `.agents/skills/release/scripts/verify-release.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: an executable script invoked as `verify-release.sh <version|vVERSION>`; exits 0 on full success, non-zero with a printed reason otherwise. Referenced by `release/SKILL.md` step 9.

- [ ] **Step 1: Write the script**

Create `.agents/skills/release/scripts/verify-release.sh`:

```bash
#!/usr/bin/env bash
# verify-release.sh — verify a published nanoPyCodeAgent release.
#
# Against the OFFICIAL PyPI index (bypassing any local mirror lag) it checks:
#   1. the version is present on PyPI
#   2. a GitHub Release exists for the tag with wheel + sdist assets
#   3. `uvx ...@VERSION` runs the console entry point (smoke test)
#
# Usage: verify-release.sh <version|vVERSION>   e.g. verify-release.sh 0.1.1
#
# Smoke test runs the entry point with no args (currently side-effect-free).
# If the entry point ever gains required args/interaction, adjust step 3.
set -euo pipefail

PACKAGE="nanoPyCodeAgent"
PYPI_JSON="https://pypi.org/pypi/${PACKAGE}/json"
PYPI_INDEX="https://pypi.org/simple/"
POLL_TIMEOUT="${VERIFY_TIMEOUT:-300}"   # seconds budget per polling stage
POLL_INTERVAL="${VERIFY_INTERVAL:-15}"  # seconds between polls

usage() {
  cat <<'EOF'
Usage: verify-release.sh <version|vVERSION>

Verifies a published release against official PyPI + GitHub Release:
  1. version present on PyPI (pinned to pypi.org, ignores mirrors)
  2. GitHub Release for the tag has wheel + sdist assets
  3. uvx smoke test runs the published artifact

Env overrides:
  VERIFY_TIMEOUT   seconds to wait per polling stage (default 300)
  VERIFY_INTERVAL  seconds between polls (default 15)
EOF
}

if [[ $# -ne 1 ]]; then usage; exit 1; fi
if [[ "$1" == "-h" || "$1" == "--help" ]]; then usage; exit 0; fi

version="${1#v}"     # strip leading v -> 0.1.1
tag="v${version}"    # normalized tag -> v0.1.1

log()  { printf '\n=== %s ===\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# 1. PyPI presence (poll, pinned to official index) -----------------------
log "Checking PyPI for ${PACKAGE} ${version}"
deadline=$(( $(date +%s) + POLL_TIMEOUT ))
until curl -fsSL "$PYPI_JSON" | grep -q "\"${version}\""; do
  (( $(date +%s) >= deadline )) && fail "version ${version} not on PyPI after ${POLL_TIMEOUT}s"
  printf 'not on PyPI yet; retrying in %ss...\n' "$POLL_INTERVAL"; sleep "$POLL_INTERVAL"
done
printf 'OK: %s %s is on PyPI\n' "$PACKAGE" "$version"

# 2. GitHub Release + assets ----------------------------------------------
log "Checking GitHub Release ${tag}"
gh release view "$tag" >/dev/null 2>&1 || fail "no GitHub Release for ${tag}"
assets="$(gh release view "$tag" --json assets --jq '.assets[].name')"
grep -q '\.whl$'     <<<"$assets" || fail "Release ${tag} missing a wheel (.whl) asset"
grep -q '\.tar\.gz$' <<<"$assets" || fail "Release ${tag} missing an sdist (.tar.gz) asset"
printf 'OK: GitHub Release %s has wheel + sdist\n' "$tag"

# 3. uvx smoke test (official index, with retries) ------------------------
log "Smoke-testing uvx ${PACKAGE}@${version}"
deadline=$(( $(date +%s) + POLL_TIMEOUT ))
until uvx --index "$PYPI_INDEX" --from "${PACKAGE}@${version}" "$PACKAGE" >/dev/null 2>&1; do
  (( $(date +%s) >= deadline )) && fail "uvx smoke test failed for ${PACKAGE}@${version} after ${POLL_TIMEOUT}s"
  printf 'uvx not ready (index propagation?); retrying in %ss...\n' "$POLL_INTERVAL"; sleep "$POLL_INTERVAL"
done
printf 'OK: uvx smoke test passed for %s@%s\n' "$PACKAGE" "$version"

log "Release ${tag} verified ✔"
```

- [ ] **Step 2: Make it executable**

Run: `chmod +x .agents/skills/release/scripts/verify-release.sh`

- [ ] **Step 3: Verify bash syntax**

Run: `bash -n .agents/skills/release/scripts/verify-release.sh && echo SYNTAX_OK`
Expected: prints `SYNTAX_OK` (exit 0).

- [ ] **Step 4: Verify argument handling (no network)**

Run: `.agents/skills/release/scripts/verify-release.sh --help; echo "help=$?"; .agents/skills/release/scripts/verify-release.sh; echo "noarg=$?"`
Expected: usage text twice; `help=0` then `noarg=1`.

- [ ] **Step 5: Optional lint (if available)**

Run: `command -v shellcheck >/dev/null && shellcheck .agents/skills/release/scripts/verify-release.sh || echo "shellcheck not installed; skipped"`
Expected: no warnings, or the skip message.

- [ ] **Step 6: Commit**

```bash
git add .agents/skills/release/scripts/verify-release.sh
git commit -m "feat: add verify-release.sh for the release skill"
```

---

### Task 2: `release` SKILL.md

**Files:**
- Create: `.agents/skills/release/SKILL.md`

**Interfaces:**
- Consumes: `.agents/skills/release/scripts/verify-release.sh` (Task 1).
- Produces: the `release` skill, discoverable by `description`. Referenced by `AGENTS.md` (Task 6) and `docs/RELEASING.md` (Task 5).

- [ ] **Step 1: Write the skill file**

Create `.agents/skills/release/SKILL.md`:

````markdown
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
````

- [ ] **Step 2: Verify frontmatter has name + description**

Run: `grep -qE '^name: release$' .agents/skills/release/SKILL.md && grep -qE '^description:' .agents/skills/release/SKILL.md && echo FM_OK`
Expected: prints `FM_OK`.

- [ ] **Step 3: Verify the referenced script path exists**

Run: `test -x .agents/skills/release/scripts/verify-release.sh && echo SCRIPT_OK`
Expected: prints `SCRIPT_OK`.

- [ ] **Step 4: Commit**

```bash
git add .agents/skills/release/SKILL.md
git commit -m "feat: add release skill (SKILL.md)"
```

---

### Task 3: `land-pr` SKILL.md

**Files:**
- Create: `.agents/skills/land-pr/SKILL.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the `land-pr` skill, discoverable by `description`. Referenced by `AGENTS.md` (Task 6) and `docs/RELEASING.md` (Task 5).

- [ ] **Step 1: Write the skill file**

Create `.agents/skills/land-pr/SKILL.md`:

````markdown
---
name: land-pr
description: >
  Use when merging a feature/bugfix PR into main — the everyday, no-release flow.
  Makes the PR self-contained: rewrites the PR description from the PR's own
  contents, appends a changelog [Unreleased] entry when warranted, regenerates the
  English dev notes from the Chinese source when touched, and keeps the bilingual
  README in sync. Then — only after explicit maintainer confirmation — merges the
  PR. Does NOT tag or publish. Triggers on
  "合并 PR / land PR / 合并这个 PR / merge this PR".
---

# Land a PR

Merge a feature/bugfix PR into `main`, making the PR **self-contained** first:
its code, changelog entry, dev notes (zh + en), and README (zh + en) all in sync
within the PR. This skill never tags or publishes — that is the `release` skill's job.

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

### 2. Ensure a PR exists
```bash
gh pr view --json number,url 2>/dev/null || gh pr create --fill
```
Note the PR number for later steps.

### 3. Append a changelog entry (when warranted)
Inspect `git diff main...HEAD`. If the changes are worth recording for users, add
an entry under `## [Unreleased]` in `<series>` (changelogs) in the right group
(Added / Changed / Fixed / Removed). Purely internal/tooling changes may need
**no** entry — decide, and surface the decision at the gate.

### 4. Sync English dev notes (if the Chinese source changed)
If this PR modified `docs/dev_notes/zh-CN/<series>.md`, regenerate the whole
`docs/dev_notes/en/<series>.md` by translating the Chinese source. The English
file is generated — do not hand-edit beyond this regeneration.

### 5. Keep the bilingual README in sync
If this PR changed only one of `README.md` / `README.zh-CN.md`, mirror the change
into the other (translate/align) so the pair stays consistent. Both READMEs are
hand-written sources — propose the synced change and let the maintainer adjust the
wording at the gate; do not blindly overwrite. If both were already changed, skip.

### 6. Commit and push the sync changes
Commit any changes from steps 3–5 to the feature branch and push:
```bash
git commit -am "docs: sync changelog/dev-notes/README for this PR"
git push
```
(Skip if steps 3–5 produced no changes.)

### 7. Rewrite the PR description from scratch
Build the description **only** from the PR's actual contents — commits, changed
files, `gh pr diff`. **Do not read or extend the old description** (it may be
stale). Update via the GitHub API (`gh pr edit` can fail on deprecated Projects
Classic):
```bash
gh api repos/{owner}/{repo}/pulls/{number} -X PATCH -f body="..." --silent
```

### 8. ⛔ Confirmation gate (mandatory)
Present to the maintainer: the rewritten **PR description**, the **changelog
entry** added (or "none, because …"), and any **dev notes / README sync** done
(or a README drift warning). **Wait for explicit confirmation** (e.g. "确认 / go").
Do not merge until approved.

### 9. Merge
```bash
gh pr merge --merge
```
Use the project's existing convention (merge commit; `--squash` only if asked).
Done — do **not** tag or publish.
````

- [ ] **Step 2: Verify frontmatter has name + description**

Run: `grep -qE '^name: land-pr$' .agents/skills/land-pr/SKILL.md && grep -qE '^description:' .agents/skills/land-pr/SKILL.md && echo FM_OK`
Expected: prints `FM_OK`.

- [ ] **Step 3: Commit**

```bash
git add .agents/skills/land-pr/SKILL.md
git commit -m "feat: add land-pr skill (SKILL.md)"
```

---

### Task 4: `.claude/skills` symlink (Claude Code discovery)

**Files:**
- Create: `.claude/skills` (symlink → `../.agents/skills`)

**Interfaces:**
- Consumes: `.agents/skills/` (Tasks 1–3).
- Produces: Claude-Code-discoverable skills at `.claude/skills/<name>/SKILL.md` via the symlink.

- [ ] **Step 1: Create the symlink**

```bash
mkdir -p .claude
ln -s ../.agents/skills .claude/skills
```

- [ ] **Step 2: Verify the link target and resolution**

Run: `readlink .claude/skills; test -f .claude/skills/release/SKILL.md && test -f .claude/skills/land-pr/SKILL.md && echo LINK_OK`
Expected: prints `../.agents/skills` then `LINK_OK`.

- [ ] **Step 3: Confirm git records it as a symlink (mode 120000)**

Run: `git add .claude/skills && git ls-files -s .claude/skills`
Expected: line begins with `120000` (a symlink, not a copied dir).

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: symlink .claude/skills to .agents/skills"
```

> Fallback (only if a later real-world check shows Claude Code does not resolve a
> symlinked skills dir): replace with per-skill symlinks `.claude/skills/<name>`
> → `../../.agents/skills/<name>`, or thin pointer `SKILL.md` files carrying the
> same frontmatter. Decide from observed behavior; do not pre-optimize.

---

### Task 5: `docs/RELEASING.md` maintainer guide

**Files:**
- Create: `docs/RELEASING.md`

**Interfaces:**
- Consumes: references the two skills (Tasks 2–3) and `release.yml`.
- Produces: maintainer guide; linked from `AGENTS.md` (Task 6) and both READMEs (Task 8).

- [ ] **Step 1: Write the file**

Create `docs/RELEASING.md`:

```markdown
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
```

- [ ] **Step 2: Verify it references both skills**

Run: `grep -q 'land-pr' docs/RELEASING.md && grep -q 'release' docs/RELEASING.md && echo DOC_OK`
Expected: prints `DOC_OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/RELEASING.md
git commit -m "docs: add RELEASING.md maintainer guide"
```

---

### Task 6: root `AGENTS.md`

**Files:**
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: `.agents/skills/land-pr|release/SKILL.md` (Tasks 2–3), `docs/RELEASING.md` (Task 5).
- Produces: project instruction file; symlink target for `CLAUDE.md` (Task 7).

- [ ] **Step 1: Write the file**

Create `AGENTS.md`:

```markdown
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
```

- [ ] **Step 2: Verify references resolve**

Run: `for p in .agents/skills/land-pr/SKILL.md .agents/skills/release/SKILL.md docs/RELEASING.md; do test -e "$p" || { echo "MISSING $p"; exit 1; }; done; echo REFS_OK`
Expected: prints `REFS_OK`.

- [ ] **Step 3: Commit**

```bash
git add AGENTS.md
git commit -m "feat: add root AGENTS.md project instructions"
```

---

### Task 7: `CLAUDE.md` symlink → `AGENTS.md`

**Files:**
- Create: `CLAUDE.md` (symlink → `AGENTS.md`)

**Interfaces:**
- Consumes: `AGENTS.md` (Task 6).
- Produces: project-level `CLAUDE.md` for Claude Code, same content as `AGENTS.md`.

- [ ] **Step 1: Create the symlink**

```bash
ln -s AGENTS.md CLAUDE.md
```

- [ ] **Step 2: Verify link + resolution**

Run: `readlink CLAUDE.md; head -1 CLAUDE.md`
Expected: prints `AGENTS.md` then `# AGENTS.md`.

- [ ] **Step 3: Confirm git records it as a symlink**

Run: `git add CLAUDE.md && git ls-files -s CLAUDE.md`
Expected: line begins with `120000`.

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: symlink CLAUDE.md to AGENTS.md"
```

---

### Task 8: README pointers (en + zh)

**Files:**
- Modify: `README.md` (append a Releasing section)
- Modify: `README.zh-CN.md` (append a 发布 section)

**Interfaces:**
- Consumes: `docs/RELEASING.md` (Task 5).
- Produces: discoverable pointer from both READMEs to the maintainer guide.

- [ ] **Step 1: Append to `README.md`**

Append at end of file:

```markdown

## Releasing

For maintainers: see [docs/RELEASING.md](docs/RELEASING.md) for the release process and prerequisites.
```

- [ ] **Step 2: Append to `README.zh-CN.md`**

Append at end of file:

```markdown

## 发布

维护者请参阅 [docs/RELEASING.md](docs/RELEASING.md) 了解发布流程与前置条件。
```

- [ ] **Step 3: Verify both pointers exist**

Run: `grep -q 'docs/RELEASING.md' README.md && grep -q 'docs/RELEASING.md' README.zh-CN.md && echo PTR_OK`
Expected: prints `PTR_OK`.

- [ ] **Step 4: Commit**

```bash
git add README.md README.zh-CN.md
git commit -m "docs: link README to RELEASING.md (en + zh)"
```

---

### Task 9: changelog `[Unreleased]` entry

**Files:**
- Modify: `docs/changelogs/0.1.x.md` (add an entry under `## [Unreleased]`)

**Interfaces:**
- Consumes: nothing.
- Produces: the changelog entry the next `release` will cut into a version.

- [ ] **Step 1: Add the entry**

Under `## [Unreleased]` in `docs/changelogs/0.1.x.md`, add:

```markdown
### Added
- Project-level agent skills `land-pr` and `release` (in `.agents/skills/`, cross-agent: Claude Code / Codex / pi), with a `verify-release.sh` post-publish check, a root `AGENTS.md`, and `docs/RELEASING.md`.
```

- [ ] **Step 2: Verify**

Run: `grep -q 'land-pr' docs/changelogs/0.1.x.md && echo CL_OK`
Expected: prints `CL_OK`.

- [ ] **Step 3: Commit**

```bash
git add docs/changelogs/0.1.x.md
git commit -m "docs: add changelog Unreleased entry for the release skills"
```

---

## Finishing: dogfood the merge

After all tasks pass, **merge this PR using the `land-pr` skill itself**
(dogfood). Expectations on this branch: both READMEs were changed together
(no drift warning), the changelog already has an entry (step 3 of `land-pr`
finds it present and skips), no dev-notes zh changed (step 4 skips). `land-pr`
then rewrites the PR description from the branch contents, runs the confirmation
gate, and merges. Do **not** run `release` — this work is not a version bump.
