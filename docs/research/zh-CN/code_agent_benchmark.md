# Code Agent Benchmark 调研

> 本文件为**手写中文源文件**（source of truth）；英文版 [`../en/code_agent_benchmark.md`](../en/code_agent_benchmark.md) 由其生成。

调研时间：2026-08-17。

模型发布公告里的分数只有放在「哪个 benchmark + 哪个 harness + 哪档 effort」这三件事一起看时才有意义。本文调研六个 2026 年的模型发布——DeepSeek-V4-Flash-0731、Claude Opus 5、GPT-5.6 Sol、Qwen3.8-27B、Kimi-K3、GLM-5.2——把它们报的 code agent 相关 benchmark 拉平成一张表，然后回答一个具体问题：nanoPyCodeAgent 想跑其中哪一个，还差什么。

**读数前的三条注意事项：**

1. **同一个 benchmark 在不同发布公告里的分数不可直接比。** 例如 Terminal-Bench 2.1 上的 Claude Fable 5：Terminal-Bench 官方榜（Claude Code harness）是 83.8%，OpenAI 公告里写 83.1%，Kimi-K3 模型卡里写 88.0%。差异来自 harness、effort 档位、采样次数和评测日期，不是抄错。
2. **harness 是分数的一部分。** 各家现在普遍用自研 harness 报分（DeepSeek Harness、Kimi Code、Claude Code、Codex），换 harness 掉 3～6 个点是常态。
3. **内部 benchmark 不可复现。** DSBench、QwenSWEBench、Kimi Code Bench、CursorBench、Frontier-Bench 都是厂商自持数据集，只能当趋势看。

## 一、全景表：谁报了什么

| Benchmark | 类别 | DeepSeek-V4-Flash-0731 | Opus 5 | GPT-5.6 Sol | Qwen3.8-27B | Kimi-K3 | GLM-5.2 |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: |
| Terminal-Bench 2.1 | 终端 agent | ✅ | ✅(三方) | ✅ | ✅ | ✅ | ✅ |
| SWE-bench Pro | 仓库级修 bug | — | — | ✅ | ✅ | — | ✅ |
| DeepSWE (v1.1) | 长时程工程 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| NL2Repo-Bench | 从零建仓库 | ✅ | — | — | ✅ | — | ✅ |
| ProgramBench | 从二进制重建程序 | — | — | — | — | ✅ | ✅ |
| SWE-Marathon | 超长时程 | — | — | — | — | ✅ | ✅ |
| FrontierSWE | 长时程 + 性能/研究 | — | — | — | — | ✅ | ✅ |
| Frontier-Bench v0.1 | 终端 agent（Anthropic 内部） | — | ✅ | — | — | — | — |
| CursorBench 3.2 | IDE 内多文件（Cursor 内部） | — | ✅ | — | — | — | — |
| AA Coding Agent Index | 复合指数 | — | ✅ | ✅ | — | — | — |
| PostTrainBench | ML 后训练工程 | — | — | — | — | ✅ | ✅ |
| MLS-Bench-Lite | ML 方法研究 | — | — | — | — | ✅ | — |
| CyberGym | 安全（漏洞复现） | ✅ | — | ✅ | — | — | — |
| Agents' Last Exam | 通用 agent | ✅ | — | ✅ | ✅ | — | — |
| AutomationBench | 业务流程自动化 | ✅ | ✅ | — | — | ✅ | ✅ |
| Toolathlon / Tool-Decathlon | 工具使用 | ✅ | — | — | — | — | ✅ |
| MCP-Atlas | MCP 工具使用 | — | — | — | — | — | ✅ |
| JobBench | 职业任务 | — | — | — | ✅ | ✅ | — |
| CoWorkBench | 长时程办公 | — | — | — | ✅ | — | — |
| LiveCodeBench v6 | 竞赛代码生成 | — | — | — | ✅ | — | — |
| SciCode | 科研代码 | — | — | — | — | ✅ | — |
| OSWorld (2.0 / Verified) | 计算机操作 | — | ✅ | ✅ | ✅ | — | — |
| 内部集 | — | DSBench-FullStack / Hard | — | — | QwenSWEBench | Kimi Code Bench 2.0 | — |

一句话结论：**Terminal-Bench 2.1 和 DeepSWE 是当前唯一被六家全部采纳的两个 code agent benchmark**，是横向比较的事实标准；SWE-bench Pro 是次一档的共识项。

## 二、Benchmark 逐个说明

### 2.1 终端 / CLI Agent

#### Terminal-Bench (2.1)

