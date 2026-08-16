# Built-in Tools in Popular Code Agents

> Generated from the Chinese source [`../zh-CN/agent_tools.md`](../zh-CN/agent_tools.md). Do not edit by hand.

nanoPyCodeAgent currently has only a Bash tool, while mainstream code agents typically provide other built-in tools as well. This document surveys the tool designs of Pi, Claude Code, Codex, OpenCode, and Grok Build.

## Pi

Pi has a relatively small core toolset. The [Pi Quick Start](https://pi.dev/docs/latest/quickstart#first-session) introduces four core tools:

- `read`: read files
- `write`: create or overwrite files
- `edit`: edit files
- `bash`: run shell commands

It also offers three optional extension tools: `grep`, `find`, and `ls`.

## Claude Code

Claude Code provides a larger set of tools. The [Claude Code tools reference](https://code.claude.com/docs/en/tools-reference) introduces the following major tools.

### File operations

- `Read`: read file contents, including text, images, PDFs, and Jupyter Notebooks
- `Write`: create or completely overwrite files
- `Edit`: make localized changes to files through exact string replacement
- `NotebookEdit`: edit Jupyter Notebooks by cell

### Search and code intelligence

- `Glob`: find files by filename pattern
- `Grep`: search file contents by pattern, powered by ripgrep
- `LSP`: provide code intelligence through language servers, such as go to definition, find references, and type-error reporting

### Command execution

- `Bash`: execute shell commands in the environment
- `PowerShell`: execute PowerShell commands natively, primarily on Windows
- `Monitor`: run commands in the background and stream output line by line, for monitoring logs, polling state, and subscribing to WebSocket events

### Web access

- `WebFetch`: fetch content from a URL, convert it to Markdown, and use a small model to extract information according to a prompt
- `WebSearch`: search the web and return result titles and links

### Subagents and orchestration

- `Agent`: spawn a subagent with an independent context window to complete a task
- `SendMessage`: send a message to an Agent Team teammate, or resume a specific subagent by ID
- `Workflow`: run dynamic workflow scripts that orchestrate multiple subagents in the background and return an aggregated result
- `Skill`: run a Skill—a reusable prompt workflow—in the main conversation

### Task management

- `TaskCreate`, `TaskGet`, `TaskList`, `TaskUpdate`: create, retrieve, list, and update tasks
- `TaskOutput`: retrieve background-task output; deprecated in favor of reading output files with `Read`
- `TaskStop`: stop a background task by ID
- `TodoWrite`: manage the session task list; disabled by default and superseded by the `Task*` family

### Planning and workspaces

- `EnterPlanMode`, `ExitPlanMode`: enter plan mode to design an approach, submit the plan for approval, and exit
- `EnterWorktree`, `ExitWorktree`: create and enter an isolated Git worktree, then return to the original directory on exit

### Scheduling

- `CronCreate`, `CronDelete`, `CronList`: create, cancel, and list scheduled tasks within the current session
- `ScheduleWakeup`: schedule the next iteration of `/loop` at an adaptive cadence
- `RemoteTrigger`: create and manage Routines on claude.ai—that is, scheduled cloud agents

### User interaction and output

- `AskUserQuestion`: ask the user multiple-choice questions to clarify requirements
- `Artifact`: publish an HTML or Markdown file as an Artifact page on claude.ai
- `PushNotification`: send desktop or mobile push notifications
- `SendUserFile`: send reports, screenshots, and other files from the session directly to the user's device
- `ReportFindings`: report code-review findings as a structured list
- `ShareOnboardingGuide`: upload `ONBOARDING.md` and generate a link for sharing it with the team

### MCP-related tools

- `ListMcpResourcesTool`, `ReadMcpResourceTool`: list and read resources exposed by MCP servers
- `ToolSearch`: search for and load deferred tools on demand; requires Tool Search to be enabled
- `WaitForMcpServers`: wait for MCP servers that are still connecting in the background to become ready

## Codex

Unlike Pi and Claude Code, Codex has no dedicated `Read`, `Glob`, or `Grep` tools; it reads and searches by using `exec_command` to invoke commands such as `rg` and `sed`. In addition to the [official tools documentation](https://developers.openai.com/api/docs/guides/tools), this document also refers to the source code of the open-source [Codex](https://github.com/openai/codex) project.

Tools commonly available in a standard local coding turn include:

- `exec_command`: execute shell commands
- `write_stdin`: send additional input to, or poll, a long-running command
- `apply_patch`: modify files with structured patches
- `update_plan`: update the task plan
- `view_image`: view local images
- `web_search`, or `web.run` under the newer namespace: search the web

Conditionally available tools also include:

- Interaction: `request_user_input`
- MCP resources: `list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource`
- Permissions: `request_permissions`
- Multi-agent collaboration: `spawn_agent`, `send_message`, `followup_task`, `wait_agent`, `interrupt_agent`, `list_agents`
- Search-based tool discovery: `tool_search`
- Image generation: `image_gen.imagegen`
- Dynamic tools injected by MCP, Apps, and plugins

## OpenCode

[OpenCode](https://github.com/anomalyco/opencode) v1.18.3 includes the following built-in tools:

### Files and execution

- `bash`: execute shell commands
- `read`: read text or images, or list directory contents
- `write`: create or overwrite files
- `edit`: perform exact string replacements
- `apply_patch`: use patches to add, modify, or delete multiple files
- `glob`: find files by filename pattern
- `grep`: search file contents with regular expressions

### Web access

- `webfetch`: fetch content from a specified URL
- `websearch`: search the internet

### User interaction

- `question`: ask the user questions during execution

### Skills and task management

- `skill`: load a `SKILL.md` file
- `todowrite`: create and update task lists

## Grok Build

The recently open-sourced [Grok Build](https://github.com/xai-org/grok-build) includes the following built-in tools:

- Files and execution: `run_terminal_command`, `read_file`, `search_replace`, `write`, `list_dir`, `grep`, `lsp`
- Background tasks and subagents: `spawn_subagent`, `get_command_or_subagent_output`, `wait_commands_or_subagents`, `kill_command_or_subagent`, `monitor`
- Task management: `todo_write`, `update_goal`
- Scheduled tasks: `scheduler_create`, `scheduler_delete`, `scheduler_list`
- Plan mode: `enter_plan_mode`, `exit_plan_mode`, `ask_user_question`
- Web: `web_search`, `web_fetch`
- MCP meta-tools: `search_tool`, `use_tool`
- Memory: `memory_search`, `memory_get`
- Media: `image_gen`, `image_to_video`, `reference_to_video`

The following may also be added dynamically at runtime:

- `image_edit`
- Server-side `x_search`
