# Individual prompt index

[Comparative study](../agent_system_prompt.md)

This index covers selected primary prompts, model variants, planning, verification, and handoff prompts. Each file corresponds to one original, template, dynamic fragment, or explicitly labeled assembly sample. Source text retains its original language and analysis is bilingual. Builders are not presented as real requests, and test fixtures are not presented as production defaults.

## codex

- [Codex: gpt-6-astra](codex/gpt-6-astra.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-6.1-sol](codex/gpt-6.1-sol.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-6-sol](codex/gpt-6-sol.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-6-luna](codex/gpt-6-luna.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-5.6-sol](codex/gpt-5.6-sol.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-daybreak-blue-latest](codex/gpt-daybreak-blue-latest.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-daybreak-red-latest](codex/gpt-daybreak-red-latest.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: gpt-5.5](codex/gpt-5.5.md) — Model-specific instruction template; not a concatenation of every runtime message.
- [Codex: generic fallback prompt](codex/fallback.md) — Complete static fallback prompt.
- [Codex: context-compaction handoff](codex/compaction.md) — Specialized compaction prompt.

## opencode

- [OpenCode: anthropic](opencode/anthropic.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: default](opencode/default.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: gpt-astra](opencode/gpt-astra.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: gpt](opencode/gpt.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: codex](opencode/codex.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: gemini](opencode/gemini.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: beast](opencode/beast.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: kimi](opencode/kimi.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: meta](opencode/meta.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: trinity](opencode/trinity.md) — Complete static provider prompt; environment, skills, and project instructions are added separately.
- [OpenCode: plan-mode](opencode/plan-mode.md) — Dynamic plan-mode reminder.
- [OpenCode: explore](opencode/explore.md) — Specialized exploration-agent system prompt.
- [OpenCode: compaction](opencode/compaction.md) — Specialized compaction-agent system prompt.

## pi

- [Pi: structured coding-agent prompt](pi/coding-system.md) — Complete builder source with runtime variables, not a purported final prompt from a particular request.
- [Pi: summarization-system](pi/summarization-system.md) — Summarization-only system message.
- [Pi: checkpoint](pi/checkpoint.md) — Compaction task prompt, not the primary system prompt.
- [Pi: branch-summary](pi/branch-summary.md) — Task prompt for summarizing a departing conversation branch.

## grok-build

- [Grok Build: main](grok-build/main.md) — Primary-agent template with conditional branches.
- [Grok Build: subagent](grok-build/subagent.md) — Delegated-worker template.
- [Grok Build: goal-planner](grok-build/goal-planner.md) — Specialized planner template run at goal creation.
- [Grok Build: goal-verifier](grok-build/goal-verifier.md) — Independent verification-agent template.

## deepseek-harness

- [DeepSeek Harness: headless persona fragment](deepseek-harness/headless-persona.md) — Deployment persona fragment retaining the model placeholder.
- [DeepSeek Harness: plan-mode policy](deepseek-harness/plan-policy.md) — Deployment-supplied plan:policy text.
- [DeepSeek Harness: bash-result checking fragment](deepseek-harness/bash-result-check.md) — System-prompt fragment registered by a tool plugin.
- [DeepSeek Harness: assembled session fixture](deepseek-harness/assembled-session-fixture.md) — Committed assembly test snapshot, not a production-default runtime capture.

## nanopycodeagent

- [Interactive system prompt](nanopycodeagent/interactive.md) — Complete string value at the current baseline; concatenations are resolved.
- [Headless system prompt](nanopycodeagent/headless.md) — Complete string value at the current baseline; concatenations are resolved.
- [Injected truncation-recovery prompt](nanopycodeagent/truncation-recovery.md) — Complete string value at the current baseline; concatenations are resolved.
- [Runtime-budget reminder generator](nanopycodeagent/budget-reminder.md) — Dynamic-prompt builder source.

## claude

- [Claude: Opus 5.5](claude/opus-5-5.md) — Prompt for claude.ai and mobile apps, not a complete Claude Code or API system prompt.
- [Claude: Sonnet 5.5](claude/sonnet-5-5.md) — Prompt for claude.ai and mobile apps, not a complete Claude Code or API system prompt.
- [Claude: Fable 5.1](claude/fable-5-1.md) — Prompt for claude.ai and mobile apps, not a complete Claude Code or API system prompt.
