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

### Pi agent baselines

The same entry point also supports `harbor_adapter:PiCodeAgent`. Register a local
unmodified Pi binary distribution with `distribution_path` and
`distribution_sha256`, a public `model_config_path`, and optionally `thinking`
in the agent kwargs. The digest covers every distribution file and its mode.
The workflow saves one content-addressed distribution snapshot in the shared
cache, verifies it again before installation, and records its file manifest and
public model configuration with every job. Pi runs its native prompt, tools,
compaction, and retry behavior; no nanoPyCodeAgent wheel is installed or built.

Currently this adapter supports the official DeepSeek OpenAI-compatible API.
The public models file must reference `${DEEPSEEK_API_KEY}`; supply the actual
key through the process environment. Personal Pi configuration, extensions,
skills, and session history are not copied into task environments. Catalog
refresh is disabled so the recorded model configuration remains reproducible.
Installation-only checks validate the actual binary and provider registration
without a model call and use the same reviewed verifier dependency profiles.
Native sessions and completed JSON events remain in `agent/pi/` and `agent/pi.txt`.
Usage includes compaction when Pi supplies it, and reported costs are estimates.
Missing usage stays diagnosed. Pi does not currently generate an ATIF trajectory.
On Linux, the Pi command runs under a child subreaper. Cancellation stops its
process tree, including detached tool sessions, before control returns to Harbor.
Successful runs retain intentional background services. Set
`verifier.kwargs.require_agent_quiescence=true` to require a completed or
confirmed-cancelled supervision record before any official assertion executes.
Missing or incomplete records stop grading. Installation checks exercise the
supervisor without a model call; interrupted usage/cost totals remain partial.

The comparison runner supports Pi arms and `--phase all` for installation checks
followed by the model queue. A registered `minimum_free_disk_bytes` stops new
jobs before they start when disk space is insufficient. Existing jobs and
failed attempts are preserved. Agent-specific budget differences must be
declared in the experiment instead of assuming native agent defaults match.
For constrained Docker storage, an optional `batch_images` plan restores each
batch by registered repository digest, verifies image identities, and evicts
only image references absent from the run's initial inventory. It checks the
actual Docker storage volume and never forces image or container deletion.

### Cache original task images

If Docker image pulls repeatedly stall, the optional cache utility downloads the
same public Docker Hub image in bounded parallel HTTP ranges:

```bash
python benchmarks/harbor/scripts/cache_image.py \
  alexgshaw/git-multibranch:20251031 \
  --cache .cache/nanopy-harbor/images --load
```

