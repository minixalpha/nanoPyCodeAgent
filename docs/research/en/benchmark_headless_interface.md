# What Benchmarks Require of a Headless Agent

> Generated from the Chinese source [`../zh-CN/benchmark_headless_interface.md`](../zh-CN/benchmark_headless_interface.md). Do not edit by hand.

Surveyed on 2026-08-18.

[`code_agent_benchmark.md`](code_agent_benchmark.md) concluded: build headless mode first, then talk about scores. But "build headless mode" is not a single instruction — what each benchmark asks of an agent differs enormously. One specifies a Python class interface, one specifies a single JSON field, and one specifies nothing at all but hard-codes its runner inside its own repository. This document reads the integration surface of all three candidate benchmarks down to the source level and then converges on the minimum contract nanoPyCodeAgent should implement.

The conclusion up front: **the three share only five requirements, and the most counter-intuitive of them is "exit 0 even when the task was not solved".**

---

## 1. Terminal-Bench 2.1 / Harbor

The only one of the three that genuinely **specifies an interface**. And note the shape: what you write is not "an agent that can be invoked from the command line" but **a Python adapter class running inside the Harbor process**, which in turn installs and invokes your CLI inside the container.

### 1.1 The adapter interface

Harbor has two agent kinds. A CLI that runs inside the container is the second:

```python
# External agent (the agent process lives outside the container)
from harbor.agents.base import BaseAgent

class MyExternalAgent(BaseAgent):
    @staticmethod
    def name() -> str: ...
    def version(self) -> str | None: ...
    async def setup(self, environment: BaseEnvironment) -> None: ...
    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None: ...
```

```python
# Installed agent (the agent is installed into the container) — nanoPyCodeAgent's category
from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template

class MyInstalledAgent(BaseInstalledAgent):
    async def install(self, environment: BaseEnvironment) -> None:
        await self.exec_as_root(environment, command="...")   # system packages
        await self.exec_as_agent(environment, command="...")  # user-level installs

    @with_prompt_template
    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None: ...

    def populate_context_post_run(self, context: AgentContext) -> None: ...
```

Only `install()` and `run()` are actually required; `populate_context_post_run()` feeds the trajectory and token accounting back to Harbor — optional, but valuable (see §1.4).

How to run it:

```bash
harbor run -d terminal-bench/terminal-bench-2-1 \
           --agent-import-path "path.to.agent:SomeAgent" -k 5
```

(The Harbor docs also show the equivalent `--agent path.to.agent:SomeAgent` form.)

### 1.2 How the instruction reaches the CLI: two official examples

**Claude Code** (`src/harbor/agents/installed/claude_code.py`) — injected via an environment variable first, then fed in over **a stdin pipe**, which avoids shell escaping and command-line length problems:

```bash
export PATH="$HOME/.local/bin:$PATH"; \
harbor_claude_code_instruction_<uuid>="$HARBOR_CLAUDE_CODE_INSTRUCTION_<UUID>"; \
unset HARBOR_CLAUDE_CODE_INSTRUCTION_<UUID>; \
printf "%s" "$harbor_claude_code_instruction_<uuid>" | \
claude --verbose --output-format=stream-json --print 2>&1 | tee /logs/agent/claude-code.txt
```

**mini-swe-agent** (`src/harbor/agents/installed/mini_swe_agent.py`) — a command-line argument, with **stdin explicitly wired to `/dev/null`**:

```bash
mini-swe-agent --yolo --model=<model> --task=<shlex.quote(instruction)> \
  --output=<trajectory-path> --exit-immediately 2>&1 </dev/null | tee /logs/agent/mini-swe-agent.txt
```

nanoPyCodeAgent should support both shapes: `-p/--prompt` for the argument form, and reading all of stdin when it is not a tty for the pipe form. Note that `--exit-immediately` semantics — run to completion and exit rather than entering a REPL — is a requirement, not an option.

### 1.3 The hard constraints

All of the following were read out of the Harbor source; none of it is in the documentation:

1. **A non-zero exit code marks the whole trial as an agent failure.** `BaseInstalledAgent._exec()` wraps every command as `set -o pipefail; <cmd>`, and a non-zero return code raises `NonZeroAgentExitCodeError`.
   → **"Turn limit reached but the task is unsolved" must exit 0**, or it will be treated as an infrastructure fault (and may trigger a retry, burning money for nothing). This runs against intuition and contradicts the first draft of `code_agent_benchmark.md`.
