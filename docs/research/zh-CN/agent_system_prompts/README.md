# 逐份提示词索引

[综合调研](../agent_system_prompt.md)

本索引覆盖本轮选定的主提示词、模型变体、规划、验证和交接提示词。39 份本地来源记录在 `en/` 保存英文原文，在 `zh-CN/` 保存全文中文译文，解读同步为双语。工具名、路径、代码标识符、模板占位符和机器读取的固定格式标记保留原样。另有 3 份 Claude 官方页面记录，仅保存来源链接、英文短引文及其中文译文和分析，未归档全文。每份记录分别标注正文、模板、动态片段或组装样本；不把代码生成器误称为一次真实请求，也不把测试快照误称为生产默认。

## codex

- [Codex：gpt-6-astra](codex/gpt-6-astra.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-6.1-sol](codex/gpt-6.1-sol.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-6-sol](codex/gpt-6-sol.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-6-luna](codex/gpt-6-luna.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-5.6-sol](codex/gpt-5.6-sol.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-daybreak-blue-latest](codex/gpt-daybreak-blue-latest.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-daybreak-red-latest](codex/gpt-daybreak-red-latest.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：gpt-5.5](codex/gpt-5.5.md) — 模型专用指令模板；不是运行时所有消息的拼接结果。
- [Codex：通用回退提示词](codex/fallback.md) — 完整静态回退提示词。
- [Codex：上下文压缩交接](codex/compaction.md) — 专用压缩提示词。

## opencode

- [OpenCode：anthropic](opencode/anthropic.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：default](opencode/default.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：gpt-astra](opencode/gpt-astra.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：gpt](opencode/gpt.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：codex](opencode/codex.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：gemini](opencode/gemini.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：beast](opencode/beast.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：kimi](opencode/kimi.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：meta](opencode/meta.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：trinity](opencode/trinity.md) — 完整静态 provider 提示词；其后仍有环境、技能和项目指令。
- [OpenCode：plan-mode](opencode/plan-mode.md) — 规划模式动态提醒。
- [OpenCode：explore](opencode/explore.md) — 专用探索代理系统提示词。
- [OpenCode：compaction](opencode/compaction.md) — 专用压缩代理系统提示词。

## pi

- [Pi：编码代理分段提示词](pi/coding-system.md) — 完整组装器源码；含运行时变量，不冒充某次请求的最终文本。
- [Pi：summarization-system](pi/summarization-system.md) — 摘要专用系统消息。
- [Pi：checkpoint](pi/checkpoint.md) — 压缩请求的任务提示词，不是主系统提示词。
- [Pi：branch-summary](pi/branch-summary.md) — 离开会话分支时的总结任务提示词。

## grok-build

- [Grok Build：main](grok-build/main.md) — 含条件分支的主代理模板。
- [Grok Build：subagent](grok-build/subagent.md) — 委派工作代理模板。
- [Grok Build：goal-planner](grok-build/goal-planner.md) — 目标创建时运行的专用规划器模板。
- [Grok Build：goal-verifier](grok-build/goal-verifier.md) — 独立验收代理模板。

## deepseek-harness

- [DeepSeek Harness：headless 身份片段](deepseek-harness/headless-persona.md) — 部署身份片段，保留 model 占位符。
- [DeepSeek Harness：规划模式指导](deepseek-harness/plan-policy.md) — 部署提供的 plan:policy 文本。
- [DeepSeek Harness：命令结果检查片段](deepseek-harness/bash-result-check.md) — 工具插件注册的系统提示词片段。
- [DeepSeek Harness：组装后的会话测试样本](deepseek-harness/assembled-session-fixture.md) — 已提交的组装结果测试快照；不是生产默认配置的运行捕获。

## nanopycodeagent

- [交互模式系统提示词](nanopycodeagent/interactive.md) — 当前主线基准的完整字符串值；组合字符串已展开。
- [无人值守模式系统提示词](nanopycodeagent/headless.md) — 当前主线基准的完整字符串值；组合字符串已展开。
- [截断恢复注入提示词](nanopycodeagent/truncation-recovery.md) — 当前主线基准的完整字符串值；组合字符串已展开。
- [运行预算提醒生成器](nanopycodeagent/budget-reminder.md) — 动态提示词生成器源码。

## claude

- [Claude：Opus 5.5](claude/opus-5-5.md) — 仅短引文及译文；claude.ai 与移动端提示词；不是 Claude Code 或 API 的完整系统提示词。
- [Claude：Sonnet 5.5](claude/sonnet-5-5.md) — 仅短引文及译文；claude.ai 与移动端提示词；不是 Claude Code 或 API 的完整系统提示词。
- [Claude：Fable 5.1](claude/fable-5-1.md) — 仅短引文及译文；claude.ai 与移动端提示词；不是 Claude Code 或 API 的完整系统提示词。
