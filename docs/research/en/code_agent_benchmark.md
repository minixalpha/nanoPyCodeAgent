# Code Agent Benchmark Survey

> Generated from the Chinese source [`../zh-CN/code_agent_benchmark.md`](../zh-CN/code_agent_benchmark.md). Do not edit by hand.

Surveyed on 2026-08-17.

A score in a model release announcement only means something when you read it together with three things at once: which benchmark, which harness, and which effort level. This document surveys six 2026 model releases — DeepSeek-V4-Flash-0731, Claude Opus 5, GPT-5.6 Sol, Qwen3.8-27B, Kimi-K3, and GLM-5.2 — flattens the code-agent benchmarks they report into one table, and then answers a concrete question: which of them could nanoPyCodeAgent run, and what is still missing?

**Three caveats before reading any number:**

1. **The same benchmark is not directly comparable across announcements.** Take Claude Fable 5 on Terminal-Bench 2.1: the official leaderboard (Claude Code harness) says 83.8%, OpenAI's announcement says 83.1%, and the Kimi-K3 model card says 88.0%. The spread comes from harness, effort level, sampling count, and evaluation date — not from transcription errors.
2. **The harness is part of the score.** Vendors now routinely report with their own harness (DeepSeek Harness, Kimi Code, Claude Code, Codex), and swapping harnesses commonly moves a score by 3–6 points.
3. **Internal benchmarks are not reproducible.** DSBench, QwenSWEBench, Kimi Code Bench, CursorBench, and Frontier-Bench are all vendor-held datasets; treat them as trend indicators only.

## 1. The landscape: who reports what

| Benchmark | Category | DeepSeek-V4-Flash-0731 | Opus 5 | GPT-5.6 Sol | Qwen3.8-27B | Kimi-K3 | GLM-5.2 |
| --- | --- | :-: | :-: | :-: | :-: | :-: | :-: |
| Terminal-Bench 2.1 | Terminal agent | ✅ | ✅(3rd party) | ✅ | ✅ | ✅ | ✅ |
| SWE-bench Pro | Repo-level bug fixing | — | — | ✅ | ✅ | — | ✅ |
| DeepSWE (v1.1) | Long-horizon engineering | ✅ | ✅(3rd party) | ✅ | ✅ | ✅ | ✅ |
| NL2Repo-Bench | Repo generation from scratch | ✅ | — | — | ✅ | — | ✅ |
| ProgramBench | Rebuild a program from its binary | — | — | — | — | ✅ | ✅ |
| SWE-Marathon | Ultra-long-horizon | — | — | — | — | ✅ | ✅ |
| FrontierSWE | Long-horizon + perf/research | — | — | — | — | ✅ | ✅ |
| Frontier-Bench v0.1 | Terminal agent (Anthropic internal) | — | ✅ | — | — | — | — |
| CursorBench 3.2 | In-IDE multi-file (Cursor internal) | — | ✅ | — | — | — | — |
| AA Coding Agent Index | Composite index | — | ✅ | ✅ | — | — | — |
| PostTrainBench | ML post-training engineering | — | — | — | — | ✅ | ✅ |
| MLS-Bench-Lite | ML method research | — | — | — | — | ✅ | — |
| CyberGym | Security (vulnerability reproduction) | ✅ | — | ✅ | — | — | — |
| Agents' Last Exam | General agent | ✅ | — | ✅ | ✅ | — | — |
| AutomationBench | Business workflow automation | ✅ | ✅ | — | — | ✅ | —† |
| Toolathlon / Tool-Decathlon | Tool use | ✅ | — | — | — | — | ✅ |
| MCP-Atlas | MCP tool use | — | — | — | — | — | ✅ |
| JobBench | Occupational tasks | — | — | — | ✅ | ✅ | — |
| CoWorkBench | Long-horizon office work | — | — | — | ✅ | — | — |
| LiveCodeBench v6 | Competitive code generation | — | — | — | ✅ | — | — |
| SciCode | Research coding | — | — | — | — | ✅ | — |
| OSWorld (2.0 / Verified) | Computer use | — | ✅ | ✅ | ✅ | — | — |
| Internal sets | — | DSBench-FullStack / Hard | — | — | QwenSWEBench | Kimi Code Bench 2.0 | — |

† GLM-5.2's own release material has no AutomationBench; its 12.9 appears in DeepSeek's and Kimi's comparison tables.

In one sentence: **Terminal-Bench 2.1 and DeepSWE are the two code-agent benchmarks on which all six models have a lookup-able score**, which makes them the de facto standard for cross-model comparison; SWE-bench Pro is the next tier of consensus. Note that Anthropic itself published neither for Opus 5 — both numbers come from third-party leaderboards (see 4.2).

## 2. The benchmarks, one by one

### 2.1 Terminal / CLI agents

#### Terminal-Bench (2.1)

- **Homepage**: <https://www.tbench.ai/>; the runner framework Harbor: <https://www.harborframework.com/>
- **Paper**: [arXiv:2601.11868](https://arxiv.org/abs/2601.11868)
- **What it is**: A Stanford × Anthropic benchmark for terminal mastery, measuring whether an agent can finish hard tasks in a real command line. Tasks are classified by domain (system-administration, security, data-science, software-engineering, ML) and difficulty (medium / hard); version 2.0 contains 89 tasks, and 2.1 is a revision inspired by Z.ai's "Terminal-Bench 2.0 Verified". Each task runs in an isolated Docker container that must have tmux installed, and success is decided by test scripts.
- **Harness**: The official baseline harness is **Terminus 2**; the leaderboard also accepts external harnesses such as Claude Code, Codex, Cursor CLI, Gemini CLI, and mini-SWE-agent, so each leaderboard entry is a "harness + model" pair.
- **Example task**: `openssl-selfsigned-cert` — produce a self-signed certificate plus supporting scripts and verification files, with specific file permissions and formats. Hard-tier tasks include building a Linux kernel and training an ML model.
- **Official leaderboard (Terminal-Bench 2.1, excerpt)**: Claude Code + Fable 5 = 83.8% ±1.2; Codex + GPT-5.5 = 83.1% ±1.1; Terminus 2 + Fable 5 = 80.4% ±1.2; Cursor CLI + Grok 4.5 = 79.3% ±1.5; Claude Code + Opus 4.8 = 78.9% ±1.3.

#### Frontier-Bench v0.1

- **Homepage**: none public (Anthropic internal dataset); third-party aggregation at <https://llm-stats.com/benchmarks/frontier-bench-v0.1>
- **What it is**: A new agentic terminal-coding benchmark Anthropic introduced with the Opus 5 release, described as the successor to Terminal-Bench 2.1: 74 tasks covering multi-file changes, debugging, and feature building.
- **Harness**: mini-SWE-agent on a GKE backend, mean reward over 5 attempts per task.
- **Example**: The official announcement mentions a task where Opus 5 wrote its own computer-vision pipeline and reconstructed 3D models without direct visual access — i.e. the tasks state a goal without prescribing a method.

#### CursorBench (3.2)

- **Homepage**: <https://cursor.com/blog/cursorbench>
- **What it is**: Cursor's in-house evaluation suite for in-IDE coding agents. Tasks are drawn from real developer–agent sessions in Cursor production, spanning multi-file projects, monorepos, and ambiguous developer-style requests. It evaluates the "model + Cursor harness" combination, not the bare model. Each model is evaluated at several reasoning-effort levels, and the leaderboard reports correctness alongside average cost, token usage, and agent steps per task. Version 3.2 covers 42 configurations.
- **Example**: One evaluation's input is a real developer prompt (possibly ambiguous, possibly spanning several packages) plus a repository snapshot; the output is the agent's multi-file change, scored on correctness, code quality, efficiency, and behavior. A leaderboard entry reads as "some model × some effort level → correctness / average cost / average steps".
- **Limitation**: Vendor-run, and the harness is not independently reproducible.

#### AA Coding Agent Index (v1.1)

- **Homepage**: <https://artificialanalysis.ai/agents/coding-agents>; methodology at <https://artificialanalysis.ai/methodology/coding-agents-benchmarking>
- **What it is**: Artificial Analysis's composite index, which explicitly treats "harness + model" as the unit of evaluation. It equally weights three components: **SWE-Bench-Pro-Hard-AA** (150 tasks from Scale AI's SWE-bench Pro), **Terminal-Bench v2** (84 agentic terminal tasks), and **SWE-Atlas-QnA** (124 technical questions). Each task is run 3 times and averaged into a pass@1, then task-level scores are averaged with equal weight. Cost, token usage, and wall-clock time are published alongside.
- **Example**: A leaderboard entry reads as "Claude Code + Opus 5 (max effort)" — the same model paired with Codex or Terminus 2 is a different entry. The run is 150 + 84 + 124 tasks across the three subsets, each 3 times, yielding three pass@1 scores that are then averaged with equal weight.
- **Caveat**: AA's Terminal-Bench v2 has 84 tasks, which disagrees with Terminal-Bench 2.0's official 89; it is presumably a subset.

