# Agent 系统提示词：来源、内容方向与通用能力优化

> 中文源文件；[英文版](../en/agent_system_prompt.md) 由本文件完整翻译生成。
> 调研日期：2026-10-05。运行提示词仍保持本轮开始时的主线版本；本文提出待验证的改动方向，不报告新的 benchmark 收益。

## 结论与本轮目标

本轮优先研究**需求覆盖、执行反馈、独立验证和有证据的完成判断**。当前提示词已经要求自主执行、使用工具检查、及时保存交付物和预算内收尾；缺口在于这些要求还没有落实为足够具体的工作方法。先试小幅补充这些方法，比直接移植某个大项目的整套提示词更适合当前四工具 agent。

这个判断来自两类证据：现有 benchmark 出现过正常结束、自测通过但官方验证失败；参考项目则提供了把“完成任务”细化为可观察行为的不同写法。前者说明值得研究的问题，后者提供候选设计；两者都不能证明某段文字已经有效。此前的冻结 baseline、复跑样本和新实验应独立记录。

本轮按要求先在[开发笔记](../../dev_notes/zh-CN/0.10.x.md)记录动机，再更新参考项目、保存逐份资料，最后进行比较。运行时的工具、预算、恢复机制和测试脚本不在本轮文档改动范围内。

## 来源更新与覆盖边界

### 参考仓库已更新

先确认各仓库工作区干净，再分别 fetch 其 origin，并向现有跟踪分支执行 fast-forward 更新。下面是更新后的固定版本；完整远端地址、更新前后 SHA 和 UTC 时间保存在[来源清单](../agent_system_prompts/sources.json)。本地 `references/` 被 Git 忽略，评审不应依赖评审者拥有相同的本地 clone：每份归档都提供固定提交的上游链接和源码哈希。

| 项目 | 跟踪分支 | 更新后提交 | 本次结果 |
| --- | --- | --- | --- |
| Codex | `main` | `823ea830c0fd` | 已更新 |
| OpenCode | `dev` | `907b3bc518fa` | 已更新 |
| Pi | `main` | `b7dfc049e917` | 已更新 |
| Grok Build | `main` | `2bdd1d6a6369` | 已更新 |
| DeepSeek Harness | `master` | `5badb15009ae` | fetch 后确认已是最新 |
| 本地 claude-code | `main` | `a371abbe75ff` | fetch 后确认已是最新；不作为官方提示词来源 |

`references/claude-code` 的 origin 是 `yasasbanukaofficial/claude-code`，不能据此声称取得了 Anthropic 官方 Claude Code 的完整提示词。本轮遵照指定来源，只分析官方页面的 Opus 5.5、Sonnet 5.5 和 Fable 5.1。

### 42 份记录，各自说明“这份文字是什么”

[逐份索引](agent_system_prompts/README.md)含 42 份记录，每份有中英文文档：Codex 10、OpenCode 13、Pi 4、Grok Build 4、DeepSeek Harness 4、本项目基准 4、Claude 官方页面 3。它们不是 42 份可直接替换的主系统提示词。

- 开源项目原文按许可证保留，附来源文件、提取位置、文件和提取文本的 SHA256；[许可证及归档说明](../agent_system_prompts/README.md)随文保存。
- 静态字符串、模型模板、动态提醒、专用代理提示词、生成器源码和测试组装样本分别标注。模板占位符保留，未把不完整的静态片段拼成“实际运行时全量提示词”。
- 中文源文件提供中文解读，英文版本完整翻译解读；两种版本中的原文块都保留原始语言，以便逐字核对，不把译文冒充原文。
- 这是一组覆盖主要入口和相关专用职责的资料，不是所有仓库内全部工具描述、权限消息、技能、插件和用户指令的穷尽归档。Codex 中相同正文的模型条目合并为一份；正文不同的变体分别保存。OpenCode 的主提示词选择器所引用的十份正文全部保存。

