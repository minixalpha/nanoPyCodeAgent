# Headless contract and verification prompt comparison

**Execution status:** the original candidate at `7ea2d75` was abandoned after
retrieving a task-specific reference solution and evaluation source. Preserve all
five started candidate trials in the [audit](../../results/headless-p0-original-candidate-audit-20261007.json);
the other 15 never started. All main-control trials continue unchanged. The
[guarded-candidate plan](../headless-p0-guarded-20261007/README.md) is a separate,
explicitly adaptive comparison, with 20 fresh candidate trials. The original
predeclared plan and prompt hashes remain unchanged below.

This [predeclared experiment](experiment.json) evaluates the first candidate from
the [prompt study](../../../../docs/research/en/agent_system_prompt.md). Compare
current main (`6664f7bac9d7f9b26f49e523ac6ee7e4e8a6b9ac`, including truncation
recovery) with a candidate that changes only `HEADLESS_SYSTEM_PROMPT`.
The exact [control](control-prompt.txt) and [treatment](treatment-prompt.txt)
strings are saved without trailing newlines and hashed in the plan.

The candidate adds task-contract identification, representative and boundary
checks, independent references or invariants, diagnosis and retesting, and
evidence-based completion. Verification remains proportional to task and budget.
It contains no task names, hidden verifier parameters, or prescribed algorithms.
Earlier executable feedback is a separate hypothesis, excluded from this test.

Run all 20 pinned pilot tasks once per arm: **40 fresh model runs**. The released
18/20 result is historical context, not the control arm. There is no held-out
cohort or within-task replication, so this is an exploratory comparison.
Keep every score and infrastructure failure. Do not tune the prompt or add
favorable replacement runs after observing results.

## Execution

Use a dedicated control checkout at the recorded main revision and the candidate
checkout for treatment. Both use the standard repository adapter; do not copy or
modify adapters per job. Configure the official DeepSeek credentials in each
command's environment, set `ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`,
and leave `ANTHROPIC_MODEL` unset. Credentials must not enter the configuration.

Before model work, run the 20-task install-only configuration from the control
repository root. Check the candidate's installation separately. Full trials
repeat setup in fresh containers. QEMU's registered profile must pass; the other
19 tasks report `not_configured`, not verified dependencies.

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config /absolute/path/to/headless-p0-20261007/install-only.json \
  --job-name headless-p0-install-20261007 --install-only
```

Run the two arms of each budget group concurrently, with **one trial per arm**
and at most **two concurrent trials total**. Wait for both arms before starting
the next group. The plan fixes group order and alternates arm launch order.
For example, from each arm's repository root:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config /absolute/path/to/headless-p0-20261007/budget-720s.json \
  --job-name headless-p0-control-720s-20261007
```

Use the corresponding treatment job name in the treatment checkout. Share the
existing verified APT cache with `--cache-dir` when using separate checkouts.
Use fresh names to reproduce the experiment; existing outputs are immutable.
Every runner records its source snapshot, wheel hash, config, and working-tree
patch. Verify that the two source snapshots differ only in the headless prompt.

Preserve native task images, package sources, official scripts, model, endpoint,
100-reply limit, 65,536-token request cap, work budgets, and verifier limits.
Whole-trial retries stay disabled. Only verifier timeouts may retry, at most
three times on the same output using the original per-attempt timeout.

Report paired task outcomes, regressions, unscored trials, time, token estimates,
accounting completeness, and observed checking behavior. A normal terminal state
or a final claim of testing is not a substitute for an official passing result.
