# Twelve-task main baseline, 2026-10-11

The frozen main runtime passed **10 of 12 tasks (83.3%)**. Both remaining
tasks reached the official assertions and failed on output correctness. There
were no final setup or verifier errors in these twelve scored trials. This is
a new development baseline, with one run per task; it is not a comparison with
the prompt candidates in PR #48.

The failures expose two concrete verification gaps: losing original evidence
before recovery, and validating an implementation against a reference that
shares its unproven assumption. More self-tests alone would not address either.

## Runtime and cohort

- Runtime: main `2eb99b608dfb39464d17d109a4a8f11afda607a9`, in the detached
  `jobs/dev12-baseline-main-source` worktree. Agent and adapter source are
  unchanged. The reporting branch contains only benchmark infrastructure,
  configurations, and evidence.
- Model: `deepseek/deepseek-flash` at
  `https://api.deepseek.com/anthropic`; 100 replies, 65,536 output tokens per
  request; temperature and reasoning effort unset. The original 385-word
  headless prompt is frozen in the configuration directory.
- Dataset: `terminal-bench/terminal-bench-2-1`, revision
  `sha256:7d7bdc1cbedad549fc1140404bd4dc45e5fd0ea7c4186773687d177ad3a0699a`.
  Twelve tasks were selected by public names and coverage before their packages
  were downloaded or their outcomes known. They extend the previously exercised
  22 tasks to a 34-task development pool. The other 55 packages remain unopened
  by this experiment. This purposive sample is not a full-dataset score or an
  estimate of repeated-run reliability.
- Each task ran once, in the registered order, with concurrency two and a
  barrier between consecutive pairs. No task was replaced and no complete
  model trial was retried. Work limits are native agent limits minus 180 seconds;
  setup has a separate 1,800-second allowance. Original verifier limits remain
  unchanged, with at most three attempts and only timeouts permitting a retry.

[Selection and configuration](../configs/dev12-baseline-20261011/README.md),
[active plan](../configs/dev12-baseline-20261011/experiment-v3.json), and
[machine-readable results](../results/dev12-main-baseline-20261011.json) contain
the revisions, budgets, artifact hashes, metrics, and post-run diagnosis.

## Results

Agent time below is Harbor's agent-execution stage, excluding environment
startup, agent installation, and the official verifier. Test counts refer to
the official task suite; the security task also ran 367 project tests.

| Task | Reward | Official tests | Agent seconds | Observed self-verification |
| --- | ---: | --- | ---: | --- |
| `cobol-modernization` | 1 | 3 passed | 505.2 | Executed original COBOL as an oracle; byte comparisons, exit behavior, 155 differential and 120 fuzz cases. |
| `fix-code-vulnerability` | 1 | 6 passed | 66.3 | Reproduced a failing header-validation test, then 367 project tests passed; exercised the WSGI entry point. |
| `nginx-request-logging` | 1 | 8 passed | 34.1 | Real HTTP requests, 404 content, log fields, and a concurrent rate-limit probe. |
| `git-multibranch` | 1 | 1 passed | 232.1 | Password SSH clone/push, both HTTPS deployment paths, deployment timing, and service restart. |
| `db-wal-recovery` | 0 | 5 passed, 2 failed | 302.0 | Checked structure and consistency of reconstructed data, without the lost original WAL as an oracle. |
| `multi-source-data-merger` | 1 | 3 passed | 55.8 | Synthetic mixed-alias case found a dropped-record bug; fixed it and checked final values and conflicts. |
| `query-optimize` | 1 | 6 passed | 536.7 | Full output comparison with original SQL; separate Python reference covered all 17,834 filtered rows. |
| `adaptive-rejection-sampler` | 1 | 9 passed | 566.0 | Distribution moments, quantiles, KS checks, invalid inputs, reproducibility, and saved-sample checks. |
| `pytorch-model-cli` | 0 | 5 passed, 1 failed | 298.7 | 330 image comparisons passed against a reference using the same inferred normalization. |
| `constraints-scheduling` | 1 | 3 passed | 30.2 | Minute-resolution search for the earliest valid slot, then calendar structure and conflict checks. |
| `custom-memory-heap-crash` | 1 | 6 passed | 280.7 | Reproduced release crash; debug/release runs, debugger allocation-site checks, and zero-error Valgrind runs. |
| `build-pov-ray` | 1 | 3 passed | 393.0 | Official-source build, deterministic renders, height-field regression, and reproducible rebuild. |

