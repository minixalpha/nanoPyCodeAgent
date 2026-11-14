# Code Agent Permission Modes Compared

> Generated from the [Chinese source](../zh-CN/agent_permission_modes.md), which is the source of truth.

Research date: **2026-11-14**. This note covers local coding-agent permissions in Claude Code, Codex, Pi, Grok Build, OpenCode, and DeepSeek Harness. Grok means the official `xai-org/grok-build`, rather than a third-party CLI with the same name or the Grok chat product.

## 1. Scope and sources

“Permission mode” can refer to at least four different questions:

| Layer | Question | Typical values |
| --- | --- | --- |
| Execution boundary | What can tools actually read or write, and can they use the network? | Read-only, workspace-write, full access |
| Approval policy | Which operations require approval, and what happens without an answer? | Ask, deny operations that would ask, skip ordinary approvals |
| Reviewer | Who decides when approval is required? | User, separate model reviewer |
| Workflow | Should the agent plan or implement now? | Plan, Build |

These layers are recorded separately below. The number of UI choices is not the number of states in the entire permission system. **No prompt can mean either automatic permission or automatic rejection; planning does not necessarily impose tool-level or operating-system restrictions.**

Official online documentation was accessed on the research date. Open-source implementations were inspected read-only in the existing, clean `references/` checkouts; those repositories were not fetched or updated. The SHAs below pin the implementations inspected here, **without claiming that they are the latest upstream commits or released versions on the research date**. Differences between online documentation and snapshots are identified separately. No live model sessions or security-bypass experiments were run.

| Project | Evidence inspected |
| --- | --- |
| Claude Code | Anthropic's official permission-mode and permission-rule documentation; the local third-party source mirror is not used as authority |
| Codex | Official OpenAI documentation; source `48524f337a84b570f0c2453ca43ec9a1a29375c0` |
| Pi | Official repository source and documentation `8636e211e7834e4ca46a22aec1d65dfd2eac8677` |
| Grok Build | Official repository source and bundled user guide `2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8` |
| OpenCode | Official V2 documentation; source `5a750e64a2d6da24d6f0ad2846791502a0e52cfa` |
| DeepSeek Harness | Official repository source, composition configuration, and package documentation `39163dd30f703a79079e2d2446545cff3c453738` |

## 2. Overview

| Agent | Modes or equivalent mechanisms | How to count them |
| --- | --- | --- |
| Claude Code | `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions` | Six public named modes; `manual` aliases `default` |
| Codex | Ask for approval, Approve for me, Full access, Custom; also read-only configurations | UI presets combine three traditional sandbox categories, two common approval policies, two reviewers, and granular settings; there is no single equivalent enum |
| Pi | Core execution proceeds directly; extensions implement permission gates and Plan | No built-in tiered tool-approval modes; project trust is separate |
| Grok Build | CLI/compatibility settings accept six Claude-like names; native choices are `default`, `ask`, `auto`, `always-approve` | Native `default` and `ask` both mean prompting; compatibility `plan` does not enter the actual Plan workflow |
| OpenCode | `allow`, `ask`, `deny`; Build/Plan agents can carry different rules | Three per-operation rule outcomes and two common primary agents, rather than three global permission levels |
| DeepSeek Harness | Read Only, Workspace Write, Full access; optional experimental Auto review | Default base/Web composition provides three presets; loading the experiment adds `auto`; `custom` is derived state |

Evidence and limitations for each entry follow in the corresponding section.

## 3. Claude Code

### 3.1 Six public modes

| Configuration value | Semantics |
| --- | --- |
| `default` (Manual; alias `manual`) | Routine reads and built-in read-only commands proceed; modifications, other commands, and network actions follow approval rules |
| `acceptEdits` | Automatically approves routine edits and some filesystem commands within working/additional directories; other operations remain permission-controlled |
| `plan` | Explores and proposes changes, generally blocking source edits; exploration commands use classifier review or user approval depending on configuration, with an interactive-terminal bypass exception |
| `auto` | A separate classifier allows or blocks actions requiring review; this does not remove permission checks |
| `dontAsk` | Allows reads and pre-approved operations; operations that would prompt are denied |
| `bypassPermissions` | Skips ordinary prompts and checks, with explicit-rule, interaction, and dangerous-action exceptions |

Source: [official mode documentation][CC-MODES]. Plan still permits tools; acceptEdits does not approve every Bash command.

### 3.2 Rules, defaults, and entry points

`allow`, `ask`, and `deny` refine modes; ordinary rules are checked in `deny` → `ask` → `allow` order. Current documentation retains deny, explicit ask, and certain critical-path deletion checks even under bypass. Bash sandboxing is separate. Sources: [permission rules][CC-RULES], [mode exceptions][CC-MODES].

