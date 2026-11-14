# Code Agent 权限模式对比

> 本文件为**中文源文件**（source of truth）；英文版 [`../en/agent_permission_modes.md`](../en/agent_permission_modes.md) 由其生成。

调研日期：**2026-11-14**。范围是 Claude Code、Codex、Pi、Grok Build、OpenCode 和 DeepSeek Harness 的本地 coding agent 权限机制。这里的 Grok 指官方 `xai-org/grok-build`，不是同名第三方 CLI 或 Grok 聊天产品。

## 1. 口径与来源

“权限模式”至少包含四个不同问题：

| 层次 | 回答的问题 | 典型取值 |
| --- | --- | --- |
| 执行边界 | 工具真正能读写什么、能否联网？ | 只读、工作区可写、完整访问 |
| 审批策略 | 哪些操作需要批准？无人回答时怎么办？ | 询问、拒绝需要询问的操作、跳过一般审批 |
| 审批者 | 需要批准时由谁判断？ | 用户、独立模型审查器 |
| 工作流程 | 现在先规划还是实施？ | Plan、Build |

下面分别记录这些层次，不把 UI 选项数当成整个权限系统的状态数。**不弹窗可能意味着自动放行，也可能意味着自动拒绝；计划模式也不一定有工具层或操作系统层限制。**

官方线上文档在调研日访问；开源实现使用仓库现有、工作区干净的 `references/` 快照，只读检查，未 fetch 或更新引用仓库。因此下列 SHA 固定的是本文核验的实现，**不声称它们都是调研日的远端最新提交或已发布版本**。线上文档与快照有不同口径时分别说明。没有运行真实模型会话或安全绕过实验。

| 项目 | 核验依据 |
| --- | --- |
| Claude Code | Anthropic 官方权限模式、权限规则文档；不以本地第三方源码镜像为依据 |
| Codex | OpenAI 官方文档；源码 `48524f337a84b570f0c2453ca43ec9a1a29375c0` |
| Pi | 官方仓库源码与文档 `8636e211e7834e4ca46a22aec1d65dfd2eac8677` |
| Grok Build | 官方仓库源码与内置用户指南 `2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8` |
| OpenCode | 官方 V2 文档；源码 `5a750e64a2d6da24d6f0ad2846791502a0e52cfa` |
| DeepSeek Harness | 官方仓库源码、组合配置与包文档 `39163dd30f703a79079e2d2446545cff3c453738` |

## 2. 总览

| Agent | 有哪些模式或等价机制 | 如何理解数量 |
| --- | --- | --- |
| Claude Code | `default`、`acceptEdits`、`plan`、`auto`、`dontAsk`、`bypassPermissions` | 6 个公开命名模式；`manual` 是 `default` 的别名 |
| Codex | Ask for approval、Approve for me、Full access、Custom；另有只读配置 | UI 是预设；底层是 3 类传统沙箱、2 种常用审批策略、2 种审批者及细粒度配置，不能压成一个枚举 |
| Pi | 核心默认直接执行；权限门禁、Plan 通过扩展实现 | 没有内置的多档工具审批模式；项目信任另算 |
| Grok Build | CLI/兼容设置接受与 Claude 相似的 6 个名称；原生权限选择是 `default`、`ask`、`auto`、`always-approve` | 原生 `default` 与 `ask` 都落到询问语义；兼容 `plan` 不等于进入真实 Plan 工作流 |
| OpenCode | `allow`、`ask`、`deny`；Build/Plan agent 可带不同规则 | 3 个逐操作规则结果，常用 2 个主代理；不是 3 个全局权限档位 |
| DeepSeek Harness | Read Only、Workspace Write、Full access；可选实验性 Auto review | 默认 base/Web 组合提供 3 个预设；加载实验插件后增加 `auto`，`custom` 只是派生状态 |

各项证据和限制见下文对应小节。

## 3. Claude Code

### 3.1 六种公开模式

