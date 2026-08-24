# Event Journal 实现协议 v1

> 本文件为**中文源文件**（source of truth）；英文版
> [`../en/event-journal-protocol-v1.md`](../en/event-journal-protocol-v1.md)
> 由其生成。

| 项目 | 值 |
|---|---|
| 状态 | 已实现（Implemented） |
| 协议版本 | v1 |
| `schema_version` | `1` |
| 可见性 | 内部协议；不是公开 Run Output 或 ATIF 接口 |
| 领域术语 | [`CONTEXT.md`](../../../CONTEXT.md) |
| 核心实现 | [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py) |
| 事件生产与文本投影 | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| 行为测试 | [`test_event_journal.py`](../../../tests/test_event_journal.py)、[`test_agent_events.py`](../../../tests/test_agent_events.py)、[`test_agent.py`](../../../tests/test_agent.py) |

## 文档定位

这是一份**已实现协议规范**，不是 RFC。

- RFC 用于实现前或行为变更前的提案、讨论和评审。
- ADR 用于记录难以逆转、反直觉或存在重要取舍的架构决策及其理由。
- 本文固定当前已经落地的 wire contract、事件语义、持久化行为和兼容性边界。

如果后续要改变这些行为，可以先写 RFC 或 ADR；变更被接受并实现后，再更新本文和协议版本。

本文中的“必须”“应当”“可以”分别表示协议要求、推荐行为和允许行为。除非特别说明，字段和校验规则描述的是 `schema_version = 1`。

## 目标与边界

Event Journal 为一次 **Agent Run** 保存可重放的内部运行事实。完整链路是：

```text
Agent core
    ↓ 产生
Native Event {type, payload}
    ├─→ live projector → 现有 stdout 文本 Run Output
    └─→ journal writer → Journal Entry
                           ↓ UTF-8 JSONL，追加写
                       Event Journal
                           ↓ 后续 projector（不属于 v1）
                       ATIF Trajectory / 其他公开表示
```

这里的边界是：

- **Native Event** 是 agent-independent 的运行事实。
- **Journal Entry** 为 Native Event 增加持久化所需的身份、顺序和记录时间。
- **Event Journal** 是单个 Agent Run 的 Journal Entry 追加序列。
- stdout 是同一组 Native Event 的实时文本投影，但不等于 Event Journal。
- ATIF、`stream-json` 和其他公开输出是后续投影，不属于 v1。

Event emitter 必须先把事件追加到 Journal，再交给 live projector。持久化截断只作用于 Journal Entry；projector 收到的是未截断的 Native Event，因此现有 stdout 行为不受 Journal 大小限制影响。

## 编码与基本类型

- 文件使用 UTF-8 JSONL；每个完整行只包含一个 Journal Entry，并以 `\n` 结束。
- writer 使用紧凑 JSON 编码，不要求字段顺序具有语义。
- payload 必须是 JSON object；其递归值只允许 `null`、boolean、有限 number、string、array 和 object。
- `NaN`、正负无穷、Python 对象等非标准 JSON 值必须被拒绝。
- 所有时间戳使用 RFC 3339 UTC 格式，并以 `Z` 结尾，例如 `2026-08-23T08:00:01.420Z`。
- `duration_ms` 是非负 number，单位为毫秒；它来自 monotonic clock 的耗时差，不用于事件排序。

## Journal Entry envelope

每个 JSONL 行的顶层结构如下：