Select a mode with `--permission-mode <mode>`, `permissions.defaultMode`, or interactive switching; `--dangerously-skip-permissions` selects bypass. The documented built-in starting mode is `auto` for interactive terminal/VS Code since v2.1.283, but Manual for unspecified-mode `claude -p`/SDK runs since v2.1.302. Headless approval requires an available approval path. **The mode named `default` is not necessarily the actual default selected by an entry point.** Source: [startup behavior][CC-MODES].

## 4. Codex

### 4.1 User-facing options are combined presets

| Preset/configuration | Sandbox | Approval policy | Reviewer | Semantics |
| --- | --- | --- | --- | --- |
| Ask for approval | `workspace-write` | `on-request` | `user` | Work within the workspace; ask the user for broader permissions |
| Approve for me | `workspace-write` | `on-request` | `auto_review` | Retain the workspace boundary and route eligible requests to a separate reviewer |
| Full access | `danger-full-access` | `never` | No ordinary approval requests | Codex sandboxing does not restrict file or network access |
| Custom | Named permission profile or custom configuration | Configurable | Configurable | There is no single fixed Custom access scope |
| Read-only configuration | `read-only` or a read-only profile | Composable | Composable | Standing permissions cannot modify ordinary files; approval settings determine whether broader access can be requested |

Sources: [official permissions UI][CX-MODES], [automatic review][CX-AUTO], [sandbox documentation][CX-SANDBOX]. Labels and available options vary by client, environment, and organization policy; CLI, IDE, desktop, and cloud menus need not match.

### 4.2 Three independent configuration dimensions

**Sandbox.** Traditional `sandbox_mode` has three values: `read-only`, `workspace-write`, and `danger-full-access`. Read-only still permits commands that read; workspace-write does not mean reads are confined to the workspace. Actual profiles also determine readable paths, additional write roots, network settings, and protected paths. Current source supports named permission profiles with separate filesystem and network policies. Sources: [sandbox enum][CX-TYPES], [permission-profile implementation][CX-PROFILES].

**Approval policy.** Common public CLI choices are `on-request` and `never`. The former permits approval requests when needed. The latter returns failures to the agent without escalating to the user; **it does not remove sandbox restrictions**. Configuration also supports `granular`, controlling sandbox escalation, rule-triggered approvals, skills, `request_permissions`, and MCP elicitation separately. Disabling a category rejects its requests rather than executing them without review. Sources: [CLI enum][CX-CLI-POLICY], [protocol definitions][CX-POLICY].

**Reviewer.** `approvals_reviewer = "user"` routes to the user; `"auto_review"` routes to a separate reviewer that can deny. With approval policy `never`, there are no corresponding approval requests for that reviewer. Sources: [reviewer definition][CX-TYPES], [official automatic-review documentation][CX-AUTO].

### 4.3 Compatibility values and non-interactive execution

Current official documentation no longer offers `untrusted` as a selectable policy, although the inspected protocol snapshot retains internal `UnlessTrusted`. That snapshot deserializes `on-failure` as an alias of `OnRequest`; it is not an independent retry-and-escalate-after-failure mode. Sources: [current sandbox documentation][CX-SANDBOX], [protocol definitions][CX-POLICY].

`--full-auto` is no longer supported. Current `--approve-for-me` combines `workspace-write + on-request + auto_review`; `--yolo` bypasses approvals and sandboxing. Official documentation gives read-only as the default sandbox for `codex exec`. Automation should fix its policy explicitly rather than assume interactive-client defaults. Sources: [non-interactive documentation][CX-EXEC], [CLI composition implementation][CX-SHARED].

Codex Plan is a collaboration workflow, rather than a fourth value in the sandbox enum. Permission comparisons must still specify its actual execution boundary and approval policy. Source: [collaboration-mode and sandbox type definitions][CX-TYPES].

## 5. Pi

### 5.1 Core has no tiered tool-approval modes

Pi's core tools execute with the operating-system permissions of the user who started it, without requiring approval for every call, and it has no built-in sandbox. The working directory controls resource discovery and default paths, rather than file-access confinement. There is no built-in `default / acceptEdits / bypass` menu, and default execution is not an isolated environment. Source: [official security documentation][PI-SECURITY].

| Capability | Built into core? | Semantics |
| --- | --- | --- |
| Default tool execution | Yes | Enabled tools execute with Pi process permissions |
| Tool-subset selection | Yes | Limits the tools available to the model; retaining Bash does not establish read-only confinement |
| `permission-gate` | Official extension example; must be loaded | Intercepts selected dangerous Bash patterns at `tool_call`, asks interactively, and blocks matching calls without UI |
| `plan-mode` | Official extension example; must be loaded | Restricts built-in write tools and checks a Bash allowlist; not an OS-enforced read-only guarantee for every third-party tool |
| Container/VM/external sandbox | External execution environment | Restricting the entire Pi process also covers extensions, installers, and child processes |