| 配置值 | 语义 |
| --- | --- |
| `default`（Manual，别名 `manual`） | 常规读取和内置只读命令可直接执行；修改、其他命令及网络操作按规则请求批准 |
| `acceptEdits` | 自动批准工作目录及额外目录内的常规文件修改和部分文件系统命令；其他操作仍按权限规则处理 |
| `plan` | 探索并提交方案，通常阻止源文件编辑；探索命令是否由分类器审查或向用户询问，取决于会话配置；交互终端中启用了 bypass 的情况另有例外 |
| `auto` | 独立分类器审查需要检查的操作并允许或阻止；不是直接信任执行模型的判断，也不是取消权限检查 |
| `dontAsk` | 允许读取及预先批准的操作；原本需要询问的操作转为拒绝，不会自动授予权限 |
| `bypassPermissions` | 跳过一般权限提示和检查；仍有显式规则、特定交互及危险操作的例外 |

依据：[官方模式说明][CC-MODES]。不能把 `plan` 理解成“禁止一切工具”，也不能把 `acceptEdits` 理解成“所有 Bash 都免审批”。

### 3.2 规则、默认值和入口

`allow`、`ask`、`deny` 规则细化模式；普通规则按 `deny` → `ask` → `allow` 检查。当前文档明确保留 bypass 下的 deny、显式 ask 和部分关键路径删除检查等例外，因此 bypass 不保证永远没有提示。Bash 沙箱是独立机制。依据：[权限规则][CC-RULES]、[模式例外][CC-MODES]。

入口是 `--permission-mode <mode>`、设置中的 `permissions.defaultMode` 或交互模式切换；`--dangerously-skip-permissions` 选择 bypass。当前文档说明 v2.1.283 起交互终端和 VS Code 内置起始模式为 `auto`，而 v2.1.302 起未指定模式的 `claude -p`/SDK 使用 Manual。需要审批但没有可用批准路径时，不能假设 headless 会放行。**名为 `default` 的模式不等于所有入口实际默认选中的模式。**依据：[启动模式说明][CC-MODES]。

## 4. Codex

### 4.1 用户看到的是组合预设

| 预设/配置 | 沙箱 | 审批策略 | 审批者 | 语义 |
| --- | --- | --- | --- | --- |
| Ask for approval | `workspace-write` | `on-request` | `user` | 工作区内执行；需要更大权限时请求用户审批 |
| Approve for me | `workspace-write` | `on-request` | `auto_review` | 保持原工作区边界，将符合条件的审批请求交给独立审查器 |
| Full access | `danger-full-access` | `never` | 不产生一般审批 | 不由 Codex 沙箱限制文件和网络访问 |
| Custom | 命名权限 profile 或自定义配置 | 可配置 | 可配置 | 不存在一个固定的“Custom 权限范围” |
| 只读配置 | `read-only` 或只读 profile | 可组合 | 可组合 | 常驻权限不能修改普通文件；是否可以请求额外权限由审批配置决定 |

依据：[官方权限界面][CX-MODES]、[自动审查][CX-AUTO]、[沙箱说明][CX-SANDBOX]。UI 名称和可选项会随客户端、环境与组织策略变化；不能据此推断所有 CLI、IDE、桌面和云环境都展示同一菜单。

### 4.2 三个独立配置维度

**沙箱。** 传统 `sandbox_mode` 有 `read-only`、`workspace-write`、`danger-full-access` 三值。只读不代表不能运行读取命令；工作区可写不代表只能读取工作区。文件读取范围、额外可写目录、网络开关和受保护目录还要看实际 profile。当前源码还支持命名权限 profile，能分别定义文件系统和网络策略。依据：[沙箱枚举][CX-TYPES]、[权限 profile 实现][CX-PROFILES]。

**审批策略。** 常用公开 CLI 选项是 `on-request` 和 `never`。前者允许在需要时请求批准；后者不再向用户升级请求，失败交还 agent，**不会自动解除沙箱**。配置层另有 `granular`，可分别控制沙箱升级、规则触发、skill、`request_permissions` 和 MCP elicitation 的审批流；关闭某类表示拒绝对应请求，不是免审执行。依据：[CLI 枚举][CX-CLI-POLICY]、[协议定义][CX-POLICY]。

**审批者。** `approvals_reviewer = "user"` 路由给用户，`"auto_review"` 路由给独立审查器；后者可以拒绝。审批策略为 `never` 时，没有相应审批请求可交给它审查。依据：[审批者定义][CX-TYPES]、[官方自动审查说明][CX-AUTO]。

