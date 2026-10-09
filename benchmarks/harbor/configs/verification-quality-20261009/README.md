# Verification quality and long-command guidance comparison

This is a predeclared exploratory comparison of two independent prompt changes
against a fresh shared control. It is not a new pilot20 score. The frozen
[plan](experiment.json) contains every task revision, source revision, prompt
hash, configuration hash, and scheduled job. Results must retain failures and
infrastructure errors without replacing trials based on their outcomes.

| Arm | Source revision | Headless prompt words | Change |
| --- | --- | ---: | --- |
| Control | `2eb99b608dfb39464d17d109a4a8f11afda607a9` | 385 | Current main, including the workspace-reference clarification |
| Verification | `3b69d6d` | 482 | Concrete verification planning, real-entry checks, complete item coverage, justified test corrections, and final-version evidence |
| Operations | `ca624b0` | 480 | Explicit Bash time limit, redirected background work, completion status, and intermediate deliverables |

Only `HEADLESS_SYSTEM_PROMPT` differs between arms. The interactive prompt,
tools, runtime recovery, work budgets, adapter, images, and official tests are
unchanged. No finish gate or new runtime verification machinery is introduced.
The candidate strategies are bundles; this experiment cannot attribute an
observed difference to an individual sentence.

## Cohort and limits

Each arm runs each task twice: **24 fresh model trials** in total, with at most
two active trials. The queue rotates arm order and runs consecutive pairs to
completion before starting the next pair. Repeat indices are descriptive;
provider seeds are not fixed, and pairs do not share random model samples.

| Task | Selection | Work budget |
| --- | --- | ---: |
| `torch-pipeline-parallelism` | Prior diagnostic failure | 720 seconds |
| `llm-inference-batching-scheduler` | Prior avoidable tool timeout | 1,620 seconds |
| `build-cython-ext` | Outside the previous pilot20 tuning cohort | 720 seconds |
| `cancel-async-tasks` | Outside the previous pilot20 tuning cohort | 720 seconds |

The two new tasks were selected from the pinned catalog using task names and
public requirements. The candidate text was drafted before their instructions
were read. Their hidden tests and solutions are not inspected until all outputs
are fixed. The experiment designer previously inspected pipeline evaluation
code during diagnosis; that task is explicitly diagnostic. No task-specific
backward-order rule, hidden expected answer, function name, or model parameter
is added to either candidate.

All runs use `deepseek/deepseek-flash` at the official DeepSeek Anthropic-compatible
endpoint, 100 replies, and 65,536 output tokens per request. Temperature and
reasoning effort are not explicitly set. Setup has a separate 1,800-second
limit. Whole-trial retries are disabled. Only verifier timeouts may retry, with
at most three attempts on the same agent output and the original per-attempt
limit. Setup failures and verifier errors remain separate from scored failures.

## Execution

Create the three isolated checkouts listed in the plan, at their recorded refs.
The exact prompt files and candidate patches are retained here for reproduction.
Use new job names and a new registration directory for any later reproduction;
never overwrite this experiment's records. Credentials belong in the process
environment, not in configuration files or logs. Set `ANTHROPIC_API_KEY` and
`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, and leave
`ANTHROPIC_MODEL` unset so the adapter uses the model in the configurations.

From the repository root:

```bash
python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/verification-quality-20261009/experiment.json \
  --phase preflight

python benchmarks/harbor/scripts/run_comparison.py \
  --plan benchmarks/harbor/configs/verification-quality-20261009/experiment.json \
  --phase model
```

The orchestrator invokes only the standard command from each source root:
`uv run --project benchmarks/harbor python -m harbor_adapter run --config ...`.
It introduces no adapter copies or bootstrap scripts. Standard job snapshots
record the wheel and Python sources. All arms share the verified APT cache.

Before any model work, run install-only checks on all four control tasks and a
wheel-installation smoke check for each candidate. None of these tasks has a
registered verifier-dependency profile: their status must remain explicitly
`not_configured`, even when agent installation succeeds. Full trials repeat
setup in fresh containers. A failed install-only check blocks model launch.

The orchestrator records its registered plan and every launch, skips only jobs
already recorded as finished, and refuses to restart a previously started job.
Interrupted jobs require inspection; the orchestrator never silently retries
them. A completed reward of zero is a valid result, not a reason to rerun.

## Evaluation

Report each candidate against the fresh control, separating the diagnostic and
new-task cohorts. Preserve raw rewards, but exclude confirmed external
task-answer or hidden-test exposure from independent-capability comparisons.
Use only common eligible cases for paired comparisons.

Review tool evidence for real-entry validation, complete coverage within chosen
cases, independently justified expectations, unresolved failed checks, and
unsupported final claims. Track checks that became stale after relevant edits.
Missing evidence is unknown; a command name or zero exit code alone does not
prove validation. Also report agent execution time, model attempts, tool
timeouts, truncation/recovery, estimated cost, and accounting completeness.

Two repeats and two tasks outside prior tuning are insufficient to establish a
general capability gain. Report every regression and cost increase. Do not
promote a candidate based solely on pipeline or one favorable trial.
