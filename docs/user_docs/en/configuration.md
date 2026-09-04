# Configuration Reference

[English](configuration.md) | [简体中文](../zh-CN/configuration.md) |
[User documentation](../README.md)

nanoPyCodeAgent reads credentials, the API endpoint, and the model from the
process environment. An optional user-level settings file can fill in values
that are absent from that environment.

## Configuration sources and precedence

From highest to lowest priority:

1. Environment variables already present in the nanoPyCodeAgent process.
2. The `env` object in `~/.nanoPyCodeAgent/settings.json`.
3. Built-in defaults for settings that have one.

The settings file only fills an environment key that is completely unset. It
never replaces a key that is already present. nanoPyCodeAgent does not load a
project `.env` file, has no project-level settings file, and has no CLI flags
for credentials, endpoint, or model selection.

The settings file is loaded before the Anthropic client is created and before
the model is selected, so the same precedence applies in interactive and
headless modes.

## Supported settings

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | One credential is required | none | Anthropic API key, or an API key accepted by a compatible third-party service. |
| `ANTHROPIC_AUTH_TOKEN` | One credential is required | none | Bearer token used for services that authenticate with `Authorization: Bearer`, such as OpenRouter's Anthropic-compatible endpoint. |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | Base URL used by the Anthropic SDK. Set it for a compatible proxy or third-party endpoint; leave it unset for the official API. |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Model passed to every Messages API call. |

At least one of `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` must provide a
usable credential. If neither is available, the command reports the missing
credentials on stderr and exits with status `1` before starting an Agent Run.

The settings-file loader accepts any key whose name begins with `ANTHROPIC_`.
The four variables above are the nanoPyCodeAgent configuration contract;
additional variables are interpreted, if at all, by the installed Anthropic
Python SDK and can change with that dependency.

## Environment variables

Set variables in the shell that starts the agent. For the official Anthropic
API, the minimum configuration is:

```bash
export ANTHROPIC_API_KEY="your-api-key"
nanoPyCodeAgent
```

For an Anthropic-compatible service, configure the credential form required by
that service, its base URL, and a model it exposes. For example:

```bash
export ANTHROPIC_AUTH_TOKEN="your-token"
export ANTHROPIC_BASE_URL="https://example.com/anthropic"
export ANTHROPIC_MODEL="provider/model-name"
nanoPyCodeAgent -p "run the test suite"
```

Environment variables are inherited in the normal operating-system way. The
agent does not persist them.

## Settings file

The optional settings file has the fixed user-level path:

```text
~/.nanoPyCodeAgent/settings.json
```

It must be UTF-8 JSON with a top-level object. Configuration values belong in
an `env` object, which must also be an object when present. The shape mirrors
the `env` field in [Claude Code settings](https://code.claude.com/docs/en/settings):

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_AUTH_TOKEN": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_MODEL": ""
  }
}
```

The empty strings are placeholders. Replace the values you use and leave the
rest empty or remove their keys. For example:

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "your-token",
    "ANTHROPIC_BASE_URL": "https://example.com/anthropic",
    "ANTHROPIC_MODEL": "provider/model-name"
  }
}
```

Settings-file rules:

- A missing file is normal and is ignored silently.
- A missing `env` field supplies no values. Only entries under `env` are read;
  other top-level fields are ignored.
- Only keys beginning with `ANTHROPIC_` are eligible; other environment keys
  are ignored.
- A value must be a string. Non-string values are ignored.
- Leading and trailing whitespace is removed from a settings-file value.
  Empty and whitespace-only values are ignored.
- An unreadable file, invalid UTF-8 or JSON, a non-object top level, or a
  non-object `env` value is a configuration error and stops startup with an
  exception.

The loader does not enforce file permissions. Because this file can contain
credentials, restrict access to your user account; for example:

```bash
chmod 600 ~/.nanoPyCodeAgent/settings.json
```

## Empty values and precedence

"Unset" and "set to an empty string" are different for environment variables.
The settings loader uses key presence to decide precedence:

| Environment state | Settings-file value | Result |
| --- | --- | --- |
| Key is unset | Non-empty string | The trimmed settings-file value is loaded. |
| Key is unset | Empty, whitespace-only, or non-string value | The entry is ignored; a built-in default may apply. |
| Key is present and non-empty | Any value | The environment value wins. |
| Key is present but empty or whitespace-only | Any value | The environment key still blocks the settings-file value. |

For `ANTHROPIC_MODEL`, an empty or whitespace-only final environment value
falls back to `claude-sonnet-4-6`. Empty credential or base-URL environment
values do not receive that fallback and can cause authentication or request
failures. Unset an empty environment variable if you want the settings file to
supply it:

```bash
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL ANTHROPIC_MODEL
```

## Precedence example

Given this file:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://settings.example/v1",
    "ANTHROPIC_MODEL": "settings-model"
  }
}
```

and this environment:

```bash
export ANTHROPIC_MODEL="environment-model"
```

the run uses `environment-model` and
`https://settings.example/v1`: the environment keeps the model while the file
fills the otherwise-unset base URL.

See the [CLI reference](cli_reference.md) for command modes, options, output,
and exit statuses.
