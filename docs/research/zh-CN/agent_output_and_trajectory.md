# 主流 Code Agent 的调用输出、执行跟踪（Trace）、任务轨迹（Trajectory）与会话设计

> 本文件为**中文源文件**（source of truth）；英文版 [`../en/agent_output_and_trajectory.md`](../en/agent_output_and_trajectory.md) 由其生成。

> **后续决策（2026-08-23）：** 本文关于“`--trajectory` 写 native trajectory JSONL，再由 Harbor adapter 转 ATIF”的建议已被 [`agent_events_to_atif_examples.md` 第 7.3 节](agent_events_to_atif_examples.md#73-内部-event-journal-与对外-atif-trajectory-是不同产物) 取代。当前建议是内部保留 append-only Event Journal（可用 JSONL 编码），`--trajectory` 对外只写 ATIF-v1.7；Event Journal 不是另一种 trajectory。本文的 `--output-format` stdout 契约不受影响。

调研时间：2026-08-22。

[`benchmark_headless_interface.md`](benchmark_headless_interface.md) 先提出了下面这组接口，但没有说明两个参数控制的是否是同一种产物：

```text
[--output-format text|stream-json]
[--trajectory <path>]
```

这两个参数表面上都与“输出”有关，实际上属于不同平面。要比较 Pi、Claude Code、Codex、OpenCode 和 Grok Build，必须先回答四个问题：

1. agent 本次调用向人或调用程序交付了什么？
2. agent 内部到底执行了什么？
3. benchmark 要怎样记录 agent 完成任务的路径？
4. agent 下次从哪里恢复上下文？

它们分别对应 **run output、execution trace、trajectory 和 session**。下面先用同一次运行说明四者的区别，再进入各项目实现。

---

## 一、先从一次运行看四种产物

假设用户要求 agent：

```text
修复 parser.py 在工具参数为空时抛出的异常，并运行相关测试。
```

一次典型执行可能是：读取报错位置，搜索调用方，修改代码，运行测试，最后回答用户。本文把从接收这条 prompt 到 agent 停止自动执行称为一次 **run**；一个 run 内可以有多次模型请求和多次工具调用。

### 1.1 Run output：本次调用交付给调用方的公开输出

run output 回答的是：**“这次调用要让外部看见什么？”** 调用方既可以是终端前的人，也可以是 Shell 脚本、benchmark harness、SDK 或 UI。

同一结果可以有不同表示形式。例如 `text` 模式只给出最终回答：

```text
已修复空工具参数的解析，并新增回归测试。相关测试 12 项全部通过。
```

`json` 模式可以在 run 结束时交付一个机器可读的**单个结果对象**。它汇总的是**本次 run 最终怎样结束**，例如最终状态、回答、stop reason、用量和成本；它不汇总完整执行过程，也不是把 trace、trajectory 或 session 全部装进一个 JSON：

```json
{"status":"completed","result":"已修复空工具参数的解析，并新增回归测试。相关测试 12 项全部通过。","usage":{"input_tokens":1200,"output_tokens":180}}
```

`stream-json` 模式则可以在运行期间发布一个稳定的公开事件协议。下面采用 **JSON Lines（JSONL）**：每个非空行都是一个完整 JSON 对象。它也常称 **Newline-Delimited JSON（NDJSON，按换行分隔的 JSON）**；其中 `ND` 就是 `Newline-Delimited`：

```jsonl
{"type":"tool.completed","tool":"pytest","is_error":false,"result":"12 passed"}
{"type":"assistant.message","content":"已修复空工具参数的解析，并新增回归测试。相关测试 12 项全部通过。"}
{"type":"run.completed","status":"completed"}
```

这里先固定四个后文会反复使用的 output 协议术语：

- **单个结果对象（single result object）**：run 结束后只输出一个 JSON 对象，概括本次 run 的最终结果。不同产品包含的字段不同，常见字段有最终回答、completed/failed 状态、stop reason、run/session ID、turn 数、token usage 和 cost；它通常不包含逐步执行记录。
- **公开事件流（public event stream）**：agent 在 run 期间按发生顺序逐条交付给外部调用方的稳定事件协议。它只公开经过筛选、适合长期兼容的事件，例如工具开始/结束、完整助手消息和 run 结束；它不是内部 event bus 或 execution trace 的原样输出。本文讨论的各家 CLI 事件流都使用 JSONL/NDJSON，即一行一个完整事件对象。
- **partial 与 delta**：`partial` 指一条尚未完成的消息、thinking 或 tool arguments 的中间状态；`delta` 指相对于此前内容新增加或改变的那一小段。协议可以反复发送累计的 partial snapshot，也可以只发送 delta，让消费者自行拼接。表格中的“partial / delta 能力”统一询问：**公开事件流是否会在一个逻辑内容尚未完成时，就把它的片段交给调用方。**
- **终止事件（terminal event）**：公开事件流中明确宣告本次 run 以 completed、failed 等状态结束的最后一类事件，例如 `run.completed` 或 `result`。它比 EOF 表达得更多：EOF 只说明 stdout 已关闭，既可能是正常退出，也可能是进程崩溃、被中断或输出被截断。

因此，“有公开事件流”和“有 partial / delta”是两个独立能力。例如只在 pytest 完成后发送 `tool.completed`，再发送完整的 `assistant.message`，仍是实时事件流，但没有 partial / delta；若回答生成过程中先后发送 `assistant.delta: "已修"` 和 `assistant.delta: "复完成"`，才具备内容增量能力。无论是否发送 delta，正常收尾时都还可以用一个终止事件说明整个 run 已结束。

本文后文把 stdout 的编码和记录边界称为**传输格式（wire format）**：stdout 中实际出现的是一段文本、一个 JSON 对象，还是一行一个 JSON 对象，以及记录之间怎样分隔。若讨论范围还包括事件类型、顺序、终止和错误语义，本文称为**输出协议**。

即使公开流里出现了 `tool.completed`，它仍然是 **run output**，因为这是 agent 明确承诺给调用方的公共协议；它不是内部 trace 的原样倾倒。**`--output-format` 只选择这个公开输出怎样编码和分帧。** 它不负责开启 trace、保存 trajectory 或持久化 session。

### 1.2 Execution trace：为排障保留的运行时证据

execution trace 回答的是：**“agent 内部实际发生了什么？”** 它面向 agent 开发者和可观测系统，常见内容包括：

- provider 请求、响应元数据、重试与退避；
- 模型调用、工具调度、子进程、并发任务和耗时；
- 完整或经脱敏的工具输入输出、stderr、异常栈；
- span 之间的父子关系、内部状态转换和性能数据。

一段调试 trace 可能包含下面这样的事实：

```text
inference attempt=1 status=429 retry_after_ms=800
inference attempt=2 request_id=req_2 latency_ms=1430
tool call_id=t1 process_id=4312 stdout_bytes=824 exit_code=0
```

这些信息有助于解释延迟或故障，却不应该因为用户选择了 `--output-format stream-json` 就全部进入 stdout。trace 往往更详细、更敏感，也更贴近当前实现；其 schema 通常不具备 run output 那样的公共兼容承诺。

日志、metrics 和 OpenTelemetry 是诊断信号的记录或传输方式，不是与 trace 并列的另一种“用户输出”。其中 OpenTelemetry trace 本身就是 execution trace 的一种表示。

### 1.3 Trajectory：为任务评测保留的执行路径

trajectory 回答的是：**“agent 通过怎样的观察和动作得到这个任务结果？”** 它通常以一次 benchmark trial 或一次任务 run 为边界，面向评测框架和离线分析器。

同一运行的 trajectory 可以被整理为：

```jsonl
{"step":1,"observation":"parser.py 在 arguments 为空时解引用失败","action":{"tool":"search","query":"parse tool arguments"}}
{"step":2,"observation":"找到两个调用方和一个缺失的空值分支","action":{"tool":"edit","file":"parser.py"},"result":"added empty-argument handling"}
{"step":3,"observation":"代码已修改","action":{"tool":"pytest","target":"tests/test_parser.py"},"result":"12 passed"}
{"outcome":"completed","result":"bug fixed","usage":{"input_tokens":1200,"output_tokens":180}}
```

trajectory 与 trace 都描述执行过程，但取舍不同：

- trace 贴近运行时实现，目标是还原故障现场，可能记录每次重试、内部队列和原始 payload；
- trajectory 贴近任务语义，目标是比较和归因，保留 observation、action、tool result、outcome、token 和 cost 等分析字段；
- trajectory 可以由公开事件流、trace 或 session 转换得到，但转换后的产物才是 trajectory，数据来源本身不会因此改变类别。

trajectory 通常是 run 结束后固定下来的分析产物。它可以支持可视化或离线 replay，但 **replay 不等于 resume**：只有步骤记录，不代表 agent 能恢复当时的产品状态并继续对话。

因此也不能把整份 session export 直接改名为 trajectory：session 可能包含多次 run、旧任务、分支和 compaction 元数据。adapter 必须先切出当前 task/trial 的边界，再整理为 observation/action/outcome。

### 1.4 Session：为继续工作持久化的产品状态

session 回答的是：**“下一次调用要从什么状态继续？”** 它通常比单次 run 活得更久，并支持 continue、resume、fork、rewind 或 compaction。

session 可能保存：

- session ID、工作目录、模型和工具配置；
- 用户消息、助手消息、工具调用及结果；
- 稳定的 entry/message ID 与 parent 关系；
- compaction checkpoint、分支、权限决策和其他恢复所需状态。

例如用户结束进程后又执行：

```text
agent --resume s1 -p "再让它兼容 arguments 缺失的情况"
```

agent 必须从 session `s1` 重建上下文。这是 session 的核心能力，也是它与 trajectory 的判定边界：**能否可靠地 continue/resume/fork，比文件叫 transcript、history、rollout 还是 JSONL 更重要。**

Codex 是最容易因命名产生误解的例子。它把持久会话文件命名为 `rollout-*.jsonl`，但 `resume` 会继续使用它，`fork` 会从它派生新会话，`--ephemeral` 会关闭它。因此本文把 Codex rollout 归入 **session store**。另一个 opt-in 的 `rollout-trace` 才是用于排障的 execution trace；二者不是同一种文件。

---

## 二、用生命周期和用途判断，不要用文件名判断

四个概念的最小边界如下：

| 概念 | 核心问题 | 典型生命周期 | 主要消费者 | 典型内容 | 是否用于 resume | 对应控制面 |
| --- | --- | --- | --- | --- | :-: | --- |
| Run output | 本次调用向外交付什么？ | 一次 run | 人、脚本、runner、SDK、UI | 最终回答、公开事件、状态、usage | 否 | `--output-format` |
| Execution trace | 运行时内部发生了什么？ | 一次 run、进程或 trace tree | 开发者、可观测平台 | 请求/响应、重试、span、内部工具与异常 | 否 | debug / trace / telemetry 配置 |
| Trajectory | agent 怎样完成这个任务？ | 一次 task / trial / run | benchmark、离线分析器 | observation、action、tool result、outcome、cost | 通常否 | `--trajectory` 或 adapter |
| Session | 下次从什么状态继续？ | 跨多次 run | agent 产品自身 | 可恢复 transcript、稳定 ID、分支、compaction、配置 | 是 | session / resume / persistence 配置 |

同一个 session 可以包含多次 run；每次 run 又各自产生自己的 output，并可选地记录 trace 和 trajectory：

```text
session s1
├─ run r1：首次修复任务
│  ├─ output o1 ───────────────> 当前调用方
│  ├─ execution trace t1 ──────> 调试器 / tracing backend
│  └─ trajectory j1 ───────────> benchmark 产物
└─ run r2：resume 后的追加要求
   ├─ output o2
   ├─ execution trace t2
   └─ trajectory j2
```

它们的数据会重叠，但兼容性承诺不同。一个合理实现可以从同一组内部事件投影出四种产物；这里的“投影”是指按各自用途筛选字段并转换结构，而不是复制全部内部事件：

```text
                         ┌─ text renderer ───────────────> stdout
agent loop ─> canonical ├─ final JSON reducer ──────────> stdout
              events     ├─ JSONL event serializer ─────> stdout
                         ├─ trace recorder ──────────────> debug bundle / OTel
                         ├─ trajectory projector ────────> requested artifact
                         └─ session recorder ────────────> session store
```

前三条虽然可能输出不同数量的记录，但都属于 run output。`--output-format` 只能在这三条之间选择；它不能顺便改变 trace、trajectory 或 session 的持久化策略。

---

## 三、调研范围与核心结论

### 3.1 证据范围

调研前先尝试更新 `references/` 下的代码。四个可访问仓库已 fast-forward 到远端最新提交；Claude Code 的第三方镜像远端已经不可访问，未对它做强制替换。

| 项目 | 本地 revision | 更新结果 | 证据等级 |
| --- | --- | --- | --- |
| Grok Build | `19d42e35c07a9c9244f03f6df0c4c353f970d4f9` | 已更新 | xAI 官方开源仓库 |
| Pi | `c49906ec77788625aacbdc53ebca6fbe65bd20f5` | 已更新 | `references/pi` 所跟踪的公开仓库 |
| OpenCode | `e00890c67261a435cee6409366a68999a93393fd` | 已更新 | OpenCode 官方开源仓库 |
| Codex | `4f39251a010a8bd7d692d25fb33832ff06f1635a` | 已更新 | OpenAI 官方开源仓库 |
| Claude Code | `a371abbe75ffa0d0a3c92290e2bbf56a7ef54367` | 远端返回 `Repository not found`，保留快照 | **非官方 sourcemap 镜像，只用于辅助验证实现思路** |

Claude Code 的正式契约以 Anthropic 当前的 [CLI reference](https://code.claude.com/docs/en/cli-usage)、[headless 文档](https://code.claude.com/docs/en/headless)和 [sessions 文档](https://code.claude.com/docs/en/sessions)为准。本地 `references/claude-code/README.md` 自己也明确说明它不是 Anthropic 官方项目，因此本文不会把该快照中的内部字段当作当前稳定 API。

### 3.2 核心结论

1. **`--output-format` 只选择公开 run output 的 stdout 表示形式。** 它不是文件重定向，也不控制 execution trace、trajectory 或 session。
2. **`text`、`json` 和 `stream-json` 描述的是三种 stdout 传输格式。** `text` 是最终文本，`json` 是结束时的单个结果对象，`stream-json` 是运行期间逐行发布的 JSONL/NDJSON 事件。
3. **`--trajectory PATH` 应是独立控制面。** 参数出现时为本次 run 生成一份以当前任务为边界的 trajectory，`PATH` 只指定产物位置，不改变 stdout。
4. **trajectory 不是简化版 session。** trajectory 为评测解释任务路径；session 为产品恢复状态。要做 resume，必须另行设计稳定 ID、分支、compaction 和 schema migration。
5. **五个被调研产品都有 session 实现，但都没有与本文建议完全等价的 benchmark `--trajectory PATH`。** benchmark 可以从公开事件流或 session 派生 trajectory，这不等于两者本来就是同一概念。
6. **`json` 这个名字没有行业统一语义。** Claude Code 和 Grok 用它表示单个结果对象；Pi、Codex 和 OpenCode 用它表示 JSONL 事件流。因此不能只列枚举名，必须说明 stdout 的实际传输格式和输出语义。

---

## 四、五个项目的实现全景

### 4.1 向调用方输出什么：文本、单个结果对象或事件流

先看每个项目提供哪些 **run output 形态**。下表按 stdout 中实际出现的内容比较，而不是按各家的格式名称比较；`—` 表示没有提供这种输出形态。

| 项目 | 给人读的文本 | run 结束后的一个结果 JSON | run 期间的逐行事件（JSONL/NDJSON） |
| --- | --- | --- | --- |
| Pi | print mode | — | `--mode json` |
| Claude Code | `--output-format text` | `--output-format json` | `--output-format stream-json` |
| Codex | `codex exec` 默认 | — | `codex exec --json` |
| OpenCode | `opencode run --format default`，可能有多段已完成 text | —；`opencode export` 是另一个 session 导出命令 | `opencode run --format json` |
| Grok Build | `--output-format plain`，边生成边写 text chunk | `--output-format json` | `streaming-json`；另有 Messages 兼容流 |

再只看第三列的**公开事件流**。下面两个属性描述事件流的内容粒度与结束方式，并不是另外两种 output format。

| 项目 | 是否提前输出尚未完成的内容（partial / delta） | 是否用流内终止事件明确宣告整个 run 结束 |
| --- | --- | --- |
| Pi | 是；`message_update` 提供 delta，`message_end` 提供完整消息 | 是；`agent_settled`。`agent_end` 只结束一次 low-level run |
| Claude Code | 可选；另加 `--include-partial-messages` | 是；`result` |
| Codex | 否；没有公开的 token/text delta 契约 | 是；`turn.completed` / `turn.failed`，但中断是例外 |
| OpenCode | 否；只发较粗的完成事件 | 否；依赖 EOF + exit code |
| Grok Build | 是；原生流默认发 text/thought chunk，Messages 兼容流另有 partial flag | 是；原生流成功为 `end`、失败为 `error`，兼容流为 `result` |

从这两张表能看出三个共同模式：

- 给人看的模式倾向于只把最终答案放 stdout，把进度和诊断放 stderr。
- 给程序看的实时模式几乎都采用“一行一个对象”的 JSONL，而不是一个长寿命 JSON array。
- 没有一家把 `--output-format` 当成 session、trace 或 trajectory 的开关。

同时也有两个不能靠“行业惯例”猜出来的差异：

- `json` 既可能是单个对象，也可能是 JSONL。Claude/Grok 属于前者，Pi/Codex/OpenCode 属于后者。
- “流式”既可能只表示**事件发生时立即发出**，也可能进一步包含不同粒度的 text/thinking/tool-argument delta。Claude 用额外 flag 开启 raw partial；Grok 的原生流默认已有 text/thought chunk，而额外 flag 只改变 Messages 兼容流的 framing。可见“流式”和“token 级”不是同一个承诺。

### 4.2 Execution trace、trajectory 与 session

下表比较另外三个平面。“没有专用 trajectory”表示没有面向 benchmark、以一次 task/run 为边界的稳定产物接口；不表示这些产品的数据不能被 adapter 转换成 trajectory。

| 项目 | Execution trace | 专用 benchmark trajectory | Session：存储与主要内容 |
| --- | --- | --- | --- |
| Pi | 隐藏的 `/debug` 可写 TUI 渲染行和最近发给模型的消息；不是稳定的 headless trace 协议 | 无；可从 JSON 事件流或 session export 派生 | 默认 JSONL；header，message，model/thinking change，compaction，branch/custom entry；`id`/`parentId` 形成树，支持 continue/resume/fork |
| Claude Code | `--debug` / `--debug-file` 记录诊断日志，另支持 telemetry；与 stdout output format 独立 | 无；Harbor 一类 runner 可解析 `stream-json` 后生成 | 默认 transcript JSONL；消息、工具交互及恢复元数据，支持 continue/resume/fork，可关闭 persistence |
| Codex | opt-in `rollout-trace` 本地 bundle：manifest、原始事件、prompt/response、工具与终端 payload，以及离线归约状态；另有 OpenTelemetry | 无；`rollout` 是 session，`rollout-trace` 是 debug trace，都不是 benchmark trajectory 接口 | 默认 `rollout-*.jsonl`；session metadata、model-visible message/reasoning、tool call/output 等可恢复项；支持 resume/fork，`--ephemeral` 关闭 |
| OpenCode | 有运行日志和 debug 子命令；未发现面向用户的完整、稳定 execution-trace 产物 | 无；`export` 导出的是 materialized session snapshot | 全局 SQLite 中的 session/message/part 及 durable event/projection；支持 continue/session/fork，大工具输出可单独落盘 |
| Grok Build | `RUST_LOG` 可把诊断写 stderr，`GROK_LOG_FILE` 可写文件；另有内部日志与 session trace export，均不属于 output format | 无与本文语义等价的 CLI 参数 | session 目录保存权威 updates、模型 chat history、summary/plan/compaction/subagent 等恢复状态；支持 continue/resume/fork |

最值得记住的不是“各家都用了 JSONL”，而是每份数据被谁消费：公开稳定协议是 output，排障证据是 trace，任务评测路径是 trajectory，能恢复和分叉的产品状态是 session。

---

## 五、逐项目设计

### 5.1 Pi：`json` 就是事件流，session 是另一份树形 JSONL

**Run output。**

Pi 的 headless 接口分三种模式：

- print mode：只输出最终助手文本；
- `--mode json`：先输出 session header，再逐行输出 agent/session 事件；
- `--mode rpc`：stdin/stdout 都是 JSONL，既是输入控制协议，也是输出事件协议。

`--mode json` 的第一行类似：

```json
{"type":"session","version":3,"id":"...","timestamp":"...","cwd":"..."}
```

后续可能出现 `agent_start`、turn/message/tool lifecycle、queue update、compaction、auto-retry、`agent_end` 和 `agent_settled` 等事件。其中 `message_update` 只保留 delta，不重复累计中的完整消息；`message_end` 才是权威的最终消息。这是一个很好的流大小控制设计：消费者可以用 delta 做实时 UI，但在结束时用 final snapshot 校准。

这里不能把 `agent_end` 当成整个命令的 terminal event：它只说明一次 low-level agent run 结束，随后仍可能 auto-retry、auto-compact 或处理 queued continuation。`agent_settled` 才表示 Pi 不会再自动继续；进程异常和外部中断仍要结合 EOF 与 exit code 判断。

Pi 还专门接管 stdout：协议写入走受控的 raw stdout，其他普通输出被导向 stderr，并处理写入背压。这说明“机器模式 stdout 不得混入日志”不是文档礼仪，而是实现层的边界。

**Session。**

Pi 的 session 是另一份 append-only JSONL。它有 session header，以及带 `id` / `parentId` 的 message、model change、compaction、branch 等 entry，因此历史本质上是一棵树，而不是 stdout 事件的逐字复制。切换分支只是移动当前 leaf，不会删除另一条分支；compaction 会改变送给模型的活动上下文，但不会抹掉原历史。

**Execution trace。**

Pi 的隐藏 `/debug` 主要写 TUI 渲染行和最近送给模型的消息，不是稳定的 headless trace。

**Trajectory。**

Pi 没有专用 benchmark trajectory；评测方可以从 JSON 事件流或导出的 session 中选择 task steps，再转换成自己的 trajectory schema。

**可借鉴点：**

- 流里的 delta 与最终 snapshot 分工明确；
- session entry 有持久 ID 和 parent，stdout 临时事件 ID 不承担恢复职责；
- stdout guard 与背压处理适合任何 JSONL CLI；
- 缺点是把 JSONL 模式命名为 `json`，调用方必须读文档才知道不是单个 JSON。

源码入口：[JSON event stream 文档](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md)、[RPC event reference](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md)、[print mode](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/src/modes/print-mode.ts)、[session format](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/session-format.md)。

### 5.2 Claude Code：最清楚地区分 text、json 与 stream-json

**Run output。**

Claude Code 的公开定义最适合直接回答本文的命名问题：

| 格式 | stdout 传输格式 |
| --- | --- |
| `text` | 完成后输出最终纯文本 |
| `json` | 完成后输出**一个**结果对象，包含 result、session ID、用量/成本等元数据 |
| `stream-json` | 运行期间逐行输出 SDK message/event，即 NDJSON |

`stream-json` 默认意味着“消息或事件一产生就发”，并不自动等于“每个 token 都发”。只有再加 `--include-partial-messages`，才会出现原始 `stream_event`，包含 text、thinking 或 tool-input delta。这个拆分值得保留：很多 benchmark 只需要工具开始/结束、最终消息和用量，没必要承担 token 级事件的体积和兼容性成本。

它还有两个容易与 trajectory 混淆、实际完全不同的概念：

- `--input-format stream-json` 控制 stdin；不会由 output format 隐式推导；
- `--replay-user-messages` 是双工客户端的输入确认回显，不是把旧 session 的执行历史重放到输出。

**Session。**

Claude Code 默认把 session 保存为 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`。continue、resume 和 fork 操作的是这份持久状态；stdout 的 text/json/stream-json 只影响当前调用怎样向父进程报告。`--no-session-persistence` 也是独立开关。

本地非官方快照显示 transcript entry 带 parent UUID，并会把大 tool result 的完整内容单独落盘、在消息中留下 preview 和路径。这进一步说明 session 是可恢复的有向历史，不是 stdout event log；同时也说明 session 和 stream 都可能包含完整工具参数、结果、hook stdout/stderr，必须按敏感数据处理。

**Execution trace。**

`--debug` / `--debug-file` 记录的是诊断日志，不受 output format 控制。

**Trajectory。**

Claude Code 没有专用 trajectory 路径参数；Harbor 解析 `stream-json` 后生成 benchmark 记录，是“从 run output 投影 trajectory”，不是把 stdout 流重新命名为 trajectory。

**可借鉴点：**

- 三种输出名与 stdout 传输格式一一对应，歧义最小；
- partial delta 是独立能力，不绑死在 `stream-json` 名字上；
- terminal `result` 汇总状态、最终答案、session ID、turn、usage/cost，消费者不必自己扫描整条流算最终结果；
- session persistence 与 stdout representation 完全正交。

正式契约：[CLI reference](https://code.claude.com/docs/en/cli-usage)、[headless mode](https://code.claude.com/docs/en/headless)、[sessions](https://code.claude.com/docs/en/sessions)、[custom session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)。

### 5.3 Codex：默认文本、`--json` JSONL、rollout 自动持久化

**Run output。**

`codex exec` 没有 `--output-format`：

- 默认模式只把最终回答放 stdout，其他进度、工具信息和日志走 stderr；
- `--json` 把 `thread.started`、turn、item 和 error 事件逐行写到 stdout；
- `-o/--output-last-message FILE` 额外保存最后一条助手消息，不替代也不重定向 stdout；
- `--output-schema FILE` 约束模型最终回答的**内容形状**，不改变外层 JSONL 事件协议；
- `--ephemeral` 关闭 session rollout 持久化。

Codex 的公开 JSONL 顶层事件包括：

```text
thread.started
turn.started
item.started / item.updated / item.completed
turn.completed / turn.failed
error
```

item 再用 `type` 区分 agent message、reasoning、command execution、file change、MCP/collab tool、web search、todo 和 error。成功运行通常以 `turn.completed` 收尾，里面带 usage；失败以 `turn.failed` 收尾。当前实现的 interrupted 分支可能没有终止 JSON 事件，因此可靠的 runner 仍应同时检查 EOF、exit code/signal 和 stderr。

**Session。**

普通 session 会自动写到：

```text
$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread-id>.jsonl
```

每行外层带 timestamp、ordinal、type 和 payload，写一行 flush 一次。resume 会继续 append 原 rollout；fork 创建新 thread ID，并把继承历史物化到一份新的 rollout。持久化 policy 会保留可恢复所需的 message、reasoning、tool call/output 等，但过滤许多 transient delta、begin、warning 和 UI event，所以 rollout 也不是 stdout JSONL 的镜像。

**Execution trace。**

Codex 还区分了 opt-in `rollout-trace`。它在本地 bundle 中保存 `manifest.json`、有序原始事件、prompt/response、工具 I/O、终端输出和 payload 引用，并可离线归约成供调试器查看的语义图。它有独立的 `trace_id`，同时引用被观察 session 的 `rollout_id`，正面说明 trace identity 与 session identity 不应混为一谈。

`rollout-trace` 用于本地排障，不用于 resume；OpenTelemetry 又是另一条可观测出口。

**Trajectory。**

Codex 没有专用 benchmark trajectory。session rollout 与 `rollout-trace` 都不是稳定的 benchmark trajectory 接口；评测方需要从公开 JSONL、session rollout 或 trace 中另做投影。

**可借鉴点：**

- 默认模式严格执行“stdout 结果、stderr 诊断”；
- `--output-last-message` 展示了“额外文件出口”不必改变主输出格式；
- rollout 使用 ordinal、逐行 flush，并能修复缺少结尾换行的 torn tail；
- JSONL 是 SDK 实际消费的公开集成面，但 schema 没有版本号，消费者仍要容忍未知事件、item 类型和新增字段。

源码与正式契约：[OpenAI CLI reference](https://developers.openai.com/codex/cli/reference)、[exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs)、[stdout contract](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/lib.rs)、[exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs)、[rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs)、[rollout trace](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout-trace/README.md)。

### 5.4 OpenCode：run 的 `json` 是较粗的 JSONL，session 存在 SQLite

**Run output。**

OpenCode 的命令是：

```text
opencode run --format default|json
```

这里的 `json` 仍然不是一个汇总对象，而是每行一个 `{type, timestamp, sessionID, ...data}` 的事件。当前公开流只投影较粗的语义边界事件：step start/finish、完成的 text、仅在 `--thinking` 下出现的完成 reasoning、完成或失败的 tool use，以及 error。它不发原始 token delta，不含完整用户 prompt，也没有统一的 header、schema version 或 terminal footer。正常完成靠 stdout EOF 加进程退出码识别。

default 格式会把每个已完成的 assistant text part 写到 stdout；一次带工具的 run 可能有工具前后的多段 text，`--thinking` 还会加入 reasoning。因此它是人类可读输出，但不像 Claude/Codex 的 headless text 那样严格承诺“stdout 只有一个最终回答”。

这使它非常轻，但给自动化消费者留下三个成本：

1. 没有终止对象，无法只读最后一行得到 status、result 和 usage；
2. schema 未版本化，且是从内部 session event 临时投影出来的；
3. `--format json` 的名字看不出它是流。

**Session。**

OpenCode 的持久层与 CLI 流差别更大。session/message/part，以及内部 durable event/projection，主要存在全局 SQLite 数据库；`--continue`、`--session` 和 `--fork` 决定加载或复制哪份 session。`opencode export [sessionID]` 是另一个命令，它把 materialized session snapshot 作为一个 pretty JSON 写到 stdout，用户再自行用 Shell 重定向；它不能当作 `run --format json` 的最终对象模式。

大工具输出会截断 preview，把全文放到 data 目录的 tool-output 文件中。stream、session 和 export 默认都不能被视作已经做过完整 secret redaction；`export --sanitize` 也只是有限清洗。

**Execution trace。**

OpenCode 有常规运行日志和一组面向配置、LSP、文件、snapshot 等问题的 debug 子命令，但没有公开的完整 execution-trace 产物。

**Trajectory。**

OpenCode 没有专用 benchmark trajectory。`opencode export` 的对象仍是 session snapshot；只有 adapter 把其中 task steps 转成评测 schema 后，结果才是 trajectory。

**可借鉴点：**

- CLI 流可以只投影对集成方有用的语义事件，不必泄露内部所有 event；
- session 存储实现可以是 SQLite，对外传输格式仍然可以是 JSONL；
- 反面经验是：terminal footer 和 schema version 很便宜，却能显著降低 runner 的状态推断成本。

源码入口：[run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts)、[session tables](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/core/src/session/sql.ts)、[export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts)。

### 5.5 Grok Build：最完整的输出矩阵，以及多层 session 状态

**Run output。**

Grok Build 提供四种 headless 格式：

| 格式 | 语义 |
| --- | --- |
| `plain` | 给人的纯文本；生成中的 text chunk 直接写出，结束时补换行 |
| `json` | 结束时一个汇总对象，含 text、stop reason、session/request ID、turn、usage 和完整时才出现的 cost |
| `streaming-json` | 从 ACP session update 投影出的原生 NDJSON 事件 |
| `streaming-messages-json` | 与 Anthropic Messages 风格兼容的 NDJSON 流 |

原生流有 text、thought、tool call/update、plan、`available_commands`、`auto_compact_*`、max-turns 等类型；成功以 `end` 收尾，失败以 `error` 收尾。它默认就会按 ACP chunk 发 text/thought。兼容流有 init、assistant、user、result 等消息，并且只有这一模式可用 `--include-partial-messages` 打开 Messages stream framing；其中 tool input 等部分 delta 仍可能是一次性粗粒度数据。

这个矩阵展示了两条不同的扩展轴：

- **时间轴：**最终结果对象，还是实时事件流；
- **schema 轴：**agent 自己的语义事件，还是某个外部生态的兼容传输格式（wire format）。

它也展示了兼容层的代价：同一个内部事件要维护两套公开投影，某些内部状态无法无损映射，partial framing、usage、error 和 terminal result 都要各自定义。nanoPyCodeAgent 在有具体消费者之前不需要复制这套复杂度。

**Session。**

Grok 的 session 默认存在 `~/.grok/sessions/<encoded-cwd>/<session-id>/`，其中至少区分：

- `updates.jsonl`：恢复 UI/conversation 的权威 session updates；
- `chat_history.jsonl`：送给模型的历史，不是 session source of truth；
- summary、plan、rewind、signals、feedback、compaction、subagent 等其他状态。

JSONL writer 使用 owner-only 目录、append 和 torn-tail 修复。continue/resume/fork 操作这份 session；output format 仍然只是当前 headless 调用的 stdout 选择。

**Execution trace。**

headless 模式可通过 `RUST_LOG` 把诊断日志写到 stderr，或通过 `GROK_LOG_FILE` 写文件；产品数据目录还包含内部日志和 session trace exports。这些用于排障或 session 分析，不是 output format。

**Trajectory。**

Grok Build 没有形成与本文建议等价的 benchmark `--trajectory PATH`；评测方仍需从公开流、session 或 trace export 中转换。

Grok 的原生 `json` / `streaming-json` 对 usage/cost 还有一个值得借鉴的规则：服务端没有完整上报成本时就省略 cost，或标记 incomplete，而不是把缺失值写成 0。Messages 兼容流受目标 schema 约束，有些未知值仍会回落到 0，并在文档中明确 caveat。对 nanoPyCodeAgent 自己可控的原生 benchmark 协议来说，“未知”与“免费”必须是两个状态。

**可借鉴点：**

- aggregate JSON 和 native event stream 同时存在，各自服务简单脚本与实时 runner；
- 可优雅收尾时有明确的 terminal record：原生成功为 `end`、原生失败为 `error`，兼容流为 `result`；
- 模型输入历史与产品恢复历史分开，避免把“当前上下文”误当成“完整轨迹”；
- compatibility stream 应由真实集成需求驱动，不应一开始就做。

源码入口：[headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md)、[format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs)、[headless writer](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless.rs)、[session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs)。

---

## 六、`stream-json` 到底是什么

建议把 `stream-json` 的正式定义写成：

> **一个以 LF 分隔的、按事件发生顺序增量写入 stdout 的 JSON 对象序列。每个非空行必须是一个完整 JSON 对象；当协议能够优雅收尾时，最后一条记录必须描述运行如何结束。没有 terminal record 的 EOF 表示流被中止、崩溃或截断，消费者必须再检查 exit code/signal。**

例如：

```jsonl
{"schema_version":1,"type":"run.started","run_id":"r1","sequence":0,"timestamp":"2026-08-22T10:00:00.000Z"}
{"schema_version":1,"type":"tool.started","run_id":"r1","sequence":1,"timestamp":"2026-08-22T10:00:01.000Z","tool_call_id":"t1","tool":"bash","arguments":{"command":"pwd"}}
{"schema_version":1,"type":"tool.completed","run_id":"r1","sequence":2,"timestamp":"2026-08-22T10:00:01.050Z","tool_call_id":"t1","is_error":false,"result":"/app"}
{"schema_version":1,"type":"assistant.message","run_id":"r1","sequence":3,"timestamp":"2026-08-22T10:00:02.000Z","message":{"role":"assistant","content":"Done."}}
{"schema_version":1,"type":"run.completed","run_id":"r1","sequence":4,"timestamp":"2026-08-22T10:00:02.010Z","status":"completed","result":"Done.","turns":1,"usage":{"input_tokens":120,"output_tokens":8}}
```

### 6.1 它与普通 JSON 的区别

| 维度 | `json` | `stream-json` |
| --- | --- | --- |
| 文档边界 | 整个 stdout 是一个 JSON value | 每个非空行是一个 JSON value |
| 首次可解析时间 | 通常等运行结束 | 第一条事件产生时 |
| 内存 | producer/consumer 常需聚合最终结果 | 可以逐行处理，空间可近似常数 |
| 中途状态 | 通常没有 | 可以有 tool、message、usage、error 等事件 |
| 中断后产物 | 整个文档可能无效或根本没写 | 之前的完整行仍可解析，但必须结合 exit code 判断未正常结束 |
| 最适合 | Shell 脚本、CI 读取一次结果 | runner、实时 UI、Harbor adapter、长任务观测 |

本文将这种格式称为 **JSON Lines（JSONL）**；它也常称 **Newline-Delimited JSON（NDJSON）**。两个名字都强调记录由换行分隔，并不表示它只能保存在文件里。这里推荐 CLI 枚举名用 `stream-json`，再在文档中明确传输格式是 JSONL/NDJSON。

### 6.2 它不自动承诺什么

`stream-json` 不自动意味着：

- token 级输出；可以只在完整消息或工具阶段发生时发事件；
- 输入也是 JSONL；输入应由独立的 `--input-format` 决定；
- 自动保存到文件；stdout 去哪里由父进程或 Shell 决定；
- 能 resume；恢复需要稳定 session ID、持久 entry ID、上下文重建和兼容策略；
- 是完整审计日志；公开流可以有意省略 prompt、raw provider payload、秘密和超大 tool output；
- 所有行拼起来是合法 JSON array。它们只是合法 JSON values 的序列。

如果以后需要 token 级 delta，建议像 Claude 一样再增加 `--include-partial-messages`；Grok 也说明了 native chunks 与 compatibility framing 是两层不同能力。不要让 `stream-json` 的第一版就背负一个隐含的高频协议。

---

## 七、`--trajectory PATH` 应该是什么语义

五个项目都没有与本文语义完全相同的 `--trajectory PATH`。这不是因为 session 可以替代 trajectory，而是因为这些产品首先解决的是交互式继续工作：Pi、Claude、Codex 和 Grok 会持久化 session 文件或目录，OpenCode 使用 SQLite；用户用 session ID continue/resume/fork。需要 benchmark trajectory 时，集成方通常再从公开事件流或 session 中投影。

nanoPyCodeAgent 当前还没有这样的 session 系统。在这个前提下，建议：

```text
--trajectory PATH
```

同时表达两件紧密相关、不会互相冲突的事：

1. **presence enables：**出现该参数才生成本次运行的 trajectory；
2. **value chooses destination：**`PATH` 是该 trajectory 的文件路径。

它**不应该**：

- 改变 stdout 的目标；
- 隐式把 output format 切成 stream-json；
- 把 stderr 也捕获进去；
- 承诺该文件可直接 resume；
- 同时兼作 session ID 或目录。

因此下面三条命令含义不同：

```bash
# 最终文本到终端，不保存 trajectory
nanoPyCodeAgent -p "fix it" --output-format text

# NDJSON 事件流由 Shell 原样重定向；这仍只是公开 stream
nanoPyCodeAgent -p "fix it" --output-format stream-json > events.jsonl

# 最终文本仍到终端，同时由 agent 独立保存一份 trajectory
nanoPyCodeAgent -p "fix it" --output-format text --trajectory run.jsonl
```

第二条和第三条产生的 JSONL **不必相同**：公开 stream 追求稳定、小而安全；trajectory 可以有更完整的归因字段和截断元数据。两者应从同一组内部标准事件投影，避免事实不一致。

路径契约还应明确：

- `PATH` 表示文件而不是目录；
- 默认不覆盖已有文件，避免无声丢失一次昂贵运行；如有需要另加显式 overwrite 语义；
- 文件创建为当前用户可读写，Unix 上目标权限以 `0600` 为准；
- 每条记录写完就 flush，使超时或被 kill 后仍保留完整前缀；
- reader 应容忍 crash 留下的最后一个不完整行，但不能悄悄忽略中间坏行；
- 不建议允许 `--trajectory -`，否则它会与选定的 stdout formatter 争用同一个协议通道。

如果未来增加**默认自动持久化 session**，含义应继续分开：`--no-session-persistence` 控制是否保存，`--session`/`--resume` 控制身份，只有在确实允许覆盖默认位置时才引入 `--session-path`。不要把今天的 benchmark trajectory 悄悄升格为明天的 resume 格式。execution trace 也应由单独的 debug/trace 配置控制，不能借用 `--trajectory`。

---

## 八、给 nanoPyCodeAgent 的建议契约

### 8.1 CLI

建议把原来的两档扩成三档：

```text
nanoPyCodeAgent [-p PROMPT | --prompt-file PATH | stdin]
                [--max-turns N]
                [--output-format text|json|stream-json]
                [--trajectory PATH]
```

| `--output-format` 值 | stdout 契约 | 典型消费者 |
| --- | --- | --- |
| `text`（默认） | 仅最终助手文本；空结果允许空 stdout | 人、最简单的 benchmark runner |
| `json` | run 初始化后恰好一个 result object；preflight 失败可空 stdout；不夹日志 | Shell、CI、一次性脚本 |
| `stream-json` | 每行一个事件；可优雅收尾时以 terminal event 结束，否则 EOF + 非零退出/信号表示 aborted stream | Harbor adapter、SDK、实时 UI |

`--trajectory PATH` 不属于这张 output-format 表。它保持上述 stdout 契约不变，另外写一份供 benchmark、离线统计和失败归因使用的增量 JSONL。

诊断、重试提示、traceback 和人类进度一律写 stderr。API 错误原文仍可出现在 stderr，满足 Harbor 的错误分类要求；机器模式 stdout 必须始终保持可解析。

### 8.2 单个 `json` 结果对象

建议至少包含：

```json
{
  "schema_version": 1,
  "run_id": "r1",
  "status": "completed",
  "result": "Done.",
  "stop_reason": "end_turn",
  "turns": 3,
  "usage": {
    "input_tokens": 1200,
    "output_tokens": 240
  }
}
```

`status` 应表达 agent 层结果，例如 `completed`、`max_turns`、`timeout`、`failed`。它与进程退出码不是同一个维度：按照 [`benchmark_headless_interface.md`](benchmark_headless_interface.md) 的结论，`max_turns` 这类“trial 正常跑完但任务可能没完成”的状态仍可 exit 0；参数错误、缺凭证或无法继续的 API/基础设施故障才 exit 非 0。

协议从哪里开始也要明确：CLI 参数解析、配置加载或凭证检查等 **preflight** 在 run/writer 初始化前失败时，可以保持 stdout 为空、把诊断写 stderr 并非零退出；一旦已经创建 `run_id` 并发出/准备协议，任何仍可报告的失败都应在 `json` 模式输出唯一的 `status: "failed"` result，在 `stream-json` 模式优雅写出 `run.failed`。进程崩溃或被外部强杀仍可能没有结果对象或 footer。

usage/cost 缺失时应省略或明确标记 `usage_incomplete: true`，不能用 0 代替未知。Grok 的完整性规则在这里比“始终填满一张数字表”更适合 benchmark。

如果未来增加 `--output-schema PATH`，它应该约束 `result` 的语义内容，而不是改变 CLI 结果对象的外层结构。Codex 和 Grok 都把“模型结构化回答”与“CLI 输出协议”分开，这是正确边界。

### 8.3 `stream-json` 最小事件集

第一版不必复制五家全部事件。建议最小集是：

```text
run.started
assistant.message
tool.started
tool.completed
usage
run.completed
run.failed
```

每条公共 envelope 建议都有：

| 字段 | 作用 |
| --- | --- |
| `schema_version` | 明确兼容边界；不要重蹈几个无版本公开流的覆辙 |
| `type` | discriminator，消费者按它宽松分派 |
| `run_id` | 关联同一次进程运行 |
| `sequence` | 单调递增，检测遗漏、排序和截断 |
| `timestamp` | 墙钟归因；耗时计算最好另用 monotonic clock 后填 duration |
| `turn` | 可选，关联模型轮次 |
| `message_id` / `tool_call_id` | 可选，关联 started/completed |

协议规则：

- 未知 type 和新增字段必须可忽略；同一个 major `schema_version` 内只做向后兼容扩展；
- 每个到达语义终态的工具都发 `tool.completed`，无论成功失败，并带 `is_error`；进程中止时允许已发出的 `tool.started` 没有配对终态；
- 能够优雅收尾的正常运行最后一条是 `run.completed`，能够报告的内部失败最后一条是 `run.failed`；
- interrupted、signal、OOM、序列化或写出失败等情况可能没有 footer；收到 terminal event 可确认协议级结束，没有 terminal event 时必须把 EOF 与 exit code/signal 一起解释为 abort/crash/truncation；
- tool output 过大时记录 preview、原始大小、truncated 标志；是否另存全文要有明确路径和清理策略；
- token delta 以后用 `assistant.delta` 或 partial flag 增加，不能让 `assistant.message` 同时表示 delta 和 final snapshot。

### 8.4 trajectory 内容与稳定性

trajectory 的目标是“解释这次运行为什么得到这个结果”，至少应能重建：

- 输入任务与运行配置摘要；
- 每轮模型完成消息或经过安全筛选的响应；
- 工具名、参数、结果、错误与 duration；
- stop reason、turn、usage/cost 及完整性标记；
- compaction/truncation 的发生和被省略内容的大小；
- 最终 status 与 result。

但第一版应明确标记为：**供 benchmark/analysis 使用，不是 execution trace，也不是 resumable session。** 它不需要收集 provider 重试、内部队列和异常栈等全部调试细节；这些属于 execution trace。要支持 resume，还需要稳定 parent/entry ID、分支语义、模型/工具配置迁移、compaction 后上下文恢复和长期 schema migration；Pi、Claude、Codex、OpenCode、Grok 的 session 实现都证明这远不只是“读回 JSONL 再继续”。

Harbor 需要 ATIF 时，建议在 adapter 层把 native trajectory 转成 ATIF，而不是让 agent loop 直接依赖 benchmark schema。只有当 Harbor 成为唯一主要消费者时，才值得考虑把 ATIF 直接作为持久格式。

### 8.5 安全与数据量

五个项目的 trace、trajectory、session 和公开 stream 都可能保存或输出 user prompt、reasoning、tool arguments、文件内容、命令输出、环境路径和 provider metadata。部分项目会清洗命令中的可识别 secret 或截断大结果，但没有一个通用保证能把所有秘密洗掉。

因此应把 trajectory 当作敏感文件：

- owner-only 权限；
- 文档明确警告不要上传原始 trajectory；
- API key、Authorization header 和已识别凭证在写入前 redaction；
- 大输出以有界 preview + size/hash/truncated metadata 表达；
- 如果 spill 全文，使用同权限目录并定义保留期；
- 公开 `stream-json` 默认比本地 trajectory 更保守；
- 不要把“缺失/已截断”伪装成空字符串或 0。

---

## 九、最终建议

对本文开头四个概念，最终边界是：

```text
--output-format text|json|stream-json
```

**指定 stdout 的编码/表示形式。** 它既不接收路径，也不负责文件重定向。

```text
--trajectory PATH
```

**参数出现即开启独立 trajectory writer，PATH 同时指定该 trajectory 文件的位置。** 它不改变 stdout；因为 nanoPyCodeAgent 当前没有默认持久化 trajectory，所以这不是“修改一个已有默认路径”。

```text
json
```

**一旦 run 初始化，结束时输出一个 JSON object；初始化前的 preflight 失败可以空 stdout + 非零退出。**

```text
stream-json
```

**运行期间输出 NDJSON：一行一个完整事件对象；能优雅收尾时最后一行是 terminal result，异常中止时则可能只有一个仍可解析的完整前缀。** 它与 `json` 的差别是“单个最终快照”对“可增量消费的事件序列”，而不是“是否写文件”。

```text
execution trace
```

**由独立的 debug/trace 配置开启，服务排障和可观测性。** 它可以比公开 output 和 trajectory 更详细、更敏感，也不承诺可用于 resume。

```text
session
```

**由独立的 persistence/session/resume 接口管理，服务跨 run 的继续、分叉和压缩。** Codex 的 `rollout-*.jsonl` 属于这一类；文件名中的 rollout 不会把它变成 trajectory。

这套定义最接近 Claude Code 和 Grok 的清晰命名，同时吸收 Pi 的 delta/final 分工、Codex 的 stdout/stderr 边界和额外文件出口、OpenCode 的语义投影，以及各家 session 与公开事件流分离的共同设计。

---

## 十、参考入口

- Pi：[usage](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/usage.md)、[JSON event stream](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md)、[RPC events](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md)、[sessions](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/sessions.md)
- Claude Code：[CLI reference](https://code.claude.com/docs/en/cli-usage)、[headless mode](https://code.claude.com/docs/en/headless)、[sessions](https://code.claude.com/docs/en/sessions)、[session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)
- Codex：[OpenAI CLI reference](https://developers.openai.com/codex/cli/reference)、[exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs)、[exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs)、[rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs)、[rollout trace](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout-trace/README.md)
- OpenCode：[run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts)、[export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts)
- Grok Build：[headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md)、[format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs)、[session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs)