- **主页**：<https://www.tbench.ai/>，运行框架 Harbor：<https://www.harborframework.com/>
- **论文**：[arXiv:2601.11868](https://arxiv.org/abs/2601.11868)
- **介绍**：Stanford × Anthropic 合作的终端能力 benchmark，衡量 agent 在真实命令行环境里完成硬任务的能力。任务按领域（system-administration、security、data-science、software-engineering、ML）和难度（medium / hard）分类，2.0 版含 89 个任务，2.1 是受 Z.ai 的「Terminal-Bench 2.0 Verified」启发做的修订版。每个任务跑在独立 Docker 容器里，容器内需要 tmux，由测试脚本判定成功与否。
- **harness**：官方基线 harness 叫 **Terminus 2**；榜单同时接受 Claude Code、Codex、Cursor CLI、Gemini CLI、mini-SWE-agent 等外部 harness，因此榜单条目是「harness + 模型」的组合。
- **示例任务**：`openssl-selfsigned-cert`——生成自签名证书、配套脚本和校验文件，且文件权限和格式都要符合要求。难档任务包括编译 Linux 内核、训练一个 ML 模型。
- **官方榜（Terminal-Bench 2.1，节选）**：Claude Code + Fable 5 = 83.8% ±1.2；Codex + GPT-5.5 = 83.1% ±1.1；Terminus 2 + Fable 5 = 80.4% ±1.2；Cursor CLI + Grok 4.5 = 79.3% ±1.5；Claude Code + Opus 4.8 = 78.9% ±1.3。

#### Frontier-Bench v0.1

- **主页**：无公开主页（Anthropic 内部数据集），第三方汇总见 <https://llm-stats.com/benchmarks/frontier-bench-v0.1>
- **介绍**：Anthropic 在 Opus 5 发布时启用的新 agentic 终端编码 benchmark，被描述为 Terminal-Bench 2.1 的后继者，74 个任务，覆盖多文件改动、调试、功能开发。
- **harness**：mini-SWE-agent + GKE 后端，每题 5 次尝试取平均 reward。
- **示例**：官方博客提到一个任务里 Opus 5 自己写了一条计算机视觉流水线、在没有直接视觉输入的情况下重建 3D 模型——说明任务是开放式的「给目标、不给方法」。

#### CursorBench (3.2)

- **主页**：<https://cursor.com/blog/cursorbench>
- **介绍**：Cursor 自研的 IDE 内编码 agent 评测集，任务来自 Cursor 生产环境里真实的开发者-agent 会话，覆盖多文件项目、monorepo 和含糊的口语化需求。评的是「模型 + Cursor harness」的组合，不是裸模型。每个模型在多档 reasoning effort 下评测，榜单同时报正确率、平均成本、token 用量和 agent 步数。3.2 版含 42 个配置。
- **局限**：厂商自评、harness 不可独立复现。

#### AA Coding Agent Index (v1.1)

- **主页**：<https://artificialanalysis.ai/agents/coding-agents>，方法论 <https://artificialanalysis.ai/methodology/coding-agents-benchmarking>
- **介绍**：Artificial Analysis 的复合指数，明确以「harness + 模型」为评测单位。由三个子项等权合成：**SWE-Bench-Pro-Hard-AA**（150 个来自 Scale AI SWE-bench Pro 的任务）、**Terminal-Bench v2**（84 个终端任务）、**SWE-Atlas-QnA**（124 道技术问答）。每题跑 3 次取平均得 pass@1，再对任务等权平均。同时公布成本、token 用量和墙钟耗时。

### 2.2 仓库级软件工程

#### SWE-bench Verified

- **主页**：<https://www.swebench.com/>
- **介绍**：SWE-bench 的人工校验子集，500 个实例。给定一个真实仓库快照和一个 GitHub issue，agent 要产出能让隐藏测试通过的补丁。是这一类的老基线，目前头部模型已到 90%+，区分度下降，但仍是最容易上手的入口。

#### SWE-bench Pro

- **主页**：<https://scale.com/blog/swe-bench-pro>，榜单 <https://labs.scale.com/leaderboard/swe_bench_pro_public>，代码 <https://github.com/scaleapi/SWE-bench_Pro-os>
- **介绍**：Scale AI 做的 SWE-bench 接棒者，针对四个问题设计：数据污染、任务多样性不足、问题被过度简化、测试不可复现。共 1865 个实例（731 公开 / 858 私有 / 276 商业），来自 41 个仓库（11 公开 / 12 私有 / 18 来自企业初创公司）。任务形式仍是「仓库 + issue → 补丁」，但是长时程、跨文件的难题。
- **难度参照**：刚发布时 GPT-5 与 Claude Opus 4.1 只有 23.3% / 23.1%（同期 Verified 上普遍 70%+）。

#### DeepSWE (v1.1)

- **主页**：<https://deepswe.datacurve.ai/>，代码 <https://github.com/datacurve-ai/deep-swe>，数据 <https://huggingface.co/datasets/datacurve/deep-swe>
- **论文**：[arXiv:2607.07946](https://arxiv.org/abs/2607.07946)
- **介绍**：Datacurve 出的长时程工程任务集，113 个任务，取自活跃开源仓库，覆盖 TypeScript、Go、Python、JavaScript、Rust。每题一个隔离环境和一个程序化 verifier。v1.1 相对 v1 没换任务，改的是执行与评分方式——在干净隔离环境里对 agent 提交的代码打分，让结果可复现、可审计。
- **harness**：官方榜统一用 **mini-swe-agent**（在 Modal 上由 Pier 驱动），这是「同一 harness 横向比模型」的少数样板。
- **v1.1 榜单（节选）**：Claude Opus 5 = 74.0%，GPT-5.6 Sol = 72.7%，Grok 4.6 = 67.0%，Gemini 3.7 Flash = 65.0%，DeepSeek V4 Pro 0813 = 63.0%。

#### FrontierSWE

- **主页**：<https://www.proximal.so/blog/frontierswe>，代码 <https://github.com/Proximal-Labs/frontier-swe>，第三方榜 <https://epoch.ai/benchmarks/frontierswe>
- **介绍**：Proximal Labs 的超长时程编码 benchmark，覆盖三类任务：功能实现、性能工程、研究型任务。
- **计分方式特殊**：主指标是 **dominance**——在单个任务上对随机对手的成对胜率，0～1 区间，不是「完成了百分之多少的任务」。看这个 benchmark 的分数时要留意这一点。

#### SWE-Marathon

- **主页**：论文 [arXiv:2606.07682](https://arxiv.org/abs/2606.07682)，第三方榜 <https://llm-stats.com/benchmarks/swe-marathon>
- **介绍**：Abundant AI 的超长时程任务集，只有 20 个任务，但每个都是项目级：产品克隆、库重写、ML 工程。每题配一个可执行环境、一份人写的参考实现和一套多层校验。**记录到的 agent 轨迹平均 2720 万 token**，量级远超其他 SWE / 命令行 benchmark。
- **有意思的观察**：13.8% 的 rollout 里出现了 reward hacking——agent 试图绕过环境或 verifier 而不是真做任务。失败模式集中在自我校验差、自称任务不可行、过早终止。

#### NL2Repo-Bench

- **主页**：论文 [arXiv:2512.12730](https://arxiv.org/abs/2512.12730)
- **介绍**：ByteDance Seed 等机构做的仓库生成 benchmark，104 个任务，覆盖九类 Python 库。**给 agent 的只有一份自然语言需求文档和一个空工作区**，agent 要自己设计架构、管理依赖、实现多模块逻辑，最终产出一个能安装的 Python 库；评测方式是跑上游项目原本的 pytest 套件，再加结构一致性和跨文件架构校验。
- **难度**：SOTA 平均测试通过率不到 40.5%。失败模式：过早终止、全局一致性丢失、跨文件依赖脆弱、几百步交互中规划不足。

#### ProgramBench

- **主页**：<https://programbench.com/>，论文 [arXiv:2605.03546](https://arxiv.org/abs/2605.03546)
- **介绍**：**给 agent 一个编译好的可执行文件加它的用法文档，要求从零写出行为一致的程序。** 没有方法签名、没有类骨架、没有 PRD、没有文件布局说明——语言、架构、构建脚本全由 agent 自己定。200 个任务，24.8 万条行为测试，规模从 `jq` 到 SQLite、PHP、FFmpeg。
- **难度**：全部前沿模型的「完全解决」率都是 0%。因此发布公告里的 ProgramBench 分数是部分测试通过率，不是任务完成率。也有批评指出其 harness 缺上下文管理，对 Claude Code / Codex 这类会跑很长的 harness 不够公平。

### 2.3 ML / 科研工程

#### PostTrainBench

- **主页**：<https://github.com/aisa-group/PostTrainBench>，论文 [arXiv:2603.08640](https://arxiv.org/abs/2603.08640)，第三方榜 <https://epoch.ai/benchmarks/post-train-bench>
- **介绍**：衡量 CLI agent 能否自主给一个 1～4B 的基座模型做后训练：**一张 H100、10 小时窗口**，目标是提高该模型在指定 benchmark 上的表现。用什么数据、怎么微调、怎么分配算力全自由，不给起始代码，不允许人介入。评测经 Harbor 编排的 E2B 沙箱执行，训练与推理走共享的 Tinker 服务。
- **特别之处**：这是少数**直接以「CLI 脚手架」为评测对象**的 benchmark——官方跑 Claude Code、Codex CLI、Gemini CLI、OpenCode 四种脚手架。当前结论：AI 平均约 28%，人类工程团队约 51%。

#### MLS-Bench / MLS-Bench-Lite

- **主页**：论文 [arXiv:2605.08678](https://arxiv.org/abs/2605.08678)，第三方榜 <https://llm-stats.com/benchmarks/mls-bench-lite>
- **介绍**：140 个任务、12 个 ML 领域，评的是 AI 系统能否产出**真正可迁移的 ML 方法改进**（不是调参涨点）。每题要求在受控的编辑范围内改进某个指定组件，并配有复现过的强人类基线。Lite 是官方 30 题子集，覆盖 LLM 预训练/后训练、机器人、世界模型、CV、RL、优化、ML 系统、AI for Science。
- **注意**：不要和 OpenAI 的 **MLE-bench**（75 个 Kaggle 竞赛，Lite 为 22 个）搞混，两者不同。

#### SciCode

- **主页**：<https://scicode-bench.github.io/>，代码 <https://github.com/scicode-bench/SciCode>，论文 [arXiv:2407.13168](https://arxiv.org/abs/2407.13168)
- **介绍**：科学家策划的科研编码 benchmark，从真实研究问题转写而来，覆盖物理、数学、材料、生物、化学 6 个领域 16 个子领域，80 个主问题拆成 338 个子问题，带科学背景说明和科学家标注的金标准解与测试用例。偏「模型的科学编码能力」，不太考验 agent 循环。

#### LiveCodeBench (v6)

- **主页**：<https://livecodebench.github.io/>
- **介绍**：持续从 LeetCode、AtCoder、Codeforces 收新题的无污染竞赛编码评测，除代码生成外还评自修复、代码执行、测试输出预测。同样偏模型能力，不测 agent 循环。

### 2.4 安全

#### CyberGym

- **主页**：<https://www.cybergym.io/cybergym/>，论文 [arXiv:2506.02548](https://arxiv.org/abs/2506.02548)
- **介绍**：大规模真实漏洞分析评测，1507 个历史漏洞实例，来自 Google OSS-Fuzz，覆盖 188 个 C/C++ 项目。主任务是**漏洞复现**：给 agent 一段文字描述和打补丁前的代码库，要它写出能触发该漏洞的 PoC。该 benchmark 的构建过程本身发现了 35 个 0-day 和 17 个不完整补丁。
- **相关**：同组还有 ExploitGym（<https://www.cybergym.io/exploitgym/>，把漏洞变成可用攻击）和 ExploitBench（能力阶梯式的 LLM 安全 agent 评测）。

### 2.5 通用 Agent / 工具使用

#### Agents' Last Exam (ALE)

- **主页**：<https://agents-last-exam.org/>，代码 <https://github.com/rdi-berkeley/agents-last-exam>，论文 [arXiv:2606.05405](https://arxiv.org/abs/2606.05405)
- **介绍**：Berkeley RDI 联合 250～300 位行业专家做的大规模 agent 评测，围绕 55 个子行业（归为 13 个行业簇）组织，已收 1000～1500+ 任务，目标 5000。**每个任务由确定性脚本对照专家自己的交付物打分，不用 LLM 当裁判。** 采用滚动评测：每约 6 个月发一批新的公开子集，私有任务轮换进、退役的公开任务轮换出，以抑制泄漏。
- **难度**：最难档远未饱和，主流 harness + 骨干模型组合的平均完全通过率为 2.6%。

#### AutomationBench (Zapier)

- **主页**：<https://zapier.com/benchmarks>，代码 <https://github.com/zapier/AutomationBench>，论文 [arXiv:2604.18934](https://arxiv.org/abs/2604.18934)
- **介绍**：评 agent 通过 REST API 做跨应用工作流编排，47 个真实工具，覆盖销售、市场、运营、支持、财务、HR 六大业务职能，任务模式取自 Zapier 平台上每月 20 亿+ 任务、370 万家公司的真实流量。一个任务可能横跨 CRM、收件箱、日历和 IM，agent 要自己发现端点、遵守一份策略文档、把正确数据写进每个系统。
- **评分**：确定性终态断言（不用 LLM 裁判），含正向和负向断言；差一点也算失败。

#### Toolathlon / The Tool Decathlon

- **主页**：<https://github.com/hkust-nlp/Toolathlon>（另有 toolathlon.xyz），论文 [arXiv:2510.25726](https://arxiv.org/abs/2510.25726)（ICLR 2026）
- **介绍**：HKUST NLP 做的工具使用评测，覆盖 **32 个软件应用、604 个工具**，从 Google Calendar、Notion 到 WooCommerce、Kubernetes、BigQuery。108 个人工构造任务，平均需要约 20 轮跨应用交互，每题有专门的校验脚本。
- **难度参照**：论文里最好的 Claude-4.5-Sonnet 只有 38.6% 成功率。DeepSeek 公告中的「Toolathlon-Verified」和 GLM 公告中的「Tool-Decathlon」都指这个 benchmark。

#### MCP-Atlas

- **主页**：<https://github.com/scaleapi/mcp-atlas>，论文 [arXiv:2602.00933](https://arxiv.org/abs/2602.00933)
- **介绍**：Scale AI 做的 MCP 工具能力评测，**1000 个由人类专家撰写并校验的自然语言任务，覆盖 36 个真实 MCP server、220 个工具**。提示里不说用哪个 server、哪个工具、什么参数，agent 要在语义相近的干扰项中自己找工具，并跨 server 组合多步流程。用 claim-level rubric 打分：把最终答案拆成基于工具输出的原子事实逐条核对，从而与 agent 的啰嗦程度和文风解耦。公开子集 500 题。

#### JobBench

- **主页**：论文 [arXiv:2605.26329](https://arxiv.org/abs/2605.26329)，榜单 <https://www.vals.ai/benchmarks>
- **介绍**：130 个 agentic 任务，覆盖 35 个职业。设计思路是「对齐人的委派意愿」而不是「按 GDP 价值替代人」：任务建在 Workbank 之上——一份 1500+ 名劳动者填写的、说明自己希望把哪些职责交给 AI 的调查——从「高委派意愿 × 高经济暴露」的交集里挑出 35 个职业。每题打包成一个含各类参考文件的工作区，输出由事实锚定的 rubric 链评分，平均每题 35.6 条二值判据。
- **难度参照**：最强组合 Claude Opus 4.7 + Claude Code 为 45.9%。

#### CoWorkBench

- **主页**：无公开主页，第三方汇总见 <https://llm-stats.com/benchmarks/coworkbench>
- **介绍**：长时程办公/生产力任务评测，覆盖计算机科学、金融、法律、医疗等领域。不是编码题，而是专业工作流：调研一个主题、从多个来源综合信息。评测配置为 256K 上下文、8 小时超时。

### 2.6 计算机操作与多模态（顺带记录）

这几个不是 code agent benchmark，但在同一批公告里出现，便于对照：

- **OSWorld 2.0 / OSWorld-Verified**——真实操作系统里的计算机操作任务。
- **WebArena-Verified**——浏览器操作。
- **AndroidWorld**——移动端操作。
- **BrowseComp**——agentic 网页检索。
- **RecreationBench**（复刻应用）、**Vision2Web**（[arXiv:2603.26648](https://arxiv.org/abs/2603.26648)，视觉驱动的网站开发）、**SWE-MM**（多模态软件工程）、**ClawEval-MM**（多模态工具使用）——Qwen3.8-27B 视觉侧报的几项，其中前三项与「看图写代码」相关。

### 2.7 厂商内部集

只作趋势参考，无法复现：**DSBench-FullStack / DSBench-Hard**（DeepSeek，后者专注困难编码 agent 问题）、**QwenSWEBench**（Qwen）、**Kimi Code Bench 2.0**（Moonshot）、**CursorBench**（Cursor）、**Frontier-Bench**（Anthropic）。

## 三、Harness 一览

harness（脚手架）决定了模型怎么看到工具、怎么管上下文、怎么决定停止。这是分数里最容易被忽略的变量。

| Harness | 归属 | 说明 |
| --- | --- | --- |
| **Terminus 2** | Terminal-Bench 官方 | Terminal-Bench 的基线 harness，跑在 Harbor 上 |
| **Harbor** | Terminal-Bench 生态 | 不是 agent，而是运行框架：Docker 隔离、任务编排、评分。要求 Python ≥3.12、Docker ≥20.10、Docker Compose ≥2.0，容器内需 tmux |
| **mini-SWE-agent** | Princeton | 极简 bash-first 控制流，性能接近完整 SWE-agent。DeepSWE 官方榜和 Anthropic 的 Frontier-Bench 都用它 |
| **SWE-agent / OpenHands** | 学界 / OSS | 仓库级 SWE benchmark 的常用脚手架；GLM-5.2 的 SWE-bench Pro 走 OpenHands |
| **Claude Code** | Anthropic | 被广泛用作第三方模型的评测 harness（Qwen3.8、GLM-5.2 都用它报分，GLM 甚至标注了 2.1.167 这个具体版本） |
| **Codex CLI** | OpenAI | GPT 系列的官方 harness；Kimi 报 GPT-5.6 Sol 的 FrontierSWE 分数时用它 |
| **Kimi Code** | Moonshot | Kimi-K3 自研 harness，模型卡里所有主分数都基于它 |
| **DeepSeek Harness** | DeepSeek | V4-Flash-0731 用其 **minimal mode** 报分（模型卡称将开源） |
| **Cursor CLI / Gemini CLI / OpenCode** | 各自厂商 | 出现在 Terminal-Bench 榜和 PostTrainBench 的四脚手架对照里 |

**对本项目的直接启示**：Terminal-Bench 和 PostTrainBench 这类 benchmark 是**面向 CLI agent** 设计的，nanoPyCodeAgent 这种「一个可执行 CLI + 几个内置工具」的形态天生适配；而 SWE-bench 家族是**面向 patch** 设计的，接入时只需要在结束时产出 `git diff`。

## 四、各模型发布时的 benchmark 与得分

以下表格尽量照抄各自发布材料。同一 benchmark 跨表不可比（见开头注意事项）。

### 4.1 DeepSeek-V4-Flash-0731

- **来源**：<https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731>
- **模型名**：`deepseek-ai/DeepSeek-V4-Flash-0731`
- **harness**：公开 benchmark 中的 Code Agent 任务使用 **DeepSeek Harness 的 minimal mode**，`max` reasoning effort，`temperature=1.0`、`top_p=0.95`

| Benchmark | V4-Flash-0731 | V4-Flash (Preview) | V4-Pro (Preview) | GLM-5.2 | Opus 4.8 |
| --- | :-: | :-: | :-: | :-: | :-: |
| Terminal Bench 2.1 | 82.7 | 61.8 | 72.1 | 81.0 | 85.0 |
| NL2Repo | 54.2 | 39.4 | 38.5 | 48.9 | 69.7 |
| CyberGym | 76.7 | 38.7 | 52.7 | — | 83.1 |
| DeepSWE | 54.4 | 7.3 | 12.8 | 46.2 | 58.0 |
| Toolathlon-Verified | 70.3 | 49.7 | 55.9 | 59.9 | 76.2 |
| Agents' Last Exam | 25.2 | 15.8 | 16.5 | 23.8 | 25.7 |
| AutomationBench Public | 25.1 | 10.8 | 12.8 | 12.9 | 27.2 |
| DSBench-FullStack† | 68.7 | 37.0 | 41.8 | 61.8 | 71.6 |
| DSBench-Hard† | 59.6 | 25.8 | 31.1 | 54.5 | 71.7 |

† 内部测试集；DSBench-Hard 专注困难编码 agent 问题。

### 4.2 Claude Opus 5

- **来源**：<https://www.anthropic.com/news/claude-opus-5>
- **模型名**：`claude-opus-5`
- **harness**：Frontier-Bench 用 **mini-SWE-agent + GKE 后端**，每题 5 次尝试取平均 reward。模型带 effort 档位（low / medium / high / max），公告中的对比多在 max effort 下。Opus 5 与 Fable 5 的评测中，安全分类器拒答时以 Opus 4.8 作为兜底。
- **重要说明**：Anthropic 官方发布页**大量使用相对表述而非绝对数字**，且**没有报 SWE-bench Verified / SWE-bench Pro / Terminal-Bench**。

官方公告中的表述：

| Benchmark | Opus 5 表现（官方原义） |
| --- | --- |
| Frontier-Bench v0.1 | SOTA，超过 Fable 5，是 Opus 4.8 的两倍以上 |
| CursorBench 3.2 | max effort 下与 Fable 5 峰值分数差距在 0.5% 以内，成本只有一半 |
| AA Coding Agent Index | 榜首 |
| ARC-AGI 3 | 次优模型的 3 倍 |
| Zapier AutomationBench | 同等每任务成本下通过率约为次优模型的 1.5 倍；churn-prevention 序列 100% 通过 |
| OSWorld 2.0 | 超过 Fable 5，成本仅约三分之一 |
| GDPval-AA v2 / HLE / DeepSearchQA | 领先 |
| 生命科学 | 全项优于 Opus 4.8；有机化学 +10.2pt，蛋白功能预测 +7.7pt |
| OSS-Fuzz | 漏洞识别与 Mythos 5 相当，漏洞利用开发明显落后 |

三方来源补充的具体数字（**非官方，谨慎引用**）：

| Benchmark | Opus 5 | 对照 | 来源 |
| --- | :-: | --- | --- |
| Frontier-Bench v0.1 | 43.3% | Fable 5 33.7%、Opus 4.8 18.7% | [Vellum](https://www.vellum.ai/blog/claude-opus-5-benchmarks-explained)、[llm-stats](https://llm-stats.com/benchmarks/frontier-bench-v0.1) |
| DeepSWE v1.1 | 74.0% | GPT-5.6 Sol 72.7% | [DeepSWE 官方榜](https://deepswe.datacurve.ai/) |
| Terminal-Bench 2.1 | 89.1%（max effort） | GPT-5.6 Sol xhigh 89.5% | [Artificial Analysis](https://artificialanalysis.ai/evaluations/terminalbench-v2-1) |
| SWE-bench Verified | 97%（聚合站数据，未见官方确认） | — | [morphllm](https://www.morphllm.com/claude-benchmarks) |

### 4.3 GPT-5.6 Sol

- **来源**：OpenAI 2026-07-09 发布公告 <https://openai.com/index/gpt-5-6/>（该页对本次抓取返回 403，下表转引三方对该公告的整理）
- **模型名**：`gpt-5.6-sol`，另有 Sol Ultra 档以及同族 Terra / Luna
- **harness**：公告未在转引材料中明示编码 benchmark 的 harness；OpenAI 系列惯例是 Codex CLI。Sol Ultra 对应更高的 reasoning effort。

| Benchmark | Sol | Sol Ultra | Terra | Luna | 对照 |
| --- | :-: | :-: | :-: | :-: | --- |
| Terminal-Bench 2.1 | 88.8% | 91.9% | 87.4% | 84.7% | GPT-5.5 85.6%、Fable 5 83.1%、Opus 4.8 78.9% |
| SWE-bench Pro | 64.6% | — | 63.4% | 62.7% | Mythos 5 80.3%、Fable 5 80.0%、GPT-5.5 59.4% |
| DeepSWE v1.1 | 72.7% | — | 69.6% | 67.2% | Fable 5 69.7%、GPT-5.5 67.0%、Opus 4.8 59.0% |
| AA Coding Agent Index v1.1 | 80 | — | 77.4 | 74.6 | Fable 5 77.2、GPT-5.5 76.4、Opus 4.8 72.5 |
| Agents' Last Exam | 52.7% | — | 50.4% | 50.3% | GPT-5.5 46.9%、Opus 4.8 45.2%、Fable 5 40.5% |
| BrowseComp | 90.4% | 92.2% | 87.5% | 83.3% | Mythos 5 88.0%、GPT-5.5 84.4% |
| OSWorld 2.0 | 62.6% | — | 50.2% | 45.6% | Opus 4.8 54.8%、GPT-5.5 47.5% |
| ExploitBench | 73.5% | — | — | — | GPT-5.5 47.9% |
| CyberGym | 84.5% | — | — | — | — |
| ARC-AGI-3 | 7.78% | — | 0.80% | 0.18% | Opus 4.8 1.5%、GPT-5.5 0.43% |
| AA Intelligence Index v4.1 | 58.9 | — | 55.0 | 51.2 | Fable 5 59.9、Opus 4.8 55.7 |
| GPQA Diamond | 94.6% | — | 92.9% | 92.3% | Fable 5 92.6%、GPT-5.5 93.6% |

**一条需要记录的风评**：METR 报告称 Sol 在其软件工程评测中出现了该机构历史上检出率最高的 evaluation gaming——利用评测 bug、抽取隐藏测试答案、用能满足指标但没真正完成任务的捷径替代实现。这提醒我们自建 benchmark 时必须做 reward hacking 检查（SWE-Marathon 也观察到 13.8% 的 rollout 有此行为）。

### 4.4 Qwen3.8-27B

- **来源**：<https://huggingface.co/Qwen/Qwen3.8-27B>
- **模型名**：`Qwen/Qwen3.8-27B`
- **harness**：多数编码项使用 **Claude Code harness**，`temperature=1.0`、`top_p=0.95`、256K 上下文；Terminal Bench 2.1 用 **Terminus**；NL2Repo 额外施加了 bash 限制；QwenSWEBench 为 avg@3、8 小时超时

| 分类 | Benchmark | 得分 | 备注 |
| --- | --- | :-: | --- |
| 编码 | Terminal Bench 2.1 (Terminus) | 73.0 | |
| 编码 | SWE-bench Pro | 61.7 | Claude Code harness |
| 编码 | NL2Repo-Bench | 42.3 | Claude Code harness，加 bash 限制 |
| 编码 | DeepSWE 1.1 | 42.2 | Claude Code harness |
| 编码 | QwenSWEBench | 79.0 | 内部集，avg@3，8h 超时 |
| 编码 | LiveCodeBench v6 | 90.3 | |
| Agent | CoWorkBench | 70.7 | |
| Agent | JobBench | 33.4 | |
| Agent | Agents' Last Exam | 20.4 (Pass@1) / 42.9 (Score) | |
| 通用 | IFBench | 79.5 | |
| 通用 | GPQA Diamond | 89.2 | |
| 通用 | HLE | 30.8 | GPT-4o 判分 |
| 视觉 | OSWorld-Verified | 84.3 | 计算机操作 |
| 视觉 | WebArena-Verified | 64.8 | 浏览器操作 |
| 视觉 | AndroidWorld | 81.9 | 移动端操作 |
| 视觉 | RecreationBench | 47.1 | 复刻应用 |
| 视觉 | ClawEval-MM | 57.4 (Pass@3) | 多模态工具使用 |
| 视觉 | SWE-MM | 38.6 | 多模态软件工程 |
| 视觉 | Vision2Web | 62.9 | 视觉驱动的网站开发 |

### 4.5 Kimi-K3

- **来源**：<https://huggingface.co/moonshotai/Kimi-K3>
- **模型名**：`moonshotai/Kimi-K3`
- **harness**：主分数用自研 **Kimi Code harness**；对照分数的来源逐项标注（见备注列）

| Benchmark | Kimi K3 | Fable 5 | GPT-5.6 Sol | Opus 4.8 | GPT-5.5 | GLM-5.2 | 备注 |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | --- |
| DeepSWE | 67.5 | 70.0 | 73.0 | 59.0 | 67.0 | 46.2 | K3 用 Kimi Code；GLM-5.2 取自其发布博客；其余取自官方榜（v1.1 任务） |
| Terminal-Bench 2.1 | 88.3 | 88.0 | 88.8 | 84.6 | 83.4 | 82.7 | K3 用 Kimi Code；其余取各 harness 中最好成绩 |
| ProgramBench | 77.8 | 76.8 | 77.6 | 71.9 | 70.8 | 63.7 | K3 与 GLM-5.2 用 Kimi Code |
| SWE-Marathon | 42.0 | 35.0 | 39.0 | 40.0 | 14.0 | 13.0 | Claude Code harness；H20 校准分支 |
| FrontierSWE | 81.2 | 86.6 | 71.3 | 66.7 | 64.9 | 67.3 | K3 用 Kimi Code；GPT-5.6 Sol 用 Codex |
| MLS-Bench-Lite | 48.3 | 49.9 | 46.2 | 42.8 | 35.5 | 40.4 | 混用多种 harness |
| SciCode | 58.7 | 60.2 | 56.1 | 53.5 | 56.1 | 50.5 | 引自 Artificial Analysis（2026-07-23） |
| Kimi Code Bench 2.0 | 72.9 | 76.9 | 64.8 | 71.7 | 69.0 | 64.2 | 内部集；max reasoning effort |
| PostTrainBench | 36.6 | 41.4 | 34.6 | 34.1 | 28.4 | 34.3 | 官方 Harbor 实现；3 次 H20 运行取平均 |
| BrowseComp | 91.2 | 88.0 | 90.4 | 84.3 | 84.4 | — | 300K token 处做上下文压缩 |
| AutomationBench | 30.8 | 29.1 | 29.7 | 27.2 | 22.7 | 12.9 | 官方 GitHub 配置；600 题公开子集 |
| JobBench | 54.3 | 57.4 | 45.4 | 48.4 | 38.3 | 43.4 | 取自 Vals AI |

### 4.6 GLM-5.2

- **来源**：<https://huggingface.co/zai-org/GLM-5.2>
- **模型名**：`zai-org/GLM-5.2`
- **harness（逐项标注，是本批公告里最透明的）**：
  - SWE-bench Pro → **OpenHands**，OpenAI 兼容 API，`temperature=1`、`top_p=1`、`max_new_tokens=32k`、400K 上下文
  - DeepSWE → 官方框架 + **mini-swe-agent**，2 小时超时，隔离沙箱（2 CPU / 8GB RAM）
  - Terminal-Bench 2.1（Terminus-2）→ **Terminus-2**，256K 上下文，沙箱 4 CPU / 8GB RAM
  - Terminal-Bench 2.1（Best Reported Harness）→ **Claude Code 2.1.167**，`temperature=1.0`、`top_p=0.95`、`max_new_tokens=131072`，无墙钟限制
  - FrontierSWE / PostTrainBench / SWE-Marathon → 1M 上下文，max effort，128K 输出

编码：

| Benchmark | GLM-5.2 | GLM-5.1 | Qwen3.7-Max | MiniMax M3 | DeepSeek-V4-Pro | Opus 4.8 | GPT-5.5 | Gemini 3.1 Pro |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| SWE-bench Pro | 62.1 | 58.4 | 60.6 | 59 | 55.4 | 69.2 | 58.6 | 54.2 |
| NL2Repo | 48.9 | 42.7 | 47.2 | 42.1 | 35.5 | 69.7 | 50.7 | 33.4 |
| DeepSWE | 46.2 | 18 | 18 | 20 | 8 | 58 | 70 | 10 |
| ProgramBench | 63.7 | 50.9 | — | — | 47.8 | 71.9 | 70.8 | 39.5 |
| Terminal Bench 2.1 (Terminus-2) | 81.0 | 63.5 | 75 | 65 | 64 | 85 | 84 | 74 |
| Terminal Bench 2.1 (最佳 harness) | 82.7 | 69 | — | — | — | 78.9 | 83.4 | 70.7 |
| FrontierSWE (Dominance) | 74.4 | 30.5 | — | — | 29.0 | 75.1 | 72.6 | 39.6 |
| PostTrainBench | 34.3 | 20.1 | — | — | — | 37.2 | 28.4 | 21.6 |
| SWE-Marathon | 13.0 | 1.0 | — | — | — | 26.0 | 12.0 | 4.0 |

Agent 与推理（节选）：

| Benchmark | GLM-5.2 | GLM-5.1 | DeepSeek-V4-Pro | Opus 4.8 | GPT-5.5 | Gemini 3.1 Pro |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| MCP-Atlas（公开集） | 76.8 | 71.8 | 73.6 | 77.8 | 75.3 | 69.2 |
| Tool-Decathlon | 48.2 | 40.7 | 52.8 | 59.9 | 55.6 | 48.8 |
| HLE | 40.5 | 31 | 37.7 | 49.8 | 41.4 | 45 |
| HLE（带工具） | 54.7 | 52.3 | 48.2 | 57.9 | 52.2 | 51.4 |
| AIME 2026 | 99.2 | 95.3 | 94.6 | 95.7 | 98.3 | 98.2 |
| GPQA-Diamond | 91.2 | 86.2 | 90.1 | 93.6 | 93.6 | 94.3 |

## 五、对 nanoPyCodeAgent 的 benchmark 推荐

评估口径：**跑得起来**（不需要 GPU / 不需要注册私有集 / 环境可本地复现）、**测的是 agent 循环而不是模型**（否则测的是 Claude 而不是本项目）、**能横向对照**（有别人用同一 benchmark 报过分）、**成本可控**。

### 第一优先：Terminal-Bench 2.1

最合适的第一个 benchmark，理由：

1. **形态天然匹配**。任务就是「在一个 Linux 容器里用命令行把事做成」，而本项目正好是 bash + read + write + edit 四件套。
2. **官方支持自定义 agent**。Harbor 提供 `--agent-import-path` 挂载自定义 agent，不必等官方适配。
3. **横向可比性最高**。六个模型发布全都报了它，且官方榜按「harness + 模型」列条目——这正是「同一模型换 harness 掉几分」的直接对照，能量化 nanoPyCodeAgent 相对 Claude Code / Terminus 2 的差距。
4. **成本可控**。可以先跑 10～20 题子集；`-k` 参数控制采样次数。

建议做法：先在本地跑 Terminus 2 + `claude-sonnet-4-6` 得到基线，再跑 nanoPyCodeAgent + 同一模型，两者之差就是 harness 差距，这比绝对分数更有信息量。

### 第二优先：SWE-bench Verified 子集

- 老基线、文档最全、patch 形式最简单（结束时 `git diff` 即可）。
- 缺点是每个实例一个 Docker 镜像，磁盘和拉取时间是主要成本，所以只跑 20～50 题子集。
- 价值在于验证 edit 工具的正确性：仓库级精确改动是 edit 工具的主战场。

### 第三优先：NL2Repo-Bench

- 只需要 Python + pytest，环境依赖在所有长时程 benchmark 里最轻。
- 「空工作区 + 一份规格 → 一个能安装的库」直接压测 write 工具和多文件规划能力，正好补 SWE-bench 只测局部修改的盲区。
- 104 题，可跑子集。

### 值得后续考虑

- **DeepSWE v1.1**：113 题，官方榜要求 mini-swe-agent 才能上榜，但可以自建 harness 自测；六家全报，对照价值高。
- **PostTrainBench**：唯一直接把「CLI 脚手架」当评测对象的 benchmark，未来若想论证「nanoPyCodeAgent 作为脚手架的质量」，它的四脚手架对照（Claude Code / Codex CLI / Gemini CLI / OpenCode）是最好的框架——但需要一张 H100 和 10 小时，现阶段不现实。

### 暂不建议

| Benchmark | 原因 |
| --- | --- |
| SWE-Marathon | 平均 2720 万 token/题，成本量级不合适 |
| ProgramBench | 全员完全解决率 0%，对本项目没有区分度 |
| MLS-Bench / PostTrainBench | 需要 GPU |
| CyberGym / ExploitGym | 需要 OSS-Fuzz 构建环境，且方向与本项目无关 |
| Agents' Last Exam | 大量私有任务，滚动评测，个人项目难以对齐 |
| Toolathlon / MCP-Atlas / AutomationBench | 需要 MCP / 多应用工具生态，本项目尚无 MCP 支持 |
| LiveCodeBench / SciCode / GPQA / HLE | 测模型不测 agent，跑了只是在测 Claude |

## 六、为了跑起来，项目还缺什么

现状（截至 v0.7.0）：`agent.py` 是一个交互式 REPL——`load_settings_env()` → `anthropic.Anthropic()` → `while True: input("You> ")`，内层再一个 `while True` 处理 tool_use 直到模型不再调工具。四个工具（read / write / edit / bash），`MAX_TOKENS = 8192`，无 CLI 参数，`main()` 直接调 `run()`。

好消息是有两件事已经做对了：`terminal.py` 的 ANSI 上色和 Spinner 都用 `sys.stdout.isatty()` 做了门控（`terminal.py:22`、`terminal.py:69`），所以在容器里不会喷转义序列；`bash_tool.py` 已有 120 秒超时和 20000 字符输出截断（`bash_tool.py:13-14`），并且把 stdin 设成 `/dev/null`（`bash_tool.py:61`），命令不会抢走 agent 的输入。

下面按优先级列出缺口。

### P0 — 不做就完全跑不起来

1. **非交互（headless）一次性任务模式**。这是最硬的阻塞项：benchmark 通过一条命令把任务描述交给 agent，跑完就退出。当前唯一入口是 `input()` 循环（`agent.py:146`），容器里 stdin 是 EOF，会立刻 `break` 打印 `Bye!` 退出，什么都不做。需要一个 CLI 层：`nanoPyCodeAgent -p "<任务>"`、`--prompt-file <path>`，或从 stdin 读整段。

2. **明确的终止条件与退出码**。正常完成 exit 0；超轮数、超时、API 连续失败 exit 非 0。`main()` 现在没有返回码概念（`__init__.py`）。

3. **轮数上限 + 墙钟超时**。`agent.py:158` 的内层 `while True` 没有任何上限，模型一旦陷入「反复试同一条命令」的循环就会一直烧钱到 API 报错。需要 `--max-turns` 和 `--timeout`。

4. **错误重试，不许崩**。模块 docstring 明说只处理 happy path、异常即崩溃（`agent.py:10-13`）。benchmark 里一次 429 / `overloaded_error` / 网络抖动就是整题 0 分。至少要给 `client.messages.stream` 加指数退避重试，并把单题失败收敛成「这题 0 分」而不是「整个 run 挂掉」。

5. **benchmark 化的系统提示词**。当前提示词面向对话助手（`agent.py:43-50`）。非交互模式下必须显式要求：不要向用户提问、不要停下来等确认、自己决策到底、完成后明确声明结束。这一条不改，分数会被「模型礼貌地询问下一步」大量吃掉。

6. **可配置的工作目录**。benchmark 在容器里指定工作目录（Terminal-Bench 常用 `/app`）。bash 工具每次开新 shell、`cd` 不跨调用保留（`bash_tool.py:39` 的 docstring 已说明），长任务里模型必须反复写绝对路径。需要 `--workdir`，并考虑让 bash 会话保留 cwd。

### P1 — 不做的话分数会很难看

7. **上下文管理 / compaction**。`messages` 列表只增不减（`agent.py:139`）。Terminal-Bench 的 hard 任务几十轮后必然打满上下文，然后 API 直接报错——这会被计成「任务失败」而不是「harness 缺陷」。参考各家做法：Kimi 在 300K token 处压缩上下文，GLM 用 256K～1M 上下文。最小可行方案是「工具结果二次截断 + 旧轮次摘要或丢弃」。

8. **Trajectory 落盘**。把每轮的 request/response、tool call 与结果、token 用量、耗时写成 JSONL。没有这个，一题失败只能看终端 scrollback 猜原因，无法归因也无法复现。

9. **token 与成本统计**。从 `message.usage` 累加输入/输出 token。现在的 benchmark 报告普遍同时看分数和 token 用量（AA Coding Agent Index、CursorBench 都报成本与步数），只有分数没有成本是不完整的。

10. **`MAX_TOKENS` 与 bash 超时可配**。8192 输出上限（`agent.py:42`）对长任务偏小——各家都在 128K 量级报分。`BASH_TIMEOUT_SECONDS = 120`（`bash_tool.py:13`）对「编译内核」「跑完整测试套件」这类 Terminal-Bench 任务不够。

11. **grep / glob 工具**。现在靠 bash 里的 `grep`，能用，但输出难以结构化截断，模型容易一次拉回上万行把上下文打满。仓库级任务（SWE-bench、NL2Repo）里专用的 Grep/Glob 明显更省 token。

### P2 — 想正式上榜或横向对比才需要

12. **Harbor agent adapter**。写一个 adapter：Jinja2 安装模板（容器内 `pip install nanoPyCodeAgent` 或 `uv tool install`）+ 一个 agent 类，把任务 instruction 交给 CLI，API key 通过环境变量注入。具体接口以 `harbor-framework/terminal-bench-2-1` 仓库的提交说明为准。

13. **OpenAI 兼容后端**。想跟 GLM / Kimi / Qwen / DeepSeek 对比就必须支持非 Anthropic 协议——GLM-5.2 的 SWE-bench Pro 就是走 OpenAI 兼容 API 报的。当前唯一依赖是 `anthropic`（`pyproject.toml`），靠 `ANTHROPIC_BASE_URL` 指代理只能部分绕过。

14. **patch 输出模式**。SWE-bench 家族要的是补丁：任务结束时把 `git diff` 写到指定文件或 stdout。

15. **thinking / reasoning effort 透传**。现在没传 `thinking` 参数。所有厂商都是在 max effort 下报分的，不透传就是自带劣势。

16. **批量运行器与多次采样**。`-k 5` 式的多次采样求均值是通行做法（Frontier-Bench 就是 5 次取平均），需要能并发跑多题并汇总。

17. **reward hacking 自查**。SWE-Marathon 观察到 13.8% 的 rollout 有 reward hacking，METR 报告 GPT-5.6 Sol 的 gaming 检出率创其历史新高。自建评测时要检查 agent 是不是改了测试、读了隐藏答案、或用捷径糊过了断言。

### 最小可行路径

一句话：**P0 全做 + P1 的第 7 与第 8 项**，就足够跑通 Terminal-Bench 2.1 的一个小子集并拿到可信数字。落成一条实现顺序：

1. 加 CLI 层与 headless 模式（P0-1、2、6）——这一步之后就能被脚本调用。
2. 加轮数上限、超时、重试（P0-3、4）——这一步之后单题失败不再毁掉整个 run。
3. 改 benchmark 化系统提示词（P0-5）。
4. 加 trajectory JSONL 与 token 统计（P1-8、9）——这一步之后失败可归因。
5. 加最简 compaction（P1-7）——这一步之后 hard 任务不再必然撞上下文墙。
6. 写 Harbor adapter（P2-12），跑 20 题子集，与 Terminus 2 + 同模型的基线对照。