### 4.3 兼容值和非交互运行

当前官方文档不再将 `untrusted` 列为用户可选策略，但核验快照的协议仍保留内部 `UnlessTrusted`。同一快照把 `on-failure` 反序列化为 `OnRequest` 的别名，不能再当成独立的“失败后自动重试并升级”模式。依据：[当前沙箱文档][CX-SANDBOX]、[协议定义][CX-POLICY]。

`--full-auto` 已不再支持。当前 `--approve-for-me` 组合 `workspace-write + on-request + auto_review`；`--yolo` 是跳过审批和沙箱的快捷入口。`codex exec` 官方说明的默认沙箱为只读；自动化应显式固定策略，不能套用交互客户端的默认值。依据：[非交互文档][CX-EXEC]、[CLI 组合实现][CX-SHARED]。

Codex 的 Plan 是协作工作流，不是上述沙箱枚举里的第四档。讨论权限时仍需列出它实际配套的执行边界和审批策略。依据：[协作模式与沙箱类型定义][CX-TYPES]。

## 5. Pi

### 5.1 核心没有多档工具审批模式

Pi 的核心工具在启动它的操作系统用户权限下执行，不在每次调用前要求批准，也没有内置沙箱。工作目录影响资源发现和默认路径，不构成文件访问边界。因此不能给 Pi 虚构一个内置 `default / acceptEdits / bypass` 菜单，也不能把默认执行能力称作隔离环境。依据：[官方安全说明][PI-SECURITY]。

| 能力 | 是否核心内置 | 语义 |
| --- | --- | --- |
| 默认工具执行 | 是 | 以 Pi 进程权限执行启用的工具 |
| 选择工具子集 | 是 | 限制模型可调用哪些工具；若仍有 Bash，不等于只读边界 |
| `permission-gate` | 官方扩展示例，需加载 | 在 `tool_call` 上拦截部分危险 Bash 模式，交互确认；无 UI 时拒绝匹配的调用 |
| `plan-mode` | 官方扩展示例，需加载 | 限制内置写工具并检查 Bash 允许列表；不能概括为所有第三方工具的操作系统级只读保证 |
| 容器/VM/外部沙箱 | 外部执行环境 | 限制整个 Pi 进程时，才覆盖扩展、安装器和子进程等进程内能力 |

依据：[CLI 工具选择][PI-CLI]、[权限门禁示例][PI-GATE]、[计划扩展示例][PI-PLAN]、[隔离部署说明][PI-CONTAINERS]。示例门禁只匹配其代码列出的命令模式，不是通用 Shell 安全分析器。

### 5.2 项目信任另算

`--approve`、`--no-approve`、`defaultProjectTrust` 和 `/trust` 控制是否加载项目设置、扩展、MCP 等资源；不控制之后每次工具执行的权限。全局项目信任默认值为 `ask`；非交互环境中没有决策来源时，`ask`/`never` 跳过受保护项目资源，`always` 加载。拒绝项目信任也不会阻止默认加载的上下文指令影响模型。依据：[官方项目信任说明][PI-SECURITY]。

## 6. Grok Build

### 6.1 原生选择与兼容模式

原生 `[ui] permission_mode` 记录 `default`、`ask`、`auto`、`always-approve`。其中 `default` 与 `ask` 都映射到询问行为，`auto` 才是分类器审查，`always-approve` 才是通常所说的 YOLO。核验快照的内置交互默认是 Ask，配置和启动条件可以覆盖。依据：[原生配置解析][GR-CONFIG]、[UI 状态定义][GR-UI]。

CLI `--permission-mode` 和 Claude 兼容 `permissions.defaultMode` 接受以下六个名称：

| 名称 | 语义 |
| --- | --- |
| `default` | 内置只读操作可直接执行；其他操作按规则询问 |
| `acceptEdits` | 常规文件修改自动批准，其他调用继续经过权限处理 |
| `auto` | 对非快速放行操作进行安全审查；不能自动允许的调用在交互环境询问，非交互环境失败 |
| `dontAsk` | 仅运行预先批准或内置免审的操作；其余需要询问的调用拒绝 |
| `bypassPermissions` | 产品名称 Always-approve，通常跳过提示；显式 deny、hooks 和部分 Shell ask 规则仍然有效 |
| `plan` | 兼容值；权限默认效果与 `default` 相同，不能代替实际进入 Plan 工作流 |

