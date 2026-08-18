# Benchmark 对 Agent Headless 接口的要求

> 本文件为**手写中文源文件**（source of truth）；英文版 [`../en/benchmark_headless_interface.md`](../en/benchmark_headless_interface.md) 由其生成。

调研时间：2026-08-18。

[`code_agent_benchmark.md`](code_agent_benchmark.md) 得出的结论是：先做 headless，再谈跑分。但"做 headless"不是一句话——不同 benchmark 对 agent 的要求差得很远，有的规定了一个 Python 类接口，有的只规定一个 JSON 字段，有的干脆什么都不规定但把 runner 写死在自己的仓库里。本文把三个候选 benchmark 的接入面逐个读到源码级，最后收敛成一份 nanoPyCodeAgent 该实现的最小契约。

结论先放这里：**三者的共同要求只有五条，而其中最反直觉的一条是「跑完没做完也必须 exit 0」。**

---

## 一、Terminal-Bench 2.1 / Harbor

三个里唯一真正**规定了接口**的。而且要注意：你写的不是"一个能被命令行调用的 agent"，而是**一个跑在 Harbor 进程里的 Python 适配类**，它再去容器里安装并调用你的 CLI。

### 1.1 适配类接口

Harbor 分两种 agent。跑在容器里的 CLI 属于后者：

```python
# 外部 agent（agent 进程在容器外）
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
# 安装型 agent（agent 装进容器里跑）—— nanoPyCodeAgent 属于这一类
from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template

class MyInstalledAgent(BaseInstalledAgent):
    async def install(self, environment: BaseEnvironment) -> None:
        await self.exec_as_root(environment, command="...")   # 装系统包
        await self.exec_as_agent(environment, command="...")  # 装用户级工具

    @with_prompt_template
    async def run(self, instruction: str, environment: BaseEnvironment,
                  context: AgentContext) -> None: ...

    def populate_context_post_run(self, context: AgentContext) -> None: ...
```

实际必须实现的只有 `install()` 和 `run()`；`populate_context_post_run()` 用来把轨迹和 token 统计回填给 Harbor，可选但很有价值（见 §1.4）。

运行方式：

```bash
harbor run -d terminal-bench/terminal-bench-2-1 \
           --agent-import-path "path.to.agent:SomeAgent" -k 5
```

（Harbor 文档里另有 `--agent path.to.agent:SomeAgent` 的等价写法。）

### 1.2 instruction 怎么进 CLI：两个官方范例

**Claude Code**（`src/harbor/agents/installed/claude_code.py`）——先经环境变量注入，再从 **stdin 管道**喂进去，避免 shell 转义和命令行长度问题：

```bash
export PATH="$HOME/.local/bin:$PATH"; \
harbor_claude_code_instruction_<uuid>="$HARBOR_CLAUDE_CODE_INSTRUCTION_<UUID>"; \
unset HARBOR_CLAUDE_CODE_INSTRUCTION_<UUID>; \
printf "%s" "$harbor_claude_code_instruction_<uuid>" | \
claude --verbose --output-format=stream-json --print 2>&1 | tee /logs/agent/claude-code.txt
```

**mini-swe-agent**（`src/harbor/agents/installed/mini_swe_agent.py`）——走命令行参数，且**显式把 stdin 接到 `/dev/null`**：

```bash
mini-swe-agent --yolo --model=<model> --task=<shlex.quote(instruction)> \
  --output=<trajectory-path> --exit-immediately 2>&1 </dev/null | tee /logs/agent/mini-swe-agent.txt
```

两种形态 nanoPyCodeAgent 都该兼容：`-p/--prompt` 走参数，非 tty 时整段读 stdin 走管道。注意 `--exit-immediately` 这类"跑完立刻退出、不进 REPL"的语义是必需品，不是可选项。

### 1.3 硬约束清单

以下都是从 Harbor 源码读出来的，文档里没写：

1. **非零退出码 = 整个 trial 判 agent 失败。** `BaseInstalledAgent._exec()` 把命令包成 `set -o pipefail; <cmd>` 执行，返回码非 0 就抛 `NonZeroAgentExitCodeError`。
   → **"轮数用尽但任务没做完"必须 exit 0**，否则会被当成基础设施故障（还可能触发重试，白烧钱）。这一条与直觉相反，也与 `code_agent_benchmark.md` 初版的写法冲突。
