# Pi + DeepSeek Flash dev34 agent baseline

**Status: all 34 model attempts finished. The audited outcomes are 26 official
passes, six scored failures, and two unscored legacy timeout attempts. One pass
followed confirmed cancellation at the time limit; another accessed public
reference tests and a solution. No complete, uncontaminated 34-task pass rate
is claimed.** See the complete [English report](../../reports/en/pi-deepseek-flash-dev34-20261024.md),
[Simplified Chinese report](../../reports/zh-CN/pi-deepseek-flash-dev34-20261024.md),
and [audited results](../../results/pi-deepseek-flash-dev34-20261024.json). After the
October 27 repository relocation, the project volume had approximately 69 GiB
free and Docker's system volume approximately 20 GiB. The active
[v7 plan](experiment-v7.json) restores and verifies the original images one
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
- Runtime adapter checkouts: the first six attempts retain `jobs/runtime-source`,
  detached at `d6ed70a5d6a1c5b0f9b6c9d20b4a1c2b49153f67`; the remaining
  28 use `jobs/supervised-source`, detached at
  `29db8d7abbbe5f1660b8fb4d7caeeb0d183dc64d`.
- [Distribution manifest](pi-distribution.json): all files and permissions,
  pinned by `60a810111c1fd9b34b59a815fb6399c6b861017e1a2278ae881bb2a563177dd9`.
  This pins the installed local bytes; an upstream release archive checksum has
  not been independently checked. No Pi source or binary is modified.
- Model: `deepseek/deepseek-flash`, through the official OpenAI-compatible API at
  `https://api.deepseek.com`.
- Reasoning: **high**, selected before any model work. Temperature is unset.
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

The [active experiment plan](experiment-v7.json) registers all 34 fresh model trials,
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
does not certify their verifier dependencies. All 34 Pi installation checks have completed successfully, including
**QEMU's verifier dependency preflight**. The other 33 verifier profiles remain
explicitly `not_configured`; their installation success does not certify
verifier dependencies.

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
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/harbor-supervised-runtime-venv"
uv run --frozen --project jobs/supervised-source/benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev34-20261024/experiment-v7.json \
  --phase all
```

The runner executes each job through the standard repository entry point:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>
```

Each invocation runs from the frozen runtime checkout. Native jobs and input
manifests are stored under `jobs/runtime-source/jobs/` for the first six attempts
and `jobs/supervised-source/jobs/` for the remaining 28; orchestration state is
stored under `jobs/pi-deepseek-flash-dev34-20261029-supervision-v7-orchestration/`. Existing
records cannot be overwritten. A previous interrupted job requires inspection.
If preflight fails, preserve it and register any corrective installation check
separately before authorizing model work from the resulting evidence.

During execution, inspect operational stages only. Freeze all 34 outputs before
reviewing new task trajectories or hidden-test content. Keep setup and verifier
errors separate from scored task failures. Once the run finishes, produce both
complete English and Simplified Chinese reports together, plus audited results.
Both reports and the results are now complete; raw trajectories remain local.

## Original preparation evidence (before execution)

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

## October 29 MTEB image restoration

V4 successfully completed 30 installation checks, including QEMU's registered
verifier dependency profile. Before starting pair 16, the range-cache utility
rejected MTEB's multi-architecture OCI index, which is outside the utility's
documented single-platform support. No native pair-16 trial, model call, or
verifier execution occurred. This is an image-transfer failure, separate from
task setup and task scores. Its original logs remain preserved.

The original registered reference is
`alexgshaw/mteb-leaderboard@sha256:a8538f4882ff132e0a20a75be3fffc07164318a7425ad19a6b4bf5268107feb4`.
A native Docker pull reached its 600-second timeout before installing the image.
The cache utility now supports this format: it retains the original parent
index, selects exactly one Linux amd64 image manifest by digest, verifies its
size and SHA256, and downloads the original native layers through the existing
verified range path. The native configuration and compressed/uncompressed layer
digests remain unchanged. Native-platform attestations preserve their original
manifest, configuration, and in-toto payloads with digest verification. Other
platform and attestation references remain unchanged in the parent index, with
their blobs unfetched. Docker imports with
`--platform linux/amd64`, and both the utility and runner require the original
parent image/repository digest after loading. Image residency follows the same
batch-cache policy as other task images.

An isolated real-Docker import probe using the repository cache writer confirmed
that this preserves the parent image ID and repository digest. Its temporary
image was removed. See [import evidence](oci-index-import-evidence.json), which
also records the native-pull timeout. The complete Harbor workflow suite passed
**206 tests**, including native-platform selection, parent/child preservation,
and rejection of mismatched or ambiguous manifests.

The [v5 plan](experiment-v5.json) reuses
[30 strictly validated native installation records](preflight-resume-30-evidence.json),
with all prior results, bootstrap records, manifests, configurations, and model
snapshots bound by hash. Completed checks are never rerun. The initial protected
inventory includes the previous protected images and the images already present
when recovery resumes. The four remaining checks run fresh, then the unchanged
34-task model queue begins automatically after complete installation success.
The adapter source, Pi distribution, model settings, task revisions, resources,
budgets, and verifier policy remain unchanged; no adapter code changed here.

## Native-attestation completeness amendment

