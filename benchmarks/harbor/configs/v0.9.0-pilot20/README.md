# Frozen v0.9.0 pilot20 configuration

These files define one 20-task baseline for the published v0.9.0 agent, before
0.10.0 development. `baseline.json` records the release revision, original task
revisions, task image digests, source/test hashes, budgets, and failure policy.
The four budget groups are disjoint and cover the same 20 tasks as install-only.

Copy this configuration directory into a checkout at the recorded v0.9.0
revision, then run from that repository root using the standard Harbor adapter.
The runner builds the agent from its current checkout. Configure an official
DeepSeek API key in the environment and
set `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`. Leave
`ANTHROPIC_MODEL` unset so the explicit configuration selects `deepseek-flash`.
See the [adapter documentation](../../README.md) for dependency and cache setup.

Run dependency preflight before any model work:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/v0.9.0-pilot20/install-only.json \
  --install-only
```

After preflight succeeds, run these four commands sequentially. The adapter
generates a fresh job name when `--job-name` is omitted.

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/v0.9.0-pilot20/budget-720s.json
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/v0.9.0-pilot20/budget-1620s.json
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/v0.9.0-pilot20/budget-2220s.json
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/v0.9.0-pilot20/budget-3420s.json
```

The agent setup timeout is 1,800 seconds. Each task retains its native work and
per-attempt verifier limits; the agent work budget reserves 180 seconds from the
native agent timeout. Concurrency is two, with one model run per task and no
whole-trial retries. Only verifier timeouts may retry, at most three attempts on
the same agent output with the original per-attempt limit.

At this revision, only the pinned QEMU task has a registered verifier dependency
profile. The other 19 tasks must report `not_configured`, rather than being
described as having passed verifier dependency preflight. Preserve every trial
and report setup failures, verifier errors, and scored failures separately.
