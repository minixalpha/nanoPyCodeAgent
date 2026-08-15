# 五个 Code Agent 的 Edit 工具设计调研

> 本文明确指定使用中文编写和维护。

## 研究范围与口径

本文调研 `references/` 下五个 Code Agent 的模型可调用编辑工具，回答三个问题：

1. 项目是否提供 Edit 工具；若没有，用什么协议完成局部编辑？
2. 为什么要在 Bash 和整文件 `write` 之外设计 Edit，它具体提供了哪些能力？
3. nanoPyCodeAgent 已有 `read`、`write`、`bash` 后，下一步应采用什么 Edit 契约？

这里的“Edit 工具”泛指表达“基于当前文件做局部变更”的模型协议，包括精确字符串替换、带锚点的编辑和 Patch；普通 GUI/服务端 `fs/writeFile` RPC 不算模型工具。本文以当前检出的源码为准。`claude-code` 是本仓库采用的第三方源码镜像，不是 Anthropic 官方开源仓库。

| 项目 | 当前提交 | 提交日期 |
| --- | --- | --- |
| `grok-build` | [`eb267fe`](https://github.com/xai-org/grok-build/tree/eb267feff13129e568df38fb6fdf0ceb65f735d6) | 2026-08-13 |
| `pi` | [`b1efcf7`](https://github.com/earendil-works/pi/tree/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004) | 2026-08-14 |
| `claude-code` | [`a371abb`](https://github.com/yasasbanukaofficial/claude-code/tree/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367) | 2026-04-05 |
| `opencode` | [`e23586a`](https://github.com/anomalyco/opencode/tree/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3) | 2026-08-14 |
| `codex` | [`5bc8da6`](https://github.com/openai/codex/tree/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87) | 2026-08-14 |

两条口径需要先声明：

- **快照新旧不齐。** `grok-build`、`pi`、`opencode`、`codex` 都是 2026-08 中旬的检出，`claude-code` 镜像停在 2026-04-05，比其余四个旧约四个月。本文关于 Claude Code 的结论只对该镜像成立，不能当作 Claude Code 当前版本的描述。
- **同名工具要认准包。** 有些仓库同时存在多套 Edit 实现，本文只调研模型在该 Code Agent 里实际会调用的那一套。Pi 的 CLI 由 `@earendil-works/pi-coding-agent` 提供（`bin: pi` → `cli.ts` → `main.ts` → `AgentSession` → `createAllToolDefinitions`），落到 [`packages/coding-agent/src/core/tools/edit.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts)，本文写的就是它；通用 agent 内核 `@earendil-works/pi-agent-core` 另有一份 [`packages/agent/src/harness/tools/edit.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/agent/src/harness/tools/edit.ts)，共用同一套匹配算法但把 I/O 换成全 `env` 抽象，当前只被 `server/create-harness.ts` 引用，CLI 走不到。OpenCode 的两代差异大得多，按 V1/V2 分别记录。

## 结论

五个项目都有结构化局部编辑能力，但并没有收敛到同一种 Edit：

| 项目 | 是否有名为 Edit 的模型工具 | 主编辑协议 | 设计取向 |
| --- | --- | --- | --- |
| Grok Build | 默认没有 `edit`；默认叫 `search_replace`，其他 preset 可换成 `hashline_edit`、OpenCode `edit` 或 `apply_patch` | 精确 old/new 字符串；可选行哈希锚点或 Patch | 按模型/preset 选择协议，工具外层统一做权限、hook、plan gate 和事件 |
| Pi | 有 `edit` | 单文件 `edits[]`，每项为 `oldText`/`newText` | 一次提交多个不重叠局部替换，轻量、可嵌入、可替换执行后端 |
| Claude Code | 有 `Edit`，另有 `NotebookEdit` | 单个 `old_string`/`new_string`，可 `replace_all` | 强 Read-before-Edit、防陈旧、历史、权限、LSP 和 IDE 集成 |
| OpenCode | V1/V2 都有 `edit`，也有 `apply_patch` | 单个 old/new + `replaceAll`；V1 的 GPT 模型改用 Patch | V1 偏重 fuzzy 与生态集成，V2 偏重 exact、canonical path 和进程内 expected-bytes 条件写 |
| Codex | **没有**字符串型 `edit` | 自由格式 `apply_patch` | 用一套 Patch 覆盖多文件 add/update/delete/move，减少重叠工具 |

因此，“Edit 工具”真正的共同点不是名字或 schema，而是：**模型只表达变更及其前置条件，运行时读取当前文件、验证前置条件，再保留未涉及的内容。**

相较整文件 `write`，Edit 的第一价值是少传 token、少重写无关内容；相较 Bash，它的第一价值是让 Agent 运行时理解“改哪个资源、以什么旧内容为前提、实际产生了什么 diff”。但 Edit 仍不是天然的安全边界或事务：只要 Bash 可以任意写文件，路径规则就能被绕过；只要检查和落盘不是同一个强一致存储事务，外部进程仍可能制造竞态。

## 为什么要设计 Edit 工具

### 1. 用增量表达替代整文件重传

改三行代码时，`write(path, complete_content)` 要让模型重发整个文件。文件越大，输入 token、无意改动未关注区域的概率、冲突后的重试成本和 UI 重新计算 diff 的成本都越高。Edit 只发送目标旧文本和新文本；Patch 只发送带上下文的 hunk。

这也是 Claude Code、Pi 和 OpenCode 都把 `write` 留给新建或完整重写、把普通修改交给 Edit 的原因。Codex 更进一步，根本不暴露 whole-file Write，新增文件也用 `*** Add File` Patch 表达。

### 2. 把模型所依赖的旧状态变成可验证前置条件

局部编辑不是“在第 37 行写入”，而是“只有这段旧内容仍存在且能唯一定位时才替换”。若用户、formatter 或另一个工具已改掉它，Edit 应失败并让模型重读，而不是像 whole-file Write 那样覆盖当前版本。

不同项目选择了不同强度的前置条件：

- 字符串 Edit：旧文本存在且默认唯一；
- Patch：上下文 hunk 仍能定位；
- Hashline：Read 返回的行号与内容 hash 仍能验证；
- Claude Code：再叠加会话 Read 状态和 mtime/内容比较；
- OpenCode V2：权限批准后读取原始 bytes，提交时执行 `writeIfUnchanged(expectedBytes)`。

前两类是“语义前置条件”，后两类进一步绑定了读取版本。它们都比无条件覆盖好，但都不自动等于跨写者 CAS 或文件系统事务。

### 3. 让错误默认失败，而不是猜一个位置

旧文本出现多次时，默认只替换第一个很危险。主流字符串 Edit 普遍要求唯一匹配；模型要么增加少量上下文，要么显式开启 `replace_all`。批量协议还会拒绝重叠范围，避免先应用一个替换后改变另一个替换的含义。

这种 fail-closed 语义也让错误可恢复：工具可明确返回“不存在”“找到 N 处”“文件已变化”“锚点已陈旧”，而不是只交给模型一段 shell stderr。

### 4. 建立可审批、可观察的文件变更生命周期

结构化输入让 Agent 运行时在执行前知道目标路径，并可在执行后得到 old/new 内容或 unified diff，从而接入一条可审计的生命周期。具体项目的授权时机不同；较完整的顺序是：

```text
目标与 canonical path 解析
→ 路径/读取授权（敏感内容读取前）
→ 读取当前内容并验证前置条件
→ 计算最终 diff / 内容审批 / 可选预写 checkpoint
→ 提交前复核或 expected-bytes 条件写
→ 落盘
→ formatter / LSP / 文件事件 / history / undo / 审计
→ 给模型的摘要与给 Agent 运行时的结构化结果
```

任意 Bash 当然也能修改文件，但 Agent 运行时很难从一个动态 shell 程序中可靠推导最终写集合、执行前 diff 和每个 hunk 的归属。

### 5. 适配模型的训练分布，而不是追求唯一协议

OpenCode 会给现代非 OSS GPT 模型暴露 `apply_patch`，给其他模型暴露 `edit`/`write`；Grok Build 也用 preset 在 search/replace、Hashline、OpenCode Edit 和 Codex Patch 之间切换。这个事实说明：工具 schema 是模型适配面，不能只按 Agent 运行时的实现难度决定。

字符串替换对模型最简单；Patch 更适合一次多文件变更；Hashline 把“旧内容仍是我看到的版本”编码得最强，但要求 Read 输出和 Edit 输入采用一套新的锚点语言。不存在对所有模型都最优的接口。

## 各项目实现

### 1. Grok Build

#### 是否有 Edit

有局部编辑能力，但默认工具名是 `search_replace`。默认 Grok Build 工具集注册 `read_file` + `search_replace`，workspace 版本另加 `write`；Codex preset 改用 `apply_patch`。文件工具也可成组切换成 `hashline_read`/`hashline_edit`/`hashline_grep`，而且 registry 明确拒绝标准与 Hashline 文件工具混用。[preset 配置](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-agent/src/config.rs#L170-L347)与[互斥校验](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/registry/types.rs#L878-L908)体现了这种“按协议成套替换”的设计。

#### `search_replace`

输入为：

```text
file_path: string
old_string: string
new_string: string
replace_all: boolean = false
```

它先做 exact 字符串查找；默认要求唯一，`replace_all=true` 才替换所有非重叠匹配。`old_string == new_string` 失败。只要文件含 CRLF，就会转到 LF 逻辑空间匹配，再把整个输出恢复为 CRLF；普通 CRLF 文件因此可保持风格，混合行尾则会被统一。[schema 与描述](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L53-L139)和[匹配、换行及落盘](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L522-L738)给出了实际语义。

精确匹配失败后，默认只返回邻近行、可能由用户修改以及 Unicode typography 的诊断；可选配置才启用 Unicode confusable 归一化回退。回退会把 smart quotes、dash、特殊空格等映射后匹配，再把范围映射回原始 UTF-8 字节，并对 partial expansion、重叠和歧义 fail closed。[归一化回退](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/helpers.rs#L136-L263)刻意比“模糊找到差不多的位置就改”保守。

空 `old_string` 兼任创建/整文件写入。一个容易误读的兼容点是：`empty_old_string_does_not_override` 默认仍为 false，因此可覆盖现存非空文件，成功文案还会称其为 “created”；显式开启 guard 后，预期语义才收窄为 create-or-fill-empty。这个 guard 也不是严格 fail-closed：创建分支会吞掉读取错误，把不可读目标当成不存在处理。[版本化参数](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L94-L139)和[空串分支](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build/search_replace/mod.rs#L294-L405)说明了这个历史兼容取舍。

成功结果包含修改上下文和行号；结构里的 `patch` 字段当前始终为 `None`。它会发出带 previous/new content 的 `FileWritten`，供 hunk tracker、rewind 和 UI 使用。外层 session 再统一做 plan-mode gate、pre-tool hook 与编辑权限。因此核心 search/replace 相对薄，控制面主要在编排层，但仓库里的 `FileOperationLockManager` 当前没有接入这条执行路径。

边界是：它没有会话级 prior-Read revision、mtime、expected-bytes CAS 或共享路径锁；读、算、写之间仍可被其他工具或外部进程竞争。CRLF 恢复会统一整个输出的行尾，混合行尾文件可能产生无关变化。默认 UTF-8 解码还是 lossy，编辑非法 UTF-8 文本存在替换字符风险。权限按词法路径匹配，而已有目标在 I/O 前会 canonicalize；symlink 指向另一权限域时需要依赖外层 OS sandbox，而不能只信工具规则。

#### `hashline_edit`

Hashline Read 给每行返回 `LINE:HASH[:CONTEXT_HASH]` anchor；Edit 一次接受多个操作：

- `replace(anchor, end_anchor?, content)`：替换/删除一行或范围；
- `insert_after(anchor, content)`：可用普通 anchor、BOF `0:` 或 `EOF`；
- `write(content)`：整文件替换，不需要 anchor。

schema 见 [`types.rs`](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/types.rs#L7-L116)。所有 anchor 都针对同一个编辑前快照验证；任一个 stale、ambiguous、not-found 或 overlap，整批逻辑编辑在写盘前失败。通过后按从下到上应用一次，并返回带新 anchor 的局部片段供后续编辑。[批量校验和应用](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/grok_build_hashline/edit/apply.rs#L143-L305)。

它解决的是普通行号在插入/删除后漂移、旧文本太长又浪费 token 的问题；stale anchor 还会在附近寻找移动后的候选，并只返回 fresh anchor 让模型重试，而不是擅自修改。代价是 Read/Edit 必须绑定为一套协议，默认三字符、会忽略部分空白差异的 hash 也不是密码学 revision；模型还可能把 anchor 前缀误抄进内容，因此实现专门检测并报错。逻辑批次的“全验证后一次写”也不等于可见性原子、崩溃持久或跨写者 CAS。与默认 `search_replace` 不同，当前 Hashline Edit 不发送 `FileWritten` 事件，普通 replace/insert 还会把 CRLF 统一为 LF。

#### 其他兼容 preset

Grok Build 还保留两套从其他 Agent 协议移植的实现，而不只是给工具改名：

- `Codex:apply_patch` 接受 JSON 字段 `patch`，Patch 本体支持多文件 Add/Delete/Update/Move。它先解析并在内存中计算全部变化，再顺序执行 I/O；hunk 失败可在写前阻断，但落盘阶段失败不回滚，Add/Move destination 也可覆盖已有文件。[工具与三阶段执行](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/codex/apply_patch/tool.rs#L25-L105)与[提交阶段](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/codex/apply_patch/tool.rs#L313-L477)说明它是“全量预检 + 非事务提交”。
- `OpenCode:edit` 使用 `filePath`/`oldString`/`newString`/`replaceAll`，但该移植版只做 exact，不包含 OpenCode V1 当前的多层 fuzzy；空 old 可创建或覆盖空文件，普通编辑默认要求唯一，并发送 `FileWritten`。[schema 与执行](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/opencode/edit/mod.rs#L45-L88)及[替换路径](https://github.com/xai-org/grok-build/blob/eb267feff13129e568df38fb6fdf0ceb65f735d6/crates/codegen/xai-grok-tools/src/implementations/opencode/edit/mod.rs#L333-L472)。

这两个兼容实现同样没有 prior-Read revision、共享文件锁或原子替换；它们的价值主要是匹配特定模型的工具训练分布，而不是提供更强的文件系统保证。

### 2. Pi

#### 是否有 Edit

有，默认工具集同时包含 `read`、`write`、`edit`、`bash`。当前 schema 已从早期的单个 old/new 演进为：

```text
path: string
edits: Array<{
  oldText: string
  newText: string
}>
```

`edits` 必须非空；每个 `oldText` 都在同一个原始文件上匹配，而不是在前一项的结果上继续匹配。工具提示要求多个相距较远的改动放进同一次调用，相邻或重叠改动合并成一个 block。[schema 与模型指导](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L34-L64)。

Pi 曾同时支持单编辑和多编辑 schema，但模型会混用两种形状而反复产生非法调用，最终只保留 `edits[]`；恢复旧 session 时，`prepareArguments` 仍把顶层 `oldText`/`newText` 折入数组，也容忍部分模型把数组 double-encode 成 JSON string。[兼容转换](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L105-L135)说明 schema 简洁本身也是可靠性功能。

#### 功能与算法

一次调用的所有替换先完成验证，再倒序应用并只写一次：

- 禁止空 `oldText`，因此 Edit 不负责创建；
- 每项必须唯一，拒绝 not-found、重复；整批最终内容无变化时失败，但没有逐项 no-op 校验；
- 拒绝不同 edit 的重叠范围；
- exact 失败后，回退到 NFKC、逐行尾空白、smart quotes、dash 和特殊空格归一化；
- 保留 UTF-8 BOM，并把普通 LF/CRLF 文件恢复为检测到的行尾风格；
- fuzzy 命中时只重写实际触及的行，未触及行从原始内容拷回，避免整文件被归一化；
- 返回显示用 diff、标准 unified patch 和首个变化行；参数完整时 TUI 在执行前异步预览 diff。

核心算法见 [`edit-diff.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit-diff.ts#L295-L374)，执行路径见 [`edit.ts`](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L298-L367)。值得注意的是模型描述说 “exact”，但实现有 fuzzy fallback；这改善复制文本时的成功率，也意味着人类不能只根据 prompt 推断实际匹配边界。

Pi 将 `readFile`、`writeFile`、`access` 抽成可注入 operations，同一协议可接 SSH、VM 等后端。所有 `write`/`edit` 还共用按现存文件 `realpath` 归并的进程内 mutation queue：同真实文件串行，不同文件仍可并行；Abort 只有在底层 I/O settled 后才释放队列，避免已报告取消的写与下一次写交错。[operations](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/edit.ts#L81-L103)与[mutation queue](https://github.com/earendil-works/pi/blob/b1efcf7d7c5d7394fbb12ede0174e04d39ee7004/packages/coding-agent/src/core/tools/file-mutation-queue.ts#L1-L60)体现了 Pi 的轻量、可嵌入取向。

边界是：队列只协调参与它的 Pi 工具，不包含 Bash 和外部编辑器；没有 mtime/hash/expected bytes，也没有 temp + fsync + rename；默认路径不限制在 cwd 内。fuzzy fallback 会归一化被触及的完整行，仍可能改变这些行上不在 oldText 中的尾空白或 Unicode 形式。混合行尾会按首先检测到的风格整体统一，裸 CR 会变成 LF；UTF-8 解码是有损的，也没有 NUL/binary guard。可注入 I/O 便于远程后端，但工具外围没有跟上：mutation queue 的 `realpath` 与 TUI 的执行前 diff 预览都直接调用本机 `node:fs`，绕过了 `operations`，抽象并不彻底。

### 3. Claude Code

#### 是否有 Edit

有 `Edit`，并为 `.ipynb` 单独提供 `NotebookEdit`。普通 Edit 的 schema 是：

```text
file_path: string  # schema 文案要求 absolute，运行时也接受相对路径和 ~
old_string: string
new_string: string
replace_all: boolean = false
```

Claude Code 的 `Write` 提示直接要求修改已有文件时优先 Edit，因为 Edit “只发送 diff”；Write 留给新建或完整重写。[Write 工具提示](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileWriteTool/prompt.ts#L10-L17)给出了设计 Edit 的产品级理由：压缩模型输出，同时避免重传未改区域。

默认要求 `old_string` 唯一；多次出现时让模型增加上下文或显式 `replace_all`。工具提示明确提醒不要把 Read 的行号前缀复制进字符串。虽然 schema 文案要求绝对路径，运行时的 `expandPath` 也接受相对路径和 `~`，所以描述契约与实现边界并不完全一致。[schema](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/types.ts#L5-L34)、[prompt](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/prompt.ts#L4-L27)与[路径展开](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/path.ts#L8-L84)表现出它针对 Claude 输出习惯做了细致约束，也暴露了接口漂移。

#### 强制先读与防陈旧

Claude Code 不只在 prompt 中建议 Read，而是在运行时强制：普通现存文件必须有会话 Read state，仅由系统自动注入的 partial view 不够；若当前 mtime 晚于读取时间则拒绝。实现还试图在 cache state 未记录 offset/limit 时用内容相同作为纯 touch 的回退，不过 FileRead 默认会记录 `offset=1`，普通完整读取通常也走不到这个回退。真正写入前又同步读取当前 metadata/content，检查后到落盘之间刻意不插入异步 yield，以缩小单一 JS 事件循环内的竞态窗口。[输入校验](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/FileEditTool.ts#L137-L361)与[提交前复核](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/FileEditTool.ts#L425-L491)是五个项目里最重的会话级保护。

空 `old_string` 是一个受限创建入口：目标不存在或现存文件空白时允许，非空文件会拒绝，避免借 Edit 隐式 whole-file overwrite。FileEdit 核心 matcher 以 exact 为先，失败只做直引号/curly quote 归一化，并把新字符串恢复成文件原有的 typography 风格；完整调用链在进入工具前还有一组固定的 desanitize 规则，用来反转 API 隐藏或缩写的少数 token，但仍不像 OpenCode V1 那样做任意缩进、锚点相似度回退。[quote 匹配](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L18-L135)与[输入还原](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L526-L657)。删除时 `new_string=""` 还有去掉紧随换行的便利语义，但这个特殊分支与 `replace_all` 组合存在缺陷：例如删除 `x\nx` 中的全部 `x`，末尾 occurrence 可能残留，结果文案却仍宣称全部替换成功。[删除实现](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L206-L228)。

#### 控制面与输出

Edit 复用 Claude Code 完整的 mutation 生命周期：路径/deny/UNC 与 symlink 权限检查、团队 memory secret 校验、可选 history、UTF-8/UTF-16LE 与主导行尾恢复、结构化 patch、可用时的 VS Code/LSP 通知、诊断清理和遥测，并在成功后更新 Read state，使下一次连续编辑基于新内容；它不自动运行 formatter。[写后集成与结果](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/FileEditTool.ts#L490-L593)。底层写入优先采用同目录临时文件、flush、保留 mode 后 rename；失败时会静默退化为直接覆盖，所以这只是 best-effort 原子替换，不是强保证。[写入实现](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/utils/file.ts#L369-L477)。

它仍不是跨写者 CAS：mtime/内容检查与最终写之间还有窗口；同步写路径提供进程内“无 await”顺序，不是内核事务。强制先 Read 还会增加工具调用成本，而且只开放 Edit 的路径策略仍可能被 Bash 绕过。另一个值得警惕的契约边界是：API 消息规范化会静默删除非 Markdown `new_string` 的逐行尾空白，实际写入不一定逐字等于模型参数。[输入规范化](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/FileEditTool/utils.ts#L526-L657)。

`NotebookEdit` 值得单列，因为 Notebook 不是普通 JSON 文本替换问题。它按真实 cell ID 或 FileRead 合成的 `cell-N` ID 执行 replace、insert、delete；修改 code cell 时清空 outputs 和 execution count，维护 nbformat 4.5+ cell ID，同时也要求 Read-before-Edit 与 mtime 新鲜度。[校验](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/NotebookEditTool/NotebookEditTool.ts#L176-L294)和[cell 操作](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/NotebookEditTool/NotebookEditTool.ts#L295-L453)说明结构化文件适合领域专用 Edit，而不是强行复用文本替换。不过它只在前置校验时检查陈旧，权限/历史等待后没有普通 Edit 的最终复核，而且会重新 stringify 整个 notebook；单 cell 编辑仍可能覆盖并发变化并制造较大的格式 diff。其 [prompt 仍描述](https://github.com/yasasbanukaofficial/claude-code/blob/a371abbe75ffa0d0a3c92290e2bbf56a7ef54367/src/tools/NotebookEditTool/prompt.ts#L1-L8)已不在 schema 中的 `cell_number`，也是文案和实现漂移的例子。

### 4. OpenCode

OpenCode 仓库同时存在两代实现：`packages/opencode` 的 V1/legacy 和 `packages/core` 的 Location-scoped V2 新架构。两者同名但语义不能混写。V1 会按模型在 `apply_patch` 与 `edit` + `write` 之间二选一；[V2 built-ins](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/builtins.ts#L20-L42)当前同时注册三者，再按 permission 过滤。

#### 为什么同时有 `edit` 与 `apply_patch`

V1 registry 按模型选择：现代非 OSS、非 GPT-4 的 GPT 模型看到 `apply_patch`，其他模型看到 `edit` + `write`，不会把三套重叠接口全塞给同一个模型。[工具选择](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/registry.ts#L286-L297)。这直接证明两种接口主要服务不同模型能力：old/new 更容易生成，Patch 更适合多文件和 GPT 的训练分布。

#### V1 `edit`：宽松匹配与厚集成

输入是 `filePath`、`oldString`、`newString`、可选 `replaceAll`。单文件 semaphore 覆盖 read-compute-write；现存文件禁止空 old，目标不存在时空 old 可创建。它保留 BOM 和原文件 LF/CRLF，先生成 diff 请求 `edit` 权限，再落盘、运行 formatter，基于 formatter 后结果重算最终 diff，发布 file/watcher event，触发 LSP 并把诊断返回模型。[执行生命周期](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/edit.ts#L35-L215)。

匹配策略依次尝试 exact、逐行 trim、首尾行 block anchor + Levenshtein 相似度、空白归一化、缩进弹性、转义归一化、边界 trim、context-aware 和多 occurrence。replacer 选出具体实际字符串后，外层默认要求该字符串唯一，`replaceAll` 才全改；但 block-anchor fuzzy 会在多个候选中取最高分，同分时保留第一个，并不要求原始 fuzzy 候选全局唯一。另有“命中跨度相对 oldString 大太多”保护，避免一个短输入通过 fuzzy 吞掉大块内容。[replacer 实现](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/edit.ts#L217-L736)。

这套策略对模型少量抄错很宽容，但风险也最大：所谓“exact edit”的 prompt 与实际运行边界相差很远，0.65 相似度的 block anchor 可能接受已经显著变化的中间区域。权限 diff 能让有人类审批的场景兜底；自动批准时，宽松 fallback 更应谨慎。V1 的 [prompt 还声称修改前必须 Read](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/edit.txt#L1-L8)，但对应 FileTime/read-state 检查已经从当前实现删除；这是“提示契约与运行时漂移”的另一个反例。

V1 `apply_patch` 使用 `{ patchText }` JSON 包裹与 Codex 相近的 Patch 语言，支持一次调用多文件 add/delete/update/move。匹配按 exact、`trimEnd`、`trim`、Unicode 标点归一逐级回退；所有变更先计算并一次审批，之后逐文件落盘、formatter、事件与 LSP。Add 和 Move destination 会覆盖已有文件，提交不回滚也没有 expected-bytes CAS；formatter 发生在批准的 diff 之后，最终实际变更还可能大于审批预览。Move destination 虽会进入 metadata，并可能单独触发外部目录授权，却没有加入 `edit` permission 的 path patterns，内部目标的审批范围也不完整。[工具执行](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/tool/apply_patch.ts#L18-L278)与[Patch 匹配](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/opencode/src/patch/index.ts#L430-L506)展示了这种“Patch 表达力 + V1 厚集成”的组合。

#### V2 `edit`：exact + expected bytes

V2 保留同样的单个 old/new + `replaceAll` 形状，但不做 V1 的相似度 fuzzy，源码把 V1 fuzzy、formatter、watcher、snapshot/undo、LSP 都列为后续 TODO。它：

- 通过 `LocationMutation` canonicalize 路径，防相对路径/工作区 symlink 越界；显式外部绝对路径先申请 `external_directory`；
- 禁止空 old 和 no-op，要求唯一或显式 replace-all；
- 匹配前剥离 UTF-8 BOM，并把 `oldString` 和 `newString` 一起换算成文件检测到的行尾，写回时再补上 BOM；
- 返回 replacements、unified patch、additions/deletions，并给模型一个有限 old/new diff preview；
- 权限批准后才读取 source bytes；提交时在 canonical-path 进程内锁中比较当前 bytes 与 expected bytes，不同即 stale。

需要说清的是，V2 的 exact 不是裸字节 exact，而是**剥掉 BOM、把 old/new 换算到文件行尾之后**的 exact：`detectLineEnding` 只要文件里出现过一次 `\r\n` 就判定为 CRLF，`convertToLineEnding` 先把输入统一成 LF 再按需转回 CRLF。[归一化辅助函数](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/edit.ts#L42-L53)与[匹配前的换算](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/edit.ts#L161-L165)。这层换算方向确定、范围可枚举，而且只改写命中的 span，未命中区域仍是原字节，因此它同时解决了“Read 输出被剥掉 `\r`、模型交不出 CRLF 原文”和“不要顺手归一化整份文件”两个问题——这是五个项目里对该问题最克制的处理。代价是判定很粗：文件里只要出现过一次 `\r\n` 就整体按 CRLF 换算，混合行尾文件中纯 LF 的片段因此匹配不到，只能 fail closed 让模型重读。

执行见 [`V2 edit.ts`](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/edit.ts#L22-L223)，进程内 keyed lock 与 expected-bytes 条件写见 [`file-mutation.ts`](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/file-mutation.ts#L54-L171)。比较与普通写入只对协作使用该锁的 OpenCode mutation 连续，外部进程和 Bash 仍可在两者之间竞争。这是“先把可解释的 exact 与进程内并发语义做清楚，再逐步补 UX”的取向。

V2 `apply_patch` 支持一次 add/update/delete：先解析和 resolve 所有目标，批量授权，再 preflight 读取；Add 用 create-only `wx`，Update 用 expected bytes。提交仍按顺序进行，后续失败不会回滚先前成功项，Delete 也没有 expected-content CAS，Move 尚未支持。[V2 Patch](https://github.com/anomalyco/opencode/blob/e23586af2623f1bc2e8e6965d2d7acf7bd03d5c3/packages/core/src/tool/apply-patch.ts#L17-L218)。所以“批量 preflight”不应被写成“多文件事务”。

### 5. Codex

#### 没有字符串型 Edit

Codex 不注册 `edit`/`edit_file`；[在存在 environment 且模型 metadata 声明 `apply_patch_tool_type` 时](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/spec_plan.rs#L1090-L1110)，它注册自由格式 `apply_patch`，这是当前唯一专用文件修改工具。schema 不是 JSON old/new，而是受 Lark grammar 约束的文本：

```text
*** Begin Patch
*** Add File: path
+new content
*** Update File: old-path
*** Move to: new-path
@@ optional context
-old
+new
*** Delete File: path
*** End Patch
```

工具定义明确说它“用于编辑文件且不要包 JSON”，并把 freeform custom tool 标为适合 GPT-5；provider 侧 Lark grammar 支持多 hunk add/delete/update/move。[工具 spec](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/handlers/apply_patch_spec.rs#L5-L27)与[grammar](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/handlers/apply_patch.lark#L1-L19)。旧 JSON/function 调用面后来被[删除](https://github.com/openai/codex/commit/e783341b705721728a8fa422416c10c3a09c7716)，避免模型与测试同时面对两种等价协议；Patch 由内置 Rust parser 执行，也不依赖系统安装的 `patch(1)`。

这是一条重要反例：需要专用局部编辑协议，不代表一定需要字符串型 Edit。Add File 已覆盖新建，Update 适合普通修改，多文件共享一个 parser 和权限入口；代价是模型必须稳定生成 Patch 语言。

#### 功能与边界

执行前会解析整份 Patch，对 Update/Delete 读取旧内容，对所有 Update hunk 计算新内容和 unified diff，并拒绝多个 operation 使用同一个 source path；然后才根据完整变更集合做安全分类、审批和 sandbox 执行。[预验证](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/apply-patch/src/invocation.rs#L200-L280)与[handler](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/core/src/tools/handlers/apply_patch.rs#L359-L447)体现了“先理解变更，再决定能否执行”。Move destination 之间或 destination 与其他 source 的冲突并未被同一规则完全覆盖，仍可能进入顺序执行后部分失败。

上下文定位依次尝试 exact、忽略行尾空白、两侧 trim、Unicode 标点/特殊空格归一化；EOF anchor 优先从文件末尾找。[`seek_sequence`](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/apply-patch/src/seek_sequence.rs#L1-L115)。即便模型以受限的 `apply_patch <<'PATCH' ...` shell 形式调用，Codex 也会识别并路由到同一 Patch 审批/沙箱链，而不是当任意 Bash 执行。

Patch 的重要限制是：

- 实际文件操作按 file action 顺序提交，失败不回滚，返回值会携带已提交 delta；
- Add 可覆盖已有目标，而不是 create-only；
- Move 是先写目标再删源，删源失败可能同时留下两份；
- Update 的验证结果到实际落盘间没有 expected-bytes CAS；审批后运行时会重新读取并重算 Patch，若外部变化没有破坏 hunk，它可能基于新文件继续应用，最终结果也可能不同于审批时的预览；
- 最终是文本整文件重写，不表达二进制增量、chmod 等 metadata。

顺序提交和 Move 过程见 [`apply-patch/src/lib.rs`](https://github.com/openai/codex/blob/5bc8da6d78fe32343dc51eaf73b96fd288ae0e87/codex-rs/apply-patch/src/lib.rs#L438-L663)。工具外层还提供 writable-root safety classification、平台 sandbox、hook、流式 diff event 和远端文件系统，但这些是 Codex 控制面能力，不是 Patch grammar 自带的原子性。

## 功能对比

| 能力 | Grok `search_replace` / Hashline | Pi | Claude Code | OpenCode V1 / V2 | Codex |
| --- | --- | --- | --- | --- | --- |
| 普通接口 | 单 old/new；Hashline 可批量 | `edits[]` 批量 old/new | 单 old/new | 单 old/new | 多文件 Patch |
| 默认唯一匹配 | 是 | 每项必须唯一 | 是 | V1 block fuzzy 可择优；V2 是 | hunk 取首个上下文候选 |
| 全部替换 | `replace_all` | 无直接开关 | `replace_all` | `replaceAll` | 多个 hunk/上下文 |
| 同调用多处/多文件 | Search 可改同字面量；Hashline 多组；Patch 多文件 | 同文件多组 | `replace_all` 可改同字面量；不可多组/多文件 | Edit 可改同字面量；Patch 多文件 | 多文件 |
| 创建 | `search_replace` 空 old；Hashline write | 否 | 空 old 受限创建 | V1 空 old；V2 Edit 否；Patch Add | Patch Add |
| 模糊回退 | search 可选 Unicode；Hash anchor recovery | NFKC/尾空白/Unicode | quote 归一 + 固定 desanitize | V1 多层 fuzzy；V2 仅 BOM/行尾换算后 exact | hunk trim/Unicode |
| CRLF/BOM | Search 保持 LF 或统一为 CRLF；Hashline 转 LF；BOM 无专门保护 | BOM、普通 LF/CRLF；混合行尾会统一 | UTF-8/UTF-16LE、主导 LF/CRLF | V1 Edit 保留；V2 剥 BOM 匹配、old/new 按文件行尾换算；Patch 可能混合行尾 | 默认转 LF；实验特性可保留行尾，BOM 无专门处理 |
| 防陈旧 | old/anchor 前置条件 | old 前置条件 | prior Read + mtime/content | V1 Edit: old；V2 Edit/Patch Update: expected bytes，Add: `wx`，Delete: 无 | hunk 前置条件，无 CAS |
| 同文件进程内串行 | 无共享路径锁 | realpath queue | 最终段无 `await`，无路径锁 | V1 仅 Edit semaphore；V2 每目标 canonical lock | 无路径锁/CAS |
| Diff/UI | context；Search 有 `FileWritten` event | 预览 + diff + patch | structured patch + IDE | V1/V2 diff | diff event + A/M/D summary |
| formatter/LSP/history | Search 接 hunk/rewind；无工具内 formatter | 扩展 hook；无内建 LSP | 无 formatter；可选 history/LSP | V1 有；V2 TODO | 通用事件/hook，无工具内 formatter |

## 设计取舍

### Exact 与 fuzzy

Exact 的优点是可解释、可测试：工具改动的就是模型提交的前置条件。缺点是 Read 格式、CRLF、尾空白、smart quotes 等微小差异会导致重试。

Fuzzy 能提高一次成功率，却会扩大工具实际获准修改的范围。Grok 的 Unicode offset-map 会把有限归一化命中映射回原始字节，并拒绝无法完整回映的候选；Pi 则在归一化文本上替换，只回填未触及的原始行块，因此触及行可能附带发生 NFKC、标点或尾空白变化。OpenCode V1 的 block similarity 更激进，还需要额外的跨度保护和审批 diff。OpenCode V2 则划出了另一端的下限：只做 BOM 与行尾这两项方向确定、范围可枚举的换算，不引入任何相似度判断，命中范围因此仍然等于模型提交的字面量。对没有执行前审批 UI 的小型 Agent，exact-first/fail-closed 更合适，而“允许哪几项换算”必须是可枚举、可写进工具描述的短清单，不是一串启发式。

### 单替换、批量替换与 Patch

- 单 old/new：schema 最小，模型成功率高；多个调用会重复 I/O，也不能逻辑原子地验证一组改动。
- 同文件 `edits[]`：一次读、全量验证、一次写；必须定义所有匹配基于原始还是逐步结果，并处理重叠。
- Patch：多文件表达力最强，但 parser、错误恢复、partial commit 和模型适配成本最高。

Pi 的演进还说明，不要同时在一个 schema 中提供顶层 old/new 与 `edits[]` 两种等价形状；模型会混用。应选一个稳定接口，兼容只放在运行时输入迁移层。

### “验证后写”与真正原子性

必须区分：

1. **逻辑全验证**：在内存中先确认所有替换可应用；
2. **单文件可见性原子**：并发观察者只看到完整旧版或新版，通常由同文件系统的 temp + rename 提供；
3. **崩溃持久性**：成功返回后即使掉电，文件和目录项仍可靠，通常还需 file/directory `fsync`；
4. **跨写者并发 CAS**：只有文件仍是指定 revision/bytes 才提交；
5. **多文件事务**：全部成功或全部回滚。

Pi/Hashline 批量 Edit 做到第 1 项；Claude 的底层写入尽力采用 temp + rename、但可静默退化，只能说尝试第 2 项，也没有完整的第 3/4 项；OpenCode V2 `writeIfUnchanged` 是进程内锁保护的条件写，并非跨写者 CAS。上述具备多文件 Patch 的实现（Grok 兼容 preset、OpenCode、Codex）都没有第 5 项。报告和工具错误不能把其中一层包装成另一层。

## 对 nanoPyCodeAgent 的设计建议

### 当前约束

nanoPyCodeAgent 当前只暴露 `read`、`write`、`bash`，默认模型是 Claude Sonnet 4.6；工具调用由单线程循环按模型返回顺序执行。[系统提示与工具集](../../src/nanopycodeagent/agent.py#L37-L50)和[顺序 dispatch](../../src/nanopycodeagent/agent.py#L169-L179)意味着目前没有同一进程内的并行 lost-update 问题。

现有 `write` 是明确的 last-writer-wins：直接 `Path.write_bytes`，不要求先 Read、不检查 revision、没有 atomic replace，并跟随指向普通文件的 symlink。[`write_tool.py`](../../src/nanopycodeagent/write_tool.py#L89-L153)。`read` 最多整文件加载 10 MB，并在展示时把 CRLF 的 `\r` 去掉。[大小上限](../../src/nanopycodeagent/read_tool.py#L13-L23)与[换行视图](../../src/nanopycodeagent/read_tool.py#L117-L129)意味着模型复制出的多行旧文本通常只含 LF。新 Edit 必须与这些真实语义相容，不能突然宣称一套 Bash 可以绕过、Write 也没有的安全边界。

### 结论：现在增加一个薄、精确、单替换 Edit

`write` 已解决新建文件和整文件重写，但普通代码修改仍要重发完整文件或退回 Bash。此时 Edit 的 token、未触及内容保留和 old-text 前置条件都已有直接收益，值得作为第四个内置工具。

首版建议采用：

```text
Edit(
  path: string,
  old_text: string,
  new_text: string,
  replace_all: boolean = false,
)
```

选择 `path` 是为了与本项目 Read/Write 一致；选择 snake_case 是为了与 Python 和当前 schema 风格一致。虽然 Claude Code 使用 `old_string`，清晰的工具描述足以教会默认 Claude 模型，没必要为了复制某一个产品而让本项目字段命名分裂。

首版的精确契约应是：

1. 只编辑已经存在的 UTF-8 普通文件；missing、目录、FIFO、device 失败。创建和 whole-file overwrite 继续用 `write`。
2. `old_text` 不得为空，`old_text == new_text` 失败；`new_text=""` 合法，表示精确删除，不附带“顺手删除下一换行”等隐藏语义。
3. 先做 exact literal match（第 6 条允许在其后追加一次、且仅一次 CRLF 重试）。命中 0 处失败；多于 1 处且 `replace_all=false` 失败并报告匹配数；`replace_all=true` 替换所有非重叠匹配并返回实际次数。
4. 不做 regex，不做 trim、缩进、相似度或 Unicode fuzzy。允许的输入换算只有第 5、6 条的 BOM 与行尾两项，它们方向确定、范围可枚举，并且必须如实写进工具描述——不能像 OpenCode V1 和 Pi 那样，对模型宣称 exact，实际匹配边界却更宽。错误提示让模型 Read 后扩大/修正上下文。首版没有执行前 diff 审批，宁可多一次重试，也不要静默扩大授权的修改范围。
5. 严格 UTF-8 解码，拒绝非法 UTF-8 和含 NUL 的文件：`read` 对非法字节使用 replacement character 便于查看，Edit 若照此 round-trip 会永久损坏原字节。UTF-8 BOM 在匹配前剥离、写回时原样补回。这一条不能省：`read` 目前不剥 U+FEFF，模型看到的首行带一个不可见字符，不剥就会让针对首行的 `old_text` 神秘失配。Pi 和 OpenCode V2 都是这么处理的。
6. 兼容 Read 的换行视图，采用 OpenCode V2 的思路做**一次方向确定的换算**，而不是并列多个候选：先用 `old_text` 原样做 raw exact；只有当匹配数为 0、文件含 `\r\n`、且 `old_text` 含 `\n` 而不含 `\r` 时，才用 `old_text` 的 LF→CRLF 形式重试一次，此时写入的也换成 `new_text` 的 LF→CRLF 形式。两趟之间不取并集：唯一性判定和 `replace_all` 计数都发生在实际命中的那一趟里，因此不存在候选去重和跨编码 span 重叠的歧义（取并集就会出现这种歧义：内容 `"a\r\na\na"` 配 `old_text="a\na"`，两种编码分别命中 `[3,6)` 和 `[0,4)`，彼此重叠）。`old_text` 显式含 `\r` 时只做 raw exact，视为模型在表达原字节。两趟都只改写命中的 span，未触及区域始终保持原字节。因为第二趟只在第一趟颗粒无收时才跑，一次调用只会命中一种行尾风格，混合行尾文件里另一种风格的片段这次匹配不到——这是有意的 fail closed，错误信息要讲明 CRLF 重试已经试过。这条限制只影响多行 `old_text`：不含 `\n` 的单行 `old_text` 与行尾无关，第一趟就能跨两种风格全部命中，也不会触发重试。
7. 文件大小沿用 `MAX_READ_BYTES` 10 MB 上限，因为实现需要整文件 read-compute-write；错误明确建议大文件用 Bash/专用脚本。
8. 路径展开、普通文件检查、symlink 行为、错误格式与 `read`/`write` 对齐。首版仍直接写回并明确不提供 mtime/CAS/atomic replace。

### 不建议首版加入的能力

- **不强制 prior Read。** 当前会话没有 read revision registry，Read 还可能只是窗口；old_text 的唯一匹配已经是局部前置条件。强行记录 mtime 会增加状态，却仍不能消除 TOCTOU。
- **不做 `edits[]` 批量。** 当前 loop 会顺序执行多个 tool call；先用单替换取得模型可靠性和小实现。只有工具往返延迟或一文件多点修改成为实测瓶颈时，再像 Pi 一样升级，而且只能保留一种公开 schema。
- **不做 `apply_patch`。** Parser、多文件 partial commit、move/delete、权限目标集合都会显著扩大 nano agent 的核心。默认 Claude 模型也更熟悉 old/new Edit。
- **不做 formatter、LSP、history、审批和 workspace sandbox 的局部版本。** 这些是整个 mutation/exec 控制面的能力。只在 Edit 上加路径保护会被 Bash 绕过。
- **不先做 per-file queue。** 当前工具执行是单线程的；等真正引入并行 tool calls 时，再以 canonical/real path 为 key，让 Read-Compute-Write 整段进入共享 mutation queue。

### 模型提示、结果与终端展示

工具描述应直接告诉模型：

- 普通局部修改优先 Edit；新文件或整文件重写用 Write；批量机械变换用 Bash；
- `old_text` 必须与文件内容逐字一致且默认唯一，通常取 2–4 行足够，不要包含 Read 的行号前缀；唯一的例外是行尾和 BOM——Read 显示的是 LF，CRLF 文件由工具自行换算，不必也不要自己拼 `\r`；
- 不匹配时先 Read 最新内容，不要反复提交同一调用；
- `replace_all` 只用于明确要修改所有相同字面量的场景。

成功结果保持精简，例如：

```text
[edited src/app.py: replaced 1 occurrence, lines 42-44]
```

调用在终端显示 `[edit] path` 和折叠后的 old/new 小型 diff；不要把完整大字符串再次塞进 tool result，因为它已经存在于 assistant 的 tool input 中。若生成 unified diff，应设置与 Bash/Read 类似的硬上限并在截断时明确标记。

错误应具备恢复信息：not-found 建议重新 Read；duplicate 返回匹配数并建议增加上下文或显式 `replace_all`；invalid UTF-8、oversize、non-regular file 分别说明为何不能安全 round-trip，而不是统一成“edit failed”。

### 建议测试矩阵

首版至少覆盖：

- 唯一替换、删除、Unicode、空文件/no-op；
- not-found、重复匹配、`replace_all` 及返回计数；
- LF、CRLF、无末尾换行、混合行尾的未触及内容不变；
- CRLF 文件里 LF 形式的多行 `old_text` 能命中并按 CRLF 写回；混合行尾文件里一次调用只命中一种风格、另一种 fail closed；单行 `old_text` 跨两种风格全部命中且不触发重试；显式含 `\r` 的 `old_text` 只走 raw exact；两趟各自的 `replace_all` 计数正确；
- UTF-8 BOM 在匹配前剥离、写回时补回，针对首行的 `old_text` 能命中；非法 UTF-8 和 NUL 拒绝；
- missing、目录、FIFO/device、超过大小上限；
- `~`、相对/绝对路径、symlink 与 Write 一致；
- terminal preview 折叠，tool result 正确设置 `is_error`；
- 同一模型回复中的多个 Edit 按顺序看到前一次结果。

### 后续演进条件

当产品引入并行调用、审批 UI、undo、远程 FS 或受限模式时，再建立 Write/Edit/Patch 共用的 mutation core：canonical path、统一权限、expected digest、per-file queue、尽力 atomic replace、mode/BOM/行尾策略、before/after event 与 bounded diff。Bash 同时进入同一个 OS/容器/VM 文件系统边界，否则控制面仍可绕过。

最终建议可以概括为：

> nanoPyCodeAgent 现在需要的是一个“精确失败、语义诚实”的薄 Edit，而不是把成熟 Agent 的完整控制面压进一个 Python 文件。先用唯一 old-text 前置条件解决局部修改的 token 与误覆盖问题；等架构真的出现并发、审批和远端需求，再升级 mutation core，而不是提前模拟安全性。