依据：[官方内置权限指南][GR-GUIDE]、[兼容模式映射][GR-COMPAT]。子代理的继承和支持范围还需检查具体调用路径；不能只看到定义枚举就宣称所有运行入口行为相同。

### 6.2 规则、Plan 与沙箱

规则按照 `deny > ask > allow` 合并。Always-approve 仍保留硬拒绝、hook 限制及部分 Shell 分段规则；自动审查也有明确阻止结果。`--always-approve`（别名 `--yolo`）和 `--permission-mode auto` 是不同入口。无人值守不能把 Auto 当成“保证所有工具运行”。依据：[权限指南][GR-GUIDE]。

真实 `/plan`/`enter_plan_mode` 有独立状态：文件编辑仅放行会话计划文件，其他文件编辑拒绝，即便当前是 Always-approve；批准计划后再实施。这与兼容字符串 `plan` 不同。OS 沙箱则是另外的配置，默认关闭，不能从 Ask/Auto 推断已启用隔离。依据：[Plan 指南][GR-PLAN]、[沙箱指南][GR-SANDBOX]。

## 7. OpenCode

### 7.1 三种逐操作决策，不是固定全局模式

本文以当前 **V2** 文档及源码为准。V2 使用 `permissions` 规则数组、`shell` 和 `subagent`；V1 常见的 `permission`、`bash`、`task` 配置名称不同，不能混用。

| `effect` | 语义 |
| --- | --- |
| `allow` | 当前操作直接继续 |
| `ask` | 等客户端作出批准或拒绝决定 |
| `deny` | 当前操作拒绝 |

每条规则按 `action + resource` 匹配，**最后匹配的规则生效**；没有匹配时回退 `ask`。因此它不同于 Claude/Grok 的固定 deny 优先。基础规则默认允许所有操作，然后对 `*.env`、`*.env.*` 的读取设为 ask，并允许 `*.env.example`。V2 默认也没有对工作区外访问强制询问。依据：[官方权限文档][OC-PERMISSIONS]、[规则求值实现][OC-ENGINE]、[默认规则定义][OC-DEFAULTS]。

例如，可用 V2 配置表示“Shell 先问，查看状态免审，禁止 push”：

```json
{
  "permissions": [
    { "action": "shell", "resource": "*", "effect": "ask" },
    { "action": "shell", "resource": "git status *", "effect": "allow" },
    { "action": "shell", "resource": "git push *", "effect": "deny" }
  ]
}
```

### 7.2 Build/Plan 与审批结果

| 主代理 | 语义 |
| --- | --- |
| Build (`build`) | 默认执行代理，按照有效权限规则运行工具 |
| Plan (`plan`) | 探索和讨论方案；拒绝普通文件编辑，允许指定计划目录 `~/.opencode/plan` 内的编辑；Shell 仍受其权限规则控制 |

这是带有不同权限和提示词的 agent profile，不是操作系统沙箱。配置中的 `mode: primary / subagent / all` 只决定代理可以在哪种角色运行，也不是权限等级。依据：[官方代理文档][OC-AGENTS]、[Plan 实现][OC-PLAN]。

客户端审批回复为 `once`、`always`、`reject`。`always` 将工具建议的匹配模式保存为项目级持久批准，不覆盖已配置的 deny；并非给整个进程无限授权。组织 policies 可在权限规则之后作硬拒绝。非交互客户端需要显式处理 ask，不能默认视为 allow。依据：[审批说明][OC-PERMISSIONS]、[审批服务实现][OC-ENGINE]。

## 8. DeepSeek Harness

### 8.1 base/Web 三个预设，可选第四个 Auto

