"""The command-line entry point: an interactive session or a headless run.

One command serves both. With a task — ``-p``, ``--prompt-file``, or piped
on stdin — the agent works that task and exits; with none, and a terminal
attached, it opens the usual prompt.

Three ways to hand over the task look redundant until you watch a benchmark
harness start an agent: some pipe the instruction on stdin to sidestep shell
quoting and command-length limits, some pass it as an argument and wire
stdin to /dev/null, and a task read from a file is what makes a long
instruction bearable to type. Accepting all three costs a few lines and
removes a reason for the agent to be unusable in someone's harness.
"""

import argparse
import sys
from pathlib import Path

from .agent import DEFAULT_MAX_TURNS, _package_version, run, run_headless

# Reserved by argparse for a misuse of the command line itself, and used here
# for the same: a task that cannot be read is a mistake in how the agent was
# invoked, not an outcome of running it.
EXIT_USAGE = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nanoPyCodeAgent",
        description=(
            "A nano code agent. Give it a task to run once and exit, or run "
            "it with no task in a terminal for an interactive session."
        ),
    )
    task = parser.add_mutually_exclusive_group()
    task.add_argument(
        "-p",
        "--prompt",
        metavar="TEXT",
        help="the task to carry out, then exit",
    )
    task.add_argument(
        "--prompt-file",
        metavar="PATH",
        help="read the task from this file, carry it out, then exit",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=DEFAULT_MAX_TURNS,
        metavar="N",
        help=(
            "stop a headless run after this many model replies "
            f"(default: {DEFAULT_MAX_TURNS})"
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"nanoPyCodeAgent {_package_version()}",
    )
    return parser


def _read_task(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str | None:
    """The task to run, or None to open an interactive session.

    Stdin counts as a task only when it is not a terminal, which is exactly
    the case where something piped one in. Anything that arrives — from an
    argument, a file, or a pipe — has to be a real instruction: an empty one
    means the caller believes it sent a task and did not, and silently
    starting a session (or a run with nothing to do) hides that.
    """
    if args.prompt is not None:
        task = args.prompt
    elif args.prompt_file is not None:
        try:
            task = Path(args.prompt_file).expanduser().read_text(encoding="utf-8")
        except OSError as exc:
            parser.error(f"cannot read --prompt-file: {exc}")
        except UnicodeDecodeError:
            parser.error(f"--prompt-file is not valid UTF-8 text: {args.prompt_file}")
    elif sys.stdin is not None and not sys.stdin.isatty():
        task = sys.stdin.read()
    else:
        return None

    task = task.strip()
    if not task:
        parser.error(
            "the task is empty; pass it with -p/--prompt or --prompt-file, "
            "or pipe it on stdin"
        )
    return task


def main(argv: list[str] | None = None) -> int:
    """Parse the command line and run, returning the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.max_turns < 1:
        parser.error("--max-turns must be at least 1")

    task = _read_task(args, parser)
    if task is None:
        return run()
    return run_headless(task, max_turns=args.max_turns)
