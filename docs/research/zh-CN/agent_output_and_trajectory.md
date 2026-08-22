# 主流 Code Agent 的输出格式与轨迹设计

> 本文件为**手写中文源文件**（source of truth）；英文版 [`../en/agent_output_and_trajectory.md`](../en/agent_output_and_trajectory.md) 由其生成。

调研时间：2026-08-22。

[`benchmark_headless_interface.md`](benchmark_headless_interface.md) 先提出了下面这组接口，但没有把每个参数的线协议定义完整：

```text
[--output-format text|stream-json]
[--trajectory <path>]
```

本文从 Pi、Claude Code、Codex、OpenCode 和 Grok Build 的当前实现反推这些概念应该怎样拆分。结论先放在最前面：

1. **`--output-format` 选择 stdout 的表示形式，不是文件重定向。** 写文件仍由 Shell 的 `>`，或另一个明确的文件参数负责。
2. **对 nanoPyCodeAgent，`--trajectory PATH` 最自然的语义是“开启 trajectory，并把它写到 PATH”。** 它不改变 stdout，也不改变 `--output-format`。
3. **`stream-json` 应定义为 NDJSON/JSONL 事件流：每行都是一个完整、可独立解析的 JSON 对象。** 它不是“一个 JSON 文档被拆成若干块”，也不天然承诺 token 级增量。
4. **`json` 这个名字在业界没有统一语义。** Claude Code 和 Grok 用它表示“结束时输出一个对象”；Pi、Codex 和 OpenCode 却用它表示 JSONL 事件流。因此接口文档必须写清线协议，不能只列枚举名。
5. **stdout 事件流、持久 session、调试 trace、benchmark trajectory 和 telemetry 是五种不同产物。** 它们可以来自同一个内部事件模型，但不应共用一个含糊的开关。

---

## 一、调研范围与证据等级

调研前先尝试更新 `references/` 下的代码。四个可访问仓库已 fast-forward 到远端最新提交；Claude Code 的第三方镜像远端已经不可访问，未对它做强制替换。

| 项目 | 本地 revision | 更新结果 | 证据等级 |
| --- | --- | --- | --- |
| Grok Build | `19d42e35c07a9c9244f03f6df0c4c353f970d4f9` | 已更新 | xAI 官方开源仓库 |
| Pi | `c49906ec77788625aacbdc53ebca6fbe65bd20f5` | 已更新 | `references/pi` 所跟踪的公开仓库 |
| OpenCode | `e00890c67261a435cee6409366a68999a93393fd` | 已更新 | OpenCode 官方开源仓库 |
| Codex | `4f39251a010a8bd7d692d25fb33832ff06f1635a` | 已更新 | OpenAI 官方开源仓库 |
| Claude Code | `a371abbe75ffa0d0a3c92290e2bbf56a7ef54367` | 远端返回 `Repository not found`，保留快照 | **非官方 sourcemap 镜像，只用于辅助验证实现思路** |