```json
{
  "schema_version": 1,
  "run_id": "run-7d9e81d0-2dbe-4d4c-a473-62582e5dc842",
  "seq": 4,
  "recorded_at": "2026-08-23T08:00:01.420Z",
  "type": "tool.completed",
  "payload": {
    "model_call_id": "model-bb7241c2-348d-4bb6-975a-b33f05ce76b2",
    "tool_call_id": "toolu_01Abc",
    "tool_name": "read",
    "result": "file contents",
    "is_error": false,
    "duration_ms": 3.72,
    "source_timestamp": "2026-08-23T08:00:01.419Z"
  }
}
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `schema_version` | integer | Journal Entry wire schema 版本。v1 固定为 `1`。 |
| `run_id` | non-empty string | Agent Run 的身份；同一文件中的所有 entry 必须相同。 |
| `seq` | positive integer | run 内权威顺序号。writer 从 `1` 开始逐条递增。 |
| `recorded_at` | RFC 3339 UTC string | Journal writer 接受并记录该事实的墙上时间。它不是排序依据。 |
| `type` | string | Native Event 类型。v1 只允许本文事件目录中的类型。 |
| `payload` | object | 对应事件的事实数据。 |
| `truncation` | object，可选 | 仅当持久化时有字符串被截断才出现；详见“截断协议”。 |

`seq` 是 run 内排序的唯一权威。`recorded_at` 可能相同，也可能受墙上时钟调整影响，消费者不得仅按时间戳重排。

## 所有事件共有的来源时间字段

每种 v1 事件的 payload 都包含：

| 字段 | 必需 | 类型 | 含义 |
|---|---:|---|---|
| `source_timestamp` | 是 | RFC 3339 UTC string 或 `null` | Native Event producer 所知道的事实发生时间。nano core 在事件边界采时；adapter 只复制上游 Source Record 的可信时间；无法确定时写 `null`。 |

`source_timestamp` 属于 Native Event，`recorded_at` 属于 Journal Entry。两者表达不同阶段，不得互相替代。

这里的 producer 是产生 Native Event 的组件，不是模型供应商：

| producer 情况 | `source_timestamp` |
|---|---|
| 当前 nano core 直接产生事件 | core 在 user、model、tool 或 run 的对应事件边界读取 UTC。 |
| 未来 adapter 从带可信时间的 Source Record 归一化事件 | 复制上游时间，不改写成 adapter 的接收时间。 |
| 未来 adapter 的 Source Record 没有可信时间 | 写 `null`；Journal writer 的接收时间仍由 `recorded_at` 保存。 |

## 事件目录

v1 支持九种事件：

| 事件 | 语义 |
|---|---|
| `run.started` | Agent Run 已建立，运行参数已经确定。 |
| `user.message` | 本次 Agent Run 的入口用户消息。 |
| `model.started` | 一次模型调用开始。 |
| `model.output_delta` | 模型流式产生一段文本。 |
| `model.completed` | 一次模型调用成功完成，最终消息和 usage 已可用。 |
| `tool.started` | 一个工具调用开始。 |
| `tool.completed` | 一个工具调用以正常结果、工具级错误或异常结束。 |
| `run.completed` | Agent Run 正常结束，包括达到轮次上限。 |
| `run.failed` | Agent Run 因未处理异常失败。 |

### `run.started`

| 字段 | 类型 | 含义 |
|---|---|---|
| `mode` | `"interactive"` 或 `"headless"` | 本次运行模式。 |
| `model` | non-empty string | 请求使用的模型标识。 |
| `max_turns` | positive integer 或 `null` | 最大模型调用轮数；interactive 当前为 `null`。 |
| `producer` | object | 产生 Native Event 的程序身份；必须包含 non-empty string `name` 和 `version`。nano core 写入 `{ "name": "nanoPyCodeAgent", "version": <package version> }`。 |

该事件必须是 nano core 产生的第一个事件。它只说明 Agent Run 已开始，不表示模型请求已经发出。

`producer.version` 来自安装包元数据。hatch-vcs 构建的开发版本通常包含 Git revision；直接从未安装的源码运行、无法读取包元数据时写 `"unknown"`。`producer` 是 run 级溯源信息，不随字符串大小上限截断。

`producer.version` 与 Journal Entry 的 `schema_version` 正交：前者回答“哪个 nanoPyCodeAgent 构建产生了这次运行”，后者回答“reader 应按哪个 wire schema 解析每条记录”。消费者不得用其中一个推断另一个。

### `user.message`

| 字段 | 类型 | 含义 |
|---|---|---|
| `message_id` | non-empty string | nano 为入口用户消息生成的本地身份。 |
| `content` | 任意 JSON value | 本次输入的用户内容。当前 CLI 产生 string；协议允许结构化内容。 |

interactive 模式下，每次用户输入建立一个新的 Agent Run 和 Journal。此前对话仍会作为模型上下文保存在进程内，但不会在新 Journal 中复制成完整请求快照，也没有 v1 session link。

### `model.started`

| 字段 | 类型 | 含义 |
|---|---|---|
| `model_call_id` | non-empty string | nano 为一次模型调用生成的本地关联 ID。 |
| `model` | non-empty string | 本次请求使用的模型标识。 |

一个 Agent Run 可以有多次模型调用；每次都使用新的 `model_call_id`。

### `model.output_delta`

| 字段 | 类型 | 含义 |
|---|---|---|
| `model_call_id` | non-empty string | 关联的模型调用。 |
| `delta` | string | 本次流式回调新增的文本，可为空字符串。 |

该事件只表示文本增量。纯工具调用回复可以没有任何 delta。完整文本仍会出现在随后 `model.completed.content` 的 text block 中；这项有意的重复同时保留实时过程和最终完成态。

### `model.completed`

| 字段 | 类型 | 含义 |
|---|---|---|
| `model_call_id` | non-empty string | 关联的本地模型调用 ID。 |
| `message_id` | non-empty string | 完成消息的稳定身份；优先使用 provider response ID，缺失时回退到 `model_call_id`。 |
| `content` | array | provider-neutral 的完整消息 block；schema 见下文。 |
| `tool_calls` | array | `content` 中全部 `tool_call` block 的有序副本，必须逐项完全相等。 |
| `model` | non-empty string | provider 返回的实际模型；缺失时回退到请求模型。 |
| `stop_reason` | string 或 `null` | provider 的停止原因，例如 `end_turn` 或 `tool_use`。 |
| `usage` | object 或 `null` | 本次模型调用的 token usage；schema 见下文。 |
| `provider_response_id` | non-empty string 或 `null` | provider 原始 response/message ID。 |
| `generation_id` | non-empty string 或 `null` | provider generation ID；当前从 `x-generation-id` response header 读取。 |
| `duration_ms` | non-negative number | 从开始请求到完整消息和响应头可用的耗时。 |

`content` 支持以下 block：

| `type` | 其他字段 | 含义 |
|---|---|---|
| `text` | `text: string` | 完整文本片段。 |
| `tool_call` | `tool_call_id: non-empty string`、`tool_name: non-empty string`、`input: object` | provider-neutral 工具调用。 |
| `extension` | `namespace: non-empty string`、`source_type: string \| null`、`value: JSON value` | 尚未标准化的 provider block。nano 的 Anthropic adapter 使用 `namespace: "anthropic"`。 |

未知 provider block 必须包装成 `extension`，不能静默丢弃，也不能直接发明新的 `content.type`。

当 `usage` 非 `null` 时：

| 字段 | 必需 | 类型 | 含义 |
|---|---:|---|---|
| `input_tokens` | 是 | non-negative integer | provider 报告的输入 token 数。 |
| `output_tokens` | 是 | non-negative integer | provider 报告的输出 token 数。 |
| `cache_read_input_tokens` | 否 | non-negative integer | 从 prompt cache 读取的输入 token 数。 |
| `cache_creation_input_tokens` | 否 | non-negative integer | 写入 prompt cache 的输入 token 数。 |

provider 返回的其他 JSON usage 字段可以原样保留。v1 不根据 usage 或价格目录计算 cost。

### `tool.started`

| 字段 | 必需 | 类型 | 含义 |
|---|---:|---|---|
| `tool_call_id` | 是 | non-empty string | provider 工具调用 ID；与 `model.completed.tool_calls[].tool_call_id` 对应。 |
| `tool_name` | 是 | non-empty string | 工具名称。 |
| `input` | 是 | object | 完整的工具输入。 |
| `model_call_id` | core profile | non-empty string | 产生该工具调用的模型调用。nano core 总是写入；基础 v1 payload validator 为兼容归一化来源允许省略。 |

同一个工具调用会同时出现在 `model.completed.tool_calls` 和工具生命周期事件中：前者保存模型的 action，后者保存实际执行边界。

### `tool.completed`

| 字段 | 必需 | 类型 | 含义 |
|---|---:|---|---|
| `tool_call_id` | 是 | non-empty string | 与对应 `tool.started` 相同。 |
| `tool_name` | 是 | non-empty string | 工具名称。 |
| `result` | 是 | string 或 `null` | 工具返回给模型的文本；执行抛出异常时为 `null`。 |
| `is_error` | 是 | boolean | 结果是否表示错误。工具的预期失败也可产生 string result 并设为 `true`。 |
| `duration_ms` | 是 | non-negative number | 工具执行耗时。 |
| `error` | 条件必需 | object | `result` 为 `null` 时必须存在。nano core 写 `{ "type": ..., "message": ... }`。 |
| `model_call_id` | core profile | non-empty string | 产生该工具调用的模型调用；nano core 总是写入。 |

预期内的工具错误会结束于 `tool.completed`，agent 可以继续把结果交给模型。工具抛出的未处理异常会先产生 `tool.completed`（`result: null`、`is_error: true`），再使 run 产生 `run.failed`。

### `run.completed`

| 字段 | 类型 | 含义 |
|---|---|---|
| `outcome` | `"completed"` 或 `"max_turns_exhausted"` | 正常结束原因。达到轮次上限属于可解释的正常终态，不是异常。 |
| `duration_ms` | non-negative number | 整个 Agent Run 的耗时。 |

当最后一轮模型回复仍请求工具、但 `max_turns` 已耗尽时，core 不执行这些工具，直接记录 `max_turns_exhausted`。

### `run.failed`

| 字段 | 类型 | 含义 |
|---|---|---|
| `error_type` | non-empty string | 未处理异常的 Python 类型名。 |
| `message` | string | 异常消息，可以为空。 |
| `duration_ms` | non-negative number | 从 run 开始到失败的耗时。 |

`run.failed` 记录后，原异常继续向调用方传播。CLI 参数错误、设置加载失败和缺少 API credential 发生在 Agent Run 建立之前，因此没有 Journal，也不会产生 `run.failed`。

## nano core 事件顺序

core 当前保证以下典型序列：

```text
# 无工具的成功运行
run.started
user.message
model.started
model.output_delta *
model.completed
run.completed(outcome = completed)