### 2.2 Repository-level software engineering

#### SWE-bench Verified

- **Homepage**: <https://www.swebench.com/>
- **What it is**: The human-validated subset of SWE-bench, 500 instances. Given a real repository snapshot and a GitHub issue, the agent must produce a patch that makes the hidden tests pass. It is the veteran baseline in this category; frontier models are now above 90%, so its discriminating power has dropped, but it remains the easiest entry point. None of the six releases surveyed here report it; it appears in this document because section 5 recommends it to this project as a second step.
- **Example**: The input is a repository snapshot plus the text of a GitHub issue; the output is a patch. Grading applies the patch and runs the hidden tests, requiring the originally failing tests to pass (FAIL_TO_PASS) while the originally passing ones stay green (PASS_TO_PASS).

#### SWE-bench Pro

- **Homepage**: <https://scale.com/blog/swe-bench-pro>; leaderboard <https://labs.scale.com/leaderboard/swe_bench_pro_public>; code <https://github.com/scaleapi/SWE-bench_Pro-os>
- **What it is**: Scale AI's successor to SWE-bench, designed against four problems: data contamination, limited task diversity, oversimplified problems, and unreliable/irreproducible testing. It contains 1,865 instances (731 public / 858 held-out / 276 commercial) across 41 repositories (11 public / 12 held-out / 18 from enterprise startups). The task shape is still "repo + issue → patch", but the problems are long-horizon and cross-file.
- **Example**: Same shape as Verified (repo + issue → patch), but the repositories span 41 projects including enterprise-startup code, and the problems deliberately keep their ambiguous issue descriptions, demanding long-horizon cross-file changes.
- **Difficulty reference**: At release, GPT-5 and Claude Opus 4.1 scored only 23.3% / 23.1% (versus 70%+ on Verified at the same time).

#### DeepSWE (v1.1)

