# DeepSeek Harness on the Pi 34-task development pool

Status: all 34 installation checks passed. Model execution has not started;
using the existing Pi-configured DeepSeek credential is awaiting explicit
maintainer authorization after automatic approval review blocked that source.
The [preflight audit](preflight-evidence.json) records SDK initialization and
process supervision success for every task, two passed verifier dependency
profiles, and 32 explicitly unconfigured profiles. The official keyless SDK smoke and corrected WAL container
installation smoke passed. The first WAL setup failure is preserved in
[setup evidence](setup-evidence.json).

This run uses the complete existing Pi development pool. `selection.json`,
original task revisions and file hashes, image identities, resources, and
native timeouts are preserved. No tasks are selected or replaced by outcome.
The other 55 tasks remain unopened.

The upstream source is the user's clean local `deepseek-harness` checkout at
`f3803c96974ad4a94195fb97e5c637e9c2a3afe3` (`0.2.2-alpha.2`). The source archive
SHA256 is `0a851c705c243519cc573d077d8cf23295591498825d82b795b43b37255d43e4`.
Builds use an isolated copy under `jobs/deepseek-harness-build-f3803c9/` and the
upstream frozen pnpm lockfile. The original checkout is unchanged.

The selected `sdk-minimal` profile follows the upstream `BENCHMARK.md` and
Python SDK guide. It retains the upstream system prompt, persistent bash,
image reading, working-directory tool, automatic compaction, request retries,
and generation defaults. Each task receives an isolated Harness home and
session. No personal instructions, extensions, settings, or previous sessions
are copied. The SDK is driven by the reusable repository adapter through the
standard Harbor entry point.

The model is `deepseek/deepseek-flash`, with `high` reasoning and the official
Messages endpoint `https://api.deepseek.com/anthropic`. The official API guide
checked on October 30 still maps this mutable alias to DeepSeek-V4.1-Flash-1017.
Temperature and SDK `max_tokens` remain unset; the upstream provider default is
256,000 output tokens. Pi used OpenAI-compatible requests and model metadata
with a 384,000-token ceiling. This compares complete agent configurations; it
does not isolate the causal effect of the harness under identical generation
budgets. Neither configuration imposes Nano's 100-reply limit or finalization
reminders.

All tasks require fresh installation-only checks before the model queue opens.
These checks install hash-pinned SDK/runtime wheels and their Python
dependencies, initialize the actual SDK profile/provider/model without a task
prompt, and exercise the Linux process supervisor. QEMU and PyTorch model
recovery additionally run their reviewed verifier dependency profiles. The other 32 verifier profiles are
explicitly `not_configured`; agent installation success does not certify them.

The existing APT-index and original uv/Python release caches retain upstream
sources, bytes, size and SHA256 checks. Original task images and official tests
are unchanged. Maximum concurrency is two, with pair barriers. Setup allows
1,800 seconds; agent and verifier attempts retain task-native limits. Only
verifier timeouts may retry, at most three total attempts with the same output.
Whole-trial retries are disabled. The verifier requires confirmed agent
completion or cancellation before it starts.

Review only operational metadata while the queue runs, and freeze every output
before reviewing new solution trajectories or hidden tests. Keep setup errors,
model execution errors, verifier errors, and scored failures separate. Preserve
every failed preparation or trial. Final results must include complete English
and Simplified Chinese reports, the Pi comparison, timeout interpretation,
reference-exposure findings, and accounting limitations. The previous Pi report
contains 26 official passes, six scored failures, and two unscored legacy
timeouts, including a pass with public reference exposure; do not treat it as
an uncontaminated 34-task reference score.

Build preparation uses the upstream commands:

```bash
pnpm install --frozen-lockfile --store-dir /path/to/shared-pnpm-store
pnpm exec tsx scripts/build-exe-for-python-sdk.ts \
  --targets=node24-linux-x64 --build-artifacts --compress=GZip
python scripts/build-python-release.py --package sdk --output-dir dist-python
python scripts/build-python-release.py --package runtime --platform linux-x64 \
  --runtime-exe dist-exe/deepseek-harness-sdk-runtime-linux-x64 \
  --output-dir dist-python
```

The [frozen experiment](experiment.json) registers 34 model jobs and 17
two-task installation jobs. The [distribution manifest](deepseek-distribution.json)
pins the runtime, SDK, five dependency wheels, build provenance, and file modes
with SHA256 `d8f6157c880dfa5ae65b6c176dd86b1e32f5f31709f8f29fa7170db45d2fb9d6`.
The upstream eight artifact-build steps and official `sdk-minimal` keyless
smoke passed, and the upstream source remains clean. The frozen adapter source
is `5b503ab6d04af2f6a719ec0dbe5418bfad4bf128`, checked out at
`jobs/deepseek-harness-runtime-source`.

The first container smoke failed before model work because the Python `dsh`
launcher requires an explicit `DSH_HOME` even for its version query. The adapter
now supplies an isolated version-probe home. The corrected smoke initialized
the actual SDK/profile/model and supervisor successfully. Both native records
remain preserved; neither is a scored task attempt. The complete Harbor suite
passed 280 tests before this small integration fix, and all 11 DeepSeek-focused
tests passed after it.

Run from this repository root:

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/dsh-harbor-venv"
export UV_CACHE_DIR="$PWD/.cache/uv"
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev34-20261030/experiment.json \
  --phase preflight
# Supply DEEPSEEK_API_KEY in the environment before the model phase.
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/deepseek-harness-dev34-20261030/experiment.json \
  --phase model
```

Each job uses the standard `python -m harbor_adapter run --config ...` workflow
from the frozen source root. Native outputs and per-job input manifests remain
under `jobs/deepseek-harness-runtime-source/jobs/`. Orchestration and image-cache
events remain under `jobs/deepseek-harness-dev34-20261030-orchestration/`.
The runner refuses to overwrite or replay previously started model jobs.

## Verifier profile metadata correction

The [metadata amendment](profile-metadata-amendment.json), registered before
model work, corrects a historical Pi description copied into `experiment.json`.
The frozen current adapter registers both `qemu-alpine-ssh-v1` and
`pytorch-model-recovery-v1` for these selected revisions, and automatically
enforces both. The other 32 tasks have no registered verifier profile. This
corrects the plan's descriptive profile fields only; it changes no execution,
task, source, dependency, timeout, or model setting. The original plan and its
execution registration remain immutable. Both QEMU's and PyTorch's dependency
profiles passed their native preflight checks.
