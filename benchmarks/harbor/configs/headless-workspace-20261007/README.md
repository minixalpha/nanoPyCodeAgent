# Clarify task-supplied workspace references

This is a single-task follow-up to the [guarded pilot20 comparison](../headless-p0-guarded-20261007/README.md), not a replacement run or a new twenty-task score.

The guarded path-tracing candidate explicitly declined to disassemble a supplied
executable because the information boundary made it unsure whether an unmentioned
workspace file was permitted. Both earlier variants passed the task, but the
candidate spent substantially longer reconstructing the scene from its image.

Clarify that task-supplied source, executables, and tests are available references
unless the task restricts them. Preserve the prohibition on externally obtained
task-specific answers or hidden evaluation tests unless explicitly requested.
The other prompt paragraphs, runtime, tools, and adapter remain unchanged. No
filename, task-specific algorithm, answer, or verifier formula enters the prompt.
The complete prompt and its SHA256 are recorded in [experiment.json](experiment.json).

The full pilot20 comparison continues with its already-prepared `03cfd53` wheels.
This follow-up runs once, only after an existing final-budget arm has finished,
so total concurrency remains at most two. Preserve all earlier outcomes and this
new outcome, including failure or an unscored result. This selected case provides
behavioral regression evidence; it cannot establish a general performance gain.

From a clean checkout of the clarified candidate, load the same credentials and
endpoint as the pilot, then use the standard entry point:

```sh
unset ANTHROPIC_MODEL
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config /absolute/path/to/benchmarks/harbor/configs/headless-workspace-20261007/path-tracing.json \
  --job-name headless-workspace-path-20261007 \
  --cache-dir /absolute/path/to/.cache/nanopy-harbor
```

The task has no registered dependency profile, so its preflight status must remain
`not_configured`. Standard setup installs the recorded wheel before model work.
The work budget is 1,620 seconds, with 100 replies and 65,536 output tokens per
request. Only verifier timeouts may retry, at most three attempts using the
original 1,800-second per-attempt limit. Whole-trial retries remain disabled.
