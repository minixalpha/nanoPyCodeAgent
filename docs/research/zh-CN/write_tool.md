# 五个 Agent 项目的写文件工具设计对比

> 本文件为**手写中文源文件**（source of truth）；英文版 [`../en/write_tool.md`](../en/write_tool.md) 由其生成。

## 研究范围

本文调研五个主流 Code Agent 项目的模型可调用写文件工具，重点回答两个问题：

1. 创建、覆盖文件本来用 Bash 就能完成，为什么还要单独设计 `write` 工具？
2. 各项目的 `write`、`edit`、`apply_patch` 等文件变更工具具体实现了什么，为什么实现这些功能？

虽然主题是 `write`，但不能只看“整文件写入”这一支。`write` 通常与 `edit`、`apply_patch` 共同组成文件变更协议：前者表达“最终文件是什么”，后两者表达“相对于当前文件改什么”。因此本文同时考察三类工具，但不把面向 GUI 客户端的普通 `fs/writeFile` RPC 算作模型工具。

结论基于以下源码快照。链接固定到检出提交；其中 `claude-code` 是当前目录所用的第三方源码镜像，不是 Anthropic 官方开源仓库。

| 项目 | 当前提交 | 提交日期 |
| --- | --- | --- |
| `grok-build` | [`500129c`](https://github.com/xai-org/grok-build/tree/500129c714ad1b10e6095481f4a8387a2ec52649) | 2026-07-29 |
| `pi` | [`c13ffe1`](https://github.com/earendil-works/pi/tree/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87) | 2026-07-30 |
| `claude-code` | [`a371abb`](https://github.com/yasasbanukaofficial/claude-code/tree/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367) | 2026-04-05 |
| `opencode` | [`8c38d26`](https://github.com/anomalyco/opencode/tree/8c38d260eb6555d2824230be100fb2a7eadd7513) | 2026-07-30 |
| `codex` | [`578c1b2`](https://github.com/openai/codex/tree/578c1b2230288104041e880a86d0f7f3a5ca6e47) | 2026-07-30 |

## 结论

用户的直觉是对的：**把一串字节创建或覆盖到文件里并不复杂，Bash 完全能做。** 独立 `write` 工具通常没有增加文件系统层面的新能力；它增加的是一层**结构化的变更协议和控制面**。

两条路径的差别大致是：

```text
Write / Edit / Patch
  → 结构化意图
  → schema 校验
  → 路径解析与权限
  → 冲突检查与并发协调
  → 文件系统变更
  → diff、历史、事件、LSP、UI

Bash
  → 任意命令字符串
  → shell 展开、管道、重定向、子进程
  → 任意副作用
```

Bash 可以手工复现上面的任何一步，但 Agent 框架看到任意 shell 程序时，很难在执行前可靠回答：

- 最终会改哪个文件，符号链接解析后又是哪一个文件；
- 这是创建、覆盖、局部替换、移动还是删除；
- 用户批准时文件会变成什么样；
- 文件在模型读取后是否被用户、formatter 或另一个工具改过；
- 应该把哪个 diff、诊断、历史快照和审计事件交给 UI；
- 同一轮并行调用是否正在写同一个真实文件；
- 相同语义如何移植到 Windows、SSH、VM 或虚拟文件系统。

所以更准确的概括是：

> Bash 解决“能不能写”；专用文件工具解决“模型以什么语义写、谁批准、如何防止错写，以及系统如何知道写了什么”。

但反过来也必须强调：**专用 `write` 工具本身不是安全边界。** 如果 Agent 同时拥有不受约束的 Bash，那么只在 `write`/`edit` 上做路径保护仍可被 `printf > file`、Python 或 `sed -i` 绕过。真正的安全边界必须覆盖所有写入通道，例如禁用 Bash、把 Bash 也放入同一文件系统沙箱，或在 OS、容器、VM 层隔离整个进程。

## 总览

| 项目 | 模型侧文件变更接口 | 整文件写入的设计取向 | 关键特征 |
| --- | --- | --- | --- |
| Grok Build | 按 preset 暴露 `write`、`search_replace`、`apply_patch` 或 Hashline `edit_file` | 工具本体较薄，重能力放在会话编排层和相邻编辑协议 | 路径权限、plan gate、hook、同参数路径字符串的批次锁、变更事件、hunk/rewind；`search_replace` 和 Hashline 提供更强前置条件 |
| Pi | 默认同时启用 `read`、`bash`、`edit`、`write` | 轻量、可嵌入、可替换后端 | 自动建目录、路径容错、同真实文件串行队列、Abort、TUI 预览、扩展 hook、SSH/VM/`ExecutionEnv` |
| Claude Code | `Write`、`Edit`，另有 `NotebookEdit` | 最重的“受管整文件替换” | 强制先完整 Read、mtime/内容防陈旧、路径与 symlink 权限、历史备份、尽力原子替换、权限位保留、diff、LSP、编辑器通知 |
| OpenCode | V1/V2 都有 `write`、`edit`、`apply_patch` | 同仓库两代实现；V1 集成厚，V2 mutation core 更严格 | Location 边界、canonical path、细粒度权限、BOM/换行处理；V2 edit 有字节 CAS，V1 有 formatter、事件、LSP 和 fuzzy edit |
| Codex | **没有独立 whole-file `Write`**；使用自由格式语法的 `apply_patch` | 认为结构化 Patch 足以覆盖创建和修改，普通命令仍由 `exec_command` 承担 | Add/Delete/Update/Move、多文件 patch、上下文校验、审批与沙箱、远端 FS、结构化 diff/event；不是多文件事务 |

这五个项目实际上给出了三种不同答案：

1. **重型专用工具**：Claude Code 把读取状态、权限、历史、落盘和 IDE 集成都收进 `Write` 生命周期。
2. **轻型结构化接口**：Pi 和 Grok 的 whole-file `write` 本体很简单，价值主要来自 schema、hook、UI、队列、事件和可替换后端。
3. **不要 whole-file Write**：Codex 只提供 `apply_patch`；创建文件就是 `Add File` patch，完整重写也可以用 patch 表达。

## 为什么专门做一个写工具

### 1. 把文件内容当数据，而不是 shell 程序的一部分

`write({ path, content })` 仍然需要正确生成 JSON，但 `content` 不会再经过 shell 的变量展开、命令替换、glob、heredoc 或重定向语法。

用 Bash 写一个包含反引号、`$()`、引号、任意 heredoc delimiter 或二进制 NUL 的文件，需要模型同时正确处理“内容语言”和“命令语言”。专用工具把两者分开，非法 JSON 还能在执行前作为 schema 错误返回模型修正。

这也是跨平台问题：统一文件 API 不依赖目标机恰好安装了 Bash、`sed` 或 `perl`，也不必让模型分别掌握 POSIX shell、PowerShell 和 `cmd.exe` 的 quoting。

### 2. 把“写哪里”变成可授权资源

对结构化调用，框架在执行前就拿到了目标路径，可以：

- 规范化相对路径、`..` 和 home；
- 解析现存目标及父目录的真实路径；
- 检查符号链接是否逃逸工作区；
- 分别授权工作区内文件和显式外部绝对路径；
- 在 plan 模式拒绝所有 mutation；
- 给 UI 展示“将修改哪个文件”。

对任意 Bash，静态分析 `command` 通常只能可靠覆盖简单的 `>`/`>>` 等形状。变量、函数、`eval`、子进程、解释器脚本、动态文件名和 symlink 会让“执行前精确推导写集合”变得不可靠。

不过这只是让策略点更明确，并不自动产生安全性。Pi 的安全文档明确说明工具继承运行进程的权限、没有内置 sandbox；它的路径保护扩展示例只拦 `write`/`edit`，如果 Bash 仍启用就可绕过。[Pi 默认工具](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/agent-session.ts#L2556-L2595)与[安全边界说明](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/docs/security.md#L31-L53)把这一点表现得很清楚。

### 3. 把“我基于哪个旧版本修改”变成前置条件

Agent 最危险的写错误之一不是语法错，而是 silent clobber：

1. 模型读了旧内容；
2. 用户、formatter 或并行工具改了文件；
3. 模型根据旧内容整文件覆盖；
4. 中间更新无声丢失。

专用协议可以选择不同强度的保护：

- Claude Code 强制现存文件先被完整读取，并比较读取后的 mtime；真正写入前又同步重读，必要时回退到内容比较。
- OpenCode V2 的 `edit` 在权限批准后读取原始 bytes，提交时在同一 canonical-path 锁内执行 `writeIfUnchanged(expectedBytes)`。
- Edit/SearchReplace/Patch 要求旧文本或上下文仍能匹配；部分 Edit/SearchReplace 还要求唯一匹配，匹配失败就拒绝。
- Pi 用同一真实路径的 mutation queue 串行化本进程内的 `write`/`edit`。

这些机制强弱不同，也都不等于跨进程、内核级原子 compare-and-swap。外部程序仍可能在“检查”和“写入”之间竞争；普通跨进程文件锁通常只能协调参与同一锁协议的写者。若要获得更强保证，需要强制 revision/CAS、事务后端或完整隔离，而不是把 advisory lock 当成所有进程都必须遵守的边界。

### 4. 在并行 Agent 中协调同文件变更

现代 Agent 常在同一轮并发执行多个 tool call。若两个 edit 都执行“读旧文件 → 计算新内容 → 写回”，后完成者会覆盖前者。

专用文件工具可以按 canonical path 或 `realpath` 建队列：

- 同一个真实文件串行；
- 不同文件继续并行；
- symlink 别名尽量归并到同一个队列；
- 锁覆盖完整的 read-compute-write，而不只是最后一次 `write()`；
- Abort 时等底层 I/O settled 后再释放锁，避免取消调用与后续写交错。

Pi 的实现和文档直接把该队列解释为避免 lost update 的机制：[mutation queue](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/file-mutation-queue.ts#L1-L60)、[扩展说明](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/docs/extensions.md#L1865-L1873)。

Bash 写入和外部编辑器不会自动参加这种进程内队列。要让 Bash 获得同样保证，必须把所有文件 I/O 代理到同一个 mutation service，或者依赖外层工作区隔离。

### 5. 在用户批准前生成可审阅信息

一个结构化 edit/patch 可以在落盘前计算：

- create、update、delete、move 的操作类型；
- unified diff；
- additions/deletions；
- 匹配次数和模糊匹配方式；
- 将受影响的 canonical resource 集合。

UI 因而可以显示真正的变更预览，而不是只显示一条可能间接调用十个程序的 shell 命令。落盘后还可返回最终 diff，避免 formatter 等后处理让批准时和实际结果不一致。

整文件 `write` 的预览策略不统一：Pi 只显示将写入的新内容；Claude Code 和 OpenCode V1 会读取旧内容并生成 diff；OpenCode V2 whole-file write 不生成 diff。

### 6. 接入历史、事件、formatter、LSP 和编辑器

独立工具调用是稳定的生命周期边界：

```text
before_tool / permission
→ before_file_edit snapshot
→ mutate
→ formatter
→ file-written event
→ LSP didChange / didSave / diagnostics
→ UI diff / history / telemetry
→ after_tool
```

Claude Code、OpenCode V1 和 Grok 都把其中一部分接到了文件工具上。若只运行任意 Bash，框架通常只能在命令结束后扫描整个工作树；这既无法生成可靠的执行前 diff，也很难区分本次命令、后台进程、用户编辑器和 formatter 各自造成的变化。

### 7. 让相同语义落到不同执行后端

Pi 把 `readFile`、`writeFile`、`mkdir` 等操作注入工具，Harness 版本则要求所有内置工具只经过宿主提供的 `ExecutionEnv`。仓库示例复用同一 `write`/`edit` 协议写 SSH 主机和 Gondolin VM：[operations 接口](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/write.ts#L21-L40)、[Harness 约束](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/agent/docs/agent-harness.md#L82-L84)。

Codex 也把 Patch 最终执行接到本地、沙箱或远端文件系统实现，而不是要求远端一定提供一个完整 shell。这使文件变更成为宿主可提供的能力接口。

## 各项目实现

### 1. Grok Build

#### 实际暴露的工具取决于 preset

Grok Build 同时维护多种 mutation 协议，而不是给所有模型塞入全部重叠工具：

- 原始 `default_grok_build_toolset()` 只列出 `search_replace`；
- 当前 `grok-build` workspace preset 在该集合上增加 OpenCode 风格的 `write`；
- 默认 `AgentBuilder` 的 `write_file_enabled` 也是 true，会在尚无 write 工具时动态补入它，因此默认实际运行态同样是 `search_replace` + `write`；
- Codex preset 使用 `apply_patch`；
- OpenCode preset 使用 `edit`/`write`；
- 可选 Hashline 配置会替换标准 read/search/edit 槽，但在默认 write feature 开启时仍保留独立 `write`。

这些组合集中注册在 [agent preset 配置](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-agent/src/config.rs#L170-L228)和[工具 registry](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/registry/types.rs#L674-L757)中，默认动态补入 Write 的逻辑位于 [`AgentBuilder`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-agent/src/builder.rs#L706-L765)。这个设计说明工具形状也是模型适配层：不同模型对整文件、字符串替换、patch 或 hash anchor 的训练分布不同。

#### `write`

模型输入是 `file_path` 和 `content`。执行时：

1. 把模型路径映射到当前显示工作区或 fork worktree；
2. best-effort 读取旧内容和存在状态；
3. 递归创建父目录；
4. 通过文件系统后端完整写入；
5. 发出包含 previous/new content 和 `is_new` 的 `FileWritten`；
6. 返回 create/update 类型、整文件结构化 edit 和行数统计。

主体实现见 [`OpenCodeWriteTool`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/opencode/write/mod.rs#L20-L195)。

这里“读旧内容”是为了变更事件和结果，不是 read-before-write guard。当前 whole-file `write`：

- 不检查模型是否先调用过 Read；
- 不比较 mtime、hash 或 expected bytes；
- 不执行 temp-file + rename；
- 直接采用 last-writer-wins；
- 本地后端只对 Windows sharing/lock 的暂时失败做重试。

其中读取失败会被当作目标不存在继续处理，而不是 fail-closed；所以这次内部 Read 不能被理解成安全检查。

对应本地落盘见 [`LocalFs::write_file`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/computer/local/file_system.rs#L56-L87)。

较重的能力位于外层会话执行器：plan mode gate、pre-tool hook、按目标文件申请 edit permission，以及同一模型批次里的 same-path mutex。[权限与 hook](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_calls.rs#L952-L1160)和[批次锁](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-shell/src/session/acp_session_impl/tool_calls.rs#L453-L504)对所有结构化写工具复用。锁 key 来自原始参数中的路径字符串，只在本次并行 batch 内有效；`a.py`、`./a.py`、绝对路径或 symlink alias 仍可能落入不同的锁。

`FileWritten` 又被通知桥接层用于 hunk tracker、审计和 rewind，所以即使 `write` 核心简单，系统仍能知道前后内容。[事件结构](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/notification/types.rs#L185-L209)明确保存了 previous content，[通知桥](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-shell/src/tools/notification_bridge.rs#L353-L376)将它交给 hunk tracker 和 rewind snapshot。

#### `search_replace` 与 Hashline

`search_replace` 用 `old_string`/`new_string` 表达局部编辑：

- 默认要求旧字符串唯一，或显式 `replace_all`；
- `old_string=""` 也可创建或完整覆盖文件，而且“空 old 不覆盖现存非空文件”的保护默认没有开启；
- 保留 CRLF；
- 可对 Unicode confusable 做有限 fallback；
- 可拒绝 `.gitignore` 命中的目标；
- 返回结构化 diff 和上下文；
- “先 Read”主要通过工具描述和依赖元数据鼓励，并没有 session read revision 的强制检查。

实现入口和参数语义见 [`search_replace`](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L59-L139)。

可选 Hashline 协议让 Read 返回“行号 + 内容 hash” anchor；一次 edit 可组合 replace、insert-after 和整文件 write。所有 anchor 会先对当前内容验证，任一 stale、ambiguous、overlap 或 not-found 都会让整批逻辑变更在落盘前失败，然后才写一次新内容。[Hashline 接口](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/mod.rs#L25-L48)和[批量验证](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/apply.rs#L143-L305)体现了“用显式前置条件防止模型凭旧上下文编辑”的思路。Hashline 内置的 whole-file write 不带 anchor，仍是完整覆盖。

这里的“整批失败”是内存中的编辑验证语义，不代表底层文件系统写入具有事务或崩溃原子性。当前 HashlineEdit 的 metadata 和 run 也没有发出 `FileWritten`，因此虽有结构化 diff，Grok 的 hunk attribution 和 rewind before-snapshot 通知链不会像 OpenCode Write/SearchReplace 那样运行。[Hashline 执行路径](https://github.com/xai-org/grok-build/blob/500129c714ad1b10e6095481f4a8387a2ec52649/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/mod.rs#L213-L434)显示它直接读、算、写和返回结果。

### 2. Pi

#### `write` 本身很薄

公开 schema 只有：

```text
path: string
content: string
```

工具承诺创建或覆盖文件并自动建立父目录，提示模型只在新文件或完整重写时使用它；局部修改交给 `edit`。[schema 与描述](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/write.ts#L14-L40)。

执行层实现了：

- 相对/绝对路径和 `~`、`file://`、开头 `@`、特殊 Unicode 空格容错；
- 对现存文件取 `realpath` 后进入 per-file mutation queue；
- 递归 `mkdir`；
- AbortSignal 前后检查；
- 可注入的 `writeFile`/`mkdir` operations；
- 成功后返回写入长度；
- TUI 流式展示目标路径、语法高亮后的新内容，默认折叠到前十行。

核心调用见 [`write.ts`](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/write.ts#L181-L260)。

Abort 的语义值得注意：底层 I/O 一旦开始不一定能取消；Pi 会等待它 settled 后再报告 abort 和释放队列，避免尚未结束的写与下一次写交错。它提供的是并发顺序，不是回滚。

#### `edit` 承担局部变更的复杂性

Pi 的 `edit` 一次接受多个 `{ oldText, newText }`：

- 所有 old text 基于同一个原始快照匹配；
- 拒绝空目标、找不到、多次匹配、重叠和 no-op；
- 全部验证通过后倒序应用并只写一次；
- exact 失败后可兼容行尾空白、Unicode NFKC、智能引号、横线和特殊空格；
- 保留 BOM 和原文件换行风格；
- 返回给 TUI 的紧凑 diff、标准 unified patch 和首个变化行；
- 参数完整时可在真正执行前异步生成 diff 预览。

多替换算法见 [`edit-diff.ts`](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/edit-diff.ts#L251-L374)，执行与结果见 [`edit.ts`](https://github.com/earendil-works/pi/blob/c13ffe1877c3a47ce9f2fc98d9880447d64a0e87/packages/coding-agent/src/core/tools/edit.ts#L287-L430)。

#### 扩展与边界

`tool_call` hook 可以修改参数或阻止调用，`tool_result` hook 可以替换结果；同名扩展还能覆盖内置实现。这使路径保护、审批、审计、SSH/VM 后端和自定义 renderer 都有稳定接入点。

Pi 的限制也很明确：

- whole-file `write` 没有先 Read、mtime、hash 或 expected-content 检查；
- 本地实现是直接 `writeFile`，没有 temp + fsync + rename；
- `write` 不读取旧文件生成 diff，只预览新内容；
- mutation queue 只协调使用同一队列的 Pi 工具，不包含 Bash 和外部进程；
- 路径默认不限制在 cwd 内，`realpath` 是为队列归并而不是 sandbox；
- 扩展 hook 修改工具参数后不会再次 schema 校验；
- 默认同时开放 Bash，因此 hook 级路径保护不能独立构成权限边界。

Pi 的设计重点不是“比 Bash 更会写文件”，而是用尽量小的协议获得 TUI、hook、并发和可替换执行环境。

### 3. Claude Code

#### 明确把 Write 与 Edit 分工

`Write` 输入只有绝对 `file_path` 和完整 `content`。工具提示明确说：

- 新文件或完整重写才用 `Write`；
- 修改现存文件优先 `Edit`，因为它只发送 diff；
- 现存文件必须先完整 Read，否则工具失败。

见 [`FileWriteTool` 描述](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/prompt.ts#L1-L19)。系统提示还直接解释了产品动机：专用工具让用户更容易理解和审阅工作，因此创建文件不要用 heredoc/echo 重定向。[系统工具指导](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/constants/prompts.ts#L286-L309)。

#### 运行时真的强制先 Read

这不是只有 prompt：

1. 展开路径并检查内容是否把秘密写入团队 memory；
2. 提前匹配 deny rule；
3. UNC 路径在 permission 前不做 stat，避免 Windows SMB/NTLM 凭据泄漏；
4. 现存文件必须有完整 Read state；
5. 文件 mtime 晚于 Read 就拒绝；
6. 真正写入前再同步读取 metadata 和 mtime；
7. Windows 等 mtime 易误报场景，对完整读取回退到内容比较；
8. 检查与写入之间刻意不插入异步 yield，缩小进程内竞态窗口。

输入校验见 [`validateInput`](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/FileWriteTool.ts#L153-L218)，最终写前重检见[同一工具的 call](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/FileWriteTool.ts#L249-L305)。

权限检查不仅看输入字符串，还检查原路径、symlink chain、断链目标的现存父目录、特殊文件和最终 resolved path，避免只按表面路径授权。[文件操作权限解析](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/fsOperations.ts#L288-L381)。

#### 落盘和后处理

执行还会：

- 自动建立父目录；
- 写前保存 file history 快照；
- 保留现存文件编码；
- 把模型给出的 content 当作完整替换，尊重其中显式换行，不偷偷沿用旧文件 CRLF；
- 对 symlink 写其 target 而不替换链接本身；
- 在同目录临时文件中写入并 flush，保留原权限位，再 rename 覆盖；
- 原子路径失败时清理临时文件并回退到直接 flush 写；
- 通知 LSP `didChange`/`didSave`、清理旧诊断；
- 通知 VS Code diff view；
- 更新 Read state，使连续编辑基于新版本；
- 返回 create/update、structured patch、original content 和行数统计。

尽力原子落盘及 fallback 见 [`writeFileSyncAndFlush`](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/file.ts#L354-L477)，LSP、编辑器和 diff 结果见 [`FileWriteTool.call`](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/FileWriteTool.ts#L297-L416)。

它是五个项目里 whole-file `write` 生命周期最完整的一套，但仍有边界：

- atomic rename 失败会回退成非原子覆盖；
- Read/mtime/内容比较不是跨进程事务 CAS；
- 写磁盘本身使用同步 I/O；
- whole-file content 的 token 成本高，所以提示仍要求现存文件优先 `Edit`；
- Bash 是另一条能力通道，安全仍依赖统一的权限与沙箱设计。

### 4. OpenCode

OpenCode 当前仓库同时存在两套实现：

- V1/legacy：`packages/opencode/src/tool/*`，旧 Session/CLI/TUI 路径仍在使用；
- Core V2：`packages/core/src/tool/*`，Location-scoped、schema-first 的新架构。

两者不能混为一谈。V1 文件工具的集成能力更完整，V2 mutation primitive 和并发语义更清晰。V2 文件工具 leaf 仍缺 formatter、显式 file-edit/watcher event 和 LSP 集成，leaf 中的 snapshot/undo 接入也标成 TODO；但 V2 会话层已经有通用 Snapshot capture/diff/restore 服务，不能误写成整个 V2 都没有 snapshot。[V2 `write` TODO](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/write.ts#L19-L47)与[会话层 Snapshot 调用](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/session/runner/llm.ts#L217-L333)分别体现了这两层。

#### 为什么同时有 write、edit、apply_patch

- `write`：模型已经知道最终完整内容时创建或显式覆盖；
- `edit`：用 old/new string 表达小改动，更省 token 并保留其余内容；
- `apply_patch`：一次表达多文件 add/update/delete，适合擅长 diff 的模型。

V1 registry 会按模型选接口：现代非 OSS GPT 暴露 `apply_patch`，其他模型主要看到 `edit` + `write`，避免把所有重叠工具同时塞给模型。[V1 工具选择](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/registry.ts#L286-L306)。

#### Core V2 的 Location 和权限

三个 mutation tool 共享 `LocationMutation`：

- 相对路径必须留在当前 Location，`../` 越界直接失败；
- 现存目标走 `realPath`；
- 不存在目标向上找最近的现存目录作为 canonical anchor；
- 工作区内 symlink 指向外部会报 `location_escape`；
- 显式外部绝对路径先申请父目录 `external_directory`，再申请具体资源 `edit`；
- 权限资源对内部路径使用 Location-relative identity，对外部使用 canonical absolute identity。

见 [`LocationMutation`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/location-mutation.ts#L90-L152)。

#### Core V2 `write`

V2 whole-file `write` 会 resolve、授权、自动建父目录、保留 UTF-8 BOM，并返回 created/wrote、canonical target、permission resource 和 `existed`。[执行流程](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/write.ts#L63-L97)。

它有意保持明确的 last-writer-wins：

- 不要求先 Read；
- 没有 mtime、hash 或 expected bytes；
- 不生成 diff；
- 不做 temp-file rename；
- 不显式管理或返回 mode；覆盖普通现存文件通常沿用底层文件权限，新文件权限依赖底层默认值和 umask；
- 同一 canonical target 只有进程内串行化。

V2 `edit` 则更严格：

- exact old string；
- 禁止 old == new 和空 old；
- 默认必须唯一，或显式 `replaceAll`；
- 保留 BOM 和原文件换行风格；
- 返回 replacements、unified diff、additions/deletions；
- 授权后读取原始 bytes，提交时在 canonical-path 锁内 `writeIfUnchanged(expectedBytes)`，文件变化就报 stale。

见 [`edit`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/edit.ts#L42-L159)和[`FileMutation`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/file-mutation.ts#L69-L166)。

V2 `apply_patch` 会先解析和 resolve 全部 hunk、批量授权、读取并 preflight 所有 update/delete，然后按顺序提交。Add 使用 create-only 的 `wx`，不会覆盖批准期间刚出现的文件；Update 使用 expected bytes；Move 尚不支持。[Patch 流程](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/core/src/tool/apply-patch.ts#L85-L202)。

它明确不是事务：提交阶段后面的操作失败，前面已经成功的修改会保留，并在错误中列出。Delete 的提交也没有 expected-content CAS。

#### V1 的厚集成

V1 `write` 会读旧内容生成 permission diff、保留 BOM、授权后写入、运行 formatter、发布 file/watcher event、touch LSP 并等待 diagnostics。[V1 `write`](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/write.ts#L46-L122)。

V1 `edit` 还实现多层 fuzzy replacer、单文件 semaphore、formatter 后最终 diff、文件事件和 LSP error 回馈；V1 Patch 支持 move，但 Add 和 Move 都可能覆盖目标，也不具备 V2 的 byte-CAS。

一个值得记录的实现/文案漂移是：V1 `write.txt` 和 `edit.txt` 声称现存文件必须先 Read，否则工具失败；实际代码没有查询 session Read 历史或 mtime，只是自己读当前文件后继续执行。[提示文案](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/write.txt#L1-L8)与[实际实现](https://github.com/anomalyco/opencode/blob/8c38d260eb6555d2824230be100fb2a7eadd7513/packages/opencode/src/tool/write.ts#L46-L122)并不一致。

这说明“单独有工具”只提供了实现 guard 的位置，并不保证 guard 真的存在；研究时必须区分 prompt、TODO 和运行时代码。

### 5. Codex

#### 没有 whole-file Write

Codex 的标准本地 Coding Turn 不向模型暴露 `write_file` 或 `edit_file`，只有自由格式输入的 `apply_patch`。App Server 中另有 `fs/writeFile` RPC，但它面向宿主客户端，不是模型工具，不能混入本比较。

`apply_patch` 不是让模型拼一条 shell 命令，而是一个带独立 grammar 的 freeform tool：

- `*** Add File`
- `*** Delete File`
- `*** Update File`
- `*** Move to`
- 多文件 patch
- 上下文行和 EOF anchor

工具 schema 与语法见 [`apply_patch_spec`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/core/src/tools/handlers/apply_patch_spec.rs#L18-L31)和 [Lark grammar](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/core/src/tools/handlers/apply_patch.lark#L1-L19)。

这给出了本问题最直接的反例：**需要结构化文件变更，不等于需要独立的 whole-file `Write`。** Add File 已能创建完整文件；Update Patch 更适合普通代码修改。

#### 实现的能力

执行链会：

1. 解析完整 patch；
2. 对 Update/Delete 读取旧文件，并为 Update 计算新内容和 unified diff；Add 直接携带目标内容；
3. 在执行动作前验证所有 hunk；
4. 用 exact → 忽略尾空白 → 两侧 trim → Unicode 标点归一化逐级寻找上下文；
5. 按 permission profile 做安全分类，必要时请求审批，并在受管配置中使用平台 sandbox；
6. 在本地、沙箱或远端 FS 执行；
7. 发送执行生命周期的 begin/end event；启用相应 feature 时，参数生成期间还可流式发送 patch diff update；
8. 返回稳定的 A/M/D 结果，并接入 hooks。

解析与预验证见 [`apply-patch invocation`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/apply-patch/src/invocation.rs#L180-L239)，上下文匹配见 [`seek_sequence`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/apply-patch/src/seek_sequence.rs#L1-L96)，安全分类见 [`safety.rs`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/core/src/safety.rs#L32-L86)。

即使模型通过 shell 形式调用 `apply_patch <<'PATCH' ...`，Codex 也会识别这种受限形状并路由到同一 Patch 安全链，而不是把它当普通任意 shell 副作用。

#### 重要边界

- 多文件 Patch 不是事务：hunk 顺序落盘，后续失败不会回滚此前成功项；
- Add File 当前可覆盖已存在目标，不是 create-only；
- Move 是先写目标再删源，删除失败可能留下两个文件；
- 最终仍是文本整文件重写，不支持二进制增量或 mode metadata；
- `apply_patch` 默认不并行，在同一工具批次的共享执行门上取独占锁，但这不是 session、进程或文件级全局锁，也没有跨进程 revision CAS；
- 外部用户进程可在验证与最终写之间竞争；
- `apply-patch` parser/runtime 内未见工具局部的 patch 大小上限，但模型、API 和上下文层仍会限制实际输入。

顺序执行和失败后保留已提交 delta 的实现见 [`apply-patch lib`](https://github.com/openai/codex/blob/578c1b2230288104041e880a86d0f7f3a5ca6e47/codex-rs/apply-patch/src/lib.rs#L390-L510)。

Codex 的选择是把大量基础设施放在通用命令执行层和 Patch runtime，而不是再为 Read、Write、Edit 各做一套模型接口。这减少了工具数量，却没有消除权限、沙箱、输出、事件、远端 FS 和并发控制的复杂度；复杂度只是换了一层。

## 功能与设计目的对照

| 功能 | 主要解决的问题 | 项目示例 |
| --- | --- | --- |
| `{ path, content }` schema | 内容/命令分离、参数校验、跨平台 quoting | Pi、Claude Code、OpenCode、Grok |
| Write/Edit/Patch 语义分工 | 控制 token、保留未改内容、适配不同模型 | 五个项目；Codex 只保留 Patch |
| canonical path / symlink 权限检查 | 权限别名、路径逃逸 | Claude Code、OpenCode V2 |
| `realpath` 队列归并 | 让路径别名尽量共享进程内写队列 | Pi |
| 自动创建父目录 | 少一次工具调用，避免模型先 `mkdir` | 五个项目的 create 路径 |
| prior Read / mtime / expected bytes | 防止基于旧上下文覆盖新修改 | Claude Code、OpenCode V2 edit |
| exact old text / patch context / hash anchor | 把旧版本假设变成可验证前置条件 | Pi/OpenCode/Grok edit、Codex Patch、Grok Hashline |
| per-file queue / lock | 防止同一 Agent 的并行 lost update | Pi、OpenCode V2；OpenCode V1 仅 edit；Grok 仅同批次同原始路径字符串；Codex 用更粗的批次执行门 |
| temp + flush + rename | 降低崩溃或中断留下截断文件的风险 | Claude Code；其他 whole-file Write 多为直接覆盖 |
| mode / 权限位管理 | 避免替换文件时破坏可执行位等权限 | Claude Code |
| BOM / 换行风格处理 | 避免小修改产生无关 diff 或破坏编码标记 | Pi edit、OpenCode；Claude Code 保留编码但尊重模型显式换行 |
| diff / additions / deletions | 批准、审阅、模型反馈、遥测 | Claude Code、OpenCode edit/patch、Pi edit、Codex Patch |
| history / rewind / file event | 撤销、审计、UI 同步、hunk 归属 | Claude Code、Grok、OpenCode V1 |
| formatter / LSP diagnostics | 写后自动形成“修改—诊断—修复”闭环 | Claude Code、OpenCode V1 |
| operations / ExecutionEnv / FS trait | SSH、VM、容器、远端或虚拟文件系统 | Pi、Codex、Grok |
| hook 和/或 permission lifecycle | 阻止、改写、审批、记录一次 mutation | 五个项目均有其中一部分；Pi 主要依赖扩展 hook，没有内置 sandbox/审批 |

## 专用写工具的成本和陷阱

### 1. 容易产生重复实现

如果 `write`、`edit`、`apply_patch` 和 Bash 各自拥有不同的路径解析、权限、落盘和事件逻辑，就会出现：

- 某个工具检查 symlink，另一个不检查；
- 某个工具原子替换，另一个直接 truncate；
- 某个工具生成最终 diff，另一个只生成批准前 diff；
- 某个工具进入同文件队列，Bash 不进入；
- prompt 声称必须 Read，但运行时没有状态检查。

OpenCode V1/V2 的 parity gap 和 Pi 的 Bash 绕过都说明：专用工具越多，越需要一个共享 mutation core，而不是复制多个 `writeFile()` 调用。

### 2. “结构化”不等于“原子”或“事务”

这三个概念应分开：

- **结构化**：框架知道操作意图和目标；
- **单文件崩溃原子性**：替换前后通常只能看到完整旧版或新版；
- **多文件事务**：整批全部成功或全部回滚。

Claude Code 只做到了尽力的单文件 temp + rename，失败还会回退；Codex、OpenCode Patch 都明确不是多文件事务；Pi、Grok 和 OpenCode whole-file write 主要是直接覆盖。

### 3. whole-file Write 可能更费 token

修改一个大文件中的三行，如果模型必须重发完整 content：

- 输入 token 更多；
- 更容易无意改掉未关注的区域；
- 冲突时重试成本更高；
- UI 需要从整文件重新算 diff。

因此 Claude Code、Pi、OpenCode 都把 `Write` 定位在新文件或完整重写，普通变更优先 `Edit`/Patch。Codex 则进一步不提供 whole-file Write。

### 4. 模型可能在重叠工具间摇摆

三个相似 schema 都进入系统提示会占上下文，也增加工具选择错误。OpenCode 按模型切换 Patch 与 Edit/Write，Grok 用 preset 选择 SearchReplace、OpenCode 或 Hashline 协议，说明工具接口要和模型训练分布一起设计。

### 5. 容易产生虚假的安全感

给 `write` 加一个“不能改 `.env`”hook 很容易，但只要 Bash 还能执行 `python -c` 或重定向，该规则就不是边界。正确做法是：

- 受限模式禁用 Bash；或
- Bash 与文件工具共享同一个工作区/文件系统 sandbox；或
- 在容器、VM、OS 权限层控制整个 Agent；
- hook 只作为更友好的策略和审批层，不把它宣传为唯一安全机制。

## 什么时候 Bash 已经够用

只使用 Bash 是一个合理的产品选择，尤其当同时满足：

- 运行环境可信、只处理本地临时工作区；
- Agent 单线程，不会并发修改同一文件；
- 用户不需要执行前 diff、逐文件审批、历史回滚或 IDE 实时同步；
- 不需要禁用任意命令而只开放“改文件”这一项能力；
- 不需要 SSH/VM/浏览器虚拟 FS 等无完整 shell 的后端；
- 模型针对 shell 使用训练充分；
- 项目愿意把安全、审批和输出控制统一投资在 exec 层。

Codex 证明了“没有 whole-file Write”完全可行，但它并不是“裸 Bash”：它仍有结构化 `apply_patch`，而且命令执行层本身有沙箱、审批、会话、输出预算和远端环境支持。

Bash 也仍然更适合：

- 运行 formatter、代码生成器、编译器或数据库迁移工具；
- 批量机械变换大量文件；
- chmod、symlink、特殊 mode、管道和复杂文件选择；
- 使用成熟 CLI 完成专用工具未表达的操作。

## 对 nanoPyCodeAgent 的建议

> **2026-08-04 修订**：本节初版把薄 `write` 相对 Bash 的收益归纳为“少量 quoting 便利”，据此建议继续 Bash-first。复核后认为这低估了两点收益，结论修正为：**现在就值得做一个薄 `write`，理由是内容/命令分离与终端展示，而不是控制面。**

“不要仅仅因为主流 Agent 都有就加薄包装”这一原则仍然成立，关键在理由是否真实。支持现在就做的理由有两条：

**第一，内容/命令分离消除的是静默坏文件，不只是 quoting 不便。** 用 heredoc 写文件的典型失败不是报错后重试：delimiter 未加引号时，内容里的 `$var`、反引号和 `$()` 会被 shell 展开，文件写坏而 exit code 仍是 0，没有任何错误让模型去重试；内容恰好包含 delimiter 时文件被静默截断。对一个没有 diff 审阅、没有写后校验的 nano agent，这类无声坏文件正是最难发现的错误。`write({path, content})` 把内容当数据，第一天就消除这整类失败，不依赖任何控制面。

**第二，本仓库已经用 `read` 否定过“Bash 能做就不单独做工具”。** `read` 工具相对 `cat`/`sed` 同样没有新增文件系统能力，它存在的理由是行号规范、输出上限，以及出错时不止说失败原因、还直接给出下一步操作的错误信息（例如告知文件总行数、给出切分超长行的 bash 命令）——纯粹的结构化与 UX。`write` 的收益完全同构：结构化输入、明确的错误语义，以及终端展示——在 tool output shading 之后，一条携带几百行 heredoc 的 bash 命令在终端里不可读，而 `write` 调用可以像 Pi 那样折叠展示“写哪个文件 + 前几行内容”。

据此，两条路线的取舍修正如下。

### 路线 A（修正）：Bash + 薄 `write`

适合 nanoPyCodeAgent 当前强调最小实现、可信本地工作区的阶段：

- 保留 Bash 作为通用文本与系统操作接口，formatter、批量变换、追加写入等仍走 Bash；
- 在 exec 层做好工作区 sandbox、审批和输出预算；
- 新增一个薄 `write`，体量与风格对齐 `read_tool.py`：`{path, content}` schema、拒绝目录与非常规文件、自动创建父目录、终端折叠展示，工具描述明确不宣称任何安全性；
- 不引入先 Read、mtime、expected_revision 或原子替换——在单线程、无审批 UI 的当前形态里它们是假保证，语义就是 last-writer-wins；
- 工具顺序先 `write` 后 `edit`：`write` 实现最简单、语义最无歧义，而 `edit` 的复杂度全在匹配语义（唯一性、模糊回退、换行风格），`apply_patch` 还要自带 parser；等 whole-file 重写的 token 成本成为现实痛点时再做 `edit`。

### 路线 B：建立统一的文件变更控制面

当产品需要 diff 审批、受限模式、并行 tool calls、远端环境、undo 或 IDE 集成时，再把文件工具升级为统一的控制面。此时关键不是工具名，而是先建立一个所有 mutation tool 共用的核心：

1. 规范化并 canonicalize 目标，定义明确的工作区和 symlink 策略；
2. 把 create 与 overwrite 分开，支持 `must_not_exist` 或 `expected_revision`/`expected_digest`；
3. 权限批准后重新检查前置条件；
4. 按 canonical path 串行化 read-compute-write；
5. 同目录临时写、flush、保留 mode，并尽力 atomic rename；
6. 统一返回 create/update/delete/move、diff 和 old/new revision；
7. 统一发出 before/after、history、LSP/formatter 等事件；
8. `Write`、`Edit`、`Patch` 都调用该核心；
9. Bash 仍由同一个文件系统 sandbox 约束，不能绕过边界。

在这个架构上，模型接口可以保持很小：

```text
Write(path, content, expected_revision?)
Edit(path, old_text, new_text, replace_all?, expected_revision?)
ApplyPatch(patch_text)
```

修正后的最终判断是：

- **为控制面做 `write`，当前不值得：权限、审阅、并发、历史、远端执行仍按路线 B 在需求出现时再建（维持原判断）；**
- **为内容/命令分离与终端展示做一个薄 `write`，现在就值得：它消除 heredoc 静默坏文件这一整类失败，依据的是 `read` 工具已经验证过的同一条价值判断；**
- **薄 `write` 必须诚实：不宣称安全边界，也不引入单线程形态下没有意义的防陈旧与原子机制；**
- **`edit`/`apply_patch` 与控制面推迟到真实需求出现；届时各 mutation tool 应共享 mutation core，避免把 `writeFile()` 包装成一座功能孤岛（维持原判断）。**
