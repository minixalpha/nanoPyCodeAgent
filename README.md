# nanoPyCodeAgent

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

### How to Update

Upgrade an installed tool to the latest release:

```bash
uv tool upgrade nanoPyCodeAgent   # or: pipx upgrade nanoPyCodeAgent
```
