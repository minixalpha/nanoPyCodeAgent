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
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
```

Run new benchmarks through the standard entry point, from the repository root:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter run \
  --config benchmarks/harbor/configs/restricted-wal.json
```

This example pins the WAL task revision and uses `deepseek/deepseek-flash`.
Set the endpoint and credentials for that model, or copy the configuration and
change `agents[].model_name`, task selection, and budgets for another run. These
are Harbor JSON configurations with an additional `integrity` section; the entry
point supplies the standard verifier, integrity, and cache policies. It accepts the repository's `NanoPyCodeAgent` adapter
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

### Evaluation integrity protocol

New standard runs require an explicit `integrity` section:

```json
{
  "integrity": {
    "protocol": "restricted-v1",
    "allowed_hosts": ["api.deepseek.com"],
    "probe_url": "https://example.com/"
  }
}
```

The same policy and English integrity instructions apply to Nano, Pi, and the
DeepSeek Harness adapter. Their native tools and model settings are preserved.
The actual inference host must be listed explicitly; provider endpoints are not
silently added. Exact DNS hosts are accepted; wildcards, IP literals, CIDRs,
extra agent network exceptions, injected skills, resumed sessions, external
tools, and filtered logs are rejected. Do not allowlist general code hosting or
search sites: that would reopen access to reference answers. Task-required data
or reviewed dependency/documentation services need explicit, preregistered hosts.
An allowed service can itself expose reference material; an allowlist is not a
content classifier.

Installation and registered dependency preflight use the task's original public
network. Before model work, a public HTTPS probe must succeed, the same probe
must fail under the allowlist, and allowed hosts must remain reachable. Redirects
are not followed by probes. A failed positive control is an infrastructure
failure, never proof of blocking. `--install-only` exercises these checks too.
The run boundary rechecks enforcement within the native agent time limit.
Harbor's external egress sidecar enforces the restriction; shell proxy variables
are not the security boundary. The task container loses `NET_RAW`, `NET_ADMIN`,
`SYS_ADMIN`, and `SYS_PTRACE`, and cannot gain privileges through setuid binaries.
Host directories, including verifier logs, are not mounted into the container.
UDP DNS forwarding is permitted only to the exact upstream resolver addresses
reported by Docker's trusted sidecar; those addresses are recorded. DNS failure
does not count as a successful HTTPS blocking probe.

