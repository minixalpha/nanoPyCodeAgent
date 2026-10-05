# Bounded truncation recovery experiment

The [predeclared plan](experiment.json) selects the two failures from the
[v0.9.0 pilot20 baseline](../../reports/v0.9.0-baseline-20261005.md), with their
original revisions and budgets. Each task receives one fresh model run; no
score replaces a trial in the released baseline.

Use a checkout of agent commit
`e1be6ed1f81a17d73677b414d4d913adb81e9e25` for the recorded behavior and wheel
version. The standard runner builds its current checkout, including local
source changes. Configure the official DeepSeek credentials as described in
the [adapter README](../../README.md), set
`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, and leave
`ANTHROPIC_MODEL` unset so the configuration chooses `deepseek-flash`.

Run dependency installation preflight first:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/truncation-recovery-20261005/install-only.json \
  --install-only
```

Both tasks lack a registered verifier dependency profile at this revision and
must explicitly report `not_configured`. After agent installation succeeds,
run the following two commands in separate terminals to reproduce the original
concurrent task pairing. Omit `--job-name` to generate fresh job names.

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/truncation-recovery-20261005/model-extraction.json
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/truncation-recovery-20261005/scheme.json
```

Record both task scores and actual recovery events. A task that passes without
reaching `max_tokens` does not demonstrate recovery effectiveness. The
[experiment report](../../reports/truncation-recovery-20261005.md) and
[structured results](../../results/tb21-truncation-recovery-20261005.json)
preserve that distinction.
