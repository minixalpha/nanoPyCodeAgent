# nanoPyCodeAgent

A nano code agent built in pure Python.

> "What I cannot create, I do not understand." — Richard Feynman, 1988

## Install / Run

Requires Python 3.13+ (managed automatically by [uv](https://docs.astral.sh/uv/)).

Run it directly once published to PyPI:

```bash
uvx nanoPyCodeAgent
```

Or run the current development branch straight from GitHub (no PyPI needed):

```bash
uvx --from "git+https://github.com/minixalpha/nanoPyCodeAgent" nanoPyCodeAgent
```

From a local checkout:

```bash
uv run nanoPyCodeAgent      # or: uv run main.py
```

## Releasing (maintainers)

Pushing a `v*` tag publishes to PyPI automatically via GitHub Actions
Trusted Publishing. One-time setup: add a pending publisher on
[PyPI](https://pypi.org/manage/account/publishing/) for repo
`minixalpha/nanoPyCodeAgent`, workflow `release.yml`, with no environment.

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```
