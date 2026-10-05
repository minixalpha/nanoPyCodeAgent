# CLI 参考

[English](../en/cli_reference.md) | [简体中文](cli_reference.md) |
[用户文档](../README.md)

`nanoPyCodeAgent` 用同一个命令提供交互会话与单次 headless 任务。命令是否收到任务
决定了启动哪一种模式。

## 命令格式

```text
nanoPyCodeAgent [-h] [-p TEXT | --prompt-file PATH] [--max-turns N] [--max-tokens N]
                [--time-budget-seconds N] [--trajectory PATH] [--version]
```

## 模式与任务输入

### 交互模式

没有提供任务选项、并且 stdin 是终端时,命令会启动交互会话:

```bash
nanoPyCodeAgent
```

输入 `/exit`,或在 `You>` 提示符下按 Ctrl-D 或 Ctrl-C,都可以正常结束会话。
`--max-turns` 不限制交互会话中的 exchange。交互模式不能使用 `--trajectory`
或 `--time-budget-seconds`。

### Headless 模式

以下任一种输入方式都会启动一次 headless run:

| 输入方式 | 示例 | 行为 |
| --- | --- | --- |
| `-p TEXT`、`--prompt TEXT` | `nanoPyCodeAgent -p "run the tests"` | 把命令行参数用作任务。 |
| `--prompt-file PATH` | `nanoPyCodeAgent --prompt-file task.md` | 以 UTF-8 读取整个文件;路径中的 `~` 会被展开。 |
| 非终端 stdin | `printf "%s" "$TASK" \| nanoPyCodeAgent` | 没有任务选项时,从 stdin 一直读取到 EOF,并将其用作任务。 |

`-p`/`--prompt` 与 `--prompt-file` 互斥。显式任务选项的优先级高于 stdin。每种方式
读到的任务都会去除首尾空白;空任务或纯空白任务属于用法错误。因此,如果 stdin
被重定向但内容为空(例如来自 `/dev/null`),运行命令不会进入交互会话。

Headless system prompt 要求 agent 自主工作、不请求确认、验证自己的工作,并用一段
简短总结结束 run。

## 当前工作目录

nanoPyCodeAgent 没有用于指定工作目录的选项。进程的当前工作目录就是本次 run 的
workspace,文件工具操作和 shell 命令都在其中执行。请先进入希望 agent 工作的目录:

```bash
cd /path/to/project
nanoPyCodeAgent -p "fix the failing tests"
```

相对形式的 prompt-file 与 trajectory 路径同样以当前工作目录为基准解析。

## 选项