These observations come from tool outputs, not just the agents' final claims.
Examples are ATIF steps 71/83/91 for COBOL, 15/19/31 for the security repair,
13/15/17/19 for data merging, 21/31/43 for SQL, and 59/61/65 for the C++ repair.
The sampler corrected a mistaken self-test expectation at step 20 after a
10/11 result; its subsequent saved samples were checked separately at step 22.
Passing the official suite does not establish correctness outside its coverage.

## Failure: database recovery destroyed its own evidence

The original task required recovering all eleven records, **including WAL
changes**, and testing their specific values. At ATIF step 5, the agent ran
`sqlite3 main.db` before copying the database and WAL, concurrently with a
640-byte WAL hexdump. At step 7, opening `main.db-wal` failed with
`FileNotFoundError`; step 9 confirmed it was gone. The trace supports SQLite's
open/close as the cause, which the agent also recognized at step 11.

The agent identified XOR key `0x42`, but only the captured prefix survived. It
then guessed the six missing rows from the alphabetical fruit names and
`value = id * 100` pattern, wrote replacement database/WAL files, and exported
that reconstruction. The final message disclosed the loss and guessing.

Step 55 verified JSON shape, eleven sorted rows, and agreement between SQLite
and JSON. Those checks compared two artifacts derived from the same guesses.
They could not establish recovery of the original values. The official verifier
found row 1 still at `100`, while its committed WAL update required `150`;
`test_recovered_data_completeness` and `test_wal_was_decrypted` failed. The
failure therefore concerns data provenance and preservation, not JSON syntax
or a verifier dependency problem.

A useful agent change is to preserve complete original inputs before opening
stateful formats, perform recovery on copies, and distinguish recovered facts
from inferred replacements. Verification must check committed updates as well
as inserted row counts. It must not treat agreement between two guessed
artifacts as evidence that the original data was recovered.

## Failure: model conversion used a shared, unsupported assumption

The supplied `model.py` defines a 784–16–16–10 ReLU network. The agent extracted
its weights, then searched preprocessing choices against public MNIST labels.
At steps 51/53, `(pixel / 255 - 0.5) / 0.5` achieved 92.07% label accuracy, so
the agent chose it over plain `pixel / 255`. This changed the requested model's
observable predictions to improve a different objective: digit-label accuracy.

At steps 75/77/83/87, the C++ CLI matched a separately written Python reference
on 330 images, including small-margin cases. Both implementations read the
same inferred normalization from the generated weights file. This was useful
for detecting implementation discrepancies, but did not validate the assumption
itself. The agent's final message acknowledged that preprocessing was inferred.
The task instructions did not explicitly specify normalization, so this was a
real uncertainty that should have remained visible in its verification claim.

The official verifier checked fixed model predictions and found 14 mismatches
among the first 50 MNIST test images. After all twelve outputs were frozen, a
separate diagnostic loaded the original float32 weights and implemented the
supplied architecture with standard-library float64 arithmetic:

| Preprocessing | Mismatches against official expectations, first 50 images |
| --- | ---: |
| `pixel / 255` | 0 |
| `(pixel / 255 - 0.1307) / 0.3081` | 10 |
| `(pixel / 255 - 0.5) / 0.5` | 14 |

The final variant reproduces every reported mismatch index. This confirms
preprocessing as a sufficient explanation for the observed failure. The
diagnostic used the original task model and a public MNIST fixture; their hashes
and all predictions are recorded in the results JSON. It did not edit the
submission, change the official score, or constitute another model trial.

For model conversion, the agent should preserve source behavior and validate
the full input-to-output contract. An independent numerical implementation is
not an independent oracle when both programs share an unverified preprocessing
choice. Label accuracy should not substitute for behavioral equivalence.

## Installation and verification accounting

