# Agent system prompts: sources, content directions, and general capability improvements

> Generated in full from the [Chinese source](../zh-CN/agent_system_prompt.md).
> Research date: 2026-10-05. Runtime prompts remain at the mainline version present when this study began. This document proposes changes to evaluate; it reports no new benchmark improvement.

## Conclusion and objective

Prioritize **requirement coverage, execution feedback, independent verification, and evidence-based completion**. The current prompts already require autonomous work, tool-based checks, timely preservation of deliverables, and finalization within budget. The gap is that these requirements do not yet specify sufficiently concrete working methods. Small additions to those methods are a better initial fit for the current four-tool agent than importing an entire large project's prompt.

Two kinds of evidence motivate this judgment. Existing benchmark runs sometimes ended normally and passed self-checks while failing official verification. Reference projects offer different ways to turn “complete the task” into observable behavior. The former identifies problems worth studying; the latter supplies candidate designs. Neither proves that a particular passage works. Keep the frozen baseline, repeated samples, and new experiments separate.

As requested, this round first recorded the motivation in the [development notes](../../dev_notes/en/0.10.x.md), then updated the reference projects and archived individual sources before making comparisons. Runtime tools, budgets, recovery mechanisms, and test scripts are outside this documentation change.

## Source updates and coverage boundaries

### Reference repositories were updated

Each repository was checked for a clean working tree, fetched from its origin, and fast-forwarded to its existing tracked branch. The table records the resulting pinned versions. The [source manifest](../agent_system_prompts/sources.json) contains complete remote URLs, before-and-after SHAs, and UTC timestamps. Local `references/` directories are Git-ignored; reviewers should not need identical local clones. Each archive provides an upstream permalink and source hashes.

| Project | Tracked branch | Updated commit | Result |
| --- | --- | --- | --- |
| Codex | `main` | `823ea830c0fd` | Updated |
| OpenCode | `dev` | `907b3bc518fa` | Updated |
| Pi | `main` | `b7dfc049e917` | Updated |
| Grok Build | `main` | `2bdd1d6a6369` | Updated |
| DeepSeek Harness | `master` | `5badb15009ae` | Already current after fetch |
| Local claude-code | `main` | `a371abbe75ff` | Already current after fetch; not an official prompt source |

The origin of `references/claude-code` is `yasasbanukaofficial/claude-code`. That repository does not establish access to Anthropic's complete official Claude Code prompt. Following the requested source, this study analyzes only the official pages for Opus 5.5, Sonnet 5.5, and Fable 5.1.

### 42 records, each identifying the kind of text it contains

The [individual index](agent_system_prompts/README.md) contains 42 records, each documented in Chinese and English: Codex 10, OpenCode 13, Pi 4, Grok Build 4, DeepSeek Harness 4, this project's baseline 4, and official Claude pages 3. They are not 42 interchangeable primary system prompts.

- Open-source originals are preserved under their licenses, with source files, extraction selectors, and SHA256 hashes for both files and extracted text. [Licenses and archive documentation](../agent_system_prompts/README.md) accompany them.
- Static strings, model templates, dynamic reminders, specialized-agent prompts, builder source, and assembled test samples are labeled separately. Template placeholders are preserved; incomplete static fragments are not assembled into a purported complete runtime request.
- The 39 local-source records preserve English originals under `en/agent_system_prompts/` and full Chinese translations under `zh-CN/agent_system_prompts/`, completed on 2026-10-06; analysis is bilingual. Tool names, paths, code identifiers, template placeholders, and machine-read format markers remain unchanged. The manifest records separate original and translation SHA256 hashes. The user subsequently supplied three Claude English Markdown bodies, now preserved in full and translated paragraph by paragraph. All 42 records contain the complete selected original and its Chinese translation.
- This selection covers major entry points and relevant specialized responsibilities. It is not an exhaustive archive of every tool description, permission message, skill, plugin, or user instruction in every repository. Codex entries with identical bodies share one record; distinct bodies have separate records. All ten bodies referenced by OpenCode's primary prompt selector are included.

