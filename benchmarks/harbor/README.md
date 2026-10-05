# Harbor adapter

[English](README.md) | [简体中文](README.zh-CN.md)

This isolated workspace contains the nanoPyCodeAgent adapter for Terminal-Bench
and other benchmarks run by Harbor. It is development infrastructure, not part
of the end-user `nanoPyCodeAgent` package. Harbor is pinned to 0.21.0 in this
workspace's lockfile.

## Run a benchmark

Set the connection credentials used by the CLI. For a third-party or proxy
endpoint, configure the API key and base URL; select the model with Harbor's
`--model` option shown below:

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_BASE_URL="https://gateway.example"
```

Run new benchmarks through the standard entry point, from the repository root:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/qemu-alpine-ssh.json
```

This example pins the QEMU task revision and uses `deepseek/deepseek-flash`.
Set the endpoint and credentials for that model, or copy the configuration and
change `agents[].model_name`, task selection, and budgets for another run. These
are ordinary Harbor JSON configurations; the entry point supplies the standard
verifier and cache policy. It accepts the repository's `NanoPyCodeAgent` adapter
with budget kwargs; credentials belong in the environment.

The entry point builds the current working tree, including uncommitted changes,
into a wheel and checks its Python sources against the recorded snapshot. It
also snapshots the adapter, records source and wheel hashes, and uses that
snapshot throughout the run. Inputs and logs live in `jobs/<job-name>-input/`;
Harbor outputs remain in `jobs/<job-name>/`. Existing jobs are never overwritten.
`summary.json` records scores, setup/preflight status, cache use, and verifier
attempts. An infrastructure exception has no score; it is not converted to zero.
The command exits nonzero for execution errors or incomplete results, while a
completed score of zero is a valid benchmark result.

Use `--job-name <unique-name>` for a readable run name. Add `--prepare-only` to
build and record inputs without starting containers. Add `--install-only` to
exercise dependency installation and preflight without calling the model or
executing the official tests. A full run still performs setup and preflight in
its own fresh container; an install-only check does not resume into model work.

### Verified dependencies and preflight

The standard adapter automatically uses `.cache/nanopy-harbor/`, shared across
runs and ignored by Git. Override it with `NANOPY_HARBOR_CACHE` or the entry
point's `--cache-dir`. On APT systems it refreshes the package index, resolves a
SHA256 download plan, restores matching cached files, and downloads missing
ones. Successful downloads are verified and saved before installation, so
APT cleanup hooks cannot erase the shared copies. A different version or digest
does not reuse an old cached file. Corrupt files fail setup before model work.
Other package managers use Harbor's regular dependency installation.

To import previously verified downloads once:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter import-apt \
  /path/to/bootstrap-cache/manifest.json
```

The manifest is a JSON array of objects with `url`, `filename`, `size`, and
`sha256`, accompanied by `packages/<filename>` files. Import validates every
file. At use time, the current APT index must independently match each entry.
Copying the entire shared cache to another machine is also supported. A new
machine with no matching cache still needs the original downloads to be
available; this mechanism does not replace package sources or invent missing
versions.

Verifier dependency profiles are tied to reviewed task revisions in
`src/harbor_adapter/bootstrap.py`. The current QEMU profile installs `sshpass`
and warms the original verifier's uv 0.9.5, Python 3.13, pytest 8.4.1, and
pytest-json-ctrf 0.3.5 dependencies using `pytest --version`. It runs no task
assertions or solution code. Unknown QEMU revisions fail setup pending profile
review; tasks without a profile explicitly report `not_configured`. Add a
profile and regression tests when another task needs verifier preflight.

Every installation writes `agent/bootstrap.json`, including partial progress
on failure. Preflight failure stops the trial before any model call. The
official verifier script remains unchanged and may still access the network
when it runs; a successful preflight is not a guarantee against later outages.
Full standard runs enable the timeout retry policy below by default, with zero
whole-trial retries. CI checks these contracts without model calls or Docker.

### Direct Harbor invocation

For adapter development or comparison with published versions, the lower-level
Harbor interface remains available. Pin the agent installed in the container:

```bash
uv run --project benchmarks/harbor harbor run \
  --task terminal-bench/openssl-selfsigned-cert \
  --agent harbor_adapter:NanoPyCodeAgent \
  --agent-kwarg git_ref=<commit-sha> \
  --model anthropic/claude-sonnet-4-6 \
  --verifier harbor_adapter:RetryingVerifier \
  --verifier-timeout-multiplier 4 \
  --env docker \
  --n-concurrent 1 \
  --n-attempts 1
