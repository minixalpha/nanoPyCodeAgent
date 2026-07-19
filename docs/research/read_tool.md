# 五个 Agent 项目的读文件工具对比

> 本文明确指定使用中文编写和维护。

## 研究范围

本文只统计**模型可以直接调用的内置工具**，不把普通内部函数、测试辅助函数或面向 GUI 客户端的 RPC 混作 Agent 工具。结论基于当前目录中的以下检出版本：

| 项目 | 当前提交 | 提交日期 |
| --- | --- | --- |
| `grok-build` | `c68e39f` | 2026-07-16 |
| `pi` | `5e336cfa` | 2026-07-15 |
| `claude-code` | `a371abb` | 2026-04-05 |
| `opencode` | `fab213312` | 2026-07-18 |
| `codex` | `1bbdb32789` | 2026-07-15 |

## 先看结论

| 项目 | 模型侧工具名 | 核心定位 | 文本分段 | 非文本文件 |
| --- | --- | --- | --- | --- |
| Grok | `read_file` | 功能完整的语义化文件阅读器 | `offset`、`limit`，默认最多 1000 行、25000 token | 图片、PDF、PPTX；`.ipynb` 按文本读取 |
| Pi | `read` | 简洁、可嵌入和可替换后端的阅读器 | `offset`、`limit`，最多 2000 行或 50 KiB | 图片 |
| Claude Code | `Read` | 与权限、上下文、技能系统深度集成的阅读器 | `offset`、`limit`，文件大小和 token 双重保护 | 图片、PDF、Jupyter Notebook |
| OpenCode | `read` | 文件、图片和目录共用的 Location-scoped 结构化阅读器 | `offset`、`limit`；大文件或显式分页时最多 2000 行或 50 KiB | JPEG、PNG、GIF、WebP；目录列表 |
| Codex | **没有专用文本读工具**；通常用 `exec_command`，旧配置用 `shell_command`；图片用 `view_image` | 复用 shell 生态，把安全、会话和输出控制放在命令执行层 | 由 `sed`、`rg`、`head` 等命令自行实现 | `view_image` 支持图片；PDF/Notebook 没有专用读取分支 |

最重要的区别是：Grok、Pi、Claude Code、OpenCode 把“读文件”建模为一个明确、只读、带结构化参数的操作；Codex 没有为文本另建一层抽象，而是让模型通过通用命令执行工具调用 `rg`、`sed`、`cat` 等程序。

## 调用接口与模型可见返回格式

这里需要区分两层：工具实现内部可以返回结构体或联合类型，但模型最终可能只看到其中一段经过排版的文本。下表中的“返回格式”特指模型上下文里实际可见的结果，而不是工具实现内部的类型。

| 项目 | 模型调用接口 | 模型可见的文本或内容 | 返回格式判断 |
| --- | --- | --- | --- |
| Grok | `read_file({ target_file, offset?, limit?, pages?, format? })` | 文本取自内部 `FileContent.content`；首个可见行和每个整十行添加 `行号→` 锚点。未格式化原文另存于 `raw_output`，但不会作为普通文本结果发给模型 | 格式化文本；图片和 PDF 页面使用多模态内容块 |
| Pi | `read({ path, offset?, limit? })` | 正文保持原样，不自动添加行号；发生截断或显式分页时，末尾追加当前范围和下一次 `offset` 提示 | 纯文本为主；图片使用独立 image content block |
| Claude Code | `Read({ file_path, offset?, limit?, pages? })` | 内部结构化结果在进入模型前被转换为 `tool_result.content`，每一行添加 `行号→` 或 `行号<TAB>` 前缀，并可能附加 `<system-reminder>` | 格式化文本；图片、PDF 和 Notebook 使用专用内容块 |
| OpenCode 经典实现 | `read({ filePath, offset?, limit? })` | 返回一个 `output: string`，用 `<path>`、`<type>`、`<content>` 包裹，并给正文每行添加 `N: ` 前缀 | XML 风格的格式化文本 |
| OpenCode V2 | `read({ path, offset?, limit? })` | 返回 `FileSystem.Content`、`TextPage` 或 `ListPage` 结构化联合；正文位于 `content` 字段且不加行号，分页位置通过 `offset`、`truncated`、`next` 表达 | 结构化 JSON；图片额外使用 file content block |
| Codex | 没有专用文本读取工具；通常调用 `exec_command({ cmd, ... })` | 工具结果是包含 `output`、`exit_code`、`session_id` 等字段的对象；`output` 是否为原文、带行号文本或其他格式完全取决于执行的命令 | 结构化命令结果，文件正文格式不固定 |

