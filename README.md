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

#### Run a branch or tagged version

Run an unreleased branch or a specific release tag straight from GitHub:

```bash
# latest commit on a branch
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@main" nanoPyCodeAgent

# a specific tag
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent@v0.1.0" nanoPyCodeAgent
```

### Configuration

Credentials and the model are read from environment variables. A local `.env`
file works too — copy `.env.example` to `.env` and fill it in (`.env` is
git-ignored).

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