Claude Code 的正式契约以 Anthropic 当前的 [CLI reference](https://code.claude.com/docs/en/cli-usage)、[headless 文档](https://code.claude.com/docs/en/headless)和 [sessions 文档](https://code.claude.com/docs/en/sessions)为准。本地 `references/claude-code/README.md` 自己也明确说明它不是 Anthropic 官方项目，因此本文不会把该快照中的内部字段当作当前稳定 API。

---

## 二、先把五个容易混淆的概念拆开

一个 headless agent 通常同时需要下面五类输出。它们的数据有重叠，但生命周期、受众和兼容性承诺不同。

| 平面 | 主要消费者 | 典型载体 | 主要用途 | 是否要求可恢复会话 |
| --- | --- | --- | --- | :-: |
| CLI presentation | 人或一次性脚本 | stdout 文本 / 单个 JSON | 给出本次运行结果 | 否 |
| Live event protocol | runner、SDK、UI | stdout NDJSON | 实时观察工具调用、消息和用量 | 否 |
| Session store | agent 自己 | JSONL、SQLite、多文件目录 | continue / resume / fork / compaction | 是 |
| Benchmark trajectory | Harbor、离线分析器 | JSONL、ATIF 等 | 统计步数、token、成本和失败归因 | 通常否 |
| Diagnostics / telemetry | 开发者、可观测平台 | stderr、日志、span、trace 文件 | 排障、性能分析、运营监控 | 否 |

这一区分解释了一个看似矛盾的事实：**agent 完全可以一边用 `stream-json` 向 stdout 发实时事件，一边把另一份更完整、可恢复的 session 写进自己的数据目录。** 前者是本次子进程的协议，后者是产品状态。

推荐的内部结构是一个事件源、多个投影器：

```text
                         ┌─ text renderer ───────────────> stdout
agent loop ─> canonical ├─ final JSON reducer ──────────> stdout
              events     ├─ NDJSON event serializer ────> stdout
                         ├─ trajectory writer ───────────> requested file
                         ├─ session recorder ────────────> session store
                         └─ diagnostics / telemetry ─────> stderr / exporter
```

`--output-format` 只选择前三个 stdout 投影器之一；`--trajectory` 控制第四个 sink；未来如果做 resume，再单独设计第五个 session recorder。这样同一个参数就不会同时承担格式、开关和路径三种职责。

---

## 三、五个项目的接口全景

下表按**实际线协议**比较，而不是按各家的命名比较。

| 项目 | 人类可读文本 | 单个汇总 JSON | JSONL 事件流 | partial / delta 能力 | 明确终止事件 | 持久会话 |
| --- | --- | --- | --- | --- | --- | --- |
| Pi | print mode | — | `--mode json` | 有 `message_update` delta | `agent_settled`；`agent_end` 只结束一次 low-level run | 默认 JSONL，支持 continue/resume/fork/`--no-session` |
| Claude Code | `--output-format text` | `--output-format json` | `--output-format stream-json` | 另加 `--include-partial-messages` | `result` | 默认 JSONL，支持 continue/resume/fork/`--no-session-persistence` |
| Codex | `codex exec` 默认 | — | `codex exec --json` | 没有公开 token delta 契约 | `turn.completed` / `turn.failed`；interrupt 是例外 | 默认 rollout JSONL，可 `--ephemeral`，支持 resume/fork |
| OpenCode | `opencode run --format default`，可能有多段已完成 text | `opencode export` 是另一个命令，不是 run 输出模式 | `opencode run --format json` | 否，只发较粗的完成事件 | 无，依赖 EOF + exit code | SQLite + 内部事件表，支持 continue/session/fork |
| Grok Build | `--output-format plain`，边生成边写 text chunk | `--output-format json` | `streaming-json`；另有 Messages 兼容流 | 原生流默认发 text/thought chunk；仅兼容流另加 partial flag，部分 delta 仍是粗粒度 | 原生流成功 `end`、失败 `error`；兼容流 `result` | 默认多文件 JSONL session，支持 continue/resume/fork |

从这张表能看出三个共同模式：

- 给人看的模式倾向于只把最终答案放 stdout，把进度和诊断放 stderr。
- 给程序看的实时模式几乎都采用“一行一个对象”的 JSONL，而不是一个长寿命 JSON array。
- session 通常自动持久化并按 session ID 管理；没有一家把 `--output-format` 当成 session 开关。

同时也有两个不能靠“行业惯例”猜出来的差异：

- `json` 既可能是单个对象，也可能是 JSONL。Claude/Grok 属于前者，Pi/Codex/OpenCode 属于后者。
- “流式”既可能只表示**事件发生时立即发出**，也可能进一步包含不同粒度的 text/thinking/tool-argument delta。Claude 用额外 flag 开启 raw partial；Grok 的原生流默认已有 text/thought chunk，而额外 flag 只改变 Messages 兼容流的 framing。可见“流式”和“token 级”不是同一个承诺。

---

## 四、逐项目设计

### 4.1 Pi：`json` 就是事件流，session 是另一份树形 JSONL

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

Pi 的 session 则是另一份 append-only JSONL。它有 session header，以及带 `id` / `parentId` 的 message、model change、compaction、branch 等 entry，因此历史本质上是一棵树，而不是 stdout 事件的逐字复制。切换分支只是移动当前 leaf，不会删除另一条分支；compaction 会改变送给模型的活动上下文，但不会抹掉原历史。

**可借鉴点：**

- 流里的 delta 与最终 snapshot 分工明确；
- session entry 有持久 ID 和 parent，stdout 临时事件 ID 不承担恢复职责；
- stdout guard 与背压处理适合任何 JSONL CLI；
- 缺点是把 JSONL 模式命名为 `json`，调用方必须读文档才知道不是单个 JSON。

源码入口：[JSON event stream 文档](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md)、[RPC event reference](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md)、[print mode](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/src/modes/print-mode.ts)、[session format](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/session-format.md)。

### 4.2 Claude Code：最清楚地区分 text、json 与 stream-json

Claude Code 的公开定义最适合直接回答本文的命名问题：

| 格式 | 线协议 |
| --- | --- |
| `text` | 完成后输出最终纯文本 |
| `json` | 完成后输出**一个**结果对象，包含 result、session ID、用量/成本等元数据 |
| `stream-json` | 运行期间逐行输出 SDK message/event，即 NDJSON |

`stream-json` 默认意味着“消息或事件一产生就发”，并不自动等于“每个 token 都发”。只有再加 `--include-partial-messages`，才会出现原始 `stream_event`，包含 text、thinking 或 tool-input delta。这个拆分值得保留：很多 benchmark 只需要工具开始/结束、最终消息和用量，没必要承担 token 级事件的体积和兼容性成本。

它还有两个容易与 trajectory 混淆、实际完全不同的概念：

- `--input-format stream-json` 控制 stdin；不会由 output format 隐式推导；
- `--replay-user-messages` 是双工客户端的输入确认回显，不是把旧 session trajectory 重放一遍。

Claude Code 默认把 session 保存为 `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl`。continue、resume 和 fork 操作的是这份持久状态；stdout 的 text/json/stream-json 只影响当前调用怎样向父进程报告。`--no-session-persistence` 也是独立开关。

本地非官方快照显示 transcript entry 带 parent UUID，并会把大 tool result 的完整内容单独落盘、在消息中留下 preview 和路径。这进一步说明 session 是可恢复的有向历史，不是 stdout event log；同时也说明 session 和 stream 都可能包含完整工具参数、结果、hook stdout/stderr，必须按敏感数据处理。

**可借鉴点：**

- 三种输出名与线协议一一对应，歧义最小；
- partial delta 是独立能力，不绑死在 `stream-json` 名字上；
- terminal `result` 汇总状态、最终答案、session ID、turn、usage/cost，消费者不必自己扫描整条流算最终结果；
- session persistence 与 stdout representation 完全正交。

正式契约：[CLI reference](https://code.claude.com/docs/en/cli-usage)、[headless mode](https://code.claude.com/docs/en/headless)、[sessions](https://code.claude.com/docs/en/sessions)、[custom session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)。

### 4.3 Codex：默认文本、`--json` JSONL、rollout 自动持久化

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

普通 session 会自动写到：

```text
$CODEX_HOME/sessions/YYYY/MM/DD/rollout-<timestamp>-<thread-id>.jsonl
```

每行外层带 timestamp、ordinal、type 和 payload，写一行 flush 一次。resume 会继续 append 原 rollout；fork 创建新 thread ID，并把继承历史物化到一份新的 rollout。持久化 policy 会保留可恢复所需的 message、reasoning、tool call/output 等，但过滤许多 transient delta、begin、warning 和 UI event，所以 rollout 也不是 stdout JSONL 的镜像。

Codex 还区分了更深的 opt-in `rollout-trace`：它可能记录 prompt、response、工具 I/O 和终端输出，用于本地排障，不用于 resume，也不是稳定的 CLI trajectory 接口。再往外还有 OpenTelemetry。这三个名字相近，目的完全不同。

**可借鉴点：**

- 默认模式严格执行“stdout 结果、stderr 诊断”；
- `--output-last-message` 展示了“额外 artifact sink”不必改变主输出格式；
- rollout 使用 ordinal、逐行 flush，并能修复缺少结尾换行的 torn tail；
- JSONL 是 SDK 实际消费的公开集成面，但 schema 没有版本号，消费者仍要容忍未知事件、item 类型和新增字段。

源码入口：[exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs)、[stdout contract](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/lib.rs)、[exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs)、[rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs)。

### 4.4 OpenCode：run 的 `json` 是较粗的 JSONL，session 存在 SQLite

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

OpenCode 的持久层与 CLI 流差别更大。session/message/part，以及内部 durable event/projection，主要存在全局 SQLite 数据库；`--continue`、`--session` 和 `--fork` 决定加载或复制哪份 session。`opencode export [sessionID]` 是另一个命令，它把 materialized session snapshot 作为一个 pretty JSON 写到 stdout，用户再自行用 Shell 重定向；它不能当作 `run --format json` 的最终对象模式。

大工具输出会截断 preview，把全文放到 data 目录的 tool-output 文件中。stream、session 和 export 默认都不能被视作已经做过完整 secret redaction；`export --sanitize` 也只是有限清洗。

**可借鉴点：**

- CLI 流可以只投影对集成方有用的语义事件，不必泄露内部所有 event；
- session 存储实现可以是 SQLite，wire protocol 仍然可以是 JSONL；
- 反面经验是：terminal footer 和 schema version 很便宜，却能显著降低 runner 的状态推断成本。

源码入口：[run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts)、[session tables](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/core/src/session/sql.ts)、[export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts)。

### 4.5 Grok Build：最完整的输出矩阵，以及双份 session 日志

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
- **schema 轴：**agent 自己的语义事件，还是某个外部生态的兼容 wire format。

它也展示了兼容层的代价：同一个内部事件要维护两套公开投影，某些内部状态无法无损映射，partial framing、usage、error 和 terminal result 都要各自定义。nanoPyCodeAgent 在有具体消费者之前不需要复制这套复杂度。

Grok 的 session 默认存在 `~/.grok/sessions/<encoded-cwd>/<session-id>/`，其中至少区分：

- `updates.jsonl`：恢复 UI/conversation 的权威 session updates；
- `chat_history.jsonl`：送给模型的历史，不是 session source of truth；
- summary、plan、rewind、signals、feedback、compaction、subagent 等其他状态。

JSONL writer 使用 owner-only 目录、append 和 torn-tail 修复。continue/resume/fork 操作这份 session；output format 仍然只是当前 headless 调用的 stdout 选择。

Grok 的原生 `json` / `streaming-json` 对 usage/cost 还有一个值得借鉴的规则：服务端没有完整上报成本时就省略 cost，或标记 incomplete，而不是把缺失值写成 0。Messages 兼容流受目标 schema 约束，有些未知值仍会回落到 0，并在文档中明确 caveat。对 nanoPyCodeAgent 自己可控的原生 benchmark 协议来说，“未知”与“免费”必须是两个状态。

**可借鉴点：**

- aggregate JSON 和 native event stream 同时存在，各自服务简单脚本与实时 runner；
- 可优雅收尾时有明确的 terminal record：原生成功为 `end`、原生失败为 `error`，兼容流为 `result`；
- 模型输入历史与产品恢复历史分开，避免把“当前上下文”误当成“完整轨迹”；
- compatibility stream 应由真实集成需求驱动，不应一开始就做。

源码入口：[headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md)、[format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs)、[headless writer](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless.rs)、[session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs)。

---

## 五、`stream-json` 到底是什么

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

### 5.1 它与普通 JSON 的区别

| 维度 | `json` | `stream-json` |
| --- | --- | --- |
| 文档边界 | 整个 stdout 是一个 JSON value | 每个非空行是一个 JSON value |
| 首次可解析时间 | 通常等运行结束 | 第一条事件产生时 |
| 内存 | producer/consumer 常需聚合最终结果 | 可以逐行处理，空间可近似常数 |
| 中途状态 | 通常没有 | 可以有 tool、message、usage、error 等事件 |
| 中断后产物 | 整个文档可能无效或根本没写 | 之前的完整行仍可解析，但必须结合 exit code 判断未正常结束 |
| 最适合 | Shell 脚本、CI 读取一次结果 | runner、实时 UI、Harbor adapter、长任务观测 |

它通常也叫 **NDJSON** 或 **JSON Lines / JSONL**。这里推荐 CLI 枚举名用 `stream-json`，文档里明确“wire format is NDJSON”，避免用户把 `jsonl` 误解成只适用于文件。

### 5.2 它不自动承诺什么

`stream-json` 不自动意味着：

- token 级输出；可以只在完整消息或工具阶段发生时发事件；
- 输入也是 JSONL；输入应由独立的 `--input-format` 决定；
- 自动保存到文件；stdout 去哪里由父进程或 Shell 决定；
- 能 resume；恢复需要稳定 session ID、持久 entry ID、上下文重建和兼容策略；
- 是完整审计日志；公开流可以有意省略 prompt、raw provider payload、秘密和超大 tool output；
- 所有行拼起来是合法 JSON array。它们只是合法 JSON values 的序列。

如果以后需要 token 级 delta，建议像 Claude 一样再增加 `--include-partial-messages`；Grok 也说明了 native chunks 与 compatibility framing 是两层不同能力。不要让 `stream-json` 的第一版就背负一个隐含的高频协议。

---

## 六、`--trajectory PATH` 应该是什么语义

五个项目大多没有一个同名 flag，因为它们默认拥有产品级 session store：Pi、Claude、Codex 和 Grok 自动保存 JSONL，OpenCode 自动保存 SQLite。用户通过 session ID continue/resume/fork，而不是每次指定一个 trajectory 文件。

nanoPyCodeAgent 当前还没有这样的 session 系统。在这个前提下，建议：

```text
--trajectory PATH
```

同时表达两件紧密相关、不会互相冲突的事：

1. **presence enables：**出现该参数才开启本次运行的 trajectory artifact；
2. **value chooses destination：**`PATH` 是该 artifact 的文件路径。

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

第二条和第三条产生的 JSONL **不必相同**：公开 stream 追求稳定、小而安全；trajectory 可以有更完整的归因字段和截断元数据。两者应从同一个 canonical event model 投影，避免事实不一致。

路径契约还应明确：

- `PATH` 表示文件而不是目录；
- 默认不覆盖已有文件，避免无声丢失一次昂贵运行；如有需要另加显式 overwrite 语义；
- 文件创建为当前用户可读写，Unix 上目标权限以 `0600` 为准；
- 每条记录写完就 flush，使超时或被 kill 后仍保留完整前缀；
- reader 应容忍 crash 留下的最后一个不完整行，但不能悄悄忽略中间坏行；
- 不建议允许 `--trajectory -`，否则它会与选定的 stdout formatter 争用同一个协议通道。

如果未来改成**默认自动持久化 session**，含义应重新拆分：`--no-session-persistence` 控制是否保存，`--session`/`--resume` 控制身份，只有在确实允许覆盖默认位置时才引入 `--session-path`。不要悄悄把今天的 debug trajectory 升格为明天的 resume 格式。

---

## 七、给 nanoPyCodeAgent 的建议契约

### 7.1 CLI

建议把原来的两档扩成三档：

```text
nanoPyCodeAgent [-p PROMPT | --prompt-file PATH | stdin]
                [--max-turns N]
                [--output-format text|json|stream-json]
                [--trajectory PATH]
```

| 选项 | stdout 契约 | 典型消费者 |
| --- | --- | --- |
| `text`（默认） | 仅最终助手文本；空结果允许空 stdout | 人、最简单的 benchmark runner |
| `json` | run 初始化后恰好一个 result object；preflight 失败可空 stdout；不夹日志 | Shell、CI、一次性脚本 |
| `stream-json` | 每行一个事件；可优雅收尾时以 terminal event 结束，否则 EOF + 非零退出/信号表示 aborted stream | Harbor adapter、SDK、实时 UI |
| `--trajectory PATH` | 不改变 stdout；另写一份增量 JSONL | 离线归因、benchmark 报表、debug |

诊断、重试提示、traceback 和人类进度一律写 stderr。API 错误原文仍可出现在 stderr，满足 Harbor 的错误分类要求；机器模式 stdout 必须始终保持可解析。

### 7.2 单个 `json` 结果对象

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

如果未来增加 `--output-schema PATH`，它应该约束 `result` 的语义内容，而不是改变上述 transport envelope。Codex 和 Grok 都把“模型结构化回答”与“CLI 输出协议”分开，这是正确边界。

### 7.3 `stream-json` 最小事件集

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

### 7.4 trajectory 内容与稳定性

trajectory 的目标是“解释这次运行为什么得到这个结果”，至少应能重建：

- 输入任务与运行配置摘要；
- 每轮模型完成消息或经过安全筛选的响应；
- 工具名、参数、结果、错误与 duration；
- stop reason、turn、usage/cost 及完整性标记；
- compaction/truncation 的发生和被省略内容的大小；
- 最终 status 与 result。

但第一版应明确标记为 **diagnostic/benchmark artifact, not resumable session**。要支持 resume，还需要稳定 parent/entry ID、分支语义、模型/工具配置迁移、compaction 后上下文恢复和长期 schema migration；Pi、Claude、Codex、OpenCode、Grok 的 session 实现都证明这远不只是“读回 JSONL 再继续”。

Harbor 需要 ATIF 时，建议在 adapter 层把 native trajectory 转成 ATIF，而不是让 agent loop 直接依赖 benchmark schema。只有当 Harbor 成为唯一主要消费者时，才值得考虑把 ATIF 直接作为持久格式。

### 7.5 安全与数据量

五个项目的 session/stream 都可能保存或输出 user prompt、reasoning、tool arguments、文件内容、命令输出、环境路径和 provider metadata。部分项目会清洗命令中的可识别 secret 或截断大结果，但没有一个通用保证能把所有秘密洗掉。

因此应把 trajectory 当作敏感文件：

- owner-only 权限；
- 文档明确警告不要上传原始 trajectory；
- API key、Authorization header 和已识别凭证在写入前 redaction；
- 大输出以有界 preview + size/hash/truncated metadata 表达；
- 如果 spill 全文，使用同权限目录并定义保留期；
- 公开 `stream-json` 默认比本地 trajectory 更保守；
- 不要把“缺失/已截断”伪装成空字符串或 0。

---

## 八、最终建议

对本文开头三个问题，最终答案是：

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

这套定义最接近 Claude Code 和 Grok 的清晰命名，同时吸收 Pi 的 delta/final 分工、Codex 的 stdout/stderr 边界和额外 artifact sink、OpenCode 的语义投影，以及各家 session 与公开事件流分离的共同设计。

---

## 九、参考入口

- Pi：[usage](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/usage.md)、[JSON event stream](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/json.md)、[RPC events](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/rpc.md)、[sessions](https://github.com/earendil-works/pi/blob/c49906ec77788625aacbdc53ebca6fbe65bd20f5/packages/coding-agent/docs/sessions.md)
- Claude Code：[CLI reference](https://code.claude.com/docs/en/cli-usage)、[headless mode](https://code.claude.com/docs/en/headless)、[sessions](https://code.claude.com/docs/en/sessions)、[session storage](https://code.claude.com/docs/en/agent-sdk/session-storage)
- Codex：[exec CLI](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/cli.rs)、[exec events](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/exec/src/exec_events.rs)、[rollout recorder](https://github.com/openai/codex/blob/4f39251a010a8bd7d692d25fb33832ff06f1635a/codex-rs/rollout/src/recorder.rs)
- OpenCode：[run command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/run.ts)、[export command](https://github.com/anomalyco/opencode/blob/e00890c67261a435cee6409366a68999a93393fd/packages/opencode/src/cli/cmd/export.ts)
- Grok Build：[headless guide](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md)、[format enum](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-pager/src/headless/cli.rs)、[session export contract](https://github.com/xai-org/grok-build/blob/19d42e35c07a9c9244f03f6df0c4c353f970d4f9/crates/codegen/xai-grok-shell/src/session/export.rs)