2. **Harbor 会正则扫 agent 的 stdout/stderr 来分类错误。** `ERROR_PATTERNS` 覆盖 rate limit、usage limit、500、Overloaded、连接中断、输出 token 超限、上下文超限、未登录、安全拒答、网络错误等，分类出的异常类型可配合重试：源码注释里给的用法是 `harbor run --max-retries 3 --retry-include ApiRateLimitError`。
   → agent 应当把 API 错误**原文打到输出**而不是吞掉；重试逻辑因此可以少写一半，agent 侧只需要基础退避。
3. **不需要 `--workdir`。** `run()` 调 `exec_as_agent` 时不传 `cwd`，容器的默认 WORKDIR 就是任务工作目录。Terminal-Bench 用 `/app`——`claude_code.py` 里硬编码的会话目录 `$CLAUDE_CONFIG_DIR/projects/-app` 就是它的 slug 形式。agent 只要"在当前进程的 cwd 里干活"即可。
4. **日志路径有约定。** agent 自己的日志写 `/logs/agent/`；`/logs/verifier/` 下的 `reward.txt`（单个整数或浮点，通常 1/0）或 `reward.json`（多指标）是**评测脚本**写的，agent 不碰，也不该去读 `/tests/`。
5. **密钥与模型全部走环境变量注入。** `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` / `ANTHROPIC_MODEL`——**这三个 nanoPyCodeAgent 已经支持**（`settings.py`），等于白送。Harbor 还会为兼容基座额外设置 `ANTHROPIC_DEFAULT_SONNET_MODEL` 等别名。
6. **墙钟超时由 harness 侧管。** 任务的 `task.toml` 里有 `[agent].timeout_sec`、`[verifier].timeout_sec`、`[environment].build_timeout_sec`（默认 600）。agent 自己的 `--timeout` 是保险，不是接入的前提。
7. **安装很轻。** `ensure_system_dependencies()` 能按需装 curl / bash / git / python3 / python3-pip / nodejs / npm / tmux / ripgrep 等，所以 `install()` 里写 `uv tool install nanoPyCodeAgent` 或 `pip install nanoPyCodeAgent` 就够。Claude Code 的 `install()` 也不过是 npm/curl 二选一加一行 `claude --version` 自检。
8. **版本可探测。** 实现 `get_version_command()` 与 `parse_version()`，Harbor 会尽力探测并记录 agent 版本（best-effort，失败不报错）。这要求 CLI 有一个 `--version`。

### 1.4 轨迹（trajectory）的额外收益

Harbor 有统一轨迹格式 ATIF（`SUPPORTS_ATIF`）。mini-swe-agent 的做法是让 CLI 用 `--output=<path>` 写自家 JSON，再在 `populate_context_post_run()` 里转成 ATIF；Claude Code 的做法是解析 `--output-format=stream-json` 的事件流。任一种做到了，Harbor 就能采集步数、token、成本，这正好覆盖 `code_agent_benchmark.md` 里 P1 的"trajectory 落盘"和"token 统计"——**这两件事顺手做了不是额外开销，而是把 harness 侧的报表能力一起拿到。**

### 1.5 任务结构（了解即可）

```
<task-name>/
├── instruction.md            # 任务指令，就是 run() 收到的 instruction
├── task.toml                 # [task] [metadata] [verifier] [agent] [solution] [environment]
├── environment/Dockerfile    # 或 docker-compose.yaml，或直接引用 docker_image
├── solution/solve.sh         # Oracle agent 用的参考解
└── tests/test.sh             # 必须往 /logs/verifier/ 写 reward 文件
```

---

## 二、SWE-bench Verified

官方**不规定 agent 接口**，只规定产物格式。换句话说：agent 侧的 runner 要自己写。

### 2.1 官方只管评测

```bash
swebench eval verified -p <path_to_predictions> --run-id <run_id> -j <num_workers>
# 旧式写法仍可用：
python -m swebench.harness.run_evaluation \
    --dataset_name princeton-nlp/SWE-bench_Verified \
    --predictions_path <path> --max_workers 8 --run_id my_run
```

predictions 是 JSONL，每行三个键：

```json
{"instance_id": "sympy__sympy-20590", "model_name_or_path": "gpt-4", "model_patch": "diff --git a/sympy/core/sympify.py..."}
```

（mini-swe-agent 写的是 `{instance_id: {...}}` 的 JSON dict，harness 两种都收。）

结果按 `run_id` + `instance_id` 缓存，改了补丁重跑必须换 `run_id`。

### 2.2 runner 侧要素（照 mini-swe-agent 抄）

来源：`SWE-agent/mini-swe-agent` 的 `src/minisweagent/run/benchmarks/swebench.py` 与 `src/minisweagent/config/benchmarks/swebench.yaml`。