The initial index probe covered an absent non-native image. A subsequent
isolated four-descriptor probe matching MTEB's index shape showed that Docker's
native-platform importer also requires attestations associated with that native
image. V5 was stopped during image transfer before pair 16 or any model work.
The new cache path fetches those original attestation manifests and their config
and in-toto payloads by descriptor, verifies all sizes and SHA256 digests, and
includes them unchanged in the OCI archive. It leaves the ARM image and ARM
attestation unfetched, preserving all their original references in the index.

A real-Docker probe of the complete native-attestation graph now succeeds and
preserves the original parent image/repository digest. Its temporary image was
removed; see [attestation import evidence](oci-index-attestation-import-evidence.json).
The [v6 plan](experiment-v6.json) preserves the same 30 validated installation
records and all earlier transfer evidence, resumes the original image bytes,
and retains the unchanged model/preflight gate. No native agent or verifier
behavior changed.

The full Harbor workflow suite passed **210 tests** after native-attestation
completeness checks. All v6 source, configuration, task, image, and reused
installation-evidence hashes validated before launch.

## Installation complete; model execution started

All 34 native installation checks have completed successfully and passed strict
provenance validation; see [complete installation evidence](preflight-complete-evidence.json).
QEMU's registered verifier profile passed, and the other 33 profiles remain
`not_configured`. MTEB's original parent image/repository digest was confirmed
after the real import, and its installation check passed.

The model gate opened automatically. The first two tasks,
`adaptive-rejection-sampler` and `build-cython-ext`, have received actual model
replies and are executing tools. Operational counters alone were inspected;
new task trajectories and official hidden-test contents remain unreviewed.
The fixed queue continues with concurrency two. All 34 model outputs must
freeze before result/trace analysis and complete bilingual reporting.

## Timeout-boundary correction after the first six attempts

Operational timestamps confirmed that the adaptive rejection sampler continued
producing assistant/tool events after Harbor recorded its agent timeout and
started verification. The frozen-output boundary is invalid for that attempt.
WAL recovery also timed out without a supervision acknowledgement, so its
boundary remains unverified. Both native zero rewards and all original outputs
are preserved, with these attempts separated from ordinary scored failures.
See [timeout-boundary evidence](timeout-boundary-evidence.json); only event
timestamps and lifecycle metadata were reviewed, not solution or hidden-test
content. The other four completed native results remain unchanged.

The original scheduling controller stopped at the completed-pair boundary before
starting task seven. The corrected adapter supervises Pi and all descendants
through a Linux child subreaper, including tools that start separate sessions.
Cancellation freezes and kills that process tree and waits for confirmation
before Harbor can start its verifier. A required verifier guard refuses missing
or incomplete confirmation. Normal completion retains intentional solution
servers. Agent timeouts, model settings, prompt, tools, and Pi distribution are
unchanged; interrupted usage/cost totals are explicitly partial.

An isolated network-disabled Docker test confirmed that a detached tool stops
writing before cancellation returns; see
[supervision probe evidence](process-supervision-probe-evidence.json).
The corrected adapter will run from a newly frozen checkout. Its 28 unstarted
tasks require fresh installation checks, including a supervisor startup probe,
before any further model work. The six existing model attempts remain under
their original source reference and are never replaced.

The corrected supervision and grading boundary passed **225 Harbor tests**.
A real network-disabled Docker probe also confirmed that a detached tool stops
writing before cancellation returns. Earlier timeout attempts remain excluded
from ordinary scored-failure counts because their frozen boundary is invalid or
unverified; the amendment does not retroactively validate those outputs.

The [v7 plan](experiment-v7.json) preserves the six completed model states and
all original installation evidence. It registers a separate `pi_supervised` arm
for the 28 unstarted tasks, frozen at `29db8d7abbbe5f1660b8fb4d7caeeb0d183dc64d`.
Fourteen fresh two-task installation jobs exercise that source and its
supervisor before the remaining model work. New model configurations require
`verifier.kwargs.require_agent_quiescence=true`. The original six models retain
`jobs/runtime-source`; the remaining jobs and fresh installation evidence live
under `jobs/supervised-source/jobs/`. The original task ordering, Pi/model
settings, per-task budgets, and concurrency limit remain unchanged.

All 28 corrected-source installation checks completed successfully, including
the process-supervision startup probe. The remaining 28 model attempts then
finished without replaying or replacing any of the first six outputs.

## Completed output freeze and audit

The last model job finished at `2026-10-29T19:11:52.019151+00:00`. The
[output freeze](outputs-freeze.json) hashed 1,449 files at
`2026-10-30T13:54:30.827662+00:00`, before new solution/hidden-test-content
review. All frozen hashes, source snapshots, task revisions, Pi distribution
pins, public model configurations, pair barriers, and installation gates were
verified. Final v7 plan validation passed. No model trial or verifier was retried.

The standard summaries retain 25 normal passes, six normal scored failures,
and three `AgentTimeoutError` execution errors. Caffe's corrected-source timeout
acknowledged 13 stopped processes before all six official tests passed; the
audit accepts its raw one while retaining its exception. Sampler and WAL retain
raw zeros and analytically null outcomes because their old timeout boundaries
are invalid/unverified. Sampler also suffered a verifier dependency error before
pytest; this overlaps its boundary exclusion rather than adding another task.

Pipeline parallelism's official pass is flagged because Pi downloaded and read
public reference tests and a solution. WAL and the inference scheduler printed
the provider key into four local event/session files. Raw traces and key values
are not published; rotate the exposed key before another experiment. The full
report pair documents these findings, partial usage, and differences from the
historical Nano budget. All controllers and trial containers have exited.