| 名称 | preset key | 沙箱 | 审批策略 | 语义 |
| --- | --- | --- | --- | --- |
| Read Only | `read-only` | `read-only` | `ask` | 常驻文件策略不允许写；需要写入时可走具体操作的一次性升级审批 |
| Workspace Write | `workspace-write` | `workspace-write` | `ask` | 允许工作区、后端支持的显式额外目录及临时区域内写入；更大范围需审批 |
| Full access | `danger-full-access` | `danger-full-access` | `never` | 绕过文件沙箱；不向用户发起一般升级询问 |
| Auto review（实验，默认关闭） | `auto` | `danger-full-access` | 选择时设为 `ask` | 每个受支持工具调用先审查，再以 Full access 执行；审查不允许时请求用户决定 |

依据：[base 组合配置][DS-BASE]、[Web 权限界面][DS-UI]、[实验 Auto 插件][DS-AUTO]。base-backed 新会话默认 Workspace Write。底层 permission-presets 包自身的默认表只有 Workspace Write 和 Full access，是 base 组合额外加入 Read Only；所以“包默认两个”与“默认 Web 三个”并不矛盾。依据：[CLI 运行说明][DS-CLI]、[preset 服务][DS-PRESETS]。

### 8.2 两个旋钮和实验审查

**文件沙箱。** `read-only / workspace-write / danger-full-access` 只定义文件修改的策略，**不包含网络限制**；进程可见性依赖具体后端。Windows 子进程沙箱忽略额外目录授权，Harness 文件工具单独执行这些授权。没有挂载执行该策略的能力时，仅配置一个策略值没有隔离效果。依据：[沙箱契约][DS-SANDBOX]。

**审批。** `ask` 调用已组合的 answerer，没有回答通道就失败关闭；`never` 直接拒绝需要审批的请求。它不是“批准所有请求”。Full access 预设之所以能少审批，是因为文件执行边界已经放开。一次性授权只覆盖指定操作，不修改整个会话的常驻策略。依据：[审批契约][DS-APPROVAL]。

**Auto。** 需显式加载实验插件，按当前 agent 的 provider/model 审查原生工具调用和程序化工具调用（PTC）内部的工具调用；不能覆盖 PTC 中直接进行的 Node 副作用。它与 Codex Approve for me 的执行边界不同：这里允许的调用以 Full access 执行。headless 可在选中 `auto` 后覆盖为 `--approval-policy never`，使审查拒绝成为最终拒绝；没有 answerer 时，`ask` 也不会自动批准。`auto` 仅供当前会话选择，不进入未来会话默认设置。依据：[Auto 集成说明][DS-AUTO]。

`custom` 表示当前沙箱/审批组合不对应已配置预设，是派生显示值，不是可切换的第四个稳定预设。独立 `sdk-minimal` 组合又与 base/Web 不同：固定 Full access 且不挂载审批和权限设置服务。依据：[preset 服务][DS-PRESETS]、[CLI 组合说明][DS-CLI]。

### 8.3 Plan 是软约束

`/plan` 和 `exit_plan_mode` 维护计划状态、提示词和计划审阅。包文档明确说明它**不限制工具，所有工具仍可调用**；需要强制边界时，应看配套沙箱和审批策略。因此这里不能把“Plan on”直接归类为 Read Only。依据：[Plan 包文档][DS-PLAN]。

## 9. 横向比较时应保留的区别

| 常见说法 | 本次核验后的准确含义 |
| --- | --- |
| “自动模式” | Claude/Grok 是带安全审查的执行；Codex Approve for me 审查被路由的审批请求；DeepSeek Auto 逐调用审查并使用 Full access；Pi 无统一内置对应模式 |
| “不询问” | Claude/Grok `dontAsk`、Codex/DeepSeek `never` 都不能直接理解为解除边界；需要询问而无批准路径时可能拒绝 |
| “只读/计划” | 沙箱只读、工具写入拒绝、Shell 允许列表、仅提示词约束是不同强度；DeepSeek Plan 明确属于软约束 |
| “完全权限” | 可能跳过沙箱，也可能只是跳过一般提示；显式 deny、组织政策、外层容器和操作系统权限仍需分别核验 |
| “默认” | 必须注明客户端、交互/非交互、版本和组合配置；不能只根据模式名称推断 |

这些是本文基于上述实现和文档的比较结论，不是对不同模式安全性的实测排名。

