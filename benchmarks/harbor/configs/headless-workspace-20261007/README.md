# Clarify task-supplied workspace references

This is a single-task follow-up to the [guarded pilot20 comparison](../headless-p0-guarded-20261007/README.md), not a replacement run or a new twenty-task score.

The registered run completed with an official pass: 340.510 agent seconds,
44 model attempts, and $0.114759216 in known estimated cost with complete usage.
The agent used the supplied executable's disassembly; no external task-answer
or hidden-test retrieval was observed. The prior main and 368-word candidate
also passed, in 403.401 and 1171.983 seconds respectively. These single runs are
descriptive comparators, not evidence of a stable speed improvement. See the
[structured evidence](../../results/headless-workspace-followup-20261007.json).

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

The completed pilot20 comparison used its already-prepared `03cfd53` wheels.
This follow-up ran once, after the control arm had finished its final budget
group, so total concurrency remained at most two. All earlier outcomes and this
new outcome are preserved. This selected case provides
behavioral regression evidence; it cannot establish a general performance gain.

From a clean checkout of the clarified candidate
`e61558f3ef23e626b7341b9811ec66044ce8610b`, load the same credentials and
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
