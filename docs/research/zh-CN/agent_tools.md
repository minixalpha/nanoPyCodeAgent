# 常见 Code Agent 内置工具

> 本文件为**手写中文源文件**（source of truth）；英文版 [`../en/agent_tools.md`](../en/agent_tools.md) 由其生成。

目前 nanoPyCodeAgent 只有 Bash 工具，但主流 Code Agent 通常还会提供其他内置工具。本文调研 Pi、Claude Code、Codex、OpenCode 和 Grok Build 的工具设计。

## Pi

Pi 的核心工具比较少。[Pi Quick Start](https://pi.dev/docs/latest/quickstart#first-session)介绍了四个核心工具：

- `read`：读文件
- `write`：创建或覆盖文件
- `edit`：编辑文件
- `bash`：运行 Shell 命令

除此之外，还有三个可选扩展工具：`grep`、`find`、`ls`。

## Claude Code

Claude Code 提供的工具更多。[Claude Code 工具参考](https://code.claude.com/docs/en/tools-reference)介绍了以下主要工具。

### 文件操作

- `Read`：读取文件内容，支持文本、图片、PDF、Jupyter Notebook
- `Write`：创建或整体覆盖文件
- `Edit`：对文件做精确字符串替换式的局部修改
- `NotebookEdit`：按 cell 修改 Jupyter Notebook

### 搜索与代码智能

- `Glob`：按文件名模式查找文件
- `Grep`：按内容模式搜索文件，基于 ripgrep
- `LSP`：通过语言服务器提供代码智能，例如跳转定义、查找引用、报告类型错误

### 命令执行

- `Bash`：在环境中执行 Shell 命令
- `PowerShell`：原生执行 PowerShell 命令，主要面向 Windows
- `Monitor`：在后台运行命令并逐行回传输出，用于监控日志、轮询状态、订阅 WebSocket 事件

### Web 访问

- `WebFetch`：抓取 URL 内容，转换成 Markdown 后用小模型按 prompt 提取信息
- `WebSearch`：执行网络搜索，返回结果标题和链接

### 子代理与编排

- `Agent`：派生一个拥有独立上下文窗口的子代理去完成任务
- `SendMessage`：给 Agent Team 队友发消息，或按 ID 恢复某个子代理
- `Workflow`：运行动态工作流脚本，在后台编排多个子代理并返回汇总结果
- `Skill`：在主对话中执行一个 Skill，即可复用的提示词工作流

### 任务管理

- `TaskCreate`、`TaskGet`、`TaskList`、`TaskUpdate`：创建、查询、列出、更新任务列表
- `TaskOutput`：获取后台任务输出；已不推荐，改用 `Read` 读取输出文件
- `TaskStop`：按 ID 停止后台任务
- `TodoWrite`：管理会话任务清单；默认已禁用，被 `Task*` 系列取代

### 计划与工作区

- `EnterPlanMode`、`ExitPlanMode`：进入计划模式设计方案，提交计划供批准并退出
- `EnterWorktree`、`ExitWorktree`：创建并切入隔离的 Git worktree，退出后返回原目录

### 定时与调度

- `CronCreate`、`CronDelete`、`CronList`：在当前会话内创建、取消、列出定时任务
- `ScheduleWakeup`：为自适应节奏的 `/loop` 安排下一次迭代时间
- `RemoteTrigger`：创建和管理 claude.ai 上的 Routines，即云端定时代理

### 用户交互与输出

- `AskUserQuestion`：向用户提多选题以澄清需求
- `Artifact`：把 HTML 或 Markdown 文件发布为 claude.ai 上的 Artifact 页面
- `PushNotification`：发送桌面或手机推送通知
- `SendUserFile`：把会话中的报告、截图等文件直接发送到用户设备
- `ReportFindings`：以结构化列表上报 Code Review 发现的问题
- `ShareOnboardingGuide`：上传 `ONBOARDING.md` 并生成团队分享链接

### MCP 相关

- `ListMcpResourcesTool`、`ReadMcpResourceTool`：列出、读取 MCP Server 暴露的资源
- `ToolSearch`：按需搜索并加载延迟加载的工具，需要开启 Tool Search
- `WaitForMcpServers`：等待仍在后台连接中的 MCP Server 就绪

## Codex

Codex 与 Pi 和 Claude Code 不太一样，没有单独的 `Read`、`Glob`、`Grep`；读取和搜索由 `exec_command` 调用 `rg`、`sed` 等命令完成。除[官方工具文档](https://developers.openai.com/api/docs/guides/tools)外，本文也参考了开源的 [Codex](https://github.com/openai/codex) 源码。

标准本地 Coding Turn 常见的工具有：

- `exec_command`：执行 Shell 命令
- `write_stdin`：向长时间运行的命令继续输入或轮询
- `apply_patch`：用结构化 Patch 修改文件
- `update_plan`：更新任务计划
- `view_image`：查看本地图片
- `web_search`，或新式命名空间下的 `web.run`：搜索网页

条件性工具还包括：

- 交互：`request_user_input`
- MCP 资源：`list_mcp_resources`、`list_mcp_resource_templates`、`read_mcp_resource`
- 权限：`request_permissions`
- 多代理：`spawn_agent`、`send_message`、`followup_task`、`wait_agent`、`interrupt_agent`、`list_agents`
- 搜索工具发现：`tool_search`
- 图片生成：`image_gen.imagegen`
- MCP、Apps、插件注入的动态工具

## OpenCode

[OpenCode](https://github.com/anomalyco/opencode) v1.18.3 的内置工具有：

### 文件与执行

- `bash`：执行 Shell 命令
- `read`：读取文本、图片或列出目录内容
- `write`：创建或覆盖文件
- `edit`：精确字符串替换
- `apply_patch`：用 Patch 批量新增、修改、删除文件
- `glob`：按文件名模式查找文件
- `grep`：用正则搜索文件内容

### Web 访问

- `webfetch`：获取指定 URL 内容
- `websearch`：搜索互联网

### 用户交互

- `question`：在执行过程中向用户提问

### 技能与任务管理

- `skill`：加载 `SKILL.md`
- `todowrite`：创建和更新任务列表

## Grok Build

刚开源的 [Grok Build](https://github.com/xai-org/grok-build) 内置工具有：

- 文件与执行：`run_terminal_command`、`read_file`、`search_replace`、`write`、`list_dir`、`grep`、`lsp`
- 后台任务与子代理：`spawn_subagent`、`get_command_or_subagent_output`、`wait_commands_or_subagents`、`kill_command_or_subagent`、`monitor`
- 任务管理：`todo_write`、`update_goal`
- 定时任务：`scheduler_create`、`scheduler_delete`、`scheduler_list`
- Plan 模式：`enter_plan_mode`、`exit_plan_mode`、`ask_user_question`
- Web：`web_search`、`web_fetch`
- MCP 元工具：`search_tool`、`use_tool`
- Memory：`memory_search`、`memory_get`
- 媒体：`image_gen`、`image_to_video`、`reference_to_video`

运行时还可能动态加入：

- `image_edit`
- 服务端 `x_search`