| 选项 | 默认值 | 契约 |
| --- | --- | --- |
| `-h`、`--help` | 无 | 打印帮助并成功退出。 |
| `-p TEXT`、`--prompt TEXT` | 无 | 把 `TEXT` 作为一次 headless 任务运行。 |
| `--prompt-file PATH` | 无 | 从 UTF-8 文件读取一次 headless 任务;文件必须可读并包含非空任务。 |
| `--max-turns N` | `50` | 一次 headless run 最多允许 `N` 轮模型回复;`N` 必须是大于或等于 `1` 的整数。 |
| `--max-tokens N` | `ANTHROPIC_MAX_TOKENS` 或 `32768` | 两种模式下每次模型回复的最大生成 token 数。`N` 必须是正整数；CLI 值优先于环境变量与 settings 文件。 |
| `--time-budget-seconds N` | 禁用 | 将 headless 解题工作限制在 `N` 秒墙钟时间内。`N` 必须是正整数；要求 POSIX 主线程且没有已启用的实时信号定时器。 |
| `--trajectory PATH` | 禁用 | 把 headless run 写成一份 ATIF-v1.7 JSON 文档;参见[Trajectory 输出](#trajectory-输出)。 |
| `--version` | 无 | 打印 `nanoPyCodeAgent VERSION` 并成功退出。 |

`--max-turns` 统计模型回复,只含 tool call 的回复也计入。如果第 `N` 个回复仍然请求
工具,这些工具不会执行,因为已经没有下一轮回复可以使用工具结果。达到上限时,命令
会在 stderr 打印诊断,但仍属于一次正常的 headless 退出。

每次新回复前，模型都会收到剩余回复次数提醒。剩余 10 次回复时（包含即将开始的
这次），提醒要求保存必要产物、执行必要验证并以总结结束。系统提示保持固定，
动态提醒追加到对话尾部。

指定 `--time-budget-seconds` 后，提醒也会报告剩余时间。轮数或时间任一进入保留
窗口就提示收尾；时间窗口取 180 秒与总预算 15% 中的较大值。截止时间会中断正在
进行的模型／工具工作，重试等待也必须落在剩余时间内。被中断的 bash 命令会终止
整个进程组；Linux 下也会终止同一会话内的其他进程。清理时直接关闭输出管道，
不会等待脱离会话的子进程关闭管道，并最多等待一秒回收直接子进程。
终态为 `time_budget_exhausted`，退出码仍为 `0`。随后费用补查有独立、
共享的 30 秒上限，再写出轨迹；无法补齐的费用保持 pending。外部时限需要为这些
收尾工作留出空间。

每次回复还受独立的生成上限约束，默认为 **32768** tokens。可用
`--max-tokens 65536` 覆盖本次调用，或通过环境变量、settings 文件中的
`ANTHROPIC_MAX_TOKENS` 设置持久默认值。所选模型与 provider 必须接受该上限。
它限制整次生成；provider 将 thinking 计入生成预算时，thinking 也占用这一上限，
因此它不保证相同数量的可见回答文本。

如果 provider 返回 `stop_reason="max_tokens"`，agent 会向 stderr 打印截断诊断，
并跳过该回复中的所有工具调用。时间与回合预算尚有剩余时，headless 模式**每次
run 最多自动恢复一次**。后续请求保留可见的部分文本和提示，移除未执行的工具
调用及不完整的 thinking，并要求模型从已确认的工具结果和当前文件继续。token
上限与原始截止时间不变；截断回复与恢复回复都计入回合预算。

第二次截断，或最后一个允许回合发生截断时，终态为 `response_truncated`；截止
时间已到时，终态为 `time_budget_exhausted`。Headless 模式对这些预算终态仍退出
`0`。恢复提示记录为 reason 为 `truncation_recovery` 的 `input.injected` 事件，
每次模型尝试的 stop reason、usage 和费用均保留在 Journal 与 ATIF 中。
交互模式会返回 `You>`，会话历史中保留部分文本和截断提示，用户可以在后续消息
中继续对话。

## 响应中断

两种模式都会对响应体读取错误、读取超时及远端协议错误最多重试两次，分别等待
1 秒和 2 秒。重试使用同一份对话；已完成的工具不会重新执行，未完成的回复和
工具参数不会加入请求历史。失败尝试不消耗 `--max-turns`，但仍可能产生服务商费用。
每次尝试都会保留在 Journal 和轨迹中。

从该轮首次中断起超过 300 秒后，不再安排新的重试。这个窗口不会取消进行中的
请求：SDK 超时和外部执行期限仍然有效。响应流打开前的失败由 SDK 自身的重试
策略处理。这个恢复循环不会重试认证失败、无效请求、程序错误或用户中断。
配置墙钟预算后，正在进行的请求和重试等待也受预算约束。传输重试耗尽时，headless
模式退出码为 `1`；因墙钟预算停止时退出 `0`，并记录独立的预算耗尽终态。

## 输出通道

Headless run 期间,stdout 包含流式模型文本以及回显的工具调用和工具结果。启动 banner、
预算上限诊断和 API 错误写入 stderr。调用方因此可以捕获 run output,同时保留运行
诊断。

`--trajectory` 不会改变 stdout。目前没有 JSON 或 JSONL stdout 模式。

## 退出状态

| 状态 | 含义 |
| --- | --- |
| `0` | help 或 version 输出完成;交互会话正常结束;或者 headless run 已经启动并交回控制权,即使模型放弃、工作未完成或用尽了 `--max-turns`。 |
| `1` | runtime 或基础设施故障阻止了正常运行,包括缺少 API 凭据或 Anthropic/HTTP API 失败。 |
| `2` | 命令行用法无效,包括任务输入冲突或为空、轮数或生成 token 上限无效、prompt file 无法读取,或者 trajectory 目标无效。 |

退出状态 `0` 不证明 headless 任务成功。脚本或 benchmark 必须检查产生的 workspace,
或者运行自己的 verifier。CLI 未处理的意外故障也可能让进程以非零状态和 traceback
结束。

## Trajectory 输出

在 headless 任务中使用 `--trajectory PATH`,可以写出一份完整的
[ATIF-v1.7](https://www.harborframework.com/docs/agents/trajectory-format) JSON
文档:

```bash
nanoPyCodeAgent -p "read README.md and summarize it" \
  --trajectory ./trajectory.json
```

Trajectory 是独立 artifact,不会替代或重定向 stdout。它描述单次 Agent Run 的任务、
模型回复、工具参数、工具结果、时间、用量、可获得的成本信息和终态。如果 run 启动后
发生被捕获的 API 失败,仍会产生带失败终态的 partial trajectory。

启动提示和 Journal 的 `run.started.max_tokens` 记录最终生效的单次生成上限;
ATIF 将它保存在 `agent.extra.max_tokens` 中。这是请求预算,实际消耗仍由 usage
字段记录。旧 Journal 没有预算信息时,转换后的 ATIF 会省略此字段。

路径契约如下:

- `--trajectory` 需要 headless 任务,不能在交互模式中使用。
- `PATH` 必须指向文件;stdout 保留给 run output,因此 `-` 会被拒绝。
- 路径中的 `~` 会被展开,相对路径以当前工作目录为基准。
- 父目录必须已经存在。
- 目标不能已经存在(符号链接也算存在);命令永远不会覆盖它。
- run 到达终态后,文件才会以仅 owner 可读写的权限(`0600`)发布。在 Agent Run
  启动前发生的失败(例如缺少凭据或 CLI 输入无效)不会产生 trajectory。

Trajectory 可能包含 secret 和 repository 内容。请按敏感数据存储和分享。

## 内部 Event Journal

每次 Agent Run 都会自动在 `~/.nanoPyCodeAgent/journals/` 下创建可重放的内部 JSONL
Event Journal。目录权限会被强制设为仅 owner 可访问(`0700`),每个 journal 文件为
`0600`。一次真正启动的 headless 任务包含一个 Agent Run;在交互会话中,每次提交
用户消息都会启动新的 Agent Run,因而也会产生新的 journal。

Journal 是可选 ATIF trajectory 的内部投影来源。它不是公开 run output,不是 ATIF
trajectory,也没有 CLI 选项可以重定向或禁用。Journal 文件目前不会自动轮转。它们
可能包含 prompt、模型回复、工具参数、工具结果和 repository 内容,应按敏感数据处理。

凭据、模型选择和 endpoint 设置请参阅[配置参考](configuration.md)。
