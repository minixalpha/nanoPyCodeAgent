# Guarded headless contract and verification comparison

Completed: **19/20 candidate passes versus 18/20 control passes**. The control's
MTEB pass has confirmed external answer/test exposure; excluding that task pair,
the common eligible result is **18/19 versus 17/19**, with one improvement
(`regex-chess`), no observed regression, and one shared failure (pipeline).
Both arms have zero unscored trials. Estimated model cost rises 30.3% and summed
agent time rises 21.6%. This is one adaptive exploratory run per task and arm.
See the [full report](../../reports/headless-p0-guarded-20261007.md) and
[structured evidence](../../results/tb21-headless-p0-guarded-20261007.json).

This [revised plan](experiment.json) evaluates the P0 contract/verification
candidate with an explicit information boundary: use task-provided material and
general documentation; do not seek or use task-specific reference solutions or
hidden evaluation tests unless the task explicitly provides or requests them.
Derive checks from the stated requirements. Both exact prompts and their hashes
are recorded alongside the plan.

## Why this is a separate experiment

The original candidate fetched an external benchmark mirror's reference solution
and evaluation source for `torch-pipeline-parallelism`, then described its
implementation as mirroring that exact reference. A passing score obtained that
way would not demonstrate independent problem-solving ability. Interrupt the
original candidate arm and its future-group launcher, preserving its three
passing trials, one pre-model installation failure, and one contaminated trial
cancelled during verification. The other 15 original candidate trials never
started. The [audit](../../results/headless-p0-original-candidate-audit-20261007.json)
contains all five started trials and the retrieval evidence; none is replaced or
folded into the revised candidate's pass rate.

Retain **all 20 unchanged main-control trials**, including already observed
outcomes and the remaining planned trials. Run **20 fresh guarded-candidate
trials**. The plan records the five control outcomes already visible when the
guard was registered. This is an adaptive exploratory comparison, not an
independently randomized confirmation. No controls are selected by score, and
the revised prompt contains no task names, test parameters, or reference code.

## Execution

The control checkout remains at `6664f7bac9d7f9b26f49e523ac6ee7e4e8a6b9ac`.
The full twenty-task candidate is frozen at
`03cfd534ddb86ea507d43cad9776e86c91d53648` (368 prompt words). Reproducing this
comparison requires that candidate checkout; the later 385-word clarification
has its own [single-task follow-up](../headless-workspace-20261007/README.md).
Only the candidate's `HEADLESS_SYSTEM_PROMPT` changes; tools, recovery, budgets,
adapter, images, and official tests remain unchanged. Use the same official
DeepSeek endpoint and `deepseek/deepseek-flash`, with 100 replies and 65,536
output tokens per request.

The original 20 control installations and both registered QEMU preflights passed
with the same adapter, profile, and task-image hashes. Check the guarded wheel's
installation before its model work:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/headless-p0-guarded-20261007/install-only.json \
  --job-name headless-p0-guarded-install-20261007 --install-only
```

Each full trial repeats setup in a fresh container. The registered QEMU dependency
preflight runs before its model invocation; other profiles remain explicitly
`not_configured`. Credentials stay in the environment. Set the official endpoint
and leave `ANTHROPIC_MODEL` unset, as in the original experiment.

In the recorded experiment, the existing control 720-second group continued.
The guarded candidate's 720-second group started after installation succeeded;
both groups finished before moving to each remaining 1,620-, 2,220-, and
3,420-second group. The plan records the exact job names and arm launch order.
One trial per arm, **at most two total**. The guarded 720-second command was:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/headless-p0-guarded-20261007/budget-720s.json \
  --job-name headless-p0-guarded-treatment-720s-20261007
```

Use the isolated control root and the corresponding absolute configuration path
for the remaining control groups. Share the verified APT cache using
`--cache-dir`. Do not rerun the already-started control group. New reproductions
must use fresh job names and run both arms in full; existing results are immutable.

Preserve every score and infrastructure failure. Only verifier timeouts may retry,
at most three attempts on the same output with native per-attempt limits. Audit
both arms' tool calls for task-specific answer/test retrieval. Retain raw rewards,
but exclude contaminated trials from independent-capability evidence and report
them separately. A final claim must disclose control reuse, the abandoned
candidate, missing scores, regressions, accounting completeness, and the absence
of replication or a held-out cohort.