- **镜像**：`docker.io/swebench/sweb.eval.x86_64.<instance_id>:latest`，其中 `instance_id` 里的双下划线 `__` 要替换成 `_1776_`（Docker 不允许双下划线），整体转小写。
- **工作目录**：`/testbed`。
- **任务文本**：数据集里的 `instance["problem_statement"]`，原文交给 agent。
- **预算基准**：`step_limit: 250`、`cost_limit: 3.`（美元）、单条命令 `timeout: 60`。
- **交 patch**：mini-swe 用哨兵——系统提示词要求 agent 先 `git diff -- <改过的文件> > patch.txt`，再用**单独一条**命令 `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && cat patch.txt` 提交，runner 抓哨兵之后的 stdout 当 `model_patch`。提示词里还明确禁止把创建/修改测试文件的改动放进补丁。

### 2.3 对 nanoPyCodeAgent 的实际要求

只有一条：**能在 `/testbed` 里 headless 跑一段 `problem_statement` 然后退出。**

补丁的收集**不建议学哨兵那套**——runner 在 agent 退出后自己 `docker exec … git add -A && git diff --cached` 收就行，agent 侧零改动，也避免了"模型忘了敲那条魔法命令就 0 分"这一整类失败。相应地，`code_agent_benchmark.md` 里 P2 的"patch 输出模式"可以不做。

---

## 三、NL2Repo-Bench

接口要求最松，但它的 runner 把 OpenHands 写死在仓库里，所以接入方式是 **fork 改代码**，不是插件式挂载。

### 3.1 实际流程

来源：`multimodal-art-projection/NL2RepoBench` 的 `openhands/openhands_app.py`。

1. 每个任务分配一个 UUID 目录 `workspaces/<task_uuid>/workspace/`，从 `test_files/<项目名>/` 复制那份需求文档（`start.md`）进去，**目录里除此之外是空的**。
2. 由 `template/config.template.toml` 生成本次任务的 `config.toml`，替换掉 `{{VOLUMES}}`（把 workspace 挂成容器里的 `/workspace`）和 `{{MODULE_CONFIG}}`（模型名 / api_key / base_url）。
3. 起容器 `docker.all-hands.dev/all-hands-ai/openhands:0.56`（runtime 用 `runtime:0.56-nikolaik`），启动命令写死：

   ```bash
   python -m openhands.core.main --config-file=/custom/path/config.toml \
     -t 'According to the start.md in the workspace, implement the entire project as per the requirements specified in the document, ensuring that the final product can be directly run in the current directory. ...'
   ```

4. 容器退出后，宿主机侧 `post_process_task(task_uuid, workspace_path, test_data, logger)` 对 workspace 目录跑 pytest，**分数 = 通过的测试数**。

配置入口是仓库根的 `config.json`：`startPro[].{moduleName, baseUrl, sk, proNameList}` 加一个 `max_pool_size` 控并发。

### 3.2 关键性质

**评分只看 workspace 目录的最终产物，跟 agent 怎么跑完全解耦。** 所以对 agent 的唯一要求是：**在指定目录 headless 跑一句 prompt，跑完退出。**

接入 nanoPyCodeAgent 有两条路：

- 改 `openhands/openhands_app.py` 里创建容器那一段（换镜像、换 `command`、去掉 config.toml 那套），约 20 行；
- 或者干脆自己写一个小 runner，复用它的 `test_files/`（需求文档 + 测试数据）和 `post_processor.py`（pytest 打分）。

后者更干净，因为 OpenHands 的那一整套 `config.toml` 对我们毫无用处。

---

## 四、三者的最小公共契约

| # | 要求 | Terminal-Bench | SWE-bench | NL2Repo |
| --- | --- | :-: | :-: | :-: |
| 1 | 一条命令拿到任务文本，跑完退出 | ✅ | ✅ | ✅ |
| 2 | 在**进程当前 cwd** 里干活（不需要 `--workdir`） | ✅ `/app` | ✅ `/testbed` | ✅ `/workspace` |
| 3 | 不交互、不提问、不等确认 | ✅ | ✅ | ✅ |
| 4 | **正常结束一律 exit 0**（含"没做完"） | ✅ 强制 | 建议 | 建议 |
| 5 | 配置全走环境变量 | ✅ | ✅ | ✅ |
| 6 | 日志写 `/logs/agent/` | ✅ | — | — |
| 7 | 结构化轨迹输出 | 可选，收益高 | — | — |
| 8 | 最终能取到 `git diff` | — | ✅（runner 侧收） | — |

