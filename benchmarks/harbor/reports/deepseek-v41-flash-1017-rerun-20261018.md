# DeepSeek Flash 1017: six previous failures rerun

Three previous failures passed: **WAL recovery, gRPC KV store, and SQL
optimization**. Regex chess failed. The sampler and pipeline-parallelism
trials are **unscored verifier errors**: dependency downloads failed before
pytest started. Their native reward zeros are preserved in the results but
are not counted as model failures.

These are fresh, single trials of all six failures from the
[October 12 baseline](dev34-main-baseline-20261012.md), using the same agent and
adapter source, prompt, task revisions, resources, and work budgets. The
[machine-readable results](../results/deepseek-v41-flash-1017-rerun-20261018.json)
contain trial IDs, raw rewards, analytical scores, timing, source and artifact
hashes, preflight history, and audit findings. The
[final registration](../configs/deepseek-v41-flash-1017-rerun-20261018/experiment-v2.json)
has SHA256
`9c9306f3eb17c3044987587a7329671160ee902a43c2b67be6de4f857e4c96c2`.

| Task | Previous result | New result | Official tests passed / failed | Agent seconds |
| --- | --- | --- | ---: | ---: |
| adaptive-rejection-sampler | Failed | Unscored: NumPy download timeout | Not started | 627.6 |
| db-wal-recovery | Failed | Passed | 7 / 0 | 76.2 |
| kv-store-grpc | Failed | Passed | 7 / 0 | 304.2 |
| query-optimize | Failed | Passed | 6 / 0 | 287.0 |
| torch-pipeline-parallelism | Failed | Unscored: CUDA dependency download timeout | Not started | 613.9 |
| regex-chess | Failed | Failed: required file missing | 0 / 4 | 644.8 |

Twenty-four official test cases executed across four tasks: 20 passed and four
failed. All six model trials completed without setup errors. There were zero
whole-trial retries and zero verifier retries. This incomplete, selected subset
does not provide a fresh score for the entire 34-task development pool.

The run used `deepseek/deepseek-flash` at the official
`https://api.deepseek.com/anthropic` endpoint. DeepSeek's
[API documentation](https://api-docs.deepseek.com/quick_start/agent_integrations/)
and [October 17 announcement](https://api-docs.deepseek.com/news/news261017/)
identify `deepseek-flash` as **DeepSeek-V4.1-Flash-1017**. This mapping was checked
before execution; the alias is not an immutable checkpoint pin.

The evaluated source remained
`2eb99b608dfb39464d17d109a4a8f11afda607a9`, with the original 385-word headless
prompt. Every model trial installed the previous baseline's exact wheel,
SHA256 `f4dcc18758e584696f955ae57fd18c751599b70e8b497ca2db7ef9e2b16e9350`.
Limits remained 100 replies and 65,536 output tokens per request; work budgets
were 720 seconds for five tasks and 3420 seconds for regex chess. Consecutive
pairs ran in ascending budget/name order with concurrency two. The standard
Harbor entry point built and recorded every source snapshot and wheel.
Temperature and reasoning effort remained unset.

WAL recovery preserved the original database and sidecar before opening SQLite,
decoded the WAL, and recovered all 11 records. gRPC passed the official request
contract tests. SQL passed correctness, database-preservation, and the official
optimized-reference performance test. The failure diagnoses from the previous
run were not injected into any new task instruction.

Regex chess stopped after about 10.7 minutes because of response truncation,
well before its 57-minute work deadline. ATIF steps 5 and 8 both ended with
`stop_reason=max_tokens`, reporting 65,536 and 65,535 completion tokens. The
agent used its one automatic truncation recovery between those responses.
Neither response produced an executed file-writing tool call, so `/app/re.json`
was absent and all four official tests failed with `FileNotFoundError`.
This run evaluated no submitted chess implementation; it does not establish
whether the previous castling bug was fixed.

The sampler's original verifier failed to download `numpy==2.3.3` because of a
network timeout. Pipeline verification failed to download
`nvidia-cusparse-cu12==12.5.4.2`, required by its original `torch==2.7.0`
dependency. Neither verifier reached pytest or produced a CTRF test report.
The original wrappers still returned native reward zero without a Harbor
exception. The analytical scores are therefore null, classified as
`verifier_error`. These were download errors within completed attempts of
363.0 and 159.8 seconds, not verifier-process timeouts; the registered
timeout-only policy did not permit another attempt. The submitted R sampler
and pipeline implementation remain officially unverified. Agent-created R
tests and a custom torch stub do not replace official verification.

Before model work, two installation-only trials were administratively
interrupted after slow downloads of uv's normally selected original CPython
3.13.9+20251120 archive. A transport amendment added a verified cache entry for
that identical archive, then all six fresh installation checks succeeded.
The archive's upstream size, filename, and SHA256 were verified with the
repository's existing cache utility. All six verifier dependency profiles were
explicitly **`not_configured`**; successful agent installation did not certify
their verifier dependencies. The
[configuration README](../configs/deepseek-v41-flash-1017-rerun-20261018/README.md)
documents both plans and the retained interruption evidence. Original images,
package sources, official test scripts, resources, and verifier time limits
were preserved.

All six native trials ended before trajectory or official-test-content review.
Outputs froze at **2026-10-18 14:09:39 UTC**. Source snapshots, installed wheel
digests, task/configuration hashes, preflight evidence, and queue barriers were
verified. Both registered plans and all 14 Harbor configurations validated.
All six original image IDs and registry digests remained unchanged; no scored
trial containers remained. A scan and review of the six frozen trajectories
found no observed benchmark-answer retrieval, hidden verifier access, or
provider credential exposure. Raw logs and trajectories remain local; only
derived findings and evidence hashes are published.

The model jobs occupied approximately **40.1 minutes** of wall time, excluding
preflight. This is an exploratory rerun of previously exposed development tasks
selected because they failed. Single trials, live dependency resolution, and
changing service conditions cannot isolate a checkpoint effect or establish
reliability. The supported conclusion is three newly observed passes, one
valid scored failure, and two unresolved official evaluations.