官方 [system prompts overview](https://platform.claude.com/docs/en/release-notes/system-prompts/overview)明确说明其页面是 **claude.ai 与移动端**的提示词，并不适用于 API。这也不等于 Claude Code 的完整运行提示词。三份页面分别为 [Opus 5.5](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-opus-5-5)（2026-09-22）、[Sonnet 5.5](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-sonnet-5-5)（2026-09-28）、[Fable 5.1](https://platform.claude.com/docs/en/release-notes/system-prompts/claude-fable-5-1)（2026-09-01）。它们是带日期的网页版本，不具有本地提交固定的可重现性；本仓库保存原文入口、短引文和双语分析，未建立全文再发布许可，因此不复制其全文或全文翻译。

## 各项目的提示词包含什么

### Codex：持续执行、工程判断与协作协议

本轮主要读取更新后的 [`models.json`](https://github.com/openai/codex/blob/823ea830c0fd418b09ff02d36cad9a1fff66465b/codex-rs/models-manager/models.json) 中 `model_messages.instructions_template`，而不是只摘取旧目录里名字带 GPT 的文件。模型目录的 11 个条目对应 8 份不同正文；另外归档[通用回退](agent_system_prompts/codex/fallback.md)和[上下文压缩交接](agent_system_prompts/codex/compaction.md)。运行时仍可能使用远端模型目录、配置覆盖、权限与环境消息，静态目录不能证明每次请求实际使用了哪份文本。

主模板把授权范围、任务连续性、工具使用、恰当检查、进度沟通和最终报告放在一起。[6.1-sol](agent_system_prompts/codex/gpt-6.1-sol.md)具体说明用户中途消息和压缩后的上下文续接；[5.5](agent_system_prompts/codex/gpt-5.5.md)较多讨论工程取舍、修改范围和前端体验；[5.6-sol](agent_system_prompts/codex/gpt-5.6-sol.md)还对应三个正文完全相同的目录条目。不同模板的存在不能用来推断某种措辞的 benchmark 优势。

可借鉴的是：把行动请求推进到可交付状态，保留用户已经确定的约束，按风险选择检查，用实际结果说明完成程度，充分检查后停止。长篇交互风格、特定工具名、插件流程和权限 UI 依赖宿主能力，不能整体移植到 nanoPyCodeAgent 的 headless 模式。

### OpenCode：按模型选择工作方法，差异值得保留

[`session/system.ts`](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/session/system.ts)按模型标识选择不同正文；[`session/llm/request.ts`](https://github.com/anomalyco/opencode/blob/907b3bc518fa48e90e8ec24dd327d13eee71c36c/packages/opencode/src/session/llm/request.ts)还允许 `agent.prompt` 覆盖，并追加环境等内容。因此 OpenCode 没有一份适用于所有配置的主提示词。

| 正文 | 主要内容方向 | 迁移判断 |
| --- | --- | --- |
| [anthropic](agent_system_prompts/opencode/anthropic.md) | 编码任务执行、任务管理、工具和表达规范 | 任务持续跟踪有用；任务管理工具不是本项目已有能力 |
| [default](agent_system_prompts/opencode/default.md)、[gpt](agent_system_prompts/opencode/gpt.md) | 环境调查、代码约定、测试及 lint/typecheck、交付说明 | 先发现项目自己的检查入口；不能在 headless 中等待用户提供命令 |
| [gpt-astra](agent_system_prompts/opencode/gpt-astra.md)、[codex](agent_system_prompts/opencode/codex.md) | 自主推进、范围与权限判断、协作和输出规则 | 提炼执行与证据要求，避免复制产品流程 |
| [gemini](agent_system_prompts/opencode/gemini.md) | 理解、计划、实现、测试、遵循项目规范；检查依赖是否存在 | 适合形成简短工作循环，不强制每个任务写长计划 |
| [kimi](agent_system_prompts/opencode/kimi.md) | 行动后观察、读取错误、修复和复测，保持需求约束 | 可用于具体化当前“用工具检查” |
| [meta](agent_system_prompts/opencode/meta.md) | 先获取证据再综合，实际执行与独立检查，保留用户纠正 | 与本轮“完成判断需要证据”的问题接近 |
| [beast](agent_system_prompts/opencode/beast.md) | 高强度调查、执行、反复测试，广泛网络检索 | 不照搬所有任务联网、过大读取量和无界追求完美的要求 |
| [trinity](agent_system_prompts/opencode/trinity.md) | 明确身份、工具调用节奏、任务执行规则 | 一条消息一个工具等约束与其他模板不同，说明工具协议必须匹配宿主 |

另外归档[规划提醒](agent_system_prompts/opencode/plan-mode.md)、[探索代理](agent_system_prompts/opencode/explore.md)和[压缩代理](agent_system_prompts/opencode/compaction.md)。规划模式的只读约束、探索输出和压缩交接各有特定职责，不能同时拼接进执行代理。未在加载路径中找到引用的历史文件也不当成当前默认配置。

### Pi：保持核心简短，由工具和上下文提供细节

[编码提示词生成器](agent_system_prompts/pi/coding-system.md)按区段组合身份、可用工具、工具提供的指导、项目上下文、技能和环境。其默认编码身份较短；`customPrompt` 替换默认前缀，`forceSystemPrompt` 则提供完全覆盖，这两种入口不能混为一谈。

另三份是[摘要系统消息](agent_system_prompts/pi/summarization-system.md)、[压缩检查点任务](agent_system_prompts/pi/checkpoint.md)和[分支总结任务](agent_system_prompts/pi/branch-summary.md)。它们说明摘要应该保留目标、约束、进度和后续工作，并且不要继续执行被总结的任务。这属于上下文管理设计，不是给普通执行代理增加一句话就能得到的能力。

Pi 最适合本项目借鉴的地方是职责划分：核心指令保持集中，工具使用事实由真实工具能力支撑，动态信息在运行时提供。它本身的短核心并未给出一套完整的独立验证策略，不能把“短”或“长”单独当作有效性的证据。

### Grok Build：把交付、验收和证据分开表达

[主模板](agent_system_prompts/grok-build/main.md)有按运行环境启用的条件段，覆盖自主执行、需求范围、工具、进度、证据与结果表述；[子代理模板](agent_system_prompts/grok-build/subagent.md)定义受委派任务的边界和返回信息。两者依赖真实调度和工具能力，不能通过抄写文本获得多代理运行时。

本轮最相关的是[目标规划器](agent_system_prompts/grok-build/goal-planner.md)与[目标验证器](agent_system_prompts/grok-build/goal-verifier.md)：前者要求把目标写成有限、可独立检查的结果，规定验证动作和应该观察到的内容；后者区分实现缺陷、需求矛盾和无法验证，审查已有证据，避免不断新增验收标准。规划器还明确区分真实入口运行、主要输出内容与仅存在文件、能启动的弱证据。

可提炼为两个同样重要的原则：**验收要有力度，范围要有边界**。本项目可以在单个 agent 内采用这种完成判断，而无需先引入独立规划器或验证器。需要注意其具体浏览器、外部 CI、重复启动和交互审批规则依赖任务与环境，不应全部变成本项目每道任务都必须执行的步骤。

### DeepSeek Harness：提示词是插件组装结果

[headless 身份片段](agent_system_prompts/deepseek-harness/headless-persona.md)只有简短身份文本；[规划指导](agent_system_prompts/deepseek-harness/plan-policy.md)来自部署配置；[命令结果检查](agent_system_prompts/deepseek-harness/bash-result-check.md)由工具插件注册，要求执行后检查结果与退出状态。[组装样本](agent_system_prompts/deepseek-harness/assembled-session-fixture.md)展示多个区段如何一起出现，但它是已提交的测试快照，使用测试 persona，不能称为生产 headless 的默认全文。

[`system-prompt` 实现](https://github.com/deepseek-ai/deepseek-harness/blob/5badb15009ae1756c3afe0ae0cef1faafc290ccc/packages/core/system-prompt/src/index.ts)负责组装注册的区段。这说明主 persona 很短并不代表完整请求没有工程约束；也说明插件注册、区段更新和工具描述属于运行时设计。当前最容易迁移的是观察命令结果的具体指导，而不是先复制整个插件架构。

### Claude 官方页面：产品行为约束，而非编码工作循环

逐份记录见 [Opus 5.5](agent_system_prompts/claude/opus-5-5.md)、[Sonnet 5.5](agent_system_prompts/claude/sonnet-5-5.md)、[Fable 5.1](agent_system_prompts/claude/fable-5-1.md)。三个页面主要覆盖产品身份与知识边界、安全与健康支持、语气格式、可信上下文和纠错。它们的格式偏好有差异，但没有提供本项目所需的完整编码验证循环。

本研究从中提取的迁移方向是核对可检查的事实、避免无依据的断言、表达未验证范围和根据证据纠错。这是设计推断，不是对代码通过率的实验证明；产品政策和聊天风格不作为此次提示词优化的主体。

## 横向内容方向与当前差距

下表按“可指导什么行为”归类，不给项目打分；一份正文中出现某类要求，也不说明实际轨迹一定遵守。

| 方向 | 参考项目中的表达 | 当前 nanoPyCodeAgent | 优先级 |
| --- | --- | --- | --- |
| 身份、沟通、授权 | Codex、OpenCode、Grok、Claude 较多 | 简洁身份；headless 明确自主完成、不等待用户 | 保留，不作为首轮新增重点 |
| 需求与范围 | Codex 持续跟踪；Grok 有界验收；OpenCode 保留约束 | 要求完成任务，但未具体说明交付条件、一般要求与示例的关系 | 高 |
| 环境事实与工具选择 | Pi 工具指导；OpenCode 检查依赖与入口；DeepSeek 工具区段 | 已说明 read/edit/write/bash 分工，要求真实工具结果 | 中，补工作方法即可 |
| 执行与反馈循环 | Kimi、Gemini、Codex、Grok 强调推进、观察和修复 | 有自主执行，缺少形成可运行反馈的具体提醒 | 中，单独实验 |
| 独立与边界验证 | Meta、Gemini 的检查；Grok 的真实入口和输出验收 | 有“用工具检查”，未规定如何避免只验证可见示例或自证 | 最高 |
| 失败诊断与约束保持 | Kimi 修复复测；Grok 区分失败类别 | 工具能返回错误，主提示词没有展开诊断方法 | 高，与验证合并成小改动 |
| 完成、证据与停止 | Codex 恰当检查后交付；Grok 检查证据且限制范围 | 已有预算与停止要求；正常终态不代表任务正确 | 高，强化语义完成而不改变终态协议 |
| 上下文压缩、委派、插件 | Codex、Pi、OpenCode、Grok、DeepSeek 各有专用层 | 本项目没有对应完整运行时 | 后续独立设计，排除本轮纯提示词实验 |

### 本项目已有的四个层次

以本轮开始时 `c8c5bf7` 主线为基准，[交互主提示词](agent_system_prompts/nanopycodeagent/interactive.md)只有简短身份及四工具指导；[headless 主提示词](agent_system_prompts/nanopycodeagent/headless.md)额外要求自主执行、检查结果、保存交付物和及时结束。[预算提醒](agent_system_prompts/nanopycodeagent/budget-reminder.md)按剩余时间与回合动态追加，已经明确保留必要验证时间、停止可选探索，并说明最后一回合的工具不会执行。[截断恢复提醒](agent_system_prompts/nanopycodeagent/truncation-recovery.md)要求从已确认结果继续，预算和一次恢复上限由代码执行。

因此不能把现状描述为“没有验证”“没有预算意识”或“完全没有恢复”。新文本应补充这些行为的判断方法，保留固定主提示词加动态预算提醒的组织方式。代码中的 `completed` 是模型正常结束的运行状态，没有独立证明交付物符合任务要求；不能单靠更换这个状态名解决正确性问题。

## benchmark 证据：能推出什么，不能推出什么

| 实验 | 观察到的结果 | 对本轮研究的意义 |
| --- | --- | --- |
| [v0.9.0 冻结 baseline](../../../benchmarks/harbor/reports/v0.9.0-baseline-20261005.md) | 18/20；两次失败涉及输出截断等问题 | 保留原始基线，不能用后续最好结果覆盖 |
| [首次截断恢复实验](../../../benchmarks/harbor/reports/truncation-recovery-20261005.md) | 2/2 通过，均未触发恢复 | 不能据此证明恢复策略提高通过率 |
| [每题追加三次](../../../benchmarks/harbor/reports/truncation-recovery-repeat3-20261005.md) | 4/6 通过；全部 `completed`；唯一真实恢复继续工作并生成产物，仍未通过 verifier | 执行继续、产物存在、正常结束和语义正确是不同指标 |
| [双预算 pilot20](../../../benchmarks/harbor/reports/dual-budget-20260929.md) | 18/20 且全部 `completed`；一项数值任务自测通过但独立验证失败，另一项准确率未达标 | 验证质量和任务解法仍有缺口；诚实承认未达标也不等于通过 |

追加实验的两个模型提取失败主要检查可见实例；官方验证换用不同规模后暴露不完整性。开发笔记还记录了轨迹复核：通过的运行额外检查不同输入条件、模型规模和输出残差，并修复额外检查发现的问题。原始轨迹路径保存在实验的[结构化结果](../../../benchmarks/harbor/results/tb21-truncation-recovery-repeat3-20261005.json)，原始文件仍在被 Git 忽略的 `jobs/` 中。这里把该轨迹观察作为候选机制线索，不认定它是唯一因果解释，也不声称已确定两次失败的全部算法根因。

这些任务名和具体验证参数只用于解释历史证据。候选提示词不应出现它们，不应从隐藏 verifier 导入参数、特定算法或答案。可推广的要求是：示例可能只覆盖有效输入的一部分；验证应围绕公开任务契约，选择能挑战关键假设的检查。

长推理也需要谨慎解读：真实恢复样本在写出脚本前触及 65,536 token 上限，但通过样本也有 53,538 token 的长回复。现有数据支持研究“更早获得可运行反馈”，不支持直接规定很低的推理上限，更不能把缩短推理当成已经验证的收益。

## 建议的提示词优化顺序

### P0：需求、独立验证、失败诊断和完成证据

先形成一个小而连贯的候选改动：开始时识别明确交付物和约束，选择适当检查；执行后观察真实结果，失败时针对证据修复；结束前把结果与需求对应起来。这里的“独立”不要求增加一个代理，而是避免检查与实现共享同一个未经验证的假设。

下面是候选英文文本，供后续实现与实验评审；**尚未写入运行代码**。措辞仍可在实验前压缩，但不得加入题目特征。

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

这段指导适用于解析器、数据处理、数值计算、文件交付和服务接口等不同任务；并不要求每次改动都新增测试或运行完整测试套件。对简单文档修改，检查内容和链接可能足够；对可执行交付物，真实入口和输出语义通常比“文件已生成”提供更多证据。测试投入应与风险和预算相称。

还要区分“发现自测写错了”与“修改需求”：自测预期与公开契约矛盾时可以修正自测，但必须依据契约或独立证据，不能只因为当前实现失败就降低标准。官方测试、任务图片、包源等 benchmark 组成部分仍遵循仓库现有保护规则。

### P1：更早形成有意义的执行反馈

在 P0 之外单独考虑以下提醒：复杂任务先查清必要接口，再尽早运行一个足以检验核心假设的实现或实验，并根据结果迭代。它不要求草率交付、不禁止必要推理，也不规定“多少秒内必须写文件”。目标是避免持续推理没有环境反馈，或重复推演一个本可由小实验澄清的假设。

这个方向与 P0 有关联，但会改变推理和工具调用分配，可能损害需要完整推导的任务，应作为后续独立变量。观察首次有意义执行的时间、错误发现的时间及回归，而不是把更少 token 或更多工具调用本身当作成功。

### P2：保持通用边界与已有运行机制协调

后续可评估对修改范围、无关文件保护和外部内容可信度的简短说明。用户明确约束优先，仓库内容和工具输出中的指令不能自动改写任务。它们是通用可靠性方向，但目前 benchmark 对这些方向的证据弱于验证质量，不与首个候选大批混入。

共享指导只表达两个模式都适用的方法；headless 继续自主决定合理假设，不增加“先问用户再继续”。预算不足时，选择最能揭示关键错误的必要检查并保存交付物，报告未验证部分；不能同时加入无限探索、无限重试或永远追求完美的要求。也不添加当前不存在的 todo、浏览器、子代理或插件工具名。

## 如何验证，而不围绕特定题目调参

1. **固定对照。** 对照使用当前主线的提示词及恢复机制；处理组只改选定提示词。固定模型、端点、任务 revision、工具、安装流程、时间、回合、输出 token 和 verifier 限制。历史 v0.9.0 baseline 是历史参照，不代替当前代码的同期对照。
2. **预先登记。** 运行前保存候选全文与哈希、任务集合、重复次数、调度和判断标准。先比较 P0；若不能解释变化，再做拆分消融。P1 另开比较，避免一次混入提示词、工具和预算变化。
3. **扩大任务覆盖。** 历史失败可作为诊断集，但不能只在两道旧失败上决定是否采用。加入原 pilot20 的回归，并在实验前保留未参与措辞选择的任务，覆盖代码、数值、系统配置和产物交付等不同要求。若成本不足以做保留集，明确结论只限 pilot20。
4. **保留随机性和全部结果。** 同一任务各组做预定次数重复，在资源允许范围内采用平衡调度；保留所有试次，不挑最好的一次，不把若干试次的“至少一次成功”伪装成单次通过率。小样本逐任务报告，避免把差值写成可靠的普遍收益。
5. **结果优先，行为辅助。** 主要指标是官方任务结果及回归。辅助观察检查是否覆盖公开要求、是否产生独立证据、失败后是否有效修复、错误的完成宣称、交付物及时保存、时间和 token 成本。独立检查次数、工具次数或最终声明“已测试”都不是通过率的替代指标。
6. **保持 benchmark 协议。** 使用 `uv run --project benchmarks/harbor python -m harbor_adapter run --config <config.json>`；有注册 profile 的任务先做依赖预检，未支持的明确记录。安装失败、verifier 错误与评分失败分别统计。只有 verifier 超时可对同一产物重试，最多总共三次，每次沿用原始时限；不因 reward 为零重跑替换结果。

本轮已完成的是来源更新、逐份双语资料和优化假设。下一步可评审 P0 的最小文本改动与预登记实验；在取得同期对照结果前，不宣称提示词已经提升 agent 通用能力。