The official [system prompts overview](https://platform.claude.com/docs/en/release-notes/system-prompts/overview) explicitly describes prompts for **claude.ai and mobile apps**, excluding the API. These are also not complete Claude Code runtime prompts. The three pages are [Opus 5.5](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-opus-5-5) (2026-09-22), [Sonnet 5.5](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-sonnet-5-5) (2026-09-28), and [Fable 5.1](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-fable-5-1) (2026-09-01). These are dated webpages whose URLs do not pin their contents. On 2026-10-06, the user placed the three English Markdown bodies under `en/`. The repository preserves all supplied page metadata, prompt text, and examples, with full translations under `zh-CN/`. The manifest records user-provided acquisition, the document hashes at receipt, and original and translated body hashes. This pins the supplied material; it does not claim a new fetch or verification of the complete live webpages.

## What the projects' prompts contain

### Codex: persistence, engineering judgment, and collaboration protocols

This study primarily reads `model_messages.instructions_template` from the updated [`models.json`](https://github.com/openai/codex/blob/823ea830c0fd418b09ff02d36cad9a1fff66465b/codex-rs/models-manager/models.json), rather than only selecting GPT-named files in older directories. Its 11 model entries contain eight distinct bodies. The [generic fallback](agent_system_prompts/codex/fallback.md) and [compaction handoff](agent_system_prompts/codex/compaction.md) are also archived. Runtime may use a remote model catalog, configuration overrides, permissions, and environment messages; the static catalog cannot establish which text every actual request uses.

The primary templates combine authorization scope, task continuity, tool use, proportionate checks, progress communication, and final reporting. [6.1-sol](agent_system_prompts/codex/gpt-6.1-sol.md) specifies how to handle mid-task user messages and continuity after compaction. [5.5](agent_system_prompts/codex/gpt-5.5.md) devotes more space to engineering tradeoffs, change scope, and frontend experience. [5.6-sol](agent_system_prompts/codex/gpt-5.6-sol.md) also represents three other catalog entries with identical text. Template differences do not establish benchmark advantages for particular wording.

Useful principles include carrying action requests through delivery, preserving established user constraints, choosing checks according to risk, grounding completion claims in results, and stopping after sufficient verification. Lengthy interaction styles, particular tool names, plugin procedures, and permission interfaces depend on host capabilities and should not be transplanted wholesale into nanoPyCodeAgent's headless mode.

### OpenCode: model-specific working methods whose differences matter

[`session/system.ts`](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/session/system.ts) selects bodies by model identifier. [`session/llm/request.ts`](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/session/llm/request.ts) also supports an `agent.prompt` override and appends environment and other information. OpenCode therefore has no single primary prompt shared by every configuration.

| Body | Main content directions | Transfer judgment |
| --- | --- | --- |
| [anthropic](agent_system_prompts/opencode/anthropic.md) | Coding execution, task management, tools, and communication | Persistent task tracking is useful; its task-management tool is not an existing capability here |
| [default](agent_system_prompts/opencode/default.md), [gpt](agent_system_prompts/opencode/gpt.md) | Environment investigation, code conventions, tests and lint/typecheck, delivery reporting | Discover the project's own checks; headless work cannot wait for a user to supply commands |
| [gpt-astra](agent_system_prompts/opencode/gpt-astra.md), [codex](agent_system_prompts/opencode/codex.md) | Autonomous progress, scope and authorization, collaboration, output rules | Extract execution and evidence requirements without copying product workflows |
| [gemini](agent_system_prompts/opencode/gemini.md) | Understand, plan, implement, test, follow conventions, check available dependencies | Useful as a short working loop, without requiring a lengthy plan for every task |
| [kimi](agent_system_prompts/opencode/kimi.md) | Observe after acting, read errors, repair and retest, preserve constraints | Can make the current instruction to check with tools more concrete |
| [meta](agent_system_prompts/opencode/meta.md) | Gather evidence before synthesis, execute and independently check, preserve user corrections | Closely related to this study's concern about evidence for completion |
| [beast](agent_system_prompts/opencode/beast.md) | Intensive investigation, execution, repeated testing, broad web research | Do not copy universal browsing, oversized reads, or unbounded perfection requirements |
| [trinity](agent_system_prompts/opencode/trinity.md) | Explicit identity, tool-call cadence, execution rules | Constraints such as one tool per message differ from other templates; protocols must match the host |

The archive also includes a [planning reminder](agent_system_prompts/opencode/plan-mode.md), [exploration agent](agent_system_prompts/opencode/explore.md), and [compaction agent](agent_system_prompts/opencode/compaction.md). Read-only planning, exploration output, and summary handoffs serve distinct responsibilities and cannot all be concatenated into an execution agent. Historical files without references in the inspected loading paths are not treated as current defaults.

### Pi: a concise core, with details supplied by tools and context

The [coding-prompt builder](agent_system_prompts/pi/coding-system.md) combines identity, available tools, tool-provided guidance, project context, skills, and environment in sections. Its default coding identity is short. `customPrompt` replaces the default prefix, while `forceSystemPrompt` supplies a complete override; those entry points should not be conflated.

The other three records are a [summarization system message](agent_system_prompts/pi/summarization-system.md), [compaction checkpoint task](agent_system_prompts/pi/checkpoint.md), and [branch-summary task](agent_system_prompts/pi/branch-summary.md). They show how summaries preserve objectives, constraints, progress, and next steps without continuing the summarized task. This is context-management design, not a capability that an ordinary execution agent gains from one additional sentence.

Pi's most relevant lesson is separation of responsibilities: keep core instructions focused, ground tool guidance in actual capabilities, and supply changing information at runtime. Its short core does not itself specify a complete independent-verification strategy. Neither brevity nor length is evidence of effectiveness on its own.

### Grok Build: distinguish delivery, acceptance, and evidence

The [main template](agent_system_prompts/grok-build/main.md) has environment-dependent sections covering autonomy, requirement scope, tools, progress, evidence, and result reporting. The [subagent template](agent_system_prompts/grok-build/subagent.md) defines delegated-task boundaries and returned information. Both depend on actual scheduling and tools; copying their text does not create a multi-agent runtime.

The [goal planner](agent_system_prompts/grok-build/goal-planner.md) and [goal verifier](agent_system_prompts/grok-build/goal-verifier.md) are especially relevant. The planner calls for a bounded set of independently checkable outcomes, validation actions, and expected observations. The verifier distinguishes implementation defects, contradictory requirements, and unverifiable outcomes; it audits existing evidence and avoids continually adding acceptance criteria. The planner also distinguishes running the real entry point and checking primary output from weak evidence such as file existence or successful startup.

Two principles matter equally: **make acceptance meaningful and keep its scope bounded**. This project can adopt that completion judgment within one agent before introducing separate planner or verifier agents. Specific browser, external-CI, repeated-launch, and interactive-approval rules depend on the task and environment; they should not all become mandatory steps for every task here.

### DeepSeek Harness: prompts assembled from plugins

The [headless persona fragment](agent_system_prompts/deepseek-harness/headless-persona.md) contains only brief identity text. [Planning guidance](agent_system_prompts/deepseek-harness/plan-policy.md) comes from deployment configuration. [Command-result guidance](agent_system_prompts/deepseek-harness/bash-result-check.md) is registered by a tool plugin and requires checking execution results and exit status. The [assembled sample](agent_system_prompts/deepseek-harness/assembled-session-fixture.md) shows multiple sections together, but it is a committed test snapshot with a fixture persona, not the default production headless prompt.

The [`system-prompt` implementation](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/system-prompt/src/index.ts) assembles registered sections. A short primary persona therefore does not imply that complete requests lack engineering constraints. Plugin registration, section updates, and tool descriptions are runtime design. The easiest immediate transfer is concrete guidance for inspecting command results, rather than reproducing the plugin architecture first.

### Official Claude pages: product behavior rather than a coding workflow

Individual records cover [Opus 5.5](agent_system_prompts/claude/opus-5-5.md), [Sonnet 5.5](agent_system_prompts/claude/sonnet-5-5.md), and [Fable 5.1](agent_system_prompts/claude/fable-5-1.md). The pages primarily cover product identity and knowledge limits, safety and wellbeing, tone and formatting, trusted context, and correction. Their formatting preferences differ, but they do not provide the complete coding-verification loop this project needs.

This study infers transferable directions: check verifiable facts, avoid unsupported claims, disclose unverified scope, and correct errors based on evidence. These are design inferences, not experimental evidence of improved coding pass rates. Product policies and chat style are not the main target of this optimization.

## Content directions and current gaps

The table groups instructions by the behavior they can guide, rather than scoring projects. A requirement appearing in a prompt does not establish compliance in actual trajectories.

| Direction | Reference-project treatment | Current nanoPyCodeAgent | Priority |
| --- | --- | --- | --- |
| Identity, communication, authorization | Extensive in Codex, OpenCode, Grok, and Claude | Concise identity; headless explicitly requires autonomy without waiting for the user | Preserve; not the main initial addition |
| Requirements and scope | Codex continuity; Grok bounded acceptance; OpenCode constraint preservation | Requires completion but does not specify acceptance or the relationship between examples and general requirements | High |
| Environment facts and tool selection | Pi tool guidance; OpenCode dependency and entry-point checks; DeepSeek tool sections | Already explains read/edit/write/bash and requires actual tool results | Medium; add working methods only |
| Execution and feedback | Kimi, Gemini, Codex, and Grok emphasize progress, observation, and repair | Autonomous execution, without concrete guidance for obtaining runnable feedback | Medium; evaluate separately |
| Independent and boundary validation | Meta and Gemini checks; Grok real entry points and output acceptance | Requires tool-based checks but does not explain how to avoid validating only visible examples or self-confirming assumptions | Highest |
| Failure diagnosis and constraint preservation | Kimi repair and retest; Grok failure categories | Tools return errors; the primary prompt does not elaborate a diagnostic method | High; combine with validation in a small change |
| Completion, evidence, and stopping | Codex delivers after proportionate checks; Grok audits evidence within bounded scope | Budget and stopping guidance already exists; normal termination does not imply correctness | High; strengthen semantic completion without changing the terminal-state protocol |
| Compaction, delegation, plugins | Specialized layers in Codex, Pi, OpenCode, Grok, and DeepSeek | No equivalent complete runtime here | Separate later design; exclude from the prompt-only experiment |

### Four existing layers in this project

At the starting mainline revision `c8c5bf7`, the [interactive prompt](agent_system_prompts/nanopycodeagent/interactive.md) provides a brief identity and four-tool guidance. The [headless prompt](agent_system_prompts/nanopycodeagent/headless.md) adds autonomous work, result checks, deliverable preservation, and timely completion. [Budget reminders](agent_system_prompts/nanopycodeagent/budget-reminder.md) are appended dynamically based on remaining time and replies; they already reserve necessary checking, stop optional exploration, and state that tools on the final reply will not execute. The [truncation-recovery reminder](agent_system_prompts/nanopycodeagent/truncation-recovery.md) requires continuation from confirmed results; code enforces the budget and single-recovery cap.

The current state therefore should not be described as lacking verification, budget awareness, or recovery altogether. New text should refine how the agent makes these judgments while preserving the fixed primary prompt and dynamic budget reminders. In code, `completed` means the model ended normally; it does not independently prove that deliverables satisfy the task. Renaming that state cannot solve correctness.

## What the benchmark evidence does and does not establish

| Experiment | Observed result | Relevance to this study |
| --- | --- | --- |
| [Frozen v0.9.0 baseline](../../../benchmarks/harbor/reports/v0.9.0-baseline-20261005.md) | 18/20; the two failures involved output truncation and related issues | Preserve the original baseline rather than replacing it with later best results |
| [Initial truncation-recovery experiment](../../../benchmarks/harbor/reports/truncation-recovery-20261005.md) | 2/2 passed, neither exercising recovery | Does not establish that recovery improved pass rates |
| [Three additional runs per task](../../../benchmarks/harbor/reports/truncation-recovery-repeat3-20261005.md) | 4/6 passed; all `completed`; the only actual recovery continued work and produced artifacts but failed verification | Continued execution, artifact existence, normal termination, and semantic correctness are distinct metrics |
| [Dual-budget pilot20](../../../benchmarks/harbor/reports/dual-budget-20260929.md) | 18/20 and all `completed`; one numerical task passed self-checks but failed independent verification, while another missed an accuracy requirement | Verification quality and solution quality still have gaps; honestly acknowledging a missed requirement is not a passing result |

The two failed model-extraction repetitions primarily checked the visible instance; official verification exposed incompleteness at a different size. The development notes also record a trajectory review: the passing run checked different input conditions, model sizes, and output residuals, then fixed an issue exposed by additional checks. The experiment's [structured results](../../../benchmarks/harbor/results/tb21-truncation-recovery-repeat3-20261005.json) preserve original trajectory paths; raw files remain in Git-ignored `jobs/` directories. This trajectory observation is a clue to a candidate mechanism, not the sole causal explanation or an established diagnosis of every algorithmic failure.

Task names and specific verification parameters explain historical evidence only. Candidate prompts should contain none of them and should not import hidden-verifier parameters, task-specific algorithms, or answers. The generalizable requirement is that examples may cover only part of the valid input space, so validation should challenge key assumptions using the public task contract.

Long reasoning also requires careful interpretation. The actual recovery case reached the 65,536-token cap before writing a script, but the passing case also included a 53,538-token response. These observations support investigating earlier runnable feedback, not imposing a very low reasoning cap or treating shorter reasoning as an established improvement.

## Recommended optimization order

### P0: requirements, independent validation, diagnosis, and completion evidence

Start with a small, coherent candidate: identify explicit deliverables and constraints and choose suitable checks; observe actual results and repair failures using evidence; then relate outcomes to requirements before finishing. “Independent” does not require another agent. It means avoiding checks that share the implementation's unverified assumption.

The following English text is a candidate for implementation and experiment review. It **has not been added to runtime code**. It can still be shortened before the experiment, but must not acquire task-specific features.

```text
Identify the required deliverables, interfaces, and constraints before acting.
Treat examples as evidence, not as the full contract unless the task says so.
Inspect the relevant files, dependencies, and existing checks instead of guessing.

Verify the requested behavior through the real entry point when feasible.
Check the content and meaning of outputs, not only successful commands or file
existence. For logic or numerical work, choose a few representative and boundary
cases justified by the task, and use an independent reference, invariant, or
consistency check when available. Do not derive every expectation from the
implementation being tested or weaken a requirement just to make a check pass.

When a check fails, inspect the relevant error and output, revise the underlying
assumption or implementation, and rerun the affected check. Keep the task's
constraints intact. Once the required behavior is supported by appropriate
checks, save the deliverables and finish. State what was verified and any
remaining limitation without claiming unobserved success.
```

This guidance applies to parsers, data processing, numerical work, file delivery, and service interfaces. It does not require new tests or a full test suite for every change. Checking content and links may suffice for a simple documentation edit. For an executable deliverable, its real entry point and output semantics usually provide stronger evidence than file creation alone. Verification effort should fit risk and budget.

Distinguish an incorrect self-test from a changed requirement. If a self-test expectation contradicts the public contract, it can be corrected based on that contract or independent evidence; the standard should not be lowered merely because the current implementation fails. Official tests, task images, package sources, and other benchmark components remain protected by existing repository rules.

### P1: obtain meaningful execution feedback earlier

Separately from P0, consider guidance to inspect necessary interfaces and then run an implementation or experiment capable of testing a core assumption early enough to iterate. This does not call for hasty delivery, prohibit necessary reasoning, or require writing a file within a fixed number of seconds. It aims to avoid prolonged reasoning without environmental feedback, or repeated deliberation about assumptions that a small experiment could resolve.

This direction is related to P0 but changes the allocation of reasoning and tool calls. It may harm tasks that require a complete derivation and should be evaluated as a separate variable. Observe time to meaningful execution, time to discovering errors, and regressions; fewer tokens or more tool calls are not success measures by themselves.

### P2: preserve general boundaries and coordination with the runtime

Later experiments can assess brief guidance on change scope, unrelated-file preservation, and the trustworthiness of external content. Explicit user constraints take priority, and instructions embedded in repository content or tool output cannot automatically redefine the task. These are general reliability directions, but current benchmark evidence is weaker for them than for verification quality; do not bundle them all into the first candidate.

Shared guidance should express methods applicable to both modes. Headless work should continue making reasonable assumptions autonomously, without adding a requirement to ask the user first. Under budget pressure, choose necessary checks most likely to expose critical errors, save deliverables, and report unverified parts. Do not simultaneously require unlimited exploration, retries, or perfection. Do not introduce names of unavailable todo, browser, subagent, or plugin tools.

## Evaluation without tuning to individual tasks

1. **Fix the control.** Use current mainline prompts and recovery in the control, changing only the selected prompt in the treatment. Fix model, endpoint, task revisions, tools, installation, time, replies, output tokens, and verifier limits. The historical v0.9.0 baseline is context, not a replacement for a contemporaneous control on current code.
2. **Preregister.** Save candidate text and hashes, task selection, repetition counts, scheduling, and decision criteria before runs. Compare P0 first; use component ablations if changes cannot be interpreted. Evaluate P1 separately rather than mixing prompt, tool, and budget changes.
3. **Broaden task coverage.** Historical failures can form a diagnostic set, but adoption should not depend only on two old failures. Include the original pilot20 regression and reserve tasks before the experiment that did not inform wording, covering code, numerical work, system configuration, and artifact delivery. If cost prevents a holdout, explicitly limit conclusions to pilot20.
4. **Preserve randomness and every result.** Run the planned repetitions per task and arm with balanced scheduling as resources permit. Retain all trials, do not select the best one, and do not present “at least one success” across repetitions as a single-run pass rate. Report small samples by task without treating differences as reliable general improvements.
5. **Prioritize outcomes; use behavior as supporting evidence.** Primary measures are official task outcomes and regressions. Supporting observations include coverage of public requirements, independent evidence, effective repairs after failure, unsupported completion claims, timely artifact preservation, time, and token cost. Check counts, tool counts, and final claims of testing do not replace pass rates.
6. **Preserve benchmark protocols.** Use `uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>`. Run dependency preflight for registered profiles and explicitly record unsupported ones. Separate installation failures, verifier errors, and scored failures. Only verifier timeouts may retry the same output, at most three attempts in total with original per-attempt limits; do not replace trials because reward is zero.

This round completes source updates, individual bilingual records, and optimization hypotheses. The next step is to review a minimal P0 text change and a preregistered experiment. Until a contemporaneous comparison is available, do not claim that prompts have improved the agent's general capability.