任务文本的三种投递方式都要能吃下：命令行参数（`--task=`）、stdin 管道（`printf … |`）、文件路径。

---

## 五、nanoPyCodeAgent 的 CLI 设计

```
nanoPyCodeAgent [-p/--prompt "任务描述" | --prompt-file <path> | (stdin)]
                [--max-turns N]
                [--output-format text|stream-json]
                [--trajectory <path>]
                [--version]
```

**headless 判定**：给了 `-p` / `--prompt-file` 就是 headless；否则若 `sys.stdin.isatty()` 为 False，就把整段 stdin 读进来当任务。这样同时兼容 `nanoPyCodeAgent -p "..."` 和 `printf "%s" "$TASK" | nanoPyCodeAgent` 两种调用形态，也顺手解决了现在"容器里 stdin 是 EOF 就立刻打印 `Bye!` 退出"的问题。

**退出码约定**（这是最容易做错的地方）：

| 退出码 | 场景 |
| :-: | --- |
| 0 | 模型声明完成；轮数用尽；墙钟超时后自行收尾 —— **任务没做成也是 0** |
| 非 0 | 无 API 凭证、参数错误、API 连续失败到无法继续 |

判据是"**失败的是任务，还是 harness**"：前者归 0，交给 verifier 判 reward；后者归非 0，让 Harbor 去分类和重试。

**输出约定**：把 API 错误原文原样打出来（Harbor 靠正则识别它们），`--output-format stream-json` 输出逐事件 JSON 供 harness 解析，`--trajectory` 落 JSONL 供事后归因。

---

## 六、对 `code_agent_benchmark.md` 结论的修正

| 原结论 | 修正 |
| --- | --- |
| P0"超轮数、超时、API 连续失败 exit 非 0" | 超轮数、超时**必须 exit 0**；非零只留给无凭证 / 参数错误 / API 持续失败 |
| P0"可配置的工作目录" | 降级——三家都靠进程 cwd，`--workdir` 是锦上添花 |
| P0"错误重试，不许崩" | 简化——基础退避 + **把 API 错误原文打到输出**，分类与重试交给 `harbor --retry-include` |
| P2"patch 输出模式" | 不必做——runner 侧 `git diff` 更省事，也避免"忘敲提交命令就 0 分" |
| P2"Harbor agent adapter，接口以仓库提交说明为准" | 接口已确认为 `BaseInstalledAgent`（见 §1.1），可以直接动手 |
| 第一优先 Terminal-Bench 的理由排序 | 首要理由应是"**官方榜条目本身就是 harness + 模型两维**"，而不是"形态匹配"（见下） |

关于最后一条，以及 DeepSWE 那句"官方榜要求 mini-swe-agent 才能上榜"——原措辞不准。DeepSWE 官网原文是 **"All models run on mini-swe-agent for consistency."**，意思是榜单把 harness 这个变量**钉死了**，条目只有"模型"一维。后果是：

- nanoPyCodeAgent 跑出来的 DeepSWE 分数在那个榜上**没有位置**，不能拿去跟 Opus 5 的 74.0% 并列——那 74.0% 是 mini-swe-agent 的分。
- 能做的只有本地 A/B：同一个模型，mini-swe-agent 跑一遍、nanoPyCodeAgent 跑一遍，比差值。

而 Terminal-Bench 官方榜的条目形如 `Claude Code + Fable 5` 与 `Terminus 2 + Fable 5`——**harness 是榜单的一个维度**，nanoPyCodeAgent 因此有一个名正言顺的位置。这才是把 Terminal-Bench 排第一的最硬理由。

---

## 七、参考

- Harbor 文档：[Agents](https://www.harborframework.com/docs/agents)、[Task Structure](https://www.harborframework.com/docs/tasks)、[如何运行 Terminal-Bench 2.1](https://www.tbench.ai/docs/run-terminal-bench-2-1)
- Harbor 源码：<https://github.com/harbor-framework/harbor>（`src/harbor/agents/installed/base.py`、`claude_code.py`、`mini_swe_agent.py`）
- mini-swe-agent：<https://github.com/SWE-agent/mini-swe-agent>（`src/minisweagent/run/benchmarks/swebench.py`、`src/minisweagent/config/benchmarks/swebench.yaml`）
- SWE-bench 评测指南：<https://www.swebench.com/SWE-bench/guides/evaluation/>
- NL2Repo-Bench：<https://github.com/multimodal-art-projection/NL2RepoBench>、论文 [arXiv:2512.12730](https://arxiv.org/abs/2512.12730)
- DeepSWE 榜单：<https://deepswe.datacurve.ai/>
