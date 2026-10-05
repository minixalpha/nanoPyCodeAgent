# Three additional runs per task

This [predeclared plan](experiment.json) follows the earlier
[two-task experiment](../../reports/truncation-recovery-20261005.md), which
passed both tasks without exercising truncation recovery. Run each task three
more times from scratch, preserving all six results. These are additional
samples, not replacements for earlier scores.

Keep the same agent/adapter Python source hashes, task revisions, images, model,
endpoint, token cap, reply cap, and work/setup/verifier budgets as the preceding
experiment. Runtime behavior is from commit
`e1be6ed1f81a17d73677b414d4d913adb81e9e25`; the runner records the exact checkout
commit and built wheel for this round.

From the repository root, configure official DeepSeek credentials, set
`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, and leave
`ANTHROPIC_MODEL` unset. Run installation preflight first:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/truncation-recovery-repeat3-20261005/install-only.json \
  --install-only
```

Both verifier dependency profiles must explicitly report `not_configured`.
After installation succeeds, run the six entries in `job_queue`, taking each
configuration path relative to this directory. Limit concurrent jobs to two:
each configuration contains one task and one attempt. For example:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/truncation-recovery-repeat3-20261005/scheme.json \
  --job-name truncation-recovery-repeat3-scheme-1-20261005
```

Use fresh job names when reproducing the experiment; the runner never overwrites
existing results. No whole-trial retries or replacements are allowed. Only
verifier timeouts may retry, at most three attempts with the original per-attempt
limit and the same agent output. Record truncation, actual recovery, subsequent
tool execution, terminal outcome, score, and accounting completeness per trial.
A passing trial without truncation does not demonstrate recovery effectiveness.