因此，如果把“纯文本”定义为“不添加行号、标签或 JSON 外壳的文件正文”，Pi 最接近纯文本；Claude Code、Grok 和经典 OpenCode 都会主动增加位置或结构标记；OpenCode V2 保留原始正文，但把它放进结构化结果；Codex 则把格式选择交给具体 shell 命令。

相关实现：Grok 的参数和文本锚点见 [`read_file/mod.rs`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/grok_build/read_file/mod.rs#L103) 与 [`output.rs`](../../references/grok-build/crates/codegen/xai-grok-tools/src/types/output.rs#L698)；Pi 见 [`read.ts`](../../references/pi/packages/coding-agent/src/core/tools/read.ts#L20)；Claude Code 见 [`FileReadTool.ts`](../../references/claude-code/src/tools/FileReadTool/FileReadTool.ts#L227) 和 [`file.ts`](../../references/claude-code/src/utils/file.ts#L290)；OpenCode 经典实现见 [`packages/opencode/src/tool/read.ts`](../../references/opencode/packages/opencode/src/tool/read.ts#L338)，V2 见 [`packages/core/src/tool/read.ts`](../../references/opencode/packages/core/src/tool/read.ts#L16)；Codex 的命令结果 schema 见 [`shell_spec.rs`](../../references/codex/codex-rs/core/src/tools/handlers/shell_spec.rs#L264)。

## 1. Grok：`read_file`

### 工具入口与参数

- 工具 ID 明确注册为 `read_file`，实现入口位于 [`grok_build/read_file/mod.rs`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/grok_build/read_file/mod.rs#L545)。
- 参数为：
  - `target_file`：工作区相对路径或绝对路径；
  - `offset`：起始行，支持正数、`0` 和负数；负数可从文件尾部反向定位；
  - `limit`：读取行数；
  - `pages`：PDF 页码或页范围；
  - `format`：PDF 的 `image` 或 `text` 输出方式。

### 文本读取

- 先把文件读成字节，再以 UTF-8 容错方式转换文本；已识别的二进制文件会被拒绝。
- 默认一次最多返回 1000 行；即使调用者传入更大的 `limit`，也会被配置上限截住。输出再受 25000 token 上限保护。
- 支持精确窗口读取；超限时会建议缩小 `offset`/`limit` 或改用搜索工具。若窗口只有一条超长行，还会建议用 shell 中的 `jq`、`cut` 等按字符提取。
- 实际文本格式不是每一行都加前缀：当前实现给首个可见行和每个整十行增加 `行号→` 锚点，以减少行号本身的 token 开销。
- 文本结果可以按约 4 KiB 的字符边界分块流式发送，但文件本身仍然是在分段前一次性读入内存。
- `SKILL.md` 是有意设置的例外：忽略传入的 `offset`/`limit`，并绕过普通行数和 token 上限，确保技能说明被完整加载。

相关实现：[`read_file/mod.rs:55`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/grok_build/read_file/mod.rs#L55)、[`read_file/mod.rs:150`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/grok_build/read_file/mod.rs#L150)、[`read_file/mod.rs:190`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/grok_build/read_file/mod.rs#L190)、[`read_file/mod.rs:442`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/grok_build/read_file/mod.rs#L442)。

### 图片和文档

- 图片按 magic bytes 判断，而不是只信扩展名。
- 图片会转成模型端可接受的 PNG/JPEG/WebP，并按尺寸、像素总数和载荷大小自动缩放压缩：默认最长边不超过 2000 px、总像素约不超过 1.05 Mpx、base64 载荷不超过 768 KiB。
- PDF 默认渲染为逐页图片，也可用 `format="text"` 提取文字。未指定页码时最多自动读取 10 页；显式指定时一次最多 20 页；文件上限为 50 MiB，处理超时为 60 秒。
- PPTX 会解压并抽取每张幻灯片的 DrawingML 文本和演讲者备注；压缩输入同样限制为 50 MiB，处理超时 60 秒。
- 工具描述声称支持 Jupyter Notebook，但当前 `read_file` 实现没有 Notebook 专用分支；`.ipynb` 实际走普通 JSON 文本路径。

相关实现：[`image.rs`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/read_file/image.rs#L25)、[`pdf.rs`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/read_file/pdf.rs#L12)、[`pptx.rs`](../../references/grok-build/crates/codegen/xai-grok-tools/src/implementations/read_file/pptx.rs#L26)。

### 与 Agent 框架的额外集成

- 可按配置拒绝读取 `.gitignore` 命中的文件，降低误读密钥、构建产物等内容的风险。
- 会尝试修正 Unicode 文件名，并为不存在的路径生成更友好的提示。
- 能返回“文件不存在”“是目录”“权限不足”等结构化错误，而不是只有一段混杂的 stderr。
- 可在读取文件时追加匹配的 Cursor rules，让路径相关规则随源码一起进入上下文。

## 2. Pi：`read`

### 工具入口与参数

- 模型侧名称为 `read`，定义位于 [`read.ts`](../../references/pi/packages/coding-agent/src/core/tools/read.ts#L203)。
- 参数很小：`path`、1-based `offset`、`limit`。
- 路径可为相对路径或绝对路径；路径层还处理 `~`、`@` 前缀、Unicode 空格，以及 macOS 截图名中的窄不换行空格、NFD 文件名和弯引号变体。

### 文本读取

- 默认把完整文件读入 `Buffer`，再选取行范围和裁剪输出。
- 返回内容最多 2000 行或 50 KiB，取先达到的限制，并且尽量不返回半行。
- 超限结果会明确给出当前行范围、文件总行数和下一次应使用的 `offset`。
- 若第一行本身超过 50 KiB，它不会悄悄截断该行，而是返回一条可执行的 `sed | head -c` 建议。
- `limit` 先选择用户需要的窗口，再应用统一的行数/字节上限；越界 `offset` 会返回包含总行数的错误。
- 与 Claude/Grok 不同，Pi 返回给模型的普通文本不自动添加行号；优点是 token 更省，代价是引用某一行时需要调用者自行建立位置锚点。

相关实现：[`read.ts:264`](../../references/pi/packages/coding-agent/src/core/tools/read.ts#L264)、[`truncate.ts`](../../references/pi/packages/coding-agent/src/core/tools/truncate.ts#L1)。

### 图片

- 支持 JPEG、PNG、GIF、WebP、BMP，并通过文件内容签名识别；扩展名伪装成图片不会误走图片分支。
- BMP 等模型接口不直接接受的格式会先转换为 PNG。
- 默认将图片缩到不超过 2000×2000，并把 base64 载荷控制在约 4.5 MiB 内；会尝试 PNG/JPEG、多档 JPEG 质量以及逐级缩小尺寸。
- 图片以真正的 image content block 附加给模型，而不是把 base64 文本塞进普通输出。模型不支持视觉输入时会明确说明图片被省略。

相关实现：[`mime.ts`](../../references/pi/packages/coding-agent/src/utils/mime.ts#L3)、[`image-process.ts`](../../references/pi/packages/coding-agent/src/utils/image-process.ts#L52)、[`image-resize-core.ts`](../../references/pi/packages/coding-agent/src/utils/image-resize-core.ts#L21)。

### 与 Agent 框架的额外集成

- `ReadOperations` 把 `readFile`、`access` 和 MIME 检测抽象成可替换操作，因此同一工具可以接到 SSH 或其他远程文件系统，而不改变模型协议。
- 支持 `AbortSignal`，长操作可以被会话取消。
- TUI 会按扩展名做语法高亮，并把 `SKILL.md`、`AGENTS.md`、`CLAUDE.md` 和 Pi 文档折叠成紧凑展示。这主要改善人类界面，不改变发给模型的文件正文。

## 3. Claude Code：`Read`

### 工具入口与参数

- 对模型暴露的名称为 `Read`，常量定义于 [`prompt.ts:5`](../../references/claude-code/src/tools/FileReadTool/prompt.ts#L5)，主实现为 [`FileReadTool.ts`](../../references/claude-code/src/tools/FileReadTool/FileReadTool.ts#L337)。
- 参数为绝对路径 `file_path`、1-based `offset`、`limit`，以及 PDF 专用 `pages`。
- 工具声明自身为只读、可并发执行，并把路径纳入权限匹配。

### 文本读取

- 返回内容使用类似 `cat -n` 的格式，每一行都有行号；默认是右对齐的 `行号→内容`，实验开关也可使用紧凑的 tab 分隔格式。
- 小于 10 MiB 的普通文件走一次读取的快速路径；大文件、管道和特殊文件走流式扫描。流式路径只保存请求窗口内的行，窗口外只计数不保留，因此读取 100 GiB 文件中的少量行不会让内存随文件大小增长。
- 两条路径都会去掉 UTF-8 BOM，并把 CRLF 规范化为 LF，也支持会话取消。
- 默认输出 token 上限为 25000。未显式传 `limit` 时，还会用 256 KiB 的总文件大小门槛提前拒绝大文件；显式提供 `limit` 后可读取大文件中的小窗口，最终仍受 token 上限约束。
- 工具提示中写着“默认最多 2000 行”，但当前核心 `call` 实现没有在缺省时把 `limit` 设为 2000，而是主要依赖 256 KiB/25000 token 两个上限；2000 行常量明确用于附件自动摄入路径。这是当前检出源码中的实现与提示差异。
- 相同文件、相同范围若修改时间未变化，后续读取会只返回“文件未变化”的短消息，复用对话中较早的内容，减少上下文和 prompt cache 成本。

相关实现：[`readFileInRange.ts`](../../references/claude-code/src/utils/readFileInRange.ts#L1)、[`limits.ts`](../../references/claude-code/src/tools/FileReadTool/limits.ts#L1)、[`FileReadTool.ts:489`](../../references/claude-code/src/tools/FileReadTool/FileReadTool.ts#L489)。

### 图片、PDF 和 Notebook

- 图片会读取为视觉内容，并根据模型 token 预算自动缩放、降采样或压缩；同时返回原始/显示尺寸，便于模型将坐标映射回原图。
- PDF 可直接作为 document block 发送，也可按 `pages` 抽取并渲染页面图片。超过 10 页必须指定页范围，一次最多 20 页；大于 3 MiB 或模型不原生支持 PDF 时会尝试页面抽取。
- `.ipynb` 有真正的 Notebook 分支：解析 cell，保留代码、Markdown、输出和可视化，再映射为结构化 tool result，而不是只把 Notebook 当作 JSON 文本。
- 常见二进制扩展会被拒绝，图片/PDF/SVG 等原生支持类型除外。

### 与 Agent 框架的额外集成

- 在读取前检查 `Read(...)` 允许/拒绝规则；UNC 路径的实际 I/O 延后到用户授权后，避免未经许可触发网络认证。
- 显式阻止 `/dev/zero`、`/dev/random`、stdin/tty 和标准文件描述符别名等可能无限输出或永久阻塞的设备文件。
- 路径不存在时，会尝试 macOS 截图空格变体、当前工作目录下的候选路径和相似文件名，并给出 `Did you mean ...`。
- 读取路径可以触发技能目录发现和条件技能激活；自动记忆文件还会附带新鲜度信息。
- 文本进入模型前会附加恶意代码分析提醒；读取事件同时进入 hook、监听器和遥测体系。

## 4. OpenCode：`read`

### 工具入口与分层

- 模型侧名称为 `read`，属于当前 V2 Location-scoped 内置工具，组装入口见 [`builtins.ts`](../../references/opencode/packages/core/src/tool/builtins.ts#L5)，工具定义见 [`read.ts`](../../references/opencode/packages/core/src/tool/read.ts#L16)。
- 参数为 `path`、1-based 正整数 `offset` 和正整数 `limit`；`limit` 在 schema 层就被限制为不超过 2000。`path` 可以指向文件或目录，因此当前实现不再暴露单独的 `list` 工具。
- 实现刻意拆成两层：`read.ts` 负责模型 schema、Location 路径、权限、文件/目录分派、图片归一化和错误投影；`read-filesystem.ts` 负责可独立测试的实际 I/O、分页、格式识别与结构化结果。
- 返回值不是预先排版的一段字符串，而是三种结构化结果的联合：普通文件的 `FileSystem.Content`、分页文本的 `TextPage`、目录的 `ListPage`。只有图片会另外产生原生 media content block。

### 文本读取

- 文件不超过 50 KiB 且调用者没有传 `offset`/`limit` 时，工具以 64 KiB 块读取完整文件并返回 UTF-8 `FileSystem.Content`。因此“小文件”默认完整返回，2000 行限制不作用于这个快速路径。
- 文件大于 50 KiB，或者调用者显式要求范围时，自动进入流式分页路径：默认从第 1 行开始，一次最多 2000 行且正文最多 50 KiB，先达到任一上限就停止读取，并返回 `truncated` 和下一次调用可用的 `next` 行号。
- 分页实现不会把整个大文件载入内存；它从文件头以 64 KiB 块扫描，保存的只有当前窗口。不过高位 `offset` 仍需要顺序扫描前面的内容，并没有使用字节索引或 seek。
- 单行最多保留 2000 个字符，后面追加明确的截断标记；CRLF 会在逐行处理时规范化，UTF-8 使用 fatal 解码，非法字节不会被替换成 `�` 后继续。
- 文本正文没有自动行号。小文件结果是包含 `content`、`encoding`、`mime` 的 `FileSystem.Content` JSON；分页结果才额外带 `offset`、`truncated`、`next`。位置锚点依赖分页元数据，而不是像 Claude Code 那样给每一行加前缀。
- 二进制判断结合扩展名、PDF magic bytes、NUL 字节和不可打印控制字符比例。PDF、Office、压缩包、可执行文件等会被拒绝；`.ipynb` 没有专用分支，会作为普通 UTF-8 JSON 文本读取。

相关实现：[`read-filesystem.ts:10`](../../references/opencode/packages/core/src/tool/read-filesystem.ts#L10)、[`read-filesystem.ts:166`](../../references/opencode/packages/core/src/tool/read-filesystem.ts#L166)、[`read-filesystem.ts:214`](../../references/opencode/packages/core/src/tool/read-filesystem.ts#L214)。

### 图片和目录

- 图片按内容签名识别 JPEG、PNG、GIF、WebP，优先级高于扩展名，因此伪装成 `.bin` 的合法图片仍能读取。原始媒体摄入上限为 20 MiB，并同时检查 `stat` 大小和实际流入字节数，避免读取期间文件增长绕过上限。
- 图片默认限制为 2000×2000 和 5 MiB base64 载荷。超限时通过 Photon/WASM 使用 Lanczos3 逐级缩小，并依次尝试 PNG 和多档 JPEG 质量；这些阈值及是否自动缩放可由 `attachments.image` 配置。若缩放器本身不可用，当前策略是保留原图，而不是让一次普通读取失败。
- 图片结果以“读取成功”文本加原生 `file` content block 返回，base64 不会伪装成普通文本。通用文本输出裁剪也不会裁掉 media block。
- 目录读取会解析每个直接子项的真实路径，只保留仍位于该目录内的普通文件和目录，因此会排除断链、特殊文件以及指向目录外部的符号链接。结果按“目录优先、同类按名称”排序，最多返回 2000 项，并用 `next` 延续分页。

相关实现：[`read-filesystem.ts:125`](../../references/opencode/packages/core/src/tool/read-filesystem.ts#L125)、[`image.ts:56`](../../references/opencode/packages/core/src/image.ts#L56)、[`photon.ts:17`](../../references/opencode/packages/core/src/image/photon.ts#L17)、[`read-filesystem.ts:325`](../../references/opencode/packages/core/src/tool/read-filesystem.ts#L325)。

### 路径、权限和输出生命周期

- 相对路径必须留在当前 Location 内，Location 内的绝对路径也可使用；相对 `..` 越界或通过符号链接逃逸会被拒绝。显式读取 Location 外绝对路径时，先要求 `external_directory` 授权，再要求目标资源的 `read` 授权。
- 工具自身在分页生产阶段控制文本窗口为 2000 行/50 KiB；Tool Registry 在结算阶段还有一层默认同为 2000 行/50 KiB 的通用模型输出保护。若完整结构化结果仍超限，会把完整内容保存到受管 `tool-output` 文件，给模型发送头尾预览和路径；留存期默认为 7 天。
- 预期错误并非全部原样暴露：二进制、媒体摄入上限、图片解码和尺寸错误保留具体消息；路径、普通文件系统、权限、非法 UTF-8、offset 越界等目前统一投影为 `Unable to read <path>`。这减少了内部错误泄露，但也让部分失败的恢复提示不如 Pi、Claude Code 具体。

相关实现：[`location-mutation.ts:120`](../../references/opencode/packages/core/src/location-mutation.ts#L120)、[`read.ts:53`](../../references/opencode/packages/core/src/tool/read.ts#L53)、[`read.ts:95`](../../references/opencode/packages/core/src/tool/read.ts#L95)、[`tool-output-store.ts:10`](../../references/opencode/packages/core/src/tool-output-store.ts#L10)、[`tool-output-store.ts:138`](../../references/opencode/packages/core/src/tool-output-store.ts#L138)。

## 5. Codex：没有专用文本 `read_file`

### 模型实际使用的工具

当前 Codex 工具注册表中没有普通文件读取器。源码中出现的 `read_file` 仅是 MCP 服务器示例/测试中的远端工具名，不是 Codex 自带的模型工具。默认工具计划在支持 Unified Exec 时暴露：

- `exec_command`：执行 shell 命令；
- `write_stdin`：继续与仍在运行的命令交互；
- `view_image`：读取并查看本地图片。

不支持 Unified Exec 或使用旧模型配置时，会改为 `shell_command`。注册逻辑见 [`spec_plan.rs:643`](../../references/codex/codex-rs/core/src/tools/spec_plan.rs#L643)，对应测试见 [`spec_plan_tests.rs:486`](../../references/codex/codex-rs/core/src/tools/spec_plan_tests.rs#L486)。

因此，Codex 读取文本通常是让 `exec_command` 执行：

```text
rg -n '^' path/to/file
sed -n '100,180p' path/to/file
head -n 200 path/to/file
```

### `exec_command` 在 Bash 之外增加了什么

- 结构化指定 `workdir`、shell、是否使用 login shell、是否分配 PTY、等待多久后返回、输出 token 预算等。
- 默认等待 10 秒、模型侧输出预算 10000 token；内部采集还有 1 MiB 上限。过长输出从中间裁剪并报告原始 token 数，保留开头和结尾通常比单纯 `head` 更利于看到命令结论或错误。
- 长命令不会阻塞整个 Agent：工具返回 `session_id`，模型可用 `write_stdin` 轮询、输入或继续收集输出。
- 命令在文件系统/网络沙箱中运行；需要越界访问时走结构化审批，并可记录受控的命令前缀规则。
- 支持本地或附加的远程环境，并返回 `exit_code`、耗时、会话 ID、是否截断等结构化元数据。

工具 schema 位于 [`shell_spec.rs`](../../references/codex/codex-rs/core/src/tools/handlers/shell_spec.rs#L17)，执行处理位于 [`exec_command.rs`](../../references/codex/codex-rs/core/src/tools/handlers/unified_exec/exec_command.rs#L80)，输出裁剪位于 [`context.rs`](../../references/codex/codex-rs/core/src/tools/context.rs#L408) 和 [`output-truncation`](../../references/codex/codex-rs/utils/output-truncation/src/lib.rs#L12)。

### `view_image`

`view_image` 是 Codex 唯一专门面向本地文件内容的模型工具。它：

- 检查模型是否支持图片输入；
- 在选定环境和文件系统沙箱内读取图片；
- 默认用 `high` 细节级别，也可在模型支持时请求 `original`；
- 把文件转成 data URL，并作为真正的 image content item 发送给模型。

实现见 [`view_image.rs`](../../references/codex/codex-rs/core/src/tools/handlers/view_image.rs#L84)。

### 不要混淆 `fs/readFile`

Codex app-server 还提供一个 `fs/readFile` JSON-RPC：接收绝对路径，返回原始字节的 base64。它面向 app-server 客户端，不在模型工具计划中，也没有 `offset`、`limit`、行号、文本 token 控制或文档解析，因此不应算作 Codex Agent 的内置读文件工具。实现见 [`fs_processor.rs:64`](../../references/codex/codex-rs/app-server/src/request_processors/fs_processor.rs#L64)。

## 与直接通过 Bash 读文件相比，增强能力有什么好处

### 1. 降低调用歧义和 shell 风险

专用工具把路径、起始行、行数、PDF 页码变成有类型的字段。模型不必自行拼接引号、转义空格、处理 `$()` 或跨平台命令差异，也不会为了“只读一个文件”顺手获得整套 shell 表达能力。权限系统还能明确知道这是只读操作。

### 2. 主动保护上下文窗口

`cat` 默认会把全部内容倾倒到 stdout；若文件巨大，Agent 只能事后面对被平台截断的结果。专用工具在读取协议层就知道总行数、当前窗口、下一段偏移，并用行数、字节数或 token 预算限制返回量。这带来三个直接收益：

- 避免单次工具结果挤占大量上下文；
- 避免 API 请求过大、OOM 或长时间阻塞；
- 截断后仍给出可继续读取的确定位置，而不是得到一个来源不明的残片。

Codex 虽没有专用文本读取器，但 `exec_command` 仍在命令输出层提供 10000 token 默认预算、中间裁剪和原始大小提示。

### 3. 给模型稳定的位置锚点

Claude Code 给每行编号，Grok 给窗口首行和每十行建立锚点；OpenCode 不改写正文，但用结构化 `offset`/`next` 标明窗口边界。模型可以引用代码位置、规划后续范围读取，并把观察结果映射到编辑操作。普通 `cat` 没有行号；Bash 可以用 `nl` 或 `cat -n` 补上，但需要模型每次都记得选择一致格式。

### 4. 原生多模态和文档理解

Bash 读图片通常只会输出二进制乱码或 base64；`pdftotext`、`jq`、`unzip` 等工具也未必安装。专用工具可以：

- 把图片作为视觉 token，而不是文本；
- 自动纠正方向、缩放、转码和压缩；
- 把 PDF 按页渲染或提取文字；
- 把 Notebook 拆成 cell；
- 把 PPTX 拆成幻灯片和备注。

这些功能不只是命令简写，而是在“文件字节”与“模型可理解内容”之间做了协议转换。

### 5. 更友好的失败恢复

专用工具知道当前工作目录、总行数、允许的格式和调用参数，因此能返回“offset 越界”“这是目录”“文件被 `.gitignore` 排除”“是否想读这个相似路径”等面向下一步行动的错误。普通 Bash 通常只给 errno 或某条命令自己的 stderr。

### 6. 与 Agent 生命周期和状态集成

Claude Code 能避免重复发送未修改文件、触发路径相关技能并记录记忆文件新鲜度；Grok 能注入路径规则；Pi 能换成远程读取后端；OpenCode 把 Location 权限、图片归一化和超限结果留存接到统一结算链路；Codex 的命令工具能暂停为会话、接受后续输入并接入审批。直接启动一次 `cat` 本身没有这些会话语义。

### 7. 可观测性和策略控制更清晰

框架可以把“读了哪个文件、读了多少、是否截断、是否命中权限规则”记录成结构化事件。若只看到一段任意 shell 脚本，系统必须先解析命令，仍可能无法准确判断管道、重定向或子进程最终读了什么。

## 专用读工具并不总比 Bash 更好

Bash 仍然适合以下情况：

- 只需要匹配内容时，用 `rg` 比整段读取更节省 token；
- 处理单条超长 JSON 时，`jq`、`cut -c` 或脚本按字段/字符提取比按行分页有效；
- 需要组合过滤、排序、解压、反序列化时，成熟 CLI 工具更灵活；
- Pi 和 Grok 都会先把整个普通文件读入内存；针对超大文件的少量窗口读取，Claude Code、OpenCode 的流式实现或 `sed`/`awk` 更节省内存；
- Codex 的通用 shell 路线可以立即利用机器上已有的新格式处理器，不需要先给 Agent 增加一个新的内置分支。

更准确的结论不是“专用工具取代 Bash”，而是：

- **常规源码、配置和多媒体阅读**：专用工具更安全、稳定、节省上下文；
- **搜索、超长单行和临时格式转换**：Bash/CLI 更强；
- **最佳 Agent 实现**通常保留两者，并在提示中让模型优先使用专用读工具、遇到专用工具表达不了的窗口或变换时再退回 shell。

## 横向评价

- **Claude Code `Read`**：语义最丰富，尤其是大文件流式扫描、重复读取去重、权限和 Notebook/PDF 集成；代价是实现复杂、与 Claude Code 内部状态耦合较深。
- **Grok `read_file`**：图片/PDF/PPTX 覆盖广，输出锚点和 token 保护清晰，并专门照顾规则、技能和超长单行；普通文本仍先整文件读入内存。
- **OpenCode `read`**：V2 分层和结构化结果边界清晰，文本与目录都支持可续页读取，大文件不整体载入，Location 权限和通用输出留存统一；文档类型较少，文本无行号，部分可恢复错误被折叠成通用消息。
- **Pi `read`**：实现最直接，50 KiB/2000 行规则容易预测，图片和远程后端抽象实用；文档类型少，也不为文本自动加行号。
- **Codex `exec_command` + `view_image`**：文本能力来自 Unix/PowerShell 组合，灵活且复用生态；安全、会话、审批和输出预算由执行层统一处理，但缺少文本范围、总行数、PDF/Notebook 语义等专用读协议。