The first request records the registry manifest digest; later requests reject a
changed tag. Every downloaded blob must match its size and SHA256, and each
uncompressed layer must match the original image configuration. The resulting
[OCI archive](https://github.com/opencontainers/image-spec/blob/main/image-layout.md)
preserves the original manifest, configuration, and compressed layers byte for
byte. Docker import must retain the original repository digest.

This Linux utility supports public `linux/amd64` images with gzip layers and
SHA256 descriptors. For OCI indexes and Docker manifest lists, it retains the
unmodified parent index and the unique native image manifest, downloading only
that platform's layers. Attestations associated with the selected image retain
their original manifest, configuration, and in-toto payloads, each verified by
digest. Other platforms and their attestations remain referenced in the
original index without fetching their blobs. Docker loads the native
platform explicitly and must retain the original parent repository digest.
`--load` requires Docker's containerd image store and platform-selective imports.
Use one cache writer at a time; `--workers` controls parallel range
requests (default eight, maximum sixteen). Completed blobs and partial ranges
can be reused after an interrupted download, with complete blobs revalidated.
Keep the manifest lock records with the run evidence. This only warms Docker's
image cache: continue using the standard benchmark entry point and installation
preflight, and retain any earlier environment-start failures separately.
Long image transfers refresh anonymous registry tokens before expiry and once
after HTTP 401. Interrupted transfers reuse saved ranges, then verify the full
blob digest before import. HTTP errors report status codes without signed URLs.

### Cache immutable APT indexes

If original APT index downloads repeatedly stall, an optional host proxy can
fetch immutable `/by-hash/SHA256/<digest>` indexes using verified parallel ranges:

```bash
python benchmarks/harbor/scripts/apt_index_proxy.py \
  --bind 172.17.0.1 --port 18742 \
  --cache .cache/nanopy-harbor/apt-indexes --workers 16
```

Choose the host's actual Docker bridge address. Register a read-only APT
configuration mount through Docker's `extra_docker_compose`, with per-host
`Acquire::http::Proxy::<original-host>` entries pointing to the proxy. The
[34-task registration](configs/dev34-main-baseline-20261012/README.md) contains
an example. Avoid global proxy environment variables: model/API traffic and
non-APT tools must retain their normal network path.

The proxy accepts only the original public Debian/Ubuntu APT hosts. It validates
exact ranges, object sizes, and whole-object SHA256 before serving an index;
cache hits are rehashed. Mutable release metadata and package downloads are
forwarded uncached. APT still checks signed release metadata and current package
hashes. Original repositories, task images, and test scripts stay unchanged.
Keep the proxy running through preflight and model trials, record the mount and
utility hashes in the experiment plan, and retain earlier setup failures.

If containers cannot reach the host listener, run the utility in an isolated
sidecar with `network_mode: service:main`, bind `127.0.0.1`, and use a readiness
health check. The registered example uses this mode. Mount only the proxy code
and index cache into the sidecar; do not share task files or credentials. Multiple
proxy processes coordinate cache writes with per-digest file locks. No host
proxy process or published port is needed in this mode.

### Cache original uv release archives

When the official uv installer repeatedly receives truncated GitHub downloads,
prepare its exact original release archives using the public release index:

```bash
python benchmarks/harbor/scripts/uv_release_cache.py prepare \
  --cache .cache/nanopy-harbor/uv-releases \
  --manifest /path/to/new-run/uv-release-manifest.json \
  --version 0.9.11 --version 0.9.5
```

The utility requires the original asset filename, size, and SHA256 from GitHub's
release metadata. It downloads verified ranges, checks the whole archive, and
preserves the metadata by content hash. Existing manifests cannot be overwritten.
Only the `x86_64-unknown-linux-gnu` archive is prepared; task images stay original.

Run `uv_release_cache.py serve --cache /cache --manifest /manifest.json` in a
loopback sidecar sharing `service:main`, with a readiness health check and both
cache and manifest mounted read-only. Set only the official installer's supported
`UV_INSTALLER_GITHUB_BASE_URL=http://127.0.0.1:18743` environment variable in the
task container. Installer scripts, versions, package contents, and normal model
traffic remain unchanged. Registered archives are rehashed before serving;
uncached uv versions/platforms redirect to their original HTTPS GitHub URLs.
Record this transport setting, utility, manifest, and native preflight evidence
before model work. This cache does not certify unsupported verifier dependencies.

For an observed managed-Python download failure, add its exact original build
and archive to a new manifest, for example `--python-build 20251014
--python-asset cpython-3.13.9+20251014-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`.
The same checks apply to the original `astral-sh/python-build-standalone` release
metadata. Set the documented
[`UV_PYTHON_INSTALL_MIRROR`](https://docs.astral.sh/uv/configuration/environment/#uv_python_install_mirror)
to `http://127.0.0.1:18743/astral-sh/python-build-standalone/releases/download`.
This changes the download route while retaining uv's original Python selection
and archive contents. Uncached Python builds redirect to their original GitHub
URLs; the mirror does not replace uv's embedded Python download index.

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

For a separately authorized infrastructure-recovery run, set the verifier
kwarg `retry_dependency_errors=true` explicitly. This also retries recognized
uv network download failures before pytest starts, using the same container,
agent output, native time limit, and maximum of three total attempts. A CTRF
report, pytest execution output, or a successful reward prevents this recovery;
valid scored failures stop immediately. Exhausted dependency failures raise
`VerifierDependencyError`, retain every attempt's evidence, and leave no
canonical reward. The default remains timeout-only; record the authorization
and selected policy in the experiment plan.

## Benchmark reports

Reports are available in [English](reports/en/) and
[Simplified Chinese](reports/zh-CN/), with matching filenames. Create or update
both full versions together, preserving results and evidence references. Raw
run evidence stays in Git-ignored `jobs/`; machine-readable results remain in
`results/`.

## Test the adapter

```bash
uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml \
  benchmarks/harbor/tests
```