2. **Harbor scans the agent's stdout/stderr with regexes to classify errors.** `ERROR_PATTERNS` covers rate limits, usage limits, 500s, Overloaded, mid-response disconnects, output-token overruns, context-window overruns, not-logged-in, safety refusals, and network errors; the resulting exception types feed the retry policy — the usage the source comments give is `harbor run --max-retries 3 --retry-include ApiRateLimitError`.
   → The agent should print API errors **verbatim** rather than swallowing them. That halves the retry logic needed on the agent side: basic backoff is enough.
3. **No `--workdir` is needed.** `run()` does not pass `cwd` to `exec_as_agent`, so the container's default WORKDIR is the task working directory. Terminal-Bench uses `/app` — the session directory `$CLAUDE_CONFIG_DIR/projects/-app` hard-coded in `claude_code.py` is its slugified form. The agent only has to work in the process's current cwd.
4. **Log paths are conventional.** The agent writes its own logs to `/logs/agent/`. Under `/logs/verifier/`, `reward.txt` (a single int or float, typically 1/0) or `reward.json` (multiple metrics) is written by the **test script**; the agent neither writes it nor should read `/tests/`.
5. **Credentials and model selection are injected purely through environment variables.** `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL` — **nanoPyCodeAgent already supports all three** (`settings.py`), so that part comes for free. Harbor additionally sets aliases such as `ANTHROPIC_DEFAULT_SONNET_MODEL` for compatible backends.
6. **Wall-clock timeouts are the harness's job.** A task's `task.toml` carries `[agent].timeout_sec`, `[verifier].timeout_sec`, and `[environment].build_timeout_sec` (default 600). The agent's own `--timeout` is a safety net, not a prerequisite for integration.
7. **Installation is cheap.** `ensure_system_dependencies()` installs curl / bash / git / python3 / python3-pip / nodejs / npm / tmux / ripgrep and more on demand, so `install()` only needs `uv tool install nanoPyCodeAgent` or `pip install nanoPyCodeAgent`. Claude Code's own `install()` is little more than an npm-or-curl branch plus a `claude --version` self-check.
8. **Versions are detected.** Implement `get_version_command()` and `parse_version()` and Harbor will record the agent version on a best-effort basis (failures are swallowed). This requires the CLI to have a `--version`.

### 1.4 The trajectory bonus

Harbor has a unified trajectory format, ATIF (`SUPPORTS_ATIF`). mini-swe-agent has its CLI write its own JSON via `--output=<path>` and converts it to ATIF in `populate_context_post_run()`; Claude Code instead parses the `--output-format=stream-json` event stream. Either one lets Harbor collect steps, tokens, and cost — which is exactly the P1 "trajectory logging" and "token accounting" items from `code_agent_benchmark.md`. **Doing those two is not extra work; it also buys the harness-side reporting.**

### 1.5 Task structure (for context)

```
<task-name>/
├── instruction.md            # the task instruction — this is what run() receives
├── task.toml                 # [task] [metadata] [verifier] [agent] [solution] [environment]
├── environment/Dockerfile    # or docker-compose.yaml, or a docker_image reference
├── solution/solve.sh         # the reference solution used by the Oracle agent
└── tests/test.sh             # must write a reward file to /logs/verifier/
```

---

## 2. SWE-bench Verified

Officially there is **no agent interface** — only an output format. In other words, the agent-side runner is yours to write.

### 2.1 The official side is evaluation only

```bash
swebench eval verified -p <path_to_predictions> --run-id <run_id> -j <num_workers>
# The older form still works:
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path <path> --max_workers 8 --run_id my_run
```

Predictions are JSONL, three keys per line:

```json
{"instance_id": "sympy__sympy-20590", "model_name_or_path": "gpt-4", "model_patch": "diff --git a/sympy/core/sympify.py..."}
```

(mini-swe-agent writes a `{instance_id: {...}}` JSON dict instead; the harness accepts both.)

Results are cached by `run_id` + `instance_id`, so re-running a modified patch requires a fresh `run_id`.

### 2.2 Runner-side essentials (copy mini-swe-agent)

Sources: `src/minisweagent/run/benchmarks/swebench.py` and `src/minisweagent/config/benchmarks/swebench.yaml` in `SWE-agent/mini-swe-agent`.