[CC-MODES]: https://code.claude.com/docs/en/permission-modes
[CC-RULES]: https://code.claude.com/docs/en/permissions
[CX-MODES]: https://learn.chatgpt.com/docs/permission-modes
[CX-AUTO]: https://learn.chatgpt.com/docs/sandboxing/auto-review
[CX-SANDBOX]: https://learn.chatgpt.com/docs/sandboxing
[CX-EXEC]: https://learn.chatgpt.com/docs/non-interactive-mode
[CX-TYPES]: https://github.com/openai/codex/blob/48524f337a84b570f0c2453ca43ec9a1a29375c0/codex-rs/protocol/src/config_types.rs
[CX-PROFILES]: https://github.com/openai/codex/blob/48524f337a84b570f0c2453ca43ec9a1a29375c0/codex-rs/core/src/config/permissions.rs
[CX-POLICY]: https://github.com/openai/codex/blob/48524f337a84b570f0c2453ca43ec9a1a29375c0/codex-rs/protocol/src/protocol.rs
[CX-CLI-POLICY]: https://github.com/openai/codex/blob/48524f337a84b570f0c2453ca43ec9a1a29375c0/codex-rs/utils/cli/src/approval_mode_cli_arg.rs
[CX-SHARED]: https://github.com/openai/codex/blob/48524f337a84b570f0c2453ca43ec9a1a29375c0/codex-rs/utils/cli/src/shared_options.rs
[PI-SECURITY]: https://github.com/earendil-works/pi/blob/8636e211e7834e4ca46a22aec1d65dfd2eac8677/packages/coding-agent/docs/security.md
[PI-CLI]: https://github.com/earendil-works/pi/blob/8636e211e7834e4ca46a22aec1d65dfd2eac8677/packages/coding-agent/docs/cli.md
[PI-GATE]: https://github.com/earendil-works/pi/blob/8636e211e7834e4ca46a22aec1d65dfd2eac8677/packages/coding-agent/examples/extensions/permission-gate.ts
[PI-PLAN]: https://github.com/earendil-works/pi/blob/8636e211e7834e4ca46a22aec1d65dfd2eac8677/packages/coding-agent/examples/extensions/plan-mode/index.ts
[PI-CONTAINERS]: https://github.com/earendil-works/pi/blob/8636e211e7834e4ca46a22aec1d65dfd2eac8677/packages/coding-agent/docs/containerization.md
[GR-CONFIG]: https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-shell/src/util/config/permissions.rs
[GR-UI]: https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-pager/src/app/actions.rs
[GR-GUIDE]: https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-pager/docs/user-guide/22-permissions-and-safety.md
[GR-COMPAT]: https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-permission-rules/src/rules.rs
[GR-PLAN]: https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-pager/docs/user-guide/19-plan-mode.md
[GR-SANDBOX]: https://github.com/xai-org/grok-build/blob/2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8/crates/codegen/xai-grok-pager/docs/user-guide/18-sandbox.md
[OC-PERMISSIONS]: https://opencode.ai/docs/permissions/
[OC-AGENTS]: https://opencode.ai/docs/agents/
[OC-ENGINE]: https://github.com/anomalyco/opencode/blob/5a750e64a2d6da24d6f0ad2846791502a0e52cfa/packages/core/src/permission.ts
[OC-DEFAULTS]: https://github.com/anomalyco/opencode/blob/5a750e64a2d6da24d6f0ad2846791502a0e52cfa/packages/schema/src/agent.ts
[OC-PLAN]: https://github.com/anomalyco/opencode/blob/5a750e64a2d6da24d6f0ad2846791502a0e52cfa/packages/core/src/plugin/plan.ts
[DS-BASE]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/packages/bundle/base/cordis.patch.yml
[DS-UI]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/packages/client/ui-permission-presets/README.md
[DS-CLI]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/apps/cli/reference/README.md
[DS-PRESETS]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/docs/subsystems/permission-presets.md
[DS-SANDBOX]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/docs/subsystems/sandbox.md
[DS-APPROVAL]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/docs/subsystems/approval.md
[DS-AUTO]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/packages/experimental/auto-review/README.md
[DS-PLAN]: https://github.com/deepseek-ai/deepseek-harness/blob/39163dd30f703a79079e2d2446545cff3c453738/packages/plan/plan-mode/README.md
