# Pi + DeepSeek Flash dev34 agent baseline

**Status: 16/34 Pi installation checks passed; resuming the remaining 18 on
October 28. No model outputs yet.** After the
repository relocation, the project volume has approximately 69 GiB free and
Docker's system volume approximately 20 GiB. The active
[v4 plan](experiment-v4.json) restores and verifies the original images one
batch at a time, then removes only image references absent from the initial
Docker inventory. Existing recovery containers and their images are preserved.
Model work remains gated on successful native installation checks for all tasks.
The [original registration](experiment.json) remains unchanged and unexecuted.

This experiment establishes the first external-agent baseline on the existing
34-task development pool. The [selection](selection.json) is byte-identical to
the October 12 selection. All task revisions and registered task-file hashes
match, and all 34 local Docker image identities and repository digests were
checked against the October 19 registration. The other 55 tasks remain unopened.

## Frozen agent and model

- Agent: upstream Pi **1.4.0**, using the existing local binary distribution.
- Runtime adapter checkout: `jobs/runtime-source`, detached at
  `d6ed70a5d6a1c5b0f9b6c9d20b4a1c2b49153f67`.
- [Distribution manifest](pi-distribution.json): all files and permissions,
  pinned by `60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9`.
  This pins the installed local bytes; an upstream release archive checksum has
  not been independently checked. No Pi source or binary is modified.
- Model: `deepseek/deepseek-flash`, through the official OpenAI-compatible API at
  `https://api.deepseek.com`.
- Reasoning: **high**, provisionally selected pending maintainer preference,
  before any model work. Temperature is unset.
- [Public model configuration](pi-models.json): the local DeepSeek provider's
  capabilities and compatibility settings, with credentials replaced by the
  `${DEEPSEEK_API_KEY}` environment reference. No other provider is copied.