- **Image**: `docker.io/swebench/sweb.eval.x86_64.<instance_id>:latest`, where the double underscore `__` inside `instance_id` is replaced with `_1776_` (Docker disallows double underscores) and the whole name is lowercased.
- **Working directory**: `/testbed`.
- **Task text**: `instance["problem_statement"]` from the dataset, handed to the agent verbatim.
- **Budget baseline**: `step_limit: 250`, `cost_limit: 3.` (USD), and a per-command `timeout: 60`.
- **Submitting the patch**: mini-swe uses a sentinel — the system prompt tells the agent to first run `git diff -- <files it changed> > patch.txt`, then submit with a **separate** command, `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt`; the runner takes the stdout after the sentinel as `model_patch`. The prompt also explicitly forbids including test-file creations or edits in the patch.

### 2.3 What this actually requires of nanoPyCodeAgent

Exactly one thing: **be able to run a `problem_statement` headlessly in `/testbed` and then exit.**

Collecting the patch is **better done without the sentinel** — after the agent exits, the runner can just `docker exec … git add -A && git diff --cached`. Zero agent-side changes, and it eliminates the entire failure class of "the model forgot to type the magic command, so the task scores 0". Accordingly, the P2 "patch output mode" item in `code_agent_benchmark.md` can be dropped.

---

## 3. NL2Repo-Bench

The loosest interface requirements of the three, but its runner hard-codes OpenHands into the repository, so integrating means **forking and editing code**, not mounting a plugin.

### 3.1 The actual flow

Source: `openhands/openhands_app.py` in `multimodal-art-projection/NL2RepoBench`.

1. Each task gets a UUID directory, `workspaces/<task_uuid>/workspace/`, into which the requirements document (`start.md`) is copied from `test_files/<project>/`. **The directory is otherwise empty.**
2. `template/config.template.toml` is rendered into a per-task `config.toml`, substituting `{{VOLUMES}}` (mounting the workspace as `/workspace` in the container) and `{{MODULE_CONFIG}}` (model name / api_key / base_url).
3. A container is started from `docker.all-hands.dev/all-hands-ai/openhands:0.56` (runtime `runtime:0.56-nikolaik`) with a hard-coded command:

   ```bash
   python -m openhands.core.main --config-file=/custom/path/config.toml \
     -t 'According to the start.md in the workspace, implement the entire project as per the requirements specified in the document, ensuring that the final product can be directly run in the current directory. ...'
   ```

4. After the container exits, `post_process_task(task_uuid, workspace_path, test_data, logger)` runs pytest against the workspace directory on the host. **The score is the number of passing tests.**

The entry configuration is `config.json` at the repository root: `startPro[].{moduleName, baseUrl, sk, proNameList}` plus a `max_pool_size` controlling concurrency.

### 3.2 The key property

**Scoring looks only at the final contents of the workspace directory and is entirely decoupled from how the agent ran.** So the only requirement on the agent is: **run one prompt headlessly in a given directory and exit when done.**

There are two ways to integrate nanoPyCodeAgent:

- Edit the container-creation block in `openhands/openhands_app.py` (swap the image, swap the `command`, drop the config.toml machinery) — roughly 20 lines; or
- Write a small runner of your own that reuses its `test_files/` (requirements documents plus test data) and `post_processor.py` (pytest scoring).

The latter is cleaner, since the whole OpenHands `config.toml` apparatus is useless to us.

---

## 4. The minimum common contract

| # | Requirement | Terminal-Bench | SWE-bench | NL2Repo |
| --- | --- | :-: | :-: | :-: |
| 1 | One command delivers the task text; exit when done | ✅ | ✅ | ✅ |
| 2 | Work in the **process's current cwd** (no `--workdir` needed) | ✅ `/app` | ✅ `/testbed` | ✅ `/workspace` |
| 3 | No interaction, no questions, no waiting for confirmation | ✅ | ✅ | ✅ |
| 4 | **Exit 0 on any normal end** (including "unsolved") | ✅ enforced | recommended | recommended |
| 5 | All configuration through environment variables | ✅ | ✅ | ✅ |
| 6 | Logs written to `/logs/agent/` | ✅ | — | — |
| 7 | Structured trajectory output | optional, high value | — | — |
| 8 | A `git diff` obtainable at the end | — | ✅ (collected runner-side) | — |

All three delivery mechanisms for the task text must work: a command-line argument (`--task=`), a stdin pipe (`printf … |`), and a file path.

