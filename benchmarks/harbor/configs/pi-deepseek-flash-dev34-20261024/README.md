# Pi + DeepSeek Flash dev34 agent baseline

**Status: prepared, not started.** The system disk had approximately 824 MiB
free at the last preparation check. No container installation preflight, model
trial, or official verifier has run for this experiment. The runner requires
at least 15 GiB free before starting new jobs. Existing recovery containers are
preserved pending a storage decision.

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

The [experiment plan](experiment.json) registers all 34 fresh model trials,
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
does not certify their verifier dependencies. At preparation time **all 34
native installation checks are pending**, including QEMU.

The [dependency transport](dependency-cache.compose.json) reuses the reviewed
loopback APT-index and original uv/Python release-cache sidecars. The
[release manifest](dependency-release-manifest.json) is unchanged. Cache use
preserves upstream filenames, sizes, SHA256 digests, and native package checks.
The worktree's ignored `.cache` link points to the repository's shared cache.
No task images, official tests, or package origins are substituted.

## Run after resolving disk space

From this experiment worktree's root, provide `DEEPSEEK_API_KEY` in the process
environment and use an isolated virtual environment. The command below first
runs all installation checks; models start only if those checks succeed.

```bash
export UV_PROJECT_ENVIRONMENT=/tmp/nanopy-pi-dev34-harbor-venv
uv run --frozen --project jobs/runtime-source/benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev34-20261024/experiment.json \
  --phase all
```

The runner executes each job through the standard repository entry point:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>
```

Each invocation runs from the frozen runtime checkout. Native jobs and input
manifests are stored under `jobs/runtime-source/jobs/`; orchestration state is
stored under `jobs/pi-deepseek-flash-dev34-20261024-orchestration/`. Existing
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
