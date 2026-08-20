# nanoPyCodeAgent

[English](README.md) | [简体中文](README.zh-CN.md)

A nano code agent built in pure Python.

> "What I cannot create, I do not understand." — Richard Feynman, 1988

## Usage

nanoPyCodeAgent requires Python 3.13 or newer.

### How to Run

There are a few ways to run it — pick whichever fits your workflow.

#### Run without installing

Use `uvx` to run the latest release without installing anything:

```bash
uvx nanoPyCodeAgent
```

#### Run after installing

Install it as a persistent command-line tool, then run it from anywhere:

```bash
uv tool install nanoPyCodeAgent   # or: pipx install nanoPyCodeAgent
nanoPyCodeAgent
```

#### Run one task and exit

Give it a task and it works through it on its own, with no prompt and nothing
to confirm — the shape a script or a benchmark harness needs:

```bash
nanoPyCodeAgent -p "add a --version flag and run the tests"
nanoPyCodeAgent --prompt-file task.md
printf "%s" "$TASK" | nanoPyCodeAgent
```

The task is carried out in the current directory. `--max-turns N` caps how
many model replies one run may spend (50 by default).

A run like this exits `0` whenever the agent actually ran — including when it
gave up or ran out of turns with the task unfinished, which is for whatever
checks the result to judge. A non-zero exit means the run could not happen at
all: `1` for missing credentials or an API that kept refusing, `2` for a
misused command line.

#### Run a branch or tagged version

Run an unreleased branch or a specific release tag straight from GitHub:

```bash
# latest commit on a branch
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@main" nanoPyCodeAgent

# a specific tag
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@v0.1.0" nanoPyCodeAgent
```

### Configuration

Credentials and the model come from two sources: **environment variables** and
an optional user-level config file at `~/.nanoPyCodeAgent/settings.json`.
Environment variables take precedence — the config file only fills in keys you
have not set in the environment.

The config file mirrors [Claude Code's settings](https://code.claude.com/docs/en/settings):
put the values under an `env` object. Empty or whitespace-only values are ignored.

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_MODEL": ""
  }
}
```

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key, or the key for a third-party / proxy service. |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | Point the SDK at a non-official / proxy endpoint. Leave it unset to use the official API — an empty value breaks requests. |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Override the model. An empty or whitespace-only value falls back to the default. |

### How to Update

Upgrade an installed tool to the latest release:

```bash
uv tool upgrade nanoPyCodeAgent   # or: pipx upgrade nanoPyCodeAgent
```

## Releasing

For maintainers: see [docs/RELEASING.md](docs/RELEASING.md) for the release process and prerequisites.