```

Use `--agent-kwarg version=<released-version>` instead of `git_ref` to install a
published PyPI release. The two pins are mutually exclusive. If neither is
provided, the adapter installs the latest published release. For reproducible
benchmark results, always provide one of them. Prefer a full 40-character commit
SHA for `git_ref`; Harbor may parse an unquoted abbreviated SHA such as `83e6271`
as a number. To use an abbreviated revision, preserve its string type with
`--agent-kwarg 'git_ref="83e6271"'`.

The adapter sends the instruction through stdin, runs the agent in the task
container's current directory, and saves combined stdout/stderr to
`/logs/agent/nanopycodeagent.txt`. It uses the CLI's 50-turn default; override
that with `--agent-kwarg max_turns=20`.

Use `--agent-kwarg time_budget_seconds=N` to bound task work and remind the model
to finalize before either time or replies run out. Choose a budget inside each
task's native timeout, reserving at least 30 seconds for cost reconciliation
plus trajectory writing and harness overhead. For example, the 3600-second
targeted experiments use 3420 seconds; that value does not fit a 900-second task.
No time budget is inferred automatically by the adapter.

For the per-reply generation limit, pass `--agent-kwarg max_tokens=32768`.
This becomes `--max-tokens 32768` in the container and overrides the forwarded
`ANTHROPIC_MAX_TOKENS` environment variable. When omitted, the adapter sends no
token flag, so the installed agent's environment/settings/default applies
(32768 in the version introducing this option). Older releases require omitting
the new option. The effective budget is recorded in the startup log and in
`agent.extra.max_tokens` in the ATIF trajectory.

The adapter also asks the agent to write an ATIF-v1.7 trajectory directly to
`/logs/agent/trajectory.json`. Harbor collects that file as the trial's native
ATIF output and backfills prompt, completion, cache-token, and cost totals into
the agent result. Missing, invalid, or partial trajectories remain explicitly
diagnosed; unknown usage or cost is not reported as zero.
If any costs are estimated, `final_metrics.extra` records
`cost_is_estimated: true` and the estimated portion in `estimated_cost_usd`.
The adapter preserves both fields in the agent result's `metadata.trajectory`,
including for partial totals. Estimates with a generation ID remain eligible
for billing reconciliation; a successful lookup replaces the estimate.

By default, the adapter strips the first provider prefix from `--model` and
passes the result to nanoPyCodeAgent as `ANTHROPIC_MODEL`. Set
`ANTHROPIC_MODEL` only when a custom endpoint requires an actual model name that
differs from Harbor's `provider/model` identity; this explicit override takes
precedence. Harbor-native provider credentials and configured base URLs are
also normalized to the `ANTHROPIC_*` variables expected by nanoPyCodeAgent's
SDK.

## Retry verifier timeouts

The example above uses `harbor_adapter:RetryingVerifier` for single-step Linux
tasks. It runs the original test script up to **three times total**, retrying
only when the script exceeds the task's native `[verifier].timeout_sec`. A
900-second task therefore gets at most three 900-second attempts. A completed
verification stops immediately, including a reward of zero. Script errors,
missing or invalid rewards, and cancellation do not trigger another attempt.

`--verifier-timeout-multiplier 4` gives Harbor's outer watchdog room for all
three attempts plus test upload, process cleanup, and log collection. It does
not extend each test-script attempt. Conflicting timeout overrides or caps
that leave insufficient overall time are rejected. Use
`--verifier-kwarg max_attempts=2` for two total attempts, or `max_attempts=1` for
one; values above three are rejected.

The runner reuses the same container, agent output, and dependency caches;
the agent is run once. Test scripts must tolerate being rerun in that
environment; verifier-side filesystem changes are not rolled back. Timed-out
process groups and other members of their Linux session are killed before
retrying. Each attempt's logs and any reward files are archived under
`verifier/attempts/1/`, `2/`, and `3/`. The runner clears current verifier
outputs before the next attempt, so a stale reward cannot determine its score.
`verifier/retry-summary.json` records each attempt's status, duration, and exit
code when available. Exhausting the attempts still produces Harbor's
`VerifierTimeoutError`.

This verifier requires `python3` and `bash` in the container, which the
nanoPyCodeAgent adapter installs. These options apply to new runs; they cannot
restore a deleted container or missing task outputs from an old trial.
Harbor's ordinary `--max-retries` setting reruns the entire trial, including
the agent, and is independent of these verifier attempts.

## Test the adapter

```bash
uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml \
  benchmarks/harbor/tests
```