Sources: [CLI tool selection][PI-CLI], [permission-gate example][PI-GATE], [plan extension example][PI-PLAN], [isolation documentation][PI-CONTAINERS]. The example gate matches only the command patterns listed in its code; it is not a general Shell security analyzer.

### 5.2 Project trust is separate

`--approve`, `--no-approve`, `defaultProjectTrust`, and `/trust` control loading project settings, extensions, MCP resources, and similar content, rather than authorizing subsequent tool executions. Global project trust defaults to `ask`. Without a decision source in non-interactive mode, `ask`/`never` skip protected project resources, while `always` loads them. Declining trust does not prevent normally loaded context instructions from influencing the model. Source: [official project-trust documentation][PI-SECURITY].

## 6. Grok Build

### 6.1 Native choices and compatibility modes

Native `[ui] permission_mode` records `default`, `ask`, `auto`, and `always-approve`. Both `default` and `ask` map to prompting; `auto` uses classifier review, while `always-approve` is the usual YOLO behavior. The inspected snapshot ships an interactive Ask default, which configuration and launch conditions can override. Sources: [native configuration parsing][GR-CONFIG], [UI state definitions][GR-UI].

CLI `--permission-mode` and Claude-compatible `permissions.defaultMode` accept these six names:

| Name | Semantics |
| --- | --- |
| `default` | Built-in read-only operations proceed; other operations ask according to rules |
| `acceptEdits` | Routine file edits are automatically approved; other calls remain permission-controlled |
| `auto` | Reviews operations outside the fast paths; calls not automatically allowed prompt interactively or fail non-interactively |
| `dontAsk` | Runs only pre-approved or built-in exempt operations; other calls requiring a prompt are denied |
| `bypassPermissions` | Product name Always-approve; normally skips prompts, while explicit deny, hooks, and some Shell ask rules remain effective |
| `plan` | Compatibility value with the same baseline permission effects as `default`; does not enter the actual Plan workflow |

Sources: [official bundled permission guide][GR-GUIDE], [compatibility-mode mapping][GR-COMPAT]. Subagent inheritance and support still depend on the invocation path; an enum alone does not prove identical behavior across every entry point.

### 6.2 Rules, Plan, and sandboxing

Rules merge with `deny > ask > allow` precedence. Always-approve retains hard denials, hook restrictions, and some segmented Shell rules; automatic review can also block. `--always-approve` (alias `--yolo`) and `--permission-mode auto` are distinct. Auto does not guarantee that unattended tools execute. Source: [permission guide][GR-GUIDE].

Actual `/plan`/`enter_plan_mode` uses separate state: file edits allow only the session's plan file and reject other files, even with Always-approve; implementation follows plan approval. This differs from the compatibility string `plan`. OS sandboxing is another setting and is off by default; Ask/Auto does not imply isolation. Sources: [Plan guide][GR-PLAN], [sandbox guide][GR-SANDBOX].

## 7. OpenCode

### 7.1 Three per-operation outcomes, rather than fixed global modes

This section uses current **V2** documentation and source. V2 uses a `permissions` array, `shell`, and `subagent`; common V1 names `permission`, `bash`, and `task` differ and must not be mixed in.

| `effect` | Semantics |
| --- | --- |
| `allow` | Continue the current operation immediately |
| `ask` | Wait for the client to approve or reject |
| `deny` | Reject the current operation |

Rules match `action + resource`, with **the last matching rule winning**; no match falls back to `ask`. This differs from Claude/Grok's fixed deny precedence. The base policy allows all operations, then asks for reads of `*.env` and `*.env.*`, while allowing `*.env.example`. V2 also has no default mandatory prompt for access outside the workspace. Sources: [official permissions documentation][OC-PERMISSIONS], [rule evaluator][OC-ENGINE], [default rule definitions][OC-DEFAULTS].

For example, this V2 configuration asks before Shell commands, allows status inspection, and denies push:

```json
{
  "permissions": [
    { "action": "shell", "resource": "*", "effect": "ask" },
    { "action": "shell", "resource": "git status *", "effect": "allow" },
    { "action": "shell", "resource": "git push *", "effect": "deny" }
  ]
}
```

### 7.2 Build/Plan and approval results

| Primary agent | Semantics |
| --- | --- |
| Build (`build`) | Default execution agent; tools follow effective permission rules |
| Plan (`plan`) | Explores and discusses plans; denies ordinary file edits but allows edits under the designated `~/.opencode/plan` directory; Shell remains subject to its permission rules |

