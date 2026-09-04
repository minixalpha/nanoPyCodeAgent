# CLI Reference

[English](cli_reference.md) | [简体中文](../zh-CN/cli_reference.md) |
[User documentation](../README.md)

`nanoPyCodeAgent` uses one command for an interactive session or a single
headless task. Which mode starts depends on whether the command receives a
task.

## Synopsis

```text
nanoPyCodeAgent [-h] [-p TEXT | --prompt-file PATH] [--max-turns N]
                [--trajectory PATH] [--version]
```

## Modes and task input

### Interactive mode

The command starts an interactive session when no task option is present and
stdin is a terminal:

```bash
nanoPyCodeAgent
```

Enter `/exit`, press Ctrl-D, or press Ctrl-C at the `You>` prompt to end the
session normally. `--max-turns` does not limit interactive exchanges.
`--trajectory` is not available in interactive mode.

### Headless mode

Any of these input methods starts one headless run:

| Input method | Example | Behavior |
| --- | --- | --- |
| `-p TEXT`, `--prompt TEXT` | `nanoPyCodeAgent -p "run the tests"` | Uses the argument as the task. |
| `--prompt-file PATH` | `nanoPyCodeAgent --prompt-file task.md` | Reads the entire file as UTF-8. `~` is expanded in the path. |
| Non-terminal stdin | `printf "%s" "$TASK" \| nanoPyCodeAgent` | Reads stdin to EOF as the task when neither task option is present. |

`-p`/`--prompt` and `--prompt-file` are mutually exclusive. An explicit task
option takes priority over stdin. Leading and trailing whitespace is removed
from every task; an empty or whitespace-only task is a usage error. Therefore,
running the command with empty redirected stdin, such as from `/dev/null`, does
not start an interactive session.

The headless system prompt tells the agent to work autonomously, avoid asking
for confirmation, verify its work, and finish with a short summary.

## Current working directory

nanoPyCodeAgent has no working-directory option. The process's current working
directory is the workspace for the run, including file-tool operations and
shell commands. Start the command from the directory you want the agent to
work in:

```bash
cd /path/to/project
nanoPyCodeAgent -p "fix the failing tests"
```

Relative prompt-file and trajectory paths are also resolved from the current
working directory.

## Options

| Option | Default | Contract |
| --- | --- | --- |
| `-h`, `--help` | — | Print help and exit successfully. |
| `-p TEXT`, `--prompt TEXT` | — | Run `TEXT` as one headless task. |
| `--prompt-file PATH` | — | Read one headless task from a UTF-8 file. The file must be readable and contain a non-empty task. |
| `--max-turns N` | `50` | Allow at most `N` model replies in a headless run. `N` must be an integer of at least `1`. |
| `--trajectory PATH` | disabled | Write the headless run as one ATIF-v1.7 JSON document. See [Trajectory output](#trajectory-output). |
| `--version` | — | Print `nanoPyCodeAgent VERSION` and exit successfully. |

`--max-turns` counts model replies, including replies that contain only tool
calls. If reply `N` still requests tools, those tools are not run because no
reply remains to consume their results. Reaching the limit prints a diagnostic
to stderr but is still a normal headless exit.

## Output channels

During a headless run, stdout carries the streamed model text plus echoed tool
calls and tool results. The startup banner, turn-limit diagnostic, and API
errors go to stderr. This separation lets callers capture the run output while
retaining operational diagnostics.

`--trajectory` does not change stdout. There is currently no JSON or JSONL
stdout mode.

## Exit statuses

| Status | Meaning |
| --- | --- |
| `0` | Help or version output completed; an interactive session ended normally; or a headless run started and returned control, even if the model gave up, left work incomplete, or exhausted `--max-turns`. |
| `1` | A runtime or infrastructure failure prevented a normal run, including missing API credentials or an Anthropic/HTTP API failure. |
| `2` | Command-line usage was invalid, including conflicting or empty task input, an invalid turn limit, an unreadable prompt file, or an invalid trajectory destination. |

Exit status `0` does not certify that a headless task succeeded. A script or
benchmark must inspect the resulting workspace or run its own verifier.
Unexpected failures not handled by the CLI may also terminate the process with
a non-zero status and a traceback.

## Trajectory output

Use `--trajectory PATH` with a headless task to write one complete
[ATIF-v1.7](https://www.harborframework.com/docs/agents/trajectory-format)
JSON document:

```bash
nanoPyCodeAgent -p "read README.md and summarize it" \
  --trajectory ./trajectory.json
```

The trajectory is a separate artifact; it does not replace or redirect
stdout. Its task, model replies, tool arguments, tool results, timing, usage,
cost information when available, and terminal state describe a single Agent
Run. A caught API failure after the run has started produces a partial
trajectory with a failed terminal state.

The path contract is:

- `--trajectory` requires a headless task and cannot be used in interactive
  mode.
- `PATH` must name a file; `-` is rejected because stdout is reserved for run
  output.
- `~` is expanded, and relative paths use the current working directory.
- The parent directory must already exist.
- The destination must not already exist, including as a symbolic link. The
  command never overwrites it.
- The file is published after the run reaches a terminal state and is created
  with owner-only permissions (`0600`). A failure before the Agent Run starts,
  such as missing credentials or invalid CLI input, creates no trajectory.

Trajectories can contain secrets and repository content. Store and share them
as sensitive data.

## Internal Event Journals

Each Agent Run automatically creates a replayable internal JSONL Event Journal
under `~/.nanoPyCodeAgent/journals/`. The directory is forced to owner-only
access (`0700`), and each journal file is `0600`. A headless task that starts
has one Agent Run; in an interactive session, each submitted user message
starts a new Agent Run and therefore a new journal.

The journal is the internal source from which an optional ATIF trajectory is
projected. It is not public run output, not an ATIF trajectory, and has no CLI
flag to redirect or disable it. Journal files are not rotated automatically.
They can contain prompts, model replies, tool arguments, tool results, and
repository content, so treat them as sensitive data.

See the [configuration reference](configuration.md) for credentials, model
selection, and endpoint settings.
