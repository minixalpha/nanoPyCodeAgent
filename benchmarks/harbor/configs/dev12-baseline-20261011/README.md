# Twelve-task development baseline from main

This cohort adds twelve tasks to the 22 previously exercised tasks. Selection
was fixed by public task names and desired coverage before downloading task
packages, reading their instructions, or seeing outcomes. It is a purposive
**development** cohort, not a representative random sample of Terminal-Bench.
The other 55 tasks are left unopened by this experiment.

Completed result: **10/12 passed**, with two scored correctness failures and no
final setup or verifier errors. See the
[baseline report](../../reports/en/dev12-main-baseline-20261011.md) and
[machine-readable evidence](../../results/dev12-main-baseline-20261011.json).

The runtime is main at `2eb99b608dfb39464d17d109a4a8f11afda607a9`, isolated in
`jobs/dev12-baseline-main-source`. This branch records configuration and evidence;
it does not change the agent or adapter. Neither prompt candidate from PR #48
is included. The fixed dataset revision is
`sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a`.

[Selection](selection.json) records the existing 22 tasks, selected revisions and
rationales. The [original registered plan](experiment.json) records runtime,
prompt, configuration and task-file hashes, work limits, preflight and queue
order. The active [pre-model revision](experiment-v3.json) accepts twelve
successful native installation trials with hash-bound provenance. All model
configurations, tasks, runtime, budgets and queue entries remain identical.

The [first preflight evidence](preflight-v1-evidence.json) retains five successful
installations, six image-pull/environment-start errors, and one agent setup
timeout while `apt-get update` was still downloading package indexes. No models
or official verifiers ran. All twelve original images are now cached, including
six downloaded with the verified image-cache utility. Their original registry
digests are recorded.

The [second preflight](experiment-v2.json) completed eleven successful
installations; POV-Ray's uv download ended with a partial-transfer error.
[Its evidence](preflight-v2-evidence.json) retains every result. The final plan
uses these eleven successes and POV-Ray's earlier successful installation,
without replaying successful installations because of another trial's network
failure. Before model work, the orchestrator requires exactly one accepted
installation-only result for every queued task and source arm. It verifies the
task revision, source snapshot, installed wheel, bootstrap status, input mode,
and recorded artifact hashes. A scored trial, failed installation, pending
registered verifier profile, incomplete set, or changed evidence is rejected.
Unsupported verifier profiles remain explicit. Both failed jobs and all eight
failed preflight trials remain in the evidence; none is a scored agent failure.

| Task | Coverage | Work budget (seconds) |
| --- | --- | ---: |
| `build-pov-ray` | Legacy native compilation | 11,820 |
| `cobol-modernization` | Language migration and behavioral compatibility | 720 |
| `custom-memory-heap-crash` | C++ memory debugging | 1,620 |
| `fix-code-vulnerability` | Security repair and behavior preservation | 720 |
| `nginx-request-logging` | Service configuration and observable behavior | 720 |
| `git-multibranch` | Git deployment and service integration | 720 |
| `db-wal-recovery` | Database recovery and data integrity | 720 |
| `multi-source-data-merger` | Data integration and conflict resolution | 720 |
| `query-optimize` | SQL correctness and performance | 720 |
| `adaptive-rejection-sampler` | Numerical algorithms and statistical checks | 720 |
| `constraints-scheduling` | Calendar constraints and temporal reasoning | 1,020 |
| `pytorch-model-cli` | C inference and model CLI contracts | 720 |

All trials use `deepseek/deepseek-flash` at the official DeepSeek
Anthropic-compatible endpoint, 100 replies and 65,536 output tokens per request.
Temperature and reasoning effort are unset. Each task runs once. Work budgets
follow the existing policy: native task agent timeout minus 180 seconds.
POV-Ray has a 12,000-second native limit; it is retained rather than capped to
match the shorter tasks. Setup independently allows 1,800 seconds.

The queue is fixed by ascending work budget, preserving selection order on ties.
Consecutive pairs finish before the next pair starts; at most two trials run
concurrently. There are no outcome-based task replacements or whole-trial
retries. Verifiers retain their original task limits and may retry only after a
timeout, at most three total attempts using the same agent output.

## Run and preserve evidence

Run from the repository root after creating the exact source checkout. Pass
credentials through the process environment, never configuration or logs. Set
`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic` and leave
`ANTHROPIC_MODEL` unset so the recorded configuration selects the model.

```bash
python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev12-baseline-20261011/experiment-v3.json \
  --phase preflight

python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/dev12-baseline-20261011/experiment-v3.json \
  --phase model
```

The reusable orchestrator calls only the standard
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`
workflow from the frozen repository root. It creates an immutable registration,
requires all twelve successful install-only records before model work, and
refuses to retry a job already recorded as started. With the final plan,
`--phase preflight` validates the recorded successful installations without
launching another installation job. Source snapshots and wheel manifests remain
in the normal Harbor job-input directories. A full model trial still installs
the agent in its own fresh container; preflight does not eliminate later
network failures.

All twelve selected verifier dependency profiles are explicitly
`not_configured`. Agent installation preflight does **not** certify verifier
dependencies. Preserve original images, package sources and official scripts.
Record setup failures, verifier errors and scored failures separately; preserve
raw rewards even when an unchanged verifier writes zero before tests start.

Inspect only public metadata/instructions before every model output freezes.
Hashing task files does not require inspecting their contents. Afterwards, audit
traces for external benchmark answers, verification quality and incomplete
accounting. A single observed pass or failure is not a stability estimate.
Keep these twelve results separate from previous pilot20 and prompt comparisons.

For a later reproduction, use new job names and a new registration directory;
never overwrite this baseline's artifacts.