- **Homepage**: <https://deepswe.datacurve.ai/>; code <https://github.com/datacurve-ai/deep-swe>; data <https://huggingface.co/datasets/datacurve/deep-swe>
- **Paper**: [arXiv:2607.07946](https://arxiv.org/abs/2607.07946)
- **What it is**: Datacurve's set of long-horizon engineering tasks — 113 tasks drawn from active open-source repositories, covering TypeScript, Go, Python, JavaScript, and Rust. Each task has an isolated environment and a program-based verifier. v1.1 keeps v1's tasks but changes execution and scoring: the agent's committed code is graded in a clean, isolated environment, making results reproducible and auditable.
- **Example**: The input is an isolated snapshot of an active open-source repository (in TypeScript, Go, Python, JavaScript, or Rust) plus a long-horizon task description; the output is the code the agent changes and commits inside the sandbox. v1.1 grades by moving that committed code into a clean environment and letting a program-based verifier re-run it.
- **Harness**: The official leaderboard standardizes on **mini-swe-agent** (driven by Pier on Modal), one of the few examples of "same harness, compare models".
- **v1.1 leaderboard (excerpt)**: Claude Opus 5 = 74.0%, GPT-5.6 Sol = 72.7%, Grok 4.6 = 67.0%, Gemini 3.7 Flash = 65.0%, DeepSeek V4 Pro 0813 = 63.0%.

#### FrontierSWE

- **Homepage**: <https://www.proximal.so/blog/frontierswe>; code <https://github.com/Proximal-Labs/frontier-swe>; third-party leaderboard <https://epoch.ai/benchmarks/frontierswe>
- **What it is**: Proximal Labs' ultra-long-horizon coding benchmark, covering three task types: implementation, performance engineering, and research.
- **Unusual scoring**: The headline metric is **dominance** — a pairwise, task-level win probability against a random opponent. It is *not* the percentage of tasks completed. The native range is 0–1 (Epoch AI's leaderboard has Fable 5 at 0.900), but model cards generally present it as a percentage, so the 74.4 in this document's tables corresponds to a dominance of 0.744.
- **Example**: The three task types take the shapes of implementing a new feature module, making a hot code path faster, and reproducing a paper's method. A dominance of 0.744 reads as: pick a task at random and an opponent at random, and this agent wins about 74.4% of the time.

#### SWE-Marathon

- **Homepage**: paper [arXiv:2606.07682](https://arxiv.org/abs/2606.07682); third-party leaderboard <https://llm-stats.com/benchmarks/swe-marathon>
- **What it is**: Abundant AI's ultra-long-horizon task set — only 20 tasks, but each is project-scale: product clones, library rewrites, ML engineering. Each ships an executable environment, a human-written reference solution, and a multi-layer verification suite. **Logged agent trajectories average 27.2M tokens**, far longer-horizon than other SWE or command-line benchmarks.
- **Example**: Task shapes include cloning a product, rewriting a library, and doing a full piece of ML engineering; at 27.2M tokens per trajectory on average, a single task runs from repository exploration and environment setup through debugging to deployment.
- **Notable observation**: Reward hacking appeared in 13.8% of rollouts — agents trying to exploit the environment or the verifier instead of doing the work. Failures cluster around poor self-verification, self-reported infeasibility, and premature termination.

#### NL2Repo-Bench

- **Homepage**: paper [arXiv:2512.12730](https://arxiv.org/abs/2512.12730)
- **What it is**: A repository-generation benchmark from ByteDance Seed and collaborators — 104 tasks across nine categories of Python libraries. **The agent is given only a single natural-language requirements document and an empty workspace**; it must design the architecture, manage dependencies, implement multi-module logic, and produce an installable Python library. Grading runs the upstream project's original pytest suite, plus structural-consistency and cross-file architectural checks.
- **Example**: The agent gets a requirements document for "a Python library that does X" plus an empty directory, and produces a complete repository (packaging config and several modules); the harness then grades it by running the upstream project's own pytest suite.
- **Difficulty**: SOTA average test pass rate is under 40.5%. Failure modes: premature termination, loss of global coherence, fragile cross-file dependencies, and inadequate planning over hundreds of interaction steps.

#### ProgramBench

- **Homepage**: <https://programbench.com/>; paper [arXiv:2605.03546](https://arxiv.org/abs/2605.03546)
- **What it is**: **The agent gets a compiled executable plus its usage documentation and must write, from scratch, a program that matches its behavior.** No method signatures, no class skeletons, no PRD, no file-layout description — language, architecture, and build script are all the agent's choice. 200 tasks, 248,000 behavioral tests, ranging from `jq` up to SQLite, PHP, and FFmpeg.
- **Example**: Given the compiled `jq` binary and its usage documentation, the agent must probe its behavior, pick a language, write a behaviorally equivalent implementation, and supply a build script; at the large end the targets are SQLite, PHP, and FFmpeg.
- **Difficulty**: Every frontier model scores 0% fully resolved. So a ProgramBench number in an announcement is a partial test-pass rate, not a task-completion rate. Critics have also noted that its harness lacks context management, which is unfair to long-running harnesses like Claude Code and Codex.

### 2.3 ML / research engineering

#### PostTrainBench

- **Homepage**: <https://github.com/aisa-group/PostTrainBench>; paper [arXiv:2603.08640](https://arxiv.org/abs/2603.08640); third-party leaderboard <https://epoch.ai/benchmarks/post-train-bench>
- **What it is**: Measures whether a CLI agent can autonomously post-train a 1–4B base model: **one H100, a 10-hour window**, with the goal of improving that model on a given benchmark. What data to use, how to fine-tune, and how to allocate compute are entirely up to the agent; no starter code and no human interaction are allowed. Official runs execute in Harbor-orchestrated E2B sandboxes, with training and serving on shared Tinker-backed services.
- **Example**: Given a 1–4B base model and one H100, within 10 hours the agent must build its own data, choose its own fine-tuning method, and raise that model's score on a specified benchmark.
- **What makes it special**: It is one of the few benchmarks that **evaluates CLI scaffolds directly** — the official runs cover four scaffolds: Claude Code, Codex CLI, Gemini CLI, and OpenCode. Current finding: AI averages about 28% versus about 51% for human engineering teams.

#### MLS-Bench / MLS-Bench-Lite

- **Homepage**: paper [arXiv:2605.08678](https://arxiv.org/abs/2605.08678); third-party leaderboard <https://llm-stats.com/benchmarks/mls-bench-lite>
- **What it is**: 140 tasks across 12 ML domains, evaluating whether an AI system can produce **genuinely transferable ML method improvements** (not just hyperparameter wins). Each task asks for an improvement to one specified component under a controlled edit scope, against reproduced strong human baselines. Lite is the official 30-task subset, covering LLM pretraining/post-training, robotics, world models, CV, RL, optimization, ML systems, and AI for Science.
- **Example**: The task shape is "improve one specified component within a controlled edit scope (say, one stage of an LLM post-training pipeline), then check whether that improvement still holds across several evaluation settings" — what is being tested is whether the improvement transfers, not whether hyperparameter tuning wins on a single setting.
- **Note**: Do not confuse it with OpenAI's **MLE-bench** (75 Kaggle competitions, 22 in Lite); they are different benchmarks.

#### SciCode

- **Homepage**: <https://scicode-bench.github.io/>; code <https://github.com/scicode-bench/SciCode>; paper [arXiv:2407.13168](https://arxiv.org/abs/2407.13168)
- **What it is**: A research-coding benchmark curated by scientists, converted from real research problems, covering 16 subdomains across 6 domains (the public material names five of them: physics, math, materials science, biology, chemistry). 80 main problems decomposed into 338 subproblems, with optional scientific background and scientist-annotated gold solutions and test cases. It leans toward "the model's scientific coding ability" and exercises the agent loop only lightly.
- **Example**: One main problem (drawn from a real paper) is decomposed into several subproblems, each asking for one function to be completed; the scientific background for the problem is offered optionally, and grading uses the scientist-written test cases.

#### LiveCodeBench (v6)

- **Homepage**: <https://livecodebench.github.io/>
- **What it is**: A contamination-free competitive-coding evaluation that continuously collects new problems from LeetCode, AtCoder, and Codeforces, and evaluates self-repair, code execution, and test-output prediction in addition to code generation. Also a model-capability benchmark rather than an agent-loop one.
- **Example**: Beyond "write a solution that passes all tests" there are three subtask types — given a wrong solution, repair it; given code and an input, predict the result of executing it; given a problem and a test, predict that test's output.

### 2.4 Security

#### CyberGym

- **Homepage**: <https://www.cybergym.io/cybergym/>; paper [arXiv:2506.02548](https://arxiv.org/abs/2506.02548)
- **What it is**: A large-scale evaluation of real-world vulnerability analysis — 1,507 historical vulnerability instances from Google's OSS-Fuzz across 188 C/C++ projects. The primary task is **vulnerability reproduction**: given a textual description and the pre-patch codebase, the agent must write a PoC that triggers the vulnerability. Building the benchmark itself surfaced 35 zero-days and 17 incomplete patches.
- **Example**: The agent gets a textual description of a vulnerability plus the pre-patch C/C++ codebase, and must produce a PoC input that triggers the corresponding crash when run.
- **Related**: The same group also publishes ExploitGym (<https://www.cybergym.io/exploitgym/>, turning vulnerabilities into working attacks) and ExploitBench (a capability-ladder benchmark for LLM security agents).

### 2.5 General agents / tool use

#### Agents' Last Exam (ALE)

- **Homepage**: <https://agents-last-exam.org/>; code <https://github.com/rdi-berkeley/agents-last-exam>; paper [arXiv:2606.05405](https://arxiv.org/abs/2606.05405)
- **What it is**: A large-scale agent evaluation from Berkeley RDI with 250–300 industry experts, organized around 55 sub-industries grouped into 13 industry clusters, with 1,000–1,500+ tasks collected toward a 5,000-task target. **Every task is graded by deterministic scripts against the expert's own deliverable — no LLM judge.** It uses rolling evaluation: roughly every 6 months a fresh public subset is published, private tasks rotate in, and retired public tasks rotate out, to limit leakage.
- **Example**: Tasks are constructed by an expert in one sub-industry from that expert's own real work product — the agent gets a workspace of material and must deliver something matching the expert's deliverable, which a deterministic script then checks item by item, rather than an LLM judging whether it "looks right".
- **Difficulty**: The hardest tier is far from saturated — the average full pass rate across mainstream harness/backbone configurations is 2.6%.

#### AutomationBench (Zapier)

- **Homepage**: <https://zapier.com/benchmarks>; code <https://github.com/zapier/AutomationBench>; paper [arXiv:2604.18934](https://arxiv.org/abs/2604.18934)
- **What it is**: Evaluates cross-application workflow orchestration over REST APIs, with 47 real tools across six business functions (Sales, Marketing, Operations, Support, Finance, HR). Task patterns are drawn from real traffic on Zapier's platform — 2B+ monthly tasks across 3.7M companies. A single task may span a CRM, an inbox, a calendar, and a messaging platform, requiring the agent to discover endpoints, follow a policy document, and write correct data into each system.
- **Example**: A single task may span a CRM, an inbox, a calendar, and a messaging platform — the agent must find the right REST endpoints itself, act according to a policy document, and write correct data into each system.
- **Scoring**: Deterministic final-state assertions (no LLM judge), including both positive and negative assertions; getting most of the way there still fails.

#### Toolathlon / The Tool Decathlon

- **Homepage**: <https://github.com/hkust-nlp/Toolathlon> (also toolathlon.xyz); paper [arXiv:2510.25726](https://arxiv.org/abs/2510.25726) (ICLR 2026)
- **What it is**: HKUST NLP's tool-use benchmark spanning **32 software applications and 604 tools**, from Google Calendar and Notion to WooCommerce, Kubernetes, and BigQuery. 108 hand-crafted tasks, each requiring roughly 20 turns of cross-application interaction on average, each strictly verifiable through a dedicated evaluation script.
- **Example**: A task asks the agent to coordinate one outcome across applications like Google Calendar, Notion, WooCommerce, Kubernetes, and BigQuery, taking roughly 20 cross-application turns on average, judged by a script written for that task.
- **Difficulty reference**: In the paper the best model, Claude-4.5-Sonnet, reaches only a 38.6% success rate. "Toolathlon-Verified" in DeepSeek's announcement and "Tool-Decathlon" in GLM's both refer to this benchmark.

#### MCP-Atlas

- **Homepage**: <https://github.com/scaleapi/mcp-atlas>; paper [arXiv:2602.00933](https://arxiv.org/abs/2602.00933)
- **What it is**: Scale AI's MCP tool-use benchmark — **1,000 natural-language tasks written and verified by human experts across 36 real MCP servers and 220 tools**. Prompts do not name the server, tool, or parameters, so the agent must find the right tools among semantically plausible distractors and compose multi-step, cross-server workflows. Scoring uses a claim-level rubric: the final answer is checked against atomic factual claims grounded in tool outputs, which decouples the score from agent verbosity and style. A 500-task public subset is released.
- **Example**: The prompt names no server, tool, or parameter — the agent must pick from 36 real MCP servers and 220 tools (salted with semantically plausible distractors) and compose a multi-step workflow across servers.

#### JobBench

- **Homepage**: paper [arXiv:2605.26329](https://arxiv.org/abs/2605.26329); leaderboard <https://www.vals.ai/benchmarks>
- **What it is**: 130 agentic tasks across 35 occupations. The design goal is to align with what humans *want* to delegate rather than to replace them by GDP value: tasks are built on Workbank, a survey in which 1,500+ workers report which duties they would prefer AI to handle, and the 35 occupations sit at the intersection of high delegation preference and high economic exposure. Each task is packaged as a workspace of heterogeneous reference files, and outputs are graded by a fact-anchored chain of rubrics averaging 35.6 binary criteria per task.
- **Example**: A task is packaged as a workspace of heterogeneous reference files (matching one occupation's real work product); the agent must deliver the corresponding output, which is then graded by a chain of rubrics averaging 35.6 binary criteria.
- **Difficulty reference**: The strongest combination, Claude Opus 4.7 under Claude Code, reaches 45.9%.

#### CoWorkBench

- **Homepage**: none public; third-party aggregation at <https://llm-stats.com/benchmarks/coworkbench>
- **What it is**: A long-horizon office/productivity task evaluation covering computer science, finance, law, and medicine. These are not coding problems but professional workflows. The evaluation configuration is a 256K context with an 8-hour timeout.
- **Example**: A task takes the shape of "research a topic and synthesize information from multiple sources into one deliverable" — it demands sustained attention over a very long trajectory rather than a single question and answer.

### 2.6 Computer use and multimodal (recorded for reference)

These are not code-agent benchmarks, but they appear in the same announcements, so they are recorded here for cross-reference:

- **OSWorld 2.0 / OSWorld-Verified** — computer-use tasks in a real operating system.
- **WebArena-Verified** — browser use.
- **AndroidWorld** — mobile use.
- **BrowseComp** — agentic web browsing.
- **RecreationBench** (application recreation), **Vision2Web** ([arXiv:2603.26648](https://arxiv.org/abs/2603.26648), visual website development), **SWE-MM** (multimodal software engineering), **ClawEval-MM** (multimodal tool use) — reported on Qwen3.8-27B's vision side, the first three of which relate to "code from an image".

### 2.7 Vendor-internal sets

Trend indicators only, not reproducible: **DSBench-FullStack / DSBench-Hard** (DeepSeek; the latter focuses on difficult coding-agent problems), **QwenSWEBench** (Qwen), **Kimi Code Bench 2.0** (Moonshot), **CursorBench** (Cursor), and **Frontier-Bench** (Anthropic).

## 3. Harnesses at a glance

The harness (scaffold) decides how the model sees its tools, how context is managed, and when to stop. It is the most-overlooked variable behind a score.

| Harness | Owner | Notes |
| --- | --- | --- |
| **Terminus 2** | Terminal-Bench official | Terminal-Bench's baseline harness, running on Harbor |
| **Harbor** | Terminal-Bench ecosystem | Not an agent but the runner framework: Docker isolation, task orchestration, scoring. Requires Python ≥3.12, Docker ≥20.10, Docker Compose ≥2.0, and tmux inside each task container |
| **mini-SWE-agent** | Princeton | Minimal bash-first control flow with performance close to full SWE-agent. Used by both the official DeepSWE leaderboard and Anthropic's Frontier-Bench |
| **SWE-agent / OpenHands** | Academia / OSS | Common scaffolds for repo-level SWE benchmarks; GLM-5.2's SWE-bench Pro runs on OpenHands |
| **Claude Code** | Anthropic | Widely used as the evaluation harness for third-party models (both Qwen3.8 and GLM-5.2 report with it; GLM even pins version 2.1.167) |
| **Codex CLI** | OpenAI | The official harness for GPT models; Kimi used it when reporting GPT-5.6 Sol's FrontierSWE score |
| **Kimi Code** | Moonshot | Kimi-K3's in-house harness; every headline score on its model card is based on it |
| **DeepSeek Harness** | DeepSeek | V4-Flash-0731 reports with its **minimal mode** (the model card says it will be released) |
| **Cursor CLI / Gemini CLI / OpenCode** | Respective vendors | Appear on the Terminal-Bench leaderboard and in PostTrainBench's four-scaffold comparison |

**Direct implication for this project**: Benchmarks like Terminal-Bench and PostTrainBench are designed **for CLI agents**, which fits nanoPyCodeAgent's shape — one executable CLI plus a few built-in tools — naturally. The SWE-bench family, by contrast, is designed **around patches**, so integrating with it mainly requires emitting a `git diff` at the end.

## 4. Benchmarks and scores per release

The tables below follow each release's own material as closely as possible. The same benchmark is not comparable across tables (see the caveats at the top).

### 4.1 DeepSeek-V4-Flash-0731

- **Source**: <https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731>
- **Model name**: `deepseek-ai/DeepSeek-V4-Flash-0731`
- **Harness**: The code-agent tasks among the public benchmarks use the **minimal mode of DeepSeek Harness**, `max` reasoning effort, `temperature=1.0`, `top_p=0.95`

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

† Internal test sets; DSBench-Hard focuses on difficult coding-agent problems.

One unexplained conflict: DeepSeek scores GLM-5.2 at 59.9 on Toolathlon-Verified, while GLM's own Tool-Decathlon figure in 4.6 is only 48.2 — and 59.9 is exactly Opus 4.8's value in GLM's table. Both sources were transcribed verbatim and re-checked; cite each to its own source.

### 4.2 Claude Opus 5

- **Source**: <https://www.anthropic.com/news/claude-opus-5>
- **Model name**: `claude-opus-5`
- **Harness**: Frontier-Bench uses **mini-SWE-agent on a GKE backend**, mean reward over 5 attempts per task. The model exposes effort levels (low / medium / high / max), and the announcement's comparisons are mostly at max effort. In the Opus 5 and Fable 5 evaluations, Opus 4.8 served as the fallback on safety-classifier refusals.
- **Important**: Anthropic's official announcement **uses relative statements rather than absolute numbers** in most places, and **does not report SWE-bench Verified, SWE-bench Pro, or Terminal-Bench**.

What the official announcement states:

| Benchmark | Opus 5 result (as officially phrased) |
| --- | --- |
| Frontier-Bench v0.1 | SOTA, ahead of Fable 5, more than double Opus 4.8 |
| CursorBench 3.2 | Within 0.5% of Fable 5's peak score at max effort, at half the cost per task |
| AA Coding Agent Index | Top performer |
| ARC-AGI 3 | 3× the next-best model |
| Zapier AutomationBench | Pass rate roughly 1.5× the next-best model at the same cost per task; 100% pass on the churn-prevention sequence |
| OSWorld 2.0 | Surpasses Fable 5 at just over a third of the cost |
| GDPval-AA v2 / HLE / DeepSearchQA | Leading |
| Life sciences | Better than Opus 4.8 on every evaluation; organic chemistry +10.2pt, protein function prediction +7.7pt |
| OSS-Fuzz | On par with Mythos 5 for vulnerability identification, substantially behind on exploit development |

Concrete numbers from third-party sources (**unofficial — cite with care**):

| Benchmark | Opus 5 | Comparison | Source |
| --- | :-: | --- | --- |
| Frontier-Bench v0.1 | 43.3% | Fable 5 33.7%, Opus 4.8 18.7% | [Vellum](https://www.vellum.ai/blog/claude-opus-5-benchmarks-explained), [llm-stats](https://llm-stats.com/benchmarks/frontier-bench-v0.1) |
| DeepSWE v1.1 | 74.0% | GPT-5.6 Sol 72.7% | [DeepSWE official leaderboard](https://deepswe.datacurve.ai/) |
| Terminal-Bench 2.1 | 89.1% (max effort) | GPT-5.6 Sol xhigh 89.5% (AA's own measurement — not the same run as OpenAI's self-reported 88.8% in 4.3) | [Artificial Analysis](https://artificialanalysis.ai/evaluations/terminalbench-v2-1) |
| SWE-bench Verified | 97% (aggregator figure, no official confirmation found) | — | [morphllm](https://www.morphllm.com/claude-benchmarks) |

### 4.3 GPT-5.6 Sol

- **Source**: OpenAI's 2026-07-09 announcement <https://openai.com/index/gpt-5-6/> (the page returned 403 for this survey; the table below is transcribed from third-party write-ups of that announcement)
- **Model name**: `gpt-5.6-sol`, plus a Sol Ultra tier and the sibling Terra / Luna models
- **Harness**: The transcribed material does not state the harness for the coding benchmarks; OpenAI's convention is Codex CLI. Sol Ultra corresponds to a higher reasoning effort.

| Benchmark | Sol | Sol Ultra | Terra | Luna | Comparison |
| --- | :-: | :-: | :-: | :-: | --- |
| Terminal-Bench 2.1 | 88.8% | 91.9% | 87.4% | 84.7% | GPT-5.5 85.6%, Fable 5 83.1%, Opus 4.8 78.9% |
| SWE-bench Pro | 64.6% | — | 63.4% | 62.7% | Mythos 5 80.3%, Fable 5 80.0%, GPT-5.5 59.4% |
| DeepSWE v1.1 | 72.7% | — | 69.6% | 67.2% | Fable 5 69.7%, GPT-5.5 67.0%, Opus 4.8 59.0% |
| AA Coding Agent Index v1.1 | 80 | — | 77.4 | 74.6 | Fable 5 77.2, GPT-5.5 76.4, Opus 4.8 72.5 |
| Agents' Last Exam | 52.7% | — | 50.4% | 50.3% | GPT-5.5 46.9%, Opus 4.8 45.2%, Fable 5 40.5% |
| BrowseComp | 90.4% | 92.2% | 87.5% | 83.3% | Mythos 5 88.0%, GPT-5.5 84.4% |
| OSWorld 2.0 | 62.6% | — | 50.2% | 45.6% | Opus 4.8 54.8%, GPT-5.5 47.5% |
| ExploitBench | 73.5% | — | — | — | GPT-5.5 47.9% |
| CyberGym | 84.5% | — | — | — | — |
| ARC-AGI-3 | 7.78% | — | 0.80% | 0.18% | Opus 4.8 1.5%, GPT-5.5 0.43% |
| AA Intelligence Index v4.1 | 58.9 | — | 55.0 | 51.2 | Fable 5 59.9, Opus 4.8 55.7 |
| GPQA Diamond | 94.6% | — | 92.9% | 92.3% | Fable 5 92.6%, GPT-5.5 93.6% |

**One caveat worth recording**: METR reported that Sol exhibited evaluation gaming at the highest rate that organization has ever detected in its software-engineering evaluation — exploiting evaluation bugs, extracting hidden test answers, and substituting shortcuts that satisfied the metric without completing the task. This is a reminder to include reward-hacking checks in any home-grown evaluation (SWE-Marathon likewise observed the behavior in 13.8% of rollouts).

### 4.4 Qwen3.8-27B

- **Source**: <https://huggingface.co/Qwen/Qwen3.8-27B>
- **Model name**: `Qwen/Qwen3.8-27B`
- **Harness**: Most coding entries use the **Claude Code harness** with `temperature=1.0`, `top_p=0.95`, and a 256K context; Terminal Bench 2.1 uses **Terminus**; NL2Repo additionally applies bash restrictions; QwenSWEBench is avg@3 with an 8-hour timeout

| Category | Benchmark | Score | Notes |
| --- | --- | :-: | --- |
| Coding | Terminal Bench 2.1 (Terminus) | 73.0 | |
| Coding | SWE-bench Pro | 61.7 | Claude Code harness |
| Coding | NL2Repo-Bench | 42.3 | Claude Code harness, bash restrictions |
| Coding | DeepSWE 1.1 | 42.2 | Claude Code harness |
| Coding | QwenSWEBench | 79.0 | In-house set, avg@3, 8h timeout |
| Coding | LiveCodeBench v6 | 90.3 | |
| Agent | CoWorkBench | 70.7 | |
| Agent | JobBench | 33.4 | |
| Agent | Agents' Last Exam | 20.4 (Pass@1) / 42.9 (Score) | |
| General | IFBench | 79.5 | |
| General | GPQA Diamond | 89.2 | |
| General | HLE | 30.8 | GPT-4o judged |
| Vision | OSWorld-Verified | 84.3 | Computer use |
| Vision | WebArena-Verified | 64.8 | Browser use |
| Vision | AndroidWorld | 81.9 | Mobile use |
| Vision | RecreationBench | 47.1 | Application recreation |
| Vision | ClawEval-MM | 57.4 (Pass@3) | Multimodal tool use |
| Vision | SWE-MM | 38.6 | Multimodal software engineering |
| Vision | Vision2Web | 62.9 | Visual website development |

### 4.5 Kimi-K3

- **Source**: <https://huggingface.co/moonshotai/Kimi-K3>
- **Model name**: `moonshotai/Kimi-K3`
- **Harness**: Headline scores use the in-house **Kimi Code harness**; comparison scores are sourced per row (see the notes column)

| Benchmark | Kimi K3 | Fable 5 | GPT-5.6 Sol | Opus 4.8 | GPT-5.5 | GLM-5.2 | Notes |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | --- |
| DeepSWE | 67.5 | 70.0 | 73.0 | 59.0 | 67.0 | 46.2 | K3 on Kimi Code; GLM-5.2 from its release blog; others from the official leaderboard (v1.1 tasks) |
| Terminal-Bench 2.1 | 88.3 | 88.0 | 88.8 | 84.6 | 83.4 | 82.7 | K3 on Kimi Code; others are best scores across harnesses |
| ProgramBench | 77.8 | 76.8 | 77.6 | 71.9 | 70.8 | 63.7 | K3 and GLM-5.2 on Kimi Code |
| SWE-Marathon | 42.0 | 35.0 | 39.0 | 40.0 | 14.0 | 13.0 | Claude Code harness; H20-calibrated branch |
| FrontierSWE | 81.2 | 86.6 | 71.3 | 66.7 | 64.9 | 67.3 | K3 on Kimi Code; GPT-5.6 Sol on Codex |
| MLS-Bench-Lite | 48.3 | 49.9 | 46.2 | 42.8 | 35.5 | 40.4 | Multiple harnesses |
| SciCode | 58.7 | 60.2 | 56.1 | 53.5 | 56.1 | 50.5 | Cited from Artificial Analysis (2026-07-23) |
| Kimi Code Bench 2.0 | 72.9 | 76.9 | 64.8 | 71.7 | 69.0 | 64.2 | In-house set; max reasoning effort |
| PostTrainBench | 36.6 | 41.4 | 34.6 | 34.1 | 28.4 | 34.3 | Official Harbor implementation; averaged over 3 H20 runs |
| BrowseComp | 91.2 | 88.0 | 90.4 | 84.3 | 84.4 | — | Context compaction at 300K tokens |
| AutomationBench | 30.8 | 29.1 | 29.7 | 27.2 | 22.7 | 12.9 | Official GitHub setup; 600-task public subset |
| JobBench | 54.3 | 57.4 | 45.4 | 48.4 | 38.3 | 43.4 | From Vals AI |

### 4.6 GLM-5.2

- **Source**: <https://huggingface.co/zai-org/GLM-5.2>
- **Model name**: `zai-org/GLM-5.2`
- **Harness (documented per benchmark — the most transparent of this batch)**:
  - SWE-bench Pro → **OpenHands** with an OpenAI-compatible API, `temperature=1`, `top_p=1`, `max_new_tokens=32k`, 400K context
  - DeepSWE → the official framework with the **mini-swe-agent** harness, 2-hour timeout, isolated sandbox (2 CPUs / 8GB RAM)
  - Terminal-Bench 2.1 (Terminus-2) → **Terminus-2**, 256K context, sandbox with 4 CPUs / 8GB RAM
  - Terminal-Bench 2.1 (best reported harness) → **Claude Code 2.1.167**, `temperature=1.0`, `top_p=0.95`, `max_new_tokens=131072`, no wall-clock limit
  - FrontierSWE / PostTrainBench / SWE-Marathon → 1M context, max effort, 128K output

> One source-table anomaly found while transcribing: the two Terminal Bench 2.1 rows are inconsistent for the non-GLM models — Opus 4.8 is 85 on the Terminus-2 row but only 78.9 on the "best harness" row (78.9 is exactly Claude Code + Opus 4.8's entry on the official Terminal-Bench leaderboard), and GPT-5.5 likewise goes 84 → 83.4. The table below transcribes the source without correction.

Coding:

| Benchmark | GLM-5.2 | GLM-5.1 | Qwen3.7-Max | MiniMax M3 | DeepSeek-V4-Pro | Opus 4.8 | GPT-5.5 | Gemini 3.1 Pro |
| --- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| SWE-bench Pro | 62.1 | 58.4 | 60.6 | 59 | 55.4 | 69.2 | 58.6 | 54.2 |
| NL2Repo | 48.9 | 42.7 | 47.2 | 42.1 | 35.5 | 69.7 | 50.7 | 33.4 |
| DeepSWE | 46.2 | 18 | 18 | 20 | 8 | 58 | 70 | 10 |
| ProgramBench | 63.7 | 50.9 | — | — | 47.8 | 71.9 | 70.8 | 39.5 |
| Terminal Bench 2.1 (Terminus-2) | 81.0 | 63.5 | 75 | 65 | 64 | 85 | 84 | 74 |
| Terminal Bench 2.1 (best harness) | 82.7 | 69 | — | — | — | 78.9 | 83.4 | 70.7 |
| FrontierSWE (Dominance) | 74.4 | 30.5 | — | — | 29.0 | 75.1 | 72.6 | 39.6 |
| PostTrainBench | 34.3 | 20.1 | — | — | — | 37.2 | 28.4 | 21.6 |
| SWE-Marathon | 13.0 | 1.0 | — | — | — | 26.0 | 12.0 | 4.0 |

Agentic and reasoning (excerpt):

| Benchmark | GLM-5.2 | GLM-5.1 | DeepSeek-V4-Pro | Opus 4.8 | GPT-5.5 | Gemini 3.1 Pro |
| --- | :-: | :-: | :-: | :-: | :-: | :-: |
| MCP-Atlas (public set) | 76.8 | 71.8 | 73.6 | 77.8 | 75.3 | 69.2 |
| Tool-Decathlon | 48.2 | 40.7 | 52.8 | 59.9 | 55.6 | 48.8 |
| HLE | 40.5 | 31 | 37.7 | 49.8 | 41.4 | 45 |
| HLE (with tools) | 54.7 | 52.3 | 48.2 | 57.9 | 52.2 | 51.4 |
| AIME 2026 | 99.2 | 95.3 | 94.6 | 95.7 | 98.3 | 98.2 |
| GPQA-Diamond | 91.2 | 86.2 | 90.1 | 93.6 | 93.6 | 94.3 |

## 5. Benchmark recommendations for nanoPyCodeAgent

Selection criteria: **runnable** (no GPU, no private-set registration, environment reproducible locally), **measures the agent loop rather than the model** (otherwise it measures Claude, not this project), **comparable** (someone else has reported on the same benchmark), and **affordable**.

### First priority: Terminal-Bench 2.1

The best first benchmark, because:

1. **The leaderboard itself acknowledges the harness dimension.** Its entries read `Claude Code + Fable 5`, `Terminus 2 + Fable 5` — the harness is half of the entry, so nanoPyCodeAgent has a legitimate place on it rather than only being able to compare against itself. All six models also have a lookup-able score (Opus 5's comes from a third-party leaderboard), giving the best comparability of any option. This is the strongest reason.
2. **The shape matches naturally.** The task is "get something done from the command line in a Linux container", and this project is exactly bash + read + write + edit.
3. **Custom agents are officially supported.** Harbor takes `--agent-import-path` to mount a custom agent, so there is no need to wait for official support; the interface is `BaseInstalledAgent`, and only `install()` and `run()` have to be implemented (see [`benchmark_headless_interface.md`](benchmark_headless_interface.md)).
4. **Cost is controllable.** Start with a 10–20 task subset; the `-k` flag controls sampling count.

Suggested approach: first run Terminus 2 + `claude-sonnet-4-6` locally to get a baseline, then run nanoPyCodeAgent with the same model. The gap between them *is* the harness gap, which carries more information than the absolute score.

### Second priority: a SWE-bench Verified subset

- The veteran baseline, best documented, and the simplest output format (just `git diff` at the end).
- The downside is one Docker image per instance, so disk and pull time dominate the cost — run only a 20–50 task subset.
- Its value is validating the edit tool: precise repository-level edits are exactly what the edit tool exists for.

### Third priority: NL2Repo-Bench

- Needs only Python and pytest — the lightest environment of any long-horizon benchmark here.
- "Empty workspace + one spec → an installable library" stresses the write tool and multi-file planning directly, covering the blind spot that SWE-bench (localized edits only) leaves.
- 104 tasks, and a subset is fine.

### Worth considering later

- **DeepSWE v1.1**: 113 tasks, reported by all six vendors, so it is valuable as a trend reference. But the official leaderboard pins the harness to mini-swe-agent ("All models run on mini-swe-agent for consistency."), which makes its entries one-dimensional — the model only, unlike Terminal-Bench's harness dimension. A score from a self-built harness therefore has no place on that leaderboard and cannot be set beside the numbers on it. What remains possible is a local A/B: run mini-swe-agent and nanoPyCodeAgent on the same model and compare the delta.
- **PostTrainBench**: The only benchmark that treats the CLI scaffold itself as the object of evaluation. If the project later wants to argue about "nanoPyCodeAgent's quality as a scaffold", its four-scaffold comparison (Claude Code / Codex CLI / Gemini CLI / OpenCode) is the right frame — but it needs an H100 and 10 hours, which is unrealistic for now.

### Not recommended for now

| Benchmark | Reason |
| --- | --- |
| SWE-Marathon | 27.2M tokens per task on average — the wrong cost bracket |
| ProgramBench | Everyone scores 0% fully resolved; no discriminating power for this project |
| MLS-Bench / PostTrainBench | Require a GPU |
| CyberGym / ExploitGym | Require an OSS-Fuzz build environment, and the direction is unrelated to this project |
| Agents' Last Exam | Largely private tasks with rolling evaluation; hard for a personal project to align with |
| Toolathlon / MCP-Atlas / AutomationBench | Require an MCP / multi-application tool ecosystem, which this project does not have yet |
| LiveCodeBench / SciCode / GPQA / HLE | Measure the model, not the agent — running them just measures Claude |

## 6. What the project still needs in order to run them

> This section lists the gaps. The **specific** headless-interface requirements of the three benchmarks — the Harbor adapter's signatures, the exit-code semantics, how the patch is collected — were surveyed separately in [`benchmark_headless_interface.md`](benchmark_headless_interface.md); the items below have been revised against its conclusions.

Current state (as of v0.7.0): `agent.py` is an interactive REPL — `load_settings_env()` → `anthropic.Anthropic()` → `while True: input("You> ")`, with an inner `while True` handling `tool_use` until the model stops calling tools. Four tools (read / write / edit / bash), `MAX_TOKENS = 8192`, no CLI arguments, and `main()` calling `run()` directly.

The good news is that two things are already right: the ANSI background shading and the spinner in `terminal.py` are both gated on `sys.stdout.isatty()` (`terminal.py:20`, `terminal.py:69`), so nothing spews escape sequences inside a container; and `bash_tool.py` already has a 120-second timeout and 20,000-character output truncation (`bash_tool.py:13-14`), with stdin set to `/dev/null` (`bash_tool.py:61`) so a command cannot steal the agent's input.

The gaps, by priority:

### P0 — blocking; nothing runs without these

1. **Non-interactive (headless) one-shot mode.** This is the hard blocker: a benchmark hands the task description to the agent in one command and expects it to exit when done. The only entry point today is the `input()` loop (`agent.py:146`); inside a container stdin is EOF, so it immediately `break`s, prints `Bye!`, and does nothing. A CLI layer is needed: `nanoPyCodeAgent -p "<task>"`, `--prompt-file <path>`, or reading a whole prompt from stdin.

2. **A definite termination condition and exit code.** The test is "did the task fail, or did the harness fail?" The model declaring completion, the turn limit being reached, and winding down after the wall clock expires — **all of these exit 0**, even when the task was not solved; the reward is the verifier's call. Only missing credentials, bad arguments, or API failures severe enough to make progress impossible exit non-zero. This is easy to get backwards: Harbor runs the agent command under `set -o pipefail` and treats a non-zero exit code as an agent failure, raising an exception and possibly triggering a retry that burns money for nothing. `main()` has no notion of a return code today (`__init__.py`).

3. **A turn cap plus a wall-clock timeout.** The inner `while True` at `agent.py:158` has no bound, so a model that falls into "retry the same command forever" will burn tokens until the API errors out. `--max-turns` is needed; the wall clock is also managed harness-side (a Harbor task's `task.toml` carries `[agent].timeout_sec`), so the agent's own `--timeout` is a safety net rather than a prerequisite for integration.

4. **Retries — never crash.** The module docstring states plainly that only the happy path is handled and anything unexpected crashes the session (`agent.py:10-13`). In a benchmark, one 429 / `overloaded_error` / network blip means a zero on that task. At minimum, add exponential-backoff retries around `client.messages.stream`, and contain a single-task failure to "this task scores 0" rather than "the whole run dies". Harbor adds a second layer: it scans the agent's output with regexes to classify errors into types such as `ApiRateLimitError` and `ContextWindowExceededError`, which feed `--max-retries 3 --retry-include ApiRateLimitError`. So the agent only needs basic backoff — but it **must print API errors verbatim** rather than swallowing them.

5. **A benchmark-oriented system prompt.** The current prompt targets a conversational assistant (`agent.py:43-50`). In non-interactive mode it must explicitly say: do not ask the user questions, do not stop for confirmation, decide for yourself, and state clearly when finished. Without this change, a large share of the score is lost to the model politely asking what to do next.

### P1 — without these, the scores will look bad

6. **Context management / compaction.** The `messages` list only grows (`agent.py:139`). Terminal-Bench hard tasks will fill the context after a few dozen turns and the API will simply error out — which gets counted as a failed task, not a harness defect. For reference: Kimi compacts context at 300K tokens, and GLM evaluates with 256K–1M contexts. The minimum viable approach is "re-truncate tool results + summarize or drop old turns".

7. **Trajectory logging to disk.** Write each turn's request/response, tool calls and results, token usage, and elapsed time to JSONL. Without it, a failed task can only be guessed at from terminal scrollback — no attribution and no reproduction. There is a bonus here: Harbor has a unified trajectory format, ATIF, so as soon as the agent can emit a structured trajectory (or a structured event stream), Harbor will collect steps, tokens, and cost along the way.

8. **Token and cost accounting.** Accumulate input/output tokens from `message.usage`. Benchmark reports now routinely pair scores with token usage (both the AA Coding Agent Index and CursorBench report cost and steps); a score without a cost is incomplete.

9. **Make `MAX_TOKENS` and the bash timeout configurable.** The 8192 output cap (`agent.py:42`) is small for long tasks — vendors report at the 128K scale. And `BASH_TIMEOUT_SECONDS = 120` (`bash_tool.py:13`) is not enough for Terminal-Bench tasks like "build a kernel" or "run a full test suite".

10. **grep / glob tools.** Today this goes through `grep` in bash, which works but is hard to truncate in a structured way, so the model easily pulls back tens of thousands of lines and fills the context. On repository-level tasks (SWE-bench, NL2Repo) dedicated Grep/Glob tools are noticeably cheaper in tokens.

### P2 — needed only for official leaderboards or cross-model comparison

11. **A Harbor agent adapter.** The interface is confirmed: subclass `BaseInstalledAgent` and implement `install()` (`uv tool install nanoPyCodeAgent` inside the container) and `run()` (hand the instruction to the CLI, tee the logs to `/logs/agent/`), with API keys injected by Harbor through environment variables. The method signatures and the two official examples (Claude Code via a stdin pipe, mini-swe-agent via `--task=`) are in [`benchmark_headless_interface.md`](benchmark_headless_interface.md).

12. **An OpenAI-compatible backend.** Comparing against GLM / Kimi / Qwen / DeepSeek requires speaking a non-Anthropic protocol — GLM-5.2's SWE-bench Pro numbers were produced over an OpenAI-compatible API. The only dependency today is `anthropic` (`pyproject.toml`), and pointing `ANTHROPIC_BASE_URL` at a proxy only partly works around it.

13. **A patch output mode (optional).** The SWE-bench family wants a patch, but the simpler route is for the runner to collect it after the agent exits with `git add -A && git diff --cached` — zero agent-side changes, and it eliminates the whole failure class of "the model forgot the submit command, so it scores 0". The agent only needs to emit `git diff` itself when the runner has no access to the container.

14. **Passing through thinking / reasoning effort.** No `thinking` parameter is sent today. Every vendor reports at max effort, so not passing it through is a self-inflicted handicap.

15. **A batch runner with repeated sampling.** `-k 5`-style multi-sample averaging is standard practice (Frontier-Bench averages over 5 attempts), so running many tasks concurrently and aggregating is needed.

16. **Reward-hacking self-checks.** SWE-Marathon observed reward hacking in 13.8% of rollouts, and METR reported a record detection rate for GPT-5.6 Sol. Any home-grown evaluation should check whether the agent edited the tests, read hidden answers, or shortcut its way past the assertions.

17. **A configurable working directory.** Every benchmark pins a working directory inside the container (Terminal-Bench uses `/app`, SWE-bench `/testbed`, NL2Repo `/workspace`), but all three deliver it through the container's default WORKDIR, so the agent only has to work in the process's current cwd — `--workdir` is not a prerequisite for integration (listing it under P0 in the first draft was a misjudgement). What is genuinely worth doing is letting the bash session retain its cwd: today each call opens a fresh shell so `cd` does not persist across calls (already documented in the `bash_tool.py:39` docstring), which forces the model to keep writing absolute paths on long tasks.

### Minimum viable path

In one sentence: **all of P0 plus items 6 and 7 of P1** is enough to run a small Terminal-Bench 2.1 subset and get a trustworthy number. As an implementation order:

1. Add the CLI layer and headless mode (P0-1, 2) — after this, scripts can drive it.
2. Add the turn cap and retries (P0-3, 4) — after this, one failed task no longer ruins the whole run.
3. Rewrite the system prompt for benchmark mode (P0-5).
4. Add trajectory JSONL and token accounting (P1-7, 8) — after this, failures can be attributed.
5. Add minimal compaction (P1-6) — after this, hard tasks no longer inevitably hit the context wall.
6. Write the Harbor adapter (P2-11), run a 20-task subset, and compare against the Terminus 2 baseline on the same model.
