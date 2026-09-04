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
```

The task runs in the current directory and the command exits when the run
ends. See the [complete CLI reference](docs/user_docs/en/cli_reference.md) for
all task input methods, options, exit statuses, trajectory output, and Event
Journal behavior.

#### Run a branch or tagged version

Run an unreleased branch or a specific release tag straight from GitHub:

```bash
# latest commit on a branch
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@main" nanoPyCodeAgent

# a specific tag
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@v0.1.0" nanoPyCodeAgent
```

### Configuration

Set `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` before running the agent.
You can also configure the endpoint and model through environment variables or
`~/.nanoPyCodeAgent/settings.json`. See the [configuration reference](docs/user_docs/en/configuration.md)
for supported variables, defaults, file format, precedence, and empty-value
handling.

### How to Update

Upgrade an installed tool to the latest release:

```bash
uv tool upgrade nanoPyCodeAgent   # or: pipx upgrade nanoPyCodeAgent
```

## Releasing

For maintainers: see [docs/RELEASING.md](docs/RELEASING.md) for the release process and prerequisites.