# 含工具的成功运行
run.started
user.message
model.started
model.output_delta *
model.completed(stop_reason = tool_use)
(tool.started → tool.completed) *
model.started
...
run.completed(outcome = completed)

# 模型或运行时异常
run.started
user.message
...
run.failed
```

其中 `*` 表示零次或多次。一个 run 必须以且只以 `run.completed` 或 `run.failed` 结束；失败的模型调用不会产生 `model.completed`。

这些是 nano core producer 的状态机保证。v1 `replay()` 当前只校验每条 entry 的 schema、单一 `run_id` 和严格递增的 `seq`，不执行跨事件状态机校验。消费者不能把“文件可 replay”误解为“生命周期一定完整”；进程被强制终止时可能没有终态事件。

## 身份与关联规则

- `run_id` 当前格式为 `run-<UUID>`，并决定文件名。
- `message_id` 标识完整用户或模型消息。
- `model_call_id` 关联 `model.started`、其所有 delta、`model.completed` 和由该回复触发的工具事件。
- `tool_call_id` 关联模型 action、`tool.started` 和 `tool.completed`。
- 所有本地 ID 只要求在相应作用域内稳定且非空；消费者不应解析 UUID 格式获取语义。

## 截断协议

Journal 可能包含超大模型文本、工具输入和工具结果。writer 对 payload 中的每个 string 独立执行字符数上限，默认 `100000` 个 Unicode code point：

- 只在持久化副本中保留字符串前缀。
- 原始 Native Event 及 live stdout projector 不截断。
- 被截断的 Journal Entry 增加顶层 `truncation`：

```json
{
  "fields": [
    {
      "path": "/result",
      "original_chars": 150000,
      "retained_chars": 100000
    }
  ]
}
```

`path` 是以 `payload` 为根的 JSON Pointer。数组索引按十进制表示，object key 中的 `~` 和 `/` 分别转义为 `~0` 和 `~1`。`original_chars` 和 `retained_chars` 按 Python Unicode 字符数计，不是 UTF-8 byte 数。

以下身份、分类和时间元数据字段不截断，以保持关联和 schema 有效：

```text
error_type, generation_id, message_id, mode, model, model_call_id,
outcome, producer, provider_response_id, source_timestamp, stop_reason,
tool_call_id, tool_name
```

截断表示 Journal 已丢失该字段的尾部，消费者不得把保留前缀当作完整值。

## 存储与追加语义

默认位置：

```text
~/.nanoPyCodeAgent/journals/<run_id>.jsonl
```

协议和实现约束如下：

- 一个 Agent Run 对应一个文件。
- `run_id` 必须匹配 `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`，防止目录逃逸。
- writer 以 create-exclusive、append-only 方式打开文件；已有同名文件时失败，不覆盖。
- 支持的平台上同时使用 close-on-exec 和 no-follow 标志。
- 配置根目录和 Journal 目录权限设为 `0700`，文件权限设为 `0600`。
- 同一个 `EventJournal` 实例内的 append 和 close 由 lock 串行化。
- 每条记录通过 write loop 写完；只有完整写入后才递增下一个 `seq`。
- 正常 close 会先 `fsync` 再关闭 descriptor。

v1 不提供自动轮转、保留期限、加密、压缩、跨进程 writer 协调或 Journal 管理 CLI。

## Replay 行为

`EventJournal.replay(path)` 按文件顺序返回 Journal Entry，并执行：

- 每个换行结束的记录必须是合法 UTF-8 JSON object。
- `schema_version` 必须为 reader 支持的 `1`。
- entry envelope 和 Native Event payload 必须通过 v1 校验。
- 所有完整 entry 的 `run_id` 必须相同。
- `seq` 必须为正整数且严格递增；reader 容许 gap，但 writer 正常情况下连续产生 `1, 2, 3, ...`。
- 最后一个没有换行的片段被视为进程在最终 write 中断留下的 partial tail，并被忽略。
- 位于文件中间的损坏行或任何已换行的无效尾行必须报错，不能跳过。

Replay 不修复文件，也不验证事件状态机、摘要、签名或防篡改链。Event Journal 的“可重放”表示可以恢复已完整写入并通过 schema 校验的事实，不表示它是事务数据库或可信审计日志。

## 敏感信息与数据范围

Journal 明确记录：

- 本次用户输入；
- 完整模型输出、流式文本和工具调用；
- 完整工具输入和返回给模型的工具结果；
- provider message/generation ID、stop reason 和 usage；
- 产生本次运行的程序名称和包版本；
- 错误类型、错误消息和各阶段耗时。

因此它可能通过 prompt、模型输出、shell command、文件内容或工具结果间接包含源码、路径、credential 或其他秘密。`0700`/`0600` 只是本机最小访问控制，不等于脱敏、加密或秘密扫描。不得默认上传、公开或作为普通诊断附件分享 Journal。

v1 没有专门记录：

- API key 或 auth header；
- 完整 provider request、HTTP header 或 SDK 原始 response；
- system prompt 和发给模型的完整历史快照；
- spinner、ANSI 颜色、提示符、banner 等 stdout 表现细节；
- token cost 或价格目录解析结果；
- session 身份、跨 run 父子关系；
- ATIF trajectory 或 public `stream-json` 记录。

“没有专门字段”不代表内容中不可能出现同类数据；例如用户把 secret 写进 shell command 时，它仍会随 `tool.started.input` 被记录。

## stdout 与公开接口边界

v1 引入 Event Journal 时，现有 stdout 文本必须保持完全不变。当前 `_TextOutputProjector` 只消费：

- `model.output_delta`：输出 reply prefix 和流式文本；
- `model.completed`：在已经输出文本时补换行；
- `tool.started`：输出工具调用预览；
- `tool.completed`：输出 string result。

Journal file path、run ID、recorded timestamp 和其他 envelope 元数据不写到 stdout。Event Journal 是内部 reconstruction data，不是稳定的用户输出 contract；外部程序不应把 `~/.nanoPyCodeAgent/journals/*.jsonl` 当作公共 CLI API。

## 版本与兼容性

v1 reader 对未知 `schema_version` 和未知事件类型 fail closed。兼容性规则是：

`schema_version` 管理协议兼容性，`run.started.producer.version` 只提供生产者溯源。修复 producer 实现但不改变 wire contract 时，只改变包版本，不提升 schema；改变必需字段、类型或语义时才按以下规则提升 schema。

`producer` 必需字段在 v1 首次合并和发布前完成，因此属于初始 v1 contract，不构成已发布协议的兼容性变更。以下规则适用于 v1 发布后的演进。

- 增加不改变既有含义的可选 payload 字段，可以保持 `schema_version = 1`；旧 reader 会忽略自己不理解的附加语义。
- provider-specific model content 应优先放进 `extension` block，而不是增加新的 block type。
- 增加事件类型、增加必需字段、改变字段类型或语义、改变 envelope 或排序规则，必须提升 `schema_version`。
- 版本升级必须同步更新中英文协议、producer、reader/replay 和 contract tests。
- 未知顶层字段目前可被 reader 忽略，但不保证 deserialize/serialize 后保留；扩展应优先放在有明确所有权的 payload 或 `extension` 中。

Event Journal v1 是内部协议，并不承诺跨 nanoPyCodeAgent 大版本永远兼容。`schema_version` 的目的，是让不兼容变化被明确拒绝，而不是被静默误读。

## 实现位置速查

| 行为 | 位置 |
|---|---|
| 事件类型、payload 校验、content/usage schema | [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py) |
| Journal Entry 编码、截断、权限、append、fsync、replay | [`event_journal.py`](../../../src/nanopycodeagent/event_journal.py) |
| run/user/model/tool 事件发射 | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| Anthropic block 到 provider-neutral content 的归一化 | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| Native Event 到现有 stdout 的文本投影 | [`agent.py`](../../../src/nanopycodeagent/agent.py) |
| envelope、顺序、权限、截断、partial tail 和 schema 测试 | [`test_event_journal.py`](../../../tests/test_event_journal.py) |
| 事件生命周期及精确 stdout 投影回归测试 | [`test_agent_events.py`](../../../tests/test_agent_events.py) |
| 原有 agent loop 与 stdout 行为测试 | [`test_agent.py`](../../../tests/test_agent.py) |
