# Harbor adapter

[English](README.md) | [简体中文](README.zh-CN.md)

This isolated workspace contains the nanoPyCodeAgent adapter for Terminal-Bench
and other benchmarks run by Harbor. It is development infrastructure, not part
of the end-user `nanoPyCodeAgent` package. Harbor is pinned to 0.21.0 in this
workspace's lockfile.

## Run a benchmark

Set the same `ANTHROPIC_*` environment variables used by the CLI. For a
third-party or proxy endpoint, set all three explicitly:

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_BASE_URL="https://gateway.example"
export ANTHROPIC_MODEL="provider-model-name"
```

From the repository root, run Harbor through this workspace and pin the agent
installed in the task container:

```bash
uv run --project benchmarks/harbor harbor run \
  --task terminal-bench/openssl-selfsigned-cert \
  --agent harbor_adapter:NanoPyCodeAgent \
  --agent-kwarg git_ref=<commit-sha> \
  --model anthropic/claude-sonnet-4-6 \
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

The adapter also asks the agent to write an ATIF-v1.7 trajectory directly to
`/logs/agent/trajectory.json`. Harbor collects that file as the trial's native
ATIF output and backfills prompt, completion, cache-token, and cost totals into
the agent result. Missing, invalid, or partial trajectories remain explicitly
diagnosed; unknown usage or cost is not reported as zero.

`ANTHROPIC_MODEL` takes precedence over Harbor's `--model`. When it is absent,
the adapter strips the first provider prefix from `--model`. Harbor-native
provider credentials and configured base URLs are also normalized to the
`ANTHROPIC_*` variables expected by nanoPyCodeAgent's SDK.

## Test the adapter

```bash
uv run --project benchmarks/harbor pytest \
  -c benchmarks/harbor/pyproject.toml \
  benchmarks/harbor/tests
```
