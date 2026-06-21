# 设计 Spec — 发布相关 skill（`land-pr` + `release`）

- **日期**: 2026-06-21
- **关联 issue**: [#4](https://github.com/minixalpha/nanoPyCodeAgent/issues/4)
- **分支**: `claude/release-skill`
- **状态**: 待审阅

> 正文用中文便于审阅；交付物（`SKILL.md` / `AGENTS.md` / `CLAUDE.md` / `docs/RELEASING.md`）一律英文。

---

## 1. 背景与目标

发布一个新版本牵涉一串横跨文档、GitHub、PyPI 的步骤。「publish 后半段」已被 CI 自动化
（推 `v*` tag 触发 `.github/workflows/release.yml` → `build` → `publish-to-pypi`(OIDC Trusted
Publishing) → `github-release`），但 tag 之前的准备与 tag 之后的验证仍靠手工。

**目标**：写**项目级、跨 agent 可移植**的 skill，把流程端到端驱动起来，并在正确位置设人工确认门。

**关键洞察**：原计划的「单一 release skill」把两种**频率不同**的动作耦合了——
「合并 PR」是每个 feature/bugfix 都做的**高频**动作且**多数不发版**，而「定版 + tag + 发布」是
攒够一批才做的**低频**动作。`release.yml` 只由 `v*` tag 触发，所以**只要不打 tag 就不会发 PyPI**，
二者本可解耦。故拆为两个 skill。

## 2. 范围与两层模型

设计哲学：**让每个 PR 自包含**——代码改动、changelog 条目、dev_notes（中英）、README（中英）
都在合并这个 PR 时同步好；**`release` 只做与发版直接相关的事**。

- **`land-pr`**（日常、高频、**不发布**，让 PR 自洽）：重写 PR desc → 按需追加 changelog
  `[Unreleased]` → dev_notes 改了 zh 就重生成 en → README 双语同步 → ⛔确认门 → 合并 PR。
- **`release`**（发版、低频、**直接 commit main**，只做发版）：定版本号 → changelog 定版 →
  ⛔确认门 → 直接 commit main → 打 tag → CI 发布 → `uvx` 验证。

**各类文档的生命周期**：
- **changelog**：`land-pr` 在每个 PR 往 `[Unreleased]` **追加**条目 → 攒够后 `release` 把
  `[Unreleased]` **定版**为 `[X.Y.Z] - 日期` 并加回空 `[Unreleased]`。
- **dev_notes / README**：由 `land-pr` 在 PR 内保证中英同步；`release` 不再触碰。

**不在范围内**：改 `release.yml` 本身；自动判定 0.x 语义化版本对错（版本号由 agent 提议、人工确认）。

## 3. 参照调研（pi / opencode）

调研两个同类项目的发布工程，佐证「发版改动直接 commit main、不走 release PR」这一选择：

| 维度 | **pi**（earendil-works/pi） | **opencode**（sst/opencode） |
|------|---------------------------|------------------------------|
| 发布触发 | **push tag `v*`** | `workflow_dispatch` 手动 |
| CHANGELOG | **入库、Keep a Changelog、`[Unreleased]`→定版** | 不入库、手写 release notes |
| Release notes | 从 CHANGELOG 抽取 | 人工手写 |
| 版本号源 | 手动 `npm version` bump | npm registry 派生 |
| **发版改动落主干** | **直接 commit main**（`parents:1` 普通提交，非 merge） | **直接 push dev** |
| release PR | **无** | **无** |

**结论**：两家都**不走 release PR**。pi 与本项目技术选择几乎一致（tag 触发 CI、Keep a Changelog
入库、`[Unreleased]` 定版、小团队、自研脚本），是最佳参照——其 `release.mjs` 干的正是
`release` skill 要干的：`[Unreleased]` 切成带日期版本 → `git commit "Release vX.Y.Z"` 直接到
main → 打 tag → tag 触发 CI 发布。

> 可选后续（**不在本次范围**）：pi 的 GitHub Release notes 从 CHANGELOG 对应 section 抽取，
> 比当前 `--generate-notes`（基于 PR 标题）更贴合手维 changelog。将来可考虑改 `release.yml`。

## 4. 关键设计决策（已与维护者对齐）

| 决策点 | 选定方案 |
|--------|----------|
| 部署布局 | 单一真源 `SKILL.md` 于 `.agents/skills`（Codex/pi 原生发现；Claude 经 `.claude/skills` 软链） |
| 自动化深度 | 指令为主 + 少量脚本（仅 `release` 的验证阶段脚本化） |
| 版本号 | agent 依 `[Unreleased]` 提议 + 人工确认 |
| 合并/发布切分 | **拆两个 skill**：`land-pr`（合并，不发布）+ `release`（发版） |
| 文档同步归属 | **dev_notes / README / changelog 追加都在 `land-pr`**；`release` 只做发版相关 |
| 发版改动落 main | **直接 commit main**（不走 release PR；参照 pi / opencode） |
| 本次实现范围 | **两个 skill 一起做**（本 PR 用 `land-pr` 合并自己，dogfood） |

维护者补充：
1. 根 `CLAUDE.md` **软链 → `AGENTS.md`**，Claude 与 Codex 读同一份项目指令。
2. PR desc **每次基于 PR 实际内容从头重写**，不读旧 desc、不增量。
3. 维护者前置信息（uv/gh/git）**单独成文** `docs/RELEASING.md`，README 双语只放指针。
4. 「commit 不加 Claude 署名」是维护者个人偏好，**不写进项目文档/交付物**（agent 执行时仍遵守）。

## 5. 文件布局（定稿）

```
.agents/skills/
  ├── land-pr/
  │   └── SKILL.md                  # 日常 PR 合并（英文）
  └── release/
      ├── SKILL.md                  # 发版（英文）
      └── scripts/
          └── verify-release.sh     # 唯一辅助脚本：发布后验证（轮询 + 重试）
.claude/skills  ──软链→ ../.agents/skills   # 整个 skills 目录软链，未来新增 skill 自动可见
AGENTS.md   (根, 英文)                # 项目指令 + 两节（land-pr / release）各指向对应 SKILL.md
CLAUDE.md   ──软链→ AGENTS.md         # Claude 读项目指令，与 Codex 同源
docs/RELEASING.md  (英文)             # 维护者文档：Prerequisites + 两 skill 分工 + 何时用哪个
README.md / README.zh-CN.md           # 各加一行指针 → docs/RELEASING.md（双语）
```

- **真源唯一**：`.agents/skills/<name>/SKILL.md`。`.agents/skills/` 是跨运行时（Codex、pi、Copilot、Gemini）约定的 skill 目录。
- **Codex / pi 原生自动发现项目级 `.agents/skills/`**（含 `SKILL.md` 的目录递归发现），已核实：
  - Codex（[官方文档](https://developers.openai.com/codex/skills)）：「scans `.agents/skills` in every directory from cwd up to the repo root」；团队共享亦可放 `.codex/skills/`。
  - pi（[官方 skills 文档](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)）：项目 trusted 后扫 `.agents/skills/`（cwd 及祖先）与 `.pi/skills/`。
  → 故 Codex / pi **无需** `AGENTS.md` 登记即可发现本仓库 skill。
- **Claude Code** 项目级 skill 目录是 `.claude/skills/`，用整目录软链 `.claude/skills → ../.agents/skills`
  让其发现同一真源；未来新增 skill 自动可见。代价：`.claude/skills` 成为别名，暂不支持「仅 Claude 专属」skill。
- **软链 fallback**：若实现时发现 Claude loader 不解析软链目录，依次退化为
  (a) 按 skill 单独软链，或 (b) 含 frontmatter 的薄指针文件。实现阶段实测后决定。

## 6. skill `land-pr`（日常 PR 合并，让 PR 自洽，不发布）

### 6.1 frontmatter

```yaml
---
name: land-pr
description: >
  Use when merging a feature/bugfix PR into main — the everyday, no-release flow.
  Makes the PR self-contained: rewrites the PR description from the PR's own
  contents, appends a changelog [Unreleased] entry when warranted, regenerates the
  English dev notes from the Chinese source when touched, and keeps the bilingual
  README in sync. Then — only after explicit maintainer confirmation — merges the
  PR. Does NOT tag or publish.
  Triggers on "合并 PR / land PR / 合并这个 PR / merge this PR".
---
```

### 6.2 流程（确认门居中）

1. **预检**（缺任一项即停并提示）：`git`/`gh` 存在；`gh auth status` 已登录；
   工作区干净；当前分支不是 `main`。
2. **确保 PR 存在**：`gh pr view` 探测当前分支的 PR；不存在则 `gh pr create`。
3. **changelog `[Unreleased]` 追加**（**按需**，不强制）：agent 判断本 PR 是否有值得记录的变更，
   提议往 `docs/changelogs/X.Y.x.md` 的 `[Unreleased]` 加条目（Added/Changed/Fixed/Removed），可为「无需」。
4. **dev_notes en 同步**：若本 PR 改了 `docs/dev_notes/zh-CN/<series>.md`，整文件重新生成
   `docs/dev_notes/en/<series>.md`（en 为 generated，不手改）。
5. **README 双语同步**：若本 PR 只改了 `README.md` 或 `README.zh-CN.md` **其一**，agent 把相应改动
   **同步到另一份**（翻译/对齐）纳入本 PR；README 是**手写润色源**，同步结果在确认门交维护者过目调整
   （不盲翻覆盖）。两份都已改则跳过。
6. **提交并 push**：步骤 3–5 的改动 commit 到 PR 分支并 push（使 PR 内容完整）。
7. **重写 PR desc**：基于 `gh pr diff` + commits + changed files **从头重写** description，
   **不读旧 desc**；更新走 GitHub API（`gh pr edit` 可能因 Projects Classic 报错）：
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number} -X PATCH -f body="..." --silent
   ```
8. **⛔ 确认门**：呈现 重写后的 **PR desc** + **changelog 追加（若有）** + **dev_notes 同步（若有）**
   + **README 同步/告警（若有）**，**等待显式确认**（如「确认 / go」）。未确认绝不合并。
9. **合并 PR**：沿用项目现有惯例（merge commit；如需 squash 由维护者指定）。结束，**不打 tag、不发布**。

## 7. skill `release`（只做发版，直接 commit main）

### 7.1 frontmatter

```yaml
---
name: release
description: >
  Use when cutting a new release of nanoPyCodeAgent (low-frequency). Does release
  work only — assumes dev notes and README were already kept in sync per-PR by
  land-pr. Picks the next version from the changelog [Unreleased], cuts the
  changelog, then — only after explicit maintainer confirmation — commits the
  changelog straight to main, pushes the vX.Y.Z tag (which triggers the PyPI +
  GitHub Release CI), and verifies the published artifacts via uvx.
  Triggers on "发布 / 发版 / cut a release / publish a release / 打 tag 发版".
---
```

### 7.2 流程（确认门居中；全程在 `main` 上操作）

1. **预检**（缺任一项即停）：`git`/`gh`/`uv` 存在；`gh auth status` 已登录；工作区干净；
   `docs/changelogs/X.Y.x.md` 的 `[Unreleased]` 有内容。
2. **切 main 并更新**：`git checkout main && git pull`。
3. **定版本号**：读 `[Unreleased]` 分组按 semver 提议下一个 `X.Y.Z`
   （有 Removed/破坏性 → major；有 Added → minor；仅 Fixed → patch）。
   **0.x 阶段语义特殊，最终一律由人工在确认门核准。**
4. **changelog 定版**：把 `## [Unreleased]` 条目移入新 `## [X.Y.Z] - <今天日期>`，保留空的 `[Unreleased]` 模板。
5. **⛔ 确认门**：呈现 拟定**版本号** + **changelog 定版 diff**，**等待显式确认**。未确认绝不提交或发布。
6. **commit + push main**：把 changelog 定版 `git commit -m "Release vX.Y.Z"` **直接提交到 main**
   并 `git push origin main`。
7. **打 tag**：`git tag vX.Y.Z && git push origin vX.Y.Z`（触发 `release.yml`）。
8. **盯 workflow**：`gh run watch` 跟踪 Release run（`build`→`publish-to-pypi`→`github-release`）。
9. **验证 + 汇报**：运行 `verify-release.sh vX.Y.Z`（见 §8），全绿则汇报成功，否则清晰报错。

## 8. 辅助脚本 `verify-release.sh`（仅 `release` 用）

仅把「最机械、需轮询重试」的步骤 8–9 脚本化；其余用 git/gh/uv 原生命令。

- **入参**：版本号或 tag（如 `0.1.1` / `v0.1.1`）。
- **职责**：
  1. 轮询**官方 PyPI** JSON（`https://pypi.org/pypi/nanoPyCodeAgent/json`）直到出现该版本——
     **显式 pin pypi.org，绕开清华镜像滞后**（带上限轮询 + 超时）；
  2. `gh release view vX.Y.Z` 校验 release 存在且含 wheel + sdist 资产；
  3. `uvx --index https://pypi.org/simple/ --from nanoPyCodeAgent@X.Y.Z nanoPyCodeAgent --help` 冒烟（带重试）。
- **退出**：全通过退 0；任一超时/失败退非 0 并打印原因（不静默成功）。

## 9. AGENTS.md / CLAUDE.md / docs/RELEASING.md / README

- **`AGENTS.md`**（根，英文）：项目通用指令文件（Codex 的项目上下文）。可放一句**何时用哪个 skill**
  的使用提示，但**非 skill 发现的必要条件**——Codex/pi 已原生自动发现 `.agents/skills`（见 §5）。
- **`CLAUDE.md`**：软链 → `AGENTS.md`。这是**项目级** CLAUDE.md，与用户全局 `~/.claude/CLAUDE.md` 叠加，不冲突。
- **`docs/RELEASING.md`**（英文，Prerequisites 权威人读来源）：
  - Prerequisites：`uv`、`gh`(已登录)、`git`；PyPI Trusted Publishing 一次性前置（已在 `release.yml` 注释）；
  - 两个 skill 的分工与**何时用哪个**（日常合并、连带 docs 同步 → `land-pr`；发版 → `release`）；
  - 如何触发：用户用自然语言说意图即可（如「合并 PR」「发布」），各 agent 按 SKILL.md 的 `description`
    匹配加载，**体验一致**；skill 发现是自动的——Codex/pi 原生扫 `.agents/skills`，Claude Code 经
    `.claude/skills` 软链（详见 §5）。
- **`README.md` / `README.zh-CN.md`**：各加一行 → `docs/RELEASING.md`（双语）。

## 10. 错误处理与幂等

- `release.yml` 的发布步骤本就幂等（`--check-url`、`gh release view || create`），失败可安全重跑。
- `verify-release.sh` 对「镜像未同步 / workflow 未完成」用**有上限轮询**，超时清晰报错而非静默成功。
- 两个 skill 的**确认门之前**任一步失败 → 停下报告，绝不进入合并 / 发布。

## 11. 测试 / 验证策略

- **路径检查**：一个轻量校验，确认各 `SKILL.md` 引用的脚本/路径真实存在（防漂移）。
- **自验证**：`release` 步骤 8–9 本身即对发布结果的端到端验证。
- **dogfood**：本 PR（`claude/release-skill`）实现两个 skill 后，**用 `land-pr` 流程合并自己**
  （本 PR 双语 README 同改、含 changelog 追加，正好覆盖 land-pr 主路径）。
- **真实考验**：放在下一次真实发布时用 `release` 整体跑一遍。

## 12. 风险与未决项

- **软链解析**：各 loader（Claude skills 目录、根 `CLAUDE.md`）能否跟随软链——实现时实测，备 fallback。
- **直接 push main**：`release` 直接 commit/push main，需 main 不强制 PR（单人项目 OK，已采纳）。
- **0.x 版本语义**：0.x 下 minor 可含破坏性变更；版本号最终由人工确认。
- **合并策略**：`land-pr` 默认沿用现有 merge commit 惯例，可由维护者改为 squash。
- **changelog 追加非强制**：`land-pr` 的 `[Unreleased]` 追加由 agent 提议、人工核定，纯内部改动可「无需」。
- **README 同步用机翻**：README 是手写润色源，`land-pr` 给出的同步改动需维护者在确认门过目调整。

## 13. 交付物清单

- [ ] `.agents/skills/land-pr/SKILL.md`
- [ ] `.agents/skills/release/SKILL.md`
- [ ] `.agents/skills/release/scripts/verify-release.sh`
- [ ] `.claude/skills`（整目录软链 → `.agents/skills`；fallback 见 §5）
- [ ] `AGENTS.md`（根）
- [ ] `CLAUDE.md`（根，软链 → `AGENTS.md`）
- [ ] `docs/RELEASING.md`
- [ ] `README.md` / `README.zh-CN.md` 指针
- [ ] changelog `[Unreleased]` 追加本次条目（用 `land-pr` 自己处理，dogfood）
