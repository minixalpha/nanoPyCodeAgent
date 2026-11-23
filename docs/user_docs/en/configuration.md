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

The per-reply generation limit also accepts `--max-tokens N`. For this setting,
the order is **CLI > environment > settings file > 32768**. It is resolved once
at startup and applies to main-agent replies in that invocation. Permission
reviews have a separate fixed output limit, described below.

## Permission modes

Set `permission_mode` at the top level of `~/.nanoPyCodeAgent/settings.json`,
outside `env`. The default is `auto`; the only other accepted value is `full`.
An invalid value stops startup. There is no CLI or environment override.
The value is fixed for the invocation, including all interactive exchanges;
editing the file while the agent runs affects only a later invocation.

- `auto`: Every valid tool call is reviewed through an independent request
  using the current endpoint and model, without giving the reviewer tools.
  `pass` permits execution; `not_pass` returns the denial and reason to the
  main model without executing the tool. Technical review failures ask for
  one-call approval in interactive mode; only `y` or `yes` approves. In
  headless mode, failure returns an error without reading input or executing.
- `full`: Ordinary calls skip model review. Use it when you want unrestricted
  tool execution within your chosen environment.

Both modes validate arguments and block some literal catastrophic operations,
such as root deletion and raw disk destruction. This limited command check
cannot analyze arbitrary scripts or equivalent actions in other languages.
Neither mode provides a sandbox or guarantees safety.

Reviews add model usage and latency. Each has a 2048-token output limit and a
60-second SDK request timeout, capped by the remaining task time. SDK retries
still apply. Reviews do not consume `--max-turns`, but their time counts toward
`--time-budget-seconds`, and their usage and costs appear in the journal and
trajectory. An exhausted task deadline stops the task without manual fallback.

## Supported settings

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | One credential is required | none | Anthropic API key, or an API key accepted by a compatible third-party service. |
| `ANTHROPIC_AUTH_TOKEN` | One credential is required | none | Bearer token used for services that authenticate with `Authorization: Bearer`, such as OpenRouter's Anthropic-compatible endpoint. |
| `ANTHROPIC_BASE_URL` | No | `https://api.anthropic.com` | Base URL used by the Anthropic SDK. Set it for a compatible proxy or third-party endpoint; leave it unset for the official API. |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Model passed to every Messages API call. |
| `ANTHROPIC_MAX_TOKENS` | No | `32768` | Positive integer controlling the generated tokens per model reply. Overridden by `--max-tokens`. |

At least one of `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` must provide a
usable credential. If neither is available, the command reports the missing
credentials on stderr and exits with status `1` before starting an Agent Run.

The settings-file loader accepts any key whose name begins with `ANTHROPIC_`.
The five variables above are the nanoPyCodeAgent configuration contract;
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
  "permission_mode": "auto",
  "env": {
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_AUTH_TOKEN": "",
    "ANTHROPIC_BASE_URL": "",
    "ANTHROPIC_MODEL": "",
    "ANTHROPIC_MAX_TOKENS": ""
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
    "ANTHROPIC_MODEL": "provider/model-name",
    "ANTHROPIC_MAX_TOKENS": "32768"
  }
}
```

Settings-file rules:

- A missing file is normal and is ignored silently.
- A missing `env` field supplies no environment values. `permission_mode` is
  read separately; other top-level fields are ignored.
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

For `ANTHROPIC_MAX_TOKENS`, a final environment value that is empty, non-integer,
zero, or negative is a usage error (exit `2`) before any model request. A valid
CLI override takes precedence even over an invalid budget in the environment.
Settings-file entries follow the string-only and placeholder rules above;
write the budget as `"32768"`, not a JSON number.

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