Version one supports single-step Linux Dockerfile/prebuilt-image tasks with
public native network policies. Custom Compose services, extra mounts,
environment overrides, and task MCP servers are unsupported and fail closed.
These limits deliberately exclude the historical dependency-cache Compose
overlays until they have a reviewed isolation design. The protocol preserves
task images, package sources, official tests, resources, and native deadlines.
CPU, memory, storage, GPU, and TPU overrides are rejected; CPU and memory
enforcement must be `auto` (Docker's native limits) or `limit`.
Missing task dependencies remain setup or task failures according to the
original verifier; network restrictions do not authorize changing the task.

All three agents use process supervision under this protocol. Network access
stays restricted through cancellation cleanup. Controller-collected output,
network-rule snapshots, preflight outcomes, and sidecar diagnostic logs are saved
under the job's host-only `.integrity/<trial-id>/` directory, outside Harbor's
native trial-log rewriting. These records are private
because output can contain credentials. They preserve collected bytes, but do
not prove complete observation of every tool action or network request.

Existing shared verifiers remain shared: after quiescence checks and evidence
collection, their native network is restored for official verification. They
remain vulnerable to malicious submitted code and retained services influencing
grading. Tasks already configured with separate verifiers retain that boundary;
the adapter records the mode without rewriting tasks. Migrating existing tasks,
isolating submitted code inside the grader, private held-out tasks, and DNS/covert
channel defenses are separate work. `restricted-v1` blocks the observed direct
web answer retrieval; it is not a proof against every adversarial strategy or
training-data contamination.

For an explicitly registered historical-protocol reproduction, pass
`--legacy-open-network` with the original configuration. This opt-out is recorded
as `legacy-open-network`, cannot be combined with `integrity`, and supplies no
integrity enforcement. Historical configurations and reports are unchanged.
Do not combine restricted and historical results into one comparable baseline.

### Freeze, review, and integrity-adjusted scores

Completed restricted runs automatically freeze output hashes and write candidate
flags to `jobs/<job-name>-input/audit/audit.json`. They do not automatically earn
an integrity-cleared score. The same audit can be invoked explicitly:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter audit \
  --job-dir jobs/<job-name> --output-dir jobs/<job-name>-input/audit
```

The output directory must be outside the job. Auditing refuses unfinished jobs,
symbolic links, special files, and changes to an existing freeze. Scanning covers
native text/JSON logs across adapters plus collected output and egress evidence;
findings contain file/line locations, not raw credential-bearing excerpts.
Patterns are triage hints: inspect surrounding calls and results, including
blocked versus successful retrieval, before deciding. No matches do not prove a
clean attempt. `clear` means no violation observed in the reviewed evidence.

Create a review bound to the exact `freeze.json` SHA256, using actual trial IDs
and evidence paths from that manifest:

```json
{
  "freeze_sha256": "<SHA256 of freeze.json>",
  "trials": {
    "<trial-id>": {
      "verdict": "violation",
      "reviewer": "<reviewer identifier>",
      "reason": "Downloaded and used the task's reference solution.",
      "evidence": ["<trial-id>/agent/pi.txt"]
    }
  }
}
```

Pass `--review /path/to/review.json` to the audit command. Verdicts are `clear`
or `violation`; every verdict requires a reviewer, reason, and frozen evidence.
Each review and resulting audit is saved under its hash, preserving previous
decisions. Raw Harbor rewards and exceptions are never overwritten. Confirmed
violations receive an effective zero and stay in the denominator. Pending
reviews have no effective score, and no adjusted pass rate is published until
all eligible trials are reviewed. Setup/verifier errors remain unscored. A native
agent timeout is eligible only when cancellation was confirmed and an official
binary reward exists. Missing required enforcement is an integrity error.

Run the optional model-free Docker probe with an existing image containing
Python 3 and CA certificates:

```bash
NANOPY_INTEGRITY_TEST_IMAGE=<image> uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml benchmarks/harbor/tests/test_integrity_docker.py
```

The probe builds Harbor's pinned egress sidecar, tests allowed and denied HTTPS,
checks that packet marks cannot bypass filtering, and removes only its own
containers. It does not call a model or run benchmark solutions/tests.

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

The reviewed `pytorch-model-recovery` revision also has a dependency-only
profile. It uses the original uv 0.9.5 installer and the verifier's Python 3.13,
pytest 8.4.1, torch 2.7.1, and pytest-json-ctrf 0.3.5 requirements, then runs only
`pytest --version` from `/tmp`. It does not import the submitted model or run
the task's tests. Other revisions require profile review.

Reviewed revisions of `multi-source-data-merger`, `pytorch-model-cli`,
`query-optimize`, `torch-pipeline-parallelism`, and `torch-tensor-parallelism`
also have dependency-only profiles. They preserve each original wrapper's
Python version, package pins, APT dependencies, and index options, and run only
`pytest --version` from `/tmp`. In particular, only the CLI profile adds the
original PyTorch CPU index and `unsafe-best-match` strategy; the other PyTorch
profiles keep their original default index. Task metadata and verifier-wrapper
hashes are recorded with these five profiles.

Every installation writes `agent/bootstrap.json`, including partial progress
on failure. Preflight failure stops the trial before any model call. The
official verifier script remains unchanged and may still access the network
when it runs; a successful preflight is not a guarantee against later outages.
Full standard runs enable the timeout retry policy below by default, with zero
whole-trial retries. CI checks these contracts without model calls or Docker.

### Verified PyPI wheel transport

Large original PyPI wheels can use the optional loopback cache:

```bash
python benchmarks/harbor/scripts/pypi_wheel_cache.py \
  --cache .cache/nanopy-harbor/pypi-ranges --bind 127.0.0.1 --port 18744
```

For Docker tasks, run it in a sidecar sharing the task's network namespace and
mount the cache only in that sidecar. Register
`UV_DEFAULT_INDEX=http://127.0.0.1:18744/simple` in the task environment.
The service always fetches current PyPI index metadata, preserving all versions,
requirements, yanks, hashes, and extra-index settings. Only wheel URLs change to
the loopback cache. Source-distribution URLs and PEP 658 metadata bytes remain
original; metadata is forwarded fresh. Every wheel request rechecks its
filename, size, SHA256, and original HTTPS URL against current PyPI release
metadata before restoring any cached bytes. Metadata outages and corrupt files
fail closed. The cache is not an offline or alternative package index.

A cold wheel is fully downloaded and verified before its body is served.
Allow a suitable uv HTTP timeout (for example `UV_HTTP_TIMEOUT=600`) within
the separately registered setup deadline. Native agent and verifier timeouts
remain unchanged.

The existing bounded range downloader verifies every range and the complete
wheel digest. File locks protect publication across task sidecars. Register the
transport and its scripts before model work, run dependency-only preflight,
and preserve original task images, scripts, package versions, sources, and
per-attempt agent/verifier limits.

Use `--audit-log /cache/run-events.jsonl` to retain current release metadata
and verified cache-hit events after the sidecars exit. The append-only log is
locked across processes and includes the originating container instance.

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
They reject model-loading diagnostics even when Pi exits zero, and require the
requested provider/model in the offline listing. Jobs with multiple Pi agents
preserve distinct public configurations in immutable job-local files; the
manifest records each `model_config_file` and its digest. Concurrent preparations
reuse a verified distribution published by another process and clean staging
directories on success or failure.
Native sessions and completed JSON events remain in `agent/pi/` and `agent/pi.txt`.
Usage includes compaction when Pi supplies it, and reported costs are estimates.
Missing usage stays diagnosed. Pi does not currently generate an ATIF trajectory.
Failed assistant streams with initialized zero usage remain unknown even if a
native retry succeeds. Known token and cost subtotals are retained, with partial
accounting flags for missing usage or cost.
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

The first [Pi + DeepSeek Flash dev34 report](reports/en/pi-deepseek-flash-dev34-20261024.md)
preserves all 34 attempts, the supervision amendment, two unscored legacy
timeouts, public-reference exposure, and partial accounting. It does not claim
a complete, uncontaminated 34-task pass rate.

The authorized [three-task Pi rerun](reports/en/pi-deepseek-flash-dev3-rerun-20261102.md)
recorded two official passes and one scored failure after confirmed timeout
cancellation. Both new passes accessed public reference solutions and tests;
neither is an independent solution. Original outcomes remain unchanged. The
rerun also fixed Pi installation checks when Harbor returns absent output streams.

The [restricted two-task follow-up](reports/en/pi-restricted-dev2-20261104.md)
allowed only the DeepSeek API host during model work. WAL passed all seven
official tests with no integrity violation observed in the reviewed evidence.
Pipeline timed out during dependency preparation before any model call, so its
behavior under restriction remains untested. Historical results remain separate.

### DeepSeek Harness baselines

`harbor_adapter:DeepSeekHarnessAgent` runs the upstream Python SDK's
`sdk-minimal` profile, as recommended by DeepSeek Harness's `BENCHMARK.md`.
Register `distribution_path`, `distribution_sha256`, and optional
`reasoning_effort` (default `high`) in the agent kwargs. The distribution is an
offline `wheels/` directory containing the SDK, native runtime, and all Python
dependencies, plus `distribution.json` with `version`, `source_commit`,
`source_archive_sha256`, `sdk_wheel`, and `runtime_wheel`. The digest covers every
file and permission; the standard workflow snapshots and rechecks the bytes.

Build the runtime and SDK from the selected upstream checkout using its documented
Python contributor workflow. Task installation uses Python 3.13 and the frozen
wheelhouse. Installation-only checks initialize the actual SDK profile and model
without sending a task prompt, and run the existing verifier dependency preflight.
Model work requires `DEEPSEEK_API_KEY` and uses the official Messages endpoint.
Each task receives a fresh Harness home and session, with upstream prompts,
tools, compaction, retries, and generation defaults. Native logs remain in
`agent/dsh/`; SDK events, completion status, and diagnostics remain beside it.

Configurations must set `verifier.kwargs.require_agent_quiescence=true`.
The shared Linux supervisor confirms cancellation of the agent process tree
before verification. A non-completed SDK finish reason is an execution error.
Reported tokens include native assistant and compaction usage; missing records
and interrupted runs remain partial, and cost remains unknown. This baseline
does not impose Pi's generation settings or Nano's turn and work budgets.

The first [official Harness dev34 report](reports/en/deepseek-harness-dev34-20261030.md)
records 22 passes, six scored failures, and six unscored errors on Pi's existing
34-task pool. Normal SDK closure in the pinned upstream runtime stops managed
background services, including the probe's `nohup` server. This affects service
tasks: KV and PyPI failed official checks after successful agent self-tests.
The report retains those failures and documents the
[keyless lifecycle probe](scripts/probe_deepseek_lifecycle.py). Treat these
results as measurements of the registered SDK configuration.

The separately authorized [six-task supplement](reports/en/deepseek-harness-dev6-supplement-20261101.md)
reran the unscored tasks with reviewed dependency preflight and verified original
PyPI wheel transport: four passed, two failed, and none remained unscored. The
original results stay unchanged. Combining the 28 original accepted attempts
with these six new attempts gives mixed coverage of 26 passes and eight failures;
this outcome-selected supplement is not an independent benchmark.

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

For separately authorized recovery of pytest collection failures, also set
`retry_collection_errors=true`. This retries only an explicit collection abort
before any test case runs. A successful reward, executed test cases, or an
ambiguous CTRF report prevents this recovery. Exhaustion raises
`VerifierCollectionError` and preserves archived rewards without publishing a
canonical score. The default is false, and the three-attempt limit is shared
with timeout and dependency recovery.

When future verification may be needed, set Docker's
`environment.kwargs.keep_containers=true` to retain the stopped task containers
and register solution paths such as `/app` in `artifacts`.
`environment.delete=false` alone still removes Docker containers. Harbor collects
the registered files before verification. Keep both the
artifact manifest and file hashes with the run evidence; trajectories alone do
not preserve binaries or the original system state.

For an explicitly authorized additional verifier batch on a retained Docker
trial, use the repository entry point without starting an agent:

```bash
uv run --project benchmarks/harbor python -m harbor_adapter verify-retained \
  --trial-dir jobs/example/task__trial \
  --task-dir /path/to/the/original/task \
  --container task__trial__env-main-1 \
  --output-dir jobs/example-additional-verifier-batch
```

All original project services must be stopped. The command starts those same
containers, waits for service health checks, verifies frozen `/app` artifacts
and original test hashes, and runs at most three attempts with the native task
timeout. The optional `--retry-dependency-errors` and
`--retry-collection-errors` flags require the same separate authorization as
their verifier kwargs. Any completed score, including zero, stops the batch.
The original trial logs are temporarily set aside inside the retained container
and restored afterward. New attempt logs, implementation sources, policy,
hashes, and integrity checks go into the separate output directory. Containers
are stopped and retained after the batch. This does not change the original
trial result or authorize repeated batches automatically.

To give dependency preparation its own budget on a retained solution, add
`--dependency-timeout-sec 3600`. This requires a reviewed profile for the exact
task revision and checks its registered task-file hashes. Preparation runs once
in the same container before verification; its logs and status are recorded
under `dependency-preparation/`. A preparation timeout or nonzero exit is a
setup failure with no score, and verification does not start. On success, the
unchanged official verifier script runs with the original per-attempt timeout
(900 seconds for `pytorch-model-recovery`). Its own remaining dependency checks
are still included in those 900 seconds. The larger preparation deadline never
extends the verifier deadline. Record this preparation policy separately from
earlier baseline results, even when the solution is identical.

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