---

## 5. The CLI design for nanoPyCodeAgent

```
nanoPyCodeAgent [-p/--prompt "<task>" | --prompt-file <path> | (stdin)]
                [--max-turns N]
                [--output-format text|stream-json]
                [--trajectory <path>]
                [--version]
```

**Headless detection**: `-p` / `--prompt-file` means headless; otherwise, if `sys.stdin.isatty()` is False, read all of stdin as the task. That covers both `nanoPyCodeAgent -p "..."` and `printf "%s" "$TASK" | nanoPyCodeAgent`, and it incidentally fixes today's behaviour where stdin is EOF inside a container so the program immediately prints `Bye!` and exits.

**Exit code contract** (the easiest thing to get wrong):

| Exit code | Situation |
| :-: | --- |
| 0 | The model declared completion; the turn limit was reached; the wall clock expired and the agent wound down — **an unsolved task is still 0** |
| non-zero | No API credentials, bad arguments, or API failures severe enough to make progress impossible |

The test is "**did the task fail, or did the harness fail?**" The former is 0, leaving the verifier to decide the reward; the latter is non-zero, letting Harbor classify and retry.

**Output contract**: print API errors verbatim (Harbor identifies them by regex), have `--output-format stream-json` emit per-event JSON for the harness to parse, and have `--trajectory` write JSONL for post-hoc attribution.

---

## 6. Corrections to the conclusions in `code_agent_benchmark.md`

| Original conclusion | Correction |
| --- | --- |
| P0 "exit non-zero on turn-limit overrun, timeout, or repeated API failures" | Turn-limit overrun and timeout **must exit 0**; non-zero is reserved for missing credentials / bad arguments / persistent API failure |
| P0 "a configurable working directory" | Downgraded — all three rely on the process cwd, so `--workdir` is a nicety |
| P0 "retries — never crash" | Simplified — basic backoff plus **printing API errors verbatim**; classification and retry belong to `harbor --retry-include` |
| P2 "a patch output mode" | Unnecessary — collecting `git diff` runner-side is simpler and avoids "the model forgot the submit command, so it scores 0" |
| P2 "a Harbor agent adapter; follow the repository's submission instructions" | The interface is confirmed to be `BaseInstalledAgent` (see §1.1); work can start now |
| The ordering of reasons for Terminal-Bench being first priority | The primary reason should be that **the official leaderboard's entries are themselves two-dimensional, harness + model**, not "the shape matches" (see below) |

On that last point, and on the DeepSWE line that read "the official leaderboard requires mini-swe-agent to be listed" — the original wording was wrong. The DeepSWE site says **"All models run on mini-swe-agent for consistency."** That means the leaderboard **pins** the harness variable, so its entries have only one dimension: the model. The consequences:

- A DeepSWE score produced by nanoPyCodeAgent has **no place** on that leaderboard, and cannot be set beside Opus 5's 74.0% — that 74.0% is mini-swe-agent's score.
- What remains possible is a local A/B: run mini-swe-agent and nanoPyCodeAgent on the same model and compare the delta.

The Terminal-Bench leaderboard, by contrast, lists entries such as `Claude Code + Fable 5` and `Terminus 2 + Fable 5` — **the harness is a dimension of the leaderboard**, so nanoPyCodeAgent has a legitimate place on it. That is the strongest reason to rank Terminal-Bench first.

---

## 7. References

- Harbor docs: [Agents](https://www.harborframework.com/docs/agents), [Task Structure](https://www.harborframework.com/docs/tasks), [How to run Terminal-Bench 2.1](https://www.tbench.ai/docs/run-terminal-bench-2-1)
- Harbor source: <https://github.com/harbor-framework/harbor> (`src/harbor/agents/installed/base.py`, `claude_code.py`, `mini_swe_agent.py`)
- mini-swe-agent: <https://github.com/SWE-agent/mini-swe-agent> (`src/minisweagent/run/benchmarks/swebench.py`, `src/minisweagent/config/benchmarks/swebench.yaml`)
- SWE-bench evaluation guide: <https://www.swebench.com/SWE-bench/guides/evaluation/>
- NL2Repo-Bench: <https://github.com/multimodal-art-projection/NL2RepoBench>, paper [arXiv:2512.12730](https://arxiv.org/abs/2512.12730)
- DeepSWE leaderboard: <https://deepswe.datacurve.ai/>