[DeepSeek's official documentation](https://api-docs.deepseek.com/quick_start/agent_integrations/)
was checked on October 24 and maps `deepseek-flash` to
DeepSeek-V4.1-Flash-1017. This alias is mutable. The registered model metadata
declares a 1,000,000-token context and 384,000-token output ceiling. Actual
generation behavior remains Pi's native behavior. The configuration retains
peak-rate token estimates; [official pricing](https://api-docs.deepseek.com/quick_start/pricing/)
also has off-peak discounts, so these estimates are not reconciled bills.

Pi retains its own system prompt, default tools, context compaction, and internal
request retry behavior. Personal extensions, skills, session history, settings,
and other providers are not copied. Model catalog refresh is disabled with
`--offline`; model requests still reach the official API. The adapter keeps
native sessions and completed JSON events rather than generating an ATIF trace.

## Task, budget, and infrastructure policy

The [active experiment plan](experiment-v4.json) registers all 34 fresh model trials,
their fixed order, configurations, source revision, distribution, infrastructure
hashes, and installation checks. Maximum concurrency is two, with consecutive
pair barriers and no whole-trial retries. Preserve every failed setup or launch
attempt; do not replace an existing model output after seeing its outcome.

Each task keeps its original image, resource limits, native agent timeout, test
scripts, package sources, and native verifier time limit. Setup separately
allows 1,800 seconds. Only verifier timeouts may retry, at most three total
attempts against the same output. Dependency-error recovery is disabled.

This run uses stock Pi loop and generation behavior. It does not inject Nano's
100-reply cap or its native-timeout-minus-180-seconds work budget and finalization
reminders. The historical Nano configuration requested 65,536 output tokens;
the Pi model metadata retains the local 384,000-token ceiling. Report these
differences when comparing scores: this is an agent baseline, not an experiment
that isolates harness behavior under identical internal budgets.

Fresh installation-only checks must finish for all 34 tasks before any model
trial. QEMU has the reviewed `qemu-alpine-ssh-v1` verifier profile. The other
33 tasks must explicitly report `not_configured`; successful Pi installation
does not certify their verifier dependencies. Sixteen Pi installation checks
have completed successfully; **18 remain pending, including QEMU's verifier
dependency preflight**.

The [dependency transport](dependency-cache.compose.json) reuses the reviewed
loopback APT-index and original uv/Python release-cache sidecars. The
[release manifest](dependency-release-manifest.json) is unchanged. Cache use
preserves upstream filenames, sizes, SHA256 digests, and native package checks.
The worktree's ignored `.cache` link points to the repository's shared cache.
No task images, official tests, or package origins are substituted.

## Execute

From this experiment worktree's root, provide `DEEPSEEK_API_KEY` in the process
environment and use an isolated virtual environment. The command below first
runs all installation checks; models start only if those checks succeed.

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/harbor-runtime-venv"
uv run --frozen --project jobs/runtime-source/benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev34-20261024/experiment-v4.json \
  --phase all
```

The runner executes each job through the standard repository entry point:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>
```

Each invocation runs from the frozen runtime checkout. Native jobs and input
manifests are stored under `jobs/runtime-source/jobs/`; orchestration state is
stored under `jobs/pi-deepseek-flash-dev34-20261028-transport-v4-orchestration/`. Existing
records cannot be overwritten. A previous interrupted job requires inspection.
If preflight fails, preserve it and register any corrective installation check
separately before authorizing model work from the resulting evidence.

During execution, inspect operational stages only. Freeze all 34 outputs before
reviewing new task trajectories or hidden-test content. Keep setup and verifier
errors separate from scored task failures. Once the run finishes, produce both
complete English and Simplified Chinese reports together, plus audited results;
no result report exists while the experiment remains unstarted.

## Preparation evidence

- The Harbor workflow suite passed **187 tests** before the final usage/error
  accounting changes; all **51 relevant tests** passed after those changes.
- All **35** Harbor configurations and the frozen experiment plan validated.
- The actual Pi 1.4.0 binary accepted the registered provider via
  `--offline --list-models deepseek-flash`, using a dummy key and no model call.
- All **34** registered task-file sets and Docker image identities matched the
  previous run. See [image evidence](image-digests.json).
- Container dependency preflight: **pending**. Model trials: **0/34 started**.

## October 27 storage amendment

The v2 registration splits installation into 17 consecutive two-task batches.
Before each installation or model batch, the runner restores missing images
using their original repository digests and checks their recorded identities.
It requires 15 GiB free on Docker's actual storage volume before restoration.
After each batch, it removes newly introduced image references without force;
Docker must retain images referenced by any remaining container. Raw task files,
logs, official tests, original images, and frozen outputs remain unchanged.
Initial Docker image IDs and all restore/verify/evict events are recorded in the
orchestration directory. This changes image-cache residency, not image contents.
The existing cache sidecars remain isolated and unchanged.

The agent runtime, Pi 1.4.0 distribution, high reasoning setting, model provider,
34 task revisions, model ordering, resources, and timeout policies are unchanged.
Canonical paths in `storage-v2/` reflect the repository relocation. The isolated
virtual environment resides on the project volume. The official model alias was
rechecked on October 27 and still maps to DeepSeek-V4.1-Flash-1017. All 51 v2 job
configurations and complete task-file sets validated; 55 relevant workflow tests
passed, including image identity, preservation, eviction, and disk-space guards.

The v2 controller was stopped during the first stalled Docker layer download,
before any native job or model call. Its launch and image-download evidence
remain local. The active v3 plan uses the existing SHA256-verified range-cache
utility to restore the same registered images, then applies the same batch
eviction policy. No task configuration, agent output, or verifier policy changed.
All 56 relevant workflow tests passed after this amendment.

## October 28 image-transfer recovery

V3 completed eight installation jobs covering 16 tasks, all successfully.
It then stopped while restoring QEMU's original 991,743,246-byte image layer:
253 one-MiB ranges remained saved, with no QEMU native trial or model work.
The original logs reported a registry `HTTPError` but did not preserve its
status code, so the exact historical HTTP status is unknown. A fresh-token
manifest request succeeded and matched the registered image digest.

The image-cache utility previously held one anonymous pull token for the entire
image transfer. It now refreshes expiring tokens and retries once with fresh
credentials on HTTP 401, coordinating refreshes between range workers. Saved
ranges remain resumable; complete blobs still require full SHA256 verification.
Sanitized failures retain HTTP status codes without exposing signed URLs.
These fixes address token expiry during long transfers; the original failure's
status cannot be established retrospectively.

The [v4 plan](experiment-v4.json) binds the 16 successful native installation
records through [resume evidence](preflight-resume-evidence.json), including
results, bootstrap records, original input configurations, source manifests,
and Pi model snapshots. The strict existing acceptance checks validated every
record as installation-only from the same frozen runtime and distribution.
The v4 orchestration directory links to the original eight completed job
records; the runner skips their image preparation and native execution.
All remaining installations are fresh. Previous transfer failures and launch
evidence remain preserved. Model work is still gated on all 34 successful
installation checks, and the agent/model/task/budget/verifier policies are unchanged.
The complete Harbor workflow suite passed **199 tests** after these changes.