The original install-only preflight had five successes, six image-pull/start
errors, and one APT setup timeout. The second had eleven successes and one
partial uv download. Both complete histories remain in the
[first](../configs/dev12-baseline-20261011/preflight-v1-evidence.json) and
[second](../configs/dev12-baseline-20261011/preflight-v2-evidence.json) evidence
files. These eight preflight failures are separate from the twelve scored
trials.

Before any model ran, plan v3 accepted exactly one successful native
installation per task: eleven from the second preflight and POV-Ray's success
from the first. The reusable orchestrator verified their task revision, source
snapshot, installed wheel, bootstrap state, installation-only mode, and artifact
hashes. No successful result was synthesized. The runtime, prompt, tasks,
budgets, and queue were unchanged across plan amendments.

The branch also adds a verified cache for original public Docker Hub images.
Six stalled image downloads were completed through digest-checked parallel
ranges and imported without rebuilding or modifying images. Task scripts,
package sources, and official tests were preserved. All twelve verifier
dependency profiles remain **`not_configured`**: successful agent installation
was never reported as successful verifier-dependency preflight.

The PyTorch verifier timed out once after 900 seconds during dependency setup;
its unchanged second attempt completed and reached the failing assertion. Every
other verifier completed on its first attempt. Each retry retained the native
per-attempt limit and the same agent output. All twelve final official suites
ran; there are no unresolved verifier errors to exclude from the denominator.

The scored phase ran from **15:50:51 to 17:11:31 UTC**, approximately **80.7
minutes** elapsed, excluding the earlier preflights. Summed across concurrent
trials, agent execution was 55.0 minutes, agent installation 39.9 minutes, and
verification 34.7 minutes. These sums are not wall-clock duration. The calendar
task alone spent 28.4 minutes installing, followed by 30.2 seconds of agent work.

Recorded token-estimated cost totals **$0.600974**, with incomplete accounting:
PyTorch step 89 had a recoverable `RemoteProtocolError` and no usage record.
The sum covers known usage only, not an exact bill or complete total. Recorded
usage is 9,362,395 input tokens (9,171,328 cached) and 407,188 output tokens;
missing usage is not imputed as zero. This in-agent transport retry is separate
from the policy forbidding retries of entire model trials.

## Audit boundaries and next experiments

All twelve outputs had frozen by the observed checkpoint at 17:09:54 UTC,
before failure-content auditing began. Their trajectory hashes still match.
Final checks also matched the registered plan, prompt, task files, input
configurations, complete source snapshots, wheel digests, original image
identities/registry digests, and previously recorded completed-result hashes.
Queue barriers and verifier retry limits were verified from native artifacts.
No containers from the twelve scored trials remained after completion.

Trace review found no observed retrieval of external benchmark solutions or
successful access to hidden verifier contents. POV-Ray used official upstream
archives; PyTorch used public MNIST images and labels, including examples later
used by the verifier. That overlap is recorded, not treated as benchmark-answer
retrieval. Several agents searched local files for references, and the Git and
database agents read bootstrap logs. These observations cannot establish that
the model had never encountered the benchmark in training.

The database agent also read process environments at step 35, placing the
provider credential in its local trace. Raw logs must remain private or be
redacted before sharing. This report and the published JSON contain derived
observations and hashes, not raw environment values. Preventing credential
values from reaching tool observations is a separate agent-hardening follow-up.

For a subsequent optimization experiment:

1. Keep these twelve tasks intact. Use the two failures to develop preservation
   and oracle-selection behavior; keep the ten passes as regression cases.
2. Require evidence for the decisive requirement: original data values for
   recovery, source predictions for conversion. Track whether the oracle shares
   assumptions or generated data with the implementation.
3. Add controlled development variants that change update values or input
   contracts. Preserve the official baseline and label variants as custom tests.
4. Compare baseline and candidate with paired repeats and the same budgets;
   measure task score, regressions, unsupported completion claims, and cost.
   This run alone cannot show an improvement or estimate variance.
5. Leave the remaining 55 tasks unopened until a candidate and a fresh
   evaluation protocol are fixed. Do not keep selecting fresh tasks after
   seeing each development result.

Infrastructure validation on this branch: **128 Harbor tests passed**, including
image-cache and accepted-preflight provenance tests. No agent optimization was
included in this baseline.