These are agent profiles with different permissions and prompts, rather than OS sandboxes. Configuration `mode: primary / subagent / all` determines the roles in which an agent can run; it is not a permission level. Sources: [official agent documentation][OC-AGENTS], [Plan implementation][OC-PLAN].

Client approval replies are `once`, `always`, and `reject`. `always` saves the tool's proposed patterns as durable project-scoped approvals, without overriding configured deny rules; it does not grant unlimited process access. Organization policies can hard-deny after permission rules. Non-interactive clients must handle ask explicitly rather than assume allow. Sources: [approval documentation][OC-PERMISSIONS], [approval-service implementation][OC-ENGINE].

## 8. DeepSeek Harness

### 8.1 Three base/Web presets, with optional Auto as a fourth

| Name | Preset key | Sandbox | Approval policy | Semantics |
| --- | --- | --- | --- | --- |
| Read Only | `read-only` | `read-only` | `ask` | Standing file policy prevents writes; a specific operation can request a one-shot escalation |
| Workspace Write | `workspace-write` | `workspace-write` | `ask` | Allows writes within the workspace, explicit additional roots where supported, and backend temporary areas; broader access requires approval |
| Full access | `danger-full-access` | `danger-full-access` | `never` | Bypasses file sandboxing and does not ask the user for ordinary escalation |
| Auto review (experimental; off by default) | `auto` | `danger-full-access` | Set to `ask` on selection | Reviews each supported tool call, then executes allowed calls with Full access; non-allowed calls request a user decision |

Sources: [base composition][DS-BASE], [Web permissions UI][DS-UI], [experimental Auto plugin][DS-AUTO]. New base-backed sessions default to Workspace Write. The permission-presets package itself defaults to just Workspace Write and Full access; the base composition adds Read Only. Thus a two-entry package default and a three-entry default Web menu are consistent. Sources: [CLI runtime documentation][DS-CLI], [preset service][DS-PRESETS].

### 8.2 Two controls and experimental review

**File sandbox.** `read-only / workspace-write / danger-full-access` governs filesystem modifications and **does not include network restrictions**. Process visibility depends on the backend. Windows subprocess confinement ignores additional directory grants; Harness file tools enforce them separately. A policy value alone provides no isolation when no enforcing capability is mounted. Source: [sandbox contract][DS-SANDBOX].

**Approval.** `ask` calls the composed answerers and fails closed without an answer channel; `never` directly rejects requests requiring approval. It does not approve every request. Full access needs fewer approvals because the file boundary is already open. One-shot approval covers the specified operation rather than changing the whole session's standing policy. Source: [approval contract][DS-APPROVAL].

**Auto.** The experimental plugin must be loaded explicitly. It uses the current agent's provider/model to review native tool calls and inner calls in programmatic tool calling (PTC), without covering direct Node side effects in PTC. Unlike Codex Approve for me, allowed calls execute with Full access. Headless can override the policy with `--approval-policy never` after selecting `auto`, making review denials final. Without an answerer, `ask` does not automatically approve either. `auto` is a current-session choice and is excluded from future-session defaults. Source: [Auto integration documentation][DS-AUTO].

`custom` is a derived display value when sandbox/approval settings do not match a configured preset, rather than a selectable fourth stable preset. The standalone `sdk-minimal` composition also differs from base/Web: it pins Full access and mounts neither approval nor permission-settings services. Sources: [preset service][DS-PRESETS], [CLI composition documentation][DS-CLI].

### 8.3 Plan is a soft constraint

`/plan` and `exit_plan_mode` maintain plan state, guidance, and review. Package documentation explicitly says that this **does not restrict tools: every tool remains callable**. Enforced limits come from the accompanying sandbox and approval policy. “Plan on” therefore cannot be classified directly as Read Only. Source: [Plan package documentation][DS-PLAN].

## 9. Distinctions to preserve in comparisons

| Common phrase | Meaning established by this research |
| --- | --- |
| “Auto mode” | Claude/Grok execute with safety review; Codex Approve for me reviews routed approval requests; DeepSeek Auto reviews calls and uses Full access; Pi has no uniform built-in counterpart |
| “Never ask” | Claude/Grok `dontAsk` and Codex/DeepSeek `never` do not inherently remove boundaries; calls requiring approval can be rejected when no approval path is available |
| “Read-only/Plan” | Read-only sandboxing, rejected write tools, Shell allowlists, and prompt-only guidance provide different constraints; DeepSeek Plan is explicitly soft guidance |
| “Full permissions” | May bypass sandboxing or only ordinary prompts; explicit deny, organizational policies, outer containers, and OS permissions require separate inspection |
| “Default” | Must identify the client, interactive/non-interactive entry point, version, and composition; a mode's name alone is insufficient |

These are comparative conclusions drawn from the implementations and documentation above, rather than an experimentally measured safety ranking.

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
