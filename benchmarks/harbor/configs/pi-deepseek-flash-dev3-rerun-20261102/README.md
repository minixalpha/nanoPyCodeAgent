# Authorized three-task Pi rerun

Status: completed and audited on November 2, 2026. **Two official passes, both
reference-exposed, and one scored failure after confirmed timeout cancellation;
zero unscored attempts.** WAL and pipeline both read reference solutions and
tests whose reconstructed bytes match the registered task hashes. Sampler failed
all nine official tests after the supervisor stopped 11 processes. These results
provide no independent passing solution from the three reruns.

See the complete [English report](../../reports/en/pi-deepseek-flash-dev3-rerun-20261102.md),
[Simplified Chinese report](../../reports/zh-CN/pi-deepseek-flash-dev3-rerun-20261102.md),
and [structured results](../../results/pi-deepseek-flash-dev3-rerun-20261102.json).
[Preflight evidence](preflight-evidence.json) and [launch evidence](launch-evidence.json)
precede the model jobs. The [freeze manifest](outputs-freeze.json) covers 326
files before trajectory review; all 1,449 original frozen artifacts remain
unchanged. WAL exposed the credential in two private raw logs. All three official
verifiers completed on their first attempt. No containers remain running;
the six initially protected images remain present. See
[validation evidence](validation-evidence.json).

The maintainer requested one fresh Pi attempt on `adaptive-rejection-sampler`,
`db-wal-recovery`, and `torch-pipeline-parallelism`. The first two attempts in the
[original baseline](../../reports/en/pi-deepseek-flash-dev34-20261024.md) were
unscored because their timeout boundaries were not confirmed. The original
pipeline attempt passed after reading public reference tests and a solution.
This is an outcome-selected development supplement, not an independent benchmark.
Keep every original outcome and every new attempt separately; do not select the
better score.

The [v2 registration](experiment-v2.json) preserves Pi 1.4.0 and its complete
distribution digest, the original public model configuration,
`deepseek/deepseek-flash`, the official OpenAI-compatible endpoint, `high`
reasoning, native prompts/tools/compaction/retries, and unset temperature.
The alias is mutable; identical backend weights across dates are not established.
All three tasks retain their original revisions, files, Docker image identities,
resources, 900-second agent limit, and 900-second per-attempt verifier limit.
Setup has its separate 1,800-second limit. Concurrency is two with pair barriers,
in the original relative task order. There are no whole-trial retries.

The registered standard adapter source is
`f3a171fcbc390c6bcb0c941be6b9cdd9dc7c456c`. Each job snapshots and hashes it through
`python -m harbor_adapter run --config ...`. Confirmed cancellation and mandatory
agent quiescence protect the agent/verifier boundary. Only verifier timeouts may
retry, at most three attempts on the same output with the original time limit.
Setup errors and verifier errors remain distinct from scored failures.

The original registration used `46c554c2cf31a2d93bb37493083aab5b8fb82012`.
All three checks failed during Pi model-registration validation because Harbor
returned `None` for empty stderr. [Initial evidence](preflight-v1-evidence.json)
preserves those setup failures and confirms zero model or verifier executions.
The v2 source normalizes absent output streams while retaining rejection of
diagnostics and missing provider/model rows. Three regression cases failed
before the fix; all 304 Harbor tests passed after it. The initial model queue
remains unexecuted; v2 has distinct job names and orchestration records.

Installation checks precede all model work. Pipeline now has the repository's
reviewed `torch-pipeline-parallelism-v1` dependency profile. Sampler and WAL
explicitly remain `not_configured`; successful Pi installation does not certify
their verifier dependencies. Existing verified APT, uv/Python-release, and PyPI
wheel caches preserve original packages and sources. The PyPI transport checks
each wheel's filename, size, SHA256, and original URL against current release
metadata. `UV_HTTP_TIMEOUT=600` permits verification before serving cold wheels;
task-native limits remain unchanged. Cache events have a separate audit log.

Each task starts a fresh container and Pi session. Earlier trajectories, failure
diagnostics, tests, and solutions are not supplied to the agent. No new prompt or
network restriction is introduced. Freeze all new outputs before reviewing new
trajectories or hidden assertions, then audit reference-material access. A rerun
alone does not establish absence of answer exposure. Keep raw logs private and
publish complete English and Simplified Chinese reports with the same evidence.

The following commands document the original launch from its pinned source
revision. Completed job names and registrations are immutable. A future repeat
needs a new registration and fresh job names, with its source checkout explicitly
pinned; do not reuse this completed queue from a newer repository revision.

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/jobs/dsh-harbor-venv"
export UV_CACHE_DIR="$PWD/.cache/uv"
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev3-rerun-20261102/experiment-v2.json \
  --phase preflight
# Supply the authorized DeepSeek credential through DEEPSEEK_API_KEY.
uv run --frozen --project benchmarks/harbor \
  python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/pi-deepseek-flash-dev3-rerun-20261102/experiment-v2.json \
  --phase model
```

Native job outputs are under `jobs/pi-dev3-rerun-*-20261102/`, with immutable
inputs in the corresponding `-input/` directories. Orchestration records are in
`jobs/pi-deepseek-flash-dev3-rerun-20261102-v2-orchestration/`, with initial failed
checks retained under `jobs/pi-deepseek-flash-dev3-rerun-20261102-orchestration/`.
