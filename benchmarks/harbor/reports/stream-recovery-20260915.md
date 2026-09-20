# Interrupted response recovery: implementation and targeted validation

## Status

The transport compatibility fix, bounded stream recovery, offline tests, and
independent review are complete. Live targeted trials are prepared and await
explicit approval for OpenRouter data transfer and API charges. No live model
requests have been made by this experiment yet.

## Problem and implementation

The September 12 and September 14 experiments recorded four interrupted model
responses across three distinct tasks. A `RemoteProtocolError` during response
iteration ended the whole agent run. SDK 1.5.0 used `httpx2`, while the CLI
caught `httpx.HTTPError`; these exception families do not share that base class.

The change handles both HTTP families and retries response-body `ReadError`,
`ReadTimeout`, and `RemoteProtocolError` at most twice, with delays of 1 and 2
seconds. It retains the last complete conversation and executes tools only
after a complete reply is received. Interrupted replies do not consume the
completed-reply turn budget. Authentication, invalid requests, programming
errors, and user cancellation are not retried by this loop. Pre-stream errors
retain the SDK retry policy without a second outer retry layer.

No further retry is scheduled beyond 300 seconds after a reply's first
interruption. This scheduling window does not cancel an in-flight request;
the SDK timeout and external supervisor deadline remain independent limits.

Journal v3 adds `model.failed`, with a separate ID per attempt, the original
error, retry intent, duration, and generation ID captured before reading the
body. ATIF keeps failed attempts in chronological order. Interrupted-generation
billing can be reconciled without treating missing token usage as complete.
Readers continue to support v1/v2 journals.

## Automated and offline evidence

| Validation | Result |
| --- | --- |
| Complete suite, locked SDK 0.112.0 / httpx | 292 passed, 4 skipped |
| Complete suite, SDK 1.5.0 / httpx2 2.12.0 | 296 passed |
| Harbor adapter and official ATIF compatibility tests | 24 passed |
| Historical interrupted response replay, SDK 1.5.0 | 4/4 recovered |

The locked environment skips four tests that explicitly require the absent
`httpx2` package. The SDK 1.5.0 run exercises both exception families. Both
full suites retain the existing Pydantic warning in the malformed-tool-input
test. CI now runs both the locked dependencies and an SDK 1.5.0 environment.

The real SDK transport test interrupts a response after complete-looking tool
JSON arrives, verifies that the discarded tool is never executed, and checks
that an earlier append operation occurs only once. Further tests cover retry
exhaustion, the scheduling window, preserved conversation history, interrupts,
permanent errors, billing reconciliation, and journal version rejection.

Offline replay consumes the original captured response bytes through SDK
1.5.0, raises the recorded transport error at EOF, and supplies a synthetic
successful reply to the retry. All four cases closed the interrupted response,
retried the same request, preserved the failed attempt, and executed no tools:

| Historical trial | Captured bytes | Outcome |
| --- | ---: | --- |
| `torch-tensor-parallelism__EEWJenL` | 280,943 | Recovered |
| `schemelike-metacircular-eval__Xuw2yU4` | 33,440 | Recovered |
| `schemelike-metacircular-eval__CJJvMtU` | 1,057,796 | Recovered |
| `llm-inference-batching-scheduler__S95o8Jv` | 34,318 | Recovered |

These replays make no external requests and provide no new task score. They
verify response handling; the retry's success is deliberately synthetic.

## Independent review

A Codex agent named `stream-reviewer` ran in a sibling Herdr split using the
[review-agent skill](/home/minix/.codex/skills/.system/review-agent/SKILL.md).
It reviewed the complete uncommitted diff and new files, relevant call sites,
tests, retry boundaries, exception compatibility, journals, ATIF, and costs.
Its final result was **No findings**. It independently reported 76 passed /
4 skipped with locked dependencies and 80 passed with cached SDK 1.5.0.
The review split was closed before creating the benchmark split.

## Targeted live experiment

The selected tasks are every distinct task explicitly classified as
`RemoteProtocolError` in the committed historical result summaries:

| Task | Relevant prior attempt | Prior result |
| --- | --- | --- |
| `schemelike-metacircular-eval` | September 14, request 18 | Reward 0; 0/63 subcases; no `eval.scm` |
| `llm-inference-batching-scheduler` | September 14, request 3 | Reward 0; interrupted model stream |
| `torch-tensor-parallelism` | September 12, request 1 | No official score; interrupted stream and later verifier dependency timeout |

Prepared job: `tb21-stream-recovery-targeted3-20260915`.

- Model: `openrouter/deepseek/deepseek-v4-flash-0731`.
- Dataset: `terminal-bench/terminal-bench-2-1`, pinned to
  `sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a`.
- Preserve each task reference and cached image digest from the baseline.
- 50 completed replies, 65,536 tokens per reply, concurrency 2, one attempt per
  task, no automatic whole-task Harbor retries.
- 3,600 seconds per agent run, 120 seconds of finalization grace, 3,780 seconds
  for the outer Harbor deadline; unchanged native verifier limits.
- SDK 1.5.0, httpx 0.28.1, httpx2 2.12.0, Pydantic 2.13.5.
- Reuse the cached uv bootstrap and passive HTTP recorder; periodic stack
  dumping stays disabled. Live trials do not inject transport faults.
- Install a wheel verified against every current package source file. Preserve
  the uncommitted source snapshot and file hashes so results can be compared
  with the final commit without pretending the snapshot was already committed.

Local reproduction command from the repository root:

```bash
PYTHONPATH=src benchmarks/harbor/.venv/bin/python \
  jobs/tb21-stream-recovery-targeted3-20260915-record/workflow/run.py
```

The runner refuses to overwrite an existing job, checks the wheel and image
digests, loads the existing endpoint credentials without writing them into the
report, and saves a source manifest, raw logs, HTTP records, journals,
trajectories, checkpoints, and verifier output under `jobs/`.

## Interpretation limits

The recovery fix cannot identify which upstream component closed the original
connections and does not establish that the model can solve these tasks. The
September 12 Scheme interpreter passed only 4/63 subcases before its stream
failed. Sampling, routing, cache state, and provider backends are uncontrolled.
This targeted experiment is not a full benchmark score or a controlled measure
of pass-rate improvement. A live run without an interruption does not exercise
the retry branch.

## Evidence locations

- [September 12 results](../results/tb21-generation-budget-65536-20260912.json)
- [September 14 results](../results/tb21-tool-input-recovery-20260914.json)
- [Journal v3 protocol](../../../docs/dev_docs/en/event-journal-protocol-v3.md)
- Local record: `jobs/tb21-stream-recovery-targeted3-20260915-record/`
- Local offline replay: `offline_replay.py` and `offline-replay.json` in that record

Raw task/model data remains in the Git-ignored local job directories. Bilingual
CLI documentation and the v2/v3 protocol sources and English versions are in sync.
